# Design Document

## Overview

配置格式转换器（Config Format Converter）为 OAK Vision System 提供 JSON 和 YAML 配置文件格式之间的无缝转换能力。该功能采用双层架构设计：核心转换逻辑作为库代码集成到配置管理器中，CLI 工具提供用户友好的命令行界面。

### 设计目标

1. **格式互转**：支持 JSON ↔ YAML 双向转换
2. **自动识别**：DeviceConfigManager 自动识别配置文件格式
3. **向后兼容**：不影响现有 JSON 配置的使用
4. **可选依赖**：PyYAML 作为可选依赖，不强制安装
5. **用户友好**：提供 CLI 工具和程序化 API 两种使用方式

### 架构层次

```
┌─────────────────────────────────────────┐
│  CLI 工具层（用户命令行交互）              │
│  tools/config_tools/convert_config.py   │
│  tools/config_tools/generate_config.py  │
└──────────────┬──────────────────────────┘
               │ 调用
               ↓
┌─────────────────────────────────────────┐
│  管理器层（高层 API）                     │
│  DeviceConfigManager                    │
│  - load_config() 自动识别格式            │
│  - export_to_yaml()                     │
│  - export_to_json()                     │
└──────────────┬──────────────────────────┘
               │ 调用
               ↓
┌─────────────────────────────────────────┐
│  转换器层（核心逻辑）                     │
│  ConfigConverter                        │
│  - json_to_yaml()                       │
│  - yaml_to_json()                       │
│  - detect_format()                      │
└─────────────────────────────────────────┘
```

## Architecture

### 文件结构

```
oak_vision_system/
├── modules/
│   └── config_manager/
│       ├── __init__.py                    # 导出 ConfigConverter
│       ├── device_config_manager.py       # 集成格式转换功能
│       └── config_converter.py            # 核心转换逻辑（新增）
│
tools/
└── config_tools/
    ├── convert_config.py                  # 配置转换 CLI 工具（新增）
    └── generate_config.py                 # 配置生成工具（增强）
```


## Components and Interfaces

### 1. ConfigConverter（核心转换器）

**位置**：`oak_vision_system/modules/config_manager/config_converter.py`

**职责**：
- 提供 JSON 和 YAML 格式之间的转换核心逻辑
- 自动检测配置文件格式
- 处理依赖缺失的友好提示

**接口设计**：

```python
class ConfigConverter:
    """配置格式转换器
    
    提供 JSON 和 YAML 配置文件格式之间的转换功能。
    所有方法均为静态方法，无需实例化。
    """
    
    @staticmethod
    def detect_format(file_path: Path) -> str:
        """检测配置文件格式
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            str: "json" 或 "yaml"
            
        Raises:
            ValueError: 不支持的文件扩展名
        """
        pass
    
    @staticmethod
    def json_to_yaml(input_path: Path, output_path: Path) -> None:
        """将 JSON 配置转换为 YAML 格式
        
        Args:
            input_path: 输入 JSON 文件路径
            output_path: 输出 YAML 文件路径
            
        Raises:
            FileNotFoundError: 输入文件不存在
            json.JSONDecodeError: JSON 格式错误
            ImportError: PyYAML 未安装
            OSError: 文件读写错误
        """
        pass
    
    @staticmethod
    def yaml_to_json(input_path: Path, output_path: Path) -> None:
        """将 YAML 配置转换为 JSON 格式
        
        Args:
            input_path: 输入 YAML 文件路径
            output_path: 输出 JSON 文件路径
            
        Raises:
            FileNotFoundError: 输入文件不存在
            yaml.YAMLError: YAML 格式错误
            ImportError: PyYAML 未安装
            OSError: 文件读写错误
        """
        pass
    
    @staticmethod
    def load_yaml_as_dict(file_path: Path) -> dict:
        """加载 YAML 文件为字典
        
        Args:
            file_path: YAML 文件路径
            
        Returns:
            dict: 配置字典
            
        Raises:
            ImportError: PyYAML 未安装
            yaml.YAMLError: YAML 格式错误
            OSError: 文件读取错误
        """
        pass
    
    @staticmethod
    def save_as_yaml(config_dict: dict, output_path: Path) -> None:
        """保存字典为 YAML 文件
        
        Args:
            config_dict: 配置字典
            output_path: 输出文件路径
            
        Raises:
            ImportError: PyYAML 未安装
            OSError: 文件写入错误
        """
        pass
```

### 2. DeviceConfigManager（增强）

**位置**：`oak_vision_system/modules/config_manager/device_config_manager.py`

**新增功能**：
- 自动识别配置文件格式（JSON/YAML）
- 导出配置为 YAML 格式
- 导出配置为 JSON 格式

**新增方法**：

