"""
数据采集模块

包含 OAK 设备数据采集、Pipeline 管理等功能
"""

from .collector import OAKDataCollector
from .pipelinemanager import PipelineManager

__all__ = [
    'OAKDataCollector',
    'PipelineManager',
]