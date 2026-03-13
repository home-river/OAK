# OAK视觉抓取系统（视觉部分）

基于OAK（OpenCV AI Kit）相机的智能视觉检测系统

## 📋 项目简介

基于OAK的depthai库的检测识别，加上自定义坐标转换建模的识别+通信的系统，完成抓取前的识别定位功能。

### 核心特性

- 🎯 **多设备角色**：支持左/右相机等角色配置与设备绑定
- 🔄 **设备热插拔**：设备连接变化时可重新识别并更新绑定
- 🧭 **坐标处理**：支持坐标变换与滤波处理
- 📡 **事件总线**：模块间通过发布-订阅通信，降低耦合
- 🛠️ **配置管理**：支持 JSON/YAML 配置、模板与校验
- 🔧 **配置转换**：提供 JSON ↔ YAML 转换工具
- 🚦 **背压控制**：队列压力监控与采集频率调节
- 🎛️ **系统管理**：统一启动/停止流程与资源清理
- 🔌 **CAN 通信**：支持 CAN 总线消息收发（可对接机械臂）
- 🖥️ **显示**：提供实时画面与检测结果叠加显示

## 🏗️ 软件架构

```
系统管理器 (SystemManager)
    ├── 事件总线 (EventBus) - 模块间通信枢纽
    ├── 配置管理 (ConfigManager) - 设备发现/配置模板
    ├── 数据采集 (OAKDataCollector) - 多设备数据采集
    ├── 数据处理 (DataProcessor) - 坐标变换/滤波/跟踪
    ├── 显示模块 (DisplayManager) - 渲染和显示
    ├── CAN通信 (CANCommunicator) - 机械臂控制
    └── 背压控制 (BackpressureMonitor) - 系统负载管理
```

### 核心模块说明

- **配置模板系统** (`core.config.templates`): 提供预定义配置模板，简化系统配置
- **事件总线** (`core.event_bus`): 发布-订阅模式的消息传递，支持模块解耦
- **数据收集器** (`modules.data_collector`): 多设备OAK相机数据采集，支持背压控制
- **背压控制** (`core.backpressure`): 智能负载监控，自动调节数据流量
- **系统管理器** (`core.system_manager`): 统一的系统生命周期管理

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

### 依赖说明

**核心依赖**：
- `depthai==2.30.0.0` - OAK相机SDK
- `opencv-python==4.8.1.78` - 计算机视觉库
- `numpy==1.24.3` - 数值计算
- `scipy==1.11.4` - 科学计算
- `python-can==4.2.2` - CAN总线通信
- `structlog==23.2.0` - 结构化日志
- `asyncio-mqtt==0.16.1` - MQTT异步通信

**可选依赖**：
- `ruamel.yaml>=0.17.0` - YAML支持（推荐，保留注释）
- `pyyaml>=6.0` - YAML支持（基础版本）

**开发依赖**：
- `pytest==7.4.3` - 测试框架
- `hypothesis==6.92.0` - 属性测试
- `black==23.11.0` - 代码格式化
- `mypy==1.7.1` - 类型检查

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
    },
    "hardware_config": {
      "confidence_threshold": 0.5,
      "hardware_fps": 20,
      "enable_depth_output": true
    }
  },
  "system_config": {
    "log_level": "INFO",
    "auto_reconnect": true,
    "max_worker_threads": 4
  }
}
```

**YAML 格式**（需要安装 `[yaml]` 扩展）：

YAML 格式支持注释，便于配置文档化：

```yaml
# OAK Vision System 配置文件
# 版本: 2.0.0

config_version: "2.0.0"

# OAK模块配置
oak_module:
  # 设备角色绑定
  role_bindings:
    LEFT_CAMERA:
      role: LEFT_CAMERA
      active_mxid: "14442C10D13F7FD000"  # 左相机设备 ID
  
  # 硬件配置
  hardware_config:
    confidence_threshold: 0.5  # 检测置信度阈值
    hardware_fps: 20          # 硬件帧率
    enable_depth_output: true # 启用深度输出

# 系统配置
system_config:
  log_level: "INFO"           # 日志等级
  auto_reconnect: true        # 自动重连
  max_worker_threads: 4       # 最大工作线程数

# 背压控制配置
backpressure_config:
  enable_monitoring: true     # 启用背压监控
  cpu_threshold: 80.0        # CPU使用率阈值
  memory_threshold: 85.0     # 内存使用率阈值
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
from oak_vision_system.core.config.templates import template_DeviceManagerConfigDTO
from oak_vision_system.modules.data_collector.collector import OAKDataCollector
from oak_vision_system.core.event_bus import get_event_bus
from oak_vision_system.core.dto.config_dto import DeviceMetadataDTO

# 创建设备配置
devices = [
    DeviceMetadataDTO(mxid="14442C10D13D0D0000", notes="左侧相机"),
    DeviceMetadataDTO(mxid="14442C10D13D0D0001", notes="右侧相机")
]
config = template_DeviceManagerConfigDTO(devices)

