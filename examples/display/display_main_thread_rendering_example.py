"""
显示模块主线程渲染示例

演示如何使用新的主线程渲染架构：
1. 使用 register_display_module() 注册显示模块
2. SystemManager.run() 自动在主线程中调用 render_once()
3. 用户按 'q' 键退出系统
"""

import logging
from typing import Dict

from oak_vision_system.core.system_manager import SystemManager
from oak_vision_system.core.dto.config_dto import (
    SystemConfigDTO,
    DisplayConfigDTO,
    DeviceRole,
)
from oak_vision_system.modules.display_modules import DisplayManager
from oak_vision_system.modules.config_manager import DeviceConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """主函数：演示主线程渲染架构"""
    
    logger.info("=" * 60)
    logger.info("显示模块主线程渲染示例")
    logger.info("=" * 60)
    
    # 1. 创建系统配置
    system_config = SystemConfigDTO(
        log_level="INFO",
        log_file_path=None,
        enable_console_log=True,
    )
    
    # 2. 创建 SystemManager
    system_manager = SystemManager(
        system_config=system_config,
        default_stop_timeout=5.0,
        force_exit_grace_period=3.0
    )
    
    # 3. 创建显示配置
    display_config = DisplayConfigDTO(
        enable_display=True,
        target_fps=30,
        window_width=1280,
        window_height=720,
        enable_fullscreen=False,
        show_fps=True,
        show_labels=True,
        show_coordinates=True,
        show_device_info=True,
    )
    
    # 4. 模拟设备列表和角色绑定
    # 在实际应用中，这些应该从 DeviceConfigManager 获取
    devices_list = ["device1", "device2"]
    role_bindings: Dict[DeviceRole, str] = {
        DeviceRole.LEFT_CAMERA: "device1",
        DeviceRole.RIGHT_CAMERA: "device2",
    }
    
    # 5. 创建 DisplayManager
    display_manager = DisplayManager(
        config=display_config,
        devices_list=devices_list,
        role_bindings=role_bindings,
        enable_depth_output=False,
    )
    
    # 6. 使用新的 register_display_module() 方法注册显示模块
    # 注意：使用 register_display_module() 而不是 register_module()
    logger.info("注册显示模块（需要主线程渲染）...")
    system_manager.register_display_module(
        name="display",
        instance=display_manager,
        priority=50  # 显示模块优先级最高
    )
    
    # 7. 启动所有模块
    logger.info("启动所有模块...")
    system_manager.start_all()
    
    # 8. 运行主循环（阻塞主线程）
    # SystemManager.run() 会自动在主线程中调用 display_manager.render_once()
    logger.info("=" * 60)
    logger.info("系统运行中...")
    logger.info("按键说明：")
    logger.info("  '1' - 切换到左相机")
    logger.info("  '2' - 切换到右相机")
    logger.info("  '3' - 切换到拼接模式")
    logger.info("  'f' - 切换全屏")
    logger.info("  'q' - 退出系统")
    logger.info("=" * 60)
    
    try:
        system_manager.run()  # 阻塞主线程，等待退出信号
    except Exception as e:
        logger.error(f"系统运行时发生错误: {e}", exc_info=True)
    
    logger.info("=" * 60)
    logger.info("系统已退出")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
