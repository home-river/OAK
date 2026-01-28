#!/usr/bin/env python3
"""
配置生成工具

用途：在指定位置生成默认配置文件和目录结构

使用方式：
1. 使用默认路径：python tools/generate_config.py
2. 交互式指定路径：python tools/generate_config.py --interactive
3. 命令行指定路径：python tools/generate_config.py --output assets/my_config

作者：OAK Vision System
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import click
except ImportError:
    print("错误: 需要安装 click 库")
    print("请运行: pip install click")
    sys.exit(1)

try:
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import PathCompleter
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

try:
    from oak_vision_system.modules.config_manager.device_config_manager import DeviceConfigManager
    from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
except ImportError as e:
    print(f"错误: 无法导入配置管理模块: {e}")
    print("请确保项目已正确安装")
    sys.exit(1)


def generate_config_files(output_path: Path, discover_devices: bool = True, format: str = 'json') -> None:
    """生成配置文件和目录结构
    
    Args:
        output_path: 输出目录路径
        discover_devices: 是否自动发现设备（默认 True）
        format: 配置文件格式（'json' 或 'yaml'，默认 'json'）
    """
    # 创建目录
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 使用 ConfigManager 生成完整配置模板
    click.echo("  正在生成配置模板...")
    
    try:
        manager = DeviceConfigManager()
        
        # 可选：发现设备
        devices = None
        if discover_devices:
            click.echo("  正在扫描设备...")
            devices = OAKDeviceDiscovery.discover_devices()
            if devices:
                click.echo(f"  [成功] 发现 {len(devices)} 个设备")
            else:
                click.echo("  [警告] 未发现设备，将生成空配置模板")
        
        # 导出配置模板（允许未绑定）
        config_dto = manager.export_template_config(devices=devices, allow_unbound=True)
        
        # 根据格式保存配置
        if format == 'yaml':
            config_file = output_path / "config.yaml"
            # 转换为字典并保存为 YAML
            from oak_vision_system.modules.config_manager import ConfigConverter
            config_dict = config_dto.to_dict()
            ConfigConverter.save_as_yaml(config_dict, config_file)
            click.echo(f"  [成功] 已生成: {config_file} (YAML 格式)")
        else:
            config_file = output_path / "config.json"
            # 转换为 JSON 并保存（不包含元数据）
            config_json = config_dto.to_json(indent=2, include_metadata=False)
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(config_json)
            click.echo(f"  [成功] 已生成: {config_file} (JSON 格式)")
        
    except ImportError as e:
        if 'yaml' in str(e).lower() and format == 'yaml':
            click.echo(f"  [错误] 生成 YAML 配置需要安装 PyYAML", err=True)
            click.echo(f"  提示: 运行 'pip install pyyaml' 安装依赖", err=True)
            raise
        else:
            click.echo(f"  [错误] 生成配置失败: {e}", err=True)
            raise
    except Exception as e:
        click.echo(f"  [错误] 生成配置失败: {e}", err=True)
        raise
    
    # 生成 README.md
    readme_file = output_path / "README.md"
    
    # 根据格式添加特定说明
    yaml_section = ""
    if format == 'yaml':
        yaml_section = """

## YAML 配置注释说明

YAML 格式支持添加注释，便于配置说明和文档化。

### 添加注释的方法

1. **行内注释**：在配置项后添加 `#` 和注释内容
   ```yaml
   confidence_threshold: 0.5  # 检测置信度阈值（0.0-1.0）
   ```

2. **独立行注释**：在配置项前添加注释行
   ```yaml
   # 这是硬件配置部分
   hardware_config:
     model_path: "models/test.blob"
   ```

3. **多行注释**：使用多个 `#` 行
   ```yaml
   # ========== 坐标变换配置 ==========
   # 用于多相机系统的坐标系对齐
   # 参数单位：平移（毫米）、旋转（度）
   coordinate_transforms:
     left_camera:
       translation_x: -50.0  # 左相机向左偏移
   ```

### 注释示例

```yaml
# OAK Vision System 配置文件
# 版本: 2.0.0
# 最后修改: 2026-01-27

config_version: "2.0.0"

# ========== OAK 模块配置 ==========
oak_module:
  # 角色绑定：定义设备角色与实际设备的映射
  role_bindings:
    LEFT_CAMERA:
      role: LEFT_CAMERA
      active_mxid: "14442C10D13F7FD000"  # 设备唯一标识符
  
  # 硬件配置
  hardware_config:
    model_path: "models/mobilenet.blob"  # 模型文件路径
    confidence_threshold: 0.5  # 置信度阈值（0.0-1.0）
    hardware_fps: 30  # 硬件帧率

# ========== 数据处理配置 ==========
data_processing_config:
  # 坐标变换参数
  coordinate_transforms:
    left_camera:
      translation_x: -50.0  # 平移 X（单位：毫米）
      translation_y: 0.0    # 平移 Y（单位：毫米）
      translation_z: 0.0    # 平移 Z（单位：毫米）
      roll: 0.0   # 滚转角（单位：度）
      pitch: 0.0  # 俯仰角（单位：度）
      yaw: 0.0    # 偏航角（单位：度）
      calibration_date: null  # 校准日期（格式：YYYY-MM-DD HH:MM）
      calibration_method: null  # 校准方法：manual（手动）或 auto（自动）
```

