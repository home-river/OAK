#!/usr/bin/env python3
"""
虚拟 CAN 通信器手动演示脚本

演示虚拟 CAN 通信器的核心功能：
1. 启动和停止
2. 事件处理
3. 坐标请求模拟
4. 统计信息管理

使用方法：
    python oak_vision_system/tests/manual/manual_virtual_can_demo.py

注意：
- 这是一个演示脚本，用于验证虚拟 CAN 通信器的功能
- 不需要真实的 CAN 硬件
- 适合在 Windows 开发环境中运行
"""

import logging
import time
import sys
import os
from unittest.mock import Mock
import numpy as np

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from oak_vision_system.modules.can_communication.virtual_can_communicator import VirtualCANCommunicator
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
from oak_vision_system.modules.data_processing.decision_layer.types import PersonWarningStatus

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def create_mock_dependencies():
    """创建 Mock 依赖项"""
    # Mock 决策层
    mock_decision_layer = Mock()
    
    # 模拟不同的坐标返回情况
    coordinate_sequence = [
        np.array([1.5, 2.0, 0.8]),  # 有效坐标
        None,                       # 无目标
        np.array([3.2, 1.8, 1.2]), # 另一个有效坐标
        np.array([0.5, 0.3, 0.1]), # 小坐标值
    ]
    
    call_count = 0
    def get_coords_side_effect():
        nonlocal call_count
        if call_count < len(coordinate_sequence):
            result = coordinate_sequence[call_count]
            call_count += 1
            return result
        else:
            # 循环返回
            call_count = 0
            return coordinate_sequence[0]
    
    mock_decision_layer.get_target_coords_snapshot.side_effect = get_coords_side_effect
    
    # Mock 事件总线
    mock_event_bus = Mock()
    mock_event_bus.subscribe.return_value = "demo_subscription_id"
    
    return mock_decision_layer, mock_event_bus


def demonstrate_basic_lifecycle(communicator):
    """演示基本生命周期"""
    print("\n" + "="*60)
    print("🔄 演示基本生命周期")
    print("="*60)
    
    # 检查初始状态
    print(f"初始状态: is_running = {communicator.is_running}")
    print(f"初始统计: {communicator.get_stats()}")
    
    # 启动通信器
    print("\n启动虚拟 CAN 通信器...")
    success = communicator.start()
    print(f"启动结果: {success}")
    print(f"运行状态: {communicator.is_running}")
    
    # 等待一下让日志输出完整
    time.sleep(1)
    
    # 停止通信器
    print("\n停止虚拟 CAN 通信器...")
    success = communicator.stop()
    print(f"停止结果: {success}")
    print(f"运行状态: {communicator.is_running}")


def demonstrate_event_handling(communicator):
    """演示事件处理"""
    print("\n" + "="*60)
    print("📡 演示事件处理")
    print("="*60)
    
    # 启动通信器
    communicator.start()
    
    # 模拟警报触发事件
    print("\n模拟人员警报 TRIGGERED 事件...")
    triggered_event = {
        "status": PersonWarningStatus.TRIGGERED,
        "timestamp": time.time()
    }
    communicator._on_person_warning(triggered_event)
    
    # 检查状态
    stats = communicator.get_stats()
    print(f"事件处理后统计: {stats}")
    
    time.sleep(1)
    
    # 模拟警报清除事件
    print("\n模拟人员警报 CLEARED 事件...")
    cleared_event = {
        "status": PersonWarningStatus.CLEARED,
        "timestamp": time.time()
    }
    communicator._on_person_warning(cleared_event)
    
    # 检查最终状态
    stats = communicator.get_stats()
    print(f"最终统计: {stats}")


def demonstrate_coordinate_requests(communicator):
    """演示坐标请求模拟"""
    print("\n" + "="*60)
    print("📍 演示坐标请求模拟")
    print("="*60)
    
    # 执行多次坐标请求
    for i in range(4):
        print(f"\n第 {i+1} 次坐标请求:")
        coords = communicator.simulate_coordinate_request()
        print(f"返回坐标: x={coords[0]}, y={coords[1]}, z={coords[2]} (毫米)")
        time.sleep(0.5)  # 短暂延迟以便观察日志
    
    # 显示统计信息
    stats = communicator.get_stats()
    print(f"\n坐标请求统计: {stats['coordinate_request_count']} 次")