```python
class DeviceConfigManager:
    
    def load_config(
        self,
        *,
        validate: bool = True,
        config_path: Optional[str] = None,
        auto_create: Optional[bool] = None
    ) -> bool:
        """加载配置（增强：自动识别 JSON/YAML 格式）
        
        工作流程：
        1. 检测文件格式（通过 ConfigConverter.detect_format）
        2. 如果是 YAML，先转换为 dict，再加载为 ConfigDTO
        3. 如果是 JSON，使用现有逻辑直接加载
        4. 验证配置有效性
        
        Args:
            validate: 是否验证配置
            config_path: 配置文件路径
            auto_create: 是否自动创建默认配置
            
        Returns:
            bool: 加载成功返回 True
            
        Raises:
            ConfigNotFoundError: 配置文件不存在且未启用自动创建
            ConfigValidationError: 配置格式错误或验证失败
            ImportError: 加载 YAML 时 PyYAML 未安装
        """
        pass
    
    def export_to_yaml(self, output_path: str) -> None:
        """导出当前配置为 YAML 格式
        
        Args:
            output_path: 输出文件路径
            
        Raises:
            ConfigValidationError: 配置未加载
            ImportError: PyYAML 未安装
            OSError: 文件写入错误
        """
        pass
    
    def export_to_json(self, output_path: str) -> None:
        """导出当前配置为 JSON 格式
        
        Args:
            output_path: 输出文件路径
            
        Raises:
            ConfigValidationError: 配置未加载
            OSError: 文件写入错误
        """
        pass
```


### 3. CLI 转换工具（终端交互型）

**位置**：`tools/config_tools/convert_config.py`

**职责**：
- 提供用户友好的终端交互界面
- 调用 ConfigConverter 执行转换
- 在终端显示友好的错误提示和进度信息
- 支持交互式确认和用户输入

**终端交互特性**：
- 彩色输出（成功 ✅、错误 ❌、警告 ⚠️、进度 🔄）
- 进度指示器
- 交互式确认提示
- 友好的错误信息格式化
- 操作摘要显示

**命令行接口**：

```bash
# 基本用法（交互式）
python tools/config_tools/convert_config.py <input_file> --format <json|yaml>

# 指定输出路径
python tools/config_tools/convert_config.py config.json --format yaml --output config.yaml

# 转换后验证配置
python tools/config_tools/convert_config.py config.json --format yaml --validate

# 强制覆盖已存在的文件（跳过确认）
python tools/config_tools/convert_config.py config.json --format yaml --force
```

**终端输出示例**：

```
🔄 正在转换配置文件...
   输入: config.json (JSON)
   输出: config.yaml (YAML)

✅ 转换成功！
   配置已保存到: config.yaml
   
💡 提示: 你可以手动编辑 YAML 文件添加注释
```

**错误输出示例**：

```
❌ 转换失败: 配置文件不存在
   文件路径: /path/to/config.json
   
💡 提示: 请检查文件路径是否正确
```

**交互式确认示例**：

```
⚠️  文件已存在: config.yaml
   是否覆盖? [y/N]: _
```

**实现设计**：

```python
import click
from pathlib import Path
from oak_vision_system.modules.config_manager import ConfigConverter, DeviceConfigManager

@click.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option(
    '--format', '-f',
    type=click.Choice(['json', 'yaml']),
    required=True,
    help='目标格式'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='输出文件路径（默认：与输入文件同名，扩展名改为目标格式）'
)
@click.option(
    '--validate', '-v',
    is_flag=True,
    help='转换后验证配置有效性'
)
@click.option(
    '--force',
    is_flag=True,
    help='强制覆盖已存在的文件'
)
def main(input_file, format, output, validate, force):
    """配置文件格式转换工具（终端交互型）
    
    支持 JSON 和 YAML 格式之间的双向转换。
    提供友好的终端交互界面和进度显示。
    
    示例:
        python convert_config.py config.json --format yaml
        python convert_config.py config.yaml --format json --validate
    """
    # 显示转换信息
    click.echo("🔄 正在转换配置文件...")
    click.echo(f"   输入: {input_file}")
    
    # 检查输出文件是否存在
    if output_path.exists() and not force:
        if not click.confirm(f"⚠️  文件已存在: {output_path}\n   是否覆盖?", default=False):
            click.echo("❌ 已取消")
            return
    
    try:
        # 执行转换
        ConfigConverter.json_to_yaml(input_path, output_path)
        
        # 显示成功信息
        click.echo(f"\n✅ 转换成功！")
        click.echo(f"   配置已保存到: {output_path}")
        
        # 可选验证
        if validate:
            click.echo("\n🔍 正在验证配置...")
            # 验证逻辑
            click.echo("✅ 配置验证通过")
        
        # 提示信息
        if format == 'yaml':
            click.echo("\n💡 提示: 你可以手动编辑 YAML 文件添加注释")
            
    except Exception as e:
        click.echo(f"\n❌ 转换失败: {e}", err=True)
        click.echo(f"\n💡 提示: 请检查文件格式和路径是否正确")
        sys.exit(1)
```

### 4. 配置生成工具（增强）

**位置**：`tools/config_tools/generate_config.py`

**新增功能**：
- 支持 `--format` 选项指定生成格式（json/yaml）
- 默认生成 JSON 格式（向后兼容）

**新增选项**：

```python
@click.option(
    '--format', '-f',
    type=click.Choice(['json', 'yaml']),
    default='json',
    help='配置文件格式（默认: json）'
)
def main(output, interactive, force, no_discover, format):
    """生成默认配置文件
    
    支持生成 JSON 或 YAML 格式的配置文件。
    """
    pass
```

