# DeviceMatchManager 接口文档

本文档记录 `DeviceMatchManager` 模块的所有公开接口，包括接口功能、参数、返回值等详细信息。

---

## 🏗️ 内部属性说明

### 核心数据属性

#### 1. `self.bindings` - 唯一数据源（Single Source of Truth）

**类型：** `List[DeviceRoleBindingDTO]`

**职责：**
- ✅ 存储所有角色的绑定配置（包括已绑定和未绑定的）
- ✅ 运行时包含完整信息（包括 `active_mxid`）
- ✅ 所有修改操作的唯一目标
- ✅ 作为计算 `match_result` 的数据源

**数据结构：**
```python
self.bindings = [
    DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        active_mxid="device1",              # 当前绑定的设备（运行时）
        last_active_mxid="device1",         # 上次使用的设备
        historical_mxids=["device1", ...],  # 历史记录
    ),
    DeviceRoleBindingDTO(
        role=DeviceRole.RIGHT_CAMERA,
        active_mxid=None,                   # 未绑定
        last_active_mxid="device2",
        historical_mxids=["device2", ...],
    ),
    # ...
]
```

**重要特性：**
- 运行时可以包含 `active_mxid`（表示当前绑定状态）
- 导出时会清除 `active_mxid`（只保存历史记录）
- 永远包含所有角色（无论是否绑定）

---

#### 2. `self.match_result` - 只读视图（Read-Only View）

**类型：** `DeviceMatchResult`

**职责：**
- ✅ 从 `self.bindings` 计算出来的匹配结果
- ✅ 提供便捷的分类查询（matched、unmatched、available）
- ✅ 只用于读取，不应该直接修改
- ✅ 通过 `_sync_result_from_bindings()` 统一更新

**数据结构：**
```python
self.match_result = DeviceMatchResult(
    matched_bindings=[...],      # 有 active_mxid 的 binding
    unmatched_bindings=[...],    # 无 active_mxid 的 binding
    available_devices=[...],     # 空闲设备列表
    result_type=MatchResultType, # 匹配结果类型
    errors=[...]                 # 错误信息
)
```

**访问控制：**
- ❌ 外部代码：只能读取，不能修改
- ❌ 内部方法：只能读取，不能修改
- ✅ `_sync_result_from_bindings()`：唯一可以修改的地方

---

#### 3. `self.online_devices` - 在线设备列表

**类型：** `List[DeviceMetadataDTO]`

**职责：**
- 存储当前在线的所有设备
- 用于匹配和查询操作
- 通过 `set_online_devices()` 更新

**数据结构：**
```python
self.online_devices = [
    DeviceMetadataDTO(mxid="device1", ...),
    DeviceMetadataDTO(mxid="device2", ...),
    # ...
]
```

---

#### 4. `self.enable_auto_bind_new_devices` - 自动绑定开关

**类型：** `bool`

**职责：**
- 控制是否自动将空闲设备绑定到未匹配的角色
- 默认为 `True`
- 通过 `set_auto_bind_new_devices()` 修改

---

### 数据流设计

```
┌─────────────────────────────────────┐
│  self.bindings (唯一数据源)          │
│  - 包含完整信息（含 active_mxid）    │
│  - 运行时可以有 active_mxid          │
│  - 所有修改操作的目标                │
└─────────────────────────────────────┘
              ↓
        _sync_result_from_bindings()
              ↓
┌─────────────────────────────────────┐
│  self.match_result (只读视图)        │
│  - 从 bindings 计算出来              │
│  - matched_bindings (有 active)      │
│  - unmatched_bindings (无 active)    │
│  - available_devices                 │
│  - result_type                       │
└─────────────────────────────────────┘
              ↓
        export_bindings()
              ↓
┌─────────────────────────────────────┐
│  导出的配置 (持久化)                 │
│  - 清除 active_mxid                  │
│  - 只保存历史记录                    │
└─────────────────────────────────────┘
```

---

