# 迁移指南

本文档包含系统重要变更的迁移说明。

## 目录

1. [SystemManager Shutdown 机制增强](#systemmanager-shutdown-机制增强)
2. [配置管理器重构](#配置管理器重构)

---

## SystemManager Shutdown 机制增强

**更新日期**: 2026-02-03  
**版本**: v2.1.0  
**影响范围**: 所有使用 SystemManager 的代码和自定义模块

### 📌 重要变更

#### 1. 新增强制退出兜底机制

SystemManager 现在能够检测模块停止失败，并在宽限期后强制退出进程，确保系统能够可靠退出。

**变更内容：**
- 新增 `force_exit_grace_period` 参数（默认 3.0 秒）
- `shutdown()` 方法现在会检查模块 `stop()` 方法的返回值
- 如果模块停止失败，系统会在宽限期后调用 `os._exit(1)` 强制退出

#### 2. 模块 stop() 方法规范化

所有被 SystemManager 管理的模块，其 `stop()` 方法需要遵循新的规范。

**核心要求：**
1. **返回值**：必须返回 `bool` 类型（`True` 成功，`False` 失败）
2. **幂等性**：可以被多次调用而不出错
3. **超时处理**：接受 `timeout` 参数，超时后返回 `False`
4. **线程安全**：使用锁保护状态变量

---

### ✅ 向后兼容

**好消息**：现有代码基本无需修改！

#### SystemManager 使用者

如果你只是使用 SystemManager 管理模块，无需任何修改：

```python
# 现有代码继续工作
manager = SystemManager(system_config=config)
manager.register_module("collector", collector, priority=10)
manager.start_all()
manager.run()
```

**可选配置**：如果需要调整强制退出宽限期：

```python
# 新增可选参数
manager = SystemManager(
    system_config=config,
    force_exit_grace_period=5.0  # 默认 3.0 秒
)
```

#### 模块开发者

如果你的模块 `stop()` 方法返回 `None`，SystemManager 会将其视为成功（向后兼容）。

**但强烈建议**按照新规范更新模块，以便：
- SystemManager 能够检测停止失败
- 兜底机制能够正常工作
- 提高系统可靠性

---

### 📝 迁移步骤

#### 步骤 1：检查现有模块

检查你的自定义模块是否符合新规范：

```python
# 检查清单
# [ ] stop() 方法返回 bool 值
# [ ] 实现了幂等性检查
# [ ] 接受 timeout 参数
# [ ] 使用锁保护状态
```

#### 步骤 2：更新模块实现

如果模块不符合规范，参考以下模板更新：

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
                return False  # 超时失败
        
        # 4. 清理状态（只在成功时执行）
        self._is_running = False
        self._thread = None
        
        # 5. 记录成功日志
        logger.info(f"{self.__class__.__name__} 已停止")
        return True
```

#### 步骤 3：更新测试

为更新后的 `stop()` 方法编写测试：

```python
def test_stop_returns_bool(self):
    """测试 stop() 返回 bool 值"""
    self.module.start()
    result = self.module.stop()
    self.assertIsInstance(result, bool)

def test_stop_idempotent(self):
    """测试 stop() 幂等性"""
    self.module.start()
    result1 = self.module.stop()
    result2 = self.module.stop()  # 第二次调用
    self.assertTrue(result1)
    self.assertTrue(result2)

def test_stop_timeout(self):
    """测试 stop() 超时处理"""
    # 创建一个不会停止的模块
    module = SlowStoppingModule()
    module.start()
    result = module.stop(timeout=0.1)
    self.assertFalse(result)  # 应该返回 False
```

#### 步骤 4：验证

1. 运行单元测试确保通过
2. 运行集成测试确保与 SystemManager 正常工作
3. 手动测试各种场景（正常关闭、超时、异常等）

---

### 🔍 详细规范

完整的模块 `stop()` 方法规范请参考：
- **适配指南**: `docs/module_stop_method_guide.md`
- **需求文档**: `.kiro/specs/system-manager/requirements.md`（Requirement 17）
- **设计文档**: `.kiro/specs/system-manager/design.md`

---

### 📊 已适配模块

以下系统内置模块已完成适配：

| 模块名称 | 状态 | 合规性 |
|---------|------|--------|
| DisplayManager | ✅ 已完成 | 100% |
| CANCommunicator | ✅ 已完成 | 100% |
| OAKDataCollector | ✅ 已完成 | 100% |
| DataProcessor | ✅ 已完成 | 100% |

---

### ⚠️ 注意事项

#### 1. 强制退出的影响

当模块停止失败时，SystemManager 会调用 `os._exit(1)` 强制退出进程。这意味着：

- ✅ 确保系统一定能够退出（不会卡死）
- ⚠️ 可能导致未刷新的数据丢失
- ⚠️ 不会执行 `finally` 块或 `__del__` 方法

**缓解措施：**
- 确保模块 `stop()` 方法正确实现
- 使用足够长的宽限期（默认 3.0 秒）
- 在模块中实现正确的资源清理逻辑

#### 2. 超时时不清理引用

当模块 `stop()` 方法超时时，**不应该**清理引用（如 `self._thread = None`）。

**原因：**
- 保持状态一致性（`_is_running` 仍为 `True`）
- 避免误导性状态（线程还在运行但引用被清空）
- 方便 SystemManager 检测失败并触发兜底机制

**正确做法：**
```python
if self._thread.is_alive():
    logger.error(f"线程停止超时 ({timeout}s)")
    return False  # 不清理引用

# 只在成功时清理
self._is_running = False
self._thread = None
return True
```

#### 3. 日志刷新

强制退出前，SystemManager 会调用 `logging.shutdown()` 刷新日志缓冲区。但仍建议：

- 使用 `logging.FileHandler` 时设置较小的缓冲区
- 关键日志使用 `flush=True`
- 定期刷新日志文件

---

### 🎯 快速开始

#### 新项目

```python
from oak_vision_system.core.system_manager import SystemManager

# 创建 SystemManager（使用默认配置）
manager = SystemManager(system_config=config)

# 注册模块（确保模块 stop() 方法符合规范）
manager.register_module("collector", collector, priority=10)
manager.register_module("processor", processor, priority=30)
manager.register_module("display", display, priority=50)

# 启动和运行
manager.start_all()
manager.run()
```

#### 现有项目

```python
# 现有代码继续工作，无需修改
manager = SystemManager(system_config=config)
manager.register_module("collector", collector, priority=10)
manager.start_all()
manager.run()

# 可选：调整强制退出宽限期
manager = SystemManager(
    system_config=config,
    force_exit_grace_period=5.0  # 增加到 5 秒
)
```

---

### 📞 获取帮助

如有问题或疑虑，请查阅：
- **适配指南**: `docs/module_stop_method_guide.md`（详细规范和示例）
- **需求文档**: `.kiro/specs/system-manager/requirements.md`
- **设计文档**: `.kiro/specs/system-manager/design.md`
- **实现代码**: `oak_vision_system/core/system_manager/system_manager.py`

---

## 配置管理器重构

**更新日期**: 2025-09-30  
**版本**: v2.0.0

### 📌 重要变更

### 文件重命名
- **旧文件**: `device_manager.py`
- **新文件**: `config_manager.py`

### 类名重命名
- **旧类名**: `OAKDeviceManager`
- **新类名**: `SystemConfigManager`

---

## 🔄 为什么要重命名？

### 设计理念的转变

**旧设计** (OAKDeviceManager):
- 名称局限在"OAK设备"范畴
- 给人感觉只管理OAK设备
- 实际功能被名称限制

**新设计** (SystemConfigManager):
- 明确定位为系统配置中心
- 管理所有模块的配置（OAK、CAN、数据处理等）
- 专注于配置的流通和分发

### 职责范围

```
SystemConfigManager 管理：
├── OAK Pipeline 配置（模型、检测参数、相机设置）
├── 系统配置（CAN通信、串口、网络等）
├── 数据处理配置（滤波、转换等）
└── 设备状态配置（设备列表、连接状态）
```

---

## ✅ 向后兼容

**好消息**：现有代码无需修改！我们保持了完全的向后兼容。

### 兼容性保证

```python
# 旧代码仍然可以正常工作
from oak_vision_system.modules.data_collector import OAKDeviceManager
manager = OAKDeviceManager()  # 实际上是 SystemConfigManager 的别名
```

---

## 📝 迁移步骤

### 1. 新项目（推荐使用新名称）

```python
# 推荐写法
from oak_vision_system.modules.data_collector import SystemConfigManager

config_manager = SystemConfigManager("config/system_config.json")
```

### 2. 旧项目迁移（渐进式）

#### 选项 A：保持旧代码不变

```python
# 无需修改，继续使用旧名称
from oak_vision_system.modules.data_collector import OAKDeviceManager
manager = OAKDeviceManager()
```

#### 选项 B：使用别名逐步迁移

```python
# 第一步：使用别名
from oak_vision_system.modules.data_collector import SystemConfigManager as OAKDeviceManager
manager = OAKDeviceManager()  # 代码其他部分不变

# 第二步：逐步替换变量名
from oak_vision_system.modules.data_collector import SystemConfigManager
config_manager = SystemConfigManager()
```

#### 选项 C：一次性迁移

```python
# 批量替换
# OAKDeviceManager → SystemConfigManager
# device_manager → config_manager (可选)
```

---

## 🔍 导入语句对照表

| 旧写法 | 新写法 |
|--------|--------|
| `from modules.data_collector import OAKDeviceManager` | `from modules.data_collector import SystemConfigManager` |
| `from modules.data_collector.device_manager import OAKDeviceManager` | `from modules.data_collector.config_manager import SystemConfigManager` |

---

## 📚 使用示例对比

### 旧风格（仍然可用）

```python
from oak_vision_system.modules.data_collector import OAKDeviceManager

# 初始化
manager = OAKDeviceManager("config/device_config.json")

# 获取配置
oak_config = manager.get_oak_config()
system_config = manager.get_system_config()

# 保存配置
manager.save_config()
```

### 新风格（推荐）

```python
from oak_vision_system.modules.data_collector import SystemConfigManager

# 初始化配置中心
config_center = SystemConfigManager("config/system_config.json")

# OAK模块从配置中心获取配置
oak_config = config_center.get_oak_config()

# CAN模块从配置中心获取配置
can_config = config_center.get_system_config()

# 设备模块从配置中心获取设备列表
devices = config_center.list_devices()

# 统一保存所有模块的配置
config_center.save_config()
```

---

## 🎯 设计模式：配置中心

### 架构图

```
┌─────────────────────────────────────────┐
│      SystemConfigManager               │
│      (配置中心)                         │
├─────────────────────────────────────────┤
│  • 管理所有模块配置                      │
│  • 序列化/反序列化                       │
│  • 配置分发接口                         │
│  • 配置备份/恢复                         │
└─────────────────────────────────────────┘
            ↓  配置分发接口  ↓
    ┌────────┬────────┬────────┬────────┐
    │  OAK   │  CAN   │  数据  │  设备  │
    │  模块  │  模块  │  处理  │  管理  │
    └────────┴────────┴────────┴────────┘
```

### 优势

✅ **统一配置源**：所有模块从同一个配置中心获取配置  
✅ **自动持久化**：配置修改后统一保存到文件  
✅ **模块解耦**：各模块只需要知道配置接口  
✅ **配置同步**：所有模块的配置自动保持一致  
✅ **易于扩展**：添加新模块配置非常简单  

---

## 📖 示例代码

### 完整示例

查看 `examples/config_manager_usage.py` 了解详细用法：
- 配置中心模式演示
- 多模块协同配置管理
- 运行模式切换示例

### 向后兼容示例

查看 `examples/device_manager_example.py` 了解旧代码如何继续工作。

---

## ❓ 常见问题

### Q1: 我必须迁移到新名称吗？

**A**: 不必须。旧名称 `OAKDeviceManager` 将永久保留作为向后兼容别名。

### Q2: 配置文件需要修改吗？

**A**: 不需要。配置文件格式完全不变。

### Q3: 功能有变化吗？

**A**: 没有。所有功能保持不变，只是类名和文件名更准确地反映了其职责。

### Q4: 什么时候应该使用新名称？

**A**: 推荐在以下情况使用新名称：
- 新项目
- 大规模重构
- 需要向其他开发者清晰传达设计意图时

### Q5: 旧文件 device_manager.py 还存在吗？

**A**: 已重命名为 `config_manager.py`。所有导入已自动更新。

---

## 🚀 快速开始

### 新项目

```python
from oak_vision_system.modules.data_collector import SystemConfigManager

# 创建配置中心
config = SystemConfigManager()

# 各模块获取配置
oak_config = config.get_oak_config()
system_config = config.get_system_config()
devices = config.list_devices()
```

### 现有项目

```python
# 继续使用现有代码，无需任何修改
from oak_vision_system.modules.data_collector import OAKDeviceManager
manager = OAKDeviceManager()
```

---

## 📞 联系支持

如有问题或疑虑，请查阅：
- 示例代码：`examples/config_manager_usage.py`
- API文档：`config_manager.py` 中的详细文档字符串

---

**更新日期**: 2025-09-30  
**版本**: v2.0.0
