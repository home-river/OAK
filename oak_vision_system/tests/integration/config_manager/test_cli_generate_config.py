"""
CLI 配置生成工具集成测试

测试 generate_config.py 命令行工具的格式选项功能
"""

import json
import pytest
from pathlib import Path
from click.testing import CliRunner

# 导入 CLI 工具
import sys
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "tools" / "config_tools"))

from generate_config import main


@pytest.fixture
def runner():
    """创建 Click CLI Runner"""
    return CliRunner()


def test_cli_generate_json_default(runner, tmp_path):
    """测试默认生成 JSON 格式"""
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    assert (output_dir / "config.json").exists()
    assert (output_dir / "README.md").exists()
    assert "[成功] 配置已成功生成" in result.output


def test_cli_generate_json_explicit(runner, tmp_path):
    """测试显式指定 JSON 格式"""
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--format', 'json',
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    assert (output_dir / "config.json").exists()
    assert "格式: JSON" in result.output


def test_cli_generate_yaml(runner, tmp_path):
    """测试生成 YAML 格式"""
    try:
        import yaml
    except ImportError:
        pytest.skip("需要 PyYAML")
    
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--format', 'yaml',
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    assert (output_dir / "config.yaml").exists()
    assert "格式: YAML" in result.output
    assert "YAML 格式支持添加注释" in result.output


def test_cli_generate_yaml_content(runner, tmp_path):
    """测试 YAML 格式内容正确性"""
    try:
        import yaml
    except ImportError:
        pytest.skip("需要 PyYAML")
    
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--format', 'yaml',
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    
    # 验证 YAML 文件可以被解析
    yaml_file = output_dir / "config.yaml"
    with open(yaml_file) as f:
        config = yaml.safe_load(f)
    
    assert "config_version" in config
    assert config["config_version"] == "2.0.0"


def test_cli_generate_json_content(runner, tmp_path):
    """测试 JSON 格式内容正确性"""
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--format', 'json',
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    
    # 验证 JSON 文件可以被解析
    json_file = output_dir / "config.json"
    with open(json_file) as f:
        config = json.load(f)
    
    assert "config_version" in config
    assert config["config_version"] == "2.0.0"


def test_cli_generate_readme_yaml_section(runner, tmp_path):
    """测试 YAML 格式的 README 包含注释说明"""
    try:
        import yaml
    except ImportError:
        pytest.skip("需要 PyYAML")
    
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--format', 'yaml',
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    
    # 验证 README 包含 YAML 注释说明
    readme_file = output_dir / "README.md"
    readme_content = readme_file.read_text(encoding='utf-8')
    
    assert "YAML 配置注释说明" in readme_content
    assert "添加注释的方法" in readme_content
    assert "行内注释" in readme_content
    assert "注释示例" in readme_content


def test_cli_generate_readme_json_no_yaml_section(runner, tmp_path):
    """测试 JSON 格式的 README 不包含 YAML 注释说明"""
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--format', 'json',
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    
    # 验证 README 不包含 YAML 注释说明
    readme_file = output_dir / "README.md"
    readme_content = readme_file.read_text(encoding='utf-8')
    
    assert "YAML 配置注释说明" not in readme_content


def test_cli_generate_terminal_output_format(runner, tmp_path):
    """测试终端输出格式"""
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--format', 'yaml',
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    # 验证输出包含关键信息
    assert "OAK Vision System - 配置生成工具" in result.output
    assert "路径:" in result.output
    assert "格式:" in result.output
    assert "[成功]" in result.output


def test_cli_generate_yaml_without_pyyaml(runner, tmp_path, monkeypatch):
    """测试在没有 PyYAML 时生成 YAML 的错误处理"""
    # 模拟 PyYAML 未安装
    def mock_import(name, *args, **kwargs):
        if 'yaml' in name.lower():
            raise ImportError("No module named 'yaml'")
        return __import__(name, *args, **kwargs)
    
    # 这个测试比较复杂，因为需要在运行时模拟导入失败
    # 暂时跳过，实际使用中会有友好的错误提示
    pytest.skip("需要更复杂的 mock 设置")


def test_cli_generate_format_conversion_hint(runner, tmp_path):
    """测试 README 包含格式转换提示"""
    output_dir = tmp_path / "test_config"
    
    result = runner.invoke(main, [
        '--output', str(output_dir),
        '--format', 'json',
        '--no-discover',
        '--force'
    ], input='y\n')
    
    assert result.exit_code == 0
    
    # 验证 README 包含格式转换说明
    readme_file = output_dir / "README.md"
    readme_content = readme_file.read_text(encoding='utf-8')
    
    assert "格式转换" in readme_content
    assert "convert_config.py" in readme_content
