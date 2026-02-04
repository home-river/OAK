# 需求文档：显示模块主线程渲染重构

## 简介

本需求文档描述了将显示模块的渲染逻辑从独立线程迁移到主线程的重构需求。当前实现中，DisplayRenderer 在独立线程中运行 OpenCV 渲染循环，这在某些环境下（特别是 Windows）容易导致窗口卡死或无响应。重构后，渲染逻辑将由 SystemManager 在主线程中驱动，DisplayManager 只负责状态管理和数据打包。

## 术语表

- **SystemManager**: 系统管理器，负责协调所有模块的生命周期和主循环调度
- **DisplayManager**: 显示模块管理器，负责管理 RenderPacketPackager 和 DisplayRenderer
- **RenderPacketPackager**: 渲染包打包器，负责订阅事件并将数据打包成渲染包
- **DisplayRenderer**: 显示渲染器，负责使用 OpenCV 渲染视频帧和检测结果
- **Main_Thread**: 主线程，Python 程序的主执行线程，OpenCV 窗口必须在此线程中创建和更新
- **Render_Once**: 单步渲染接口，执行一次渲染循环并返回控制权
- **Shutdown_Signal**: 关闭信号，用于通知 SystemManager 终止主循环

## 需求

### 需求 1: 主线程渲染架构

**用户故事**: 作为系统开发者，我希望显示模块的渲染逻辑在主线程中执行，以避免 OpenCV 窗口在某些平台上的卡死问题。

#### 验收标准

1. WHEN SystemManager 运行主循环 THEN DisplayManager SHALL 提供单步渲染接口供主线程调用
2. WHEN 单步渲染接口被调用 THEN DisplayManager SHALL 执行一次渲染循环并立即返回控制权
3. WHEN 用户按下退出键（'q'）THEN 单步渲染接口 SHALL 返回退出信号
4. WHEN DisplayManager 启动 THEN DisplayManager SHALL NOT 创建独立的渲染线程
5. WHEN DisplayManager 关闭 THEN DisplayManager SHALL 只关闭打包线程而不关闭渲染线程

### 需求 2: SystemManager 主循环驱动

**用户故事**: 作为系统架构师，我希望 SystemManager 的主循环能够驱动显示模块的渲染，实现统一的调度机制。

#### 验收标准

1. WHEN SystemManager.run() 执行主循环 THEN SystemManager SHALL 每轮循环调用一次 DisplayManager.render_once()
2. WHEN DisplayManager.render_once() 返回退出信号 THEN SystemManager SHALL 触发 SYSTEM_SHUTDOWN 事件
3. WHEN 用户按下 Ctrl+C THEN SystemManager SHALL 捕获 KeyboardInterrupt 并触发关闭流程
4. WHEN 关闭流程触发 THEN SystemManager SHALL 调用 shutdown() 方法关闭所有模块
5. WHEN 模块关闭超时 THEN SystemManager SHALL 使用兜底机制强制退出进程

### 需求 3: DisplayManager 特殊注册接口

**用户故事**: 作为系统开发者，我希望 DisplayManager 有专门的注册接口，以表明它需要主线程渲染的特殊处理。

#### 验收标准

1. WHEN 注册 DisplayManager THEN SystemManager SHALL 提供 register_display_module() 专用接口
2. WHEN DisplayManager 被注册 THEN SystemManager SHALL 标记该模块需要主线程渲染
3. WHEN SystemManager 启动模块 THEN DisplayManager SHALL 按照正常优先级顺序启动
4. WHEN SystemManager 关闭模块 THEN DisplayManager SHALL 按照正常优先级顺序关闭
5. WHEN SystemManager 执行主循环 THEN SystemManager SHALL 自动调用已注册的 DisplayManager.render_once()

### 需求 4: 渲染包打包线程管理

**用户故事**: 作为模块开发者，我希望 DisplayManager 继续管理 RenderPacketPackager 的打包线程，保持数据流的异步处理。

#### 验收标准

1. WHEN DisplayManager.start() 被调用 THEN DisplayManager SHALL 启动 RenderPacketPackager 的打包线程
2. WHEN DisplayManager.stop() 被调用 THEN DisplayManager SHALL 停止 RenderPacketPackager 的打包线程
3. WHEN 打包线程运行 THEN RenderPacketPackager SHALL 订阅事件并将数据打包成渲染包
4. WHEN DisplayManager.start() 被调用 THEN DisplayManager SHALL NOT 启动 DisplayRenderer 的渲染线程
5. WHEN DisplayManager.stop() 被调用 THEN DisplayManager SHALL NOT 尝试停止不存在的渲染线程

### 需求 5: 单步渲染接口设计

**用户故事**: 作为 SystemManager 开发者，我希望 DisplayManager 提供清晰的单步渲染接口，返回值明确指示是否需要退出。

#### 验收标准

