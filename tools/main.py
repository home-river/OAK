"""
OAK Vision System - 主程序入口（测试版本）

完整的系统启动脚本，包括：
- 真实 OAK 设备连接
- 数据采集模块（Collector）
- 数据处理模块（DataProcessor）
- 显示模块（DisplayManager）
- 通信模块（虚拟 CAN）
- 系统管理器（SystemManager）

使用方式：
    python tools/main.py
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径（必须在任何 oak_vision_system 导入之前）
sys.path.insert(0, str(Path(__file__).parent.parent))

from oak_vision_system.core.system_manager import SystemManager
from oak_vision_system.core.event_bus import get_event_bus
from oak_vision_system.modules.config_manager.device_config_manager import DeviceConfigManager
from oak_vision_system.modules.data_collector.collector import OAKDataCollector
from oak_vision_system.modules.data_processing.data_processor import DataProcessor
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.modules.can_communication.can_factory import create_can_communicator


# ==================== 配置参数 ====================
# 固定配置，无需命令行参数

# 配置文件路径（相对于项目根目录）
CONFIG_PATH = "assets/test_config/config.json"

# 是否使用虚拟 CAN（测试用）
USE_VIRTUAL_CAN = True

# 是否启用调试模式
DEBUG_MODE = True

# 是否禁用显示（无头模式）
NO_DISPLAY = False


def setup_logging():
    """配置日志系统"""
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("oak_vision_system.log", mode='a', encoding="utf-8")
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("OAK Vision System 启动")
    logger.info("=" * 60)
    
    return logger


def load_configuration(config_path: str, logger: logging.Logger):
    """加载系统配置"""
    logger.info(f"加载配置文件: {config_path}")
    
    # 检查配置文件是否存在
    if not Path(config_path).exists():
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    
    try:
        config_manager = DeviceConfigManager(config_path=config_path, auto_create=False)
        config_manager.load_config(validate=True)

        logger.info("[OK] 配置加载成功")
        return config_manager
    except Exception as e:
        logger.error(f"[ERR] 配置加载失败: {e}", exc_info=True)
        sys.exit(1)


def create_modules(config_manager: DeviceConfigManager, logger: logging.Logger):
    """创建所有模块实例"""
    logger.info("创建模块实例...")
    
    modules = {}
    
    try:
        # 1. 创建数据采集模块（Collector）
        logger.info("  - 创建 OAKDataCollector...")
        oak_config = config_manager.get_oak_module_config()
        device_metadata = oak_config.device_metadata

        collector = OAKDataCollector(
            config=oak_config,
            available_devices=list(device_metadata.values())
        )
        modules['collector'] = collector
        logger.info("    [OK] OAKDataCollector 创建成功")
        
        # 2. 创建数据处理模块（DataProcessor）
        logger.info("  - 创建 DataProcessor...")
        data_processing_config = config_manager.get_data_processing_config()
        bindings = oak_config.role_bindings

        processor = DataProcessor(
            config=data_processing_config,
            device_metadata=device_metadata,
            bindings=bindings,
            label_map=list(getattr(oak_config.hardware_config, "label_map", []) or []),
        )
        modules['processor'] = processor
        logger.info("    [OK] DataProcessor 创建成功")
        
        # 3. 创建显示模块（DisplayManager）
        if not NO_DISPLAY:
            logger.info("  - 创建 DisplayManager...")
            display_config = config_manager.get_display_config()
            role_bindings = config_manager.get_active_role_mxid_map()

            display_manager = DisplayManager(
                config=display_config,
                devices_list=list(device_metadata.keys()),
                role_bindings=role_bindings,
                enable_depth_output=bool(getattr(oak_config.hardware_config, "enable_depth_output", False)),
            )
            modules['display'] = display_manager
            logger.info("    [OK] DisplayManager 创建成功")
        else:
            logger.info("  - 跳过 DisplayManager（无头模式）")
        
        # 4. 创建通信模块（CAN 通信器）
        logger.info("  - 创建 CAN 通信器...")
        can_config = config_manager.get_can_config()

        # 如果指定了虚拟 CAN，使用 with_update 创建新配置
        if USE_VIRTUAL_CAN:
            logger.info("    使用虚拟 CAN 模式（enable_can=False）")
            can_config = can_config.with_updates(enable_can=False)

        communicator = create_can_communicator(
            config=can_config,
            decision_layer=processor.decision_layer,
            event_bus=get_event_bus(),
        )
        modules['can'] = communicator
        logger.info("    [OK] CAN 通信器创建成功")
        
        logger.info("[OK] 所有模块创建完成")
        return modules
        
    except Exception as e:
        logger.error(f"[ERR] 模块创建失败: {e}", exc_info=True)
        sys.exit(1)


def register_modules(system_manager : SystemManager, modules, logger):
    """注册模块到 SystemManager"""
    logger.info("注册模块到 SystemManager...")
    
    try:
        # 按优先级注册模块
        # 优先级：数据源(10) < 处理器(30) < 显示(50) < 通信(70)
        
        # 1. 数据采集模块（优先级 10）
        system_manager.register_module(
            "collector",
            modules['collector'],
            priority=10
        )
        logger.info("  [OK] Collector 已注册（优先级: 10）")
        
        # 2. 数据处理模块（优先级 30）
        system_manager.register_module(
            "processor",
            modules['processor'],
            priority=30
        )
        logger.info("  [OK] Processor 已注册（优先级: 30）")
        
        # 3. 显示模块（优先级 50，需要主线程渲染）
        if 'display' in modules:
            system_manager.register_display_module(
                "display",
                modules['display'],
                priority=50
            )
            logger.info("  [OK] Display 已注册（优先级: 50，主线程渲染）")
        
        # 4. 通信模块（优先级 70）
        system_manager.register_module(
            "can",
            modules['can'],
            priority=70
        )
        logger.info("  [OK] CAN 已注册（优先级: 70）")
        
        logger.info("[OK] 所有模块注册完成")
        
    except Exception as e:
        logger.error(f"[ERR] 模块注册失败: {e}", exc_info=True)
        sys.exit(1)


def main():
    """主函数"""
    # 1. 配置日志
    logger = setup_logging()
    
    # 2. 显示配置信息
    logger.info("配置参数:")
    logger.info(f"  - 配置文件: {CONFIG_PATH}")
    logger.info(f"  - 虚拟 CAN: {USE_VIRTUAL_CAN}")
    logger.info(f"  - 调试模式: {DEBUG_MODE}")
    logger.info(f"  - 无头模式: {NO_DISPLAY}")
    logger.info("")
    
    # 3. 加载配置
    config_manager = load_configuration(CONFIG_PATH, logger)
    
    # 4. 创建模块
    modules = create_modules(config_manager, logger)
    
    # 5. 创建 SystemManager
    logger.info("创建 SystemManager...")
    system_config = config_manager.get_system_config()
    event_bus = get_event_bus()
    
    system_manager = SystemManager(
        event_bus=event_bus,
        system_config=system_config,
        default_stop_timeout=5.0,
        force_exit_grace_period=3.0
    )
    logger.info("[OK] SystemManager 创建成功")
    
    # 6. 注册模块
    register_modules(system_manager, modules, logger)
    
    # 7. 启动系统
    logger.info("=" * 60)
    logger.info("启动系统...")
    logger.info("=" * 60)
    
    try:
        # 启动所有模块
        system_manager.start_all()
        logger.info("[OK] 所有模块启动成功")
        
        # 显示启动信息
        logger.info("")
        logger.info("系统运行中...")
        logger.info("  - 按 Ctrl+C 退出系统")
        if not NO_DISPLAY:
            logger.info("  - 按 'q' 键退出显示")
            logger.info("  - 按 'f' 键切换全屏")
            logger.info("  - 按 '1'/'2'/'3' 键切换显示模式")
        logger.info("")
        
        # 运行主循环（阻塞）
        system_manager.run()
        
    except KeyboardInterrupt:
        logger.info("\n接收到 Ctrl+C，正在关闭系统...")
    except Exception as e:
        logger.error(f"\n[ERR] 系统运行错误: {e}", exc_info=True)
    finally:
        logger.info("=" * 60)
        logger.info("系统已关闭")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
