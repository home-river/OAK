"""
Collector 数据采集测试（真实设备）

用于在真实配置下测试双设备 Collector 的数据采集功能。
使用 CollectorReceiver 接收并保存数据包，便于后续分析。

运行方式：
    python oak_vision_system/tests/manual/collector/test_collector_data_capture.py

功能：
    - 自动加载配置文件
    - 启动 Collector 模块
    - 使用 CollectorReceiver 接收数据
    - 保存数据日志到 test_logs/collector
    - 实时显示统计信息
    - 支持 Ctrl+C 或指定时长后停止
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from oak_vision_system.modules.config_manager.device_config_manager import DeviceConfigManager
from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
from oak_vision_system.modules.data_collector.collector import OAKDataCollector
from oak_vision_system.core.event_bus import EventBus
from oak_vision_system.tests.harness import CollectorReceiver


def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("collector_test.log", mode='w', encoding="utf-8")
        ]
    )
    return logging.getLogger(__name__)


def load_config(config_path: str, logger: logging.Logger):
    """加载配置文件"""
    logger.info(f"加载配置文件: {config_path}")
    
    if not Path(config_path).exists():
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    
    try:
        config_manager = DeviceConfigManager(config_path=config_path, auto_create=False)
        config_manager.load_config(validate=True)
        logger.info("配置加载成功")
        return config_manager
    except Exception as e:
        logger.error(f"配置加载失败: {e}", exc_info=True)
        sys.exit(1)


def print_stats(receiver: CollectorReceiver, logger: logging.Logger):
    """打印统计信息"""
    stats = receiver.get_stats()
    
    logger.info("=" * 60)
    logger.info("实时统计信息")
    logger.info("=" * 60)
    logger.info(f"运行时长: {stats['duration_seconds']:.1f} 秒")
    logger.info(f"")
    logger.info(f"视频帧:")
    logger.info(f"  - 接收: {stats['frame_count']}")
    logger.info(f"  - 处理: {stats['frame_processed']}")
    logger.info(f"  - 丢弃: {stats['frame_dropped']}")
    logger.info(f"  - 队列: {stats['frame_queue_size']}")
    logger.info(f"  - 速率: {stats['frame_rate']:.2f} 帧/秒")
    logger.info(f"")
    logger.info(f"检测数据:")
    logger.info(f"  - 接收: {stats['detection_count']}")
    logger.info(f"  - 处理: {stats['detection_processed']}")
    logger.info(f"  - 丢弃: {stats['detection_dropped']}")
    logger.info(f"  - 队列: {stats['detection_queue_size']}")
    logger.info(f"  - 速率: {stats['detection_rate']:.2f} 帧/秒")
    logger.info("=" * 60)


def main():
    """主函数"""
    logger = setup_logging()
    
    # 配置参数
    config_path = "assets/test_config/config.json"
    test_duration = 30  # 测试时长（秒）
    log_dir = "test_logs/collector"
    
    logger.info("=" * 60)
    logger.info("Collector 数据采集测试")
    logger.info("=" * 60)
    logger.info(f"配置文件: {config_path}")
    logger.info(f"测试时长: {test_duration} 秒")
    logger.info(f"日志目录: {log_dir}")
    logger.info("")
    
    # 加载配置
    config_manager = load_config(config_path, logger)
    config = config_manager.get_runnable_config()
    
    # 发现可用设备
    logger.info("发现 OAK 设备...")
    available_devices = OAKDeviceDiscovery.get_all_available_devices()
    logger.info(f"发现 {len(available_devices)} 个设备")
    
    # 创建事件总线
    event_bus = EventBus()
    
    # 创建 Collector
    logger.info("创建 OAKDataCollector...")
    collector = OAKDataCollector(
        config=config.oak_module,
        event_bus=event_bus,
        available_devices=available_devices
    )
    
    # 创建 CollectorReceiver
    logger.info("创建 CollectorReceiver...")
    receiver = CollectorReceiver(
        event_bus=event_bus,
        log_dir=log_dir,
        log_prefix="collector_data",
        frame_queue_size=100,
        detection_queue_size=100
    )
    
    try:
        # 启动 Collector
        logger.info("启动 Collector...")
        collector_result = collector.start()
        if not collector_result:
            logger.error("Collector 启动失败")
            sys.exit(1)
        logger.info("Collector 启动成功")
        
        # 启动 Receiver
        logger.info("启动 CollectorReceiver...")
        receiver.start()
        logger.info("CollectorReceiver 启动成功")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("数据采集中...")
        logger.info("=" * 60)
        logger.info(f"按 Ctrl+C 可提前停止")
        logger.info("")
        
        # 运行测试
        start_time = time.time()
        last_stats_time = start_time
        stats_interval = 5.0  # 每5秒打印一次统计
        
        while time.time() - start_time < test_duration:
            time.sleep(0.1)
            
            # 定期打印统计信息
            if time.time() - last_stats_time >= stats_interval:
                print_stats(receiver, logger)
                last_stats_time = time.time()
        
        logger.info("")
        logger.info("测试时长已到，准备停止...")
        
    except KeyboardInterrupt:
        logger.info("")
        logger.info("收到 Ctrl+C，准备停止...")
    
    finally:
        # 停止 Receiver
        logger.info("停止 CollectorReceiver...")
        final_stats = receiver.stop()
        
        # 停止 Collector
        logger.info("停止 Collector...")
        collector.stop(timeout=5.0)
        
        # 打印最终统计
        logger.info("")
        logger.info("=" * 60)
        logger.info("最终统计信息")
        logger.info("=" * 60)
        logger.info(f"运行时长: {final_stats['duration_seconds']:.1f} 秒")
        logger.info(f"")
        logger.info(f"视频帧:")
        logger.info(f"  - 接收: {final_stats['frame_count']}")
        logger.info(f"  - 处理: {final_stats['frame_processed']}")
        logger.info(f"  - 丢弃: {final_stats['frame_dropped']}")
        logger.info(f"  - 平均速率: {final_stats.get('frame_rate', 0):.2f} 帧/秒")
        logger.info(f"")
        logger.info(f"检测数据:")
        logger.info(f"  - 接收: {final_stats['detection_count']}")
        logger.info(f"  - 处理: {final_stats['detection_processed']}")
        logger.info(f"  - 丢弃: {final_stats['detection_dropped']}")
        logger.info(f"  - 平均速率: {final_stats.get('detection_rate', 0):.2f} 帧/秒")
        logger.info("=" * 60)
        logger.info(f"")
        logger.info(f"数据日志已保存到: {log_dir}")
        logger.info(f"可以使用以下命令查看日志文件:")
        logger.info(f"  ls {log_dir}")
        logger.info(f"")
        logger.info("测试完成！")


if __name__ == "__main__":
    main()
