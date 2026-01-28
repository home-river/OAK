#!/usr/bin/env python3
"""
设备发现工具

用途：发现连接的 OAK 设备并显示其 MXid

使用方式：
    python tools/discover_devices.py

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
    from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
except ImportError as e:
    print(f"错误: 无法导入设备发现模块: {e}")
    sys.exit(1)


@click.command()
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='显示详细信息'
)
def main(verbose):
    """发现连接的 OAK 设备
    
    此工具会扫描所有连接的 OAK 设备并显示其信息。
    """
    click.echo("=" * 60)
    click.echo("OAK Vision System - 设备发现工具")
    click.echo("=" * 60)
    
    click.echo("\n正在扫描设备...")
    
    try:
        devices = OAKDeviceDiscovery.discover_devices(verbose=verbose)
        
        if not devices:
            click.echo("\n未发现任何 OAK 设备")
            click.echo("\n请检查:")
            click.echo("  1. 设备是否已连接到计算机")
            click.echo("  2. USB 线缆是否正常")
            click.echo("  3. 设备驱动是否已安装")
            return
        
        click.echo(f"\n✓ 发现 {len(devices)} 个设备:\n")
        
        for idx, device in enumerate(devices, 1):
            click.echo(f"[{idx}] 设备信息:")
            click.echo(f"  MXid: {device.mxid}")
            click.echo(f"  产品名: {device.product_name or '未知'}")
            click.echo(f"  连接状态: {device.connection_status.value}")
            if device.notes:
                click.echo(f"  备注: {device.notes}")
            click.echo()
        
        click.echo("提示: 将 MXid 复制到配置文件的 device_bindings 部分")
        
    except Exception as e:
        click.echo(f"\n✗ 设备发现失败: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
