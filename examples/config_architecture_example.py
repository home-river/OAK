"""
配置架构示例：展示重构后的平级配置设计

重构前问题：
- OAK配置混杂显示配置
- 队列配置散落在OAK配置中
- 职责不清晰

重构后优势：
- OAK配置专注于硬件（检测、相机、深度）
- 显示配置独立管理所有UI相关
- 系统配置管理队列、日志等通用功能
- 各模块平级管理，职责清晰
"""

from oak_vision_system.core.dto.config_dto import (
    DeviceManagerConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    DeviceMetadataDTO,
    OAKConfigDTO,
    OAKModuleConfigDTO,
    DataProcessingConfigDTO,
    CANConfigDTO,
    DisplayConfigDTO,
    SystemConfigDTO,
)


def create_example_config():
    """创建示例配置：展示新的平级架构"""
    
    # ========== 1. OAK硬件配置（纯粹的硬件参数）==========
    oak_config = OAKConfigDTO(
        # 检测模型
        model_path="/path/to/model.blob",
        label_map=["durian", "person"],
        confidence_threshold=0.6,
        
        # 相机参数
        rgb_resolution=(1920, 1080),
        preview_resolution=(640, 480),
        hardware_fps=20,
        usb2_mode=True,
        
        # 深度计算
        enable_depth_output=True,
        depth_resolution=(640, 480),
        depth_min_threshold=400.0,
        depth_max_threshold=6000.0,
        median_filter=5,
        left_right_check=True,
        
        # Pipeline队列配置
        queue_max_size=4,
        queue_blocking=False,
    )
    
    # ========== 2. 显示配置（所有UI相关）==========
    display_config = DisplayConfigDTO(
        # 窗口配置
        enable_display=True,
        default_display_mode="rgb",
        enable_fullscreen=False,
        window_width=1280,
        window_height=720,
        window_position_x=0,
        window_position_y=0,
        
        # 渲染参数
        target_fps=20,
        
        # 叠加信息
        show_detection_boxes=True,
        show_labels=True,
        show_confidence=True,
        show_coordinates=True,
        show_fps=True,
        show_device_info=True,
        
        # 深度图显示
        normalize_depth=True,
        
        # 检测框样式
        bbox_thickness=2,
        text_scale=0.6,
        bbox_color_by_label=True,
    )
    
    # ========== 3. 系统配置（日志、性能等）==========
    system_config = SystemConfigDTO(
        # 日志配置
        log_level="INFO",
        log_to_file=True,
        log_file_path="./logs/oak_system.log",
        log_max_size_mb=100,
        log_backup_count=7,
        
        # 性能配置
        max_worker_threads=4,
        enable_profiling=False,
        
        # 系统行为
        auto_reconnect=True,
        reconnect_interval=5.0,
        max_reconnect_attempts=10,
        graceful_shutdown_timeout=5.0,
    )
    
    # ========== 4. 数据处理配置 ==========
    data_processing_config = DataProcessingConfigDTO(
        enable_data_logging=False,
        processing_thread_priority=5,
        person_timeout_seconds=5.0,
    )
    
    # ========== 5. CAN配置 ==========
    can_config = CANConfigDTO(
        enable_can=False,  # 暂不启用
    )
    
    # ========== 6. 设备角色绑定 ==========
    left_binding = DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        historical_mxids=["14442C10D13F0AD700"],
        last_active_mxid="14442C10D13F0AD700",
    )
    
    right_binding = DeviceRoleBindingDTO(
        role=DeviceRole.RIGHT_CAMERA,
        historical_mxids=["14442C10D13F0AD701"],
        last_active_mxid="14442C10D13F0AD701",
    )
    
    left_metadata = DeviceMetadataDTO(
        mxid="14442C10D13F0AD700",
        product_name="OAK-D",
        notes="左侧相机，用于检测左边区域",
    )
    
    right_metadata = DeviceMetadataDTO(
        mxid="14442C10D13F0AD701",
        product_name="OAK-D",
        notes="右侧相机，用于检测右边区域",
    )
    
    # ========== 7. OAK模块配置（硬件+设备绑定内聚）==========
    oak_module = OAKModuleConfigDTO(
        hardware_config=oak_config,
        role_bindings={
            DeviceRole.LEFT_CAMERA: left_binding,
            DeviceRole.RIGHT_CAMERA: right_binding,
        },
        device_metadata={
            "14442C10D13F0AD700": left_metadata,
            "14442C10D13F0AD701": right_metadata,
        },
    )
    
    # ========== 8. 顶层配置（平级组合，层次清晰）==========
    config = DeviceManagerConfigDTO(
        config_version="2.0.0",
        
        # 功能模块配置（平级，各自内聚）
        oak_module=oak_module,
        display_config=display_config,
        system_config=system_config,
        data_processing_config=data_processing_config,
        can_config=can_config,
    )
    
    return config


