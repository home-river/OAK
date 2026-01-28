"""
ConfigConverter 单元测试

测试配置格式转换器的基本功能和错误处理。
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch

from oak_vision_system.modules.config_manager.config_converter import ConfigConverter


class TestFormatDetection:
    """测试格式检测功能"""
    
    def test_detect_json_format(self):
        """测试 JSON 格式检测"""
        assert ConfigConverter.detect_format(Path("config.json")) == "json"
    
    def test_detect_yaml_format(self):
        """测试 YAML 格式检测"""
        assert ConfigConverter.detect_format(Path("config.yaml")) == "yaml"
        assert ConfigConverter.detect_format(Path("config.yml")) == "yaml"
    
    def test_detect_unsupported_format(self):
        """测试不支持的格式"""
        with pytest.raises(ValueError, match="不支持的文件格式"):
            ConfigConverter.detect_format(Path("config.txt"))
        
        with pytest.raises(ValueError, match="不支持的文件格式"):
            ConfigConverter.detect_format(Path("config.xml"))


class TestJSONToYAML:
    """测试 JSON 到 YAML 转换"""
    
    def test_basic_conversion(self, tmp_path):
        """测试基本转换功能"""
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "config.yaml"
        
        # 创建测试 JSON
        config = {"config_version": "2.0.0", "test": "value"}
        json_file.write_text(json.dumps(config), encoding='utf-8')
        
        # 转换
        ConfigConverter.json_to_yaml(json_file, yaml_file)
        
        # 验证
        assert yaml_file.exists()
        
        # 验证内容
        try:
            import yaml
            loaded = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
            assert loaded == config
        except ImportError:
            pytest.skip("PyYAML not installed")
    
    def test_file_not_found(self, tmp_path):
        """测试文件不存在错误 - Requirements 1.3"""
        json_file = tmp_path / "nonexistent.json"
        yaml_file = tmp_path / "output.yaml"
        
        with pytest.raises(FileNotFoundError, match="配置文件不存在"):
            ConfigConverter.json_to_yaml(json_file, yaml_file)
    
    def test_invalid_json(self, tmp_path):
        """测试无效 JSON 格式 - Requirements 1.3"""
        json_file = tmp_path / "invalid.json"
        yaml_file = tmp_path / "output.yaml"
        
        # 创建无效 JSON
        json_file.write_text("{invalid json}", encoding='utf-8')
        
        with pytest.raises(json.JSONDecodeError):
            ConfigConverter.json_to_yaml(json_file, yaml_file)
    
    def test_pyyaml_not_installed(self, tmp_path, monkeypatch):
        """测试 PyYAML 未安装错误 - Requirements 7.1"""
        json_file = tmp_path / "config.json"
        yaml_file = tmp_path / "output.yaml"
        
        # 创建测试 JSON
        config = {"test": "value"}
        json_file.write_text(json.dumps(config), encoding='utf-8')
        
        # 模拟 PyYAML 和 ruamel.yaml 都未安装
        import builtins
        real_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name in ["yaml", "ruamel.yaml", "ruamel"]:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)
        
        monkeypatch.setattr(builtins, "__import__", mock_import)
        
        with pytest.raises(ImportError, match="需要安装 YAML 库"):
            ConfigConverter.json_to_yaml(json_file, yaml_file)


class TestYAMLToJSON:
    """测试 YAML 到 JSON 转换"""
    
    def test_basic_conversion(self, tmp_path):
        """测试基本转换功能"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        yaml_file = tmp_path / "config.yaml"
        json_file = tmp_path / "config.json"
        
        # 创建测试 YAML
        config = {"config_version": "2.0.0", "test": "value"}
        yaml_file.write_text(yaml.dump(config), encoding='utf-8')
        
        # 转换
        ConfigConverter.yaml_to_json(yaml_file, json_file)
        
        # 验证
        assert json_file.exists()
        loaded = json.loads(json_file.read_text(encoding='utf-8'))
        assert loaded == config
    
    def test_file_not_found(self, tmp_path):
        """测试文件不存在错误 - Requirements 1.3"""
        yaml_file = tmp_path / "nonexistent.yaml"
        json_file = tmp_path / "output.json"
        
        with pytest.raises(FileNotFoundError, match="配置文件不存在"):
            ConfigConverter.yaml_to_json(yaml_file, json_file)
    
    def test_pyyaml_not_installed(self, tmp_path, monkeypatch):
        """测试 PyYAML 未安装错误 - Requirements 7.2"""
        yaml_file = tmp_path / "config.yaml"
        json_file = tmp_path / "output.json"
        
        # 创建测试文件
        yaml_file.write_text("test: value", encoding='utf-8')
        
        # 模拟 PyYAML 和 ruamel.yaml 都未安装
        import builtins
        real_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name in ["yaml", "ruamel.yaml", "ruamel"]:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)
        
        monkeypatch.setattr(builtins, "__import__", mock_import)
        
        with pytest.raises(ImportError, match="需要安装 YAML 库"):
            ConfigConverter.yaml_to_json(yaml_file, json_file)


class TestHelperMethods:
    """测试辅助方法"""
    
    def test_load_yaml_as_dict(self, tmp_path):
        """测试加载 YAML 为字典"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        yaml_file = tmp_path / "config.yaml"
        config = {"config_version": "2.0.0", "test": "value"}
        yaml_file.write_text(yaml.dump(config), encoding='utf-8')
        
        loaded = ConfigConverter.load_yaml_as_dict(yaml_file)
        assert loaded == config
    
    def test_save_as_yaml(self, tmp_path):
        """测试保存字典为 YAML"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        yaml_file = tmp_path / "config.yaml"
        config = {"config_version": "2.0.0", "test": "value"}
        
        ConfigConverter.save_as_yaml(config, yaml_file)
        
        assert yaml_file.exists()
        loaded = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
        assert loaded == config
    
    def test_load_yaml_pyyaml_not_installed(self, tmp_path, monkeypatch):
        """测试加载 YAML 时所有 YAML 库都未安装 - Requirements 7.1"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("test: value", encoding='utf-8')
        
        # 模拟所有 YAML 库都未安装
        import builtins
        real_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name in ["ruamel.yaml", "ruamel", "yaml"]:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)
        
        monkeypatch.setattr(builtins, "__import__", mock_import)
        
        with pytest.raises(ImportError, match="需要安装 YAML"):
            ConfigConverter.load_yaml_as_dict(yaml_file)
    
    def test_save_yaml_pyyaml_not_installed(self, tmp_path, monkeypatch):
        """测试保存 YAML 时所有 YAML 库都未安装 - Requirements 7.2"""
        yaml_file = tmp_path / "config.yaml"
        config = {"test": "value"}
        
        # 模拟所有 YAML 库都未安装
        import builtins
        real_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name in ["ruamel.yaml", "ruamel", "yaml"]:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)
        
        monkeypatch.setattr(builtins, "__import__", mock_import)
        
        with pytest.raises(ImportError, match="需要安装 YAML"):
            ConfigConverter.save_as_yaml(config, yaml_file)