## Data Models

### 配置文件格式

#### JSON 格式（现有）

```json
{
  "config_version": "2.0.0",
  "oak_module": {
    "role_bindings": {
      "LEFT_CAMERA": {
        "role": "LEFT_CAMERA",
        "active_mxid": "14442C10D13F7FD000",
        "historical_mxids": ["14442C10D13F7FD000"]
      }
    },
    "hardware_config": {
      "model_path": "models/mobilenet.blob",
      "confidence_threshold": 0.5
    }
  }
}
```

#### YAML 格式（新增）

```yaml
config_version: "2.0.0"

oak_module:
  role_bindings:
    LEFT_CAMERA:
      role: LEFT_CAMERA
      active_mxid: "14442C10D13F7FD000"
      historical_mxids:
        - "14442C10D13F7FD000"
  
  hardware_config:
    model_path: "models/mobilenet.blob"
    confidence_threshold: 0.5
```

### 格式检测规则

```python
# 基于文件扩展名
.json  → JSON 格式
.yaml  → YAML 格式
.yml   → YAML 格式
其他   → 抛出 ValueError
```


## Correctness Properties

*属性（Property）是系统在所有有效执行中应该保持为真的特征或行为——本质上是关于系统应该做什么的形式化陈述。属性是人类可读规范和机器可验证正确性保证之间的桥梁。*

### Property Reflection

在生成最终属性之前，我们需要识别并消除冗余属性：

**冗余分析**：
1. **Round-trip 属性合并**：
   - 1.1 (JSON → YAML) 和 1.2 (YAML → JSON) 可以合并为一个双向 round-trip 属性
   - 1.4 (语义等价) 实际上被 round-trip 属性包含
   - 9.1 (转换后可加载) 和 9.5 (数据完整性) 也是 round-trip 的一部分

2. **格式检测属性合并**：
   - 2.1 (.json 识别) 和 2.2 (.yaml/.yml 识别) 可以合并为一个格式检测属性

3. **日志记录属性合并**：
   - 3.5, 4.4, 10.1, 10.4 都是日志记录相关，可以合并为一个日志记录属性

4. **错误处理属性合并**：
   - 1.3, 2.3, 3.4 都是错误处理，可以合并为一个错误处理属性

**最终属性列表**（消除冗余后）：

### Core Properties

**Property 1: Round-trip Conversion Preserves Semantics**
*For any* valid configuration dictionary, converting JSON → YAML → JSON (or YAML → JSON → YAML) should produce a semantically equivalent configuration that can be successfully loaded by DeviceConfigManager.
**Validates: Requirements 1.1, 1.2, 1.4, 9.1, 9.5**

**Property 2: Format Detection is Accurate**
*For any* file path with extension .json, .yaml, or .yml, the ConfigConverter should correctly identify the format as "json" or "yaml" respectively.
**Validates: Requirements 2.1, 2.2**

**Property 3: Invalid Formats Raise Clear Errors**
*For any* file path with an unsupported extension or invalid content, the ConfigConverter should raise an appropriate exception with a descriptive error message.
**Validates: Requirements 1.3, 2.3, 3.4**

**Property 4: YAML Loading Integration**
*For any* valid YAML configuration file, DeviceConfigManager should successfully load it and convert it to a ConfigDTO object, producing the same result as loading an equivalent JSON file.
**Validates: Requirements 3.2, 3.3**

**Property 5: Configuration Export Preserves Content**
*For any* loaded configuration, exporting to YAML or JSON and then reloading should produce an equivalent ConfigDTO object.
**Validates: Requirements 4.1, 4.2**

**Property 6: Logging Records Key Operations**
*For any* successful configuration load or export operation, the system should record an info-level log entry containing the file path and detected/target format.
**Validates: Requirements 3.5, 4.4, 10.1, 10.4**

**Property 7: Error Handling Provides Context**
*For any* operation that fails (file not found, parse error, validation error), the system should provide an error message that includes the file path and specific failure reason.
**Validates: Requirements 10.2, 10.3**

### Integration Properties

**Property 8: Backward Compatibility Maintained**
*For any* existing JSON configuration file and code using DeviceConfigManager, the new YAML support should not change the loading behavior or API signatures.
**Validates: Requirements 8.1, 8.2**

**Property 9: Optional Dependency Handling**
*For any* operation requiring PyYAML when the library is not installed, the system should raise an ImportError with a clear message including the installation command.
**Validates: Requirements 7.1, 7.2**

**Property 10: Validation Detects Corruption**
*For any* configuration that has been converted, validation should detect any data loss, type changes, or structural corruption.
**Validates: Requirements 9.3, 9.4**


## Error Handling

### 错误类型和处理策略

#### 1. 文件操作错误

**FileNotFoundError**
- 触发条件：输入文件不存在
- 处理策略：抛出异常，提供文件路径
- 错误信息格式：`"配置文件不存在: {file_path}"`

