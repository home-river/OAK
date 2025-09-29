#!/usr/bin/env python3

"""
真实OAK设备连接测试脚本
专门测试OAK设备的实际连接和信息获取功能
"""

import os
import sys
import time
from pathlib import Path

from oak_modules import OAKDeviceManager


def test_real_device_connection():
    """测试真实OAK设备连接"""
    print("🔌 开始测试真实OAK设备连接")
    print("=" * 50)
    
    # 创建设备管理器
    manager = OAKDeviceManager("configs/real_device_test.json")
    
    print("\n📡 正在扫描连接的OAK设备...")
    
    # 测试设备发现
    devices = manager.list_connected()
    
    if not devices:
        print("❌ 未发现任何OAK设备")
        print("\n💡 请检查:")
        print("  1. OAK设备是否正确连接到USB端口")
        print("  2. USB线缆是否支持数据传输")
        print("  3. 设备驱动是否正确安装")
        print("  4. 是否有其他程序占用设备")
        return False
    
    print(f"\n✅ 发现 {len(devices)} 个OAK设备:")
    print("-" * 40)
    
    for i, device in enumerate(devices):
        print(f"\n📱 设备 {i+1}:")
        print(f"  🆔 MXid: {device['mxid']}")
        print(f"  📛 名称: {device.get('name', '未知')}")
        print(f"  🔄 状态: {device['state']}")
        
        # 验证MXid格式
        mxid = device['mxid']
        if mxid and len(mxid) >= 10:
            print(f"  ✅ MXid格式有效 (长度: {len(mxid)})")
        else:
            print(f"  ⚠️ MXid格式可能异常: {mxid}")
    
    return True, devices


def test_device_binding_with_real_devices(devices):
    """使用真实设备测试绑定功能"""
    print(f"\n🔗 测试设备绑定功能")
    print("=" * 50)
    
    manager = OAKDeviceManager("configs/real_binding_test.json")
    
    try:
        # 为每个设备分配别名
        for i, device in enumerate(devices):
            mxid = device['mxid']
            alias = f"oak_device_{i+1}"
            
            print(f"\n🔧 绑定设备 {i+1}:")
            print(f"  MXid: {mxid[:20]}...")
            print(f"  别名: {alias}")
            
            # 执行绑定
            manager.bind_alias(mxid, alias)
            
            # 验证绑定
            found_mxid = manager.get_mxid(alias)
            found_alias = manager.get_alias(mxid)
            
            if found_mxid == mxid and found_alias == alias:
                print(f"  ✅ 绑定成功")
            else:
                print(f"  ❌ 绑定失败: {found_mxid}, {found_alias}")
                return False
        
        print(f"\n🎉 所有 {len(devices)} 个设备绑定成功!")
        return True
        
    except Exception as e:
        print(f"\n❌ 绑定过程中出现错误: {e}")
        return False