### 注释最佳实践

1. **为关键参数添加注释**：说明参数的含义、单位和可选值
2. **使用分组注释**：用分隔线和标题组织配置结构
3. **保持注释简洁**：避免过长的注释影响可读性
4. **使用中文注释**：YAML 完全支持中文，便于团队协作
5. **注释会被保留**：使用 ruamel.yaml 库时，手动添加的注释会在保存时保留

### 注意事项

- 注释仅在 YAML 格式中有效，JSON 格式不支持注释
- 程序修改配置时会尽量保留用户添加的注释
- 建议在配置文件顶部添加版本和修改日期注释
"""
    
    config_file_name = f"config.{format}"
    readme_content = f"""# 配置方案

此配置方案由工具自动生成。

## 文件说明

- `{config_file_name}` - 系统完整配置文件
- `README.md` - 本说明文件
{yaml_section}

## 配置文件结构

配置文件包含以下部分：

### 1. 配置版本 (config_version)
- 当前版本: 2.0.0

### 2. OAK 模块配置 (oak_module)

#### 2.1 角色绑定 (role_bindings)
定义设备角色（如 LEFT_CAMERA, RIGHT_CAMERA）与实际设备的绑定关系。

运行设备发现工具获取 MXid：
```bash
python tools/discover_devices.py
```

#### 2.2 硬件配置 (hardware_config)
- `model_path`: 模型文件路径
- `confidence_threshold`: 检测置信度阈值 (0.0-1.0)
- `hardware_fps`: 硬件帧率
- `enable_depth_output`: 是否启用深度输出
- `rgb_resolution`: RGB 分辨率
- `preview_resolution`: 预览分辨率
- 更多参数请参考配置文件

#### 2.3 设备元数据 (device_metadata)
存储每个设备的详细信息（MXid、产品名、校准信息等）

### 3. 数据处理配置 (data_processing_config)

#### 3.1 坐标变换 (coordinate_transforms)
为每个设备角色配置坐标变换参数：
- `translation_x/y/z`: 平移参数（毫米）
- `roll/pitch/yaw`: 旋转参数（度）
- `calibration_date`: 校准日期
- `calibration_method`: 校准方法

#### 3.2 滤波配置 (filter_config)
- `filter_type`: 滤波器类型（MOVING_AVERAGE 等）
- `moving_average_config`: 滑动平均滤波器配置
  - `window_size`: 窗口大小

#### 3.3 其他参数
- `enable_data_logging`: 是否启用数据日志
- `processing_thread_priority`: 处理线程优先级
- `person_timeout_seconds`: 人员跟踪超时时间

### 4. CAN 通信配置 (can_config)
- `enable_can`: 是否启用 CAN 通信
- `can_interface`: CAN 接口类型
- `can_channel`: CAN 通道
- `can_bitrate`: CAN 波特率
- `frame_ids`: 帧 ID 配置

### 5. 显示配置 (display_config)
- `enable_display`: 是否启用显示
- `window_width/height`: 窗口尺寸
- `target_fps`: 目标帧率
- `show_detection_boxes`: 显示检测框
- `show_labels`: 显示标签
- `show_confidence`: 显示置信度
- 更多显示参数请参考配置文件

### 6. 系统配置 (system_config)

#### 6.1 日志配置
- `log_level`: 日志等级（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- `log_to_file`: 是否写入日志文件
- `log_file_path`: 日志文件路径
- `log_max_size_mb`: 单个日志文件最大大小
- `log_backup_count`: 日志文件备份数量

#### 6.2 性能配置
- `enable_profiling`: 启用性能分析
- `max_worker_threads`: 最大工作线程数

#### 6.3 系统行为
- `auto_reconnect`: 设备断开后自动重连
- `reconnect_interval`: 重连间隔（秒）
- `max_reconnect_attempts`: 最大重连次数
- `graceful_shutdown_timeout`: 优雅关闭超时（秒）

## 获取模型文件

### 方法 1: 使用 DepthAI Model Zoo

从 DepthAI Model Zoo 下载预训练模型：
- 仓库地址: https://github.com/luxonis/depthai-model-zoo
- 推荐模型: MobileNet-SSD（轻量级）

### 方法 2: 使用自己的模型

如果你有自己训练的模型，直接放在此目录或指定路径。

## 使用配置

### 方法 1: 通过 ConfigManager 加载

```python
from oak_vision_system.modules.config_manager import DeviceConfigManager

manager = DeviceConfigManager(config_path="{output_path.name}/{config_file_name}")
manager.load_config()
config = manager.get_runnable_config()
```

### 方法 2: 直接读取文件

```python
{"import json" if format == 'json' else "import yaml"}
from pathlib import Path

config_path = Path("{output_path.name}") / "{config_file_name}"
with open(config_path) as f:
    config = {"json.load(f)" if format == 'json' else "yaml.safe_load(f)"}
```

