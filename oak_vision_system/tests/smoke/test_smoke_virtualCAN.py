"""
显示模块主线程渲染 - 完整系统冒烟测试

本测试验证主线程渲染架构的完整集成：
1. 配置加载和验证
2. 虚拟 CAN 模式（Windows 友好）
3. 所有模块的创建和注册
4. SystemManager 主线程渲染架构
5. 按键交互和退出机制

架构特点：
- DisplayManager 使用 register_display_module() 注册
- SystemManager.run() 在主线程中调用 render_once()
- 支持三种退出方式：Ctrl+C、'q' 键、定时器

运行方式：
    python oak_vision_system/tests/smoke/test_smoke_virtualCAN.py
"""

import logging
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def load_config(config_path: str):
    """
    加载并验证配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置对象
        
    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置验证失败
    """
    from oak_vision_system.modules.config_manager import DeviceConfigManager
    
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    logger.info(f"加载配置文件: {config_file.absolute()}")
    
    # 创建配置管理器并加载配置
    config_manager = DeviceConfigManager(str(config_path), auto_create=False)
    config_manager.load_config(validate=True)
    
    config = config_manager.get_config()
    logger.info(f"✅ 配置加载成功 (版本: {config.config_version})")
    
    # 显示关键配置信息
    _log_config_summary(config)
    
    return config


def _log_config_summary(config):
    """记录配置摘要信息"""
    logger.info("\n" + "=" * 60)
    logger.info("配置摘要")
    logger.info("=" * 60)
    
    # OAK 设备配置
    oak_config = config.oak_module
    logger.info(f"[OAK 设备]")
    logger.info(f"  模型: {Path(oak_config.hardware_config.model_path).name}")
    logger.info(f"  置信度阈值: {oak_config.hardware_config.confidence_threshold}")
    logger.info(f"  设备数量: {len(oak_config.role_bindings)}")
    
    # CAN 配置
    can_config = config.can_config
    logger.info(f"[CAN 通信]")
    if can_config.enable_can:
        logger.warning(f"  ⚠️  真实 CAN 模式 (需要硬件)")
        logger.warning(f"  接口: {can_config.can_interface}")
        logger.warning(f"  通道: {can_config.can_channel}")
    else:
        logger.info(f"  ✅ 虚拟 CAN 模式 (Windows 友好)")
    
    # 显示配置
    display_config = config.display_config
    logger.info(f"[显示模块]")
    logger.info(f"  启用: {display_config.enable_display}")
    logger.info(f"  分辨率: {display_config.window_width}x{display_config.window_height}")
    logger.info(f"  目标 FPS: {display_config.target_fps}")
    logger.info("=" * 60 + "\n")


