"""
DeviceConfigManager YAML 支持集成测试

测试端到端的 YAML 支持、向后兼容性和配置验证集成。

测试范围：
- 端到端 YAML 支持
- 向后兼容性
- 配置验证集成
"""

import pytest
import json
from pathlib import Path

from oak_vision_system.modules.config_manager.device_config_manager import (
    DeviceConfigManager,
    ConfigValidationError,
    ConfigNotFoundError
)
from oak_vision_system.modules.config_manager.config_converter import ConfigConverter
from oak_vision_system.core.config import template_DeviceManagerConfigDTO


class TestEndToEndYAMLSupport:
    """测试端到端 YAML 支持 - Requirements 8.1, 8.2, 9.1"""
    
    def test_complete_yaml_workflow(self, tmp_path):
        """测试完整的 YAML 工作流程"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "config.yaml"
        yaml_export = tmp_path / "export.yaml"
        
        # 1. 创建初始 JSON 配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        # 2. 转换为 YAML
        ConfigConverter.json_to_yaml(json_file, yaml_file)
        
        # 3. 加载 YAML 配置
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        manager.load_config(validate=False)
        
        # 4. 修改配置（模拟用户操作）
        loaded_config = manager.get_config()
        assert loaded_config is not None
        
        # 5. 导出为新的 YAML 文件
        manager.export_to_yaml(str(yaml_export))
        
        # 6. 验证导出的文件可以被重新加载
        manager_reloaded = DeviceConfigManager(str(yaml_export), auto_create=False)
        manager_reloaded.load_config(validate=False)
        reloaded_config = manager_reloaded.get_config()
        
        # 7. 验证配置内容一致
        assert loaded_config.config_version == reloaded_config.config_version
        assert loaded_config.oak_module.hardware_config.model_path == reloaded_config.oak_module.hardware_config.model_path
    
    def test_yaml_to_json_to_yaml_workflow(self, tmp_path):
        """测试 YAML → JSON → YAML 工作流程"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml1 = tmp_path / "config1.yaml"
        json_export = tmp_path / "export.json"
        yaml2 = tmp_path / "config2.yaml"
        
        # 1. 创建初始配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        ConfigConverter.json_to_yaml(json_file, yaml1)
        
        # 2. 加载 YAML
        manager1 = DeviceConfigManager(str(yaml1), auto_create=False)
        manager1.load_config(validate=False)
        
        # 3. 导出为 JSON
        manager1.export_to_json(str(json_export))
        
        # 4. 加载 JSON
        manager2 = DeviceConfigManager(str(json_export), auto_create=False)
        manager2.load_config(validate=False)
        
        # 5. 导出为 YAML
        manager2.export_to_yaml(str(yaml2))
        
        # 6. 验证最终 YAML 可以加载
        manager3 = DeviceConfigManager(str(yaml2), auto_create=False)
        manager3.load_config(validate=False)
        final_config = manager3.get_config()
        
        assert final_config.config_version == config.config_version