**OSError**
- 触发条件：文件读写权限问题、磁盘空间不足
- 处理策略：抛出异常，提供文件路径和系统错误信息
- 错误信息格式：`"文件操作失败: {error}, path={file_path}"`

#### 2. 格式解析错误

**json.JSONDecodeError**
- 触发条件：JSON 格式错误
- 处理策略：抛出 ConfigValidationError，包含错误位置
- 错误信息格式：`"JSON 解析失败: {error}, path={file_path}"`

**yaml.YAMLError**
- 触发条件：YAML 格式错误
- 处理策略：抛出 ConfigValidationError，包含错误位置
- 错误信息格式：`"YAML 解析失败: {error}, path={file_path}"`

#### 3. 依赖缺失错误

**ImportError (PyYAML)**
- 触发条件：尝试使用 YAML 功能但 PyYAML 未安装
- 处理策略：抛出 ImportError，提供安装命令
- 错误信息格式：
  ```
  需要安装 PyYAML 才能使用 YAML 配置
  运行: pip install pyyaml
  或: pip install oak_vision_system[yaml]
  ```

#### 4. 配置验证错误

**ConfigValidationError**
- 触发条件：配置结构不符合 ConfigDTO 约束
- 处理策略：抛出异常，提供详细的验证错误列表
- 错误信息格式：`"配置验证失败: {error1}; {error2}; ..."`

#### 5. 格式不支持错误

**ValueError**
- 触发条件：文件扩展名不是 .json, .yaml, .yml
- 处理策略：抛出异常，列出支持的格式
- 错误信息格式：`"不支持的文件格式: {extension}，支持的格式: .json, .yaml, .yml"`

### 错误处理流程

```python
# ConfigConverter 错误处理示例
def json_to_yaml(input_path: Path, output_path: Path) -> None:
    try:
        # 1. 检查文件存在
        if not input_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {input_path}")
        
        # 2. 检查 PyYAML 依赖
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "需要安装 PyYAML 才能使用 YAML 配置\n"
                "运行: pip install pyyaml\n"
                "或: pip install oak_vision_system[yaml]"
            )
        
        # 3. 读取和解析 JSON
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigValidationError(
                f"JSON 解析失败: {e}, path={input_path}"
            )
        except OSError as e:
            raise OSError(f"文件读取失败: {e}, path={input_path}")
        
        # 4. 写入 YAML
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, 
                         default_flow_style=False, sort_keys=False)
        except OSError as e:
            raise OSError(f"文件写入失败: {e}, path={output_path}")
        
        # 5. 记录日志
        logger.info(f"配置已转换: {input_path} → {output_path}")
        
    except Exception as e:
        # 记录错误日志
        logger.error(f"配置转换失败: {e}", exc_info=True)
        raise
```

### CLI 工具错误处理（终端交互）

```python
# convert_config.py 错误处理示例
def main(input_file, format, output, validate, force):
    try:
        # 显示进度
        click.echo("🔄 正在转换配置文件...")
        
        # 执行转换
        ConfigConverter.json_to_yaml(input_path, output_path)
        
        # 成功消息
        click.echo(f"✅ 转换成功: {output_path}")
        
    except FileNotFoundError as e:
        click.echo(f"❌ 文件不存在: {e}", err=True)
        click.echo("💡 提示: 请检查文件路径是否正确", err=True)
        sys.exit(1)
        
    except ImportError as e:
        click.echo(f"❌ 依赖缺失:\n{e}", err=True)
        click.echo("💡 提示: 运行 'pip install pyyaml' 安装依赖", err=True)
        sys.exit(2)
        
    except ConfigValidationError as e:
        click.echo(f"❌ 配置验证失败:\n{e}", err=True)
        click.echo("💡 提示: 请检查配置文件格式是否正确", err=True)
        sys.exit(3)
        
    except Exception as e:
        click.echo(f"❌ 转换失败: {e}", err=True)
        click.echo("💡 提示: 请查看错误信息或联系技术支持", err=True)
        sys.exit(99)
```


## Testing Strategy

### 测试方法论

本功能采用**双重测试策略**：单元测试验证具体示例和边界情况，属性测试验证通用正确性属性。两者互补，共同确保全面覆盖。

### 1. 单元测试（Unit Tests）

**测试框架**：pytest

**测试范围**：
- 具体示例验证
- 边界情况处理
- 错误条件测试
- 集成点验证

**测试文件组织**：
```
oak_vision_system/tests/unit/modules/config_manager/
├── test_config_converter.py              # ConfigConverter 单元测试
├── test_config_manager_format_support.py # DeviceConfigManager 格式支持测试
└── test_config_converter_errors.py       # 错误处理测试
```

**关键测试用例**：

