"""
系统配置管理模块使用示例（向后兼容版本）

演示如何使用系统配置管理器，包括：
- 设备发现和配置
- Pipeline配置管理
- 配置文件的保存和加载
- DTO的使用

注意：本示例使用旧的类名 OAKDeviceManager 以演示向后兼容性
推荐新项目使用 SystemConfigManager
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 使用旧名称（向后兼容）
from oak_vision_system.modules.data_collector import OAKDeviceManager
# 推荐新项目使用：
# from modules.data_collector import SystemConfigManager as OAKDeviceManager
from oak_vision_system.core.dto import (
    DeviceType,
    PipelineType,
    DeviceConfigDTO,
    PipelineConfigDTO
)


def demonstrate_basic_usage():
    """演示基本用法"""
    print("=== OAK设备管理器基本用法演示 ===\n")
    
    # 创建设备管理器
    config_path = "config/demo_device_config.json"
    manager = OAKDeviceManager(config_path)
    
    print("1. 发现连接的设备:")
    discovered_devices = manager.discover_devices()
    
    if discovered_devices:
        for device in discovered_devices:
            print(f"   - MXid: {device.mxid[:20]}...")
            print(f"     类型: {device.device_type.value}")
            print(f"     状态: {device.connection_status.value}")
            print(f"     可用: {device.is_available}")
    else:
        print("   未发现设备，使用模拟数据演示...")
        # 使用模拟数据
        discovered_devices = [
            type('MockDevice', (), {
                'mxid': 'MOCK_DEVICE_LEFT_123456789',
                'device_type': DeviceType.OAK_D,
                'connection_status': 'connected'
            })(),
            type('MockDevice', (), {
                'mxid': 'MOCK_DEVICE_RIGHT_987654321', 
                'device_type': DeviceType.OAK_D,
                'connection_status': 'connected'
            })()
        ]
    
    print(f"\n2. 添加设备配置:")
    
    # 添加第一个设备
    if len(discovered_devices) >= 1:
        device1 = discovered_devices[0]
        success = manager.add_device(
            mxid=device1.mxid,
            alias="left_oak",
            device_type=DeviceType.OAK_D,
            properties={"position": "left", "priority": 1}
        )
        print(f"   设备1添加: {'成功' if success else '失败'}")
    
    # 添加第二个设备
    if len(discovered_devices) >= 2:
        device2 = discovered_devices[1]
        success = manager.add_device(
            mxid=device2.mxid,
            alias="right_oak", 
            device_type=DeviceType.OAK_D,
            properties={"position": "right", "priority": 2}
        )
        print(f"   设备2添加: {'成功' if success else '失败'}")
    
    print(f"\n3. 配置Pipeline:")
    
    # 为left_oak配置检测Pipeline
    detection_pipeline = manager.get_default_detection_pipeline_config(
        device_type=DeviceType.OAK_D,
        confidence_threshold=0.6
    )
    
    success = manager.set_pipeline_config("left_oak", detection_pipeline)
    print(f"   left_oak Pipeline配置: {'成功' if success else '失败'}")
    
    # 为right_oak配置组合Pipeline
    combined_pipeline = manager.get_default_combined_pipeline_config(
        device_type=DeviceType.OAK_D
    )
    
    success = manager.set_pipeline_config("right_oak", combined_pipeline)
    print(f"   right_oak Pipeline配置: {'成功' if success else '失败'}")
    
    print(f"\n4. 验证和保存配置:")
    
    # 验证配置
    if manager.validate_registry():
        print("   配置验证: 通过")
        
        # 保存配置
        if manager.save_config():
            print("   配置保存: 成功")
        else:
            print("   配置保存: 失败")
    else:
        print("   配置验证: 失败")
    
    print(f"\n5. 查询配置信息:")
    
    # 获取设备列表
    devices = manager.list_devices()
    print(f"   已配置设备数量: {len(devices)}")
    
    for device in devices:
        print(f"   - {device.alias}: {device.mxid[:20]}... ({device.device_type.value})")
        
        # 获取Pipeline配置
        pipeline_config = manager.get_pipeline_config(device.alias)
        if pipeline_config:
            print(f"     Pipeline: {pipeline_config.pipeline_type.value}")
            print(f"     分辨率: {pipeline_config.resolution_string}")
            print(f"     置信度: {pipeline_config.confidence_threshold}")
    
    # 获取注册表摘要
    summary = manager.get_registry_summary()
    print(f"\n6. 注册表摘要:")
    print(f"   配置版本: {summary.get('config_version')}")
    print(f"   设备总数: {summary.get('device_count')}")
    print(f"   启用设备数: {summary.get('enabled_device_count')}")


def demonstrate_auto_configuration():
    """演示自动配置功能"""
    print("\n\n=== 自动配置功能演示 ===\n")
    
    # 创建新的设备管理器实例
    manager = OAKDeviceManager("config/auto_config_demo.json")
    
    # 定义设备别名映射
    device_aliases = {
        "MOCK_DEVICE_LEFT_123456789": "left_camera",
        "MOCK_DEVICE_RIGHT_987654321": "right_camera"
    }
    
    print("1. 自动发现和配置设备:")
    
    configured_devices = manager.auto_discover_and_configure(
        device_aliases=device_aliases,
        default_device_type=DeviceType.OAK_D,
        create_default_pipelines=True
    )
    
    print(f"   成功配置的设备: {configured_devices}")
    
    if configured_devices:
        print("\n2. 自动配置结果:")
        
        for alias in configured_devices:
            device_config = manager.get_device_config(alias)
            pipeline_config = manager.get_pipeline_config(alias)
            
            print(f"   设备: {alias}")
            print(f"     MXid: {device_config.mxid[:20]}...")
            print(f"     类型: {device_config.device_type.value}")
            print(f"     Pipeline: {pipeline_config.pipeline_type.value if pipeline_config else 'None'}")
        
        # 保存自动配置结果
        if manager.save_config():
            print("\n   自动配置已保存")


def demonstrate_config_loading():
    """演示配置加载功能"""
    print("\n\n=== 配置加载功能演示 ===\n")
    
    # 创建新的管理器实例并加载之前保存的配置
    manager = OAKDeviceManager("config/demo_device_config.json")
    
    print("1. 加载已保存的配置:")
    
    if manager.load_config():
        print("   配置加载: 成功")
        
        # 显示加载的配置
        summary = manager.get_registry_summary()
        print(f"   加载的设备数量: {summary.get('device_count')}")
        
        devices = manager.list_devices()
        for device in devices:
            print(f"   - {device.alias}: {device.device_type.value}")
            
            # 检查Pipeline配置
            pipeline_config = manager.get_pipeline_config(device.alias)
            if pipeline_config:
                print(f"     Pipeline类型: {pipeline_config.pipeline_type.value}")
                print(f"     置信度阈值: {pipeline_config.confidence_threshold}")
    else:
        print("   配置加载: 失败")


def demonstrate_static_pipeline_configs():
    """演示静态Pipeline配置方法"""
    print("\n\n=== 静态Pipeline配置演示 ===\n")
    
    print("1. 默认检测Pipeline配置:")
    detection_config = OAKDeviceManager.get_default_detection_pipeline_config(
        device_type=DeviceType.OAK_D,
        confidence_threshold=0.7
    )
    
    print(f"   类型: {detection_config.pipeline_type.value}")
    print(f"   输入分辨率: {detection_config.resolution_string}")
    print(f"   深度分辨率: {detection_config.depth_resolution_string}")
    print(f"   置信度阈值: {detection_config.confidence_threshold}")
    print(f"   帧率: {detection_config.fps}")
    
    print(f"\n2. 默认深度Pipeline配置:")
    depth_config = OAKDeviceManager.get_default_depth_pipeline_config(
        device_type=DeviceType.OAK_D_LITE
    )
    
    print(f"   类型: {depth_config.pipeline_type.value}")
    print(f"   深度分辨率: {depth_config.depth_resolution_string}")
    print(f"   帧率: {depth_config.fps}")
    print(f"   深度模式: {depth_config.get_config_param('depth_mode', 'unknown')}")
    
    print(f"\n3. 默认组合Pipeline配置:")
    combined_config = OAKDeviceManager.get_default_combined_pipeline_config(
        device_type=DeviceType.OAK_D_PRO
    )
    
    print(f"   类型: {combined_config.pipeline_type.value}")
    print(f"   输入分辨率: {combined_config.resolution_string}")
    print(f"   深度分辨率: {combined_config.depth_resolution_string}")
    print(f"   空间检测: {combined_config.get_config_param('spatial_detection', False)}")


def demonstrate_dto_features():
    """演示DTO特性"""
    print("\n\n=== DTO特性演示 ===\n")
    
    print("1. 创建设备配置DTO:")
    device_config = DeviceConfigDTO(
        mxid="DEMO_DEVICE_123456789",
        alias="demo_device",
        device_type=DeviceType.OAK_D,
        enabled=True,
        properties={"location": "test_lab", "owner": "demo_user"}
    )
    
    print(f"   设备: {device_config.alias}")
    print(f"   MXid: {device_config.mxid}")
    print(f"   类型: {device_config.device_type.value}")
    print(f"   是否有效: {device_config.is_data_valid()}")
    print(f"   位置属性: {device_config.get_property('location', 'unknown')}")
    
    print(f"\n2. JSON序列化:")
    json_str = device_config.to_json(indent=2)
    print(f"   JSON长度: {len(json_str)} 字符")
    print(f"   JSON预览: {json_str[:100]}...")
    
    print(f"\n3. 从JSON反序列化:")
    restored_config = DeviceConfigDTO.from_json(json_str)
    print(f"   恢复的设备: {restored_config.alias}")
    print(f"   数据一致性: {device_config.alias == restored_config.alias}")
    
    print(f"\n4. Pipeline配置DTO:")
    pipeline_config = PipelineConfigDTO(
        pipeline_type=PipelineType.COMBINED,
        input_resolution=(416, 416),
        confidence_threshold=0.6,
        enable_depth_output=True,
        config_params={"custom_param": "demo_value"}
    )
    
    print(f"   Pipeline类型: {pipeline_config.pipeline_type.value}")
    print(f"   分辨率: {pipeline_config.resolution_string}")
    print(f"   是否有效: {pipeline_config.is_data_valid()}")
    print(f"   自定义参数: {pipeline_config.get_config_param('custom_param')}")


def main():
    """主函数"""
    try:
        # 确保配置目录存在
        os.makedirs("config", exist_ok=True)
        
        # 运行各种演示
        demonstrate_basic_usage()
        demonstrate_auto_configuration()
        demonstrate_config_loading()
        demonstrate_static_pipeline_configs()
        demonstrate_dto_features()
        
        print("\n\n=== 演示完成 ===")
        print("重构后的OAK设备管理模块演示了以下特性：")
        print("✓ 解耦的设备配置管理")
        print("✓ 类型安全的DTO系统")
        print("✓ 静态Pipeline配置方法")
        print("✓ 灵活的设备属性扩展")
        print("✓ 完整的配置验证机制")
        print("✓ JSON序列化支持")
        
    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