class TestBackwardCompatibility:
    """测试向后兼容性 - Requirements 8.1, 8.2, 8.3"""
    
    def test_existing_json_config_still_works(self, tmp_path):
        """测试现有 JSON 配置仍然正常工作"""
        json_file = tmp_path / "config.json"
        
        # 1. 创建传统 JSON 配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        # 2. 使用现有方式加载
        manager = DeviceConfigManager(str(json_file), auto_create=False)
        result = manager.load_config(validate=False)
        
        # 3. 验证加载成功
        assert result is True
        loaded_config = manager.get_config()
        assert loaded_config is not None
        assert loaded_config.config_version == config.config_version
    
    def test_json_default_behavior_unchanged(self, tmp_path):
        """测试 JSON 默认行为未改变"""
        json_file = tmp_path / "config.json"
        
        # 创建配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        # 加载配置（不指定格式）
        manager = DeviceConfigManager(str(json_file), auto_create=False)
        manager.load_config(validate=False)
        
        # 验证配置正确加载
        loaded_config = manager.get_config()
        assert loaded_config.config_version == config.config_version
    
    def test_api_signatures_unchanged(self, tmp_path):
        """测试 API 签名未改变"""
        json_file = tmp_path / "config.json"
        
        # 创建配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        # 测试现有 API 仍然可用
        manager = DeviceConfigManager(str(json_file), auto_create=False)
        
        # load_config 方法签名未改变
        result = manager.load_config(validate=False)
        assert isinstance(result, bool)
        
        # get_config 方法仍然可用
        loaded_config = manager.get_config()
        assert loaded_config is not None
        
        # 验证配置内容正确
        assert loaded_config.config_version == config.config_version
    
    def test_mixed_format_usage(self, tmp_path):
        """测试混合使用 JSON 和 YAML 格式"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "config.yaml"
        
        # 1. 创建 JSON 配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        # 2. 加载 JSON
        manager_json = DeviceConfigManager(str(json_file), auto_create=False)
        manager_json.load_config(validate=False)
        
        # 3. 导出为 YAML
        manager_json.export_to_yaml(str(yaml_file))
        
        # 4. 加载 YAML
        manager_yaml = DeviceConfigManager(str(yaml_file), auto_create=False)
        manager_yaml.load_config(validate=False)
        
        # 5. 验证两者等价
        json_config = manager_json.get_config()
        yaml_config = manager_yaml.get_config()
        
        assert json_config.config_version == yaml_config.config_version
        assert json_config.oak_module.hardware_config.model_path == yaml_config.oak_module.hardware_config.model_path


class TestConfigValidationIntegration:
    """测试配置验证集成 - Requirements 9.1, 9.4"""
    
    def test_yaml_config_validation(self, tmp_path):
        """测试 YAML 配置验证"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "config.yaml"
        
        # 1. 创建有效配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        ConfigConverter.json_to_yaml(json_file, yaml_file)
        
        # 2. 加载并验证 YAML 配置
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        result = manager.load_config(validate=True)  # 启用验证
        
        # 3. 验证成功
        assert result is True
        loaded_config = manager.get_config()
        assert loaded_config is not None
    
    def test_invalid_yaml_config_validation_fails(self, tmp_path):
        """测试无效 YAML 配置验证失败"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        yaml_file = tmp_path / "invalid.yaml"
        
        # 创建格式错误的 YAML（而不是结构不完整的配置）
        yaml_file.write_text("invalid: yaml: [unclosed", encoding='utf-8')
        
        # 尝试加载应该失败
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        
        # YAML 解析错误应该被捕获
        with pytest.raises((ConfigValidationError, yaml.YAMLError)):
            manager.load_config()
    
    def test_yaml_export_validation(self, tmp_path):
        """测试 YAML 导出后的验证"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml_export = tmp_path / "export.yaml"
        
        # 1. 创建并加载配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        manager = DeviceConfigManager(str(json_file), auto_create=False)
        manager.load_config(validate=False)
        
        # 2. 导出为 YAML
        manager.export_to_yaml(str(yaml_export))
        
        # 3. 重新加载并验证
        manager_reloaded = DeviceConfigManager(str(yaml_export), auto_create=False)
        result = manager_reloaded.load_config(validate=True)  # 启用验证
        
        # 4. 验证成功
        assert result is True
    
    def test_json_yaml_validation_equivalence(self, tmp_path):
        """测试 JSON 和 YAML 验证结果等价"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "config.yaml"
        
        # 1. 创建配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        ConfigConverter.json_to_yaml(json_file, yaml_file)
        
        # 2. 分别加载并验证 JSON 和 YAML
        manager_json = DeviceConfigManager(str(json_file), auto_create=False)
        result_json = manager_json.load_config(validate=True)
        
        manager_yaml = DeviceConfigManager(str(yaml_file), auto_create=False)
        result_yaml = manager_yaml.load_config(validate=True)
        
        # 3. 验证结果应该相同
        assert result_json == result_yaml
        assert result_json is True


class TestErrorHandlingIntegration:
    """测试错误处理集成"""
    
    def test_yaml_parse_error_handling(self, tmp_path):
        """测试 YAML 解析错误处理"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        yaml_file = tmp_path / "malformed.yaml"
        
        # 创建格式错误的 YAML
        yaml_file.write_text("invalid: yaml: [unclosed", encoding='utf-8')
        
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        
        # 应该抛出清晰的错误
        with pytest.raises((ConfigValidationError, yaml.YAMLError)):
            manager.load_config()
    
    def test_yaml_file_not_found_handling(self, tmp_path):
        """测试 YAML 文件不存在错误处理"""
        yaml_file = tmp_path / "nonexistent.yaml"
        
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        
        with pytest.raises(ConfigNotFoundError):
            manager.load_config()
    
    def test_export_without_config_handling(self, tmp_path):
        """测试未加载配置时导出错误处理"""
        yaml_export = tmp_path / "export.yaml"
        json_export = tmp_path / "export.json"
        
        manager = DeviceConfigManager(str(tmp_path / "dummy.json"), auto_create=False)
        
        # 未加载配置时导出应该失败
        with pytest.raises(ConfigValidationError, match="当前无可运行配置可导出，请先加载或创建配置"):
            manager.export_to_yaml(str(yaml_export))
        
        with pytest.raises(ConfigValidationError, match="当前无可运行配置可导出，请先加载或创建配置"):
            manager.export_to_json(str(json_export))