```python
# test_config_converter.py

def test_detect_format_json():
    """测试 JSON 格式检测"""
    assert ConfigConverter.detect_format(Path("config.json")) == "json"

def test_detect_format_yaml():
    """测试 YAML 格式检测"""
    assert ConfigConverter.detect_format(Path("config.yaml")) == "yaml"
    assert ConfigConverter.detect_format(Path("config.yml")) == "yaml"

def test_detect_format_unsupported():
    """测试不支持的格式"""
    with pytest.raises(ValueError, match="不支持的文件格式"):
        ConfigConverter.detect_format(Path("config.txt"))

def test_json_to_yaml_basic(tmp_path):
    """测试基本 JSON 到 YAML 转换"""
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"
    
    # 创建测试 JSON
    config = {"config_version": "2.0.0", "test": "value"}
    json_file.write_text(json.dumps(config))
    
    # 转换
    ConfigConverter.json_to_yaml(json_file, yaml_file)
    
    # 验证
    assert yaml_file.exists()
    loaded = yaml.safe_load(yaml_file.read_text())
    assert loaded == config

def test_yaml_to_json_basic(tmp_path):
    """测试基本 YAML 到 JSON 转换"""
    yaml_file = tmp_path / "config.yaml"
    json_file = tmp_path / "config.json"
    
    # 创建测试 YAML
    config = {"config_version": "2.0.0", "test": "value"}
    yaml_file.write_text(yaml.dump(config))
    
    # 转换
    ConfigConverter.yaml_to_json(yaml_file, json_file)
    
    # 验证
    assert json_file.exists()
    loaded = json.loads(json_file.read_text())
    assert loaded == config

def test_file_not_found():
    """测试文件不存在错误"""
    with pytest.raises(FileNotFoundError):
        ConfigConverter.json_to_yaml(
            Path("nonexistent.json"),
            Path("output.yaml")
        )

def test_pyyaml_not_installed(monkeypatch):
    """测试 PyYAML 未安装错误"""
    # 模拟 PyYAML 未安装
    monkeypatch.setattr("builtins.__import__", 
                       lambda name, *args: (_ for _ in ()).throw(ImportError) 
                       if name == "yaml" else __import__(name, *args))
    
    with pytest.raises(ImportError, match="需要安装 PyYAML"):
        ConfigConverter.load_yaml_as_dict(Path("config.yaml"))
```

### 2. 属性测试（Property-Based Tests）

**测试框架**：Hypothesis

**配置**：每个属性测试运行 **最少 100 次迭代**

**测试文件组织**：
```
oak_vision_system/tests/unit/modules/config_manager/
└── test_config_converter_properties.py   # 属性测试
```

**属性测试实现**：

```python
# test_config_converter_properties.py
from hypothesis import given, strategies as st
import hypothesis

# 配置 Hypothesis
hypothesis.settings.register_profile("ci", max_examples=100)
hypothesis.settings.load_profile("ci")

# 配置字典生成策略
@st.composite
def config_dict_strategy(draw):
    """生成有效的配置字典"""
    return {
        "config_version": "2.0.0",
        "oak_module": {
            "role_bindings": {},
            "hardware_config": {
                "model_path": draw(st.text(min_size=1)),
                "confidence_threshold": draw(st.floats(0.0, 1.0))
            }
        }
    }

@given(config=config_dict_strategy())
def test_property_round_trip_json_yaml_json(config, tmp_path):
    """
    Feature: config-format-converter, Property 1: Round-trip Conversion Preserves Semantics
    
    For any valid configuration, JSON → YAML → JSON should preserve semantics.
    """
    json1 = tmp_path / "config1.json"
    yaml_file = tmp_path / "config.yaml"
    json2 = tmp_path / "config2.json"
    
    # JSON → YAML → JSON
    json1.write_text(json.dumps(config))
    ConfigConverter.json_to_yaml(json1, yaml_file)
    ConfigConverter.yaml_to_json(yaml_file, json2)
    
    # 验证语义等价
    result = json.loads(json2.read_text())
    assert result == config

@given(config=config_dict_strategy())
def test_property_round_trip_yaml_json_yaml(config, tmp_path):
    """
    Feature: config-format-converter, Property 1: Round-trip Conversion Preserves Semantics
    
    For any valid configuration, YAML → JSON → YAML should preserve semantics.
    """
    yaml1 = tmp_path / "config1.yaml"
    json_file = tmp_path / "config.json"
    yaml2 = tmp_path / "config2.yaml"
    
    # YAML → JSON → YAML
    yaml1.write_text(yaml.dump(config))
    ConfigConverter.yaml_to_json(yaml1, json_file)
    ConfigConverter.json_to_yaml(json_file, yaml2)
    
    # 验证语义等价
    result = yaml.safe_load(yaml2.read_text())
    assert result == config

@given(extension=st.sampled_from([".json", ".yaml", ".yml"]))
def test_property_format_detection(extension):
    """
    Feature: config-format-converter, Property 2: Format Detection is Accurate
    
    For any supported file extension, format detection should be correct.
    """
    file_path = Path(f"config{extension}")
    detected = ConfigConverter.detect_format(file_path)
    
    if extension == ".json":
        assert detected == "json"
    else:
        assert detected == "yaml"

@given(extension=st.text(min_size=1).filter(
    lambda x: x not in [".json", ".yaml", ".yml"]
))
def test_property_invalid_format_raises_error(extension):
    """
    Feature: config-format-converter, Property 3: Invalid Formats Raise Clear Errors
    
    For any unsupported extension, should raise ValueError.
    """
    file_path = Path(f"config{extension}")
    with pytest.raises(ValueError):
        ConfigConverter.detect_format(file_path)

@given(config=config_dict_strategy())
def test_property_export_preserves_content(config, tmp_path):
    """
    Feature: config-format-converter, Property 5: Configuration Export Preserves Content
    
    For any loaded configuration, export and reload should preserve content.
    """
    # 创建 ConfigDTO
    dto = DeviceManagerConfigDTO.from_dict(config)
    
    # 导出为 YAML
    yaml_file = tmp_path / "export.yaml"
    config_dict = dto.to_dict()
    ConfigConverter.save_as_yaml(config_dict, yaml_file)
    
    # 重新加载
    reloaded_dict = ConfigConverter.load_yaml_as_dict(yaml_file)
    reloaded_dto = DeviceManagerConfigDTO.from_dict(reloaded_dict)
    
    # 验证等价
    assert reloaded_dto.to_dict() == dto.to_dict()
```

