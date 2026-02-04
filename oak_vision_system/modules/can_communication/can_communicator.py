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
from .can_communicator_base import CANCommunicatorBase

if TYPE_CHECKING:
    from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
    from oak_vision_system.modules.data_processing.decision_layer.decision_layer import DecisionLayer
    from oak_vision_system.core.event_bus.event_bus import EventBus

logger = logging.getLogger(__name__)


class CANCommunicator(CANCommunicatorBase, can.Listener):
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
        # 兜底获取决策层单例
        if decision_layer is None:
            from oak_vision_system.modules.data_processing.decision_layer.decision_layer import DecisionLayer
            try:
                decision_layer = DecisionLayer.get_instance()
                logger.info("已自动获取DecisionLayer单例")
            except RuntimeError as e:
                logger.error(f"无法获取DecisionLayer单例: {e}")
                raise
        
        # 兜底获取事件总线单例
        if event_bus is None:
            from oak_vision_system.core.event_bus.event_bus import get_event_bus
            event_bus = get_event_bus()
            logger.info("已自动获取EventBus单例")
        
        # 调用基类初始化
        CANCommunicatorBase.__init__(self, config, decision_layer, event_bus)
        can.Listener.__init__(self)  # 显式初始化can.Listener基类
        
        # CAN总线组件
        self.bus: Optional[can.Bus] = None
        self.notifier: Optional[can.Notifier] = None
        
        # 运行状态管理
        self._is_running = False
        self._running_lock = threading.Lock()
        
        # 警报定时器相关 - 使用单线程循环方案
        self._alert_active = False
        self._alert_thread: Optional[threading.Thread] = None
        self._alert_stop_event = threading.Event()
        self._alert_lock = threading.RLock()
        
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
        with self._running_lock:
            if self._is_running:
                logger.info("CANCommunicator 已在运行")
                return True
            
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
                
                # 设置运行状态
                self._is_running = True
                
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
    
    def stop(self, timeout: float = 5.0) -> bool:
        """
        停止CAN通信，清理资源
        
        Args:
            timeout: 等待Notifier停止的超时时间（秒），默认5.0秒
            
        Returns:
            bool: 停止成功返回True，超时或失败返回False
        
        流程：
        1. 幂等性检查
        2. 停止警报定时器
        3. 取消事件订阅
        4. 停止Notifier（带超时）
        5. 关闭Bus
        6. 检查enable_auto_configure，调用reset_can_interface()
        7. 记录停止日志
        
        注意：
        - 调用顺序很重要：定时器 → 事件 → Notifier → Bus → 接口
        - 确保所有资源都被正确清理
        - 使用锁保护状态变量，确保线程安全
        """
        with self._running_lock:
            # 步骤1: 幂等性检查
            if not self._is_running:
                logger.info("CANCommunicator 未在运行")
                return True
            
            logger.info("正在停止 CANCommunicator...")
            
            # 标记为正在停止（防止并发问题）
            success = True
            
            # 步骤2: 停止警报定时器
            try:
                self._stop_alert_timer()
            except Exception as e:
                logger.error(f"停止警报定时器失败: {e}", exc_info=True)
                success = False
            
            # 步骤3: 取消事件订阅
            if self._person_warning_subscription_id is not None:
                try:
                    self.event_bus.unsubscribe(self._person_warning_subscription_id)
                    logger.info("已取消PERSON_WARNING事件订阅")
                except Exception as e:
                    logger.error(f"取消事件订阅失败: {e}", exc_info=True)
                    success = False
                finally:
                    self._person_warning_subscription_id = None
            
            # 步骤4: 停止Notifier（带超时）
            if self.notifier is not None:
                try:
                    # Notifier.stop() 会等待内部线程结束
                    # 使用 timeout 参数控制等待时间
                    start_time = time.time()
                    self.notifier.stop(timeout=timeout)
                    elapsed = time.time() - start_time
                    
                    # 检查是否超时
                    if elapsed >= timeout:
                        logger.error(f"Notifier 停止超时 ({timeout}s)")
                        success = False
                    else:
                        logger.info("Notifier已停止")
                except Exception as e:
                    logger.error(f"停止Notifier失败: {e}", exc_info=True)
                    success = False
                finally:
                    self.notifier = None
            
            # 步骤5: 关闭Bus
            if self.bus is not None:
                try:
                    self.bus.shutdown()
                    logger.info("CAN总线已关闭")
                except Exception as e:
                    logger.error(f"关闭CAN总线失败: {e}", exc_info=True)
                    success = False
                finally:
                    self.bus = None
            
            # 步骤6: 检查enable_auto_configure，调用reset_can_interface()
            if self.config.enable_auto_configure:
                if sys.platform in ['linux', 'linux2']:
                    logger.info("重置CAN接口...")
                    reset_success = reset_can_interface(
                        channel=self.config.can_channel,
                        sudo_password=self.config.sudo_password
                    )
                    if not reset_success:
                        logger.warning("CAN接口重置失败")
                        success = False
                else:
                    logger.info(f"非Linux系统({sys.platform})，跳过接口重置")
            else:
                logger.info("自动配置已禁用，跳过接口重置")
            
            # 只在成功时清理状态
            if success:
                self._is_running = False
                logger.info("CANCommunicator 已停止")
            else:
                logger.error("CANCommunicator 停止过程中出现错误")
            
            return success
    
    @property
    def is_running(self) -> bool:
        """
        返回 CAN 通信器的运行状态
        
        Returns:
            bool: 正在运行返回 True，否则返回 False
        """
        with self._running_lock:
            return self._is_running
    
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
        
        使用单线程循环方案：创建一个 daemon 线程，循环发送警报帧。
        
        优势：
        - 只创建一个线程，资源效率高
        - 可以按绝对时间补偿漂移
        - 停止逻辑更干净（Event + join）
        - 并发逻辑更简单
        
        注意：使用锁保护状态变量，确保线程安全
        """
        with self._alert_lock:
            # 如果已经在运行，直接返回
            if self._alert_active:
                logger.info("警报定时器已在运行")
                return
            
            # 设置警报激活标志
            self._alert_active = True
            
            # 清除停止事件
            self._alert_stop_event.clear()
            
            # 创建并启动警报线程
            self._alert_thread = threading.Thread(
                target=self._alert_loop,
                name="CANCommunicator-AlertTimer",
                daemon=True  # daemon 线程，主程序退出时自动结束
            )
            self._alert_thread.start()
            
            # 记录警报启动和时间戳（需求8.3）
            logger.info(f"警报定时器已启动，时间戳: {time.time()}")
    
    def _stop_alert_timer(self):
        """
        停止警报定时器
        
        设置停止事件，并等待线程结束。
        
        注意：使用锁保护状态变量，确保线程安全
        """
        with self._alert_lock:
            # 如果未在运行，直接返回
            if not self._alert_active:
                logger.info("警报定时器未在运行")
                return
            
            # 清除警报激活标志
            self._alert_active = False
            
            # 设置停止事件，通知线程退出
            self._alert_stop_event.set()
            
            # 等待线程结束（带超时）
            if self._alert_thread is not None:
                self._alert_thread.join(timeout=1.0)  # 最多等待1秒
                if self._alert_thread.is_alive():
                    logger.warning("警报线程未在超时时间内结束")
                else:
                    logger.debug("警报线程已正常结束")
                self._alert_thread = None
            
            # 记录警报停止和时间戳（需求8.4）
            logger.info(f"警报定时器已停止，时间戳: {time.time()}")
    
    def _alert_loop(self):
        """
        警报发送循环（在独立线程中运行）
        
        循环逻辑：
        1. 检查是否应该继续运行
        2. 发送警报帧
        3. 等待指定间隔（可被停止事件中断）
        4. 重复
        
        优势：
        - 时间精度高，可以补偿发送耗时
        - 停止响应快（Event.wait 可被立即中断）
        - 异常隔离（单个发送失败不影响循环）
        
        注意：
        - 此方法在独立的 daemon 线程中执行
        - 必须包含异常保护，防止线程崩溃
        """
        logger.debug("警报发送线程开始运行")
        
        try:
            while self._alert_active and not self._alert_stop_event.is_set():
                # 发送警报帧
                self._send_alert()
                
                # 等待指定间隔，可被停止事件中断
                interval_seconds = self.config.alert_interval_ms / 1000.0
                if self._alert_stop_event.wait(timeout=interval_seconds):
                    # 停止事件被设置，退出循环
                    break
                    
        except Exception as e:
            logger.error(f"警报发送线程异常: {e}", exc_info=True)
        finally:
            logger.debug("警报发送线程结束运行")
    
    def _send_alert(self):
        """
        发送警报帧
        
        流程：
        1. 编码警报帧（调用CANProtocol.encode_alert()）
        2. 创建can.Message对象
        3. 发送消息
        4. 记录日志（时间戳）
        5. 处理发送异常
        
        注意：
        - 此方法在警报线程中执行
        - 必须包含异常保护，防止单次发送失败影响整个循环
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

