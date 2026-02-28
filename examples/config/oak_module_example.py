"""
OAK模块配置示例

展示如何使用新的OAKModuleConfigDTO进行内聚的OAK配置管理。
"""

from oak_vision_system.core.dto.config_dto import (
    OAKModuleConfigDTO,
    OAKConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    DeviceMetadataDTO,
    DeviceType,
)


def example_1_basic_oak_module():
    """示例1：基本的OAK模块配置"""
    print("=" * 80)
    print("示例1：基本的OAK模块配置")
    print("=" * 80)
    
    # 创建OAK模块配置（使用默认值）
    oak_module = OAKModuleConfigDTO()
    
    print("\n默认配置:")
    print(oak_module.get_summary())
    print()


def example_2_complete_oak_module():
    """示例2：完整的OAK模块配置"""
    print("=" * 80)
    print("示例2：完整的OAK模块配置（硬件+设备绑定）")
    print("=" * 80)
    
    # 1. 配置OAK硬件
    hardware = OAKConfigDTO(
        model_path="/models/yolo.blob",
        confidence_threshold=0.7,
        hardware_fps=30,
        rgb_resolution=(1920, 1080),
        enable_depth_output=True,
        queue_max_size=4,
    )
    
    # 2. 配置设备角色绑定
    left_binding = DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        historical_mxids=["14442C10D13F0AD700", "14442C10D13F0AD710"],
        active_mxid="14442C10D13F0AD700",
        last_active_mxid="14442C10D13F0AD700",
    )
    
    # 3. 配置设备元数据
    left_metadata = DeviceMetadataDTO(
        mxid="14442C10D13F0AD700",
        device_type=DeviceType.OAK_D,
        notes="左侧主相机，负责检测左边区域",
    )
    
    # 4. 组合成OAK模块配置
    oak_module = OAKModuleConfigDTO(
        hardware_config=hardware,
        role_bindings={DeviceRole.LEFT_CAMERA: left_binding},
        device_metadata={"14442C10D13F0AD700": left_metadata},
    )
    
    # 验证配置
    if not oak_module.validate():
        print("❌ 配置验证失败:")
        for error in oak_module.get_validation_errors():
            print(f"  - {error}")
        return
    
    print("\n✅ 配置验证通过！")
    print(oak_module.get_summary())
    print()


def example_3_convenient_access():
    """示例3：便捷访问方法"""
    print("=" * 80)
    print("示例3：便捷访问方法")
    print("=" * 80)
    
    # 创建配置
    oak_module = OAKModuleConfigDTO(
        hardware_config=OAKConfigDTO(
            model_path="/models/detector.blob",
            hardware_fps=20,
        ),
        role_bindings={
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                historical_mxids=["MXID_LEFT"],
                active_mxid="MXID_LEFT",
            ),
            DeviceRole.RIGHT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.RIGHT_CAMERA,
                historical_mxids=["MXID_RIGHT"],
                active_mxid="MXID_RIGHT",
            ),
        },
        device_metadata={
            "MXID_LEFT": DeviceMetadataDTO(mxid="MXID_LEFT", notes="左相机"),
            "MXID_RIGHT": DeviceMetadataDTO(mxid="MXID_RIGHT", notes="右相机"),
        },
    )
    
    # 便捷访问硬件配置
    print("\n硬件配置快捷访问:")
    print(f"  模型路径: {oak_module.model_path}")
    print(f"  硬件帧率: {oak_module.hardware_fps}")
    print(f"  置信度阈值: {oak_module.confidence_threshold}")
    
    # 便捷访问设备绑定
    print("\n设备绑定快捷访问:")
    print(f"  激活角色数: {oak_module.active_role_count}")
    print(f"  总角色数: {oak_module.total_role_count}")
    print(f"  可用角色: {[r.value for r in oak_module.available_roles]}")
    
    # 查询特定角色
    print("\n角色查询:")
    for role in [DeviceRole.LEFT_CAMERA, DeviceRole.RIGHT_CAMERA]:
        has_device = oak_module.has_active_device(role)
        mxid = oak_module.get_active_mxid(role)
        metadata = oak_module.get_device_metadata(mxid) if mxid else None
        print(f"  {role.display_name}:")
        print(f"    - 有激活设备: {has_device}")
        print(f"    - MXid: {mxid}")
        print(f"    - 备注: {metadata.notes if metadata else '无'}")
    
    print()


def example_4_hierarchical_advantage():
    """示例4：层次化设计的优势"""
    print("=" * 80)
    print("示例4：层次化设计的优势")
    print("=" * 80)
    
    # 所有OAK相关的配置都在一个对象中
    oak_module = OAKModuleConfigDTO(
        hardware_config=OAKConfigDTO(
            model_path="/models/custom.blob",
            hardware_fps=25,
            confidence_threshold=0.8,
        ),
        role_bindings={
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                historical_mxids=["DEVICE_001"],
                active_mxid="DEVICE_001",
            ),
        },
    )
    
    print("\n✅ 优势展示：")
    print("\n1. 配置内聚 - 所有OAK相关配置在一起：")
    print(f"   - 硬件配置: {oak_module.hardware_config}")
    print(f"   - 设备绑定: {oak_module.role_bindings}")
    print(f"   - 设备元数据: {oak_module.device_metadata}")
    
    print("\n2. 访问便捷 - 通过统一接口：")
    print(f"   - 直接访问FPS: {oak_module.hardware_fps}")
    print(f"   - 直接访问模型: {oak_module.model_path}")
    print(f"   - 直接查询设备: {oak_module.get_active_mxid(DeviceRole.LEFT_CAMERA)}")
    
    print("\n3. 职责清晰 - OAK模块独立管理：")
    print(f"   - OAKModuleConfigDTO 封装了OAK的一切")
    print(f"   - 不依赖外部配置")
    print(f"   - 可独立验证和序列化")
    
    print("\n4. 易于扩展 - 添加新相机类型：")
    print(f"   - 创建 NewCameraModuleConfigDTO")
    print(f"   - 模仿 OAKModuleConfigDTO 的结构")
    print(f"   - 与其他模块平级管理")
    
    print()


def show_architecture_comparison():
    """展示架构对比"""
    print("\n" + "=" * 80)
    print("架构演进：平铺 → 层次化")
    print("=" * 80)
    
    print("\n【旧架构 - 平铺设计】")
    print("config = DeviceManagerConfigDTO(")
    print("    oak_config=...,           # OAK硬件配置")
    print("    role_bindings=...,        # 设备绑定 ❌ 分离")
    print("    device_metadata=...,      # 设备元数据 ❌ 分离")
    print("    display_config=...,")
    print(")")
    print("\n问题：OAK相关配置分散在多处")
    
    print("\n【新架构 - 层次化设计】")
    print("config = DeviceManagerConfigDTO(")
    print("    oak_module=OAKModuleConfigDTO(")
    print("        hardware_config=...,    # OAK硬件配置")
    print("        role_bindings=...,      # 设备绑定 ✅ 内聚")
    print("        device_metadata=...,    # 设备元数据 ✅ 内聚")
    print("    ),")
    print("    display_config=...,")
    print(")")
    print("\n✅ 优势：OAK相关配置内聚在OAKModuleConfigDTO中")
    print("=" * 80)


if __name__ == "__main__":
    example_1_basic_oak_module()
    example_2_complete_oak_module()
    example_3_convenient_access()
    example_4_hierarchical_advantage()
    show_architecture_comparison()