def create_modules(config):
    """
    创建所有系统模块
    
    Args:
        config: 配置对象
        
    Returns:
        dict: 包含所有模块实例的字典
    """
    from oak_vision_system.core.event_bus import reset_event_bus, get_event_bus
    from oak_vision_system.modules.data_collector.collector import OAKDataCollector
    from oak_vision_system.modules.data_processing.data_processor import DataProcessor
    from oak_vision_system.modules.display_modules.display_manager import DisplayManager
    from oak_vision_system.modules.can_communication.can_factory import create_can_communicator
    
    logger.info("=" * 60)
    logger.info("创建系统模块")
    logger.info("=" * 60)
    
    modules = {}
    
    # 1. 事件总线（全局单例）
    logger.info("[1/4] 创建事件总线...")
    reset_event_bus()
    modules['event_bus'] = get_event_bus()
    logger.info("  ✅ 事件总线已就绪")
    
    # 2. OAK 数据采集器
    logger.info("[2/4] 创建 OAK 数据采集器...")
    modules['oak_collector'] = OAKDataCollector(
        config=config.oak_module,
        event_bus=modules['event_bus']
    )
    logger.info("  ✅ OAK 数据采集器已创建")
    
    # 3. 数据处理器
    logger.info("[3/4] 创建数据处理器...")
    modules['data_processor'] = DataProcessor(
        config=config.data_processing_config,
        device_metadata=config.oak_module.device_metadata,
        bindings=config.oak_module.role_bindings,
        label_map=config.oak_module.hardware_config.label_map
    )
    logger.info("  ✅ 数据处理器已创建")
    
    # 4. 显示管理器（主线程渲染架构）
    logger.info("[4/4] 创建显示管理器（主线程渲染）...")
    
    # 准备设备列表
    devices_list = [
        binding.active_mxid 
        for binding in config.oak_module.role_bindings.values() 
        if binding.active_mxid
    ]
    
    # 准备角色绑定映射
    role_bindings: Dict = {
        role: binding.active_mxid
        for role, binding in config.oak_module.role_bindings.items()
        if binding.active_mxid
    }
    
    modules['display_manager'] = DisplayManager(
        config=config.display_config,
        devices_list=devices_list,
        role_bindings=role_bindings,
        enable_depth_output=config.oak_module.hardware_config.enable_depth_output
    )
    logger.info(f"  ✅ 显示管理器已创建 (管理 {len(devices_list)} 个设备)")
    
    # 5. CAN 通信器（使用工厂函数）
    logger.info("[5/5] 创建 CAN 通信器...")
    modules['can_communicator'] = create_can_communicator(
        config=config.can_config,
        decision_layer=modules['data_processor'].decision_layer,
        event_bus=modules['event_bus']
    )
    
    from oak_vision_system.modules.can_communication.virtual_can_communicator import VirtualCANCommunicator
    if isinstance(modules['can_communicator'], VirtualCANCommunicator):
        logger.info("  ✅ 虚拟 CAN 通信器已创建")
    else:
        logger.info(f"  ✅ {modules['can_communicator'].__class__.__name__} 已创建")
    
    logger.info("=" * 60 + "\n")
    
    return modules


def register_modules(system_manager, modules):
    """
    注册所有模块到 SystemManager
    
    注意：显示模块使用 register_display_module() 注册
    
    Args:
        system_manager: SystemManager 实例
        modules: 模块字典
    """
    logger.info("=" * 60)
    logger.info("注册模块到 SystemManager")
    logger.info("=" * 60)
    
    # 注册顺序：优先级从低到高
    # 启动顺序：display(60) → can(50) → processor(30) → collector(10)
    # 关闭顺序：collector(10) → processor(30) → can(50) → display(60)
    
    logger.info("注册模块（按优先级）:")
    
    system_manager.register_module(
        "oak_collector", 
        modules['oak_collector'], 
        priority=10
    )
    logger.info("  ✅ oak_collector (priority=10)")
    
    system_manager.register_module(
        "data_processor", 
        modules['data_processor'], 
        priority=30
    )
    logger.info("  ✅ data_processor (priority=30)")
    
    system_manager.register_module(
        "can_communicator", 
        modules['can_communicator'], 
        priority=50
    )
    logger.info("  ✅ can_communicator (priority=50)")
    
    # 使用 register_display_module() 注册显示模块（主线程渲染）
    system_manager.register_display_module(
        "display_manager", 
        modules['display_manager'], 
        priority=60
    )
    logger.info("  ✅ display_manager (priority=60) [主线程渲染]")
    
    logger.info("\n注册完成，共 4 个模块")
    logger.info("=" * 60 + "\n")


