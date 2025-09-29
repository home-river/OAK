"""
OAK Vision 模块包
包含OAK设备管理、坐标修正、CAN通信等核心功能模块
"""

from .oak_device_manager import OAKDeviceManager
from .coordinate_corrector import CoordinateCorrector
from .can_module import CANCommunicator
from .calculate_module import FilteredCalculateModule

__all__ = [
    'OAKDeviceManager',
    'CoordinateCorrector', 
    'CANCommunicator',
    'FilteredCalculateModule'
]

__version__ = '1.0.0'