1. WHEN DisplayManager.render_once() 被调用 THEN DisplayManager SHALL 执行一次完整的渲染循环
2. WHEN 渲染成功完成 THEN render_once() SHALL 返回 False（表示继续运行）
3. WHEN 用户按下 'q' 键 THEN render_once() SHALL 返回 True（表示请求退出）
4. WHEN 渲染过程中发生异常 THEN render_once() SHALL 记录错误日志并返回 False
5. WHEN DisplayManager 未启用显示 THEN render_once() SHALL 立即返回 False

### 需求 6: 窗口分辨率和比例

**用户故事**: 作为用户，我希望显示窗口保持正确的 16:9 宽高比，并且能够根据配置调整分辨率。

#### 验收标准

1. WHEN 显示模式为小窗口 THEN 窗口分辨率 SHALL 保持 16:9 比例（例如 1280x720）
2. WHEN 显示模式为全屏 THEN 窗口分辨率 SHALL 使用配置的全屏分辨率（例如 1920x1080）
3. WHEN 合并显示多个设备 THEN 每个设备帧 SHALL 调整为配置的单帧尺寸后再拼接
4. WHEN 单设备显示 THEN 帧 SHALL 调整为窗口分辨率
5. WHEN 调整窗口大小 THEN 显示内容 SHALL 保持正确的宽高比

### 需求 7: 按键处理逻辑

**用户故事**: 作为用户，我希望按键处理逻辑保持在 DisplayRenderer 中，并通过返回值传递给 SystemManager。

#### 验收标准

1. WHEN 用户按下 'q' 键 THEN DisplayRenderer SHALL 检测到按键并设置退出标志
2. WHEN render_once() 检测到退出标志 THEN render_once() SHALL 返回 True
3. WHEN 用户按下其他功能键 THEN DisplayRenderer SHALL 处理相应的功能（如切换显示模式）
4. WHEN 按键处理完成 THEN DisplayRenderer SHALL 继续渲染下一帧
5. WHEN 没有按键输入 THEN render_once() SHALL 正常渲染并返回 False

### 需求 8: 异常处理和日志记录

**用户故事**: 作为系统维护者，我希望渲染过程中的异常能够被正确捕获和记录，不影响系统的稳定性。

#### 验收标准

1. WHEN render_once() 执行过程中发生异常 THEN DisplayManager SHALL 捕获异常并记录错误日志
2. WHEN 渲染异常被捕获 THEN render_once() SHALL 返回 False 以继续运行
3. WHEN 连续发生多次渲染异常 THEN DisplayManager SHALL 记录警告日志
4. WHEN 关键异常发生（如窗口创建失败）THEN DisplayManager SHALL 记录 CRITICAL 日志
5. WHEN 系统关闭 THEN DisplayManager SHALL 记录统计信息到日志

### 需求 9: 向后兼容性

**用户故事**: 作为现有代码的维护者，我希望重构后的接口保持向后兼容，最小化对现有代码的影响。

#### 验收标准

1. WHEN 使用旧的 register_module() 接口 THEN DisplayManager SHALL 仍然能够正常注册
2. WHEN DisplayManager 配置 enable_display=False THEN 系统 SHALL 正常运行而不渲染
3. WHEN 其他模块调用 DisplayManager 的公共接口 THEN 接口行为 SHALL 保持不变
4. WHEN 配置文件格式不变 THEN DisplayManager SHALL 正常加载配置
5. WHEN 事件总线消息格式不变 THEN DisplayManager SHALL 正常接收和处理事件

### 需求 10: 性能和响应性

**用户故事**: 作为用户，我希望重构后的渲染性能不低于原实现，并且窗口响应流畅。

#### 验收标准

1. WHEN 系统运行 THEN 渲染帧率 SHALL 不低于 30 FPS
2. WHEN 用户按下按键 THEN 系统 SHALL 在 100ms 内响应
3. WHEN 主循环执行 THEN CPU 使用率 SHALL 保持在合理范围（不超过 50%）
4. WHEN 渲染队列满 THEN 系统 SHALL 丢弃旧帧而不阻塞
5. WHEN 系统关闭 THEN 所有模块 SHALL 在 5 秒内完成关闭

### 需求 11: 测试和验证

**用户故事**: 作为质量保证工程师，我希望重构后的代码有完整的测试覆盖，确保功能正确性。

#### 验收标准

1. WHEN 运行冒烟测试 THEN 系统 SHALL 正常启动、运行和关闭
2. WHEN 运行单元测试 THEN DisplayManager.render_once() SHALL 通过所有测试用例
3. WHEN 运行集成测试 THEN SystemManager 和 DisplayManager 的交互 SHALL 正常工作
4. WHEN 模拟用户按键 THEN 系统 SHALL 正确响应并退出
5. WHEN 模拟渲染异常 THEN 系统 SHALL 正确处理并继续运行
