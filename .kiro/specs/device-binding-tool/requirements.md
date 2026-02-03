# 设备绑定工具需求文档

## 概述

设备绑定工具（Device Binding Tool）是一个终端交互式工具，用于帮助用户将物理 OAK 设备绑定到配置文件中的设备角色。该工具简化了设备配置流程，使用户能够快速完成设备角色分配。

## 目标用户

- 系统集成人员
- 现场部署人员
- 开发测试人员

## 核心功能

### 1. 配置文件夹选择

**功能描述：**
从 `assets/` 目录中扫描并列出所有包含配置文件的子文件夹，让用户选择要使用的配置。

**用户交互流程：**
```
📂 发现以下配置文件夹：
1. assets/example_config/
2. assets/test_config/
3. assets/production_config/

请选择配置文件夹 (输入序号): _
```

**技术要求：**
- 扫描 `assets/` 目录下的所有子文件夹
- 检查每个子文件夹是否包含 `config.json` 或 `config.yaml`
- 显示文件夹列表供用户选择
- 支持输入序号或文件夹名称
- 验证用户输入的有效性

---

### 2. 配置文件加载

**功能描述：**
加载用户选择的配置文件夹中的配置文件（优先 JSON，其次 YAML）。

**用户交互流程：**
```
✅ 已选择配置文件夹: assets/test_config/
📄 正在加载配置文件: assets/test_config/config.json
✅ 配置加载成功

📋 当前配置包含以下设备角色：
  - LEFT (左侧设备)
  - RIGHT (右侧设备)
  - MAIN (主设备)
```

**技术要求：**
- 使用 `DeviceConfigManager` 加载配置
- 优先加载 `config.json`，如果不存在则加载 `config.yaml`
- 显示配置中已定义的设备角色
- 处理配置加载失败的情况（文件损坏、格式错误等）
- **不创建新配置**，只加载现有配置

---

### 3. 设备发现

**功能描述：**
自动发现当前连接的所有 OAK 设备，并显示设备信息。

**用户交互流程：**
```
🔍 正在扫描 OAK 设备...

✅ 发现 3 个设备：
1. 设备 A
   MX ID: 14442C10D13EAFD700
   类型: OAK-D
   产品名称: OAK-D
   连接状态: 已连接

2. 设备 B
   MX ID: 14442C10D13EAFD701
   类型: OAK-D-Lite
   产品名称: OAK-D-Lite
   连接状态: 已连接

3. 设备 C
   MX ID: 14442C10D13EAFD702
   类型: OAK-D
   产品名称: OAK-D
   连接状态: 已连接
```

**技术要求：**
- 使用 `OAKDeviceDiscovery.get_all_available_devices()` 发现设备
- 提取并显示设备元数据（MX ID、类型、产品名称、连接状态）
- 处理无设备连接的情况
- 处理设备发现失败的情况

---

### 4. 交互式设备绑定

**功能描述：**
让用户为每个发现的设备分配角色，支持自定义绑定顺序。

**用户交互流程：**
```
🔗 开始设备绑定流程

配置中需要绑定的角色：
  - LEFT (左侧设备)
  - RIGHT (右侧设备)
  - MAIN (主设备)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

为角色 LEFT 选择设备：

可用设备：
1. 设备 A (14442C10D13EAFD700) - OAK-D
2. 设备 B (14442C10D13EAFD701) - OAK-D-Lite
3. 设备 C (14442C10D13EAFD702) - OAK-D
s. 跳过此角色

请选择设备 (输入序号或 's' 跳过): 1

✅ 已将设备 A (14442C10D13EAFD700) 绑定到角色 LEFT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

为角色 RIGHT 选择设备：

可用设备：
1. 设备 B (14442C10D13EAFD701) - OAK-D-Lite
2. 设备 C (14442C10D13EAFD702) - OAK-D
s. 跳过此角色

请选择设备 (输入序号或 's' 跳过): 1

✅ 已将设备 B (14442C10D13EAFD701) 绑定到角色 RIGHT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

绑定完成！

📋 绑定摘要：
  ✅ LEFT   → 设备 A (14442C10D13EAFD700)
  ✅ RIGHT  → 设备 B (14442C10D13EAFD701)
  ⏭️  MAIN   → 未绑定（已跳过）
```

