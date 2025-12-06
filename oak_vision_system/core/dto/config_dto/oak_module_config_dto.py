"""
OAK模块完整配置DTO

整合OAK模块的所有配置，包括：
- 硬件配置（检测、相机、深度、Pipeline）
- 设备绑定配置（角色绑定、设备元数据）

这是一个完整的OAK模块配置封装，对外提供统一的接口。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .base_config_dto import BaseConfigDTO
from .enums import DeviceRole
from .device_binding_dto import DeviceRoleBindingDTO, DeviceMetadataDTO
from .oak_config_dto import OAKConfigDTO


@dataclass(frozen=True)
class OAKModuleConfigDTO(BaseConfigDTO):
    """
    OAK模块完整配置DTO
    
    架构设计：
        OAKModuleConfigDTO
            ├─ hardware_config (OAK硬件配置)
            │   ├─ 检测模型配置
            │   ├─ 相机硬件参数
            │   ├─ 深度计算参数
            │   └─ Pipeline队列配置
            │
            └─ device_binding (设备绑定配置)
                ├─ role_bindings: 角色到MXid的映射
                └─ device_metadata: MXid设备元数据
    
    使用场景：
        # 创建OAK模块配置
        oak_module = OAKModuleConfigDTO(
            hardware_config=OAKConfigDTO(...),
            role_bindings={
                DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(...),
            }
        )
        
        # 访问硬件配置
        fps = oak_module.hardware_config.hardware_fps
        
        # 访问设备绑定
        left_mxid = oak_module.get_active_mxid(DeviceRole.LEFT_CAMERA)
    """
    
    # ========== OAK硬件配置 ==========
    hardware_config: OAKConfigDTO = field(default_factory=OAKConfigDTO)
    
    # ========== 设备绑定配置 ==========
    role_bindings: Dict[DeviceRole, DeviceRoleBindingDTO] = field(default_factory=dict)
    # mxid + 设备元数据
    device_metadata: Dict[str, DeviceMetadataDTO] = field(default_factory=dict)
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        # 验证硬件配置
        if self.hardware_config is not None:
            errors.extend(self.hardware_config._validate_data())
        
        # 验证设备绑定
        if not isinstance(self.role_bindings, dict):
            errors.append("role_bindings必须为字典类型")
        else:
            for role, binding in self.role_bindings.items():
                if not isinstance(role, DeviceRole):
                    errors.append(f"role_bindings的key必须为DeviceRole类型: {role}")
                if hasattr(binding,"role") and binding.role != role:
                    errors.append(f"bindings的Role和key不一致：{binding.role}!={role}")
                errors.extend(binding._validate_data())
        
        if not isinstance(self.device_metadata, dict):
            errors.append("device_metadata必须为字典类型")
        else:
            for mxid, metadata in self.device_metadata.items():
                errors.extend(metadata._validate_data())
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化默认配置"""
        if self.hardware_config is None:
            object.__setattr__(self, 'hardware_config', OAKConfigDTO())
    
    # ========== 便捷访问方法：设备绑定 ==========
    
    def get_role_binding(self, role: DeviceRole) -> Optional[DeviceRoleBindingDTO]:
        """获取角色绑定"""
        return self.role_bindings.get(role)
    
    def get_active_mxid(self, role: DeviceRole) -> Optional[str]:
        """获取角色的激活MXid"""
        binding = self.get_role_binding(role)
        return binding.active_mxid if binding else None
    
    def get_device_metadata(self, mxid: str) -> Optional[DeviceMetadataDTO]:
        """获取设备元数据"""
        return self.device_metadata.get(mxid)
    
    def has_role(self, role: DeviceRole) -> bool:
        """检查角色是否存在"""
        return role in self.role_bindings
    
    def has_active_device(self, role: DeviceRole) -> bool:
        """检查角色是否有激活的设备"""
        binding = self.get_role_binding(role)
        return binding.has_active_device if binding else False
    
    @property
    def active_role_count(self) -> int:
        """获取激活的角色数量"""
        return sum(1 for b in self.role_bindings.values() if b.has_active_device)
    
    @property
    def total_role_count(self) -> int:
        """获取总角色数量"""
        return len(self.role_bindings)
    
    @property
    def available_roles(self) -> List[DeviceRole]:
        """获取所有可用角色列表"""
        return list(self.role_bindings.keys())
    
    # ========== 便捷访问方法：硬件配置 ==========
    
    @property
    def model_path(self) -> Optional[str]:
        """快捷访问：模型路径"""
        return self.hardware_config.model_path
    
    @property
    def hardware_fps(self) -> int:
        """快捷访问：硬件帧率"""
        return self.hardware_config.hardware_fps
    
    @property
    def confidence_threshold(self) -> float:
        """快捷访问：置信度阈值"""
        return self.hardware_config.confidence_threshold
    
    # ========== 配置摘要 ==========
    
    def get_summary(self) -> str:
        """获取配置摘要"""
        lines = []
        lines.append("=== OAK模块配置摘要 ===")
        lines.append(f"硬件配置:")
        lines.append(f"  - 模型: {self.hardware_config.model_path or '未配置'}")
        lines.append(f"  - 帧率: {self.hardware_config.hardware_fps} fps")
        lines.append(f"  - 置信度: {self.hardware_config.confidence_threshold}")
        lines.append(f"  - 队列: {self.hardware_config.queue_max_size}")
        lines.append(f"\n设备绑定:")
        lines.append(f"  - 总角色数: {self.total_role_count}")
        lines.append(f"  - 激活角色数: {self.active_role_count}")
        for role in self.available_roles:
            mxid = self.get_active_mxid(role)
            status = f"激活: {mxid[:16]}..." if mxid else "未激活"
            lines.append(f"  - {role.display_name}: {status}")
        return "\n".join(lines)

