"""
测试显示模块的 stop() 方法规范合规性

验证 DisplayManager 和 RenderPacketPackager 的 stop() 方法符合子模块规范：
- 幂等性：可以被多次调用而不出错
- 返回值：返回 bool 类型表示成功/失败
- 超时处理：正确处理超时情况
- 线程安全：使用锁保护状态
"""

import time
import unittest
import threading
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacketPackager,
)


class TestRenderPacketPackagerCompliance(unittest.TestCase):
    """测试 RenderPacketPackager 的 stop() 方法规范合规性"""
    
    def setUp(self):
        """测试前准备"""
        self.devices_list = ["device1", "device2"]
        self.packagers = []
    
    def tearDown(self):
        """测试后清理"""
        for packager in self.packagers:
            try:
                packager.stop(timeout=1.0)
            except:
                pass
        self.packagers.clear()
        time.sleep(0.1)
    
    def test_packager_idempotence(self):
        """测试幂等性：stop() 可以被多次调用"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)
        
        # 启动打包器
        packager.start()
        time.sleep(0.1)
        
        # 第一次停止
        result1 = packager.stop(timeout=2.0)
        self.assertTrue(result1, "第一次停止应该返回 True")
        
        # 第二次停止（幂等性）
        result2 = packager.stop(timeout=2.0)
        self.assertTrue(result2, "第二次停止应该返回 True（幂等性）")
        
        # 第三次停止（幂等性）
        result3 = packager.stop(timeout=2.0)
        self.assertTrue(result3, "第三次停止应该返回 True（幂等性）")
    
    def test_packager_returns_bool(self):
        """测试返回值：stop() 返回 bool 类型"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)
        
        # 启动打包器
        packager.start()
        time.sleep(0.1)
        
        # 停止并检查返回值类型
        result = packager.stop(timeout=2.0)
        self.assertIsInstance(result, bool, "stop() 应该返回 bool 类型")
        self.assertTrue(result, "成功停止应该返回 True")
    
    def test_packager_thread_safety(self):
        """测试线程安全：并发调用 stop() 不会导致错误"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)
        
        # 启动打包器
        packager.start()
        time.sleep(0.1)
        
        # 并发调用 stop()
        results = []
        
        def stop_packager():
            result = packager.stop(timeout=2.0)
            results.append(result)
        
        threads = [threading.Thread(target=stop_packager) for _ in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证所有调用都成功（返回 True）
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertTrue(result, "所有并发 stop() 调用都应该返回 True")
    
    def test_packager_start_idempotence(self):
        """测试 start() 的幂等性"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)
        
        # 第一次启动
        result1 = packager.start()
        self.assertTrue(result1, "第一次启动应该返回 True")
        time.sleep(0.1)
        
        # 第二次启动（幂等性）
        result2 = packager.start()
        self.assertFalse(result2, "第二次启动应该返回 False（已在运行）")


class TestDisplayManagerCompliance(unittest.TestCase):
    """测试 DisplayManager 的 stop() 方法规范合规性"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=False,  # 禁用显示以避免创建窗口
            window_width=640,
            window_height=480,
            target_fps=30,
        )
        self.devices_list = ["device1", "device2"]
        self.managers = []
    
    def tearDown(self):
        """测试后清理"""
        for manager in self.managers:
            try:
                manager.stop(timeout=1.0)
            except:
                pass
        self.managers.clear()
        time.sleep(0.1)
    
    def test_manager_idempotence(self):
        """测试幂等性：stop() 可以被多次调用"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 第一次停止
        result1 = manager.stop(timeout=2.0)
        self.assertTrue(result1, "第一次停止应该返回 True")
        
        # 第二次停止（幂等性）
        result2 = manager.stop(timeout=2.0)
        self.assertTrue(result2, "第二次停止应该返回 True（幂等性）")
        
        # 第三次停止（幂等性）
        result3 = manager.stop(timeout=2.0)
        self.assertTrue(result3, "第三次停止应该返回 True（幂等性）")
    
    def test_manager_returns_bool(self):
        """测试返回值：stop() 返回 bool 类型"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 停止并检查返回值类型
        result = manager.stop(timeout=2.0)
        self.assertIsInstance(result, bool, "stop() 应该返回 bool 类型")
        self.assertTrue(result, "成功停止应该返回 True")
    
    def test_manager_thread_safety(self):
        """测试线程安全：并发调用 stop() 不会导致错误"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 并发调用 stop()
        results = []
        
        def stop_manager():
            result = manager.stop(timeout=2.0)
            results.append(result)
        
        threads = [threading.Thread(target=stop_manager) for _ in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证所有调用都成功（返回 True）
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertTrue(result, "所有并发 stop() 调用都应该返回 True")
    
    def test_manager_start_idempotence(self):
        """测试 start() 的幂等性"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 第一次启动
        result1 = manager.start()
        self.assertTrue(result1, "第一次启动应该返回 True")
        time.sleep(0.1)
        
        # 第二次启动（幂等性）
        result2 = manager.start()
        self.assertFalse(result2, "第二次启动应该返回 False（已在运行）")
    
    def test_manager_and_logic_both_success(self):
        """测试 AND 逻辑：两个子模块都成功停止时返回 True"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 停止管理器（两个子模块都应该成功）
        result = manager.stop(timeout=2.0)
        self.assertTrue(result, "两个子模块都成功停止时应该返回 True")
    
    def test_manager_is_running_property(self):
        """测试 is_running 属性使用内部状态标志"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 初始状态：未运行
        self.assertFalse(manager.is_running, "初始状态应该是未运行")
        
        # 启动后：运行中
        manager.start()
        time.sleep(0.1)
        self.assertTrue(manager.is_running, "启动后应该是运行中")
        
        # 停止后：未运行
        manager.stop(timeout=2.0)
        self.assertFalse(manager.is_running, "停止后应该是未运行")


if __name__ == '__main__':
    unittest.main()
