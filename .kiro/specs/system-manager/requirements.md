# Requirements Document

## Introduction

本文档定义了OAK视觉检测系统的SystemManager（系统管理器）模块需求。SystemManager是一个简洁的核心基础设施模块，负责统一管理所有功能模块的生命周期，提供清晰的启动/运行/关闭机制。

**设计原则：**
- **简洁性**：事件回调只做"置位"，不执行复杂操作
- **统一退出点**：所有退出路径汇聚到 `finally` 块
- **防重复执行**：使用 Event 防止多次关闭
- **职责分离**：回调负责"发信号"，`run()` 负责"执行关闭"

## Glossary

- **SystemManager**: 系统管理器，负责模块生命周期管理的核心基础设施模块
- **Module**: 功能模块，具有 `start()` 和 `stop()` 方法的组件（如Collector、DataProcessor、Display等）
- **ManagedModule**: 被管理的模块包装类，包含模块实例、优先级和状态信息
- **Priority**: 模块优先级，数字越大表示越靠近下游（消费者），越小表示越靠近上游（生产者）。启动时从高到低（下游→上游），关闭时从低到高（上游→下游）。建议值：显示=50，处理器=30，数据源=10
- **EventBus**: 事件总线，模块间通信的基础设施
- **SYSTEM_SHUTDOWN**: 系统停止事件类型，由显示模块发布
- **ShutdownEvent**: 系统停止事件，包含 `reason` 字段标明终止原因
- **ModuleState**: 模块状态枚举（NOT_STARTED, RUNNING, STOPPED, ERROR）
- **SystemConfigDTO**: 系统配置数据传输对象，包含日志级别、文件路径等配置信息

## Requirements

### Requirement 1: 模块注册

**User Story:** 作为系统集成者，我想要注册需要管理的模块，以便SystemManager能够统一管理它们的生命周期。

#### Acceptance Criteria

1. THE SystemManager SHALL 提供 `register_module` 方法接受模块名称、实例和优先级
2. THE SystemManager SHALL 将模块包装为 ManagedModule 对象并存储
3. THE SystemManager SHALL 为每个模块分配初始状态为 NOT_STARTED
4. THE SystemManager SHALL 记录模块注册日志（包含名称和优先级）
5. WHEN 注册同名模块时 THEN THE SystemManager SHALL 抛出 ValueError 异常

### Requirement 2: 模块启动

**User Story:** 作为SystemManager，我想要按优先级顺序启动所有注册的模块，以便系统能够正常运行。

#### Acceptance Criteria

1. THE SystemManager SHALL 提供 `start_all` 方法启动所有模块
2. THE SystemManager SHALL 按优先级从高到低的顺序启动模块（下游先启动，上游后启动）
3. WHEN 模块启动成功时 THEN THE SystemManager SHALL 将模块状态设置为 RUNNING
4. WHEN 模块启动失败时 THEN THE SystemManager SHALL 将模块状态设置为 ERROR 并抛出异常
5. THE SystemManager SHALL 记录每个模块的启动日志

### Requirement 3: 启动失败回滚

**User Story:** 作为SystemManager，我想要在模块启动失败时回滚已启动的模块，以便系统保持一致状态。

#### Acceptance Criteria

1. WHEN 任何模块启动失败时 THEN THE SystemManager SHALL 停止启动流程
2. THE SystemManager SHALL 记录启动失败的模块名称和错误信息
3. THE SystemManager SHALL 按相反顺序关闭所有已启动的模块
4. THE SystemManager SHALL 将所有已启动模块状态设置为 STOPPED
5. THE SystemManager SHALL 向调用者抛出原始异常

### Requirement 4: 系统停止事件定义

**User Story:** 作为系统，我想要定义统一的停止事件，以便显示模块能够触发系统关闭。

#### Acceptance Criteria

1. THE System SHALL 定义 SYSTEM_SHUTDOWN 事件类型
2. THE ShutdownEvent SHALL 包含 `reason` 字段（停止原因字符串）
3. THE `reason` 字段 SHALL 用于标明终止原因（如 "user_quit", "window_closed"）
4. THE SystemManager SHALL 在日志中记录停止事件的 reason

### Requirement 5: 系统停止事件订阅

**User Story:** 作为SystemManager，我想要订阅系统停止事件，以便在显示模块触发退出时能够关闭系统。

#### Acceptance Criteria

1. THE SystemManager SHALL 在初始化时订阅 SYSTEM_SHUTDOWN 事件
2. WHEN 接收到 SYSTEM_SHUTDOWN 事件时 THEN THE SystemManager SHALL 设置 `_shutdown_event` 标志
3. THE SystemManager SHALL 记录接收到的停止事件信息（reason）
4. THE 事件回调 SHALL 只做置位操作，不执行复杂逻辑

