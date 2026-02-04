"""
CAN通信模块

提供CAN总线通信功能，包括：
- CAN接口配置工具
- CAN消息监听和处理
- 协议编解码
- 与决策层和事件总线的集成
- 真实和虚拟CAN通信器实现
- 工厂函数用于自动选择合适的实现
"""

from .can_interface_config import configure_can_interface, reset_can_interface
from .can_protocol import CANProtocol
from .can_communicator_base import CANCommunicatorBase
from .can_communicator import CANCommunicator
from .virtual_can_communicator import VirtualCANCommunicator
from .can_factory import create_can_communicator

__all__ = [
    # 配置工具（向后兼容）
    'configure_can_interface',
    'reset_can_interface',
    
    # 协议支持（向后兼容）
    'CANProtocol',
    
    # 通信器基类和实现
    'CANCommunicatorBase',      # 抽象基类
    'CANCommunicator',          # 真实CAN通信器（向后兼容）
    'VirtualCANCommunicator',   # 虚拟CAN通信器
    
    # 工厂函数
    'create_can_communicator',  # 推荐使用的创建方式
]
