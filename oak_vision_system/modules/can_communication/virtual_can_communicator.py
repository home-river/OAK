"""
虚拟 CAN 通信器模块

提供虚拟 CAN 通信功能，用于 Windows 开发环境和无硬件测试场景。

设计要点：
- 继承 CANCommunicatorBase，提供与真实 CAN 通信器相同的接口
- 订阅并消费 PERSON_WARNING 事件，但不执行硬件操作
- 提供详细的日志输出，说明真实环境下的行为
- 维护统计信息，帮助验证事件流
- 支持坐标请求模拟，用于测试决策层接口
"""

import logging
import time
from typing import Optional, TYPE_CHECKING

from .can_communicator_base import CANCommunicatorBase

if TYPE_CHECKING:
    from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
    from oak_vision_system.modules.data_processing.decision_layer.decision_layer import DecisionLayer
    from oak_vision_system.core.event_bus.event_bus import EventBus

logger = logging.getLogger(__name__)


class VirtualCANCommunicator(CANCommunicatorBase):
    """
    虚拟 CAN 通信器
    
    模拟真实 CAN 通信器的行为，用于开发和测试环境。
    
    功能特点：
    - 订阅 PERSON_WARNING 事件并记录详细日志
    - 模拟坐标请求处理，调用决策层接口
    - 维护统计计数器，跟踪事件处理情况
    - 提供清晰的日志输出，说明真实环境下的行为
    - 支持统计信息查询和重置
    
    使用场景：
    - Windows 开发环境（无 CAN 硬件支持）
    - 单元测试和集成测试
    - 功能验证和调试
    - 事件流验证
    
    注意事项：
    - 仅模拟行为，不执行实际的 CAN 通信
    - 所有日志都会说明真实环境下的对应行为
    - 统计信息可用于验证事件处理的正确性
    
    使用示例：
        config = CANConfigDTO(enable_can=False)
        communicator = VirtualCANCommunicator(config, decision_layer, event_bus)
        
        # 启动虚拟通信器
        success = communicator.start()
        if success:
            print("虚拟 CAN 通信器已启动")
            
        # 查看统计信息
        stats = communicator.get_stats()
        print(f"统计信息: {stats}")
        
        # 模拟坐标请求
        coords = communicator.simulate_coordinate_request()
        print(f"模拟坐标: {coords}")
        
        # 停止通信器
        communicator.stop()
    """
    
    def __init__(
        self,
        config: 'CANConfigDTO',
        decision_layer: 'DecisionLayer',
        event_bus: 'EventBus'
    ):
        """
        初始化虚拟 CAN 通信器
        
        Args:
            config: CAN 配置 DTO，包含所有配置参数
            decision_layer: 决策层实例，用于获取目标坐标
            event_bus: 事件总线实例，用于订阅和发布事件
            
        注意：
            - 虚拟通信器不需要实际的 CAN 硬件配置
            - 所有配置参数仅用于日志输出和行为模拟
            - 统计计数器初始化为 0
        """
        # 调用基类初始化
        super().__init__(config, decision_layer, event_bus)
        
        # 统计计数器
        self.alert_triggered_count = 0      # 警报触发次数
        self.alert_cleared_count = 0        # 警报清除次数
        self.coordinate_request_count = 0   # 坐标请求次数
        
        # 状态标志
        self._alert_active = False          # 当前是否有活跃警报
        self._is_running = False            # 通信器运行状态
        
        # 事件订阅ID（用于取消订阅）
        self._person_warning_subscription_id: Optional[str] = None
        
        logger.info(
            f"VirtualCANCommunicator 已初始化 - "
            f"这是一个虚拟实现，用于开发和测试环境。"
            f"真实环境下会使用 CANCommunicator 进行实际的 CAN 通信。"
        )
        logger.info(
            f"配置信息: interface={config.can_interface}, "
            f"channel={config.can_channel}, bitrate={config.can_bitrate}"
        )
    
    def start(self) -> bool:
        """
        启动虚拟 CAN 通信
        
        模拟真实 CAN 通信器的启动过程：
        1. 检查是否已运行（幂等性）
        2. 订阅 PERSON_WARNING 事件
        3. 设置运行状态标志
        4. 输出启动日志和功能说明
        
        Returns:
            bool: 启动成功返回 True，失败返回 False
            
        注意：
            - 虚拟实现总是成功启动（无硬件依赖）
            - 会订阅真实的事件总线事件
            - 日志会说明真实环境下的对应行为
        """
        try:
            # 检查是否已运行（幂等性）
            if self._is_running:
                logger.info("VirtualCANCommunicator 已在运行")
                return True
            
            logger.info("正在启动 VirtualCANCommunicator...")
            
            # 订阅 PERSON_WARNING 事件
            from oak_vision_system.core.event_bus.event_types import EventType
            self._person_warning_subscription_id = self.event_bus.subscribe(
                event_type=EventType.PERSON_WARNING,
                callback=self._on_person_warning,
                subscriber_name="VirtualCANCommunicator._on_person_warning"
            )
            
            # 设置运行状态
            self._is_running = True
            
            # 输出详细的启动日志
            logger.info("=" * 60)
            logger.info("🚀 虚拟 CAN 通信器已启动")
            logger.info("=" * 60)
            logger.info("📋 功能说明:")
            logger.info("  • 这是一个虚拟实现，用于开发和测试环境")
            logger.info("  • 会订阅 PERSON_WARNING 事件并记录详细日志")
            logger.info("  • 支持坐标请求模拟，调用真实的决策层接口")
            logger.info("  • 维护统计计数器，帮助验证事件流")
            logger.info("")
            logger.info("⚠️  真实环境行为说明:")
            logger.info("  • 真实环境下会使用 CANCommunicator 连接实际的 CAN 总线")
            logger.info(f"  • 会连接到 {self.config.can_interface} 接口")
            logger.info(f"  • 使用通道 {self.config.can_channel}，波特率 {self.config.can_bitrate}")
            logger.info("  • 会发送实际的 CAN 消息到硬件设备")
            logger.info("  • 会接收来自硬件的坐标请求消息")
            logger.info("")
            logger.info("🔧 当前配置:")
            logger.info(f"  • CAN 接口: {self.config.can_interface}")
            logger.info(f"  • CAN 通道: {self.config.can_channel}")
            logger.info(f"  • 波特率: {self.config.can_bitrate}")
            logger.info(f"  • 警报间隔: {self.config.alert_interval_ms}ms")
            logger.info(f"  • 发送超时: {self.config.send_timeout_ms}ms")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"启动 VirtualCANCommunicator 时发生异常: {e}", exc_info=True)
            return False
    
    def stop(self, timeout: float = 5.0) -> bool:
        """
        停止虚拟 CAN 通信，清理资源
        
        模拟真实 CAN 通信器的停止过程：
        1. 检查是否正在运行（幂等性）
        2. 取消事件订阅
        3. 设置运行状态标志
        4. 输出统计信息日志
        
        Args:
            timeout: 等待资源清理的超时时间（秒），虚拟实现中不使用
            
        Returns:
            bool: 停止成功返回 True，失败返回 False
            
        注意：
            - 虚拟实现总是成功停止（无硬件依赖）
            - 会取消真实的事件总线订阅
            - 会输出完整的统计信息
        """
        try:
            # 检查是否正在运行（幂等性）
            if not self._is_running:
                logger.info("VirtualCANCommunicator 未在运行")
                return True
            
            logger.info("正在停止 VirtualCANCommunicator...")
            
            # 取消事件订阅
            if self._person_warning_subscription_id is not None:
                try:
                    self.event_bus.unsubscribe(self._person_warning_subscription_id)
                    logger.info("已取消 PERSON_WARNING 事件订阅")
                except Exception as e:
                    logger.error(f"取消事件订阅失败: {e}", exc_info=True)
                finally:
                    self._person_warning_subscription_id = None
            
            # 设置运行状态
            self._is_running = False
            self._alert_active = False
            
            # 输出统计信息日志
            logger.info("=" * 60)
            logger.info("🛑 虚拟 CAN 通信器已停止")
            logger.info("=" * 60)
            logger.info("📊 运行统计:")
            logger.info(f"  • 警报触发次数: {self.alert_triggered_count}")
            logger.info(f"  • 警报清除次数: {self.alert_cleared_count}")
            logger.info(f"  • 坐标请求次数: {self.coordinate_request_count}")
            logger.info(f"  • 当前警报状态: {'活跃' if self._alert_active else '非活跃'}")
            logger.info("")
            logger.info("⚠️  真实环境行为说明:")
            logger.info("  • 真实环境下会停止 CAN 总线连接")
            logger.info("  • 会停止警报定时器线程")
            logger.info("  • 会关闭 CAN 消息监听器")
            logger.info("  • 会清理所有 CAN 相关资源")
            if self.config.enable_auto_configure:
                logger.info("  • 会重置 CAN 接口配置（如果启用了自动配置）")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"停止 VirtualCANCommunicator 时发生异常: {e}", exc_info=True)
            return False
    
    @property
    def is_running(self) -> bool:
        """
        返回虚拟 CAN 通信器的运行状态
        
        Returns:
            bool: 正在运行返回 True，否则返回 False
            
        注意：
            - 状态与 start/stop 方法保持一致
            - 虚拟实现中无需线程同步（无并发访问）
        """
        return self._is_running
    
    def _on_person_warning(self, event_data: dict):
        """
        处理人员警报事件（事件总线回调）
        
        模拟真实 CAN 通信器的事件处理：
        - TRIGGERED 状态：记录警报触发，模拟启动警报定时器
        - CLEARED 状态：记录警报清除，模拟停止警报定时器
        
        Args:
            event_data: 事件数据，格式：
                {
                    "status": PersonWarningStatus,  # TRIGGERED 或 CLEARED
                    "timestamp": float              # Unix 时间戳
                }
        
        注意：
            - 此方法在事件总线的线程中执行
            - 会更新统计计数器和状态标志
            - 输出详细日志说明真实环境下的行为
        """
        try:
            # 解析 event_data 获取 status 和 timestamp
            from oak_vision_system.modules.data_processing.decision_layer.types import PersonWarningStatus
            
            status = event_data.get("status")
            timestamp = event_data.get("timestamp", time.time())
            
            if status == PersonWarningStatus.TRIGGERED:
                # 处理 TRIGGERED 状态
                self._alert_active = True
                self.alert_triggered_count += 1
                
                # 输出详细警告日志
                logger.warning("=" * 60)
                logger.warning("🚨 人员警报已触发 (TRIGGERED)")
                logger.warning("=" * 60)
                logger.warning(f"📅 事件时间戳: {timestamp}")
                logger.warning(f"📊 触发次数统计: {self.alert_triggered_count}")
                logger.warning("")
                logger.warning("⚠️  真实环境行为说明:")
                logger.warning("  • 真实环境下会启动 CAN 警报定时器")
                logger.warning(f"  • 会每隔 {self.config.alert_interval_ms}ms 发送警报帧到 CAN 总线")
                logger.warning("  • 警报帧会通知外部设备（如机械臂控制器）停止操作")
                logger.warning("  • 警报帧格式符合 CAN 协议规范")
                logger.warning("  • 会持续发送直到收到 CLEARED 事件")
                logger.warning("")
                logger.warning("🔧 虚拟模拟行为:")
                logger.warning("  • 设置内部警报状态为活跃")
                logger.warning("  • 增加触发次数统计计数器")
                logger.warning("  • 记录详细的事件日志")
                logger.warning("=" * 60)
                
            elif status == PersonWarningStatus.CLEARED:
                # 处理 CLEARED 状态
                self._alert_active = False
                self.alert_cleared_count += 1
                
                # 输出详细信息日志
                logger.info("=" * 60)
                logger.info("✅ 人员警报已清除 (CLEARED)")
                logger.info("=" * 60)
                logger.info(f"📅 事件时间戳: {timestamp}")
                logger.info(f"📊 清除次数统计: {self.alert_cleared_count}")
                logger.info("")
                logger.info("⚠️  真实环境行为说明:")
                logger.info("  • 真实环境下会停止 CAN 警报定时器")
                logger.info("  • 会停止向 CAN 总线发送警报帧")
                logger.info("  • 外部设备（如机械臂控制器）可以恢复正常操作")
                logger.info("  • 会清理警报相关的线程和资源")
                logger.info("")
                logger.info("🔧 虚拟模拟行为:")
                logger.info("  • 设置内部警报状态为非活跃")
                logger.info("  • 增加清除次数统计计数器")
                logger.info("  • 记录详细的事件日志")
                logger.info("=" * 60)
                
            else:
                logger.warning(f"收到未知的人员警报状态: {status}")
                
        except Exception as e:
            logger.error(f"处理人员警报事件时发生异常: {e}", exc_info=True)
    
    def simulate_coordinate_request(self) -> tuple[int, int, int]:
        """
        模拟坐标请求处理
        
        模拟真实 CAN 通信器接收到坐标请求消息时的处理流程：
        1. 增加坐标请求统计计数器
        2. 调用决策层获取目标坐标
        3. 处理返回 None 的情况（兜底坐标 0,0,0）
        4. 转换坐标为整数（毫米单位）
        5. 输出详细日志说明真实环境下的行为
        6. 返回坐标元组
        
        Returns:
            tuple[int, int, int]: 坐标元组 (x, y, z)，单位：毫米
            
        注意：
            - 调用真实的决策层接口，获取实际的目标坐标
            - 包含完善的异常处理和兜底逻辑
            - 输出详细日志说明真实环境下的 CAN 通信行为
            
        使用示例：
            coords = communicator.simulate_coordinate_request()
            print(f"获取到坐标: x={coords[0]}, y={coords[1]}, z={coords[2]}")
        """
        start_time = time.time()
        
        try:
            # 增加坐标请求统计计数器
            self.coordinate_request_count += 1
            
            logger.info("=" * 60)
            logger.info("📍 模拟坐标请求处理")
            logger.info("=" * 60)
            logger.info(f"📊 请求次数统计: {self.coordinate_request_count}")
            
            # 调用决策层获取目标坐标
            coords = self.decision_layer.get_target_coords_snapshot()
            
            # 处理返回 None 的情况（兜底坐标 0,0,0）
            if coords is None:
                x, y, z = 0, 0, 0
                logger.info("🎯 决策层返回: None（无目标）")
                logger.info("🔧 使用兜底坐标: (0, 0, 0)")
            else:
                # 转换坐标为整数（毫米单位）
                # 假设决策层返回的坐标单位是米，转换为毫米
                x = int(coords[0] * 1000)  # 米 -> 毫米
                y = int(coords[1] * 1000)  # 米 -> 毫米
                z = int(coords[2] * 1000)  # 米 -> 毫米
                logger.info(f"🎯 决策层返回: ({coords[0]:.3f}, {coords[1]:.3f}, {coords[2]:.3f}) 米")
                logger.info(f"🔧 转换为整数: ({x}, {y}, {z}) 毫米")
            
            # 计算处理时间
            processing_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            # 输出详细日志说明真实环境下的行为
            logger.info("")
            logger.info("⚠️  真实环境行为说明:")
            logger.info("  • 真实环境下会接收来自 CAN 总线的坐标请求消息")
            logger.info("  • 请求消息由外部设备（如机械臂控制器）发送")
            logger.info("  • 会调用相同的决策层接口获取目标坐标")
            logger.info("  • 会将坐标编码为 CAN 消息格式")
            logger.info(f"  • 会通过 CAN 总线发送响应消息（目标响应时间 < 10ms）")
            logger.info("  • 响应消息包含 x, y, z 坐标（毫米单位）")
            logger.info("")
            logger.info("🔧 虚拟模拟行为:")
            logger.info("  • 调用真实的决策层接口")
            logger.info("  • 执行相同的坐标转换逻辑")
            logger.info("  • 记录详细的处理日志")
            logger.info("  • 返回处理后的坐标数据")
            logger.info("")
            logger.info(f"⏱️  处理时间: {processing_time:.2f}ms")
            logger.info(f"📤 返回坐标: x={x}, y={y}, z={z} (毫米)")
            logger.info("=" * 60)
            
            return (x, y, z)
            
        except Exception as e:
            # 异常处理：使用兜底坐标
            logger.error(f"模拟坐标请求处理时发生异常: {e}", exc_info=True)
            logger.warning("🔧 异常处理: 使用兜底坐标 (0, 0, 0)")
            
            # 计算处理时间（即使异常也要记录）
            processing_time = (time.time() - start_time) * 1000
            logger.info(f"⏱️  处理时间: {processing_time:.2f}ms")
            
            return (0, 0, 0)
    
    def get_stats(self) -> dict:
        """
        获取虚拟 CAN 通信器的统计信息
        
        返回包含所有统计信息的字典，用于监控和调试。
        
        Returns:
            dict: 统计信息字典，包含以下字段：
                - is_running: bool - 通信器运行状态
                - alert_active: bool - 当前警报状态
                - alert_triggered_count: int - 警报触发次数
                - alert_cleared_count: int - 警报清除次数
                - coordinate_request_count: int - 坐标请求次数
                
        使用示例：
            stats = communicator.get_stats()
            print(f"运行状态: {stats['is_running']}")
            print(f"警报触发次数: {stats['alert_triggered_count']}")
        """
        return {
            "is_running": self._is_running,
            "alert_active": self._alert_active,
            "alert_triggered_count": self.alert_triggered_count,
            "alert_cleared_count": self.alert_cleared_count,
            "coordinate_request_count": self.coordinate_request_count
        }
    
    def reset_stats(self):
        """
        重置虚拟 CAN 通信器的统计计数器
        
        将所有统计计数器重置为 0，用于测试和调试。
        
        注意：
            - 不会重置运行状态和警报状态
            - 仅重置计数器（alert_triggered_count, alert_cleared_count, coordinate_request_count）
            - 会输出重置日志
            
        使用示例：
            communicator.reset_stats()
            print("统计信息已重置")
        """
        # 重置所有统计计数器
        old_triggered = self.alert_triggered_count
        old_cleared = self.alert_cleared_count
        old_requests = self.coordinate_request_count
        
        self.alert_triggered_count = 0
        self.alert_cleared_count = 0
        self.coordinate_request_count = 0
        
        # 输出重置日志
        logger.info("=" * 60)
        logger.info("🔄 统计信息已重置")
        logger.info("=" * 60)
        logger.info("📊 重置前统计:")
        logger.info(f"  • 警报触发次数: {old_triggered}")
        logger.info(f"  • 警报清除次数: {old_cleared}")
        logger.info(f"  • 坐标请求次数: {old_requests}")
        logger.info("")
        logger.info("📊 重置后统计:")
        logger.info(f"  • 警报触发次数: {self.alert_triggered_count}")
        logger.info(f"  • 警报清除次数: {self.alert_cleared_count}")
        logger.info(f"  • 坐标请求次数: {self.coordinate_request_count}")
        logger.info("")
        logger.info("ℹ️  注意: 运行状态和警报状态未被重置")
        logger.info(f"  • 运行状态: {self._is_running}")
        logger.info(f"  • 警报状态: {self._alert_active}")
        logger.info("=" * 60)