## 修改配置

直接编辑 `{config_file_name}` 文件，根据你的需求调整参数。

**注意事项：**
1. 修改后建议通过 ConfigManager 验证配置有效性
2. 某些参数修改后需要重启系统
3. 坐标变换参数需要通过校准工具获取
{"4. YAML 格式支持添加注释，便于配置说明" if format == 'yaml' else ""}

## 下一步

1. **绑定设备**
   ```bash
   python tools/config_tools/discover_devices.py
   ```
   将获取的 MXid 填入 `oak_module.role_bindings` 中

2. **添加模型文件**
   将模型文件路径配置到 `oak_module.hardware_config.model_path`

3. **调整参数**
   根据实际场景调整各模块参数

4. **验证配置**
   ```python
   from oak_vision_system.modules.config_manager import DeviceConfigManager
   manager = DeviceConfigManager(config_path="{config_file_name}")
   manager.load_config()
   is_valid, errors = manager.validate_config()
   ```

## 格式转换

如需在 JSON 和 YAML 格式之间转换：

```bash
# JSON 转 YAML
python tools/config_tools/convert_config.py {config_file_name} --format {"yaml" if format == 'json' else "json"}

# 转换后验证
python tools/config_tools/convert_config.py {config_file_name} --format {"yaml" if format == 'json' else "json"} --validate
```

## 参考资料

- [项目文档](../../docs/)
- [配置架构说明](../../docs/config_architecture_refactoring.md)
- [DepthAI 文档](https://docs.luxonis.com/)
"""
    
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    click.echo(f"  [成功] 已生成: {readme_file}")


@click.command()
@click.option(
    '--output', '-o',
    default='assets/test_config',
    help='输出路径（默认: assets/test_config）'
)
@click.option(
    '--interactive', '-i',
    is_flag=True,
    help='交互式模式（支持 Tab 补全修改路径）'
)
@click.option(
    '--force', '-f',
    is_flag=True,
    help='强制覆盖已存在的配置'
)
@click.option(
    '--no-discover', '-n',
    is_flag=True,
    help='不自动发现设备（生成空配置模板）'
)
@click.option(
    '--format',
    type=click.Choice(['json', 'yaml']),
    default='json',
    help='配置文件格式（默认: json）'
)
def main(output, interactive, force, no_discover, format):
    """生成默认配置文件
    
    此工具会在指定位置生成：
    - config.json 或 config.yaml: 完整的系统配置文件
    - README.md: 配置说明文档
    
    配置文件包含所有模块的完整参数，包括：
    - OAK 模块配置（硬件参数、设备绑定）
    - 数据处理配置（坐标变换、滤波器）
    - CAN 通信配置
    - 显示配置
    - 系统配置（日志、性能等）
    
    默认会自动发现连接的设备，使用 --no-discover 跳过设备发现。
    默认生成 JSON 格式，使用 --format yaml 生成 YAML 格式。
    """
    click.echo("=" * 60)
    click.echo("OAK Vision System - 配置生成工具")
    click.echo("=" * 60)
    
    # 交互式模式：允许用户修改路径
    if interactive:
        if HAS_PROMPT_TOOLKIT:
            click.echo("\n使用交互式模式（支持 Tab 补全）")
            output = prompt(
                '请输入配置保存路径: ',
                completer=PathCompleter(),
                default=output
            )
        else:
            click.echo("\n⚠ 未安装 prompt_toolkit，无法使用 Tab 补全")
            click.echo("  安装方法: pip install prompt_toolkit")
            custom_path = click.prompt(
                '请输入配置保存路径',
                default=output
            )
            output = custom_path
    
    output_path = Path(output)
    
    # 显示将要生成的位置
    click.echo(f"\n将在以下位置生成配置:")
    click.echo(f"  路径: {output_path.absolute()}")
    click.echo(f"  格式: {format.upper()}")
    
    # 检查目录是否已存在
    if output_path.exists() and not force:
        click.echo(f"\n[警告] 目录已存在: {output_path}")
        if not click.confirm('是否覆盖？', default=False):
            click.echo('已取消')
            return
    
    # 确认生成
    if not click.confirm('\n确认生成配置？', default=True):
        click.echo('已取消')
        return
    
    # 生成配置文件
    click.echo("\n正在生成配置文件...")
    try:
        discover_devices = not no_discover
        generate_config_files(output_path, discover_devices=discover_devices, format=format)
        click.echo(f"\n[成功] 配置已成功生成到: {output_path.absolute()}")
        click.echo("\n下一步:")
        click.echo("  1. 将模型文件放到配置目录")
        click.echo(f"  2. 编辑 config.{format}，根据需求调整参数")
        if no_discover:
            click.echo("  3. 运行设备发现工具获取设备 MXid:")
            click.echo("     python tools/config_tools/discover_devices.py")
        if format == 'yaml':
            click.echo("\n提示: YAML 格式支持添加注释，便于配置说明")
        click.echo("\n提示: 配置文件包含完整的系统参数，可根据需要修改")
    except Exception as e:
        click.echo(f"\n[错误] 生成配置失败: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
