
# OAK 设备发现不稳定问题阶段性结论（2026-02-27）

## 结论 1：两连扫场景下，连续两次调用“设备发现器接口”会出现漏扫/差异

- **对应文件**
  - `oak_vision_system/tests/manual/OAKAPI/manual_oakapi_two_scans_compare.py`
- **结论**
  - 在同一进程内连续两次调用 `OAKDeviceDiscovery.discover_devices()`（scan1 -> scan2），scan2 相对 scan1 可能出现 `missing/extra`。
  - 该现象与绑定工具（binding）里的“短时间内多次 discover”场景一致，因此可作为复现/回归脚本。

## 结论 2：DepthAI 源头枚举（仅取 MXID）两连扫稳定，问题主要不在“枚举 API 本身”

- **对应文件**
  - `oak_vision_system/tests/manual/OAKAPI/manual_oakapi_raw_enum_two_scans.py`
- **结论**
  - 直接调用 DepthAI 源头枚举 API（`dai.Device.getAllAvailableDevices()`，仅提取 `mxid`）连续扫描两次，结果可稳定 `MATCH`。
  - 说明“漏扫/跳变”更可能由上层发现逻辑中的**连接设备并读取信息**引入（而不是枚举函数本身随机漏设备）。

## 结论 3：间隔探测中观察到的卡顿/中断点主要发生在读取标定信息（readCalibration）

- **对应文件**
  - `oak_vision_system/tests/manual/OAKAPI/manual_oakapi_interval_missing_probe.py`
- **结论**
  - 在多轮两连扫 + 不同 interval 的探测中，发现 scan 的耗时往往在秒级。
  - 发生卡顿/需要手动中断（KeyboardInterrupt）时，堆栈指向 `OAKDeviceDiscovery._get_product_name()` 内部的 `device.readCalibration()`。
  - 推断：读取标定/EEPROM 产品名这类“需要连接设备”的操作既耗时，也可能引入副作用（设备状态变化/被占用），进而导致后续 scan2 出现 `missing/extra`。

