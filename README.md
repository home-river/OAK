# OAK视觉抓取系统

基于OAK（OpenCV AI Kit）相机的智能视觉检测与机械臂抓取控制系统。

## 📋 项目简介

面向生产环境的模块化视觉抓取系统，通过OAK深度相机实现实时目标检测、空间坐标定位和机械臂抓取控制。采用事件驱动架构，支持多设备并行处理、设备热插拔和配置热更新。

### 核心特性

- 🎯 **多设备支持**：支持左相机、右相机等多设备角色，自动识别和绑定物理设备
- 🔄 **设备角色绑定**：采用"角色-设备"分离设计，支持设备热插拔和自动识别
- ⚡ **高性能处理**：基于NumPy的批量矩阵运算，支持实时坐标变换和滤波处理
- 📡 **事件驱动架构**：基于发布-订阅模式的事件总线，实现模块间解耦通信
- 🛠️ **灵活配置管理**：支持JSON配置持久化，提供配置验证和运行时检查

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

# 安装依赖
pip install -r requirements.txt
```

### 基本使用

```python
from oak_vision_system.modules.config_manager import DeviceConfigManager
from oak_vision_system.modules.data_collector import OAKDataCollector
from oak_vision_system.core.event_bus import get_event_bus

# 初始化配置管理器
config_manager = DeviceConfigManager(config_path="config/device_config.json", auto_create=True)

# 启动数据采集
event_bus = get_event_bus()
oak_config = config_manager.get_oak_module_config()
collector = OAKDataCollector(oak_config, event_bus)
collector.start()
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
- [开发日志](plan/每日记录.md)

## 🤝 参与贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

MIT License - 查看 [LICENSE](LICENSE) 文件了解详情