### 核心设计原则

#### 1. 单向数据流
```
bindings → match_result → 导出
```
- ✅ 数据流向清晰
- ✅ 不会出现循环依赖

#### 2. 单一数据源
```
所有修改 → self.bindings
所有查询 → self.match_result
```
- ✅ `self.bindings` 是唯一可修改的数据源
- ✅ `self.match_result` 是计算结果，不直接修改

#### 3. 统一同步机制
```
修改 bindings → _sync_result_from_bindings() → 更新 match_result
```
- ✅ 所有修改后统一调用同步方法
- ✅ 保证数据一致性

---

### 私有方法说明

#### `_update_binding(binding)` - 更新单个 binding
- 职责：替换 `self.bindings` 中指定角色的 binding
- 不更新 `match_result`（需要调用者手动同步）

#### `_sync_result_from_bindings()` - 同步到 match_result
- 职责：从 `self.bindings` 重新计算 `match_result`
- 唯一可以修改 `match_result` 的方法
- 更新所有字段（matched、unmatched、available、result_type）

#### `_bind_devices_to_roles()` - 批量匹配设备
- 职责：根据历史记录批量匹配设备
- 更新 `self.bindings` 中的 `active_mxid`
- 需要调用者手动同步到 `match_result`

#### `_auto_bind_new_devices()` - 自动绑定新设备
- 职责：将空闲设备自动绑定到未匹配的角色
- 更新 `self.bindings` 中的 `active_mxid`
- 需要调用者手动同步到 `match_result`

---

## 📋 接口总览

### 1. 初始化与配置（4个）
- ✅ `__init__` - 初始化设备匹配管理器
- ✅ `set_online_devices` - 设置在线设备列表
- ✅ `set_bindings` - 设置绑定配置
- ✅ `set_auto_bind_new_devices` - 设置自动绑定开关

### 2. 核心匹配功能（2个）
- ✅ `default_match_devices` - 默认设备匹配策略
- ✅ `auto_rematch_devices` - 自动重新匹配设备

### 3. 配置管理（2个）
- ✅ `check_bindings_roles` - 检查绑定配置合法性（静态方法）
- ✅ `reset_to_default_bindingsResult` - 重置匹配结果

### 4. 结果分析与验证（2个）
- ✅ `validate_match_result` - 验证匹配结果是否满足启动条件
- ✅ `get_match_summary` - 生成匹配结果的人类可读摘要

### 5. 查询接口 - 设备（2个）
- ✅ `get_device_by_mxid` - 根据 MXID 查找在线设备
- ✅ `get_available_device_by_mxid` - 根据 MXID 查找空闲设备

### 6. 查询接口 - 绑定配置（4个）
- ✅ `get_binding_by_role` - 根据角色查找绑定配置
- ✅ `get_matched_binding_by_role` - 根据角色查找已匹配绑定
- ✅ `get_binding_by_mxid` - 根据 MXID 查找绑定配置
- ✅ `get_matched_binding_by_mxid` - 根据 MXID 查找已匹配绑定

### 7. 查询接口 - 便捷查询（5个）
- ✅ `get_unmatched_roles` - 获取所有未匹配的角色
- ✅ `list_matched_devices` - 列出所有已匹配设备
- ✅ `list_available_devices` - 列出所有空闲设备
- ✅ `get_all_bindings` - 获取所有绑定配置
- ✅ `is_role_matched` - 检查角色是否已匹配
- ✅ `is_device_bound` - 检查设备是否已绑定

### 8. 手动绑定操作（4个）
- ✅ `manual_bind_device` - 手动绑定设备到角色
- ✅ `unbind_role` - 解除角色的设备绑定
- ✅ `unbind_all_devices` - 解除所有设备绑定
- ✅ `swap_devices` - 交换两个角色的设备

### 9. 状态导出（2个）
- ✅ `get_current_status` - 获取当前匹配状态（可序列化）
- ✅ `export_bindings` - 导出可持久化的绑定配置

