# 模块启动协议与 SystemManager 回滚增强需求

## 1. 背景与问题
当前系统存在“子模块实际启动失败，但 SystemManager 未感知、未回滚”的情况，典型表现为：
- 子模块的 `start()` 采用异步线程启动；设备连接/资源初始化失败发生在子线程中。
- 由于子线程异常不会上浮到 `SystemManager.start_all()` 的调用栈，导致 `start_all()` 仍将模块标记为 RUNNING。
- 结果是系统进入 `run()` 主循环后才出现错误日志，系统仍可能继续运行，直到定时退出或人工中断。

为提高一致性与可维护性，需要明确模块生命周期协议，并增强 `SystemManager.start_all()` 对 `start()` 返回值的兜底判断，同时重写相关测试脚本以覆盖关键路径。

## 2. 目标
- 明确所有受管模块的 `start()` / `stop()` 协议与失败语义。
- `SystemManager.start_all()` 能正确处理 `start()` 的失败返回值，触发回滚。
- 通过集成测试与冒烟测试验证：
  - 启动失败时能够回滚已启动模块。
  - 关闭顺序符合优先级策略。
  - 退出路径（SYSTEM_SHUTDOWN / Ctrl+C / 显示模块退出）行为明确且可验证。

## 3. 范围
### 3.1 需要做的
- 规范子模块 `start()` 职责与失败语义：
  - `start()` 抛异常必须上浮，禁止吞异常后仍返回“成功语义”。
  - `start()` 返回 `False` 必须表示启动失败（兜底语义），上层必须按失败处理。
  - 兼容性：允许 `start()` 返回 `None` / `True` / 其他对象表示成功（仅 `is False` 视为失败）。
- `SystemManager.start_all()` 增强：
  - 捕获异常仍按现有逻辑回滚。
  - 新增对 `start()` 返回值的判断：若返回 `False`，直接触发回滚并抛出 `RuntimeError`。
  - 判断规则必须使用 `ret is False`，避免 `{}`、`[]` 等被误判为失败。
- 新增或重写测试：
  - SystemManager 集成测试（优先）：覆盖启动成功、异常启动失败回滚、返回 False 启动失败回滚、停止失败处理等。
  - 重写 smoke 测试：弃用旧架构的测试文件，编写符合当前“主线程渲染 + SystemManager 驱动”的 smoke 脚本。

### 3.2 不做的（Non-Goals）
- 不在本需求中统一重构所有模块为同步启动模型（允许保留异步启动，但必须让失败可观测）。
- 不在本需求中引入复杂的新框架（例如全新的状态机/调度器），以最小改动为优先。

## 4. 设计与约束
### 4.1 模块 `start()` 协议（统一约定）
- 成功：
  - `start()` 允许返回 `None` / `True` / 任意非 `False` 对象。
- 失败：
  - `start()` 抛异常：表示启动失败，SystemManager 必须回滚。
  - `start()` 返回 `False`：表示启动失败但模块做了兜底（例如降级/跳过），SystemManager 必须回滚。
- 推荐实践：
  - 若模块内部为异步启动，应提供可观测的“就绪/失败”机制（例如 `wait_ready()` 或在 `start()` 内做必要的同步探测）。

### 4.2 SystemManager.start_all() 行为
- 仍保持“按优先级从高到低启动”的顺序。
- 对每个模块：
  - 调用 `ret = module.instance.start()`。
  - 若 `ret is False`：视为启动失败，立即触发回滚（对 `started_modules` 逆序调用 stop），并抛出异常使上层感知失败。
  - 若 `start()` 抛异常：按现有逻辑触发回滚并抛出异常。

### 4.3 回滚策略
- 回滚仅对“已成功启动并记录在 started_modules 中”的模块执行。
- 回滚过程中：即使某模块 stop 失败，也继续尝试停止其他模块，并记录错误。

## 5. 测试计划
### 5.1 SystemManager 集成测试（建议先实现）
- Case A：所有模块 start 成功
  - 断言启动顺序符合优先级（高到低）。
  - 通过发布 SYSTEM_SHUTDOWN 使 run 退出。
  - 断言 stop 顺序符合优先级（低到高）。
- Case B：某模块 start 返回 False
  - 断言触发回滚。
  - 断言已启动模块被 stop。
  - 断言 start_all 抛出 RuntimeError。
- Case C：某模块 start 抛异常
  - 同 Case B。
- Case D：某模块 stop 返回 False
  - 断言 SystemManager 记录停止失败并按既定兜底策略处理。

### 5.2 Smoke 测试（重写）
- 目标：验证完整链路在“当前架构”下可运行与可退出。
- 建议支持两种运行模式：
  - 有硬件模式：要求插入 OAK；无法连接时明确失败退出并给出原因。
  - 无硬件模式：跳过/模拟 collector，验证 SystemManager + DisplayManager 主线程渲染、EventBus 链路、VirtualCAN、退出流程。

## 6. 验收标准
- `SystemManager.start_all()`：
  - `start()` 返回 `False` 时必定触发回滚，并让调用方获得失败信号（异常）。
  - `start()` 抛异常时仍能回滚。
- 测试：
  - 新增的 SystemManager 集成测试覆盖上述用例并通过。
  - 重写后的 smoke 测试在预期模式下行为稳定，可复现、可解释。

## 7. 实施顺序（建议）
- 第一步：定义协议（以本文件为准），并在代码评审中执行。
- 第二步：改造 `SystemManager.start_all()` 支持 `ret is False` 失败回滚。
- 第三步：补齐/重写 SystemManager 集成测试，确保框架行为稳定。
- 第四步：重写 smoke 测试脚本，使其符合当前架构与协议。
