"""
校准GUI使用示例

这个脚本演示了如何启动和使用校准GUI。

注意：这只是一个示例，实际使用时需要确保主系统已经启动。
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.calibration_tools.gui.calibration_gui import CalibrationGUI


def example_usage():
    """示例：如何使用校准GUI"""
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("校准GUI使用示例")
    logger.info("=" * 60)
    
    # 注意：以下代码需要在主系统启动后才能运行
    # 这里仅作为示例说明
    
    try:
        # 1. 获取必要的实例（需要主系统已启动）
        # from oak_vision_system.modules.config_manager import DeviceConfigManager
        # from oak_vision_system.modules.data_processing.data_processor import DataProcessor
        # from oak_vision_system.modules.data_processing.decision_layer import DecisionLayer
        # from tools.calibration_tools.core.transform_param_manager import TransformParamManager
        # from tools.calibration_tools.core.error_recorder import ErrorRecorder
        
        # config_manager = DeviceConfigManager()
        # data_processor = DataProcessor.get_instance()  # 假设已初始化
        # decision_layer = DecisionLayer.get_instance()  # 假设已初始化
        
        # 2. 创建参数管理器和误差记录器
        # param_manager = TransformParamManager(config_manager, data_processor)
        # error_recorder = ErrorRecorder(decision_layer)
        
        # 3. 启动GUI（在独立线程中）
        # gui_thread = CalibrationGUI.start_in_thread(param_manager, error_recorder)
        
        # logger.info("校准GUI已启动")
        # logger.info("GUI运行在独立线程中，不会阻塞主程序")
        
        # 4. 主程序继续运行
        # try:
        #     gui_thread.join()  # 等待GUI线程结束
        # except KeyboardInterrupt:
        #     logger.info("用户中断，退出程序")
        
        logger.info("\n使用说明：")
        logger.info("1. 确保主系统已经启动")
        logger.info("2. 运行校准工具启动脚本：")
        logger.info("   python -m tools.calibration_tools.calibration_main")
        logger.info("3. 或者在代码中使用：")
        logger.info("   CalibrationGUI.start_in_thread(param_manager, error_recorder)")
        
    except Exception as e:
        logger.error(f"示例运行失败: {e}", exc_info=True)


if __name__ == "__main__":
    example_usage()
