"""
配置校验器（函数式、无副作用）。

用于为 DeviceManagerConfigDTO 提供统一的校验入口。

校验范围：
- 角色集合完整性/唯一性
- 历史 MXID 填写规则
- MXID 引用完整性（bindings ↔ device_metadata）
- 运行时唯一性（active_mxid 唯一，可选）
- DTO 结构校验汇总（DTO.validate() 聚合）
- 跨字段一致性检查

说明：所有函数统一返回 (ok, errors)。保持确定性，不在此处打印日志，由调用方决定如何呈现。
"""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

# 仅类型检查时导入，运行期不引入依赖，避免循环依赖与导入开销
if TYPE_CHECKING:  # pragma: no cover
    from oak_vision_system.core.dto.config_dto import (
        DeviceManagerConfigDTO,
        DeviceMetadataDTO,
        DeviceRoleBindingDTO,
        DeviceRole,
    )


__all__ = [
    "validate_roles",
    "validate_mxid_references",
    "validate_active_mxid_uniqueness",
    "validate_dto_structure",
    "validate_cross_consistency",
    "validate_coordinate_transform_role",
    "run_all_validations",
    "validate_against_online_devices",
]
# ==================== 字段内部一致性校验 ====================
def validate_dto_structure(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """聚合 DTO.validate()，收集配置树上的结构/取值错误。"""
    # TODO: 调用 config.validate() 或子 DTO 的 validate()，汇总错误
    ok = True
    errors: List[str] = []
    if not config.validate():
        ok = False
        errors.extend(list(config.get_validation_errors()))
    return ok, errors


# ====================字段间交叉校验 ====================
def validate_roles(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """校验角色集合的完整性/唯一性/命名合法性。

    建议复用 DeviceMatchManager.check_bindings_roles(bindings) 进行核心校验。
    """
    # 函数内延迟导入，避免与匹配器产生循环依赖，并返回校验结果
    from .device_match import DeviceMatchManager
    bindings = list(config.oak_module.role_bindings.values())
    return DeviceMatchManager.check_bindings_roles(bindings)




def validate_mxid_references(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """校验绑定中引用的 MXID 全部存在于 device_metadata。"""
    errors = []
    available_mxids = tuple(m.mxid for m in config.oak_module.device_metadata.values())
    bindings = list(config.oak_module.role_bindings.values())
    for binding in bindings:
        if binding.active_mxid not in available_mxids:
            errors.append(f"Mxid:{binding.active_mxid} 不存在于 device_metadata")
    return len(errors) == 0, errors




def validate_active_mxid_uniqueness(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """校验active_mxid 在各角色间必须唯一。

    说明：active_mxid 不参与持久化，仅在运行态需要时检查。
    """
    errors = []
    seen_mxids = set()
    bindings = list(config.oak_module.role_bindings.values())
    for binding in bindings:
        mxid = getattr(binding, 'active_mxid', None)
        if not mxid:
            continue
        if mxid in seen_mxids:
            errors.append(f"mxid: {mxid} 重复")
        else:
            seen_mxids.add(mxid)
    return len(errors) == 0, errors


# 校验坐标变换的role和rolebinding的role是否一致
def validate_coordinate_transform_role(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    errors = []
    transforms = list(config.data_processing_config.coordinate_transforms.values())
    trans_roles = {transform.role for transform in transforms}
    binding_roles = {binding.role for binding in config.oak_module.role_bindings.values()}
    missing = binding_roles - trans_roles
    extra = trans_roles - binding_roles
    if missing:
        errors.append(f"缺少坐标变换角色: {sorted(missing)}")
    if extra:
        errors.append(f"多余的坐标变换角色: {sorted(extra)}")
    return len(errors) == 0, errors


def validate_cross_consistency(
    config: DeviceManagerConfigDTO,
    *,
    include_runtime_checks: bool = True,
) -> Tuple[bool, List[str]]:
    """
    跨字段一致性检查（如 role_bindings 与 device_metadata/coordinate_transforms 等之间的约束）。
    统一聚合跨字段校验：角色集合、MXID 引用、坐标变换角色一致性，及可选的运行态校验。
    """
    all_ok = True
    all_errors: List[str] = []

    validators = [
        validate_roles,
        validate_mxid_references,
        validate_coordinate_transform_role,
    ]
    if include_runtime_checks:
        validators.append(validate_active_mxid_uniqueness)

    for v in validators:
        ok, errs = v(config)
        if not ok:
            all_ok = False
        if errs:
            all_errors.extend(errs)

    return all_ok, all_errors


def run_all_validations(
    config: DeviceManagerConfigDTO,
    *,
    include_runtime_checks: bool = True,
) -> Tuple[bool, List[str]]:
    """按组运行校验：先字段内一致性，再字段间一致性，返回聚合结果。"""
    ok_in, errs_in = validate_dto_structure(config)
    ok_cross, errs_cross = validate_cross_consistency(
        config, include_runtime_checks=include_runtime_checks
    )
    return ok_in and ok_cross, [*errs_in, *errs_cross]


def validate_against_online_devices(
    config: DeviceManagerConfigDTO,
    online_devices: List[DeviceMetadataDTO],
) -> Tuple[bool, List[str]]:
    """
    校验配置中的 active_mxid 是否在在线设备中都存在。
    
    功能说明：
    - 根据配置中的 active_mxid 和 online_devices 进行一一对应校验
    - 校验包括：
        - 重复绑定：active_mxid 重复绑定到不同的角色
        - 不存在：active_mxid 在 online_devices 中不存在
    
    参数说明：
    - config: DeviceManagerConfigDTO，待校验的配置
    - online_devices: List[DeviceMetadataDTO]，在线设备的元数据列表
    
    返回值：
    - ok: bool，校验结果
    - errors: List[str]，校验错误列表
    """
    errors: List[str] = []
    bindings = list(config.oak_module.role_bindings.values())

    online_mxids = {d.mxid for d in online_devices}  # 在线集合
    seen: set[str] = set()                           # 重复检测

    for b in bindings:
        mxid = getattr(b, "active_mxid", None)
        if not mxid:
            # 未绑定：此处可忽略或按需视为警告
            continue

        if mxid in seen:
            errors.append(f"Mxid:{mxid} 重复绑定")
            continue
        seen.add(mxid)

        if mxid not in online_mxids:
            errors.append(f"Mxid:{mxid} 不存在于 online_devices")
        else:
            # 可选：移除一个已匹配实例，避免后续误判；对逻辑无负面影响
            online_mxids.discard(mxid)

    return len(errors) == 0, errors