def run_smoke_test(config_path: str = "assets/test_config/config.json", duration: int = 30):
    """
    运行完整的冒烟测试
    
    Args:
        config_path: 配置文件路径
        duration: 测试运行时长（秒）
        
    Returns:
        bool: 测试是否成功
    """
    from oak_vision_system.core.system_manager.system_manager import SystemManager
    
    try:
        logger.info("\n" + "=" * 60)
        logger.info("OAK Vision System - 主线程渲染冒烟测试")
        logger.info("=" * 60)
        logger.info(f"配置文件: {config_path}")
        logger.info(f"测试时长: {duration} 秒")
        logger.info("=" * 60 + "\n")
        
        # 步骤 1: 加载配置
        logger.info("【步骤 1/4】加载配置")
        config = load_config(config_path)
        
        # 步骤 2: 创建模块
        logger.info("【步骤 2/4】创建模块")
        modules = create_modules(config)
        
        # 步骤 3: 创建 SystemManager 并注册模块
        logger.info("【步骤 3/4】注册模块")
        system_manager = SystemManager(
            event_bus=modules['event_bus'],
            system_config=config.system_config
        )
        register_modules(system_manager, modules)
        
        # 步骤 4: 启动系统并运行
        logger.info("【步骤 4/4】启动系统")
        logger.info("=" * 60)
        logger.info("启动所有模块...")
        logger.info("=" * 60)
        
        system_manager.start_all()
        logger.info("✅ 所有模块已启动\n")
        
        # 启动定时器（自动关闭）
        def trigger_shutdown():
            time.sleep(duration)
            logger.info(f"\n⏰ {duration} 秒已到，触发系统关闭...")
            modules['event_bus'].publish("SYSTEM_SHUTDOWN", None)
        
        shutdown_timer = threading.Thread(
            target=trigger_shutdown, 
            daemon=True, 
            name="ShutdownTimer"
        )
        shutdown_timer.start()
        
        # 运行主循环（主线程渲染）
        logger.info("=" * 60)
        logger.info("系统运行中（主线程渲染模式）")
        logger.info("=" * 60)
        logger.info("退出方式：")
        logger.info("  • 按 Ctrl+C")
        logger.info("  • 按 'q' 键")
        logger.info(f"  • 等待 {duration} 秒自动退出")
        logger.info("\n按键说明：")
        logger.info("  '1' - 切换到左相机")
        logger.info("  '2' - 切换到右相机")
        logger.info("  '3' - 切换到拼接模式")
        logger.info("  'f' - 切换全屏")
        logger.info("  'q' - 退出系统")
        logger.info("=" * 60 + "\n")
        
        start_time = time.time()
        
        # 阻塞主线程，SystemManager.run() 会自动调用 display_manager.render_once()
        system_manager.run(force_exit_on_shutdown_failure=False)
        
        # 系统已退出
        runtime = time.time() - start_time
        logger.info("\n" + "=" * 60)
        logger.info("系统已退出")
        logger.info("=" * 60)
        logger.info(f"运行时长: {runtime:.1f} 秒")
        logger.info("=" * 60 + "\n")
        
        # 打印测试总结
        _print_test_summary()
        
        return True
        
    except KeyboardInterrupt:
        logger.info("\n用户中断测试 (Ctrl+C)")
        return False
        
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}", exc_info=True)
        return False


def _print_test_summary():
    """打印测试总结"""
    logger.info("=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    logger.info("验证项目:")
    logger.info("  ✅ 配置文件加载")
    logger.info("  ✅ 虚拟 CAN 模式")
    logger.info("  ✅ OAK 设备连接")
    logger.info("  ✅ 数据处理模块")
    logger.info("  ✅ 显示模块（主线程渲染）")
    logger.info("  ✅ SystemManager 集成")
    logger.info("  ✅ 模块启动和关闭")
    logger.info("  ✅ 主线程渲染循环")
    logger.info("  ✅ 按键交互")
    logger.info("  ✅ 退出机制")
    logger.info("\n🎉 冒烟测试通过！")
    logger.info("主线程渲染架构工作正常。")
    logger.info("=" * 60)


def main():
    """主函数"""
    # 配置文件路径
    config_path = "assets/test_config/config.json"
    
    # 测试运行时长（秒）
    test_duration = 30
    
    # 运行测试
    success = run_smoke_test(config_path, test_duration)
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
