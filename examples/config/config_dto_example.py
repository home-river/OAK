"""
配置DTO使用示例

演示新的模块化配置DTO架构的使用方法。
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from oak_vision_system.core.dto.config_dto import (
    DeviceManagerConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    DeviceMetadataDTO,
    CoordinateTransformConfigDTO,
    OAKConfigDTO,
)


def example_1_create_basic_config():
    """示例1：创建基本配置"""
    print("=" * 60)
    print("示例1：创建基本配置")
    print("=" * 60)
    
    # 创建顶层配置
    config = DeviceManagerConfigDTO()
    
    print(f"✅ 配置版本: {config.config_version}")
    print(f"   OAK模块: {type(config.oak_module).__name__}")
    print(f"   OAK配置: {config.oak_module.hardware_config.confidence_threshold}")
    print()


def example_2_device_role_binding():
    """示例2：设备角色绑定"""
    print("=" * 60)
    print("示例2：设备角色绑定")
    print("=" * 60)
    
    # 创建角色绑定
    left_binding = DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        historical_mxids=["14442C10D13D0D0000", "14442C10D13D0D0001"],
        last_active_mxid="14442C10D13D0D0000"
    )
    
    # 验证
    if left_binding.validate():
        print(f"✅ 角色绑定创建成功")
        print(f"   角色: {left_binding.role.display_name}")
        print(f"   历史MXid数量: {left_binding.mxid_count}")
        print(f"   MXid列表: {left_binding.get_mxids_display()}")
        print(f"   上次使用: {left_binding.last_active_mxid[-8:]}")
    else:
        print(f"❌ 验证失败: {left_binding.get_validation_errors()}")
    
    print()


def example_3_device_metadata():
    """示例3：设备元数据"""
    print("=" * 60)
    print("示例3：设备元数据")
    print("=" * 60)
    
    # 创建设备元数据
    metadata = DeviceMetadataDTO(
        mxid="14442C10D13D0D0000",
        notes="2025年10月购入，主力设备",
    )
    
    print(f"✅ 设备元数据创建成功")
    print(f"   MXid: {metadata.short_mxid}")
    print(f"   产品名: {metadata.product_name or '未知'}")
    print(f"   备注: {metadata.notes}")
    print(f"   健康状态: {metadata.health_status}")
    print(f"   首次发现: {metadata.first_seen_str}")
    print()


def example_4_coordinate_transform():
    """示例4：坐标变换配置"""
    print("=" * 60)
    print("示例4：坐标变换配置")
    print("=" * 60)
    
    # 创建坐标变换配置
    transform = CoordinateTransformConfigDTO(
        role=DeviceRole.LEFT_CAMERA,
        translation_x=100.0,
        translation_y=50.0,
        translation_z=200.0,
        pitch=10.0,
        yaw=45.0,
        calibration_method="manual",
        calibration_accuracy=2.5
    )
    
    print(f"✅ 坐标变换配置创建成功")
    print(f"   角色: {transform.role.display_name}")
    print(f"   平移: X={transform.translation_x}, Y={transform.translation_y}, Z={transform.translation_z}")
    print(f"   旋转: Pitch={transform.pitch}°, Yaw={transform.yaw}°")
    print(f"   标定方法: {transform.calibration_method}")
    print(f"   标定精度: {transform.calibration_accuracy}mm")
    
    # 生成变换矩阵
    try:
        import numpy as np  # noqa: F401 仅用于提示依赖
        from utils.transform_utils import build_transform_matrix
        T = build_transform_matrix(transform)
        print(f"\n变换矩阵:")
        print(T)
    except ImportError:
        print("\n（需要numpy来生成变换矩阵）")
    
    print()


def example_5_complete_config():
    """示例5：完整配置"""
    print("=" * 60)
    print("示例5：完整配置")
    print("=" * 60)
    
    # 创建完整配置
    config = DeviceManagerConfigDTO()
    
    # 设置角色绑定
    left_binding = DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        historical_mxids=["14442C10D13D0D0000"],
        last_active_mxid="14442C10D13D0D0000"
    )
    config.role_bindings[DeviceRole.LEFT_CAMERA] = left_binding
    
    # 设置设备元数据
    metadata = DeviceMetadataDTO(
        mxid="14442C10D13D0D0000",
        notes="主力设备",
    )
    config.device_metadata["14442C10D13D0D0000"] = metadata
    
    # 设置坐标变换
    transform = CoordinateTransformConfigDTO(
        role=DeviceRole.LEFT_CAMERA,
        translation_x=100.0,
        yaw=45.0
    )
    config.data_processing_config.add_coordinate_transform(transform)
    
    # 显示配置信息
    print(f"✅ 完整配置创建成功")
    print(f"\n基础设备管理:")
    print(f"  角色数量: {len(config.role_bindings)}")
    print(f"  设备数量: {len(config.device_metadata)}")
    print(f"  激活角色数量: {config.active_role_count}")
    
    print(f"\n功能模块配置:")
    print(f"  OAK - 置信度阈值: {config.oak_config.confidence_threshold}")
    print(f"  OAK - 硬件FPS: {config.oak_config.hardware_fps}")
    print(f"  数据处理 - 滤波类型: {config.data_processing_config.filter_config.filter_type}")
    print(f"  CAN - 启用状态: {config.can_config.enable_can}")
    print(f"  显示 - 显示模式: {config.display_config.default_display_mode}")
    
    # 序列化为字典
    config_dict = config.to_dict()
    print(f"\n配置已序列化为字典，顶层键:")
    print(f"  {list(config_dict.keys())}")
    
    print()


def example_6_validation():
    """示例6：验证功能"""
    print("=" * 60)
    print("示例6：验证功能")
    print("=" * 60)
    
    # 创建一个无效的配置
    binding = DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        historical_mxids=[]  # 空列表 - 无效！
    )
    
    if not binding.validate():
        print("❌ 检测到无效配置:")
        for error in binding.get_validation_errors():
            print(f"   - {error}")
    
    # 修正并重新验证
    binding = DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        historical_mxids=["14442C10D13D0D0000"]  # 有效
    )
    
    if binding.validate():
        print("\n✅ 配置修正后验证通过")
    
    print()


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("配置DTO使用示例")
    print("=" * 60 + "\n")
    
    try:
        example_1_create_basic_config()
        example_2_device_role_binding()
        example_3_device_metadata()
        example_4_coordinate_transform()
        example_5_complete_config()
        example_6_validation()
        
        print("=" * 60)
        print("✅ 所有示例运行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 示例运行出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
