"""
数据采集模块

包含系统配置管理、OAK设备管理、Pipeline管理、数据处理等功能
"""

from .config_manager import SystemConfigManager

# 向后兼容：保留旧名称作为别名
OAKDeviceManager = SystemConfigManager

__all__ = [
    'SystemConfigManager',  # 新名称（推荐）
    'OAKDeviceManager',     # 旧名称（向后兼容）
]