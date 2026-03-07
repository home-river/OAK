"""
OAK Vision System - 校准工具启动脚本

在主系统运行的基础上，启动校准工具 GUI，提供：
- 坐标变换参数的实时调整
- 误差数据记录功能

使用方式：
    python tools/calibration_tools/calibration_main.py

注意：
- 校准工具会启动完整的主系统（Collector、DataProcessor、Display、CAN）
- 校准 GUI 在独立线程中运行，不阻塞主系统
- 参数调整仅在内存中生效，不会修改配置文件
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径（必须在任何 oak_vision_system 导入之前）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oak_vision_system.core.system_manager import SystemManager
from oak_vision_system.core.event_bus import get_event_bus
from oak_vision_system.modules.config_manager.device_config_manager import DeviceConfigManager
from oak_vision_system.modules.data_collector.collector import OAKDataCollector
from oak_vision_system.modules.data_processing.data_processor import DataProcessor
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.modules.can_communication.can_factory import create_can_communicator
from oak_vision_system.modules.data_processing.decision_layer.decision_layer import DecisionLayer

# 校准工具模块
from tools.calibration_tools.core.transform_param_manager import TransformParamManager
from tools.calibration_tools.core.error_recorder import ErrorRecorder
from tools.calibration_tools.gui.calibration_gui import CalibrationGUI

from typing import Optional


# ==================== 配置参数 ====================

# 配置文件路径（相对于项目根目录）
CONFIG_PATH = "assets/test_config/config.json"

# 是否使用虚拟 CAN（测试用）
USE_VIRTUAL_CAN = True

# 是否禁用显示（无头模式）
NO_DISPLAY = False

# 误差记录日志文件路径
ERROR_LOG_PATH = "error/calibration_errors.json"


def load_configuration(config_path: str, logger: Optional[logging.Logger] = None):
    """加载系统配置"""
    if logger:
        logger.info(f"加载配置文件: {config_path}")
    
    # 检查配置文件是否存在
    if not Path(config_path).exists():
        error_msg = f"配置文件不存在: {config_path}"
        if logger:
            logger.error(error_msg)
        else:
            print(f"[ERROR] {error_msg}")
        sys.exit(1)
    
    try:
        config_manager = DeviceConfigManager(config_path=config_path, auto_create=False)
        config_manager.load_config(validate=True)

        if logger:
            logger.info("[OK] 配置加载成功")
        return config_manager
    except Exception as e:
        error_msg = f"[ERR] 配置加载失败: {e}"
        if logger:
            logger.error(error_msg, exc_info=True)
        else:
            print(error_msg)
        sys.exit(1)


def validate_single_device_mode(config_manager: DeviceConfigManager, logger: logging.Logger):
    """
    验证单设备运行模式
    
    Args:
        config_manager: 配置管理器实例
        logger: 日志记录器
    
    Returns:
        str: 设备 mxid
    
    Raises:
        SystemExit: 验证失败时退出程序
    """
    try:
        runnable_mxids = config_manager.get_runnable_mxids()
        
        if len(runnable_mxids) == 0:
            error_msg = "未检测到任何可运行的设备"
            logger.error(f"[ERR] {error_msg}")
            print(f"\n[ERROR] {error_msg}")
            print("\n可能的原因：")
            print("  1. 配置文件中没有设备配置")
            print("  2. 所有设备都处于禁用状态")
            print("  3. 设备角色绑定配置错误")
            print("\n解决方案：")
            print("  - 检查配置文件中的设备配置")
            print("  - 确保至少有一个设备处于激活状态")
            sys.exit(1)
        
        if len(runnable_mxids) > 1:
            error_msg = (
                f"校准工具仅支持单设备运行模式，"
                f"当前检测到 {len(runnable_mxids)} 个设备: {runnable_mxids}"
            )
            logger.error(f"[ERR] {error_msg}")
            print(f"\n[ERROR] {error_msg}")
            print("\n解决方案：")
            print("  - 修改配置文件，确保只有一个设备处于激活状态")
            print("  - 或者禁用其他设备的角色绑定")
            sys.exit(1)
        
        logger.info(f"[OK] 单设备运行模式验证通过: {runnable_mxids[0]}")
        return runnable_mxids[0]
        
    except AttributeError as e:
        logger.error(f"[ERR] 配置管理器方法调用失败: {e}")
        logger.error("请确保使用的是最新版本的 DeviceConfigManager")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[ERR] 设备模式验证失败: {e}", exc_info=True)
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
            label_map = config_manager.get_label_map()

            display_manager = DisplayManager(
                config=display_config,
                devices_list=list(device_metadata.keys()),
                role_bindings=role_bindings,
                label_map=label_map,
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


def register_modules(system_manager: SystemManager, modules, logger):
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


def create_calibration_tools(
    config_manager: DeviceConfigManager,
    data_processor: DataProcessor,
    logger: logging.Logger
):
    """
    创建校准工具组件
    
    Args:
        config_manager: 配置管理器实例
        data_processor: 数据处理器实例
        logger: 日志记录器
    
    Returns:
        tuple: (param_manager, error_recorder)
    
    Raises:
        SystemExit: 组件创建失败时退出程序
    """
    logger.info("创建校准工具组件...")
    
    try:
        # 1. 获取 DecisionLayer 实例
        logger.info("  - 获取 DecisionLayer 实例...")
        try:
            decision_layer = DecisionLayer.get_instance()
            logger.info("    [OK] DecisionLayer 实例获取成功")
        except RuntimeError as e:
            # DecisionLayer 未初始化
            logger.error(f"    [ERR] DecisionLayer 未初始化: {e}")
            logger.error("")
            logger.error("可能的原因：")
            logger.error("  1. DataProcessor 尚未创建")
            logger.error("  2. DataProcessor 初始化失败")
            logger.error("")
            logger.error("解决方案：")
            logger.error("  - 确保 DataProcessor 已经成功创建")
            logger.error("  - DecisionLayer 在 DataProcessor.__init__() 中自动创建")
            raise
        
        # 2. 创建 TransformParamManager
        logger.info("  - 创建 TransformParamManager...")
        try:
            param_manager = TransformParamManager(
                config_manager=config_manager,
                data_processor=data_processor
            )
            logger.info("    [OK] TransformParamManager 创建成功")
        except ValueError as e:
            logger.error(f"    [ERR] TransformParamManager 创建失败: {e}")
            logger.error("")
            logger.error("可能的原因：")
            logger.error("  1. 配置文件中缺少坐标变换配置")
            logger.error("  2. 设备角色绑定配置错误")
            logger.error("")
            raise
        except Exception as e:
            logger.error(f"    [ERR] TransformParamManager 创建失败: {e}")
            raise
        
        # 3. 创建 ErrorRecorder
        logger.info("  - 创建 ErrorRecorder...")
        try:
            error_recorder = ErrorRecorder(
                decision_layer=decision_layer,
                log_file_path=ERROR_LOG_PATH
            )
            logger.info("    [OK] ErrorRecorder 创建成功")
            logger.info(f"    误差日志文件: {ERROR_LOG_PATH}")
        except OSError as e:
            logger.error(f"    [ERR] ErrorRecorder 创建失败（文件系统错误）: {e}")
            logger.error("")
            logger.error("可能的原因：")
            logger.error("  1. 日志目录不存在且无法创建")
            logger.error("  2. 没有写入权限")
            logger.error("")
            raise
        except Exception as e:
            logger.error(f"    [ERR] ErrorRecorder 创建失败: {e}")
            raise
        
        logger.info("[OK] 校准工具组件创建完成")
        return param_manager, error_recorder
        
    except Exception as e:
        logger.error(f"[ERR] 校准工具组件创建失败: {e}", exc_info=True)
        logger.error("")
        logger.error("系统无法继续运行，即将退出...")
        sys.exit(1)


def start_calibration_gui(
    param_manager: TransformParamManager,
    error_recorder: ErrorRecorder,
    logger: logging.Logger
):
    """
    启动校准 GUI（在独立线程中）
    
    Args:
        param_manager: 参数管理器实例
        error_recorder: 误差记录器实例
        logger: 日志记录器
    
    Returns:
        Thread: GUI 线程对象
    
    Raises:
        SystemExit: GUI 启动失败时退出程序
    """
    logger.info("启动校准 GUI...")
    
    try:
        # 在独立线程中启动 GUI
        gui_thread = CalibrationGUI.start_in_thread(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        logger.info("[OK] 校准 GUI 已启动（独立线程）")
        logger.info("  - GUI 窗口应该已经打开")
        logger.info("  - GUI 不会阻塞主系统运行")
        logger.info("  - GUI 异常不会影响主系统")
        
        return gui_thread
        
    except ValueError as e:
        # 单设备模式验证失败
        logger.error(f"[ERR] GUI 启动失败（设备模式错误）: {e}")
        logger.error("")
        logger.error("可能的原因：")
        logger.error("  1. 系统检测到多个设备")
        logger.error("  2. 没有检测到任何设备")
        logger.error("")
        logger.error("解决方案：")
        logger.error("  - 确保配置文件中只有一个设备处于激活状态")
        logger.error("  - 检查 get_runnable_mxids() 返回的设备列表")
        logger.error("")
        sys.exit(1)
    except ImportError as e:
        # tkinter 导入失败
        logger.error(f"[ERR] GUI 启动失败（缺少依赖）: {e}")
        logger.error("")
        logger.error("可能的原因：")
        logger.error("  1. tkinter 未安装")
        logger.error("  2. Python 环境不支持 GUI")
        logger.error("")
        logger.error("解决方案：")
        logger.error("  - 安装 tkinter: sudo apt-get install python3-tk (Linux)")
        logger.error("  - 或使用无头模式运行主系统")
        logger.error("")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[ERR] GUI 启动失败: {e}", exc_info=True)
        logger.error("")
        logger.error("系统无法继续运行，即将退出...")
        sys.exit(1)


def main():
    """
    主函数
    
    启动流程：
    1. 加载配置
    2. 验证单设备模式
    3. 创建系统模块
    4. 创建校准工具组件
    5. 启动系统
    6. 启动校准 GUI
    7. 运行主循环
    """
    logger = None  # 初始化 logger 变量
    
    try:
        # 1. 先加载配置（此时还没有配置日志）
        config_manager = load_configuration(CONFIG_PATH, logger=None)
        system_config = config_manager.get_system_config()
        
        # 2. 创建 SystemManager（自动配置日志）
        event_bus = get_event_bus()
        system_manager = SystemManager(
            event_bus=event_bus,
            system_config=system_config,
            log_subpath="main/calibration.log",  # 使用独立的日志文件
            default_stop_timeout=5.0,
            force_exit_grace_period=3.0
        )
        
        # 3. 获取 logger（日志已经配置好了）
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("OAK Vision System - 校准工具")
        logger.info("=" * 60)
        
        # 4. 验证单设备运行模式
        device_mxid = validate_single_device_mode(config_manager, logger)
        
        # 5. 显示配置信息
        logger.info("配置参数:")
        logger.info(f"  - 配置文件: {CONFIG_PATH}")
        logger.info(f"  - 设备 MXID: {device_mxid}")
        logger.info(f"  - 虚拟 CAN: {USE_VIRTUAL_CAN}")
        logger.info(f"  - 无头模式: {NO_DISPLAY}")
        logger.info(f"  - 误差日志: {ERROR_LOG_PATH}")
        logger.info("")
        
        # 6. 创建模块
        modules = create_modules(config_manager, logger)
        
        # 7. 注册模块
        register_modules(system_manager, modules, logger)
        
        # 8. 创建校准工具组件（在模块创建后，启动前）
        data_processor = modules['processor']
        param_manager, error_recorder = create_calibration_tools(
            config_manager,
            data_processor,
            logger
        )
        
        # 9. 启动系统
        logger.info("=" * 60)
        logger.info("启动系统...")
        logger.info("=" * 60)
        
        # 启动所有模块
        system_manager.start_all()
        logger.info("[OK] 所有模块启动成功")
        
        # 10. 启动校准 GUI（在系统启动后）
        logger.info("")
        gui_thread = start_calibration_gui(param_manager, error_recorder, logger)
        
        # 显示启动信息
        logger.info("")
        logger.info("系统运行中...")
        logger.info("  - 主系统：正常运行")
        logger.info("  - 校准 GUI：已启动（独立线程）")
        logger.info("")
        logger.info("操作说明：")
        logger.info("  - 使用校准 GUI 调整坐标变换参数")
        logger.info("  - 参数调整仅在内存中生效，不会修改配置文件")
        logger.info("  - 按 Ctrl+C 退出系统")
        if not NO_DISPLAY:
            logger.info("  - 按 'q' 键退出显示")
            logger.info("  - 按 'f' 键切换全屏")
            logger.info("  - 按 '1'/'2'/'3' 键切换显示模式")
        logger.info("")
        
        # 运行主循环（阻塞）
        system_manager.run()
        
    except KeyboardInterrupt:
        if logger:
            logger.info("\n接收到 Ctrl+C，正在关闭系统...")
        else:
            print("\n接收到 Ctrl+C，正在关闭系统...")
    except SystemExit:
        # 由其他函数调用 sys.exit() 触发，不需要额外处理
        pass
    except Exception as e:
        if logger:
            logger.error(f"\n[ERR] 系统运行错误: {e}", exc_info=True)
            logger.error("")
            logger.error("系统遇到未预期的错误，即将退出...")
        else:
            print(f"\n[ERROR] 系统运行错误: {e}")
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        if logger:
            logger.info("=" * 60)
            logger.info("系统已关闭")
            logger.info("=" * 60)
        else:
            print("=" * 60)
            print("系统已关闭")
            print("=" * 60)


if __name__ == "__main__":
    main()
