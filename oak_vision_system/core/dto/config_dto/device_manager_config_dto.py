"""
设备管理器配置DTO（顶层统领）

整合所有配置模块的顶层DTO。

架构设计：
    DeviceManagerConfigDTO (顶层)
        │
        └─ 功能模块配置 (平级设计，层次清晰)
            ├─ OAKModuleConfigDTO         - OAK模块完整配置
            │   ├─ hardware_config        - OAK硬件配置
            │   └─ device_binding         - 设备绑定配置
            │
            ├─ DataProcessingConfigDTO    - 数据处理配置
            ├─ CANConfigDTO               - CAN通信配置
            ├─ DisplayConfigDTO           - 显示配置
            └─ SystemConfigDTO            - 系统级配置

设计理念：
    - OAK相关的配置（硬件+设备绑定）封装在 OAKModuleConfigDTO 中
    - 各功能模块配置平级管理，职责清晰
    - 顶层配置只负责组合，不直接管理细节
"""

from dataclasses import dataclass, field
from typing import List, Optional

from ..base_dto import validate_string_length
from .base_config_dto import BaseConfigDTO
from .enums import DeviceRole
from .oak_module_config_dto import OAKModuleConfigDTO
from .data_processing_config_dto import DataProcessingConfigDTO
from .can_config_dto import CANConfigDTO
from .display_config_dto import DisplayConfigDTO
from .system_config_dto import SystemConfigDTO


@dataclass(frozen=True)
class DeviceManagerConfigDTO(BaseConfigDTO):
    """
    设备管理器配置（顶层DTO）
    
    整合所有功能模块的配置，层次清晰，各模块职责明确。
    
    架构特点：
    1. OAK模块配置：封装了硬件配置和设备绑定
    2. 其他功能模块：数据处理、CAN、显示、系统 - 平级管理
    3. 职责分离：每个配置DTO专注于自己的领域
    4. 层次内聚：相关配置归类到同一模块下
    
    使用示例：
        config = DeviceManagerConfigDTO(
            oak_module=OAKModuleConfigDTO(
                hardware_config=OAKConfigDTO(...),
                role_bindings={...}
            ),
            display_config=DisplayConfigDTO(...),
        )
        
        # 访问OAK硬件配置
        fps = config.oak_module.hardware_config.hardware_fps
        
        # 访问设备绑定
        mxid = config.oak_module.get_active_mxid(DeviceRole.LEFT_CAMERA)
    """
    
    config_version: str = "2.0.0"
    
    # ========== 功能模块配置（平级设计，层次清晰）==========
    oak_module: OAKModuleConfigDTO = field(default_factory=OAKModuleConfigDTO)
    data_processing_config: DataProcessingConfigDTO = field(default_factory=DataProcessingConfigDTO)
    can_config: CANConfigDTO = field(default_factory=CANConfigDTO)
    display_config: DisplayConfigDTO = field(default_factory=DisplayConfigDTO)
    system_config: SystemConfigDTO = field(default_factory=SystemConfigDTO)
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        errors.extend(validate_string_length(
            self.config_version, 'config_version', min_length=1, max_length=20
        ))
        
        # 验证OAK模块配置
        if self.oak_module is not None:
            errors.extend(self.oak_module._validate_data())
        
        # 验证数据处理配置
        if self.data_processing_config is not None:
            errors.extend(self.data_processing_config._validate_data())
        
        # 验证CAN配置
        if self.can_config is not None:
            errors.extend(self.can_config._validate_data())
        
        # 验证显示配置
        if self.display_config is not None:
            errors.extend(self.display_config._validate_data())
        
        # 验证系统配置
        if self.system_config is not None:
            errors.extend(self.system_config._validate_data())
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化默认配置"""
        if self.oak_module is None:
            object.__setattr__(self, 'oak_module', OAKModuleConfigDTO())
        if self.data_processing_config is None:
            object.__setattr__(self, 'data_processing_config', DataProcessingConfigDTO())
        if self.can_config is None:
            object.__setattr__(self, 'can_config', CANConfigDTO())
        if self.display_config is None:
            object.__setattr__(self, 'display_config', DisplayConfigDTO())
        if self.system_config is None:
            object.__setattr__(self, 'system_config', SystemConfigDTO())
    
    # ========== 便捷访问方法：委托给OAK模块 ==========
    
    def get_active_mxid(self, role: DeviceRole) -> Optional[str]:
        """获取角色的激活MXid（委托给OAK模块）"""
        return self.oak_module.get_active_mxid(role)
    
    def get_device_metadata(self, mxid: str):
        """获取设备元数据（委托给OAK模块）"""
        return self.oak_module.get_device_metadata(mxid)
    
    def has_active_device(self, role: DeviceRole) -> bool:
        """检查角色是否有激活的设备（委托给OAK模块）"""
        return self.oak_module.has_active_device(role)
    
    @property
    def active_role_count(self) -> int:
        """获取激活的角色数量（委托给OAK模块）"""
        return self.oak_module.active_role_count
    
    # ========== 配置摘要 ==========
    
    def get_summary(self) -> str:
        """获取完整配置摘要"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"设备管理器配置摘要 (v{self.config_version})")
        lines.append("=" * 80)
        lines.append("")
        lines.append(self.oak_module.get_summary())
        lines.append("")
        lines.append("其他模块配置:")
        lines.append(f"  - 数据处理: {'启用' if self.data_processing_config else '禁用'}")
        lines.append(f"  - CAN通信: {'启用' if self.can_config.enable_can else '禁用'}")
        lines.append(f"  - 显示: {'启用' if self.display_config.enable_display else '禁用'}")
        lines.append(f"  - 日志级别: {self.system_config.log_level}")
        lines.append("=" * 80)
        return "\n".join(lines)
