# 子模块 stop() 方法适配指南

## 概述

本文档提供了子模块 `stop()` 方法的规范说明、实现模板和适配清单。所有被 SystemManager 管理的子模块都需要遵循这些规范，以确保系统能够可靠地启动和关闭。

**为什么需要规范？**

SystemManager 在 shutdown 机制增强后，增加了兜底机制来处理模块停止失败的情况。为了让这个机制正常工作，所有子模块的 `stop()` 方法需要：
1. 返回 `bool` 值表示成功/失败
2. 实现幂等性（可以多次调用）
3. 正确处理超时情况
4. 使用线程安全的方式管理状态

---

## 核心规范

### 1. 幂等性

`stop()` 方法可以被多次调用而不出错。

**要求：**
- 第一次调用执行关闭逻辑
- 后续调用直接返回成功（不重复执行）
- 使用状态标志（如 `_is_running`）判断是否已停止

**示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    with self._running_lock:
        # 幂等性检查
        if not self._is_running:
            self._logger.info(f"{self.__class__.__name__} 未在运行")
            return True  # 已经停止，直接返回成功
        
        # 执行关闭逻辑...
```

### 2. 返回值

必须返回 `bool` 类型表示停止是否成功。

**要求：**
- `True`：停止成功
- `False`：停止失败（超时、资源未释放等）
- 注意：返回 `None` 会被 SystemManager 视为成功（向后兼容）

**示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    # ... 执行关闭逻辑 ...
    
    if self._thread.is_alive():
        self._logger.error(f"线程停止超时 ({timeout}s)")
        return False  # 停止失败
    
    self._logger.info(f"{self.__class__.__name__} 已停止")
    return True  # 停止成功
```

### 3. 异常处理

尽量不抛出异常，内部捕获并返回 `False`。

**要求：**
- 内部捕获异常并记录日志
- 返回 `False` 表示失败
- 只在严重错误时抛出异常（如资源损坏）

**示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    try:
        # 执行关闭逻辑
        self._cleanup_resources()
        return True
    except Exception as e:
        self._logger.error(f"停止失败: {e}", exc_info=True)
        return False  # 返回失败而不是抛出异常
```

### 4. 同步执行

`stop()` 方法应该是同步的，等待所有资源清理完成后才返回。

**要求：**
- 等待所有资源清理完成后才返回
- 使用 `thread.join(timeout)` 等待线程结束
- 不使用异步或后台清理

**示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    # 设置停止信号
    self._stop_event.set()
    
    # 同步等待线程结束
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=timeout)  # 阻塞等待
        
        if self._thread.is_alive():
            return False  # 超时失败
    
    return True  # 成功
```

### 5. 超时处理

设置合理的超时时间，超时后返回 `False`。

**要求：**
- 接受 `timeout` 参数（默认值建议 5.0 秒）
- 超时后返回 `False`（不清理引用，保持状态一致性）
- 记录超时日志

**示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    # 等待线程结束（带超时）
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=timeout)
        
        if self._thread.is_alive():
            self._logger.error(f"线程停止超时 ({timeout}s)")
            # 注意：超时时不清理引用，保持状态一致性
            return False
    
    # 只在成功时清理状态
    self._is_running = False
    self._thread = None
    return True
```

**为什么超时时不清理引用？**
- 保持状态一致性（`_is_running` 仍为 `True`）
- 避免误导性状态（线程还在运行但引用被清空）
- 方便 SystemManager 检测失败并触发兜底机制

### 6. 资源清理

确保资源正确释放。

**要求：**
- 线程：使用 `thread.join(timeout)` 等待
- 队列：清空或标记为关闭
- 连接：关闭网络/设备连接
- 订阅：取消事件订阅

**示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    # 1. 设置停止信号
    self._stop_event.set()
    
    # 2. 等待线程结束
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            return False
    
    # 3. 清理资源（只在成功时执行）
    self._queue.clear()  # 清空队列
    self._connection.close()  # 关闭连接
    self._event_bus.unsubscribe(...)  # 取消订阅
    
    # 4. 清理状态
    self._is_running = False
    self._thread = None
    
    return True
```

### 7. 日志记录

记录关键操作，方便调试。

**要求：**
- 开始停止：INFO 级别
- 停止成功：INFO 级别
- 停止失败：ERROR 级别
- 超时：ERROR 级别

**示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    self._logger.info(f"正在停止 {self.__class__.__name__}...")  # INFO
    
    # ... 执行关闭逻辑 ...
    
    if self._thread.is_alive():
        self._logger.error(f"线程停止超时 ({timeout}s)")  # ERROR
        return False
    
    self._logger.info(f"{self.__class__.__name__} 已停止")  # INFO
    return True
