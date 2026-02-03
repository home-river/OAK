"""
测试 OAKDataCollector 的 stop() 方法规范合规性

验证 OAKDataCollector 的 stop() 方法符合子模块规范：
- 幂等性：可以被多次调用而不出错
- 返回值：返回 bool 类型表示成功/失败
- 超时处理：正确处理超时情况
- 线程安全：使用锁保护状态
"""

import time
import unittest
import threading
from unittest.mock import Mock, patch, MagicMock

from oak_vision_system.core.dto.config_dto import (
    OAKModuleConfigDTO,
    OAKConfigDTO,
    DeviceRoleBindingDTO,
)
from oak_vision_system.core.dto.config_dto.enums import DeviceRole
from oak_vision_system.modules.data_collector.collector import OAKDataCollector


class TestOAKDataCollectorStopCompliance(unittest.TestCase):
    """测试 OAKDataCollector 的 stop() 方法规范合规性"""
    
    def setUp(self):
        """测试前准备"""
        # 创建测试配置
        hardware_config = OAKConfigDTO(
            enable_depth_output=False,
            hardware_fps=20,
            usb2_mode=False,
            queue_max_size=4,
            queue_blocking=False,
        )
        
        # 创建设备绑定
        role_bindings = {
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="test_device_1",
            ),
            DeviceRole.RIGHT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.RIGHT_CAMERA,
                active_mxid="test_device_2",
            ),
        }
        
        self.config = OAKModuleConfigDTO(
            hardware_config=hardware_config,
            role_bindings=role_bindings,
        )
        
        self.collectors = []
    
    def tearDown(self):
        """测试后清理"""
        for collector in self.collectors:
            try:
                collector.stop(timeout=1.0)
            except:
                pass
        self.collectors.clear()
        time.sleep(0.1)
    
    def test_idempotence_without_start(self):
        """测试幂等性：未启动时多次调用 stop()"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 第一次停止（未启动）
        result1 = collector.stop(timeout=2.0)
        self.assertTrue(result1, "未启动时第一次停止应该返回 True")
        
        # 第二次停止（幂等性）
        result2 = collector.stop(timeout=2.0)
        self.assertTrue(result2, "未启动时第二次停止应该返回 True（幂等性）")
        
        # 第三次停止（幂等性）
        result3 = collector.stop(timeout=2.0)
        self.assertTrue(result3, "未启动时第三次停止应该返回 True（幂等性）")
    
    def test_idempotence_with_mock_threads(self):
        """测试幂等性：使用 Mock 线程模拟启动后多次停止"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 模拟启动：创建 Mock 线程
        mock_thread1 = Mock()
        mock_thread1.is_alive.return_value = False  # 线程已停止
        mock_thread2 = Mock()
        mock_thread2.is_alive.return_value = False  # 线程已停止
        
        collector._worker_threads = {
            "left_camera": mock_thread1,
            "right_camera": mock_thread2,
        }
        collector.running = {
            "left_camera": True,
            "right_camera": True,
        }
        
        # 第一次停止
        result1 = collector.stop(timeout=2.0)
        self.assertTrue(result1, "第一次停止应该返回 True")
        
        # 第二次停止（幂等性）
        result2 = collector.stop(timeout=2.0)
        self.assertTrue(result2, "第二次停止应该返回 True（幂等性）")
        
        # 第三次停止（幂等性）
        result3 = collector.stop(timeout=2.0)
        self.assertTrue(result3, "第三次停止应该返回 True（幂等性）")
    
    def test_returns_bool(self):
        """测试返回值：stop() 返回 bool 类型"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 停止并检查返回值类型
        result = collector.stop(timeout=2.0)
        self.assertIsInstance(result, bool, "stop() 应该返回 bool 类型")
        self.assertTrue(result, "成功停止应该返回 True")
    
    def test_timeout_handling(self):
        """测试超时处理：线程超时时返回 False"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 模拟启动：创建一个永不停止的 Mock 线程
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True  # 线程一直运行
        mock_thread.join = Mock()  # join 不会改变状态
        
        collector._worker_threads = {
            "left_camera": mock_thread,
        }
        collector.running = {
            "left_camera": True,
        }
        
        # 停止并验证超时处理
        result = collector.stop(timeout=0.1)  # 使用很短的超时
        self.assertFalse(result, "线程超时时应该返回 False")
        
        # 验证 join 被调用且带有超时参数
        mock_thread.join.assert_called_once_with(timeout=0.1)
    
    def test_thread_safety(self):
        """测试线程安全：并发调用 stop() 不会导致错误"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 模拟启动：创建 Mock 线程
        mock_thread1 = Mock()
        mock_thread1.is_alive.return_value = False
        mock_thread2 = Mock()
        mock_thread2.is_alive.return_value = False
        
        collector._worker_threads = {
            "left_camera": mock_thread1,
            "right_camera": mock_thread2,
        }
        collector.running = {
            "left_camera": True,
            "right_camera": True,
        }
        
        # 并发调用 stop()
        results = []
        
        def stop_collector():
            result = collector.stop(timeout=2.0)
            results.append(result)
        
        threads = [threading.Thread(target=stop_collector) for _ in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证所有调用都成功（返回 True）
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertTrue(result, "所有并发 stop() 调用都应该返回 True")
    
    def test_partial_failure(self):
        """测试部分失败：部分线程超时时返回 False"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 模拟启动：一个线程成功停止，一个线程超时
        mock_thread1 = Mock()
        mock_thread1.is_alive.return_value = False  # 成功停止
        
        mock_thread2 = Mock()
        mock_thread2.is_alive.return_value = True  # 超时
        mock_thread2.join = Mock()
        
        collector._worker_threads = {
            "left_camera": mock_thread1,
            "right_camera": mock_thread2,
        }
        collector.running = {
            "left_camera": True,
            "right_camera": True,
        }
        
        # 停止并验证部分失败
        result = collector.stop(timeout=0.1)
        self.assertFalse(result, "部分线程超时时应该返回 False")
        
        # 验证超时的线程不会被清理
        self.assertIn("right_camera", collector._worker_threads, "超时的线程不应该被清理")
    
    def test_exception_handling(self):
        """测试异常处理：线程 join 抛出异常时返回 False"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 模拟启动：创建一个会抛出异常的 Mock 线程
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_thread.join.side_effect = RuntimeError("Mock join error")
        
        collector._worker_threads = {
            "left_camera": mock_thread,
        }
        collector.running = {
            "left_camera": True,
        }
        
        # 停止并验证异常处理
        result = collector.stop(timeout=2.0)
        self.assertFalse(result, "线程 join 抛出异常时应该返回 False")
    
    def test_all_threads_success(self):
        """测试所有线程成功停止时返回 True"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 模拟启动：所有线程都成功停止
        mock_thread1 = Mock()
        mock_thread1.is_alive.return_value = False
        mock_thread2 = Mock()
        mock_thread2.is_alive.return_value = False
        
        collector._worker_threads = {
            "left_camera": mock_thread1,
            "right_camera": mock_thread2,
        }
        collector.running = {
            "left_camera": True,
            "right_camera": True,
        }
        
        # 停止并验证成功
        result = collector.stop(timeout=2.0)
        self.assertTrue(result, "所有线程成功停止时应该返回 True")
        
        # 验证线程被清理
        self.assertEqual(len(collector._worker_threads), 0, "成功停止后应该清理所有线程")
    
    def test_default_timeout(self):
        """测试默认超时参数"""
        collector = OAKDataCollector(config=self.config)
        self.collectors.append(collector)
        
        # 模拟启动
        mock_thread = Mock()
        mock_thread.is_alive.return_value = False
        
        collector._worker_threads = {
            "left_camera": mock_thread,
        }
        collector.running = {
            "left_camera": True,
        }
        
        # 不传入 timeout 参数，使用默认值
        result = collector.stop()
        self.assertTrue(result, "使用默认超时应该成功")


if __name__ == '__main__':
    unittest.main()
