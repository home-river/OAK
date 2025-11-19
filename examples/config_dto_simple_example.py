"""
配置DTO简单使用示例（扁平化版本）

演示新的扁平化配置DTO架构的使用方法。
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from oak_vision_system.core.dto.config_dto_v2 import (
    DeviceManagerConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    DeviceMetadataDTO,
    CoordinateTransformConfigDTO,
)


def main():
    print("=" * 60)
    print("配置DTO简单示例（扁平化版本）")
    print("=" * 60)
    
    # 1. 创建基本配置
    config = DeviceManagerConfigDTO()
    print(f"\n✅ 顶层配置创建成功")
    print(f"   配置版本: {config.config_version}")
    print(f"   OAK模块: {type(config.oak_module).__name__}")
    
    # 2. 创建设备角色绑定
    binding = DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        historical_mxids=["14442C10D13D0D0000"],
        last_active_mxid="14442C10D13D0D0000"
    )
    
    if binding.validate():
        print(f"\n✅ 设备角色绑定创建成功")
        print(f"   角色: {binding.role.display_name}")
        print(f"   历史MXid: {binding.historical_mxids}")
    
    # 3. 添加到配置
    config.role_bindings[DeviceRole.LEFT_CAMERA] = binding
    
    # 4. 创建设备元数据
    metadata = DeviceMetadataDTO(
        mxid="14442C10D13D0D0000",
        notes="主力设备",
    )
    config.device_metadata["14442C10D13D0D0000"] = metadata
    
    print(f"\n✅ 设备元数据添加成功")
    print(f"   MXid: {metadata.short_mxid}")
    print(f"   产品名: {metadata.product_name or '未知'}")
    
    # 5. 配置坐标变换
    transform = CoordinateTransformConfigDTO(
        role=DeviceRole.LEFT_CAMERA,
        translation_x=100.0,
        translation_y=50.0,
        yaw=45.0
    )
    config.data_processing_config.add_coordinate_transform(transform)
    
    print(f"\n✅ 坐标变换配置添加成功")
    print(f"   平移: ({transform.translation_x}, {transform.translation_y})")
    print(f"   偏航角: {transform.yaw}°")
    
    # 6. 访问模块配置
    print(f"\n📋 功能模块配置:")
    print(f"   OAK - 置信度: {config.oak_config.confidence_threshold}")
    print(f"   OAK - FPS: {config.oak_config.hardware_fps}")
    print(f"   数据处理 - 滤波: {config.data_processing_config.filter_config.filter_type}")
    print(f"   CAN - 启用: {config.can_config.enable_can}")
    print(f"   显示 - 模式: {config.display_config.default_display_mode}")
    
    # 7. 序列化
    config_dict = config.to_dict()
    print(f"\n✅ 配置序列化成功")
    print(f"   顶层键: {list(config_dict.keys())[:5]}...")
    
    print("\n" + "=" * 60)
    print("✅ 所有示例运行完成！")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
