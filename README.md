# OAK视觉抓取系统

基于OAK（OpenCV AI Kit）相机的智能视觉检测与机械臂抓取控制系统。

## 📋 项目简介

面向生产环境的模块化视觉抓取系统，通过OAK深度相机实现实时目标检测、空间坐标定位和机械臂抓取控制。采用事件驱动架构，支持多设备并行处理、设备热插拔和配置热更新。

### 核心特性

- 🎯 **多设备支持**：支持左相机、右相机等多设备角色，自动识别和绑定物理设备
- 🔄 **设备角色绑定**：采用"角色-设备"分离设计，支持设备热插拔和自动识别
- ⚡ **高性能处理**：基于NumPy的批量矩阵运算，支持实时坐标变换和滤波处理
- 📡 **事件驱动架构**：基于发布-订阅模式的事件总线，实现模块间解耦通信
- 🛠️ **灵活配置管理**：支持 JSON 和 YAML 配置格式，提供配置验证和运行时检查
- 🔧 **配置格式转换**：内置配置格式转换工具，支持 JSON ↔ YAML 双向转换

## 🏗️ 软件架构

```
事件总线 (EventBus)
    ├── 数据采集模块 (Collector) - OAK设备数据采集
    ├── 数据处理模块 (Transform) - 坐标变换/滤波
    └── 配置管理模块 (Config Manager) - 设备发现/绑定
```

## 🚀 快速开始

### 环境要求

- Python >= 3.10
- OAK相机设备（支持DepthAI）

### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd OAK

# 基础安装（不包含 YAML 支持）
pip install -r requirements.txt

# 或使用 pip 安装（推荐）
pip install -e .

# 如需 YAML 配置文件支持，请安装 yaml 扩展
# 推荐：安装 ruamel.yaml（支持注释保持和格式保持）
pip install -e .[yaml]

# 或：仅安装 PyYAML（基础 YAML 支持，不保留注释）
pip install -e .[yaml-basic]

# 开发环境安装（包含测试工具）
pip install -e .[dev]

# 完整安装（包含所有可选依赖）
pip install -e .[yaml,dev]
```

### 配置文件格式

系统支持 JSON 和 YAML 两种配置文件格式：

**JSON 格式**（默认支持，无需额外依赖）：
```json
{
  "config_version": "2.0.0",
  "oak_module": {
    "role_bindings": {
      "LEFT_CAMERA": {
        "role": "LEFT_CAMERA",
        "active_mxid": "14442C10D13F7FD000"
      }
    }
  }
}
```

**YAML 格式**（需要安装 `[yaml]` 扩展）：

YAML 格式支持注释，便于配置文档化：

```yaml
# OAK Vision System 配置文件
# 版本: 2.0.0

config_version: "2.0.0"

oak_module:
  role_bindings:
    LEFT_CAMERA:
      role: LEFT_CAMERA
      active_mxid: "14442C10D13F7FD000"  # 左相机设备 ID
```

**注释保持功能**：
- 安装 `ruamel.yaml`（推荐）：`pip install -e .[yaml]`
  - ✅ 支持注释保持：加载和保存 YAML 时保留用户添加的注释
  - ✅ 支持格式保持：保持原有缩进、引号风格
  - ✅ 完美支持中文注释
- 安装 `PyYAML`（基础）：`pip install -e .[yaml-basic]`
  - ⚠️ 不保留注释：加载和保存时会丢失注释
  - ✅ 基础 YAML 功能正常

**格式转换工具**：
```bash
# JSON 转 YAML
python tools/config_tools/convert_config.py config.json --format yaml

# YAML 转 JSON
python tools/config_tools/convert_config.py config.yaml --format json

# 转换后验证配置
python tools/config_tools/convert_config.py config.json --format yaml --validate
```

**生成配置文件**：
```bash
# 生成 JSON 配置（默认）
python tools/config_tools/generate_config.py --output config.json

# 生成 YAML 配置
python tools/config_tools/generate_config.py --output config.yaml --format yaml
```

### 基本使用

```python
from oak_vision_system.modules.config_manager import DeviceConfigManager
from oak_vision_system.modules.data_collector import OAKDataCollector
from oak_vision_system.core.event_bus import get_event_bus

# 初始化配置管理器（支持 JSON 和 YAML 格式）
config_manager = DeviceConfigManager(config_path="config/device_config.json", auto_create=True)
# 或使用 YAML 配置
# config_manager = DeviceConfigManager(config_path="config/device_config.yaml", auto_create=True)

# 启动数据采集
event_bus = get_event_bus()
oak_config = config_manager.get_oak_module_config()
collector = OAKDataCollector(oak_config, event_bus)
collector.start()
```

### 配置管理示例

```python
from oak_vision_system.modules.config_manager import DeviceConfigManager

# 加载配置（自动识别 JSON/YAML 格式）
manager = DeviceConfigManager(config_path="config.yaml")
manager.load_config()

# 导出为不同格式
manager.export_to_yaml("config_backup.yaml")
manager.export_to_json("config_backup.json")
```

## 📁 项目结构

```
OAK/
├── oak_vision_system/     # 核心系统代码
│   ├── core/              # 事件总线、DTO、背压控制
│   ├── modules/           # 数据采集、处理、配置管理
│   └── utils/            # 工具函数
├── examples/              # 示例代码
├── plan/                  # 设计文档
└── tests/                 # 测试代码
```

## 📚 文档

- [模块接口计划文档](plan/模块接口计划文档.md)
- [配置DTO说明](plan/dto/配置DTO说明.md)
- [配置格式转换器设计](.kiro/specs/config-format-converter/design.md)
- [开发日志](plan/每日记录.md)

## 🔧 命令行工具

### 配置格式转换工具

```bash
# 查看帮助
python tools/config_tools/convert_config.py --help

# JSON 转 YAML
python tools/config_tools/convert_config.py config.json --format yaml

# YAML 转 JSON（带验证）
python tools/config_tools/convert_config.py config.yaml --format json --validate

# 指定输出路径
python tools/config_tools/convert_config.py config.json --format yaml --output new_config.yaml

# 强制覆盖已存在的文件
python tools/config_tools/convert_config.py config.json --format yaml --force
```

### 配置生成工具

```bash
# 生成 JSON 配置
python tools/config_tools/generate_config.py --output config.json

# 生成 YAML 配置
python tools/config_tools/generate_config.py --output config.yaml --format yaml

# 交互式生成配置
python tools/config_tools/generate_config.py --interactive
```

### 设备发现工具

```bash
# 发现连接的 OAK 设备
python tools/config_tools/discover_devices.py
```

## 🤝 参与贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

MIT License - 查看 [LICENSE](LICENSE) 文件了解详情
