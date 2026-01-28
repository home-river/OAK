"""
CAN通信模块

提供CAN总线通信功能，包括：
- CAN接口配置工具
- CAN消息监听和处理
- 协议编解码
- 与决策层和事件总线的集成
"""

from .can_interface_config import configure_can_interface, reset_can_interface
from .can_protocol import CANProtocol
from .can_communicator import CANCommunicator

__all__ = [
    'configure_can_interface',
    'reset_can_interface',
    'CANProtocol',
    'CANCommunicator',
]
