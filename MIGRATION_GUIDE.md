# 配置管理器重构迁移指南

## 📌 重要变更

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
