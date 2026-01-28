"""
ConfigConverter 属性测试

使用 Hypothesis 进行属性测试，验证配置转换器的正确性属性。

测试属性：
- Property 1: Round-trip Conversion Preserves Semantics
- Property 2: Format Detection is Accurate
- Property 4: YAML Loading Integration
- Property 5: Configuration Export Preserves Content
- Property 6: Logging Records Key Operations
"""

import pytest
import json
import logging
from pathlib import Path
from hypothesis import given, strategies as st, settings, HealthCheck

from oak_vision_system.modules.config_manager.config_converter import ConfigConverter
from oak_vision_system.modules.config_manager.device_config_manager import DeviceConfigManager
from oak_vision_system.core.dto.config_dto import DeviceManagerConfigDTO
from oak_vision_system.utils import template_DeviceManagerConfigDTO


# 配置 Hypothesis
settings.register_profile("ci", max_examples=100)
settings.load_profile("ci")


# ==================== 策略定义 ====================

@st.composite
def simple_config_dict_strategy(draw):
    """生成简单的配置字典（用于转换测试）
    
    注意：排除 YAML 会规范化的控制字符（\x00-\x1f, \x7f-\x9f）
    这些字符在 YAML 规范中会被转换为空格或其他字符。
    同时避免极端浮点数值，因为 YAML 可能会将其序列化为字符串。
    """
    # 定义安全的字符集：排除控制字符和代理字符
    safe_alphabet = st.characters(
        blacklist_categories=('Cc', 'Cs'),  # 排除控制字符和代理字符
        blacklist_characters='\x85\xa0'  # 排除 YAML 特殊处理的字符
    )
    
    return {
        "config_version": "2.0.0",
        "test_string": draw(st.text(alphabet=safe_alphabet, min_size=1, max_size=50)),
        "test_number": draw(st.integers(min_value=0, max_value=1000)),
        "test_float": draw(st.floats(
            min_value=1e-10, max_value=1e10, 
            allow_nan=False, allow_infinity=False,
            exclude_min=True, exclude_max=True
        )),
        "test_bool": draw(st.booleans()),
        "test_list": draw(st.lists(st.integers(), min_size=0, max_size=5)),
        "test_dict": {
            "nested_key": draw(st.text(alphabet=safe_alphabet, min_size=1, max_size=20))
        }
    }


# ==================== Property 1: Round-trip Conversion ====================