def demonstrate_architecture():
    """演示配置架构的优势"""
    
    print("=" * 80)
    print("配置架构演示：平级设计，职责清晰")
    print("=" * 80)
    
    config = create_example_config()
    
    # 验证配置
    if not config.validate():
        print("❌ 配置验证失败：")
        for error in config.get_validation_errors():
            print(f"  - {error}")
        return
    
    print("✅ 配置验证通过！\n")
    
    # ========== 展示架构优势 ==========
    
    print("1. OAK模块配置（硬件+设备绑定内聚）：")
    print(f"   硬件配置:")
    print(f"   - 模型路径: {config.oak_module.hardware_config.model_path}")
    print(f"   - 相机分辨率: {config.oak_module.hardware_config.rgb_resolution}")
    print(f"   - 硬件帧率: {config.oak_module.hardware_config.hardware_fps} fps")
    print(f"   - 深度范围: {config.oak_module.hardware_config.depth_min_threshold}-{config.oak_module.hardware_config.depth_max_threshold}mm")
    print(f"   - Pipeline队列: {config.oak_module.hardware_config.queue_max_size}")
    print(f"   设备绑定:")
    print(f"   - 激活角色数: {config.oak_module.active_role_count}")
    print(f"   - 总角色数: {config.oak_module.total_role_count}")
    print()
    
    print("2. 显示配置（独立UI管理）：")
    print(f"   - 显示模式: {config.display_config.default_display_mode}")
    print(f"   - 窗口大小: {config.display_config.window_width}x{config.display_config.window_height}")
    print(f"   - 窗口位置: ({config.display_config.window_position_x}, {config.display_config.window_position_y})")
    print(f"   - 目标FPS: {config.display_config.target_fps}")
    print(f"   - 深度归一化: {'启用' if config.display_config.normalize_depth else '禁用'}")
    print()
    
    print("3. 系统配置（应用层通用功能）：")
    print(f"   - 日志级别: {config.system_config.log_level}")
    print(f"   - 日志文件: {config.system_config.log_file_path}")
    print(f"   - 工作线程: {config.system_config.max_worker_threads}")
    print(f"   - 自动重连: {'是' if config.system_config.auto_reconnect else '否'}")
    print()
    
    print("4. 数据处理配置：")
    print(f"   - 坐标变换配置数: {len(config.data_processing_config.coordinate_transforms)}")
    print(f"   - 滤波器类型: {config.data_processing_config.filter_config.filter_type.value}")
    print(f"   - 数据日志: {'启用' if config.data_processing_config.enable_data_logging else '禁用'}")
    print()
    
    print("5. CAN配置：")
    print(f"   - CAN通信: {'启用' if config.can_config.enable_can else '禁用'}")
    print()
    
    print("6. 便捷访问（委托模式）：")
    print(f"   通过顶层配置直接访问OAK模块:")
    for role in [DeviceRole.LEFT_CAMERA, DeviceRole.RIGHT_CAMERA]:
        mxid = config.get_active_mxid(role)  # 委托给oak_module
        metadata = config.get_device_metadata(mxid) if mxid else None  # 委托给oak_module
        if metadata:
            print(f"   - {role.display_name}: {metadata.notes}")
    
    print("\n" + "=" * 80)
    print("架构优势总结：")
    print("=" * 80)
    print("✅ 职责分离：OAK专注硬件，Display专注UI，System管理通用")
    print("✅ 易于维护：修改显示参数不影响OAK配置")
    print("✅ 清晰直观：配置层次一目了然")
    print("✅ 易于扩展：新增模块配置只需添加同级配置类")
    print("=" * 80)


def compare_old_vs_new():
    """对比旧架构 vs 新架构"""
    
    print("\n" + "=" * 80)
    print("架构对比：重构前 vs 重构后")
    print("=" * 80)
    
    print("\n【重构前的问题】")
    print("-" * 80)
    print("DeviceManagerConfigDTO (平铺设计)")
    print("  ├─ role_bindings ❓       (OAK相关，但在顶层)")
    print("  ├─ device_metadata ❓     (OAK相关，但在顶层)")
    print("  ├─ oak_config ✅          (OAK硬件配置)")
    print("  ├─ display_config ✅")
    print("  ├─ can_config ✅")
    print("  └─ system_config ✅")
    print("\n问题1：设备绑定和OAK配置分离，不内聚")
    print("问题2：顶层配置直接管理设备绑定细节")
    print("问题3：OAKConfigDTO和DisplayConfigDTO配置重复")
    
    print("\n【重构后的架构】")
    print("-" * 80)
    print("DeviceManagerConfigDTO (层次化设计)")
    print("  │")
    print("  └─ 功能模块配置（平级，内聚）")
    print("      │")
    print("      ├─ OAKModuleConfigDTO   ✅ OAK模块完整配置")
    print("      │   ├─ hardware_config")
    print("      │   │   ├─ 检测模型配置")
    print("      │   │   ├─ 相机硬件参数")
    print("      │   │   ├─ 深度计算参数")
    print("      │   │   └─ Pipeline队列配置")
    print("      │   └─ device_binding")
    print("      │       ├─ role_bindings")
    print("      │       └─ device_metadata")
    print("      │")
    print("      ├─ DisplayConfigDTO     ✅ 所有显示与UI")
    print("      │   ├─ 窗口配置")
    print("      │   ├─ 渲染参数")
    print("      │   ├─ 深度图显示")
    print("      │   └─ 叠加信息")
    print("      │")
    print("      ├─ SystemConfigDTO      ✅ 应用层系统配置")
    print("      ├─ DataProcessingConfigDTO ✅ 数据处理")
    print("      └─ CANConfigDTO         ✅ CAN通信")
    print("\n✅ 优势：")
    print("   1. OAK相关配置内聚：硬件+设备绑定在同一模块")
    print("   2. 层次清晰：相关概念归类到一起")
    print("   3. 职责明确：每个模块管理自己的完整功能")
    print("   4. 易于维护：修改OAK相关配置只需关注OAKModuleConfigDTO")
    print("   5. 便于扩展：新增相机类型只需创建新的ModuleConfigDTO")
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_architecture()
    compare_old_vs_new()

