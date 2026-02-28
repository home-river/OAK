"""
设备发现模块使用示例

展示如何使用重构后的OAKDeviceDiscovery模块：
- 发现可用设备
- 创建设备元数据
- 生成OAK模块配置
- 与DeviceManagerConfigDTO集成
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
from oak_vision_system.core.dto.config_dto import (
    DeviceManagerConfigDTO,
    DeviceRole,
    OAKConfigDTO,
    DisplayConfigDTO,
    SystemConfigDTO,
)


def example_1_basic_discovery():
    """示例1：基本设备发现"""
    print("=" * 80)
    print("示例1：基本设备发现")
    print("=" * 80)
    
    # 发现设备
    devices = OAKDeviceDiscovery.discover_devices(verbose=True)
    
    # 打印摘要
    OAKDeviceDiscovery.print_device_summary(devices)
    
    print(f"\n✅ 发现 {len(devices)} 个设备")


def example_2_auto_role_assignment():
    """示例2：自动角色分配"""
    print("\n" + "=" * 80)
    print("示例2：自动角色分配")
    print("=" * 80)
    
    # 发现设备
    devices = OAKDeviceDiscovery.discover_devices(verbose=False)
    
    if not devices:
        print("未发现设备")
        return
    
    # 自动创建OAK模块配置
    oak_module = OAKDeviceDiscovery.create_oak_module_config(devices)
    
    # 验证配置
    if oak_module.validate():
        print("\n✅ OAK模块配置创建成功")
        OAKDeviceDiscovery.print_oak_module_summary(oak_module)
    else:
        print("\n❌ 配置验证失败")


def example_3_manual_role_mapping():
    """示例3：手动指定角色映射"""
    print("\n" + "=" * 80)
    print("示例3：手动指定角色映射")
    print("=" * 80)
    
    # 发现设备
    devices = OAKDeviceDiscovery.discover_devices(verbose=False)
    
    if len(devices) < 2:
        print(f"至少需要2个设备，当前只有 {len(devices)} 个")
        return
    
    # 手动指定角色映射
    print("\n手动指定角色映射:")
    custom_mapping = {
        devices[0].mxid: DeviceRole.LEFT_CAMERA,
        devices[1].mxid: DeviceRole.RIGHT_CAMERA,
    }
    
    for mxid, role in custom_mapping.items():
        print(f"  {mxid[:16]}... -> {role.display_name}")
    
    # 创建OAK模块配置
    oak_module = OAKDeviceDiscovery.create_oak_module_config(
        devices,
        role_mapping=custom_mapping
    )
    
    print("\n✅ 使用自定义映射创建配置成功")
    print(f"  激活角色数: {oak_module.active_role_count}")
    print(f"  可用角色: {[r.display_name for r in oak_module.available_roles]}")


def example_4_integrate_with_device_manager():
    """示例4：集成到DeviceManagerConfigDTO"""
    print("\n" + "=" * 80)
    print("示例4：集成到完整的设备管理器配置")
    print("=" * 80)
    
    # 1. 发现设备
    print("\n步骤1: 发现设备...")
    devices = OAKDeviceDiscovery.discover_devices(verbose=False)
    
    if not devices:
        print("未发现设备")
        return
    
    print(f"✅ 发现 {len(devices)} 个设备")
    
    # 2. 创建OAK模块配置
    print("\n步骤2: 创建OAK模块配置...")
    oak_module = OAKDeviceDiscovery.create_oak_module_config(devices)
    
    # 3. 配置OAK硬件参数
    oak_module.hardware_config = OAKConfigDTO(
        model_path="/path/to/model.blob",
        confidence_threshold=0.7,
        hardware_fps=20,
    )
    
    print("✅ OAK硬件配置已设置")
    
    # 4. 创建完整的设备管理器配置
    print("\n步骤3: 创建完整配置...")
    config = DeviceManagerConfigDTO(
        oak_module=oak_module,
        display_config=DisplayConfigDTO(
            enable_display=True,
            default_display_mode="combined",
        ),
        system_config=SystemConfigDTO(
            log_level="INFO",
        ),
    )
    
    # 5. 验证配置
    if not config.validate():
        print("\n❌ 配置验证失败:")
        for error in config.get_validation_errors():
            print(f"  - {error}")
        return
    
    print("\n✅ 完整配置创建并验证成功！")
    
    # 6. 打印配置摘要
    print(config.get_summary())


def example_5_query_device_info():
    """示例5：查询设备信息"""
    print("\n" + "=" * 80)
    print("示例5：查询设备信息")
    print("=" * 80)
    
    # 发现设备并创建配置
    devices = OAKDeviceDiscovery.discover_devices(verbose=False)
    
    if not devices:
        print("未发现设备")
        return
    
    oak_module = OAKDeviceDiscovery.create_oak_module_config(devices)
    
    # 查询信息
    print("\n设备信息查询:")
    print(f"  总设备数: {len(oak_module.device_metadata)}")
    print(f"  激活角色数: {oak_module.active_role_count}")
    print(f"  总角色数: {oak_module.total_role_count}")
    
    # 遍历每个角色
    print("\n角色详情:")
    for role in oak_module.available_roles:
        mxid = oak_module.get_active_mxid(role)
        metadata = oak_module.get_device_metadata(mxid)
        
        print(f"\n  {role.display_name}:")
        print(f"    MXid: {mxid}")
        print(f"    产品名: {metadata.product_name or '未知'}")
        print(f"    备注: {metadata.notes}")


def main():
    """运行所有示例"""
    try:
        example_1_basic_discovery()
        example_2_auto_role_assignment()
        example_3_manual_role_mapping()
        example_4_integrate_with_device_manager()
        example_5_query_device_info()
        
        print("\n" + "=" * 80)
        print("✅ 所有示例运行完成！")
        print("=" * 80)
        
    except Exception as e:
        import traceback
        print(f"\n❌ 示例运行出错: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()

