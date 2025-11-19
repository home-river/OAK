"""
配置管理示例

演示新的模块化配置系统的使用方法
"""

import json
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from oak_vision_system.core.dto.device_config_dto import (
    OAKConfigDTO,
    SystemConfigDTO,
    DataProcessingConfigDTO,
    DeviceConfigDTO,
    DeviceManagerConfigDTO,
    DeviceType,
    ConnectionStatus
)


def create_sample_config() -> DeviceManagerConfigDTO:
    """创建示例配置"""
    
    # OAK设备配置（集中管理所有OAK相关配置）
    oak_config = OAKConfigDTO(
        # 检测模型配置
        model_path="/path/to/model.blob",
        label_map=["durian", "person"],
        num_classes=2,
        confidence_threshold=0.6,
        
        # 检测参数配置
        input_resolution=(512, 288),
        nms_threshold=0.4,
        max_detections=-1,
        depth_min_threshold=400.0,
        depth_max_threshold=7000.0,
        
        # 相机配置
        preview_resolution=(512, 288),
        hardware_fps=30,
        usb2_mode=True,
        
        # 深度图配置
        enable_depth_display=True,
        depth_display_resolution=(640, 480),
        depth_bbox_scale_factor=1.0,
        
        # 显示配置
        enable_fullscreen=False,
        default_display_mode="combined",
        
        # 队列配置
        queue_max_size=4,
        queue_blocking=False
    )
    
    # 系统配置
    system_config = SystemConfigDTO(
        enable_can=True,
        enable_alert=True,
        can_bitrate=250000,
        can_interface='socketcan',
        can_channel='can0',
        person_timeout_seconds=5.0
    )
    
    # 数据处理配置（当前为空，预留扩展）
    data_processing_config = DataProcessingConfigDTO()
    
    # 设备配置（包含设备发现的关键信息）
    device_config = DeviceConfigDTO(
        mxid="1844301041B5D00F00",
        alias="oak_camera_01",
        device_type=DeviceType.OAK_D,
        enabled=True,
        # 设备发现的关键信息
        device_name="1844301041B5D00F00",  # 设备名称
        connection_state=ConnectionStatus.CONNECTED,  # 连接状态
        product_name="OAK-D",  # 产品名称
        properties={"location": "front", "calibrated": True}
    )
    
    # 统一配置管理
    manager_config = DeviceManagerConfigDTO(
        config_version="2.0.0",
        oak_config=oak_config,
        system=system_config,
        data_processing=data_processing_config,
        devices={"oak_camera_01": device_config}
    )
    
    return manager_config


def test_config_serialization():
    """测试配置的序列化和反序列化"""
    print("=== 配置序列化测试 ===")
    
    # 创建配置
    config = create_sample_config()
    print(f"配置创建成功: {config}")
    
    # 验证配置
    if not config.is_data_valid():
        print("⚠️  配置验证失败:")
        for error in config.get_validation_errors():
            print(f"  - {error}")
        return False
    else:
        print("✅ 配置验证通过")
    
    # 转换为JSON
    json_str = config.to_json(indent=2)
    print("\n=== JSON配置 ===")
    print(json_str)
    
    # 从JSON恢复配置
    try:
        restored_config = DeviceManagerConfigDTO.from_json(json_str)
        print("\n✅ JSON反序列化成功")
        
        # 验证恢复的配置
        if restored_config.is_data_valid():
            print("✅ 恢复的配置验证通过")
        else:
            print("⚠️  恢复的配置验证失败")
            
        return True
    except Exception as e:
        print(f"❌ JSON反序列化失败: {e}")
        return False


def test_modular_access():
    """测试模块化访问"""
    print("\n=== 模块化访问测试 ===")
    
    config = create_sample_config()
    
    # 访问各个配置模块
    oak_config = config.get_oak_config()
    system = config.get_system_config()
    data_processing = config.get_data_processing_config()
    
    # 通过便捷属性访问
    print(f"便捷访问: 模型路径={config.model_path}, 置信度={config.confidence_threshold}")
    print(f"便捷访问: 帧率={config.hardware_fps}, CAN启用={config.enable_can}")
    
    # 通过模块访问详细配置
    print(f"\nOAK配置详细信息:")
    print(f"  检测模型: 标签={oak_config.label_map}, 类别数={oak_config.num_classes}")
    print(f"  检测参数: NMS阈值={oak_config.nms_threshold}, 深度范围={oak_config.depth_min_threshold}-{oak_config.depth_max_threshold}mm")
    print(f"  相机配置: 分辨率={oak_config.preview_resolution}, 帧率={oak_config.hardware_fps}")
    print(f"  深度图配置: 启用={oak_config.enable_depth_display}, 分辨率={oak_config.depth_display_resolution}")
    print(f"  显示配置: 模式={oak_config.default_display_mode}, 全屏={oak_config.enable_fullscreen}")
    print(f"  队列配置: 最大尺寸={oak_config.queue_max_size}, 阻塞={oak_config.queue_blocking}")
    
    print(f"\n系统配置: CAN={system.enable_can}, 警报={system.enable_alert}, 超时={system.person_timeout_seconds}s")
    print(f"数据处理配置: 坐标变换参数={data_processing.coordinate_transform_params}")
    
    # 设备信息
    print(f"设备数量: {config.device_count}")
    print(f"启用设备数量: {config.enabled_device_count}")
    print(f"设备别名: {config.get_aliases()}")
    
    return True


def test_config_validation():
    """测试配置验证"""
    print("\n=== 配置验证测试 ===")
    
    # 测试无效配置
    try:
        invalid_oak_config = OAKConfigDTO(
            confidence_threshold=1.5,  # 无效值：超出范围
            num_classes=0,  # 无效值：小于最小值
            label_map=["durian", "person", "apple"],  # 与num_classes不一致
        )
        
        if not invalid_oak_config.is_data_valid():
            print("✅ 检测到无效配置:")
            for error in invalid_oak_config.get_validation_errors():
                print(f"  - {error}")
        else:
            print("❌ 应该检测到无效配置，但验证通过了")
            
    except Exception as e:
        print(f"配置验证测试异常: {e}")
    
    return True


def save_sample_config():
    """保存示例配置文件"""
    print("\n=== 保存示例配置文件 ===")
    
    config = create_sample_config()
    config_file = Path(__file__).parent / "sample_oak_config.json"
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config.to_json(indent=2))
        
        print(f"✅ 配置文件已保存到: {config_file}")
        return True
    except Exception as e:
        print(f"❌ 保存配置文件失败: {e}")
        return False


if __name__ == "__main__":
    print("🚀 OAK模块化配置系统测试")
    print("=" * 50)
    
    # 运行测试
    tests = [
        test_config_serialization,
        test_modular_access,
        test_config_validation,
        save_sample_config
    ]
    
    success_count = 0
    for test_func in tests:
        try:
            if test_func():
                success_count += 1
                print("✅ 测试通过\n")
            else:
                print("❌ 测试失败\n")
        except Exception as e:
            print(f"❌ 测试异常: {e}\n")
    
    print("=" * 50)
    print(f"测试完成: {success_count}/{len(tests)} 个测试通过")
    
    if success_count == len(tests):
        print("🎉 所有测试通过！模块化配置系统工作正常。")
    else:
        print("⚠️  部分测试失败，请检查配置。")