### Requirement 6: 两个退出出口

**User Story:** 作为SystemManager，我想要明确定义两个退出出口，以便系统退出流程清晰可控。

#### Acceptance Criteria

1. THE SystemManager SHALL 使用 `try-except` 结构捕获 KeyboardInterrupt（Ctrl+C）
2. THE SystemManager SHALL 订阅 SYSTEM_SHUTDOWN 事件作为第二个退出出口
3. WHEN 捕获到 KeyboardInterrupt 时 THEN THE SystemManager SHALL 记录日志并进入 `finally` 块执行关闭
4. WHEN `_shutdown_event` 被设置时 THEN THE SystemManager SHALL 退出主循环并进入 `finally` 块执行关闭
5. THE SystemManager SHALL NOT 注册信号处理器（signal.signal）
6. THE 两个退出出口 SHALL 统一通过 `finally` 块调用 `shutdown` 方法

### Requirement 7: 主线程阻塞和统一退出

**User Story:** 作为SystemManager，我想要提供清晰的主线程阻塞机制和统一的退出点，以便退出流程简洁可控。

#### Acceptance Criteria

1. THE SystemManager SHALL 使用 `threading.Event` 作为主线程阻塞机制
2. THE SystemManager SHALL 提供 `run` 方法阻塞主线程直到接收到退出信号
3. THE `run` 方法 SHALL 使用 `try-except-finally` 结构处理退出
4. THE `run` 方法 SHALL 在 `try` 块中使用 `Event.wait(timeout=0.5)` 阻塞主线程
5. THE `run` 方法 SHALL 在 `except KeyboardInterrupt` 块中记录日志
6. THE `run` 方法 SHALL 在 `finally` 块中统一调用 `shutdown` 方法
7. THE 阻塞机制 SHALL 不消耗CPU资源（CPU使用率接近0%）

### Requirement 8: 模块关闭

**User Story:** 作为SystemManager，我想要按优先级顺序关闭所有模块，以便确保数据完整性和资源正确释放。

#### Acceptance Criteria

1. THE SystemManager SHALL 提供 `shutdown` 方法关闭所有模块
2. THE SystemManager SHALL 按优先级从低到高的顺序关闭模块（上游先关闭，下游后关闭）
3. THE SystemManager SHALL 调用模块的 `stop` 方法并检查返回值
4. WHEN 模块的 `stop` 方法返回 `True` 或 `None` 时 THEN THE SystemManager SHALL 将模块状态设置为 STOPPED
5. WHEN 模块的 `stop` 方法返回 `False` 时 THEN THE SystemManager SHALL 将模块状态设置为 ERROR 并记录到失败模块列表
6. WHEN 模块关闭过程中抛出异常时 THEN THE SystemManager SHALL 捕获异常、记录错误、将模块状态设置为 ERROR、添加到失败模块列表并继续关闭其他模块

### Requirement 9: 防重复关闭

**User Story:** 作为SystemManager，我想要防止重复关闭，以便避免资源重复释放和错误。

#### Acceptance Criteria

1. THE SystemManager SHALL 使用 `_stop_started` Event 标志防止重复关闭
2. WHEN `shutdown` 方法被调用时 THEN THE SystemManager SHALL 检查 `_stop_started` 标志
3. WHEN `_stop_started` 已设置时 THEN THE SystemManager SHALL 直接返回不执行关闭逻辑
4. WHEN `_stop_started` 未设置时 THEN THE SystemManager SHALL 设置标志并执行关闭逻辑
5. THE `shutdown` 方法 SHALL 可以被多个线程安全调用

### Requirement 10: 事件总线关闭

**User Story:** 作为SystemManager，我想要在所有模块关闭后关闭事件总线，以便清理通信基础设施。

#### Acceptance Criteria

1. WHEN 所有模块关闭后 THEN THE SystemManager SHALL 调用事件总线的 `close` 方法
2. THE SystemManager SHALL 使用 `wait=True` 参数等待事件总线中的任务完成
3. THE SystemManager SHALL 使用 `cancel_pending=False` 参数不取消待处理的任务
4. WHEN 事件总线关闭失败时 THEN THE SystemManager SHALL 记录错误但不抛出异常
5. THE 事件总线关闭 SHALL 在所有模块关闭之后执行

### Requirement 11: 日志系统初始化

**User Story:** 作为SystemManager，我想要在初始化时配置日志系统，以便所有模块使用统一的日志配置。

#### Acceptance Criteria

