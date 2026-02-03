# Design Document: SystemManager（简化版）

## Overview

SystemManager 是一个简洁的系统管理器，负责统一管理所有功能模块的生命周期。它提供清晰的启动/运行/关闭机制，确保系统能够优雅地启动和退出。

### 核心设计原则

1. **简洁性**：事件回调只做"置位"，不执行复杂操作
2. **统一退出点**：所有退出路径汇聚到 `finally` 块
3. **防重复执行**：使用 Event 防止多次关闭
4. **职责分离**：回调负责"发信号"，`run()` 负责"执行关闭"

### 核心职责

1. **模块管理**：注册、存储模块信息
2. **优先级调度**：按优先级启动（下游→上游）和关闭（上游→下游）
3. **启动失败回滚**：启动失败时自动回滚已启动的模块
4. **两个退出出口**：KeyboardInterrupt 和 SYSTEM_SHUTDOWN 事件
5. **统一关闭流程**：确保所有模块按正确顺序关闭

---

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      SystemManager                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Module       │  │ Lifecycle    │  │ Event        │     │
│  │ Registry     │  │ Controller   │  │ Subscriber   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐                       │
│  │ Logging      │  │ Exit         │                       │
│  │ Initializer  │  │ Controller   │                       │
│  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ↓                    ↓                    ↓
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   EventBus      │  │   Modules       │  │   User Input    │
│   (事件总线)     │  │   (功能模块)     │  │   (Ctrl+C/'q')  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 模块交互流程

```
启动流程：
SystemManager.start_all()
    ↓
按优先级从高到低启动模块（下游→上游）
    ↓
Display(50) → Processor(30) → Collector(10)
    ↓
SystemManager.run()
    ↓
主线程阻塞在 Event.wait()

退出流程（出口1 - KeyboardInterrupt）：
用户按 Ctrl+C
    ↓
run() 方法的 except KeyboardInterrupt 捕获
    ↓
记录日志
    ↓
进入 finally 块
    ↓
调用 shutdown()

退出流程（出口2 - SYSTEM_SHUTDOWN 事件）：
用户在显示窗口按 'q'
    ↓
显示模块发布 SYSTEM_SHUTDOWN 事件
    ↓
SystemManager._on_shutdown_event() 设置 _shutdown_event
    ↓
run() 方法的 while 循环退出
    ↓
进入 finally 块
    ↓
调用 shutdown()

关闭流程：
shutdown() 方法
    ↓
检查 _stop_started（防重复）
    ↓
按优先级从低到高关闭模块（上游→下游）
    ↓
Collector(10) → Processor(30) → Display(50)
    ↓
关闭事件总线
    ↓
恢复异常钩子
```

---

## Components and Interfaces

### 1. ModuleState（枚举）

```python
class ModuleState(Enum):
    """模块状态枚举（简化版：4个状态）"""
    NOT_STARTED = "not_started"  # 未启动
    RUNNING = "running"          # 运行中
    STOPPED = "stopped"          # 已停止
    ERROR = "error"              # 错误状态
```

**状态转换：**
```
NOT_STARTED → RUNNING → STOPPED
任何阶段发生错误 → ERROR
```

### 2. ManagedModule（数据类）

```python
@dataclass
class ManagedModule:
    """被管理的模块包装类"""
    name: str                    # 模块名称（唯一标识）
    instance: Any                # 模块实例（必须有 start() 和 stop() 方法）
    priority: int                # 优先级（数字越大越靠近下游）
    state: ModuleState           # 模块状态
```

**优先级说明：**
- 数字越大表示越靠近下游（消费者）
- 数字越小表示越靠近上游（生产者）
- 启动时从高到低（下游→上游）
- 关闭时从低到高（上游→下游）

**示例优先级：**
- 显示模块：50
- 数据处理器：30
- 数据采集器：10

### 3. ShutdownEvent（数据类）

```python
@dataclass
class ShutdownEvent:
    """系统停止事件"""
    reason: str  # 停止原因："user_quit", "window_closed" 等
```

### 4. SystemManager（主类）

