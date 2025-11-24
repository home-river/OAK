"""
OAK视觉系统功能模块包

提供设备发现、配置管理等核心功能模块。
"""

# 设备发现模块
from .config_manager.device_discovery import OAKDeviceDiscovery

# 设备配置管理模块
from .config_manager.device_config_manager import (
    DeviceConfigManager,
    MatchResultType,
    DeviceMatchResult,
    ConfigNotFoundError,
    ConfigValidationError,
)

__all__ = [
    # 设备发现
    'OAKDeviceDiscovery',
    
    # 配置管理
    'DeviceConfigManager',
    'MatchResultType',
    'DeviceMatchResult',
    'ConfigNotFoundError',
    'ConfigValidationError',
]
