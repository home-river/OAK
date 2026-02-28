"""
系统配置管理器使用示例

演示 SystemConfigManager 作为配置中心的设计理念：
- 统一管理所有模块的配置
- 配置在程序对象和文件之间的流通
- 为不同模块提供配置分发接口
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from oak_vision_system.modules.data_collector import SystemConfigManager
from oak_vision_system.core.dto.device_config_dto import OAKConfigDTO, SystemConfigDTO


def demonstrate_config_center_pattern():
    """
    演示：配置管理器作为系统配置中心
    """
    print("=" * 60)
    print("系统配置管理器 - 配置中心模式演示")
    print("=" * 60)
    
    # ========== 1. 初始化配置中心 ==========
    print("\n1. 初始化配置中心（自动加载或创建配置）")
    config_manager = SystemConfigManager("config/system_config.json")
    print("   ✅ 配置中心已就绪")
    
    # ========== 2. 为OAK模块提供配置 ==========
    print("\n2. OAK Pipeline模块获取配置")
    oak_config = config_manager.get_oak_config()
    print(f"   - 模型路径: {oak_config.model_path or '默认模型'}")
    print(f"   - 置信度阈值: {oak_config.confidence_threshold}")
    print(f"   - 硬件帧率: {oak_config.hardware_fps}")
    print(f"   - 标签数: {len(oak_config.label_map)}")
    print("   💡 OAK模块可以直接使用这些配置初始化Pipeline")
    
    # ========== 3. 为CAN模块提供配置 ==========
    print("\n3. CAN通信模块获取配置")
    system_config = config_manager.get_system_config()
    print(f"   - CAN启用: {system_config.enable_can}")
    print(f"   - CAN接口: {system_config.can_interface}")
    print(f"   - 波特率: {system_config.can_bitrate}")
    print("   💡 CAN模块可以直接使用这些配置初始化总线")
    
    # ========== 4. 为设备管理模块提供配置 ==========
    print("\n4. 设备管理模块获取设备列表")
    devices = config_manager.list_devices()
    enabled_devices = config_manager.list_enabled_devices()
    print(f"   - 总设备数: {len(devices)}")
    print(f"   - 启用设备数: {len(enabled_devices)}")
    if enabled_devices:
        for device in enabled_devices:
            print(f"     • {device.mxid[:20]}... ({device.device_type.value})")
    print("   💡 设备管理模块知道要初始化哪些设备")
    
    # ========== 5. 模块修改配置并保存 ==========
    print("\n5. 各模块修改配置示例")
    
    # OAK模块调整参数
    print("   [OAK模块] 调整检测参数...")
    oak_config.confidence_threshold = 0.7
    oak_config.hardware_fps = 30
    
    # CAN模块启用通信
    print("   [CAN模块] 启用CAN通信...")
    system_config.enable_can = True
    system_config.can_bitrate = 500000
    
    # 设备模块禁用某个设备
    if devices:
        print("   [设备模块] 禁用一个设备...")
        devices[0].enabled = False
    
    # 统一保存所有修改
    print("\n6. 保存所有模块的配置修改")
    config_manager.save_config()
    print("   ✅ 所有配置已保存（自动备份）")
    
    # ========== 7. 配置分发流程总结 ==========
    print("\n" + "=" * 60)
    print("配置分发架构总结")
    print("=" * 60)
    print("""
    ┌─────────────────────────────────────────┐
    │      SystemConfigManager               │
    │      (配置中心)                         │
    ├─────────────────────────────────────────┤
    │  • 管理所有模块配置                      │
    │  • 序列化/反序列化                       │
    │  • 配置备份/恢复                         │
    └─────────────────────────────────────────┘
              ↓ 配置分发接口 ↓
    ┌──────────┬──────────┬──────────┬──────────┐
    │ OAK模块  │ CAN模块  │数据处理  │ 设备管理 │
    │          │          │  模块    │  模块    │
    ├──────────┼──────────┼──────────┼──────────┤
    │get_oak   │get_system│get_data  │list_     │
    │_config() │_config() │_proc...  │devices() │
    └──────────┴──────────┴──────────┴──────────┘
    
    优势：
    ✅ 统一配置源：所有模块从同一个配置中心获取配置
    ✅ 自动持久化：配置修改后统一保存到文件
    ✅ 模块解耦：各模块只需要知道配置接口，不关心存储
    ✅ 配置同步：所有模块的配置自动保持一致
    """)


def demonstrate_multi_module_coordination():
    """
    演示：多模块协同配置管理
    """
    print("\n" + "=" * 60)
    print("多模块协同配置示例")
    print("=" * 60)
    
    config_manager = SystemConfigManager("config/system_config.json")
    
    # 模拟不同模块的配置需求
    print("\n场景：根据运行模式调整所有模块配置")
    
    def switch_to_performance_mode():
        """切换到性能模式"""
        print("\n➤ 切换到性能模式...")
        
        # OAK模块：提高帧率，降低分辨率
        oak_config = config_manager.get_oak_config()
        oak_config.hardware_fps = 60
        oak_config.preview_resolution = (416, 416)
        oak_config.confidence_threshold = 0.6
        print("  [OAK] 帧率→60, 分辨率→416x416")
        
        # 系统模块：提高CAN波特率
        system_config = config_manager.get_system_config()
        system_config.can_bitrate = 1000000
        print("  [CAN] 波特率→1Mbps")
        
        # 保存
        config_manager.save_config(backup=True)
        print("  ✅ 性能模式配置已保存")
    
    def switch_to_accuracy_mode():
        """切换到精度模式"""
        print("\n➤ 切换到精度模式...")
        
        # OAK模块：降低帧率，提高分辨率
        oak_config = config_manager.get_oak_config()
        oak_config.hardware_fps = 15
        oak_config.preview_resolution = (640, 640)
        oak_config.confidence_threshold = 0.8
        print("  [OAK] 帧率→15, 分辨率→640x640")
        
        # 系统模块：标准波特率
        system_config = config_manager.get_system_config()
        system_config.can_bitrate = 500000
        print("  [CAN] 波特率→500Kbps")
        
        # 保存
        config_manager.save_config(backup=True)
        print("  ✅ 精度模式配置已保存")
    
    # 演示切换
    switch_to_performance_mode()
    switch_to_accuracy_mode()
    
    print("\n💡 配置管理器协调多个模块的配置，实现一键切换运行模式")


if __name__ == "__main__":
    try:
        # 演示1：配置中心模式
        demonstrate_config_center_pattern()
        
        # 演示2：多模块协同
        demonstrate_multi_module_coordination()
        
        print("\n" + "=" * 60)
        print("✅ 演示完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