```python
class SystemManager:
    """系统管理器（简化版）"""
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        system_config: Optional[SystemConfigDTO] = None,
        default_stop_timeout: float = 5.0
    ):
        """
        初始化 SystemManager
        
        Args:
            event_bus: 事件总线实例（可选，默认使用全局单例）
            system_config: 系统配置对象（可选，用于日志初始化）
            default_stop_timeout: 默认模块关闭超时时间（秒），默认5.0秒
        """
        pass
    
    # ==================== 模块管理 ====================
    
    def register_module(self, name: str, instance: Any, priority: int) -> None:
        """
        注册模块
        
        Args:
            name: 模块名称（唯一标识）
            instance: 模块实例（必须有 start() 和 stop() 方法）
            priority: 优先级（数字越大越靠近下游）
        
        Raises:
            ValueError: 如果模块名称已存在
        """
        pass
    
    def start_all(self) -> None:
        """
        启动所有注册的模块
        
        按优先级从高到低启动（下游→上游）
        如果任何模块启动失败，触发回滚
        
        Raises:
            RuntimeError: 如果任何模块启动失败
        """
        pass
    
    # ==================== 主循环和退出 ====================
    
    def run(self) -> None:
        """
        运行系统并阻塞主线程
        
        两个退出出口：
        1. KeyboardInterrupt（Ctrl+C）- except 块捕获
        2. SYSTEM_SHUTDOWN 事件 - 设置 _shutdown_event
        
        所有退出路径汇聚到 finally 块，统一调用 shutdown()
        """
        pass
    
    def shutdown(self) -> None:
        """
        关闭系统
        
        流程：
        1. 检查 _stop_started 防止重复关闭
        2. 按优先级从低到高关闭模块（上游→下游）
        3. 关闭事件总线
        4. 恢复异常钩子
        """
        pass
    
    # ==================== 事件处理 ====================
    
    def _on_shutdown_event(self, event: ShutdownEvent) -> None:
        """
        处理 SYSTEM_SHUTDOWN 事件
        
        只做一件事：设置 _shutdown_event 标志
        """
        pass
    
    # ==================== 状态查询 ====================
    
    def get_status(self) -> Dict[str, str]:
        """
        获取所有模块的状态
        
        Returns:
            Dict[str, str]: 模块名称 -> 状态字符串的映射
        """
        pass
    
    def is_shutting_down(self) -> bool:
        """检查系统是否正在关闭"""
        pass
    
    # ==================== 上下文管理器 ====================
    
    def __enter__(self) -> "SystemManager":
        """进入 with 块时自动调用 start_all()"""
        pass
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """退出 with 块时自动调用 shutdown()"""
        pass
```

---

## Data Models

### 内部数据结构

```python
class SystemManager:
    def __init__(self, ...):
        # 事件总线
        self._event_bus: EventBus
        
        # 配置参数
        self._default_stop_timeout: float
        
        # 模块管理
        self._modules: Dict[str, ManagedModule] = {}
        
        # 退出控制
        self._shutdown_event: threading.Event  # 退出信号
        self._stop_started: threading.Event    # 防重复关闭
        
        # 日志
        self._logger: logging.Logger
        
        # 异常钩子句柄
        self._exception_handle: _HookHandle
```

### 优先级示例

```python
# 典型的模块优先级配置
modules = {
    "display": priority=50,      # 显示层（下游）
    "processor": priority=30,    # 处理层（中游）
    "collector": priority=10,    # 数据源（上游）
}

# 启动顺序（从高到低）：
# 50 (display) → 30 (processor) → 10 (collector)

# 关闭顺序（从低到高）：
# 10 (collector) → 30 (processor) → 50 (display)
```

---

## Key Implementation Details

### 1. 两个退出出口的实现

```python
def run(self):
    """主循环：两个退出出口"""
    try:
        self._logger.info("SystemManager 开始运行...")
        
        # 主循环：等待退出信号
        while not self._shutdown_event.is_set():
            self._shutdown_event.wait(timeout=0.5)
            # 出口2：SYSTEM_SHUTDOWN 事件设置 _shutdown_event
    
    except KeyboardInterrupt:
        # 出口1：Ctrl+C
        self._logger.info("捕获到 KeyboardInterrupt (Ctrl+C)")
    
    finally:
        # 统一退出点：两个出口都汇聚到这里
        if not self._stop_started.is_set():
            self.shutdown()
```

### 2. 事件订阅（只做置位）

```python
def __init__(self, ...):
    # 订阅 SYSTEM_SHUTDOWN 事件
    self._event_bus.subscribe(
        "SYSTEM_SHUTDOWN",
        self._on_shutdown_event,
        subscriber_name="SystemManager"
    )

def _on_shutdown_event(self, event: ShutdownEvent):
    """事件处理：只做置位，不执行复杂操作"""
    reason = getattr(event, 'reason', 'unknown')
    self._logger.info(f"接收到退出事件: {reason}")
    self._shutdown_event.set()  # 只做这一件事
```

### 3. 防重复关闭

```python
def shutdown(self):
    """关闭系统（防重复）"""
    # 检查是否已经开始关闭
    if self._stop_started.is_set():
        self._logger.debug("shutdown() 已经执行过，跳过")
        return
    
    # 设置标志，防止重复关闭
    self._stop_started.set()
    
    self._logger.info("开始关闭系统...")
    
    # 执行关闭逻辑...
```

### 4. 启动失败回滚

