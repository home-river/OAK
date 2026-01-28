"""
CAN通信管理器模块

提供CAN通信的核心管理功能，包括：
- CANCommunicator: 主通信管理器，协调所有组件并实现消息监听

设计要点：
- 事件驱动回调架构，使用python-can的Notifier/Listener机制
- CANCommunicator直接实现can.Listener接口，消除循环引用
- 线程安全的决策层接口调用
- 异常保护，防止回调崩溃
- 完整的日志记录和错误处理
"""

import logging
import sys
import threading
import time
from typing import Optional, TYPE_CHECKING
import can
import numpy as np

from .can_protocol import CANProtocol
from .can_interface_config import configure_can_interface, reset_can_interface

if TYPE_CHECKING:
    from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
    from oak_vision_system.modules.data_processing.decision_layer.decision_layer import DecisionLayer
    from oak_vision_system.core.event_bus.event_bus import EventBus

logger = logging.getLogger(__name__)


class CANCommunicator(can.Listener):
    """
    CAN通信管理器
    
    直接实现can.Listener接口，协调CAN通信的所有组件，包括：
    - Bus连接管理
    - 消息监听和处理（实现can.Listener接口）
    - 坐标请求响应处理
    - 人员警报定时发送
    - 事件总线订阅
    
    职责：
    - 管理CAN总线连接生命周期
    - 接收并处理CAN消息（on_message_received回调）
    - 处理坐标请求并调用决策层
    - 订阅事件总线，处理人员警报
    - 提供统一的对外接口
    
    设计说明：
    - 直接继承can.Listener，消除了CANMessageListener的循环引用
    - 在python-can的内部线程中执行on_message_received回调
    - 所有回调方法都包含异常保护，防止线程崩溃
    """
    
    def __init__(
        self,
        config: 'CANConfigDTO',
        decision_layer: Optional['DecisionLayer'] = None,
        event_bus: Optional['EventBus'] = None
    ):
        """
        初始化CAN通信管理器
        
        Args:
            config: CAN配置DTO
            decision_layer: 决策层实例（可选，如果为None则尝试获取单例）
            event_bus: 事件总线实例（可选，如果为None则尝试获取单例）
            
        Raises:
            RuntimeError: 如果decision_layer为None且单例未初始化
        """
        super().__init__()  # 初始化can.Listener基类
        self.config = config
        
        # 兜底获取决策层单例
        if decision_layer is None:
            from oak_vision_system.modules.data_processing.decision_layer.decision_layer import DecisionLayer
            try:
                self.decision_layer = DecisionLayer.get_instance()
                logger.info("已自动获取DecisionLayer单例")
            except RuntimeError as e:
                logger.error(f"无法获取DecisionLayer单例: {e}")
                raise
        else:
            self.decision_layer = decision_layer
        
        # 兜底获取事件总线单例
        if event_bus is None:
            from oak_vision_system.core.event_bus.event_bus import get_event_bus
            self.event_bus = get_event_bus()
            logger.info("已自动获取EventBus单例")
        else:
            self.event_bus = event_bus
        
        # CAN总线组件
        self.bus: Optional[can.Bus] = None
        self.notifier: Optional[can.Notifier] = None
        
        # 警报定时器相关
        self._alert_active = False
        self._alert_timer: Optional[threading.Timer] = None
        
        # 事件订阅ID（用于取消订阅）
        self._person_warning_subscription_id: Optional[str] = None
        
        logger.info("CANCommunicator已初始化")
    
    def on_message_received(self, msg: can.Message):
        """
        消息到达时的回调（python-can内部线程调用）
        
        实现can.Listener接口的回调方法。
        
        Args:
            msg: 接收到的CAN消息
            
        注意：
        - 此方法在python-can的内部线程中执行
        - 必须包含异常保护，防止回调崩溃导致Notifier线程终止
        - 执行时间应尽量短（< 1ms），避免阻塞后续消息接收
        """
        try:
            # 识别消息类型
            msg_type = CANProtocol.identify_message(msg)
            
            if msg_type is None:
                # 无法识别的消息，忽略
                return
            
            # 根据消息类型路由到对应的处理器
            if msg_type == "coordinate_request":
                self.handle_coordinate_request()
            else:
                logger.warning(f"收到未处理的消息类型: {msg_type}")
                
        except can.CanError as e:
            # 捕获CAN总线错误（需求9.4）
            logger.error(f"CAN总线错误: {e}", exc_info=True)
            # 不抛出异常，避免Notifier线程崩溃
        except Exception as e:
            # 捕获所有其他异常，防止回调崩溃
            logger.error(f"CAN消息处理异常: {e}", exc_info=True)
    
    def handle_coordinate_request(self):
        """
        处理坐标请求
        
        流程：
        1. 调用decision_layer.get_target_coords_snapshot()获取坐标
        2. 如果返回None或抛异常，使用兜底坐标(0, 0, 0)
        3. 编码响应帧
        4. 发送响应
        5. 记录日志
        
        要求：
        - 从接收请求到发送响应应在10ms内完成
        - 线程安全（决策层接口已提供锁保护）
        - 异常容错，确保总能发送响应
        """
        start_time = time.time()
        
        try:
            # 调用决策层获取目标坐标
            coords = self.decision_layer.get_target_coords_snapshot()
            
            # 处理返回None的情况（兜底逻辑）
            if coords is None:
                x, y, z = 0, 0, 0
            else:
                # 将numpy数组转换为整数坐标（毫米）
                x = int(coords[0])
                y = int(coords[1])
                z = int(coords[2])
                
        except Exception as e:
            # 处理异常情况（兜底逻辑）
            logger.error(f"获取坐标失败: {e}", exc_info=True)
            x, y, z = 0, 0, 0
        
        try:
            # 编码响应帧
            data = CANProtocol.encode_coordinate_response(x, y, z)
            
            # 创建CAN消息
            msg = can.Message(
                arbitration_id=CANProtocol.FRAME_ID,
                data=data,
                is_extended_id=False
            )
            
            # 发送响应
            if self.bus is not None:
                self.bus.send(msg, timeout=self.config.send_timeout_ms / 1000.0)
                
                # 计算响应时间
                response_time = (time.time() - start_time) * 1000  # 转换为毫秒
                
                # 记录日志（坐标值和时间戳）
                logger.info(
                    f"发送坐标响应: x={x}, y={y}, z={z}, "
                    f"响应时间={response_time:.2f}ms"
                )
            else:
                logger.error("CAN总线未初始化，无法发送响应")
                
        except can.CanError as e:
            logger.error(f"发送坐标响应失败: {e}", exc_info=True)
            # 继续运行，不中断（需求9.2）
        except Exception as e:
            logger.error(f"处理坐标响应时发生异常: {e}", exc_info=True)
    
    def start(self) -> bool:
        """
        启动CAN通信
        
        流程：
        1. 检查enable_auto_configure，调用configure_can_interface()
        2. 创建can.Bus对象
        3. 创建can.Notifier实例（使用self作为Listener）
        4. 订阅Event_Bus的PERSON_WARNING事件
        5. 记录启动日志
        6. 处理连接失败异常
        
        Returns:
            bool: 启动成功返回True，失败返回False
        """
        try:
            # 步骤1: 检查是否需要自动配置CAN接口
            if self.config.enable_auto_configure:
                # 检查是否为Linux系统
                if sys.platform in ['linux', 'linux2']:
                    logger.info("开始自动配置CAN接口...")
                    success = configure_can_interface(
                        channel=self.config.can_channel,
                        bitrate=self.config.can_bitrate,
                        sudo_password=self.config.sudo_password
                    )
                    if not success:
                        logger.error("CAN接口自动配置失败，请手动配置")
                        # 继续尝试连接，可能接口已经手动配置好了
                else:
                    logger.info(f"非Linux系统({sys.platform})，跳过自动配置")
            else:
                logger.info("自动配置已禁用，假设接口已手动配置")
            
            # 步骤2: 创建can.Bus对象
            logger.info(
                f"连接CAN总线: interface={self.config.can_interface}, "
                f"channel={self.config.can_channel}, bitrate={self.config.can_bitrate}"
            )
            self.bus = can.Bus(
                interface=self.config.can_interface,
                channel=self.config.can_channel,
                bitrate=self.config.can_bitrate
            )
            
            # 步骤3: 创建can.Notifier实例（使用self作为Listener）
            # Notifier会自动创建内部线程来监听CAN总线
            # 直接传入self，因为CANCommunicator已经实现了can.Listener接口
            self.notifier = can.Notifier(self.bus, [self])
            
            # 步骤4: 订阅Event_Bus的PERSON_WARNING事件
            from oak_vision_system.core.event_bus.event_types import EventType
            self._person_warning_subscription_id = self.event_bus.subscribe(
                event_type=EventType.PERSON_WARNING,
                callback=self._on_person_warning,
                subscriber_name="CANCommunicator._on_person_warning"
            )
            
            # 步骤5: 记录启动日志
            logger.info(
                f"CAN通信已启动: interface={self.config.can_interface}, "
                f"channel={self.config.can_channel}, bitrate={self.config.can_bitrate}, "
                f"auto_configure={self.config.enable_auto_configure}"
            )
            
            return True
            
        except can.CanError as e:
            # 步骤6: 处理连接失败异常
            logger.error(f"CAN总线连接失败: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"启动CAN通信时发生异常: {e}", exc_info=True)
            return False
    
    def stop(self):
        """
        停止CAN通信，清理资源
        
        流程：
        1. 停止警报定时器
        2. 取消事件订阅
        3. 停止Notifier
        4. 关闭Bus
        5. 检查enable_auto_configure，调用reset_can_interface()
        6. 记录停止日志
        
        注意：
        - 调用顺序很重要：定时器 → 事件 → Notifier → Bus → 接口
        - 确保所有资源都被正确清理
        """
        logger.info("开始停止CAN通信...")
        
        # 步骤1: 停止警报定时器
        self._stop_alert_timer()
        
        # 步骤2: 取消事件订阅
        if self._person_warning_subscription_id is not None:
            try:
                self.event_bus.unsubscribe(self._person_warning_subscription_id)
                logger.info("已取消PERSON_WARNING事件订阅")
            except Exception as e:
                logger.error(f"取消事件订阅失败: {e}", exc_info=True)
            finally:
                self._person_warning_subscription_id = None
        
        # 步骤3: 停止Notifier
        if self.notifier is not None:
            try:
                self.notifier.stop()
                logger.info("Notifier已停止")
            except Exception as e:
                logger.error(f"停止Notifier失败: {e}", exc_info=True)
            finally:
                self.notifier = None
        
        # 步骤4: 关闭Bus
        if self.bus is not None:
            try:
                self.bus.shutdown()
                logger.info("CAN总线已关闭")
            except Exception as e:
                logger.error(f"关闭CAN总线失败: {e}", exc_info=True)
            finally:
                self.bus = None
        
        # 步骤5: 检查enable_auto_configure，调用reset_can_interface()
        if self.config.enable_auto_configure:
            if sys.platform in ['linux', 'linux2']:
                logger.info("重置CAN接口...")
                success = reset_can_interface(
                    channel=self.config.can_channel,
                    sudo_password=self.config.sudo_password
                )
                if not success:
                    logger.warning("CAN接口重置失败")
            else:
                logger.info(f"非Linux系统({sys.platform})，跳过接口重置")
        else:
            logger.info("自动配置已禁用，跳过接口重置")
        
        # 步骤6: 记录停止日志
        logger.info("CAN通信已停止")
    
    def _on_person_warning(self, event_data: dict):
        """
        处理人员警报事件（事件总线回调）
        
        根据事件状态启动或停止警报定时器：
        - status=TRIGGERED: 启动警报定时器
        - status=CLEARED: 停止警报定时器
        
        Args:
            event_data: 事件数据，格式：
                {
                    "status": PersonWarningStatus,  # TRIGGERED 或 CLEARED
                    "timestamp": float              # Unix 时间戳
                }
        
        注意：
        - 此方法在事件总线的线程中执行
        - 仅负责启动/停止定时器，不阻塞事件总线
        """
        try:
            # 解析event_data获取status
            from oak_vision_system.modules.data_processing.decision_layer.types import PersonWarningStatus
            
            status = event_data.get("status")
            timestamp = event_data.get("timestamp", time.time())
            
            if status == PersonWarningStatus.TRIGGERED:
                # 启动警报定时器
                logger.info(f"收到人员警报TRIGGERED事件，时间戳: {timestamp}")
                self._start_alert_timer()
            elif status == PersonWarningStatus.CLEARED:
                # 停止警报定时器
                logger.info(f"收到人员警报CLEARED事件，时间戳: {timestamp}")
                self._stop_alert_timer()
            else:
                logger.warning(f"收到未知的人员警报状态: {status}")
                
        except Exception as e:
            logger.error(f"处理人员警报事件时发生异常: {e}", exc_info=True)
    
    def _start_alert_timer(self):
        """
        启动警报定时器
        
        设置_alert_active标志为True，并调用_schedule_next_alert()
        开始周期性发送警报帧。
        """
        # 设置警报激活标志
        self._alert_active = True
        
        # 调度第一次警报发送
        self._schedule_next_alert()
        
        # 记录警报启动和时间戳（需求8.3）
        logger.info(f"警报定时器已启动，时间戳: {time.time()}")
    
    def _stop_alert_timer(self):
        """
        停止警报定时器
        
        设置_alert_active标志为False，并取消当前定时器（如果存在）。
        """
        # 清除警报激活标志
        self._alert_active = False
        
        # 取消当前定时器
        if self._alert_timer is not None:
            self._alert_timer.cancel()
            self._alert_timer = None
        
        # 记录警报停止和时间戳（需求8.4）
        logger.info(f"警报定时器已停止，时间戳: {time.time()}")
    
    def _schedule_next_alert(self):
        """
        调度下一次警报发送
        
        检查_alert_active标志，如果为True则创建threading.Timer，
        间隔为alert_interval_ms，回调为_send_alert()。
        
        使用递归调度方式实现周期发送：每次发送后调度下一次。
        """
        # 检查警报是否仍然激活
        if not self._alert_active:
            return
        
        # 计算间隔（转换为秒）
        interval_seconds = self.config.alert_interval_ms / 1000.0
        
        # 创建定时器
        self._alert_timer = threading.Timer(interval_seconds, self._send_alert)
        
        # 启动定时器
        self._alert_timer.start()
    
    def _send_alert(self):
        """
        发送警报帧（定时器回调）
        
        流程：
        1. 编码警报帧（调用CANProtocol.encode_alert()）
        2. 创建can.Message对象
        3. 发送消息
        4. 记录日志（时间戳）
        5. 处理发送异常
        6. 调用_schedule_next_alert()实现递归调度
        
        注意：
        - 此方法在定时器线程中执行
        - 必须包含异常保护，防止定时器线程崩溃
        """
        try:
            # 步骤1: 编码警报帧
            data = CANProtocol.encode_alert()
            
            # 步骤2: 创建can.Message对象
            msg = can.Message(
                arbitration_id=CANProtocol.FRAME_ID,
                data=data,
                is_extended_id=False
            )
            
            # 步骤3: 发送消息
            if self.bus is not None:
                self.bus.send(msg, timeout=self.config.send_timeout_ms / 1000.0)
                
                # 步骤4: 记录日志（时间戳）
                logger.info(f"发送警报帧，时间戳: {time.time()}")
            else:
                logger.error("CAN总线未初始化，无法发送警报")
                
        except can.CanError as e:
            # 步骤5: 处理发送异常（需求9.2）
            logger.warning(f"发送警报帧超时或失败: {e}")
            # 继续运行，不中断警报流程
        except Exception as e:
            logger.error(f"发送警报时发生异常: {e}", exc_info=True)
        finally:
            # 步骤6: 调用_schedule_next_alert()实现递归调度
            self._schedule_next_alert()