### 3. 集成测试（Integration Tests）

**测试范围**：
- DeviceConfigManager 与 ConfigConverter 的集成
- CLI 工具的端到端测试
- 与现有配置系统的兼容性测试

**测试文件组织**：
```
oak_vision_system/tests/integration/config_manager/
├── test_config_manager_yaml_support.py   # YAML 支持集成测试
└── test_cli_convert_config.py            # CLI 工具集成测试
```

**关键集成测试**：

```python
# test_config_manager_yaml_support.py

def test_load_yaml_config(tmp_path):
    """测试 DeviceConfigManager 加载 YAML 配置"""
    yaml_file = tmp_path / "config.yaml"
    
    # 创建有效的 YAML 配置
    config = template_DeviceManagerConfigDTO([])
    yaml_file.write_text(yaml.dump(config.to_dict()))
    
    # 加载
    manager = DeviceConfigManager(str(yaml_file))
    manager.load_config()
    
    # 验证
    loaded = manager.get_config()
    assert loaded.config_version == config.config_version

def test_export_to_yaml(tmp_path):
    """测试导出为 YAML"""
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"
    
    # 创建并保存 JSON 配置
    manager = DeviceConfigManager(str(json_file))
    manager.create_and_set_default_config()
    manager.save_config()
    
    # 导出为 YAML
    manager.export_to_yaml(str(yaml_file))
    
    # 验证
    assert yaml_file.exists()
    loaded = yaml.safe_load(yaml_file.read_text())
    assert "config_version" in loaded

def test_backward_compatibility(tmp_path):
    """测试向后兼容性"""
    json_file = tmp_path / "config.json"
    
    # 使用现有方式创建配置
    manager = DeviceConfigManager(str(json_file))
    manager.create_and_set_default_config()
    manager.save_config()
    
    # 重新加载（应该仍然工作）
    manager2 = DeviceConfigManager(str(json_file))
    manager2.load_config()
    
    assert manager2.get_config() is not None
```

### 4. CLI 工具测试

**测试框架**：Click Testing (CliRunner)

```python
# test_cli_convert_config.py
from click.testing import CliRunner
from tools.config_tools.convert_config import main

def test_cli_convert_json_to_yaml(tmp_path):
    """测试 CLI 工具 JSON 到 YAML 转换（终端交互）"""
    runner = CliRunner()
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"
    
    # 创建测试文件
    json_file.write_text('{"test": "value"}')
    
    # 运行 CLI
    result = runner.invoke(main, [
        str(json_file),
        '--format', 'yaml',
        '--output', str(yaml_file)
    ])
    
    assert result.exit_code == 0
    assert yaml_file.exists()
    assert "🔄 正在转换" in result.output
    assert "✅ 转换成功" in result.output

def test_cli_interactive_confirmation(tmp_path):
    """测试终端交互式确认"""
    runner = CliRunner()
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"
    
    # 创建测试文件
    json_file.write_text('{"test": "value"}')
    yaml_file.write_text('existing content')
    
    # 测试拒绝覆盖
    result = runner.invoke(main, [
        str(json_file),
        '--format', 'yaml',
        '--output', str(yaml_file)
    ], input='n\n')
    
    assert result.exit_code == 0
    assert "⚠️  文件已存在" in result.output
    assert "❌ 已取消" in result.output
    
    # 测试接受覆盖
    result = runner.invoke(main, [
        str(json_file),
        '--format', 'yaml',
        '--output', str(yaml_file)
    ], input='y\n')
    
    assert result.exit_code == 0
    assert "✅ 转换成功" in result.output

def test_cli_validate_option(tmp_path):
    """测试 --validate 选项"""
    runner = CliRunner()
    json_file = tmp_path / "config.json"
    
    # 创建有效配置
    config = template_DeviceManagerConfigDTO([])
    json_file.write_text(config.to_json())
    
    # 运行带验证的转换
    result = runner.invoke(main, [
        str(json_file),
        '--format', 'yaml',
        '--validate'
    ])
    
    assert result.exit_code == 0
    assert "验证通过" in result.output or "转换成功" in result.output
```

### 测试覆盖率目标

