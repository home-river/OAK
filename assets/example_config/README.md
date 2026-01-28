# 示例配置

此文件夹提供一个完整的配置示例，展示如何组织配置文件和模型文件。

## 文件结构

```
example_config/
├── config.json          # 配置文件
├── model.blob           # 模型文件（需要自己下载）
└── README.md            # 本说明文件
```

## 使用方式

### 1. 复制此文件夹作为模板

```bash
# 创建你自己的配置
cp -r assets/example_config assets/my_config
cd assets/my_config
```

### 2. 修改配置文件

编辑 `config.json`，根据你的需求调整参数：

```json
{
  "hardware_config": {
    "model_path": "assets/my_config/model.blob",
    "confidence_threshold": 0.5,
    "hardware_fps": 30,
    "enable_depth_output": true
  },
  "device_bindings": {
    "left_camera": "your_device_mxid_here",
    "right_camera": "another_device_mxid_here"
  },
  "system_config": {
    "enable_can_communication": false
  }
}
```

### 3. 添加模型文件

将你的 `.blob` 模型文件放在此目录，命名为 `model.blob`。

### 4. 在代码中使用

```python
from pathlib import Path
import json

# 加载配置
config_dir = Path("assets/my_config")
config_path = config_dir / "config.json"

with open(config_path) as f:
    config = json.load(f)

model_path = config_dir / "model.blob"
```

## 配置方案管理

你可以创建多个配置文件夹，用于不同的场景：

```
assets/
├── test_config/         # 测试配置
├── example_config/      # 示例配置
├── production_config/   # 生产环境配置
├── debug_config/        # 调试配置
└── ...
```

每个配置文件夹都是独立的，包含完整的配置和模型文件。

## 获取模型

参考 `assets/test_config/README.md` 中的模型获取方法。
