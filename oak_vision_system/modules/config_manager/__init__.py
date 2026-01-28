"""配置管理子包

提供设备配置管理和格式转换功能。

主要组件：
- DeviceConfigManager: 设备配置管理器
- ConfigConverter: 配置格式转换器（JSON ↔ YAML）
- OAKDeviceDiscovery: 设备发现
- DeviceMatchManager: 设备匹配管理器
"""

from .device_config_manager import DeviceConfigManager
from .config_converter import ConfigConverter
from .device_discovery import OAKDeviceDiscovery
from .device_match import DeviceMatchManager

__all__ = [
    "DeviceConfigManager",
    "ConfigConverter",
    "OAKDeviceDiscovery",
    "DeviceMatchManager",
]


