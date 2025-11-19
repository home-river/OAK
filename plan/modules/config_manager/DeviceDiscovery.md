# OAKDeviceDiscovery 接口文档

本文档记录 `OAKDeviceDiscovery` 发现器模块的公开接口、职责边界与使用方式，便于与配置管理/匹配器等模块解耦对齐。

---

## 🎯 模块职责与边界

### 职责（Do）
- 扫描本机可用的 OAK 设备
- 提取并返回设备元数据（MXID、连接状态、产品名称等）
- 产出标准 `DeviceMetadataDTO` 列表，供上游/下游直接使用

### 非职责（Don't）
- 不做角色绑定、匹配与持久化（交由 ConfigManager/DeviceMatch）
- 不做交互与文件读写（交由工具/上层）
- 不维护长期状态（全部静态、即取即用）

---

## 🧾 输入 / 输出

- 输入：无（可选 `verbose` 控制台输出开关）
- 输出：`List[DeviceMetadataDTO]`
  - `mxid: str`
  - `product_name: Optional[str]`
  - `connection_status: ConnectionStatus`（connected/disconnected/unknown）
  - `notes: Optional[str]`（包含发现时间说明）
  - `first_seen: float`、`last_seen: float`（UNIX 时间戳）

---

## 🔁 工作流概览

```
get_all_available_devices()  →  depthai 查询原始设备列表
          ↓
discover_devices()           →  映射为 DeviceMetadataDTO（补充状态/产品名/时间戳）
          ↓
返回 List[DeviceMetadataDTO]  →  供 ConfigManager / DeviceMatch / UI 使用
```

---

## 📋 接口总览

### 公共接口（推荐调用）
- `discover_devices(verbose: bool = False) -> List[DeviceMetadataDTO]`
  - 执行完整发现流程，返回标准化 DTO 列表
- `get_all_available_devices(verbose: bool = False) -> List[dai.DeviceInfo]`
  - 仅查询 depthai 层的原始设备信息（一般用于诊断）

### 内部辅助（不建议外部直接使用）
- `_get_product_name(device_info: dai.DeviceInfo, verbose: bool = True) -> Optional[str]`
- `_parse_connection_state(state_str: str) -> ConnectionStatus`
- `_print_devices_summary(devices: List[DeviceMetadataDTO]) -> None`

---

## 🔎 接口详细说明

### 1) `discover_devices`
- 功能：
  - 获取原始设备列表 → 解析连接状态 → 尝试读取产品名称 → 组装 `DeviceMetadataDTO`
  - 在 `verbose=True` 时输出发现摘要
- 返回：`List[DeviceMetadataDTO]`（可能为空）
- 失败处理：
  - 单个设备处理异常时跳过该设备，继续处理其他设备

### 2) `get_all_available_devices`
- 功能：
  - 调用 `depthai.DeviceBootloader.getAllAvailableDevices()` 获取原始设备清单
  - 异常时返回空列表并记录日志/可选打印
- 返回：`List[dai.DeviceInfo]`（原始对象）

---

## 🧪 调试与测试建议

- Mock 集成测试：
  - 模拟返回 `dai.DeviceInfo`、模拟产品名读取，验证 DTO 构造完整性
- 真实硬件测试：
  - 标记 `@pytest.mark.hardware`，连接真实设备验证 MXID/状态/时间戳
- 诊断输出：
  - `discover_devices(verbose=True)` 查看发现摘要

---

## ⚠️ 边界与约束

- 连接状态简化映射：`UNBOOTED/BOOTED/CONNECTED → connected`；未知状态 → `unknown`
- 读取产品名称需要可连接设备，失败时返回 `None`
- 不保证顺序稳定（由底层枚举顺序决定）

---

## ✅ 推荐用法

```python
from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery

# 发现设备（静默）
devices = OAKDeviceDiscovery.discover_devices(verbose=False)

# 发现设备（带摘要）
devices = OAKDeviceDiscovery.discover_devices(verbose=True)

# 与匹配器/配置管理器衔接
# online_devices = devices
# result = device_matcher.default_match_devices(online_devices)
```

---

## 📌 与其他模块的关系

- ConfigManager：消费发现结果，进行配置创建/加载/合并
- DeviceMatch：基于 `DeviceMetadataDTO` 与绑定关系进行匹配
- Tools/CLI：可基于发现结果做绑定/诊断