# 启动数据采集
event_bus = get_event_bus()
collector = OAKDataCollector(config.oak_module, event_bus)
result = collector.start()

# 检查启动结果
if isinstance(result, dict):
    print(f"成功启动设备: {result['started']}")
    if result['skipped']:
        print(f"跳过设备: {result['skipped']}")
else:
    print("启动失败")
```

### 系统管理器使用

```python
from oak_vision_system.core.system_manager import SystemManager
from oak_vision_system.modules.config_manager import DeviceConfigManager

# 使用系统管理器统一管理
config_manager = DeviceConfigManager("config/device_config.json")
system_manager = SystemManager(config_manager)

# 启动完整系统
system_manager.start()

# 优雅关闭
system_manager.stop()
```

### 配置管理示例

```python
from oak_vision_system.modules.config_manager import DeviceConfigManager
from oak_vision_system.core.config.templates import template_DeviceManagerConfigDTO

# 使用配置模板快速创建配置
devices = [DeviceMetadataDTO(mxid="your_device_id", notes="主设备")]
config = template_DeviceManagerConfigDTO(devices)

# 或加载现有配置（自动识别 JSON/YAML 格式）
manager = DeviceConfigManager(config_path="config.yaml")
manager.load_config()

# 导出为不同格式
manager.export_to_yaml("config_backup.yaml")
manager.export_to_json("config_backup.json")
```

### 事件订阅示例

```python
from oak_vision_system.core.event_bus import get_event_bus, EventType

event_bus = get_event_bus()

# 订阅检测数据
def handle_detection(detection_data):
    print(f"检测到 {detection_data.detection_count} 个目标")

event_bus.subscribe(EventType.RAW_DETECTION_DATA, handle_detection)
```

## 🚀 高级功能

### 背压控制系统

系统内置智能背压控制，自动监控CPU和内存使用率，动态调整数据采集频率：

```python
from oak_vision_system.core.backpressure import BackpressureMonitor, BackpressureConfig

# 配置背压监控
config = BackpressureConfig(
    cpu_threshold=80.0,      # CPU使用率阈值
    memory_threshold=85.0,   # 内存使用率阈值
    check_interval=1.0       # 检查间隔（秒）
)

monitor = BackpressureMonitor(config, event_bus)
monitor.start()
```

### 配置模板系统

使用预定义模板快速创建配置：

```python
from oak_vision_system.core.config.templates import (
    template_DeviceManagerConfigDTO,
    template_SystemConfigDTO,
    template_OAKConfigDTO
)

# 创建系统配置模板
system_config = template_SystemConfigDTO()

# 创建OAK硬件配置模板
oak_config = template_OAKConfigDTO()

# 创建完整设备管理配置
devices = [DeviceMetadataDTO(mxid="device_id", notes="设备说明")]
full_config = template_DeviceManagerConfigDTO(devices)
```

### 多设备协同工作

```python
# 配置多个设备角色
devices = [
    DeviceMetadataDTO(mxid="device_left", notes="左侧相机"),
    DeviceMetadataDTO(mxid="device_right", notes="右侧相机"),
    DeviceMetadataDTO(mxid="device_center", notes="中央相机")
]

config = template_DeviceManagerConfigDTO(devices)
collector = OAKDataCollector(config.oak_module, event_bus, devices)

# 启动结果包含每个设备的状态
result = collector.start()
print(f"成功启动: {result['started']}")
print(f"跳过设备: {result['skipped']}")
```

## 📁 项目结构

```
OAK/
├── oak_vision_system/          # 核心系统代码
│   ├── core/                   # 核心基础设施
│   │   ├── config/             # 配置模板系统
│   │   ├── dto/                # 数据传输对象
│   │   ├── event_bus/          # 事件总线
│   │   ├── backpressure/       # 背压控制
│   │   └── system_manager/     # 系统管理器
│   ├── modules/                # 功能模块
│   │   ├── config_manager/     # 配置管理
│   │   ├── data_collector/     # 数据采集
│   │   ├── data_processing/    # 数据处理
│   │   ├── display_modules/    # 显示模块
│   │   └── can_communication/  # CAN通信
│   ├── utils/                  # 工具函数
│   └── tests/                  # 测试代码
├── tools/                      # 命令行工具
│   ├── config_tools/           # 配置工具
│   ├── binding_tools/          # 设备绑定工具
│   └── calibration_tools/      # 标定工具
└── plan/                       # 设计文档
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

# 详细输出模式
python tools/config_tools/discover_devices.py --verbose

# 输出为 JSON 格式
python tools/config_tools/discover_devices.py --json
```

### 交互式配置转换工具

```bash
# 启动交互式配置转换
python tools/config_tools/interactive_convert.py
```



## 🤝 参与贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

MIT License - 查看 [LICENSE](LICENSE) 文件了解详情
