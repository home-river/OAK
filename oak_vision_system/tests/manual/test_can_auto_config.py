#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAN接口自动配置功能测试

测试目标：
1. 验证CAN接口自动配置功能是否正常工作
2. 测试不同配置参数的效果
3. 验证接口重置功能

使用方法：
    python oak_vision_system/tests/manual/test_can_auto_config.py

注意：
- 需要在Linux系统上运行
- 需要sudo权限（会提示输入密码）
- 测试完成后会自动清理接口
"""

import os
import sys
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from oak_vision_system.modules.can_communication.can_interface_config import (
    configure_can_interface,
    reset_can_interface
)


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check_interface_status(channel: str) -> bool:
    """检查接口状态"""
    import subprocess
    try:
        result = subprocess.run(
            ['ip', 'link', 'show', channel],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            status = result.stdout
            is_up = 'UP' in status
            print(f"✅ 接口 {channel} 存在")
            print(f"   状态: {'已启用 (UP)' if is_up else '未启用 (DOWN)'}")
            print(f"   详情: {status.split('mtu')[0].strip()}")
            return True
        else:
            print(f"❌ 接口 {channel} 不存在")
            return False
            
    except Exception as e:
        print(f"❌ 检查接口状态失败: {e}")
        return False


def test_configure_can_interface():
    """测试CAN接口配置功能"""
    print_section("测试1: CAN接口自动配置")
    
    # 测试参数
    channel = 'can0'
    bitrate = 250000
    
    print(f"\n📋 测试参数:")
    print(f"   接口: {channel}")
    print(f"   波特率: {bitrate}")
    print(f"   平台: {sys.platform}")
    
    # 检查平台
    if sys.platform not in ['linux', 'linux2']:
        print(f"\n⚠️  警告: 当前平台 ({sys.platform}) 不支持自动配置")
        print("   自动配置功能仅支持Linux系统")
        return False
    
    # 执行配置
    print(f"\n🔧 开始配置接口 {channel}...")
    print("   (可能需要输入sudo密码)")
    
    success = configure_can_interface(
        channel=channel,
        bitrate=bitrate,
        sudo_password=None  # 会提示输入密码
    )
    
    if success:
        print(f"\n✅ 接口配置成功！")
        
        # 验证配置结果
        print(f"\n🔍 验证配置结果:")
        time.sleep(1)  # 等待接口完全启动
        check_interface_status(channel)
        
        return True
    else:
        print(f"\n❌ 接口配置失败")
        return False


def test_reset_can_interface():
    """测试CAN接口重置功能"""
    print_section("测试2: CAN接口重置")
    
    channel = 'can0'
    
    print(f"\n🔧 开始重置接口 {channel}...")
    
    success = reset_can_interface(
        channel=channel,
        sudo_password=None
    )
    
    if success:
        print(f"\n✅ 接口重置成功！")
        
        # 验证重置结果
        print(f"\n🔍 验证重置结果:")
        time.sleep(1)
        check_interface_status(channel)
        
        return True
    else:
        print(f"\n❌ 接口重置失败")
        return False


def test_virtual_can_interface():
    """测试虚拟CAN接口配置"""
    print_section("测试3: 虚拟CAN接口配置")
    
    channel = 'vcan0'
    
    print(f"\n📋 测试虚拟CAN接口: {channel}")
    print("   虚拟CAN不需要硬件，适合开发测试")
    
    # 配置虚拟CAN
    print(f"\n🔧 配置虚拟CAN接口...")
    
    import subprocess
    try:
        # 加载vcan模块
        subprocess.run(['sudo', 'modprobe', 'vcan'], check=True, capture_output=True)
        
        # 创建虚拟接口
        subprocess.run(['sudo', 'ip', 'link', 'add', 'dev', channel, 'type', 'vcan'], 
                      check=False, capture_output=True)
        
        # 启动接口
        subprocess.run(['sudo', 'ip', 'link', 'set', 'up', channel], 
                      check=True, capture_output=True)
        
        print(f"✅ 虚拟CAN接口配置成功")
        
        # 验证
        print(f"\n🔍 验证配置结果:")
        time.sleep(1)
        check_interface_status(channel)
        
        # 清理
        print(f"\n🧹 清理虚拟接口...")
        subprocess.run(['sudo', 'ip', 'link', 'set', 'down', channel], 
                      check=False, capture_output=True)
        subprocess.run(['sudo', 'ip', 'link', 'delete', channel], 
                      check=False, capture_output=True)
        print(f"✅ 虚拟接口已清理")
        
        return True
        
    except Exception as e:
        print(f"❌ 虚拟CAN配置失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  CAN接口自动配置功能测试")
    print("=" * 70)
    print("\n📝 说明:")
    print("   - 此测试会验证CAN接口自动配置功能")
    print("   - 需要sudo权限（会提示输入密码）")
    print("   - 测试完成后会自动清理")
    print("   - 按 Ctrl+C 可随时退出")
    
    input("\n按 Enter 键开始测试...")
    
    results = []
    
    try:
        # 测试1: 配置CAN接口
        result1 = test_configure_can_interface()
        results.append(("CAN接口配置", result1))
        
        if result1:
            # 测试2: 重置CAN接口
            time.sleep(2)
            result2 = test_reset_can_interface()
            results.append(("CAN接口重置", result2))
        
        # 测试3: 虚拟CAN接口
        time.sleep(2)
        result3 = test_virtual_can_interface()
        results.append(("虚拟CAN接口", result3))
        
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中出错: {e}")
    
    # 打印测试结果
    print_section("测试结果汇总")
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n📊 总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
