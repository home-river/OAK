"""
配置DTO模块（层次化架构）

层次清晰的文件组织，相关配置内聚管理。

文件组织：
- enums.py: 枚举类型
- device_binding_dto.py: 设备绑定相关（3个DTO）
- oak_config_dto.py: OAK硬件配置
- oak_module_config_dto.py: OAK模块完整配置（硬件+设备绑定）
- data_processing_config_dto.py: 数据处理配置（包含子配置）
- can_config_dto.py: CAN通信配置
- display_config_dto.py: 显示配置
- system_config_dto.py: 系统级配置
- device_manager_config_dto.py: 顶层管理配置

架构设计（层次内聚）：
    DeviceManagerConfigDTO (顶层)
        └─ 功能模块配置 (平级)
            ├─ OAKModuleConfigDTO        ← OAK模块完整配置
            │   ├─ hardware_config       ← OAK硬件配置
            │   └─ device_binding        ← 设备角色绑定
            ├─ DataProcessingConfigDTO
            ├─ CANConfigDTO
            ├─ DisplayConfigDTO
            └─ SystemConfigDTO

设计优势：
    - OAK相关配置内聚：硬件配置和设备绑定在同一模块
    - 层次清晰：相关概念归类到一起
    - 职责明确：每个模块管理自己的完整功能
"""

# 枚举类
from .enums import DeviceType, DeviceRole, ConnectionStatus, FilterType

# 设备绑定相关（OAK模块使用）
from .device_binding_dto import (
    DeviceRoleBindingDTO,
    DeviceMetadataDTO,
    MAX_HISTORICAL_MXIDS,
)

# OAK模块配置（层次化）
from .oak_config_dto import OAKConfigDTO
from .oak_module_config_dto import OAKModuleConfigDTO

# 其他功能模块配置（平级设计）
from .data_processing_config_dto import (
    CoordinateTransformConfigDTO,
    FilterConfigDTO,
    MovingAverageFilterConfigDTO,
    DataProcessingConfigDTO,
    DecisionLayerConfigDTO,
    PersonWarningConfigDTO,
    ObjectZonesConfigDTO,
    GraspZoneConfigDTO,
)
from .can_config_dto import CANConfigDTO, FrameIdConfigDTO, CanFrameMeta
from .display_config_dto import DisplayConfigDTO
from .system_config_dto import SystemConfigDTO

# 顶层管理
from .device_manager_config_dto import DeviceManagerConfigDTO

__all__ = [
    # 枚举
    'DeviceType',
    'DeviceRole',
    'ConnectionStatus',
    'FilterType',
    
    # 设备绑定
    'DeviceRoleBindingDTO',
    'DeviceMetadataDTO',
    'MAX_HISTORICAL_MXIDS',
    
    # OAK模块配置（层次化）
    'OAKConfigDTO',              # OAK硬件配置
    'OAKModuleConfigDTO',        # OAK模块完整配置（硬件+设备绑定）
    'FrameIdConfigDTO',
    
    # 其他功能模块配置（平级）
    'DataProcessingConfigDTO',
    'CANConfigDTO',
    'FrameIdConfigDTO',
    'CanFrameMeta',
    'DisplayConfigDTO',
    'SystemConfigDTO',
    
    # 数据处理子配置
    'CoordinateTransformConfigDTO',
    'FilterConfigDTO',
    'MovingAverageFilterConfigDTO',
    'DecisionLayerConfigDTO',
    'PersonWarningConfigDTO',
    'ObjectZonesConfigDTO',
    'GraspZoneConfigDTO',
    
    # 顶层管理
    'DeviceManagerConfigDTO',
]