def test_device_configuration_with_real_devices(devices):
    """使用真实设备测试配置创建"""
    print(f"\n⚙️ 测试设备配置创建")
    print("=" * 50)
    
    manager = OAKDeviceManager("configs/real_config_test.json")
    
    try:
        # 准备配置数据
        mxids = [device['mxid'] for device in devices]
        aliases = [f"real_oak_{i+1}" for i in range(len(devices))]
        
        # 为每个设备创建不同的外参配置
        kinematics_list = []
        base_params = {"Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Ry": 22.9, "Rz": -25.2}
        
        for i in range(len(devices)):
            params = base_params.copy()
            # 为不同设备添加偏移
            params["Tx"] += i * 100.0
            params["Ty"] += i * 50.0
            params["Rz"] += i * 5.0
            kinematics_list.append(params)
        
        print(f"\n📝 创建包含 {len(devices)} 个设备的配置:")
        for i, (alias, params) in enumerate(zip(aliases, kinematics_list)):
            print(f"  {alias}: Tx={params['Tx']:.1f}, Ty={params['Ty']:.1f}, Tz={params['Tz']:.1f}")
        
        # 创建配置
        manager.create_new_config(
            mxids=mxids,
            aliases=aliases,
            kinematics_list=kinematics_list,
            filter_type="moving_average",
            filter_window=5
        )
        
        print(f"\n✅ 配置创建成功")
        
        # 验证配置
        if manager.validate():
            print(f"✅ 配置校验通过")
        else:
            print(f"❌ 配置校验失败")
            return False
        
        # 保存配置
        manager.save()
        print(f"💾 配置已保存")
        
        # 测试配置读取
        print(f"\n📖 测试配置读取:")
        for alias in aliases:
            kinematics = manager.get_kinematics(alias)
            print(f"  {alias}: {kinematics}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 配置创建过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_bind_real_devices(devices):
    """测试自动绑定真实设备"""
    print(f"\n🤖 测试自动绑定功能")
    print("=" * 50)
    
    manager = OAKDeviceManager("configs/auto_bind_real_test.json")
    
    try:
        # 创建设备别名映射
        device_aliases = {}
        default_kinematics = {}
        
        for i, device in enumerate(devices):
            mxid = device['mxid']
            alias = f"auto_oak_{i+1}"
            
            device_aliases[mxid] = alias
            default_kinematics[alias] = {
                "Tx": -1500.0 + i * 100,
                "Ty": -760.0 + i * 50,
                "Tz": 1200.0,
                "Ry": 22.9,
                "Rz": -25.2 + i * 5
            }
        
        print(f"\n📋 准备自动绑定映射:")
        for mxid, alias in device_aliases.items():
            print(f"  {mxid[:20]}... -> {alias}")
        
        # 执行自动绑定
        bound_devices = manager.auto_bind_devices(device_aliases, default_kinematics)
        
        print(f"\n✅ 成功自动绑定 {len(bound_devices)} 个设备:")
        for device in bound_devices:
            print(f"  📱 {device['alias']}: {device['mxid'][:20]}... ({device['state']})")
        
        # 验证绑定结果
        if len(bound_devices) == len(devices):
            print(f"✅ 所有设备都成功绑定")
            return True
        else:
            print(f"⚠️ 部分设备绑定失败: 期望{len(devices)}个，实际{len(bound_devices)}个")
            return False
            
    except Exception as e:
        print(f"\n❌ 自动绑定过程中出现错误: {e}")
        return False


def main():
    """主测试函数"""
    print("🎯 真实OAK设备连接测试")
    print("作者: OAK项目组")
    print("版本: 1.0.0")
    print("=" * 60)
    
    # 创建配置目录
    config_dir = Path("configs")
    config_dir.mkdir(exist_ok=True)
    
    test_results = []
    
    try:
        # 1. 测试设备连接
        print(f"\n🔍 步骤1: 设备发现测试")
        connection_success, devices = test_real_device_connection()
        test_results.append(("设备发现", connection_success))
        
        if not connection_success:
            print(f"\n⏹️ 由于未发现设备，跳过后续测试")
            return
        
        # 2. 测试设备绑定
        print(f"\n🔗 步骤2: 设备绑定测试")
        binding_success = test_device_binding_with_real_devices(devices)
        test_results.append(("设备绑定", binding_success))
        
        # 3. 测试配置创建
        print(f"\n⚙️ 步骤3: 配置创建测试")
        config_success = test_device_configuration_with_real_devices(devices)
        test_results.append(("配置创建", config_success))
        
        # 4. 测试自动绑定
        print(f"\n🤖 步骤4: 自动绑定测试")
        auto_bind_success = test_auto_bind_real_devices(devices)
        test_results.append(("自动绑定", auto_bind_success))
        
        # 生成测试报告
        print(f"\n" + "=" * 60)
        print(f"📊 真实设备测试报告")
        print(f"=" * 60)
        
        total_tests = len(test_results)
        passed_tests = sum(1 for _, success in test_results if success)
        
        print(f"发现设备数量: {len(devices)}")
        print(f"测试项目数量: {total_tests}")
        print(f"通过测试: {passed_tests} ✅")
        print(f"失败测试: {total_tests - passed_tests} ❌")
        print(f"通过率: {(passed_tests/total_tests*100):.1f}%")
        
        if passed_tests < total_tests:
            print(f"\n❌ 失败的测试:")
            for test_name, success in test_results:
                if not success:
                    print(f"  • {test_name}")
        
        # 设备详细信息
        print(f"\n📱 设备详细信息:")
        for i, device in enumerate(devices):
            print(f"  设备{i+1}: {device['mxid']} ({device['state']})")
        
        print(f"\n🎉 真实设备测试完成!")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程中出现未预期的错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
