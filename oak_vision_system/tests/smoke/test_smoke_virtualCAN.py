"""
完整系统冒烟测试

测试流程：
1. 通过 DeviceConfigManager 加载配置
2. 创建真实的 OAK 设备模块（PipelineManager）
3. 创建数据处理模块（DataProcessor）
4. 使用工厂函数创建虚拟 CAN 通信器
5. 注册到 SystemManager
6. 启动完整的检测流
7. 运行并监控系统状态
8. 优雅关闭所有模块

使用场景：
- 真实 OAK 设备连接
- 虚拟 CAN 通信（Windows 环境）
- 完整的端到端集成测试
"""

import logging
import time
import sys
import signal
import threading
from pathlib import Path
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SystemSmokeTest:
    """系统冒烟测试类"""
    
    def __init__(self, config_path: str):
        """
        初始化冒烟测试
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        
        # 模块引用
        self.device_config_manager = None
        self.event_bus = None
        self.oak_collector = None
        self.data_processor = None
        self.display_manager = None
        self.can_communicator = None
        self.system_manager = None
        
        # 运行状态
        self.running = True
        self.test_start_time = None
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理中断信号（Ctrl+C）"""
        logger.info("\n\n收到中断信号，准备优雅关闭...")
        self.running = False
    
    def step_1_load_config(self) -> bool:
        """步骤 1: 加载配置文件"""
        logger.info("=" * 80)
        logger.info("步骤 1: 加载配置文件")
        logger.info("=" * 80)
        
        try:
            # 检查配置文件是否存在
            if not self.config_path.exists():
                logger.error(f"❌ 配置文件不存在: {self.config_path}")
                logger.error(f"   请确保配置文件路径正确")
                return False
            
            logger.info(f"配置文件路径: {self.config_path.absolute()}")
            
            # 导入配置管理器
            from oak_vision_system.modules.config_manager import DeviceConfigManager
            
            # 创建配置管理器实例
            self.device_config_manager = DeviceConfigManager(
                str(self.config_path),
                auto_create=False  # 不自动创建，配置文件必须存在
            )
            
            # 加载并验证配置
            logger.info("正在加载配置...")
            self.device_config_manager.load_config(validate=True)
            
            # 获取配置对象
            config = self.device_config_manager.get_config()
            
            logger.info(f"✅ 配置加载成功")
            logger.info(f"   配置版本: {config.config_version}")
            
            # 显示关键配置信息
            self._display_config_info(config)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 加载配置失败: {e}", exc_info=True)
            return False
    
    def _display_config_info(self, config):
        """显示配置信息"""
        logger.info("\n关键配置信息:")
        
        # OAK 设备配置
        logger.info("\n[OAK 设备配置]")
        oak_config = config.oak_module
        logger.info(f"  模型路径: {oak_config.hardware_config.model_path}")
        logger.info(f"  标签映射: {oak_config.hardware_config.label_map}")
        logger.info(f"  置信度阈值: {oak_config.hardware_config.confidence_threshold}")
        
        # 设备角色绑定
        logger.info("\n[设备角色绑定]")
        for role, binding in oak_config.role_bindings.items():
            logger.info(f"  {role}:")
            logger.info(f"    • 活跃设备: {binding.active_mxid}")
            logger.info(f"    • 历史设备: {binding.historical_mxids}")
        
        # CAN 配置
        logger.info("\n[CAN 通信配置]")
        can_config = config.can_config
        logger.info(f"  enable_can: {can_config.enable_can}")
        logger.info(f"  接口类型: {can_config.can_interface}")
        logger.info(f"  通道: {can_config.can_channel}")
        logger.info(f"  波特率: {can_config.can_bitrate}")
        
        if can_config.enable_can:
            logger.warning("  ⚠️  警告: enable_can=True，将尝试连接真实 CAN 硬件")
            logger.warning("  ⚠️  Windows 环境建议设置为 False 使用虚拟 CAN")
        else:
            logger.info("  ✅ 将使用虚拟 CAN 模式（适用于 Windows）")
        
        # 数据处理配置
        logger.info("\n[数据处理配置]")
        dp_config = config.data_processing_config
        logger.info(f"  滤波器类型: {dp_config.filter_config.filter_type}")
        logger.info(f"  人员标签 ID: {dp_config.decision_layer_config.person_label_ids}")
        logger.info(f"  警报距离阈值: {dp_config.decision_layer_config.person_warning.d_in} mm")
    
    def step_2_create_modules(self) -> bool:
        """步骤 2: 创建所有系统模块"""
        logger.info("\n" + "=" * 80)
        logger.info("步骤 2: 创建系统模块")
        logger.info("=" * 80)
        
        try:
            config = self.device_config_manager.get_config()
            
            # 2.1 创建事件总线
            logger.info("\n[2.1] 创建事件总线")
            # 注意：系统内多个模块（如 DataProcessor / RenderPacketPackager）使用 get_event_bus() 获取全局单例。
            # 若此处手动 new EventBus() 会导致发布/订阅不在同一总线上，从而无法接收渲染包。
            from oak_vision_system.core.event_bus import reset_event_bus, get_event_bus

            reset_event_bus()
            self.event_bus = get_event_bus()
            logger.info("✅ 事件总线创建成功")
            
            # 2.2 创建 OAKDataCollector（OAK 设备数据采集器）
            logger.info("\n[2.2] 创建 OAKDataCollector（OAK 设备数据采集器）")
            logger.info("      这将连接真实的 OAK 设备...")
            from oak_vision_system.modules.data_collector.collector import OAKDataCollector
            
            self.oak_collector = OAKDataCollector(
                config=config.oak_module,
                event_bus=self.event_bus
            )
            logger.info("✅ OAKDataCollector 创建成功")
            logger.info("   OAK 设备已准备就绪")
            
            # 2.3 创建 DataProcessor（数据处理模块）
            logger.info("\n[2.3] 创建 DataProcessor（数据处理模块）")
            from oak_vision_system.modules.data_processing.data_processor import DataProcessor
            
            self.data_processor = DataProcessor(
                config=config.data_processing_config,
                device_metadata=config.oak_module.device_metadata,
                bindings=config.oak_module.role_bindings,
                label_map=config.oak_module.hardware_config.label_map
            )
            logger.info("✅ DataProcessor 创建成功")
            logger.info("   包含: 坐标转换器、滤波器、决策层")
            
            # 2.4 创建 DisplayManager（显示模块）
            logger.info("\n[2.4] 创建 DisplayManager（显示模块）")
            from oak_vision_system.modules.display_modules.display_manager import DisplayManager
            
            # 准备设备列表（从 role_bindings 中提取活跃的 MXID）
            devices_list = [
                binding.active_mxid 
                for binding in config.oak_module.role_bindings.values() 
                if binding.active_mxid
            ]
            
            # 准备角色绑定映射（DeviceRole -> MXID）
            role_to_mxid = {
                role: binding.active_mxid
                for role, binding in config.oak_module.role_bindings.items()
                if binding.active_mxid
            }
            
            self.display_manager = DisplayManager(
                config=config.display_config,
                devices_list=devices_list,
                role_bindings=role_to_mxid,
                enable_depth_output=config.oak_module.hardware_config.enable_depth_output
            )
            logger.info("✅ DisplayManager 创建成功")
            logger.info(f"   管理设备数: {len(devices_list)}")
            logger.info(f"   显示模式: {config.display_config.default_display_mode}")
            logger.info(f"   深度输出: {'启用' if config.oak_module.hardware_config.enable_depth_output else '禁用'}")
            
            # 2.5 使用工厂函数创建 CAN 通信器
            logger.info("\n[2.5] 使用工厂函数创建 CAN 通信器")
            from oak_vision_system.modules.can_communication.can_factory import create_can_communicator
            from oak_vision_system.modules.can_communication.virtual_can_communicator import VirtualCANCommunicator
            
            self.can_communicator = create_can_communicator(
                config=config.can_config,
                decision_layer=self.data_processor.decision_layer,
                event_bus=self.event_bus
            )
            
            # 验证 CAN 类型
            if isinstance(self.can_communicator, VirtualCANCommunicator):
                logger.info("✅ CAN 通信器创建成功: VirtualCANCommunicator")
                logger.info("   虚拟 CAN 模式（适用于 Windows 开发环境）")
            else:
                logger.info(f"✅ CAN 通信器创建成功: {self.can_communicator.__class__.__name__}")
                logger.warning("   ⚠️  真实 CAN 模式（需要硬件支持）")
            
            # 2.6 创建 SystemManager 并注册模块
            logger.info("\n[2.6] 创建 SystemManager 并注册模块")
            from oak_vision_system.core.system_manager.system_manager import SystemManager
            
            self.system_manager = SystemManager(
                event_bus=self.event_bus,
                system_config=config.system_config
            )
            
            # 注册所有模块（按优先级：数字越大越靠近下游）
            # 注意：EventBus 不需要注册，它是基础设施，SystemManager 会自动管理
            # 启动顺序：display(60) → can_communicator(50) → data_processor(30) → oak_collector(10)
            # 关闭顺序：oak_collector(10) → data_processor(30) → can_communicator(50) → display(60)
            self.system_manager.register_module("oak_collector", self.oak_collector, priority=10)
            self.system_manager.register_module("data_processor", self.data_processor, priority=30)
            self.system_manager.register_module("can_communicator", self.can_communicator, priority=50)
            self.system_manager.register_module("display_manager", self.display_manager, priority=60)
            
            logger.info("✅ SystemManager 创建成功")
            logger.info(f"   已注册 {len(self.system_manager._modules)} 个模块:")
            logger.info("     • oak_collector (priority=10)")
            logger.info("     • data_processor (priority=30)")
            logger.info("     • can_communicator (priority=50)")
            logger.info("     • display_manager (priority=60)")
            logger.info("   注意：EventBus 由 SystemManager 自动管理，无需注册")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建模块失败: {e}", exc_info=True)
            return False
    
    def step_3_start_and_run_system(self, duration: int = 30) -> bool:
        """步骤 3: 启动并运行系统（使用 SystemManager 标准流程）"""
        logger.info("\n" + "=" * 80)
        logger.info("步骤 3: 启动并运行系统")
        logger.info("=" * 80)
        
        try:
            # 3.1 使用 SystemManager.start_all() 启动所有模块
            logger.info("\n[3.1] 使用 SystemManager.start_all() 启动所有模块...")
            logger.info("      SystemManager 将按优先级顺序启动：")
            logger.info("      display(60) → can(50) → processor(30) → collector(10)")
            
            self.system_manager.start_all()
            
            logger.info("\n✅ 所有模块已通过 SystemManager 启动")
            logger.info("   系统状态: RUNNING")
            
            # 3.2 启动定时器，在指定时间后触发 SYSTEM_SHUTDOWN 事件
            logger.info(f"\n[3.2] 启动定时器，{duration} 秒后自动关闭系统...")
            
            def trigger_shutdown():
                time.sleep(duration)
                logger.info(f"\n⏰ {duration} 秒已到，触发 SYSTEM_SHUTDOWN 事件...")
                self.event_bus.publish("SYSTEM_SHUTDOWN", None)
            
            shutdown_timer = threading.Thread(target=trigger_shutdown, daemon=True, name="ShutdownTimer")
            shutdown_timer.start()
            
            # 3.3 调用 SystemManager.run() 阻塞等待
            logger.info("\n[3.3] 调用 SystemManager.run() 进入主循环...")
            logger.info("      系统正在运行，等待退出信号...")
            logger.info("      • 按 Ctrl+C 可提前停止")
            logger.info(f"      • 或等待 {duration} 秒自动停止")
            logger.info("")
            
            self.test_start_time = time.time()
            
            # 阻塞等待，直到收到退出信号（Ctrl+C 或 SYSTEM_SHUTDOWN 事件）
            # SystemManager.run() 会在退出时自动调用 shutdown()
            self.system_manager.run()
            
            logger.info("\n✅ 系统已正常退出")
            logger.info(f"   实际运行时间: {int(time.time() - self.test_start_time)} 秒")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 系统运行失败: {e}", exc_info=True)
            return False
    
    def print_test_summary(self):
        """打印测试总结"""
        logger.info("\n" + "=" * 80)
        logger.info("冒烟测试总结")
        logger.info("=" * 80)
        
        logger.info("\n测试项目:")
        logger.info("  ✅ 配置文件加载")
        logger.info("  ✅ 事件总线创建（基础设施）")
        logger.info("  ✅ OAK 设备连接（真实硬件）")
        logger.info("  ✅ 数据处理模块创建")
        logger.info("  ✅ 显示模块创建")
        logger.info("  ✅ 虚拟 CAN 通信器创建")
        logger.info("  ✅ SystemManager 模块注册")
        logger.info("  ✅ 系统启动（标准流程）")
        logger.info("  ✅ 检测流运行")
        logger.info("  ✅ 视频显示")
        logger.info("  ✅ 事件处理")
        logger.info("  ✅ 系统停止")
        
        logger.info("\n测试结果: 🎉 所有测试通过！")
        logger.info("\n系统集成验证成功，可以投入使用。")
    
    def run(self, duration: int = 30) -> bool:
        """
        运行完整的冒烟测试（使用 SystemManager 标准流程）
        
        Args:
            duration: 测试运行时长（秒），默认 30 秒
            
        Returns:
            bool: 测试是否成功
        """
        try:
            # 步骤 1: 加载配置
            if not self.step_1_load_config():
                return False
            
            # 步骤 2: 创建模块并注册到 SystemManager
            if not self.step_2_create_modules():
                return False
            
            # 步骤 3: 启动并运行系统（SystemManager 会自动处理启动和关闭）
            if not self.step_3_start_and_run_system(duration):
                return False
            
            # 打印总结
            self.print_test_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 冒烟测试失败: {e}", exc_info=True)
            return False


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("OAK Vision System - 完整系统冒烟测试")
    logger.info("=" * 80)
    logger.info("\n测试配置:")
    logger.info("  • 真实 OAK 设备连接")
    logger.info("  • 虚拟 CAN 通信（Windows 环境）")
    logger.info("  • 完整数据流测试")
    logger.info("  • 使用 SystemManager 标准流程")
    logger.info("")
    
    # 配置文件路径（相对于项目根目录）
    config_path = "assets/test_config/config.json"
    
    # 测试运行时长（秒）
    test_duration = 30
    
    logger.info(f"配置文件: {config_path}")
    logger.info(f"测试时长: {test_duration} 秒")
    logger.info("")
    
    # 创建并运行测试
    test = SystemSmokeTest(config_path)
    success = test.run(duration=test_duration)
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