def demonstrate_statistics_management(communicator):
    """演示统计信息管理"""
    print("\n" + "="*60)
    print("📊 演示统计信息管理")
    print("="*60)
    
    # 启动并执行一些操作
    communicator.start()
    
    # 触发一些事件
    for i in range(2):
        triggered_event = {
            "status": PersonWarningStatus.TRIGGERED,
            "timestamp": time.time()
        }
        communicator._on_person_warning(triggered_event)
        
        cleared_event = {
            "status": PersonWarningStatus.CLEARED,
            "timestamp": time.time()
        }
        communicator._on_person_warning(cleared_event)
    
    # 执行一些坐标请求
    for i in range(3):
        communicator.simulate_coordinate_request()
    
    # 显示统计信息
    print("\n操作后的统计信息:")
    stats = communicator.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 重置统计信息
    print("\n重置统计信息...")
    communicator.reset_stats()
    
    # 显示重置后的统计信息
    print("\n重置后的统计信息:")
    stats = communicator.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def demonstrate_error_handling(communicator):
    """演示错误处理"""
    print("\n" + "="*60)
    print("⚠️  演示错误处理")
    print("="*60)
    
    communicator.start()
    
    # 模拟决策层异常
    print("\n模拟决策层异常...")
    original_side_effect = communicator.decision_layer.get_target_coords_snapshot.side_effect
    communicator.decision_layer.get_target_coords_snapshot.side_effect = Exception("模拟决策层异常")
    
    # 执行坐标请求（应该返回兜底坐标）
    coords = communicator.simulate_coordinate_request()
    print(f"异常情况下返回坐标: {coords}")
    
    # 恢复正常行为
    communicator.decision_layer.get_target_coords_snapshot.side_effect = original_side_effect
    
    # 模拟无效事件数据
    print("\n模拟无效事件数据...")
    invalid_event = {
        "status": "invalid_status",
        "timestamp": "invalid_timestamp"
    }
    
    # 处理无效事件（不应崩溃）
    try:
        communicator._on_person_warning(invalid_event)
        print("无效事件处理完成，未发生崩溃")
    except Exception as e:
        print(f"意外异常: {e}")


def main():
    """主演示函数"""
    print("🚀 虚拟 CAN 通信器功能演示")
    print("="*60)
    print("这是一个虚拟 CAN 通信器的功能演示脚本")
    print("适用于 Windows 开发环境和无硬件测试场景")
    print("="*60)
    
    # 创建配置
    config = CANConfigDTO(
        enable_can=False,  # 虚拟模式
        can_interface="socketcan",
        can_channel="can0",
        can_bitrate=250000,
        alert_interval_ms=500,
        send_timeout_ms=100
    )
    
    # 创建 Mock 依赖
    mock_decision_layer, mock_event_bus = create_mock_dependencies()
    
    # 创建虚拟通信器
    communicator = VirtualCANCommunicator(
        config=config,
        decision_layer=mock_decision_layer,
        event_bus=mock_event_bus
    )
    
    try:
        # 演示各种功能
        demonstrate_basic_lifecycle(communicator)
        demonstrate_event_handling(communicator)
        demonstrate_coordinate_requests(communicator)
        demonstrate_statistics_management(communicator)
        demonstrate_error_handling(communicator)
        
        print("\n" + "="*60)
        print("✅ 所有演示完成！")
        print("="*60)
        print("虚拟 CAN 通信器功能验证成功")
        print("可以在 Windows 开发环境中正常使用")
        
    except Exception as e:
        logger.error(f"演示过程中发生异常: {e}", exc_info=True)
        return 1
    
    finally:
        # 确保通信器被正确停止
        if communicator.is_running:
            communicator.stop()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)