**统计：** 共 27 个接口，全部已实现 ✅

---

## 📖 接口详细说明

## 1. 初始化与配置

### 1.1 `__init__`
初始化设备匹配管理器

**签名：**
```python
def __init__(
    self, 
    bindings: List[DeviceRoleBindingDTO],
    auto_bind_new_devices: bool = True,
    online_devices: List[DeviceMetadataDTO] = None
)
```

**参数：**
- `bindings`: 绑定配置列表
- `auto_bind_new_devices`: 是否自动绑定新设备（默认 True）
- `online_devices`: 在线设备列表（可选）

**功能：**
- 初始化管理器状态
- 验证绑定配置合法性
- 如果提供了在线设备，自动执行匹配

---

### 1.2 `set_online_devices`
设置在线设备列表

**签名：**
```python
def set_online_devices(self, online_devices: List[DeviceMetadataDTO])
```

**功能：** 更新当前在线设备列表

---

### 1.3 `set_bindings`
设置绑定配置

**签名：**
```python
def set_bindings(self, bindings: List[DeviceRoleBindingDTO])
```

**功能：** 更新绑定配置，会验证配置合法性

**异常：** 如果配置不合法抛出 `ValueError`

---

### 1.4 `set_auto_bind_new_devices`
设置自动绑定开关

**签名：**
```python
def set_auto_bind_new_devices(self, enable: bool) -> None
```

**功能：** 启用/禁用自动绑定新设备功能

---

## 2. 核心匹配功能

### 2.1 `default_match_devices`
默认设备匹配策略

**签名：**
```python
def default_match_devices(
    self,
    online_devices: List[DeviceMetadataDTO] = None,
    bindings: List[DeviceRoleBindingDTO] = None
) -> DeviceMatchResult
```

**功能：**
- 按优先级匹配设备：last_active_mxid > historical_mxids
- 可选自动绑定新设备到未匹配角色
- 返回完整的匹配结果

**返回：** `DeviceMatchResult` 对象

---

### 2.2 `auto_rematch_devices`
自动重新匹配设备

**签名：**
```python
def auto_rematch_devices(self, online_devices: List[DeviceMetadataDTO]) -> bool
```

**功能：** 使用新的在线设备列表重新执行匹配

**返回：** 是否执行了重新匹配（bool）

---

## 3. 配置管理

### 3.1 `check_bindings_roles`（静态方法）
检查绑定配置合法性

**签名：**
```python
@staticmethod
def check_bindings_roles(bindings: List[DeviceRoleBindingDTO]) -> Tuple[bool, List[str]]
```

**功能：**
- 检查是否有重复角色
- 检查是否有重复的 active_mxid
- 验证 historical_mxids 不为空

**返回：** `(是否合法, 错误列表)`

---

### 3.2 `reset_to_default_bindingsResult`
重置匹配结果

**签名：**
```python
def reset_to_default_bindingsResult(self)
```

**功能：** 清空所有匹配状态，重置为初始状态

---

## 4. 结果分析与验证

### 4.1 `validate_match_result`
验证匹配结果是否满足启动条件

**签名：**
```python
def validate_match_result(self, result: DeviceMatchResult = None) -> Tuple[bool, List[str]]
```

**功能：** 检查匹配结果的 `result_type` 是否允许启动系统

**返回：** `(是否可启动, 问题列表)`

---

### 4.2 `get_match_summary`
生成匹配结果的人类可读摘要

**签名：**
```python
def get_match_summary(self, result: DeviceMatchResult) -> str
```

**功能：** 生成格式化的匹配状态摘要文本

**返回：** 多行文本字符串

---

## 5. 查询接口 - 设备

### 5.1 `get_device_by_mxid`
根据 MXID 查找在线设备

**签名：**
```python
def get_device_by_mxid(self, mxid: str) -> Optional[DeviceMetadataDTO]
```

**功能：** 从所有在线设备中查找指定 MXID 的设备

