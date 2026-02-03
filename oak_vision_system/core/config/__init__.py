"""
配置核心功能模块

提供配置模板构建工具，用于生成默认配置对象。
"""

from .templates import (
    template_SystemConfigDTO,
    template_OAKConfigDTO,
    template_DisplayConfigDTO,
    template_FrameIdConfigDTO,
    template_CANConfigDTO,
    template_CoordinateTransformConfigDTO,
    template_MovingAverageFilterConfigDTO,
    template_FilterConfigDTO,
    template_DataProcessingConfigDTO,
    template_DeviceManagerConfigDTO,
    template_OAKModuleConfigDTO,
    template_DeviceRoleBindingDTO,
)

__all__ = [
    'template_SystemConfigDTO',
    'template_OAKConfigDTO',
    'template_DisplayConfigDTO',
    'template_FrameIdConfigDTO',
    'template_CANConfigDTO',
    'template_CoordinateTransformConfigDTO',
    'template_MovingAverageFilterConfigDTO',
    'template_FilterConfigDTO',
    'template_DataProcessingConfigDTO',
    'template_DeviceManagerConfigDTO',
    'template_OAKModuleConfigDTO',
    'template_DeviceRoleBindingDTO',
]
