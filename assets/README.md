# Assets - 配置和资源管理

此目录用于存放项目的配置文件和资源文件（如模型文件）。

## 目录结构

```
assets/
├── test_config/         # 测试专用配置
│   ├── config.json     # 测试配置文件
│   ├── model.blob      # 测试模型文件
│   └── README.md       # 说明文档
├── example_config/      # 示例配置（作为模板）
│   ├── config.json     # 示例配置文件
│   ├── model.blob      # 示例模型文件
│   └── README.md       # 说明文档
└── README.md           # 本文件
```

## 设计理念

每个配置文件夹是一个**完整的配置方案**，包含：
- ✅ 配置文件 (`config.json`) - 系统参数、设备绑定等
- ✅ 模型文件 (`model.blob`) - 对应的检测模型
- ✅ 说明文档 (`README.md`) - 配置说明（可选）

这样的设计便于：
- 在不同配置方案间快速切换
- 分享完整的配置方案
- 版本管理和备份

## 快速开始

### 1. 创建你的配置

```bash
# 复制示例配置作为模板
cp -r assets/example_config assets/my_config
```

### 2. 修改配置文件

编辑 `assets/my_config/config.json`，根据你的需求调整参数。

### 3. 添加模型文件

将你的 `.blob` 模型文件放在 `assets/my_config/` 目录。

### 4. 在代码中使用

```python
from pathlib import Path
import json

# 加载配置
config_dir = Path("assets/my_config")
config_path = config_dir / "config.json"

with open(config_path) as f:
    config = json.load(f)
```

## 配置方案示例

你可以创建多个配置文件夹，用于不同的场景：

- `test_config/` - 测试环境配置
- `production_config/` - 生产环境配置
- `debug_config/` - 调试配置
- `demo_config/` - 演示配置
- `high_fps_config/` - 高帧率配置
- `low_power_config/` - 低功耗配置

## Git 管理

- ✅ 配置文件 (`*.json`) 会被提交到仓库
- ❌ 模型文件 (`*.blob`) 已在 `.gitignore` 中被忽略
- ✅ 说明文档 (`README.md`) 会被提交到仓库

每个开发者需要自己准备模型文件。

## 获取模型

参考 `assets/test_config/README.md` 中的详细说明。

推荐来源：
- [DepthAI Model Zoo](https://github.com/luxonis/depthai-model-zoo)
- 自己训练的模型

## 注意事项

1. **模型路径** - 配置文件中的 `model_path` 应该使用相对路径
2. **设备 MXid** - 需要根据实际连接的设备修改
3. **参数调优** - 根据实际场景调整置信度、帧率等参数