**返回：** 设备元数据对象，未找到返回 `None`

---

### 5.2 `get_available_device_by_mxid`
根据 MXID 查找空闲设备

**签名：**
```python
def get_available_device_by_mxid(self, mxid: str) -> Optional[DeviceMetadataDTO]
```

**功能：** 从空闲设备列表中查找指定 MXID 的设备

**返回：** 设备元数据对象，未找到返回 `None`

---

## 6. 查询接口 - 绑定配置

### 6.1 `get_binding_by_role`
根据角色查找绑定配置

**签名：**
```python
def get_binding_by_role(self, role: DeviceRole) -> Optional[DeviceRoleBindingDTO]
```

**功能：** 从所有绑定配置中查找指定角色

**返回：** 绑定对象，未找到返回 `None`

---

### 6.2 `get_matched_binding_by_role`
根据角色查找已匹配绑定

**签名：**
```python
def get_matched_binding_by_role(self, role: DeviceRole) -> Optional[DeviceRoleBindingDTO]
```

**功能：** 从已匹配绑定列表中查找指定角色

**返回：** 绑定对象，未找到返回 `None`

---

### 6.3 `get_binding_by_mxid`
根据 MXID 查找绑定配置

**签名：**
```python
def get_binding_by_mxid(self, mxid: str) -> Optional[DeviceRoleBindingDTO]
```

**功能：** 从所有绑定配置中查找绑定了指定设备的角色

**返回：** 绑定对象，未找到返回 `None`

---

### 6.4 `get_matched_binding_by_mxid`
根据 MXID 查找已匹配绑定

**签名：**
```python
def get_matched_binding_by_mxid(self, mxid: str) -> Optional[DeviceRoleBindingDTO]
```

**功能：** 从已匹配绑定列表中查找绑定了指定设备的角色

**返回：** 绑定对象，未找到返回 `None`

---

## 7. 查询接口 - 便捷查询

### 7.1 `get_unmatched_roles`
获取所有未匹配的角色

**签名：**
```python
def get_unmatched_roles(self) -> List[DeviceRole]
```

**功能：** 返回所有未匹配设备的角色列表

**返回：** 角色列表

---

### 7.2 `list_matched_devices`
列出所有已匹配设备

**签名：**
```python
def list_matched_devices(self) -> List[Tuple[DeviceRole, str]]
```

**功能：** 返回 (角色, MXID) 元组列表

**返回：** `[(DeviceRole, mxid), ...]`

---

### 7.3 `list_available_devices`
列出所有空闲设备

**签名：**
```python
def list_available_devices(self) -> List[DeviceMetadataDTO]
```

**功能：** 返回所有未被绑定的在线设备

**返回：** 设备元数据列表

---

### 7.4 `get_all_bindings`
获取所有绑定配置

**签名：**
```python
def get_all_bindings(self) -> List[DeviceRoleBindingDTO]
```

**功能：** 返回所有绑定配置的副本

**返回：** 绑定配置列表

---

### 7.5 `is_role_matched`
检查角色是否已匹配

**签名：**
```python
def is_role_matched(self, role: DeviceRole) -> bool
```

**功能：** 检查指定角色是否已绑定设备

**返回：** `True` 表示已匹配，`False` 表示未匹配

---

### 7.6 `is_device_bound`
检查设备是否已绑定

**签名：**
```python
def is_device_bound(self, mxid: str) -> bool
```

**功能：** 检查指定设备是否已被绑定到某个角色

**返回：** `True` 表示已绑定，`False` 表示未绑定

---

## 8. 手动绑定操作

### 8.1 `manual_bind_device`
手动绑定设备到角色

**签名：**
```python
def manual_bind_device(
    self, 
    role: DeviceRole, 
    mxid: str
) -> Tuple[bool, str]
```

**功能：**
- 手动将指定设备绑定到角色
- 如果设备已被其他角色绑定，自动解绑旧角色
- 自动更新历史记录（通过 `set_active_Mxid_by_device` 方法）
- 自动更新匹配状态

