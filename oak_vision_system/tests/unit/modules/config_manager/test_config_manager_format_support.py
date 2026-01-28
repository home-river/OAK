"""
DeviceConfigManager 格式支持测试

测试 DeviceConfigManager 对 YAML 和 JSON 格式的支持。

测试范围：
- YAML 配置加载
- 配置导出功能（YAML 和 JSON）
- 错误处理
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
from oak_vision_system.utils import template_DeviceManagerConfigDTO


class TestYAMLConfigLoading:
    """测试 YAML 配置加载功能 - Requirements 3.1, 3.2"""
    
    def test_load_yaml_config_basic(self, tmp_path):
        """测试基本 YAML 配置加载"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "config.yaml"
        
        # 1. 创建有效的配置并保存为 JSON
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        # 2. 使用 ConfigConverter 转换为 YAML（确保格式兼容）
        ConfigConverter.json_to_yaml(json_file, yaml_file)
        
        # 3. 使用 DeviceConfigManager 加载
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        result = manager.load_config(validate=False)
        
        # 4. 验证加载成功
        assert result is True
        loaded_config = manager.get_config()
        assert loaded_config is not None
        assert loaded_config.config_version == config.config_version
    
    def test_load_yaml_config_auto_detection(self, tmp_path):
        """测试 YAML 格式自动检测 - Requirements 3.2"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "config.yaml"
        
        # 创建配置并保存为 JSON
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        # 使用 ConfigConverter 转换为 YAML
        ConfigConverter.json_to_yaml(json_file, yaml_file)
        
        # 加载时应该自动检测为 YAML 格式
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        manager.load_config(validate=False)
        
        # 验证配置已正确加载
        loaded_config = manager.get_config()
        assert loaded_config.config_version == config.config_version
    
    def test_load_yaml_config_with_yml_extension(self, tmp_path):
        """测试 .yml 扩展名支持 - Requirements 3.2"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yml_file = tmp_path / "config.yml"
        
        # 创建配置并保存为 JSON
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        # 使用 ConfigConverter 转换为 YAML
        ConfigConverter.json_to_yaml(json_file, yml_file)
        
        # 加载 .yml 文件
        manager = DeviceConfigManager(str(yml_file), auto_create=False)
        manager.load_config(validate=False)
        
        # 验证配置已正确加载
        loaded_config = manager.get_config()
        assert loaded_config is not None
    
    def test_yaml_json_equivalence(self, tmp_path):
        """测试 YAML 和 JSON 加载结果等价 - Requirements 3.3"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "config.yaml"
        
        # 1. 创建配置并保存为 JSON
        config = template_DeviceManagerConfigDTO([])
        config_dict = config.to_dict()
        json_file.write_text(json.dumps(config_dict, indent=2), encoding='utf-8')
        
        # 2. 转换为 YAML
        ConfigConverter.json_to_yaml(json_file, yaml_file)
        
        # 3. 分别加载 JSON 和 YAML
        manager_json = DeviceConfigManager(str(json_file), auto_create=False)
        manager_json.load_config(validate=False)
        
        manager_yaml = DeviceConfigManager(str(yaml_file), auto_create=False)
        manager_yaml.load_config(validate=False)
        
        # 4. 验证两者等价
        json_config = manager_json.get_config()
        yaml_config = manager_yaml.get_config()
        
        assert json_config.config_version == yaml_config.config_version
        assert json_config.oak_module.hardware_config.model_path == yaml_config.oak_module.hardware_config.model_path
        assert json_config.oak_module.hardware_config.confidence_threshold == yaml_config.oak_module.hardware_config.confidence_threshold


class TestConfigExport:
    """测试配置导出功能 - Requirements 4.1, 4.2"""
    
    def test_export_to_yaml_basic(self, tmp_path):
        """测试基本 YAML 导出功能"""
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
        
        # 3. 验证文件存在且可解析
        assert yaml_export.exists()
        loaded = yaml.safe_load(yaml_export.read_text(encoding='utf-8'))
        assert loaded is not None
        assert "config_version" in loaded
    
    def test_export_to_json_basic(self, tmp_path):
        """测试基本 JSON 导出功能"""
        json_file = tmp_path / "config.json"
        json_export = tmp_path / "export.json"
        
        # 1. 创建并加载配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        manager = DeviceConfigManager(str(json_file), auto_create=False)
        manager.load_config(validate=False)
        
        # 2. 导出为 JSON
        manager.export_to_json(str(json_export))
        
        # 3. 验证文件存在且可解析
        assert json_export.exists()
        loaded = json.loads(json_export.read_text(encoding='utf-8'))
        assert loaded is not None
        assert "config_version" in loaded
    
    def test_export_yaml_without_loaded_config(self, tmp_path):
        """测试未加载配置时导出 YAML 失败 - Requirements 4.3"""
        yaml_export = tmp_path / "export.yaml"
        
        # 创建管理器但不加载配置
        manager = DeviceConfigManager(str(tmp_path / "nonexistent.json"), auto_create=False)
        
        # 尝试导出应该失败
        with pytest.raises(ConfigValidationError, match="当前无可运行配置可导出"):
            manager.export_to_yaml(str(yaml_export))
    
    def test_export_json_without_loaded_config(self, tmp_path):
        """测试未加载配置时导出 JSON 失败 - Requirements 4.3"""
        json_export = tmp_path / "export.json"
        
        # 创建管理器但不加载配置
        manager = DeviceConfigManager(str(tmp_path / "nonexistent.json"), auto_create=False)
        
        # 尝试导出应该失败
        with pytest.raises(ConfigValidationError, match="当前无可运行配置可导出"):
            manager.export_to_json(str(json_export))
    
    def test_export_yaml_preserves_content(self, tmp_path):
        """测试 YAML 导出保持内容完整性"""
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
        original_config = manager.get_config()
        
        # 2. 导出为 YAML
        manager.export_to_yaml(str(yaml_export))
        
        # 3. 重新加载导出的 YAML
        manager_reloaded = DeviceConfigManager(str(yaml_export), auto_create=False)
        manager_reloaded.load_config(validate=False)
        reloaded_config = manager_reloaded.get_config()
        
        # 4. 验证内容等价
        assert original_config.config_version == reloaded_config.config_version
        assert original_config.oak_module.hardware_config.model_path == reloaded_config.oak_module.hardware_config.model_path
        assert original_config.oak_module.hardware_config.confidence_threshold == reloaded_config.oak_module.hardware_config.confidence_threshold
    
    def test_export_json_preserves_content(self, tmp_path):
        """测试 JSON 导出保持内容完整性"""
        json_file = tmp_path / "config.json"
        json_export = tmp_path / "export.json"
        
        # 1. 创建并加载配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        manager = DeviceConfigManager(str(json_file), auto_create=False)
        manager.load_config(validate=False)
        original_config = manager.get_config()
        
        # 2. 导出为 JSON
        manager.export_to_json(str(json_export))
        
        # 3. 重新加载导出的 JSON
        manager_reloaded = DeviceConfigManager(str(json_export), auto_create=False)
        manager_reloaded.load_config(validate=False)
        reloaded_config = manager_reloaded.get_config()
        
        # 4. 验证内容等价
        assert original_config.config_version == reloaded_config.config_version
        assert original_config.oak_module.hardware_config.model_path == reloaded_config.oak_module.hardware_config.model_path
        assert original_config.oak_module.hardware_config.confidence_threshold == reloaded_config.oak_module.hardware_config.confidence_threshold


class TestErrorHandling:
    """测试错误处理 - Requirements 3.4, 7.1, 7.2"""
    
    def test_yaml_file_not_found(self, tmp_path):
        """测试 YAML 文件不存在错误"""
        yaml_file = tmp_path / "nonexistent.yaml"
        
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        
        with pytest.raises(ConfigNotFoundError):
            manager.load_config()
    
    def test_invalid_yaml_format(self, tmp_path):
        """测试无效 YAML 格式错误"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        yaml_file = tmp_path / "invalid.yaml"
        
        # 创建无效的 YAML
        yaml_file.write_text("invalid: yaml: content: [", encoding='utf-8')
        
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        
        with pytest.raises((ConfigValidationError, yaml.YAMLError)):
            manager.load_config()
    
    def test_pyyaml_not_installed_load(self, tmp_path, monkeypatch):
        """测试加载 YAML 时 PyYAML 未安装 - Requirements 7.1"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("config_version: '2.0.0'", encoding='utf-8')
        
        # 模拟 PyYAML 未安装
        import builtins
        real_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)
        
        monkeypatch.setattr(builtins, "__import__", mock_import)
        
        manager = DeviceConfigManager(str(yaml_file), auto_create=False)
        
        with pytest.raises(ImportError, match="需要安装 PyYAML"):
            manager.load_config()
    
    def test_pyyaml_not_installed_export(self, tmp_path, monkeypatch):
        """测试导出 YAML 时 PyYAML 未安装 - Requirements 7.2"""
        json_file = tmp_path / "config.json"
        yaml_export = tmp_path / "export.yaml"
        
        # 创建并加载配置
        config = template_DeviceManagerConfigDTO([])
        json_file.write_text(config.to_json(indent=2), encoding='utf-8')
        
        manager = DeviceConfigManager(str(json_file), auto_create=False)
        manager.load_config(validate=False)
        
        # 模拟 PyYAML 未安装
        import builtins
        real_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)
        
        monkeypatch.setattr(builtins, "__import__", mock_import)
        
        with pytest.raises(ImportError, match="需要安装 PyYAML"):
            manager.export_to_yaml(str(yaml_export))