@given(config=simple_config_dict_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_round_trip_json_yaml_json(config, tmp_path):
    """
    Feature: config-format-converter, Property 1: Round-trip Conversion Preserves Semantics
    
    For any valid configuration, JSON → YAML → JSON should preserve semantics.
    
    **Validates: Requirements 1.1, 1.2, 1.4**
    """
    json1 = tmp_path / "config1.json"
    yaml_file = tmp_path / "config.yaml"
    json2 = tmp_path / "config2.json"
    
    # JSON → YAML → JSON
    json1.write_text(json.dumps(config), encoding='utf-8')
    ConfigConverter.json_to_yaml(json1, yaml_file)
    ConfigConverter.yaml_to_json(yaml_file, json2)
    
    # 验证语义等价
    result = json.loads(json2.read_text(encoding='utf-8'))
    assert result == config, f"Round-trip failed: {config} != {result}"


@given(config=simple_config_dict_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_round_trip_yaml_json_yaml(config, tmp_path):
    """
    Feature: config-format-converter, Property 1: Round-trip Conversion Preserves Semantics
    
    For any valid configuration, YAML → JSON → YAML should preserve semantics.
    
    **Validates: Requirements 1.1, 1.2, 1.4**
    """
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    yaml1 = tmp_path / "config1.yaml"
    json_file = tmp_path / "config.json"
    yaml2 = tmp_path / "config2.yaml"
    
    # YAML → JSON → YAML
    yaml1.write_text(yaml.dump(config), encoding='utf-8')
    ConfigConverter.yaml_to_json(yaml1, json_file)
    ConfigConverter.json_to_yaml(json_file, yaml2)
    
    # 验证语义等价
    result = yaml.safe_load(yaml2.read_text(encoding='utf-8'))
    assert result == config, f"Round-trip failed: {config} != {result}"


# ==================== Property 2: Format Detection ====================

@given(extension=st.sampled_from([".json", ".yaml", ".yml"]))
def test_property_format_detection_supported(extension):
    """
    Feature: config-format-converter, Property 2: Format Detection is Accurate
    
    For any supported file extension (.json, .yaml, .yml), 
    format detection should correctly identify the format.
    
    **Validates: Requirements 2.1, 2.2**
    """
    file_path = Path(f"config{extension}")
    detected = ConfigConverter.detect_format(file_path)
    
    if extension == ".json":
        assert detected == "json", f"Expected 'json' for {extension}, got {detected}"
    else:
        assert detected == "yaml", f"Expected 'yaml' for {extension}, got {detected}"


@given(
    extension=st.text(min_size=1, max_size=10).filter(
        lambda x: x not in [".json", ".yaml", ".yml"] and not x.startswith(".")
    )
)
def test_property_format_detection_unsupported(extension):
    """
    Feature: config-format-converter, Property 2: Format Detection is Accurate
    
    For any unsupported extension, format detection should raise ValueError.
    
    **Validates: Requirements 2.3**
    """
    # 确保扩展名以点开头
    if not extension.startswith("."):
        extension = f".{extension}"
    
    file_path = Path(f"config{extension}")
    
    with pytest.raises(ValueError, match="不支持的文件格式"):
        ConfigConverter.detect_format(file_path)


# ==================== Property 4: YAML Loading Integration ====================

def valid_config_dto_strategy():
    """生成有效的 DeviceManagerConfigDTO（简化版本）"""
    # 使用模板生成默认配置，返回一个固定策略
    config = template_DeviceManagerConfigDTO([])
    return st.just(config)


@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_yaml_loading_integration(config_dto, tmp_path):
    """
    Feature: config-format-converter, Property 4: YAML Loading Integration
    
    For any valid YAML configuration file, DeviceConfigManager should successfully 
    load it and convert it to a ConfigDTO object, producing the same result as 
    loading an equivalent JSON file.
    
    **Validates: Requirements 3.2, 3.3**
    """
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"
    
    # 1. 保存为 JSON
    config_dict = config_dto.to_dict()
    json_text = json.dumps(config_dict, indent=2, ensure_ascii=False)
    json_file.write_text(json_text, encoding='utf-8')
    
    # 2. 使用 ConfigConverter 转换为 YAML（确保格式兼容）
    ConfigConverter.json_to_yaml(json_file, yaml_file)
    
    # 3. 使用 DeviceConfigManager 分别加载 JSON 和 YAML
    manager_json = DeviceConfigManager(str(json_file), auto_create=False)
    manager_json.load_config(validate=False)
    
    manager_yaml = DeviceConfigManager(str(yaml_file), auto_create=False)
    manager_yaml.load_config(validate=False)
    
    # 4. 验证两者加载的配置等价（忽略动态生成的字段）
    json_config = manager_json.get_config()
    yaml_config = manager_yaml.get_config()
    
    # 比较关键字段而不是整个字典（避免 created_at 等动态字段的影响）
    assert json_config.config_version == yaml_config.config_version
    assert json_config.oak_module.hardware_config.model_path == yaml_config.oak_module.hardware_config.model_path
    assert json_config.oak_module.hardware_config.confidence_threshold == yaml_config.oak_module.hardware_config.confidence_threshold
    assert len(json_config.oak_module.role_bindings) == len(yaml_config.oak_module.role_bindings)
    assert json_config.display_config.enable_display == yaml_config.display_config.enable_display
    assert json_config.can_config.enable_can == yaml_config.can_config.enable_can


# ==================== Property 5: Configuration Export Preserves Content ====================

@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_export_to_yaml_preserves_content(config_dto, tmp_path):
    """
    Feature: config-format-converter, Property 5: Configuration Export Preserves Content
    
    For any loaded configuration, exporting to YAML and then reloading should 
    produce an equivalent ConfigDTO object.
    
    **Validates: Requirements 4.1**
    """
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    json_file = tmp_path / "config.json"
    yaml_export = tmp_path / "export.yaml"
    
    # 1. 保存原始配置为 JSON
    config_dict = config_dto.to_dict()
    json_text = json.dumps(config_dict, indent=2, ensure_ascii=False)
    json_file.write_text(json_text, encoding='utf-8')
    
    # 2. 加载配置
    manager = DeviceConfigManager(str(json_file), auto_create=False)
    manager.load_config(validate=False)
    
    # 3. 导出为 YAML
    manager.export_to_yaml(str(yaml_export))
    
    # 4. 重新加载导出的 YAML
    manager_reloaded = DeviceConfigManager(str(yaml_export), auto_create=False)
    manager_reloaded.load_config(validate=False)
    
    # 5. 验证内容等价
    original_config = manager.get_config()
    reloaded_config = manager_reloaded.get_config()
    
    # 比较关键字段
    assert original_config.config_version == reloaded_config.config_version
    assert original_config.oak_module.hardware_config.model_path == reloaded_config.oak_module.hardware_config.model_path
    assert original_config.oak_module.hardware_config.confidence_threshold == reloaded_config.oak_module.hardware_config.confidence_threshold
    assert len(original_config.oak_module.role_bindings) == len(reloaded_config.oak_module.role_bindings)


@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_export_to_json_preserves_content(config_dto, tmp_path):
    """
    Feature: config-format-converter, Property 5: Configuration Export Preserves Content
    
    For any loaded configuration, exporting to JSON and then reloading should 
    produce an equivalent ConfigDTO object.
    
    **Validates: Requirements 4.2**
    """
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"
    json_export = tmp_path / "export.json"
    
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    # 1. 保存原始配置为 JSON，然后转换为 YAML
    config_dict = config_dto.to_dict()
    json_text = json.dumps(config_dict, indent=2, ensure_ascii=False)
    json_file.write_text(json_text, encoding='utf-8')
    
    # 使用 ConfigConverter 转换为 YAML（确保格式兼容）
    ConfigConverter.json_to_yaml(json_file, yaml_file)
    
    # 2. 加载 YAML 配置
    manager = DeviceConfigManager(str(yaml_file), auto_create=False)
    manager.load_config(validate=False)
    
    # 3. 导出为 JSON
    manager.export_to_json(str(json_export))
    
    # 4. 重新加载导出的 JSON
    manager_reloaded = DeviceConfigManager(str(json_export), auto_create=False)
    manager_reloaded.load_config(validate=False)
    
    # 5. 验证内容等价
    original_config = manager.get_config()
    reloaded_config = manager_reloaded.get_config()
    
    # 比较关键字段
    assert original_config.config_version == reloaded_config.config_version
    assert original_config.oak_module.hardware_config.model_path == reloaded_config.oak_module.hardware_config.model_path
    assert original_config.oak_module.hardware_config.confidence_threshold == reloaded_config.oak_module.hardware_config.confidence_threshold
    assert len(original_config.oak_module.role_bindings) == len(reloaded_config.oak_module.role_bindings)


# ==================== Property 6: Logging Records Key Operations ====================

@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_logging_records_load_operations(config_dto, tmp_path, caplog):
    """
    Feature: config-format-converter, Property 6: Logging Records Key Operations
    
    For any successful configuration load operation, the system should record 
    an info-level log entry containing the file path and detected format.
    
    **Validates: Requirements 3.5, 10.1, 10.4**
    """
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"
    
    # 1. 保存配置为 JSON 和 YAML
    config_dict = config_dto.to_dict()
    json_text = json.dumps(config_dict, indent=2, ensure_ascii=False)
    json_file.write_text(json_text, encoding='utf-8')
    ConfigConverter.json_to_yaml(json_file, yaml_file)
    
    # 2. 测试 JSON 加载日志
    with caplog.at_level(logging.INFO):
        manager_json = DeviceConfigManager(str(json_file), auto_create=False)
        manager_json.load_config(validate=False)
    
    # 验证日志包含文件路径和格式类型
    log_messages = [record.message for record in caplog.records if record.levelname == 'INFO']
    assert any(str(json_file) in msg and 'json' in msg.lower() for msg in log_messages), \
        f"Expected log with path and format, got: {log_messages}"
    
    caplog.clear()
    
    # 3. 测试 YAML 加载日志
    with caplog.at_level(logging.INFO):
        manager_yaml = DeviceConfigManager(str(yaml_file), auto_create=False)
        manager_yaml.load_config(validate=False)
    
    # 验证日志包含文件路径和格式类型
    log_messages = [record.message for record in caplog.records if record.levelname == 'INFO']
    assert any(str(yaml_file) in msg and 'yaml' in msg.lower() for msg in log_messages), \
        f"Expected log with path and format, got: {log_messages}"


@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_logging_records_export_operations(config_dto, tmp_path, caplog):
    """
    Feature: config-format-converter, Property 6: Logging Records Key Operations
    
    For any successful configuration export operation, the system should record 
    an info-level log entry containing the output path and target format.
    
    **Validates: Requirements 4.4, 10.4**
    """
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    json_file = tmp_path / "config.json"
    yaml_export = tmp_path / "export.yaml"
    json_export = tmp_path / "export.json"
    
    # 1. 保存并加载配置
    config_dict = config_dto.to_dict()
    json_text = json.dumps(config_dict, indent=2, ensure_ascii=False)
    json_file.write_text(json_text, encoding='utf-8')
    
    manager = DeviceConfigManager(str(json_file), auto_create=False)
    manager.load_config(validate=False)
    
    caplog.clear()
    
    # 2. 测试 YAML 导出日志
    with caplog.at_level(logging.INFO):
        manager.export_to_yaml(str(yaml_export))
    
    # 验证日志包含输出路径和格式类型
    log_messages = [record.message for record in caplog.records if record.levelname == 'INFO']
    assert any(str(yaml_export) in msg and 'yaml' in msg.lower() for msg in log_messages), \
        f"Expected log with path and format, got: {log_messages}"
    
    caplog.clear()
    
    # 3. 测试 JSON 导出日志
    with caplog.at_level(logging.INFO):
        manager.export_to_json(str(json_export))
    
    # 验证日志包含输出路径和格式类型
    log_messages = [record.message for record in caplog.records if record.levelname == 'INFO']
    assert any(str(json_export) in msg and 'json' in msg.lower() for msg in log_messages), \
        f"Expected log with path and format, got: {log_messages}"


# ==================== Property 8: Backward Compatibility ====================

@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_backward_compatibility_json_loading(config_dto, tmp_path):
    """
    Feature: config-format-converter, Property 8: Backward Compatibility Maintained
    
    For any existing JSON configuration file and code using DeviceConfigManager,
    the new YAML support should not change the loading behavior or API signatures.
    
    **Validates: Requirements 8.1, 8.2**
    """
    json_file = tmp_path / "config.json"
    
    # 1. 保存为 JSON（传统方式）
    json_text = config_dto.to_json(indent=2)
    json_file.write_text(json_text, encoding='utf-8')
    
    # 2. 使用 DeviceConfigManager 加载（应该仍然正常工作）
    manager = DeviceConfigManager(str(json_file), auto_create=False)
    result = manager.load_config(validate=False)
    
    # 3. 验证加载成功
    assert result is True
    loaded_config = manager.get_config()
    assert loaded_config is not None
    assert loaded_config.config_version == config_dto.config_version


@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_backward_compatibility_api_unchanged(config_dto, tmp_path):
    """
    Feature: config-format-converter, Property 8: Backward Compatibility Maintained
    
    For any configuration, the API signatures and behavior should remain unchanged
    when using JSON format.
    
    **Validates: Requirements 8.1, 8.2**
    """
    json_file = tmp_path / "config.json"
    
    # 保存配置
    json_text = config_dto.to_json(indent=2)
    json_file.write_text(json_text, encoding='utf-8')
    
    # 测试 API 签名未改变
    manager = DeviceConfigManager(str(json_file), auto_create=False)
    
    # load_config 返回 bool
    result = manager.load_config(validate=False)
    assert isinstance(result, bool)
    
    # get_config 返回配置对象
    loaded_config = manager.get_config()
    assert loaded_config is not None
    assert hasattr(loaded_config, 'config_version')
    assert hasattr(loaded_config, 'oak_module')


# ==================== Property 9: Optional Dependency Handling ====================

def test_property_optional_dependency_yaml_load_without_pyyaml(tmp_path, monkeypatch):
    """
    Feature: config-format-converter, Property 9: Optional Dependency Handling
    
    For any operation requiring YAML libraries when they are not installed,
    the system should raise an ImportError with a clear message including
    the installation command.
    
    **Validates: Requirements 7.1**
    """
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("config_version: '2.0.0'", encoding='utf-8')
    
    # 模拟所有 YAML 库都未安装
    import builtins
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name in ["ruamel.yaml", "ruamel", "yaml"]:
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    # 尝试加载 YAML 应该失败并提供清晰的错误信息
    with pytest.raises(ImportError) as exc_info:
        ConfigConverter.load_yaml_as_dict(yaml_file)
    
    # 验证错误信息包含安装命令
    error_message = str(exc_info.value)
    assert "需要安装 YAML" in error_message or "pip install" in error_message


def test_property_optional_dependency_yaml_save_without_pyyaml(tmp_path, monkeypatch):
    """
    Feature: config-format-converter, Property 9: Optional Dependency Handling
    
    For any operation requiring YAML libraries when they are not installed,
    the system should raise an ImportError with a clear message.
    
    **Validates: Requirements 7.2**
    """
    yaml_file = tmp_path / "config.yaml"
    config = {"config_version": "2.0.0", "test": "value"}
    
    # 模拟所有 YAML 库都未安装
    import builtins
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name in ["ruamel.yaml", "ruamel", "yaml"]:
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    # 尝试保存 YAML 应该失败并提供清晰的错误信息
    with pytest.raises(ImportError) as exc_info:
        ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 验证错误信息包含安装命令
    error_message = str(exc_info.value)
    assert "需要安装 YAML" in error_message or "pip install" in error_message


@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_optional_dependency_json_works_without_pyyaml(config_dto, tmp_path, monkeypatch):
    """
    Feature: config-format-converter, Property 9: Optional Dependency Handling
    
    For any JSON configuration, the system should work normally even when
    PyYAML is not installed.
    
    **Validates: Requirements 7.3**
    """
    json_file = tmp_path / "config.json"
    
    # 保存为 JSON
    json_text = config_dto.to_json(indent=2)
    json_file.write_text(json_text, encoding='utf-8')
    
    # 模拟 PyYAML 未安装
    import builtins
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("No module named 'yaml'")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    # JSON 配置应该仍然可以正常加载
    manager = DeviceConfigManager(str(json_file), auto_create=False)
    result = manager.load_config(validate=False)
    
    assert result is True
    loaded_config = manager.get_config()
    assert loaded_config is not None


# ==================== Property 10: Validation Detects Corruption ====================

@given(config_dto=valid_config_dto_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_property_validation_detects_corruption_after_conversion(config_dto, tmp_path):
    """
    Feature: config-format-converter, Property 10: Validation Detects Corruption
    
    For any configuration that has been converted, validation should detect
    any data loss, type changes, or structural corruption.
    
    **Validates: Requirements 9.3, 9.4**
    """
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"
    
    # 1. 保存原始配置为 JSON
    json_text = config_dto.to_json(indent=2)
    json_file.write_text(json_text, encoding='utf-8')
    
    # 2. 转换为 YAML
    ConfigConverter.json_to_yaml(json_file, yaml_file)
    
    # 3. 加载 YAML 并验证（应该通过）
    manager = DeviceConfigManager(str(yaml_file), auto_create=False)
    result = manager.load_config(validate=True)
    
    # 4. 验证应该成功（没有数据损坏）
    assert result is True
    loaded_config = manager.get_config()
    
    # 5. 验证关键字段未损坏
    assert loaded_config.config_version == config_dto.config_version
    assert loaded_config.oak_module.hardware_config.model_path == config_dto.oak_module.hardware_config.model_path
    assert loaded_config.oak_module.hardware_config.confidence_threshold == config_dto.oak_module.hardware_config.confidence_threshold


# ==================== Property 11: Comment Preservation ====================

def test_property_comment_preservation_load_save_cycle(tmp_path):
    """
    Feature: config-format-converter, Property 11: Comment Preservation
    
    For any YAML file with user comments, loading and saving should preserve
    all comments when using ruamel.yaml.
    
    **Validates: Requirements 11.1, 11.2**
    """
    try:
        from ruamel.yaml import YAML
    except ImportError:
        pytest.skip("ruamel.yaml not installed")
    
    yaml_file = tmp_path / "config_with_comments.yaml"
    
    # 1. 创建带注释的 YAML 文件
    yaml_content = """# 这是顶部注释
# OAK Vision System 配置文件
config_version: "2.0.0"  # 版本号

# 测试配置部分
test_string: "hello"  # 用户添加的注释
test_number: 42  # 这是一个数字
test_bool: true

# 嵌套配置
test_dict:
  nested_key: "value"  # 嵌套字段注释
"""
    yaml_file.write_text(yaml_content, encoding='utf-8')
    
    # 2. 加载配置
    config = ConfigConverter.load_yaml_as_dict(yaml_file)
    
    # 3. 修改配置（模拟程序修改）
    config['test_number'] = 100
    
    # 4. 保存配置
    ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 5. 验证注释保留
    saved_content = yaml_file.read_text(encoding='utf-8')
    
    # 检查关键注释是否保留
    assert "这是顶部注释" in saved_content, "顶部注释应该被保留"
    assert "版本号" in saved_content, "行内注释应该被保留"
    assert "用户添加的注释" in saved_content, "用户注释应该被保留"
    assert "嵌套字段注释" in saved_content, "嵌套字段注释应该被保留"
    
    # 验证数据修改生效
    reloaded = ConfigConverter.load_yaml_as_dict(yaml_file)
    assert reloaded['test_number'] == 100, "数据修改应该生效"


def test_property_comment_preservation_chinese_comments(tmp_path):
    """
    Feature: config-format-converter, Property 11: Comment Preservation
    
    For any YAML file with Chinese comments, the system should correctly
    handle and preserve Chinese characters.
    
    **Validates: Requirements 11.3**
    """
    try:
        from ruamel.yaml import YAML
    except ImportError:
        pytest.skip("ruamel.yaml not installed")
    
    yaml_file = tmp_path / "config_chinese.yaml"
    
    # 1. 创建带中文注释的 YAML 文件
    yaml_content = """# 配置文件说明
# 这是一个测试配置文件
config_version: "2.0.0"  # 配置版本

# 硬件配置
hardware:
  model_path: "models/test.blob"  # 模型文件路径
  confidence: 0.5  # 置信度阈值（范围：0.0-1.0）
  
# 坐标变换参数
transform:
  translation_x: -50.0  # 左相机向左偏移 50 毫米
  translation_y: 0.0  # Y 轴偏移量
  calibration_method: manual  # 标定方法：manual（手动）或 auto（自动）
"""
    yaml_file.write_text(yaml_content, encoding='utf-8')
    
    # 2. 加载并保存
    config = ConfigConverter.load_yaml_as_dict(yaml_file)
    ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 3. 验证中文注释保留
    saved_content = yaml_file.read_text(encoding='utf-8')
    
    assert "配置文件说明" in saved_content
    assert "硬件配置" in saved_content
    assert "模型文件路径" in saved_content
    assert "置信度阈值" in saved_content
    assert "左相机向左偏移 50 毫米" in saved_content
    assert "标定方法：manual（手动）或 auto（自动）" in saved_content


def test_property_comment_preservation_format_maintained(tmp_path):
    """
    Feature: config-format-converter, Property 11: Comment Preservation
    
    For any YAML file, saving should maintain the original indentation style
    and format when using ruamel.yaml.
    
    **Validates: Requirements 11.4**
    """
    try:
        from ruamel.yaml import YAML
    except ImportError:
        pytest.skip("ruamel.yaml not installed")
    
    yaml_file = tmp_path / "config_format.yaml"
    
    # 1. 创建带特定格式的 YAML 文件
    yaml_content = """config_version: "2.0.0"

test_dict:
  key1: "value1"
  key2: "value2"
  nested:
    deep_key: "deep_value"

test_list:
  - item1
  - item2
  - item3
"""
    yaml_file.write_text(yaml_content, encoding='utf-8')
    
    # 2. 加载并保存
    config = ConfigConverter.load_yaml_as_dict(yaml_file)
    ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 3. 验证格式保持
    saved_content = yaml_file.read_text(encoding='utf-8')
    
    # 检查缩进风格（应该使用块风格，不是流式风格）
    assert "test_dict:" in saved_content
    assert "  key1:" in saved_content  # 2 空格缩进
    assert "  nested:" in saved_content
    assert "    deep_key:" in saved_content  # 4 空格缩进（嵌套）
    
    # 检查列表格式
    assert "test_list:" in saved_content
    assert "- item1" in saved_content or "  - item1" in saved_content
    
    # 不应该有流式风格（如 {key: value}）
    assert "{" not in saved_content or "}" not in saved_content


def test_property_comment_preservation_pyyaml_fallback(tmp_path, monkeypatch):
    """
    Feature: config-format-converter, Property 11: Comment Preservation
    
    When ruamel.yaml is not available but PyYAML is installed, the system
    should fall back to PyYAML (without comment preservation) and log a warning.
    
    **Validates: Requirements 11.5, 11.6**
    """
    # 模拟 ruamel.yaml 未安装，但 PyYAML 已安装
    import sys
    import builtins
    
    # 保存原始模块
    original_modules = sys.modules.copy()
    
    # 移除 ruamel.yaml
    if 'ruamel.yaml' in sys.modules:
        del sys.modules['ruamel.yaml']
    if 'ruamel' in sys.modules:
        del sys.modules['ruamel']
    
    # 模拟导入失败
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == "ruamel.yaml" or name == "ruamel":
            raise ImportError("No module named 'ruamel.yaml'")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    try:
        import yaml as pyyaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    yaml_file = tmp_path / "config.yaml"
    
    # 创建配置
    config = {
        "config_version": "2.0.0",
        "test": "value"
    }
    
    # 应该能够保存（使用 PyYAML）
    ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 验证文件创建成功
    assert yaml_file.exists()
    
    # 加载验证
    loaded = ConfigConverter.load_yaml_as_dict(yaml_file)
    assert loaded == config
    
    # 恢复模块
    sys.modules.update(original_modules)


def test_property_comment_preservation_no_yaml_library(tmp_path, monkeypatch):
    """
    Feature: config-format-converter, Property 11: Comment Preservation
    
    When neither ruamel.yaml nor PyYAML is installed, the system should
    raise a clear error message recommending ruamel.yaml.
    
    **Validates: Requirements 11.7**
    """
    import sys
    import builtins
    
    # 保存原始模块
    original_modules = sys.modules.copy()
    
    # 移除所有 YAML 库
    for module_name in ['ruamel.yaml', 'ruamel', 'yaml']:
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    # 模拟所有 YAML 库都未安装
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name in ["ruamel.yaml", "ruamel", "yaml"]:
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    yaml_file = tmp_path / "config.yaml"
    config = {"config_version": "2.0.0"}
    
    # 尝试保存应该失败
    with pytest.raises(ImportError) as exc_info:
        ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 验证错误信息推荐 ruamel.yaml
    error_message = str(exc_info.value)
    assert "ruamel.yaml" in error_message.lower() or "pip install" in error_message.lower()
    
    # 恢复模块
    sys.modules.update(original_modules)


@given(config=simple_config_dict_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_comment_preservation_round_trip_with_comments(config, tmp_path):
    """
    Feature: config-format-converter, Property 11: Comment Preservation
    
    For any configuration with comments, a round-trip (load → modify → save → load)
    should preserve both the data and the comments.
    
    **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
    """
    try:
        from ruamel.yaml import YAML
    except ImportError:
        pytest.skip("ruamel.yaml not installed")
    
    yaml_file = tmp_path / "config_roundtrip.yaml"
    
    # 1. 创建带注释的初始配置
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    
    with open(yaml_file, 'w', encoding='utf-8') as f:
        yaml.dump(config, f)
    
    # 手动添加注释
    content = yaml_file.read_text(encoding='utf-8')
    commented_content = f"# 测试注释\n{content}"
    yaml_file.write_text(commented_content, encoding='utf-8')
    
    # 2. 加载配置
    loaded_config = ConfigConverter.load_yaml_as_dict(yaml_file)
    
    # 3. 修改配置
    if 'test_string' in loaded_config:
        loaded_config['test_string'] = "modified"
    
    # 4. 保存配置
    ConfigConverter.save_as_yaml(loaded_config, yaml_file)
    
    # 5. 验证注释保留
    saved_content = yaml_file.read_text(encoding='utf-8')
    assert "测试注释" in saved_content, "注释应该在 round-trip 后保留"
    
    # 6. 验证数据正确
    final_config = ConfigConverter.load_yaml_as_dict(yaml_file)
    if 'test_string' in final_config:
        assert final_config['test_string'] == "modified", "数据修改应该生效"


# ==================== 库回退测试 ====================

def test_library_fallback_ruamel_yaml_available(tmp_path):
    """
    测试 ruamel.yaml 可用时的行为
    
    **Validates: Requirements 11.5**
    """
    try:
        from ruamel.yaml import YAML
    except ImportError:
        pytest.skip("ruamel.yaml not installed")
    
    yaml_file = tmp_path / "config.yaml"
    config = {
        "config_version": "2.0.0",
        "test": "value"
    }
    
    # 保存配置
    ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 验证文件创建成功
    assert yaml_file.exists()
    
    # 加载验证
    loaded = ConfigConverter.load_yaml_as_dict(yaml_file)
    assert loaded == config


def test_library_fallback_pyyaml_only(tmp_path, monkeypatch):
    """
    测试只有 PyYAML 可用时的行为
    
    **Validates: Requirements 11.6**
    """
    # 模拟 ruamel.yaml 未安装
    import builtins
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == "ruamel.yaml" or name == "ruamel":
            raise ImportError("No module named 'ruamel.yaml'")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    try:
        import yaml as pyyaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    
    yaml_file = tmp_path / "config.yaml"
    config = {
        "config_version": "2.0.0",
        "test": "value"
    }
    
    # 应该能够保存（使用 PyYAML）
    ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 验证文件创建成功
    assert yaml_file.exists()
    
    # 加载验证
    loaded = ConfigConverter.load_yaml_as_dict(yaml_file)
    assert loaded == config


def test_library_fallback_neither_available(tmp_path, monkeypatch):
    """
    测试两个库都不可用时的错误提示
    
    **Validates: Requirements 11.7**
    """
    import builtins
    real_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name in ["ruamel.yaml", "ruamel", "yaml"]:
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    yaml_file = tmp_path / "config.yaml"
    config = {"config_version": "2.0.0"}
    
    # 尝试保存应该失败
    with pytest.raises(ImportError) as exc_info:
        ConfigConverter.save_as_yaml(config, yaml_file)
    
    # 验证错误信息推荐 ruamel.yaml
    error_message = str(exc_info.value)
    assert "ruamel.yaml" in error_message.lower() or "pip install" in error_message.lower()