**技术要求：**
- 遍历配置中定义的所有设备角色
- 对每个角色，显示可用设备列表（排除已绑定的设备）
- 支持用户选择设备或跳过
- 更新配置中的设备绑定信息
- 更新 `last_active_mxid` 和 `historical_mxids`
- 显示绑定摘要

**绑定规则：**
- 每个设备只能绑定到一个角色
- 已绑定的设备不再出现在后续选择列表中
- 支持跳过某些角色（不绑定设备）
- 按配置中定义的角色顺序进行绑定

---

### 5. 配置验证

**功能描述：**
在绑定完成后，对更新后的配置进行静态验证，确保配置的完整性和有效性。

**用户交互流程：**
```
🔍 正在验证配置...

✅ 配置验证通过
  - 设备绑定信息完整
  - 设备角色定义有效
  - 配置结构正确
```

或者验证失败时：
```
🔍 正在验证配置...

❌ 配置验证失败：
  - 错误：设备 LEFT 的 MX ID 格式无效
  - 警告：设备 MAIN 未绑定

是否仍要保存配置？(y/n): _
```

**技术要求：**
- 使用 `DeviceConfigManager.validate_config(include_runtime_checks=False)` 进行静态验证
- 显示验证结果（成功/失败）
- 如果验证失败，显示错误和警告信息
- 如果验证失败，询问用户是否仍要保存配置

---

### 6. 配置保存

**功能描述：**
将更新后的配置保存回原配置文件。

**用户交互流程：**
```
💾 正在保存配置...

✅ 配置已保存到: assets/test_config/config.json

📋 保存摘要：
  - 已更新 2 个设备绑定
  - 配置文件格式: JSON
  - 保存时间: 2026-02-03 15:30:45
```

**技术要求：**
- 使用 `DeviceConfigManager.save_config(validate=True)` 保存配置
- 保存到原配置文件路径
- 显示保存结果
- 处理保存失败的情况（权限不足、磁盘空间不足等）

---

### 7. 错误处理和用户体验

**功能描述：**
提供友好的错误处理和用户体验。

**技术要求：**

#### 7.1 输入验证
- 验证用户输入的有效性（序号范围、命令格式等）
- 提供清晰的错误提示
- 允许用户重新输入

#### 7.2 异常处理
- 捕获并处理所有可能的异常
- 显示友好的错误消息
- 提供恢复或退出选项

#### 7.3 用户确认
- 在关键操作前请求用户确认（如保存配置）
- 支持用户取消操作

#### 7.4 进度提示
- 显示操作进度（如"正在扫描设备..."）
- 使用表情符号和颜色增强可读性

#### 7.5 帮助信息
- 在每个步骤提供简短的帮助信息
- 支持 `--help` 参数显示完整帮助

---

## 命令行参数

工具应支持以下命令行参数：

```bash
python device_binding_tool.py [OPTIONS]
```

### 参数列表

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--config-dir` | `-d` | 配置根目录路径 | `assets` |
| `--config-folder` | `-f` | 直接指定配置文件夹名称（跳过选择步骤） | 无 |
| `--auto-bind` | `-a` | 自动绑定模式（按顺序自动分配） | `False` |
| `--show-devices` | `-s` | 仅显示发现的设备，不进行绑定 | `False` |
| `--validate-only` | `-v` | 仅验证现有配置，不进行绑定 | `False` |
| `--help` | `-h` | 显示帮助信息 | - |

### 使用示例

```bash
# 交互式绑定（默认）
python device_binding_tool.py

# 指定配置目录
python device_binding_tool.py --config-dir /path/to/configs

# 直接使用指定配置文件夹
python device_binding_tool.py --config-folder test_config

# 仅显示设备
python device_binding_tool.py --show-devices

# 仅验证配置
python device_binding_tool.py --config-folder test_config --validate-only
```

---

## 技术架构

### 依赖模块

```python
# 核心依赖
from oak_vision_system.modules.config_manager.device_config_manager import DeviceConfigManager
from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
from oak_vision_system.core.dto.config_dto import (
    DeviceMetadataDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
)