```python
def start_all(self):
    """启动所有模块（带回滚）"""
    sorted_modules = sorted(
        self._modules.values(),
        key=lambda m: m.priority,
        reverse=True  # 降序：优先级高的先启动
    )
    
    started = []
    try:
        for module in sorted_modules:
            self._logger.info(f"启动模块: {module.name}")
            module.instance.start()
            module.state = ModuleState.RUNNING
            started.append(module)
    
    except Exception as e:
        self._logger.error(f"模块启动失败: {e}")
        
        # 回滚：按相反顺序停止已启动的模块
        for module in reversed(started):
            try:
                self._logger.info(f"回滚停止: {module.name}")
                module.instance.stop()
                module.state = ModuleState.STOPPED
            except Exception as stop_err:
                self._logger.error(f"回滚失败: {stop_err}")
                module.state = ModuleState.ERROR
        
        raise  # 重新抛出原始异常
```

### 5. 按优先级关闭

```python
def shutdown(self):
    """关闭所有模块"""
    if self._stop_started.is_set():
        return
    self._stop_started.set()
    
    self._logger.info("开始关闭所有模块...")
    
    # 按优先级升序排序（与启动相反）
    sorted_modules = sorted(
        self._modules.values(),
        key=lambda m: m.priority  # 升序：优先级低的先关闭
    )
    
    for module in sorted_modules:
        if module.state != ModuleState.RUNNING:
            continue
        
        try:
            self._logger.info(f"停止模块: {module.name}")
            module.instance.stop()
            module.state = ModuleState.STOPPED
        except Exception as e:
            self._logger.error(f"停止模块失败 {module.name}: {e}")
            module.state = ModuleState.ERROR
    
    # 关闭事件总线
    try:
        self._logger.info("关闭事件总线...")
        self._event_bus.close(wait=True, cancel_pending=False)
    except Exception as e:
        self._logger.error(f"关闭事件总线失败: {e}")
    
    # 恢复异常钩子
    try:
        self._exception_handle.detach()
    except Exception as e:
        self._logger.error(f"恢复异常钩子失败: {e}")
    
    self._logger.info("SystemManager 关闭完成")
```

### 6. 日志系统初始化

```python
def __init__(self, ...):
    # 初始化日志系统
    if system_config:
        try:
            from oak_vision_system.utils.logging_utils import configure_logging
            configure_logging(system_config)
        except Exception as e:
            logging.basicConfig(level=logging.INFO)
            logging.warning(f"日志配置失败: {e}")
    
    # 创建 logger 实例
    self._logger = logging.getLogger(__name__)
```

### 7. 异常钩子（只记录日志）

```python
def __init__(self, ...):
    # 安装异常钩子：只用于记录日志
    from oak_vision_system.utils.logging_utils import attach_exception_logger
    
    exception_logger = logging.getLogger(f"{__name__}.exceptions")
    self._exception_handle = attach_exception_logger(
        exception_logger,
        handle_threads=True,
        ignore_keyboard_interrupt=True  # 忽略 KeyboardInterrupt
    )
    
    # 注意：不包装钩子来设置退出标志
    # 异常钩子只用于记录日志，不触发退出
```

---

## Error Handling

### 异常处理策略

1. **模块启动失败**
   - 捕获异常
   - 设置模块状态为 ERROR
   - 触发回滚：停止所有已启动的模块
   - 重新抛出原始异常

2. **模块关闭失败**
   - 捕获异常
   - 记录错误日志
   - 设置模块状态为 ERROR
   - 继续关闭其他模块（不阻塞）

3. **事件总线关闭失败**
   - 捕获异常
   - 记录错误日志
   - 不抛出异常（确保 shutdown 完成）

4. **异常钩子恢复失败**
   - 捕获异常
   - 记录错误日志
   - 不抛出异常

### 错误恢复保证

- **启动失败**：所有已启动的模块被停止
- **关闭失败**：其他模块仍然被关闭
- **事件总线**：总是尝试关闭
- **异常钩子**：总是尝试恢复

---

## Testing Strategy

### 单元测试

**测试重点：**
1. 模块注册（正常、重复注册）
2. 模块启动（单个、多个、按优先级）
3. 启动失败回滚
4. 模块关闭（单个、多个、按优先级）
5. 防重复关闭
6. 状态查询
7. 上下文管理器

**Mock 对象：**
```python
class MockModule:
    """用于测试的模拟模块"""
    def __init__(self, should_fail_start=False, should_fail_stop=False):
        self.should_fail_start = should_fail_start
        self.should_fail_stop = should_fail_stop
        self.start_called = False
        self.stop_called = False
        self._running = False
    
    def start(self):
        if self.should_fail_start:
            raise RuntimeError("Mock start failure")
        self.start_called = True
        self._running = True
    
    def stop(self):
        self.stop_called = True
        if self.should_fail_stop:
            raise RuntimeError("Mock stop failure")
        self._running = False
    
    def is_running(self):
        return self._running
```