**返回：** `(成功/失败, 消息)`

---

### 8.2 `unbind_role`
解除角色的设备绑定

**签名：**
```python
def unbind_role(self, role: DeviceRole) -> Tuple[bool, str]
```

**功能：**
- 解除指定角色的设备绑定
- 不清除历史记录（设备仍在 historical_mxids 中）
- 自动更新匹配状态

**返回：** `(成功/失败, 消息)`

---

### 8.3 `swap_devices`
交换两个角色的设备

**签名：**
```python
def swap_devices(self, role1: DeviceRole, role2: DeviceRole) -> Tuple[bool, str]
```

**功能：**
- 快速交换两个角色的设备绑定
- 适用于设备接反、快速测试等场景
- 自动更新历史记录和匹配状态

**返回：** `(成功/失败, 消息)`

---

### 8.4 `unbind_all_devices`
解除所有设备绑定

**签名：**
```python
def unbind_all_devices(self) -> Tuple[bool, str]
```

**功能：**
- 批量解除所有角色的设备绑定
- 不清除历史记录（设备仍在 historical_mxids 中）
- 自动更新匹配状态
- 时间复杂度：O(n)，性能优化

**返回：** `(成功/失败, 消息)`

---

## 9. 状态导出

### 9.1 `get_current_status`
获取当前匹配状态（可序列化）

**签名：**
```python
def get_current_status(self) -> Dict
```

**功能：** 返回可序列化为 JSON 的完整状态快照，用于 CLI 和监控

**返回字段：**
```python
{
    "result_type": str,           # 匹配结果类型
    "can_start": bool,            # 是否可启动系统
    "matched_devices": {          # 已匹配设备（角色->MXID）
        "left_camera": "mxid1",
        ...
    },
    "unmatched_roles": [...],     # 未匹配角色列表
    "available_devices": [...],   # 空闲设备 MXID 列表
    "errors": [...]               # 错误信息列表
}
```

---

### 9.2 `export_bindings`
导出可持久化的绑定配置

**签名：**
```python
def export_bindings(self) -> List[DeviceRoleBindingDTO]
```

**功能：**
- 根据当前匹配结果更新绑定配置
- 用于保存用户的手动调整
- 返回可持久化的配置列表

**返回：** 绑定配置列表

---

## 📝 使用建议

### 常见使用模式

#### 1. 初始化和匹配
```python
# 创建匹配器
matcher = DeviceMatchManager(bindings, auto_bind_new_devices=True)

# 执行匹配
result = matcher.default_match_devices(online_devices)

# 验证是否可启动
can_start, issues = matcher.validate_match_result()
```

#### 2. 手动调整绑定
```python
# 绑定设备
success, msg = matcher.manual_bind_device(DeviceRole.LEFT_CAMERA, "mxid1")

# 交换设备
success, msg = matcher.swap_devices(DeviceRole.LEFT_CAMERA, DeviceRole.RIGHT_CAMERA)

# 解绑单个设备
success, msg = matcher.unbind_role(DeviceRole.MIDDLE_CAMERA)

# 解绑所有设备
success, msg = matcher.unbind_all_devices()

# 导出配置
bindings = matcher.export_bindings()
```

#### 3. 状态查询
```python
# 获取状态快照
status = matcher.get_current_status()

# 检查角色是否匹配
if matcher.is_role_matched(DeviceRole.LEFT_CAMERA):
    print("左相机已匹配")

# 列出空闲设备
available = matcher.list_available_devices()
```

### 注意事项

1. **DTO 不可变**：所有 DTO 对象都是不可变的，修改时需要创建新对象
2. **状态同步**：手动绑定操作会自动更新匹配状态，无需手动调用更新方法
3. **线程安全**：当前实现不是线程安全的，多线程环境需要加锁
4. **历史记录**：解绑操作不会清除历史记录，设备仍可自动重新匹配