```

### 8. 线程安全

使用锁保护状态，防止并发调用导致的竞态条件。

**要求：**
- 使用 `threading.Lock` 或 `threading.RLock`
- 保护 `_is_running` 等状态变量
- 防止并发调用导致的竞态条件

**示例：**
```python
def __init__(self):
    self._running_lock = threading.RLock()  # 可重入锁
    self._is_running = False

def stop(self, timeout: float = 5.0) -> bool:
    with self._running_lock:  # 使用锁保护
        # 幂等性检查
        if not self._is_running:
            return True
        
        # 执行关闭逻辑...
        
        # 更新状态
        self._is_running = False
        return True
```

---

## 推荐实现模板

以下是一个完整的 `stop()` 方法实现模板，遵循所有规范：

```python
import logging
import threading

class MyModule:
    """示例模块"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._running_lock = threading.RLock()
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread = None
    
    def start(self):
        """启动模块"""
        with self._running_lock:
            if self._is_running:
                self._logger.warning("模块已在运行")
                return
            
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop)
            self._thread.start()
            self._is_running = True
            self._logger.info("模块已启动")
    
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
                self._logger.info(f"{self.__class__.__name__} 未在运行")
                return True
            
            self._logger.info(f"正在停止 {self.__class__.__name__}...")
            
            # 2. 设置停止信号
            self._stop_event.set()
            
            # 3. 等待线程结束（带超时）
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=timeout)
                
                if self._thread.is_alive():
                    self._logger.error(f"线程停止超时 ({timeout}s)")
                    # 注意：超时时不清理引用，保持状态一致性
                    return False
            
            # 4. 清理资源（只在成功时执行）
            try:
                self._cleanup_resources()
            except Exception as e:
                self._logger.error(f"资源清理失败: {e}", exc_info=True)
                return False
            
            # 5. 清理状态
            self._is_running = False
            self._thread = None
            
            # 6. 记录成功日志
            self._logger.info(f"{self.__class__.__name__} 已停止")
            return True
    
    def _run_loop(self):
        """主循环（在独立线程中运行）"""
        while not self._stop_event.is_set():
            # 执行工作...
            self._stop_event.wait(timeout=0.1)
    
    def _cleanup_resources(self):
        """清理资源"""
        # 清空队列、关闭连接、取消订阅等
        pass
```

---

## 常见错误

### 错误 1：不返回 bool 值

**错误示例：**
```python
def stop(self):  # 没有返回值
    self._stop_event.set()
    self._thread.join()
    # 没有 return 语句
```

**正确示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    self._stop_event.set()
    self._thread.join(timeout=timeout)
    
    if self._thread.is_alive():
        return False  # 超时失败
    
    return True  # 成功
```

### 错误 2：没有幂等性检查

**错误示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    # 没有检查是否已停止
    self._stop_event.set()
    self._thread.join(timeout=timeout)
    return not self._thread.is_alive()
```

**正确示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    with self._running_lock:
        # 幂等性检查
        if not self._is_running:
            return True  # 已停止，直接返回
        
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        
        if self._thread.is_alive():
            return False
        
        self._is_running = False
        return True
```

### 错误 3：超时时清理引用

**错误示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    self._stop_event.set()
    self._thread.join(timeout=timeout)
    
    # 错误：无论是否超时都清理引用
    self._is_running = False
    self._thread = None
    
    return not self._thread.is_alive()  # 这里 _thread 已经是 None
```

**正确示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    self._stop_event.set()
    self._thread.join(timeout=timeout)
    
    if self._thread.is_alive():
        # 超时：不清理引用，保持状态一致性
        return False
    
    # 只在成功时清理引用
    self._is_running = False
    self._thread = None
    return True
```

### 错误 4：没有线程安全保护

**错误示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    # 没有锁保护，可能导致竞态条件
    if not self._is_running:
        return True
    
    self._stop_event.set()
    # ... 其他逻辑 ...
    self._is_running = False
    return True
```

**正确示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    with self._running_lock:  # 使用锁保护
        if not self._is_running:
            return True
        
        self._stop_event.set()
        # ... 其他逻辑 ...
        self._is_running = False
        return True
```

### 错误 5：抛出异常而不是返回 False

**错误示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    self._stop_event.set()
    self._thread.join(timeout=timeout)
    
    if self._thread.is_alive():
        raise TimeoutError("线程停止超时")  # 错误：抛出异常
    
    return True
```

**正确示例：**
```python
def stop(self, timeout: float = 5.0) -> bool:
    self._stop_event.set()
    self._thread.join(timeout=timeout)
    
    if self._thread.is_alive():
        self._logger.error(f"线程停止超时 ({timeout}s)")
        return False  # 返回 False 而不是抛出异常
    
    return True
```

---

## 模块适配清单

### 已适配模块

| 模块名称 | 文件路径 | 合规性 | 状态 | 备注 |
|---------|---------|--------|------|------|
| DisplayManager | `oak_vision_system/modules/display_modules/display_renderer.py` | 100% | ✅ 已完成 | 已添加幂等性检查、返回值、超时处理、线程安全 |
| CANCommunicator | `oak_vision_system/modules/can_communication/can_communicator.py` | 100% | ✅ 已完成 | 已添加幂等性检查、返回值、超时参数、线程安全 |
| OAKDataCollector | `oak_vision_system/modules/data_collector/collector.py` | 100% | ✅ 已完成 | 已添加幂等性检查、返回值、超时处理、线程安全 |
| DataProcessor | `oak_vision_system/modules/data_processing/data_processor.py` | 100% | ✅ 已完成 | 已符合规范（最佳实践） |

### 适配检查清单

使用以下清单检查模块是否符合规范：

- [ ] **幂等性**：可以多次调用 `stop()` 而不出错
- [ ] **返回值**：返回 `bool` 类型（`True` 成功，`False` 失败）
- [ ] **异常处理**：内部捕获异常，返回 `False` 而不是抛出
- [ ] **同步执行**：等待所有资源清理完成后才返回
- [ ] **超时处理**：接受 `timeout` 参数，超时后返回 `False`
- [ ] **超时不清理**：超时时不清理引用，保持状态一致性
- [ ] **资源清理**：正确释放线程、队列、连接、订阅等资源
- [ ] **日志记录**：记录开始、成功、失败、超时等关键操作
- [ ] **线程安全**：使用锁保护状态变量

---

## 适配步骤

### 步骤 1：审查当前实现

1. 检查是否有幂等性检查
2. 检查是否返回 `bool` 值
3. 检查是否有超时处理
4. 检查是否有线程安全保护

### 步骤 2：修改实现

根据规范和模板修改 `stop()` 方法：

1. 添加幂等性检查（如果缺少）
2. 修改返回类型为 `bool`
3. 添加 `timeout` 参数（如果缺少）
4. 添加超时处理逻辑
5. 添加线程安全保护（如果缺少）
6. 更新文档字符串

### 步骤 3：编写/更新测试

为修改后的实现编写或更新单元测试：

1. 测试幂等性（多次调用）
2. 测试返回值（成功/失败）
3. 测试超时处理
4. 测试线程安全（并发调用）

### 步骤 4：验证

1. 运行单元测试确保通过
2. 运行集成测试确保与 SystemManager 正常工作
3. 手动测试各种场景（正常关闭、超时、异常等）

---

## 测试示例

以下是一个完整的测试示例，验证 `stop()` 方法是否符合规范：

```python
import unittest
import threading
import time

class TestModuleStopCompliance(unittest.TestCase):
    """测试模块 stop() 方法是否符合规范"""
    
    def setUp(self):
        """设置测试环境"""
        self.module = MyModule()
    
    def test_stop_returns_bool(self):
        """测试 stop() 返回 bool 值"""
        self.module.start()
        result = self.module.stop()
        self.assertIsInstance(result, bool)
    
    def test_stop_idempotent(self):
        """测试 stop() 幂等性"""
        self.module.start()
        
        # 第一次调用
        result1 = self.module.stop()
        self.assertTrue(result1)
        
        # 第二次调用（应该直接返回成功）
        result2 = self.module.stop()
        self.assertTrue(result2)
    
    def test_stop_timeout(self):
        """测试 stop() 超时处理"""
        # 创建一个不会停止的模块
        module = SlowStoppingModule()
        module.start()
        
        # 使用短超时
        result = module.stop(timeout=0.1)
        
        # 应该返回 False（超时）
        self.assertFalse(result)
    
    def test_stop_thread_safe(self):
        """测试 stop() 线程安全"""
        self.module.start()
        
        results = []
        
        def call_stop():
            result = self.module.stop()
            results.append(result)
        
        # 并发调用 stop()
        threads = [threading.Thread(target=call_stop) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 所有调用都应该成功
        self.assertTrue(all(results))
    
    def test_stop_success(self):
        """测试 stop() 成功场景"""
        self.module.start()
        time.sleep(0.1)  # 让模块运行一会儿
        
        result = self.module.stop()
        
        self.assertTrue(result)
        self.assertFalse(self.module._is_running)
```

---

## 参考资料

- **SystemManager 设计文档**: `.kiro/specs/system-manager/design.md`
- **SystemManager 需求文档**: `.kiro/specs/system-manager/requirements.md`
- **Shutdown 增强任务**: `.kiro/specs/system-manager/shutdown-enhancement-tasks.md`
- **SystemManager 实现**: `oak_vision_system/core/system_manager/system_manager.py`

---

## 总结

遵循本指南的规范，可以确保：

1. ✅ 模块能够可靠地停止
2. ✅ SystemManager 能够检测停止失败
3. ✅ 兜底机制能够正常工作
4. ✅ 系统能够可靠地退出
5. ✅ 代码易于维护和调试

如有问题或疑问，请参考本文档或查阅相关代码实现。