### 集成测试

**测试场景：**
1. 完整生命周期：init → register → start → run → shutdown
2. KeyboardInterrupt 退出
3. SYSTEM_SHUTDOWN 事件退出
4. 多模块场景
5. 启动失败场景
6. 关闭失败场景

---

## Usage Examples

### 基本用法

```python
# 创建管理器
manager = SystemManager(system_config=config)

# 注册模块（按优先级）
manager.register_module("collector", collector, priority=10)
manager.register_module("processor", processor, priority=30)
manager.register_module("display", display, priority=50)

# 启动所有模块
manager.start_all()  # 按优先级 50→30→10 启动

# 运行主循环（阻塞）
manager.run()  # 等待 Ctrl+C 或 SYSTEM_SHUTDOWN 事件

# 自动关闭（在 finally 块中）
# - 按优先级 10→30→50 关闭模块
# - 关闭事件总线
# - 恢复异常钩子
```

### 使用上下文管理器

```python
with SystemManager(system_config=config) as manager:
    manager.register_module("collector", collector, priority=10)
    manager.register_module("processor", processor, priority=30)
    manager.register_module("display", display, priority=50)
    manager.run()
# 自动调用 shutdown()
```

---

## Design Decisions

### 1. 为什么只有两个退出出口？

**原因：**
- 简化退出逻辑，避免多个退出路径导致的复杂性
- KeyboardInterrupt 是最直接的用户中断方式
- SYSTEM_SHUTDOWN 事件是模块间协调退出的标准方式

**不支持的退出方式：**
- ❌ SIGTERM 信号（可以后续扩展）
- ❌ 全局异常钩子触发退出（异常钩子只记录日志）

### 2. 为什么事件回调只做"置位"？

**原因：**
- 避免在回调线程中执行复杂操作
- 防止死锁和竞态条件
- 保持退出流程的可预测性

**设计：**
```python
def _on_shutdown_event(self, event):
    self._shutdown_event.set()  # 只做这一件事
```

### 3. 为什么使用 `finally` 块统一退出？

**原因：**
- 确保所有退出路径都执行关闭逻辑
- 避免遗漏资源清理
- 代码更清晰易读

**设计：**
```python
def run(self):
    try:
        # 主循环
        ...
    except KeyboardInterrupt:
        # 记录日志
        ...
    finally:
        # 统一退出点
        if not self._stop_started.is_set():
            self.shutdown()
```

### 4. 为什么简化状态机？

**原因：**
- 6个状态（NOT_STARTED, STARTING, RUNNING, STOPPING, STOPPED, ERROR）过于复杂
- STARTING 和 STOPPING 是瞬态，不需要单独状态
- 4个状态（NOT_STARTED, RUNNING, STOPPED, ERROR）足够表达模块生命周期

**简化后的状态转换：**
```
NOT_STARTED → RUNNING → STOPPED
任何阶段发生错误 → ERROR
```

---

## Comparison with Previous Design

| 特性 | 之前的设计 | 简化后的设计 |
|------|-----------|-------------|
| 代码行数 | ~500行 | ~200行 |
| 状态数量 | 6个状态 | 4个状态 |
| 退出方式 | 4种（事件/SIGINT/SIGTERM/异常） | 2种（KeyboardInterrupt/事件） |
| 信号处理 | 注册 signal.signal | 不注册，用 try-except |
| 事件处理 | 复杂（发布事件+置位） | 简单（只置位） |
| 退出路径 | 多个分散的退出点 | 统一的 finally 块 |
| 异常钩子 | 触发退出 | 只记录日志 |
| 关闭回调 | 支持 | 不支持（简化） |
| 超时处理 | 复杂的超时控制 | 简化的默认超时 |
| 可读性 | 较复杂 | 清晰简洁 |
| 功能完整性 | 100% | 90%（删除非核心功能） |

---

## Summary

SystemManager 简化版设计保留了核心功能，删除了过度复杂的特性：

**保留的核心功能：**
- ✅ 模块注册和管理
- ✅ 按优先级启动/关闭
- ✅ 启动失败回滚
- ✅ 两个明确的退出出口
- ✅ 统一的关闭流程
- ✅ 防重复关闭
- ✅ 事件总线关闭
- ✅ 日志系统初始化
- ✅ 异常日志记录

**删除的复杂功能：**
- ❌ 复杂的状态机（6个→4个状态）
- ❌ 信号处理器（signal.signal）
- ❌ 异常钩子触发退出
- ❌ 关闭回调机制
- ❌ 复杂的超时处理
- ❌ 过度的配置项

**设计目标达成：**
- 代码量减少 60%
- 退出逻辑清晰明确
- 易于理解和维护
- 保留所有核心功能