# 标准库
from pathlib import Path
from typing import List, Optional, Dict
import sys
import argparse
```

### 类结构

```python
class DeviceBindingTool:
    """设备绑定工具主类"""
    
    def __init__(self, config_dir: str = "assets"):
        """初始化工具"""
        
    def run(self) -> bool:
        """运行完整的绑定流程"""
        
    def select_config_folder(self) -> Optional[Path]:
        """选择配置文件夹"""
        
    def load_config(self, config_path: Path) -> bool:
        """加载配置文件"""
        
    def discover_devices(self) -> List[DeviceMetadataDTO]:
        """发现设备"""
        
    def interactive_bind_devices(
        self,
        devices: List[DeviceMetadataDTO]
    ) -> bool:
        """交互式绑定设备"""
        
    def validate_config(self) -> bool:
        """验证配置"""
        
    def save_config(self) -> bool:
        """保存配置"""
```

---

## 数据流

```
┌─────────────────────┐
│  1. 选择配置文件夹   │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  2. 加载配置文件     │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  3. 发现设备         │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  4. 交互式绑定       │
│     - 遍历角色       │
│     - 选择设备       │
│     - 更新配置       │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  5. 验证配置         │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  6. 保存配置         │
└─────────────────────┘
```

---

## 非功能性需求

### 性能要求
- 设备发现应在 5 秒内完成
- 配置加载应在 1 秒内完成
- 配置保存应在 1 秒内完成

### 可用性要求
- 提供清晰的用户提示和错误消息
- 支持中文和英文界面（可选）
- 使用表情符号和颜色增强可读性

### 可靠性要求
- 处理所有可能的异常情况
- 在保存前备份原配置文件（可选）
- 提供配置回滚功能（可选）

### 可维护性要求
- 代码结构清晰，易于理解
- 充分的注释和文档
- 遵循项目代码规范

---

## 测试要求

### 单元测试
- 配置文件夹扫描功能
- 配置加载功能
- 设备发现功能
- 配置验证功能
- 配置保存功能

### 集成测试
- 完整的绑定流程
- 错误处理流程
- 用户取消流程

### 手动测试场景
1. 正常绑定流程（所有角色都绑定）
2. 部分绑定流程（跳过某些角色）
3. 无设备连接场景
4. 配置文件损坏场景
5. 用户中断场景（Ctrl+C）

---

## 实现优先级

### P0（必须实现）
- ✅ 配置文件夹选择
- ✅ 配置文件加载
- ✅ 设备发现
- ✅ 交互式设备绑定
- ✅ 配置验证
- ✅ 配置保存

### P1（应该实现）
- ⚠️ 命令行参数支持
- ⚠️ 错误处理和用户体验优化
- ⚠️ 帮助信息

### P2（可以实现）
- ⏸️ 自动绑定模式
- ⏸️ 配置备份功能
- ⏸️ 配置回滚功能
- ⏸️ 多语言支持

---

## 限制和约束

### 技术限制
- 依赖 `DeviceConfigManager` 的现有 API
- 不支持 RGB 预览功能（需要单独实现）
- 仅支持 JSON 和 YAML 配置格式

### 使用限制
- 需要 OAK 设备物理连接
- 需要配置文件已存在（不创建新配置）
- 需要配置文件可写权限

---

## 未来扩展

### 可能的功能扩展
1. **RGB 预览功能** - 在绑定前预览设备图像
2. **设备测试功能** - 测试设备是否正常工作
3. **批量绑定功能** - 一次性绑定多个配置
4. **配置模板功能** - 从模板创建新配置
5. **Web 界面** - 提供 Web 界面进行绑定

---

## 参考文档

- `oak_vision_system/modules/config_manager/device_config_manager.py` - 配置管理器实现
- `oak_vision_system/modules/config_manager/device_discovery.py` - 设备发现实现
- `oak_vision_system/core/dto/config_dto/` - 配置 DTO 定义
- `MIGRATION_GUIDE.md` - 配置管理器迁移指南

---

## 版本历史

| 版本 | 日期 | 作者 | 说明 |
|------|------|------|------|
| 1.0 | 2026-02-03 | - | 初始版本 |

