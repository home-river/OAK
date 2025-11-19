校验器（独立模块，函数式）
位置：modules/config_manager/validators.py

一、校验目标
- 面向持久化配置与运行态一致性，确保 `DeviceManagerConfigDTO` 可被安全加载/保存，并在运行时与绑定/设备元数据保持一致。

二、校验范围（功能清单）
- OAK 角色集合校验：角色集合完整/无重复，命名合法；各角色绑定结构合法。
- 历史记录必填校验：每个角色的 `historical_mxids` 按规则非空/不超上限（与实现约定一致）。
- MXID 引用完整性：`role_bindings` 中引用的所有 MXID 必须存在于 `device_metadata`。
- 运行态唯一性（可选）：同一 MXID 不得被多个角色同时作为 active（运行时检查，导出时不持久化 active）。
- DTO 结构校验聚合：聚合调用各 DTO 的 `validate()`，汇总其结构与取值范围错误。
- 交叉一致性：`role_bindings ↔ device_metadata` 字段交叉检查，发现漂移或缺失。

三、接口签名（建议）
```python
from typing import Tuple, List, Optional
from oak_vision_system.core.dto.config_dto import DeviceManagerConfigDTO, DeviceMetadataDTO

def validate_roles(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """校验角色集合完整/无重复/命名合法；可复用 DeviceMatchManager.check_bindings_roles。"""

def validate_historical_mxids(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """校验各角色 historical_mxids 非空且不超上限（与实现约定对齐）。"""

def validate_mxid_references(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """确保 bindings 中引用的 MXID 均存在于 device_metadata。"""

def validate_active_mxid_uniqueness(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """运行态检查：同一 MXID 不得被多个角色同时 active。"""

def validate_dto_structure(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """聚合调用各 DTO 的 validate()，汇总结构/取值范围错误。"""

def validate_cross_consistency(config: DeviceManagerConfigDTO) -> Tuple[bool, List[str]]:
    """交叉校验 role_bindings 与 device_metadata 的一致性（如引用缺失/重复）。"""

def run_all_validations(
    config: DeviceManagerConfigDTO,
    *,
    include_runtime_checks: bool = True,
) -> Tuple[bool, List[str]]:
    """统一入口：按顺序串联上述校验，返回 (是否通过, 错误列表)。"""

# 可选：运行期校验（在线设备）
def validate_against_online_devices(
    config: DeviceManagerConfigDTO,
    online_devices: List[DeviceMetadataDTO]
) -> Tuple[bool, List[str]]:
    """校验绑定 MXID 是否在线（可用于启动前的软门槛）。"""
```

四、使用约定
- device_config_manager 在 load/save/create_default 前后调用 `run_all_validations()`；
- 错误优先聚合后返回，必要时抛出语义化异常由上层转换为用户提示；
- `include_runtime_checks=False` 时仅做持久化必需校验，忽略 active 与在线状态。 