1. THE SystemManager SHALL 接受可选的 `system_config` 参数（SystemConfigDTO类型）
2. WHEN `system_config` 提供时 THEN THE SystemManager SHALL 调用 `configure_logging` 初始化日志系统
3. WHEN 日志配置失败时 THEN THE SystemManager SHALL 使用默认日志配置并记录警告
4. THE SystemManager SHALL 在日志配置完成后记录 SystemManager 初始化信息
5. THE SystemManager SHALL 创建自己的 logger 实例用于记录日志

### Requirement 12: 模块状态查询

**User Story:** 作为系统监控者，我想要查询所有模块的状态，以便了解系统运行情况。

#### Acceptance Criteria

1. THE SystemManager SHALL 提供 `get_status` 方法返回所有模块状态
2. THE 返回结果 SHALL 是字典格式，键为模块名称，值为状态字符串
3. THE 状态字符串 SHALL 包括："not_started", "running", "stopped", "error"
4. THE SystemManager SHALL 提供 `is_shutting_down` 方法检查系统是否正在关闭
5. THE `is_shutting_down` 方法 SHALL 返回 `_stop_started` 标志的状态

### Requirement 13: 日志记录

**User Story:** 作为开发者，我想要清晰的日志记录，以便调试和监控系统运行。

#### Acceptance Criteria

1. THE SystemManager SHALL 记录所有模块的注册事件（INFO级别）
2. THE SystemManager SHALL 记录所有模块的启动和关闭事件（INFO级别）
3. THE SystemManager SHALL 记录接收到的停止事件（INFO级别）
4. THE SystemManager SHALL 记录错误信息（ERROR级别）
5. THE SystemManager SHALL 在日志中包含模块名称和操作类型

### Requirement 14: 上下文管理器支持

**User Story:** 作为Python开发者，我想要使用 `with` 语句管理SystemManager，以便自动处理资源清理。

#### Acceptance Criteria

1. THE SystemManager SHALL 实现 `__enter__` 方法
2. THE SystemManager SHALL 实现 `__exit__` 方法
3. WHEN 进入 `with` 块时 THEN THE SystemManager SHALL 调用 `start_all` 方法
4. WHEN 退出 `with` 块时 THEN THE SystemManager SHALL 调用 `shutdown` 方法
5. THE `__exit__` 方法 SHALL 返回 False 以不抑制异常

### Requirement 15: 可配置性

**User Story:** 作为系统集成者，我想要配置SystemManager的行为，以便适应不同的使用场景。

#### Acceptance Criteria

1. THE SystemManager SHALL 接受 `event_bus` 参数（可选，默认使用全局单例）
2. THE SystemManager SHALL 接受 `system_config` 参数（可选，用于日志初始化）
3. THE SystemManager SHALL 接受 `default_stop_timeout` 参数配置默认关闭超时（默认5秒）
4. THE SystemManager SHALL 在初始化时记录配置参数（DEBUG级别）
5. THE 配置参数 SHALL 保持简洁，只包含必要的配置项

### Requirement 16: 异常日志记录

**User Story:** 作为开发者，我想要记录所有未捕获的异常，以便调试和排查问题。

#### Acceptance Criteria

1. THE SystemManager SHALL 在初始化时使用 `attach_exception_logger` 安装异常钩子
2. THE 异常钩子 SHALL 只用于记录未捕获异常的日志
3. THE 异常钩子 SHALL NOT 触发系统退出或设置退出标志
4. THE 异常钩子 SHALL 配置 `ignore_keyboard_interrupt=True` 忽略 KeyboardInterrupt
5. THE SystemManager SHALL 在关闭时调用 `_exception_handle.detach()` 恢复原有异常钩子

### Requirement 17: 强制退出兜底机制

**User Story:** 作为SystemManager，我想要在模块停止失败时强制退出进程，以便确保系统能够可靠退出。

#### Acceptance Criteria

1. THE SystemManager SHALL 接受 `force_exit_grace_period` 参数配置强制退出宽限期（默认3.0秒）
2. THE SystemManager SHALL 在 `shutdown` 方法中跟踪所有停止失败的模块
3. WHEN 模块的 `stop` 方法返回 `False` 时 THEN THE SystemManager SHALL 将模块名称添加到失败模块列表
4. WHEN 模块的 `stop` 方法抛出异常时 THEN THE SystemManager SHALL 将模块名称添加到失败模块列表
5. WHEN 所有模块关闭后存在失败模块时 THEN THE SystemManager SHALL 记录 CRITICAL 级别日志（包含失败模块列表）
6. THE SystemManager SHALL 等待 `force_exit_grace_period` 秒后调用 `logging.shutdown()` 刷新日志缓冲区
7. THE SystemManager SHALL 调用 `os._exit(1)` 强制退出进程（退出码1表示模块停止失败）
8. WHEN 所有模块成功停止时 THEN THE SystemManager SHALL NOT 触发强制退出机制

---

## 后续工作

### 子模块 stop() 方法规范

