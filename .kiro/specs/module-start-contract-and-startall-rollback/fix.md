# data_collector/collector.py 与模块启动协议不一致问题修复说明

## 1. 关联规范
- 规范文档：`.kiro/specs/module-start-contract-and-startall-rollback/requirements.md`
- 相关条款：
  - `start()` 失败语义必须可被上层感知：
    - 抛异常：启动失败，必须上浮
    - 返回 `False`：启动失败兜底语义，上层必须按失败处理并回滚
  - `SystemManager.start_all()` 将（计划）补充 `ret is False` 的回滚判断

## 2. 现象与根因（为什么当前不符合规范）

### 2.1 现象（从终端日志可复现）
- 系统已经进入 `SystemManager.run()` 主循环后，`OAKDataCollector` 才在子线程中报错：
  - `RuntimeError: Cannot find any device with given deviceInfo`
  - 异常发生在线程 `OAKWorker-left_camera/right_camera` 中
- `SystemManager.start_all()` 并未回滚（因为它未感知到 `start()` 失败）

### 2.2 根因
当前 `OAKDataCollector.start()` 的职责是“启动工作线程”，而不是“确认启动成功”。其行为特征：
- `start()` 仅创建并启动线程，然后立即返回一个 `dict`（包含 started/skipped）。
- 真实的设备连接发生在 `_start_OAK_with_device()` 内，若未插设备/绑定 MXID 不可用，会在子线程里抛异常。
- 子线程异常不会自动上浮到调用 `start()` 的主线程，因此：
  - `start()` 不会抛异常
  - `start()` 也不会返回 `False`
  - 上层（SystemManager）只能认为“启动成功”，随后把模块标记为 RUNNING

这与规范中“启动失败必须通过异常上浮或返回 False 表达”的要求不一致。

## 3. 当前实现不符合点（逐条对照规范）

- **不符合点 A：`start()` 无法表达启动失败**
  - 规范要求：失败必须 `raise` 或 `return False`
  - 现状：即使所有设备都无法连接，`start()` 仍会返回 `dict`，上层难以判定失败

- **不符合点 B：启动失败不在 `start()` 同步阶段暴露**
  - 规范要求：`start()` 职责应包含“失败语义上浮/可观测”
  - 现状：失败发生在子线程，表现为“系统运行中才出现错误日志”，但框架不回滚

- **不符合点 C：子线程异常对系统状态不产生确定性影响**
  - 现状：线程异常仅记录日志，系统仍可继续跑到定时 shutdown（或等待人工 Ctrl+C）
  - 这会导致 smoke/集成测试结果不稳定，且失败原因与退出码容易不一致

## 4. 修改方案（你后续可自行落地的两种实现路径）

> 建议优先落地 **方案 1（同步预检 + 失败返回 False/抛异常）**，改动最小、最符合当前 SystemManager 的同步管理模型。

### 方案 1：在 `OAKDataCollector.start()` 内做同步“设备可用性预检”（推荐）
目标：在启动线程前就判断配置中绑定的 `active_mxid` 是否存在于当前可用设备列表中，若不存在则 **直接失败**（返回 `False` 或抛异常），避免 SystemManager 误判 RUNNING。

建议实现步骤：
1. 在 `start()` 开始处调用：
   - `dai.DeviceBootloader.getAllAvailableDevices()` 获取 `DeviceInfo` 列表
   - 将可用 `mxid` 收集成集合 `available_mxids`
2. 对 `self.config.role_bindings` 做预检：
   - `active_mxid` 为空：保持当前行为，记录到 `skipped[role] = "no_active_mxid"`
   - `active_mxid` 不在 `available_mxids`：记录错误，并触发失败
3. 失败语义选择（二选一）：
   - **返回 `False`（兜底失败）**：符合规范，且与后续 `SystemManager.start_all()` 的 `ret is False` 回滚配合
   - **抛 `RuntimeError`（强失败）**：更直接，立即触发回滚（即使 SystemManager 未改 ret 判断也有效）

推荐策略：
- 对“无法读取可用设备列表”的异常：**抛异常**（说明环境/驱动异常，不宜继续）
- 对“读取成功但缺少绑定 MXID”：**返回 False**（可作为兜底失败语义）

额外建议：
- 若预检失败，应避免启动任何 worker 线程（保持一致性）。

### 方案 2：保留异步启动，但将失败显式上报到系统层（备选）
目标：仍允许 `start()` 只起线程，但一旦 `_start_OAK_with_device` 失败，应让系统立刻进入可控退出/失败路径。

建议实现方式：
- 在 `_start_OAK_with_device` 捕获到设备连接失败后：
  - 通过 `event_bus.publish("SYSTEM_SHUTDOWN", ShutdownEvent(reason="oak_start_failed"))` 触发系统退出
  - 或者设置某个 collector 内部的 failure flag，供上层查询

注意：此方案对“启动回滚”的一致性不如方案 1，因为失败发生在 `start_all()` 之后。

## 5. 验收要点（落地后用什么标准判断改好了）
- 未插设备 / MXID 不可用时：
  - `OAKDataCollector.start()` 必须返回 `False` 或抛异常
  - SystemManager（在实现 ret 判断后）必须触发启动回滚
  - 不应出现“进入 run() 主循环后才出现启动失败”的情况
- 插入设备且 MXID 正确时：
  - `start()` 正常返回 started/skipped 结构
  - worker 线程正常运行并发布数据

## 6. 相关联的后续修改（非本文件直接修改范围）
- `SystemManager.start_all()`：增加 `ret is False` 失败回滚（按规范文档第 4.2 节）
- SystemManager 集成测试：补充 start 返回 False 的回滚用例
- smoke 测试：区分“有硬件模式/无硬件模式”，避免因为环境导致不稳定
