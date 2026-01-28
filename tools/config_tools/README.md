# 工具集

此目录包含 OAK Vision System 的实用工具脚本。

## 可用工具

### 1. 配置生成工具 (`generate_config.py`)

**用途：** 在指定位置生成默认配置文件和目录结构

**使用方式：**

```bash
# 使用默认路径（assets/test_config）
python tools/generate_config.py

# 交互式模式（支持 Tab 补全，需要 prompt_toolkit）
python tools/generate_config.py --interactive

# 指定输出路径
python tools/generate_config.py --output assets/my_config

# 强制覆盖已存在的配置
python tools/generate_config.py --force
```

**生成的文件：**
- `config.json` - 配置文件
- `README.md` - 说明文档

**依赖：**
- `click` - 必需
- `prompt_toolkit` - 可选（用于 Tab 补全）

安装依赖：
```bash
pip install click
pip install prompt_toolkit  # 可选
```

---

### 2. 设备发现工具 (`discover_devices.py`)

**用途：** 发现连接的 OAK 设备并显示其 MXid

**使用方式：**

```bash
# 基本使用
python tools/discover_devices.py

# 显示详细信息
python tools/discover_devices.py --verbose
```

**输出示例：**
```
[1] 设备信息:
  MXid: 14442C10D13D0D0000
  产品名: OAK-D
  连接状态: connected
```

**依赖：**
- `click` - 必需
- `depthai` - 必需

---

## 快速开始

### 步骤 1: 生成配置

```bash
python tools/generate_config.py
```

### 步骤 2: 发现设备

```bash
python tools/discover_devices.py
```

### 步骤 3: 编辑配置

将步骤 2 中获取的 MXid 填入配置文件：

```json
{
  "device_bindings": {
    "left_camera": "14442C10D13D0D0000",
    "right_camera": "14442C10D13D0D0001"
  }
}
```

### 步骤 4: 添加模型文件

将你的 `.blob` 模型文件放到配置目录，命名为 `model.blob`。

---

## 常见问题

### Q: 如何安装依赖？

```bash
pip install click prompt_toolkit
```

### Q: 为什么交互式模式没有 Tab 补全？

需要安装 `prompt_toolkit`：
```bash
pip install prompt_toolkit
```

### Q: 设备发现工具找不到设备怎么办？

检查：
1. 设备是否已连接
2. USB 线缆是否正常
3. 驱动是否已安装
4. 是否有权限访问设备（Linux 可能需要 udev 规则）

### Q: 生成的配置在哪里？

默认在 `assets/test_config/`，可以通过 `--output` 参数指定其他位置。

---

## 开发者信息

如果你想添加新的工具，请遵循以下规范：

1. 使用 `click` 作为命令行框架
2. 提供清晰的帮助信息
3. 添加错误处理
4. 更新本 README 文档

示例模板：

```python
#!/usr/bin/env python3
"""工具说明"""

import click

@click.command()
@click.option('--option', help='选项说明')
def main(option):
    """工具功能描述"""
    pass

if __name__ == '__main__':
    main()
```