为了配合 SystemManager 的统一关闭机制和兜底机制，所有被管理的子模块需要确保其 `stop()` 方法满足以下规范：

#### 核心规范

1. **幂等性**：`stop()` 方法可以被多次调用而不出错
   - 第一次调用执行关闭逻辑
   - 后续调用直接返回成功（不重复执行）

2. **返回值**：必须返回 `bool` 类型
   - `True`：停止成功
   - `False`：停止失败（超时、资源未释放等）
   - 注意：返回 `None` 会被视为成功（向后兼容）

3. **异常处理**：尽量不抛出异常
   - 内部捕获异常并记录日志
   - 返回 `False` 表示失败
   - 只在严重错误时抛出异常

4. **同步执行**：`stop()` 方法应该是同步的
   - 等待所有资源清理完成后才返回
   - 使用 `thread.join(timeout)` 等待线程结束
   - 不使用异步或后台清理

5. **超时处理**：设置合理的超时时间
   - 接受 `timeout` 参数（默认值建议 5.0 秒）
   - 超时后返回 `False`（不清理引用，保持状态一致性）
   - 记录超时日志

6. **资源清理**：确保资源正确释放
   - 线程：使用 `thread.join(timeout)` 等待
   - 队列：清空或标记为关闭
   - 连接：关闭网络/设备连接
   - 订阅：取消事件订阅

7. **日志记录**：记录关键操作
   - 开始停止：INFO 级别
   - 停止成功：INFO 级别
   - 停止失败：ERROR 级别
   - 超时：ERROR 级别

8. **线程安全**：使用锁保护状态
   - 使用 `threading.Lock` 或 `threading.RLock`
   - 保护 `_is_running` 等状态变量
   - 防止并发调用导致的竞态条件

#### 推荐实现模板

```python
def stop(self, timeout: float = 5.0) -> bool:
    """停止模块
    
    Args:
        timeout: 等待线程停止的超时时间（秒）
        
    Returns:
        bool: 是否成功停止
    """
    with self._running_lock:
        # 1. 幂等性检查
        if not self._is_running:
            logger.info(f"{self.__class__.__name__} 未在运行")
            return True
        
        logger.info(f"正在停止 {self.__class__.__name__}...")
        
        # 2. 设置停止信号
        self._stop_event.set()
        
        # 3. 等待线程结束（带超时）
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            
            if self._thread.is_alive():
                logger.error(f"线程停止超时 ({timeout}s)")
                # 注意：超时时不清理引用，保持状态一致性
                return False
        
        # 4. 清理状态（只在成功时执行）
        self._is_running = False
        self._thread = None
        
        # 5. 记录成功日志
        logger.info(f"{self.__class__.__name__} 已停止")
        return True
```

#### 需要适配的模块

**需要适配的模块：**
- `oak_vision_system/modules/can_communication/` - CAN 通信模块 ✅ 已完成
- `oak_vision_system/modules/data_collector/` - 数据采集模块 ✅ 已完成
- `oak_vision_system/modules/data_processing/` - 数据处理模块 ✅ 已完成
- `oak_vision_system/modules/display_modules/` - 显示模块 ✅ 已完成
- 其他自定义模块

**适配状态：**
- ✅ DisplayManager: 100% 合规（已完成适配）
- ✅ CANCommunicator: 100% 合规（已完成适配）
- ✅ OAKDataCollector: 100% 合规（已完成适配）
- ✅ DataProcessor: 100% 合规（已符合规范）

**注意：** 子模块的适配工作已在 SystemManager 实现完成后进行。详细的适配指南请参考 `docs/module_stop_method_guide.md`。

### 显示模块退出逻辑适配

**当前行为：**
- 显示模块检测到键盘事件 'q' 时，直接退出自身的循环线程

**需要修改为：**
- 显示模块检测到键盘事件 'q' 时，发布 `SYSTEM_SHUTDOWN` 事件到事件总线
- 事件数据应包含 `reason="user_quit"` 或 `reason="key_q"`
- 不再直接退出自身循环，而是等待 SystemManager 统一关闭

**修改示例：**
```python
# 当前实现（需要修改）
if key == ord('q'):
    break  # 直接退出循环

# 修改后的实现
if key == ord('q'):
    from oak_vision_system.core.system_manager import ShutdownEvent
    self.event_bus.publish(
        "SYSTEM_SHUTDOWN",
        ShutdownEvent(reason="user_quit")
    )
    # 继续运行，等待 SystemManager 调用 stop()
```

**相关需求：** Requirement 4, Requirement 5, Requirement 6

**执行顺序：**
1. 先实现 SystemManager
2. 适配显示模块的 'q' 键退出逻辑
3. 适配其他子模块的 `stop()` 方法
