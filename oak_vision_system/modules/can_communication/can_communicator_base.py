"""
CAN 通信器抽象基类

提供 CAN 通信器的抽象接口，支持真实和虚拟实现。

设计要点：
- 定义统一的接口规范（start, stop, is_running）
- 使用 TYPE_CHECKING 避免循环导入
- 子类必须实现所有抽象方法
- 提供完整的文档字符串和类型提示
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
    from oak_vision_system.modules.data_processing.decision_layer.decision_layer import DecisionLayer
    from oak_vision_system.core.event_bus.event_bus import EventBus

logger = logging.getLogger(__name__)


class CANCommunicatorBase(ABC):
    """
    CAN 通信器抽象基类
    
    定义 CAN 通信器的统一接口，支持真实硬件和虚拟模拟两种实现。
    
    职责：
    - 定义 CAN 通信器的核心接口（start, stop, is_running）
    - 管理配置、决策层和事件总线的引用
    - 提供子类实现的规范
    
    子类必须实现：
    - start(): 启动 CAN 通信
    - stop(): 停止 CAN 通信
    - is_running 属性: 返回运行状态
    
    使用示例：
        # 真实 CAN 实现
        communicator = CANCommunicator(config, decision_layer, event_bus)
        communicator.start()
        
        # 虚拟 CAN 实现
        communicator = VirtualCANCommunicator(config, decision_layer, event_bus)
        communicator.start()
    """
    
    def __init__(
        self,
        config: 'CANConfigDTO',
        decision_layer: 'DecisionLayer',
        event_bus: 'EventBus'
    ):
        """
        初始化 CAN 通信器基类
        
        Args:
            config: CAN 配置 DTO，包含所有配置参数
            decision_layer: 决策层实例，用于获取目标坐标
            event_bus: 事件总线实例，用于订阅和发布事件
            
        注意：
            - 子类必须在 __init__ 方法开头调用此方法
            - 此方法仅保存引用，不执行任何初始化逻辑
        """
        self.config = config
        self.decision_layer = decision_layer
        self.event_bus = event_bus
        
        logger.debug(f"{self.__class__.__name__} 基类已初始化")
    
    @abstractmethod
    def start(self) -> bool:
        """
        启动 CAN 通信
        
        子类必须实现此方法，执行以下操作：
        1. 初始化必要的资源（总线连接、事件订阅等）
        2. 设置运行状态标志
        3. 记录启动日志
        4. 处理启动失败的异常
        
        Returns:
            bool: 启动成功返回 True，失败返回 False
            
        注意：
            - 必须支持幂等性（重复调用不会出错）
            - 必须包含完善的异常处理
            - 失败时应记录详细的错误日志
        """
        pass
    
    @abstractmethod
    def stop(self, timeout: float = 5.0) -> bool:
        """
        停止 CAN 通信，清理资源
        
        子类必须实现此方法，执行以下操作：
        1. 检查运行状态（幂等性）
        2. 停止所有定时器和线程
        3. 取消事件订阅
        4. 关闭总线连接（如果有）
        5. 清理所有资源
        6. 记录停止日志
        
        Args:
            timeout: 等待资源清理的超时时间（秒），默认 5.0 秒
            
        Returns:
            bool: 停止成功返回 True，超时或失败返回 False
            
        注意：
            - 必须支持幂等性（重复调用不会出错）
            - 必须确保所有资源都被正确清理
            - 超时时应记录警告日志
            - 即使部分清理失败，也应尽量清理其他资源
        """
        pass
    
    @property
    @abstractmethod
    def is_running(self) -> bool:
        """
        返回 CAN 通信器的运行状态
        
        Returns:
            bool: 正在运行返回 True，否则返回 False
            
        注意：
            - 此属性必须线程安全
            - 状态应与 start/stop 方法保持一致
        """
        pass
