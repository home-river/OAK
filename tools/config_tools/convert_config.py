#!/usr/bin/env python3
"""
配置格式转换工具

用途：在 JSON 和 YAML 配置格式之间进行转换

使用方式：
1. JSON 转 YAML：python tools/config_tools/convert_config.py config.json --format yaml
2. YAML 转 JSON：python tools/config_tools/convert_config.py config.yaml --format json
3. 转换后验证：python tools/config_tools/convert_config.py config.json --format yaml --validate
4. 强制覆盖：python tools/config_tools/convert_config.py config.json --format yaml --force

作者：OAK Vision System
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import click
except ImportError:
    print("错误: 需要安装 click 库")
    print("请运行: pip install click")
    sys.exit(1)

try:
    from oak_vision_system.modules.config_manager import ConfigConverter, DeviceConfigManager
except ImportError as e:
    print(f"错误: 无法导入配置管理模块: {e}")
    print("请确保项目已正确安装")
    sys.exit(1)


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
    """配置文件格式转换工具
    
    支持 JSON 和 YAML 格式之间的双向转换。
    提供友好的终端交互界面和进度显示。
    
    示例:
        python convert_config.py config.json --format yaml
        python convert_config.py config.yaml --format json --validate
    """
    click.echo("=" * 60)
    click.echo("OAK Vision System - 配置格式转换工具")
    click.echo("=" * 60)
    
    # 转换路径为 Path 对象
    input_path = Path(input_file)
    
    # 检测输入格式
    try:
        input_format = ConfigConverter.detect_format(input_path)
    except ValueError as e:
        click.echo(f"\n[错误] {e}", err=True)
        click.echo("\n提示: 支持的格式为 .json, .yaml, .yml")
        sys.exit(1)
    
    # 确定输出路径
    if output:
        output_path = Path(output)
    else:
        # 自动生成输出路径
        if format == 'yaml':
            output_path = input_path.with_suffix('.yaml')
        else:
            output_path = input_path.with_suffix('.json')
    
    # 显示转换信息
    click.echo(f"\n正在转换配置文件...")
    click.echo(f"  输入: {input_path} ({input_format.upper()})")
    click.echo(f"  输出: {output_path} ({format.upper()})")
    
    # 检查输出文件是否存在
    if output_path.exists() and not force:
        click.echo(f"\n[警告] 文件已存在: {output_path}")
        if not click.confirm('是否覆盖?', default=False):
            click.echo("\n已取消")
            return
    
    # 执行转换
    click.echo("\n正在转换...")
    try:
        if format == 'yaml':
            ConfigConverter.json_to_yaml(input_path, output_path)
        else:
            ConfigConverter.yaml_to_json(input_path, output_path)
        
        click.echo("\n[成功] 转换完成")
        click.echo(f"  配置已保存到: {output_path}")
        
        # 可选验证
        if validate:
            click.echo("\n正在验证配置...")
            try:
                manager = DeviceConfigManager(str(output_path))
                success = manager.load_config(validate=True)
                if not success:
                    click.echo("[错误] 配置验证失败", err=True)
                    click.echo("\n提示: 请检查配置文件格式是否正确")
                    sys.exit(3)
                click.echo("[成功] 配置验证通过")
            except Exception as e:
                click.echo(f"[错误] 配置验证失败: {e}", err=True)
                click.echo("\n提示: 请检查配置文件格式是否正确")
                sys.exit(3)
        
        # 提示信息
        if format == 'yaml':
            click.echo("\n提示: 你可以手动编辑 YAML 文件添加注释")
        
    except FileNotFoundError as e:
        click.echo(f"\n[错误] 文件不存在: {e}", err=True)
        click.echo("\n提示: 请检查文件路径是否正确")
        sys.exit(1)
        
    except ImportError as e:
        click.echo(f"\n[错误] 依赖缺失:\n{e}", err=True)
        click.echo("\n提示: 运行 'pip install pyyaml' 安装依赖")
        sys.exit(2)
        
    except Exception as e:
        click.echo(f"\n[错误] 转换失败: {e}", err=True)
        click.echo("\n提示: 请检查文件格式和路径是否正确")
        sys.exit(99)


if __name__ == '__main__':
    main()