- **单元测试覆盖率**：> 90%
- **属性测试迭代次数**：≥ 100 次/属性
- **集成测试覆盖**：所有关键用户流程
- **CLI 测试覆盖**：所有命令行选项和错误场景



## YAML 注释保持功能设计

### 技术选型：ruamel.yaml

**选择理由**：
1. **注释保持**：完整保留用户手动添加的注释
2. **格式保持**：保持原有缩进、引号风格和空行
3. **中文支持**：完美支持中文注释和字符
4. **向后兼容**：API 与 PyYAML 类似，易于迁移

**依赖策略**：
- ruamel.yaml 作为可选依赖（推荐）
- PyYAML 作为回退方案（不保留注释）
- 优先使用 ruamel.yaml，自动回退到 PyYAML

### 依赖管理

**pyproject.toml 配置**：

```toml
[project.optional-dependencies]
yaml = [
    "ruamel.yaml>=0.17.0",  # 推荐：支持注释保持
]

# 向后兼容：仍然支持 PyYAML
yaml-basic = [
    "PyYAML>=6.0",  # 基础 YAML 支持（不保留注释）
]
```

**安装方式**：

```bash
# 推荐：安装 ruamel.yaml（支持注释保持）
pip install oak_vision_system[yaml]

# 或：仅安装 PyYAML（基础功能）
pip install oak_vision_system[yaml-basic]

# 或：手动安装
pip install ruamel.yaml
```

### ConfigConverter 增强设计

**库检测和回退逻辑**：

```python
# config_converter.py

import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 尝试导入 ruamel.yaml（优先）
try:
    from ruamel.yaml import YAML
    HAS_RUAMEL_YAML = True
    logger.debug("使用 ruamel.yaml（支持注释保持）")
except ImportError:
    HAS_RUAMEL_YAML = False
    logger.debug("ruamel.yaml 未安装，将回退到 PyYAML")

# 回退到 PyYAML
if not HAS_RUAMEL_YAML:
    try:
        import yaml as pyyaml
        HAS_PYYAML = True
        logger.debug("使用 PyYAML（不保留注释）")
    except ImportError:
        HAS_PYYAML = False


class ConfigConverter:
    """配置格式转换器（增强版）
    
    支持 ruamel.yaml 注释保持功能。
    优先使用 ruamel.yaml，自动回退到 PyYAML。
    """
    
    @staticmethod
    def _get_yaml_handler():
        """获取 YAML 处理器
        
        Returns:
            YAML 处理器实例或 None
            
        Raises:
            ImportError: 两个库都未安装
        """
        if HAS_RUAMEL_YAML:
            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.default_flow_style = False
            yaml.allow_unicode = True
            yaml.width = 4096  # 避免长行自动换行
            return yaml
        elif HAS_PYYAML:
            logger.warning(
                "使用 PyYAML 作为回退方案，注释将不会被保留。"
                "推荐安装 ruamel.yaml: pip install ruamel.yaml"
            )
            return None  # 使用 PyYAML 的全局函数
        else:
            raise ImportError(
                "需要安装 YAML 库才能使用 YAML 配置\n"
                "推荐: pip install ruamel.yaml (支持注释保持)\n"
                "或: pip install pyyaml (基础功能)\n"
                "或: pip install oak_vision_system[yaml]"
            )
    
    @staticmethod
    def load_yaml_as_dict(file_path: Path) -> Dict[str, Any]:
        """加载 YAML 文件为字典（保留注释信息）
        
        Args:
            file_path: YAML 文件路径
            
        Returns:
            dict: 配置字典
            
        Raises:
            ImportError: YAML 库未安装
            OSError: 文件读取错误
        """
        yaml_handler = ConfigConverter._get_yaml_handler()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if HAS_RUAMEL_YAML:
                    # ruamel.yaml: 保留注释
                    data = yaml_handler.load(f)
                else:
                    # PyYAML: 不保留注释
                    data = pyyaml.safe_load(f)
            return data
        except Exception as e:
            raise OSError(f"YAML 文件读取失败: {e}, path={file_path}")
    
    @staticmethod
    def save_as_yaml(
        config_dict: Dict[str, Any], 
        output_path: Path,
        preserve_comments: bool = True
    ) -> None:
        """保存字典为 YAML 文件（保留注释）
        
        Args:
            config_dict: 配置字典
            output_path: 输出文件路径
            preserve_comments: 是否尝试保留注释（需要 ruamel.yaml）
            
        Raises:
            ImportError: YAML 库未安装
            OSError: 文件写入错误
        """
        yaml_handler = ConfigConverter._get_yaml_handler()
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                if HAS_RUAMEL_YAML:
                    # ruamel.yaml: 保留注释和格式
                    yaml_handler.dump(config_dict, f)
                else:
                    # PyYAML: 不保留注释
                    pyyaml.dump(
                        config_dict,
                        f,
                        allow_unicode=True,
                        default_flow_style=False,
                        sort_keys=False
                    )
        except OSError as e:
            raise OSError(f"YAML 文件写入失败: {e}, path={output_path}")
```

### 配置文件注释模板设计

**注释添加策略**：
1. **文件头部注释**：配置文件说明和最后修改时间
2. **字段行内注释**：关键字段的说明和可选值
3. **分组注释**：配置分组的说明

