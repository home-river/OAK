"""
虚拟 CAN 通信器核心最小测试

测试虚拟 CAN 通信器的核心功能：
1. 基本生命周期（初始化、启动、停止）
2. 事件处理（PERSON_WARNING 事件订阅和处理）
3. 坐标请求模拟
4. 统计信息管理
5. 接口兼容性（与真实 CAN 通信器相同的接口）

设计原则：
- 最小化测试：只测试核心功能，不过度测试边缘情况
- 快速执行：所有测试应在几秒内完成
- 无外部依赖：不依赖真实的 CAN 硬件或复杂的 Mock
- 验证关键行为：确保虚拟实现符合接口契约
"""

import logging
import time
import unittest
from unittest.mock import Mock, MagicMock
import numpy as np

from oak_vision_system.modules.can_communication.virtual_can_communicator import VirtualCANCommunicator
from oak_vision_system.modules.can_communication.can_communicator_base import CANCommunicatorBase
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
from oak_vision_system.modules.data_processing.decision_layer.types import PersonWarningStatus


class TestVirtualCANCommunicatorCore(unittest.TestCase):
    """虚拟 CAN 通信器核心功能测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试配置
        self.config = CANConfigDTO(
            enable_can=False,  # 虚拟模式
            can_interface="socketcan",
            can_channel="can0",
            can_bitrate=250000,
            alert_interval_ms=500,
            send_timeout_ms=100
        )
        
        # 创建 Mock 依赖
        self.mock_decision_layer = Mock()
        self.mock_event_bus = Mock()
        self.mock_event_bus.subscribe.return_value = "test_subscription_id"
        
        # 创建虚拟通信器实例
        self.communicator = VirtualCANCommunicator(
            config=self.config,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
    
    def test_inheritance_and_interface_compatibility(self):
        """测试继承关系和接口兼容性"""
        # 验证继承关系
        self.assertIsInstance(self.communicator, CANCommunicatorBase)
        self.assertIsInstance(self.communicator, VirtualCANCommunicator)
        
        # 验证必需的接口方法存在
        self.assertTrue(hasattr(self.communicator, 'start'))
        self.assertTrue(hasattr(self.communicator, 'stop'))
        self.assertTrue(hasattr(self.communicator, 'is_running'))
        self.assertTrue(callable(self.communicator.start))
        self.assertTrue(callable(self.communicator.stop))
        
        # 验证虚拟特有的方法存在
        self.assertTrue(hasattr(self.communicator, 'simulate_coordinate_request'))
        self.assertTrue(hasattr(self.communicator, 'get_stats'))
        self.assertTrue(hasattr(self.communicator, 'reset_stats'))
    
    def test_initial_state(self):
        """测试初始状态"""
        # 验证初始运行状态
        self.assertFalse(self.communicator.is_running)
        self.assertFalse(self.communicator._is_running)
        self.assertFalse(self.communicator._alert_active)
        
        # 验证初始统计计数器
        self.assertEqual(self.communicator.alert_triggered_count, 0)
        self.assertEqual(self.communicator.alert_cleared_count, 0)
        self.assertEqual(self.communicator.coordinate_request_count, 0)
        
        # 验证初始订阅状态
        self.assertIsNone(self.communicator._person_warning_subscription_id)
    
    def test_start_lifecycle(self):
        """测试启动生命周期"""
        # 验证初始状态
        self.assertFalse(self.communicator.is_running)
        
        # 启动通信器
        result = self.communicator.start()
        
        # 验证启动结果
        self.assertTrue(result)
        self.assertTrue(self.communicator.is_running)
        self.assertTrue(self.communicator._is_running)
        
        # 验证事件订阅
        self.mock_event_bus.subscribe.assert_called_once()
        call_args = self.mock_event_bus.subscribe.call_args
        self.assertEqual(call_args[1]['event_type'], 'person_warning')  # EventType.PERSON_WARNING
        self.assertEqual(call_args[1]['callback'], self.communicator._on_person_warning)
        self.assertEqual(call_args[1]['subscriber_name'], "VirtualCANCommunicator._on_person_warning")
        
        # 验证订阅 ID 被保存
        self.assertEqual(self.communicator._person_warning_subscription_id, "test_subscription_id")
    
    def test_start_idempotence(self):
        """测试启动的幂等性"""
        # 第一次启动
        result1 = self.communicator.start()
        self.assertTrue(result1)
        self.assertTrue(self.communicator.is_running)
        
        # 第二次启动（应该是幂等的）
        result2 = self.communicator.start()
        self.assertTrue(result2)
        self.assertTrue(self.communicator.is_running)
        
        # 验证事件订阅只被调用一次
        self.assertEqual(self.mock_event_bus.subscribe.call_count, 1)
    
    def test_stop_lifecycle(self):
        """测试停止生命周期"""
        # 先启动
        self.communicator.start()
        self.assertTrue(self.communicator.is_running)
        
        # 停止通信器
        result = self.communicator.stop()
        
        # 验证停止结果
        self.assertTrue(result)
        self.assertFalse(self.communicator.is_running)
        self.assertFalse(self.communicator._is_running)
        self.assertFalse(self.communicator._alert_active)
        
        # 验证事件取消订阅
        self.mock_event_bus.unsubscribe.assert_called_once_with("test_subscription_id")
        
        # 验证订阅 ID 被清理
        self.assertIsNone(self.communicator._person_warning_subscription_id)
    
    def test_stop_idempotence(self):
        """测试停止的幂等性"""
        # 先启动再停止
        self.communicator.start()
        result1 = self.communicator.stop()
        self.assertTrue(result1)
        self.assertFalse(self.communicator.is_running)
        
        # 第二次停止（应该是幂等的）
        result2 = self.communicator.stop()
        self.assertTrue(result2)
        self.assertFalse(self.communicator.is_running)
        
        # 验证取消订阅只被调用一次
        self.assertEqual(self.mock_event_bus.unsubscribe.call_count, 1)
    
    def test_person_warning_triggered_event(self):
        """测试 PERSON_WARNING TRIGGERED 事件处理"""
        # 启动通信器
        self.communicator.start()
        
        # 模拟 TRIGGERED 事件
        event_data = {
            "status": PersonWarningStatus.TRIGGERED,
            "timestamp": time.time()
        }
        
        # 处理事件
        self.communicator._on_person_warning(event_data)
        
        # 验证状态更新
        self.assertTrue(self.communicator._alert_active)
        self.assertEqual(self.communicator.alert_triggered_count, 1)
        self.assertEqual(self.communicator.alert_cleared_count, 0)
    
    def test_person_warning_cleared_event(self):
        """测试 PERSON_WARNING CLEARED 事件处理"""
        # 启动通信器并触发警报
        self.communicator.start()
        self.communicator._alert_active = True
        self.communicator.alert_triggered_count = 1
        
        # 模拟 CLEARED 事件
        event_data = {
            "status": PersonWarningStatus.CLEARED,
            "timestamp": time.time()
        }
        
        # 处理事件
        self.communicator._on_person_warning(event_data)
        
        # 验证状态更新
        self.assertFalse(self.communicator._alert_active)
        self.assertEqual(self.communicator.alert_triggered_count, 1)  # 保持不变
        self.assertEqual(self.communicator.alert_cleared_count, 1)    # 增加
    
    def test_simulate_coordinate_request_with_valid_coords(self):
        """测试坐标请求模拟（有效坐标）"""
        # 设置决策层返回有效坐标（米单位）
        coords_meters = np.array([1.5, 2.0, 0.8])  # 1.5m, 2.0m, 0.8m
        self.mock_decision_layer.get_target_coords_snapshot.return_value = coords_meters
        
        # 调用坐标请求模拟
        result = self.communicator.simulate_coordinate_request()
        
        # 验证返回值（应转换为毫米）
        expected = (1500, 2000, 800)  # 毫米单位
        self.assertEqual(result, expected)
        
        # 验证统计计数器
        self.assertEqual(self.communicator.coordinate_request_count, 1)
        
        # 验证决策层被调用
        self.mock_decision_layer.get_target_coords_snapshot.assert_called_once()
    
    def test_simulate_coordinate_request_with_none_coords(self):
        """测试坐标请求模拟（无目标坐标）"""
        # 设置决策层返回 None
        self.mock_decision_layer.get_target_coords_snapshot.return_value = None
        
        # 调用坐标请求模拟
        result = self.communicator.simulate_coordinate_request()
        
        # 验证返回兜底坐标
        expected = (0, 0, 0)
        self.assertEqual(result, expected)
        
        # 验证统计计数器
        self.assertEqual(self.communicator.coordinate_request_count, 1)
    
    def test_simulate_coordinate_request_with_exception(self):
        """测试坐标请求模拟（决策层异常）"""
        # 设置决策层抛出异常
        self.mock_decision_layer.get_target_coords_snapshot.side_effect = Exception("决策层异常")
        
        # 调用坐标请求模拟（不应抛出异常）
        result = self.communicator.simulate_coordinate_request()
        
        # 验证返回兜底坐标
        expected = (0, 0, 0)
        self.assertEqual(result, expected)
        
        # 验证统计计数器仍然增加
        self.assertEqual(self.communicator.coordinate_request_count, 1)
    
    def test_get_stats(self):
        """测试统计信息获取"""
        # 设置一些状态
        self.communicator.start()
        self.communicator._alert_active = True
        self.communicator.alert_triggered_count = 3
        self.communicator.alert_cleared_count = 2
        self.communicator.coordinate_request_count = 5
        
        # 获取统计信息
        stats = self.communicator.get_stats()
        
        # 验证统计信息
        expected_stats = {
            "is_running": True,
            "alert_active": True,
            "alert_triggered_count": 3,
            "alert_cleared_count": 2,
            "coordinate_request_count": 5
        }
        self.assertEqual(stats, expected_stats)
    
    def test_reset_stats(self):
        """测试统计信息重置"""
        # 设置一些统计数据
        self.communicator.start()
        self.communicator._alert_active = True
        self.communicator.alert_triggered_count = 3
        self.communicator.alert_cleared_count = 2
        self.communicator.coordinate_request_count = 5
        
        # 重置统计信息
        self.communicator.reset_stats()
        
        # 验证计数器被重置
        self.assertEqual(self.communicator.alert_triggered_count, 0)
        self.assertEqual(self.communicator.alert_cleared_count, 0)
        self.assertEqual(self.communicator.coordinate_request_count, 0)
        
        # 验证状态标志未被重置
        self.assertTrue(self.communicator.is_running)
        self.assertTrue(self.communicator._alert_active)
    
    def test_event_handling_exception_safety(self):
        """测试事件处理的异常安全性"""
        # 启动通信器
        self.communicator.start()
        
        # 模拟无效的事件数据
        invalid_event_data = {
            "status": "invalid_status",  # 无效状态
            "timestamp": "invalid_timestamp"  # 无效时间戳
        }
        
        # 处理事件（不应抛出异常）
        try:
            self.communicator._on_person_warning(invalid_event_data)
        except Exception as e:
            self.fail(f"事件处理不应抛出异常: {e}")
        
        # 验证统计计数器未被错误更新
        self.assertEqual(self.communicator.alert_triggered_count, 0)
        self.assertEqual(self.communicator.alert_cleared_count, 0)


class TestVirtualCANCommunicatorIntegration(unittest.TestCase):
    """虚拟 CAN 通信器集成测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = CANConfigDTO(enable_can=False)
        self.mock_decision_layer = Mock()
        self.mock_event_bus = Mock()
        self.mock_event_bus.subscribe.return_value = "test_subscription_id"
        
        self.communicator = VirtualCANCommunicator(
            config=self.config,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
    
    def test_complete_workflow(self):
        """测试完整的工作流程"""
        # 1. 启动通信器
        start_result = self.communicator.start()
        self.assertTrue(start_result)
        self.assertTrue(self.communicator.is_running)
        
        # 2. 处理警报触发事件
        triggered_event = {
            "status": PersonWarningStatus.TRIGGERED,
            "timestamp": time.time()
        }
        self.communicator._on_person_warning(triggered_event)
        self.assertTrue(self.communicator._alert_active)
        self.assertEqual(self.communicator.alert_triggered_count, 1)
        
        # 3. 模拟坐标请求
        self.mock_decision_layer.get_target_coords_snapshot.return_value = np.array([1.0, 2.0, 3.0])
        coords = self.communicator.simulate_coordinate_request()
        self.assertEqual(coords, (1000, 2000, 3000))
        self.assertEqual(self.communicator.coordinate_request_count, 1)
        
        # 4. 处理警报清除事件
        cleared_event = {
            "status": PersonWarningStatus.CLEARED,
            "timestamp": time.time()
        }
        self.communicator._on_person_warning(cleared_event)
        self.assertFalse(self.communicator._alert_active)
        self.assertEqual(self.communicator.alert_cleared_count, 1)
        
        # 5. 检查统计信息
        stats = self.communicator.get_stats()
        expected_stats = {
            "is_running": True,
            "alert_active": False,
            "alert_triggered_count": 1,
            "alert_cleared_count": 1,
            "coordinate_request_count": 1
        }
        self.assertEqual(stats, expected_stats)
        
        # 6. 重置统计信息
        self.communicator.reset_stats()
        self.assertEqual(self.communicator.alert_triggered_count, 0)
        self.assertEqual(self.communicator.alert_cleared_count, 0)
        self.assertEqual(self.communicator.coordinate_request_count, 0)
        
        # 7. 停止通信器
        stop_result = self.communicator.stop()
        self.assertTrue(stop_result)
        self.assertFalse(self.communicator.is_running)
    
    def test_multiple_events_handling(self):
        """测试多个事件的处理"""
        self.communicator.start()
        
        # 模拟多次警报触发和清除
        for i in range(3):
            # 触发警报
            triggered_event = {
                "status": PersonWarningStatus.TRIGGERED,
                "timestamp": time.time()
            }
            self.communicator._on_person_warning(triggered_event)
            
            # 清除警报
            cleared_event = {
                "status": PersonWarningStatus.CLEARED,
                "timestamp": time.time()
            }
            self.communicator._on_person_warning(cleared_event)
        
        # 验证统计计数器
        self.assertEqual(self.communicator.alert_triggered_count, 3)
        self.assertEqual(self.communicator.alert_cleared_count, 3)
        self.assertFalse(self.communicator._alert_active)  # 最后状态应为非活跃
    
    def test_multiple_coordinate_requests(self):
        """测试多次坐标请求"""
        # 设置不同的坐标返回值
        coords_sequence = [
            np.array([1.0, 2.0, 3.0]),
            None,  # 无目标
            np.array([4.0, 5.0, 6.0]),
        ]
        self.mock_decision_layer.get_target_coords_snapshot.side_effect = coords_sequence
        
        # 执行多次坐标请求
        results = []
        for _ in range(3):
            result = self.communicator.simulate_coordinate_request()
            results.append(result)
        
        # 验证结果
        expected_results = [
            (1000, 2000, 3000),  # 第一次：有效坐标
            (0, 0, 0),           # 第二次：无目标，兜底坐标
            (4000, 5000, 6000),  # 第三次：有效坐标
        ]
        self.assertEqual(results, expected_results)
        
        # 验证统计计数器
        self.assertEqual(self.communicator.coordinate_request_count, 3)


if __name__ == '__main__':
    # 配置日志以便调试
    logging.basicConfig(level=logging.INFO)
    
    # 运行测试
    unittest.main(verbosity=2)