**注释模板示例**：

```yaml
# OAK Vision System 配置文件
# 版本: 2.0.0
# 最后修改: 2026-01-27 15:30
# 
# 说明:
#   - 本文件支持中文注释
#   - 修改后请保存为 UTF-8 编码
#   - 详细文档: https://docs.example.com

config_version: "2.0.0"

# ========== 坐标变换配置 ==========
# 用于多相机系统的坐标系对齐
coordinate_transforms:
  left_camera:
    role: left_camera
    
    # 平移参数（单位：毫米）
    translation_x: -50.0  # 左相机向左偏移
    translation_y: 0.0
    translation_z: 0.0
    
    # 旋转参数（单位：度）
    roll: 0.0   # 滚转角
    pitch: 0.0  # 俯仰角
    yaw: 0.0    # 偏航角
    
    # 标定信息
    calibration_date: null  # 格式: "YYYY-MM-DD HH:MM"
    calibration_method: null  # 可选值: manual（手动）或 auto（自动）
  
  right_camera:
    role: right_camera
    translation_x: 50.0  # 右相机向右偏移
    # ... 其他参数同上
```

**注释生成工具**：

```python
# config_template.py

def add_yaml_comments(yaml_handler, config_dict: Dict[str, Any]) -> None:
    """为配置字典添加注释（仅 ruamel.yaml）
    
    Args:
        yaml_handler: ruamel.yaml YAML 实例
        config_dict: 配置字典
    """
    if not HAS_RUAMEL_YAML:
        return  # PyYAML 不支持注释
    
    # 文件头部注释
    yaml_handler.yaml_set_start_comment(
        "OAK Vision System 配置文件\n"
        f"版本: {config_dict.get('config_version', '2.0.0')}\n"
        f"最后修改: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    # 字段注释
    if 'coordinate_transforms' in config_dict:
        yaml_handler.yaml_set_comment_before_after_key(
            'coordinate_transforms',
            before='\n========== 坐标变换配置 ==========\n用于多相机系统的坐标系对齐'
        )
        
        # 为嵌套字段添加注释
        for role, transform in config_dict['coordinate_transforms'].items():
            # calibration_method 注释
            yaml_handler.yaml_set_comment_before_after_key(
                'calibration_method',
                after='可选值: manual（手动）或 auto（自动）',
                indent=2
            )
```

### 用户体验增强

**加载时的提示**：

```python
def load_config(self, validate: bool = True) -> bool:
    """加载配置（增强版）"""
    # ... 现有逻辑 ...
    
    # 检测 YAML 库
    if format_type == "yaml":
        if HAS_RUAMEL_YAML:
            self.logger.info(
                f"配置已加载: path={path}, format=yaml (支持注释保持)"
            )
        elif HAS_PYYAML:
            self.logger.warning(
                f"配置已加载: path={path}, format=yaml (使用 PyYAML，注释将不会保留)\n"
                f"推荐安装 ruamel.yaml 以支持注释保持: pip install ruamel.yaml"
            )
```

**保存时的提示**：

```python
def export_to_yaml(self, output_path: str) -> None:
    """导出为 YAML（增强版）"""
    # ... 现有逻辑 ...
    
    if HAS_RUAMEL_YAML:
        self.logger.info(
            f"配置已导出为 YAML: path={output_path} (支持注释保持)"
        )
    else:
        self.logger.warning(
            f"配置已导出为 YAML: path={output_path} (不保留注释)\n"
            f"推荐安装 ruamel.yaml: pip install ruamel.yaml"
        )
```

### 测试策略

**注释保持测试**：

```python
def test_yaml_comment_preservation():
    """测试 YAML 注释保持功能"""
    if not HAS_RUAMEL_YAML:
        pytest.skip("需要 ruamel.yaml")
    
    # 1. 创建带注释的 YAML 文件
    yaml_content = """
# 这是顶部注释
config_version: "2.0.0"  # 这是行内注释

# 这是分组注释
coordinate_transforms:
  left_camera:
    translation_x: -50.0  # 用户添加的注释
"""
    
    # 2. 加载配置
    manager = DeviceConfigManager(yaml_file)
    manager.load_config()
    
    # 3. 修改配置
    # ... 修改逻辑 ...
    
    # 4. 保存配置
    manager.save_config()
    
    # 5. 验证注释保留
    saved_content = yaml_file.read_text()
    assert "这是顶部注释" in saved_content
    assert "这是行内注释" in saved_content
    assert "用户添加的注释" in saved_content
```

**中文注释测试**：

```python
def test_chinese_comments():
    """测试中文注释支持"""
    yaml_content = """
# 配置文件说明
config_version: "2.0.0"  # 版本号

coordinate_transforms:
  left_camera:
    translation_x: -50.0  # 左相机向左偏移 50 毫米
    calibration_method: manual  # 手动标定
"""
    
    # 加载 → 保存 → 验证
    # ... 测试逻辑 ...
    
    assert "配置文件说明" in saved_content
    assert "左相机向左偏移 50 毫米" in saved_content
```

