"""
测试显示模块的统计和监控功能

验证需求：
- 13.1: 提供 get_stats() 方法返回统计信息
- 13.2: 统计信息包含当前FPS、总渲染帧数、丢弃帧数、队列使用率、运行时长
- 13.4: 统计信息线程安全
"""

import unittest
import time
import threading
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacketPackager,
    RenderPacket,
)


class TestDisplayStats(unittest.TestCase):
    """测试显示模块的统计功能"""
    
    def setUp(self):
        """测试前准备"""
        self.device_id = "test_device_001"
        self.devices_list = [self.device_id]
        
        # 创建配置（禁用显示以避免创建窗口）
        self.config = DisplayConfigDTO(
            enable_display=False,
            target_fps=30,
            window_width=640,
            window_height=480,
        )
    
    def test_renderer_stats_structure(self):
        """测试 DisplayRenderer 的统计信息结构（需求 13.1, 13.2）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
        )
        
        renderer = DisplayRenderer(
            config=self.config,
            packager=packager,
            devices_list=self.devices_list,
        )
        
        # 获取统计信息
        stats = renderer.get_stats()
        
        # 验证统计信息包含必要字段（需求 13.2）
        self.assertIn("frames_rendered", stats)
        self.assertIn("fps", stats)
        self.assertIn("fps_history", stats)
        self.assertIn("avg_fps", stats)
        self.assertIn("min_fps", stats)
        self.assertIn("max_fps", stats)
        self.assertIn("runtime_sec", stats)
        self.assertIn("is_running", stats)
        
        # 验证初始值
        self.assertEqual(stats["frames_rendered"], 0)
        self.assertEqual(stats["fps"], 0.0)
        self.assertEqual(len(stats["fps_history"]), 0)
        self.assertFalse(stats["is_running"])
    
    def test_manager_stats_structure(self):
        """测试 DisplayManager 的统计信息结构（需求 13.1, 13.2）"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        
        # 获取统计信息
        stats = manager.get_stats()
        
        # 验证统计信息包含必要字段（需求 13.2）
        self.assertIn("packager", stats)
        self.assertIn("renderer", stats)
        self.assertIn("queue_stats", stats)
        self.assertIn("total_queue_drops", stats)
        self.assertIn("total_drops", stats)
        
        # 验证 packager 统计信息
        packager_stats = stats["packager"]
        self.assertIn("render_packets", packager_stats)
        self.assertIn("drops", packager_stats)
        
        # 验证 renderer 统计信息
        renderer_stats = stats["renderer"]
        self.assertIn("frames_rendered", renderer_stats)
        self.assertIn("fps", renderer_stats)
        
        # 验证队列统计信息
        queue_stats = stats["queue_stats"]
        self.assertIn(self.device_id, queue_stats)
        
        device_queue_stats = queue_stats[self.device_id]
        self.assertIn("size", device_queue_stats)
        self.assertIn("maxsize", device_queue_stats)
        self.assertIn("usage_ratio", device_queue_stats)
        self.assertIn("drop_count", device_queue_stats)
    
    def test_fps_history_collection(self):
        """测试 FPS 历史记录收集（需求 13.2）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
        )
        
        renderer = DisplayRenderer(
            config=self.config,
            packager=packager,
            devices_list=self.devices_list,
        )
        
        # 模拟多次 FPS 更新
        with renderer._stats_lock:
            renderer._stats["fps_history"] = [20.0, 25.0, 30.0, 28.0, 26.0]
        
        stats = renderer.get_stats()
        
        # 验证 FPS 历史记录
        self.assertEqual(len(stats["fps_history"]), 5)
        self.assertEqual(stats["fps_history"], [20.0, 25.0, 30.0, 28.0, 26.0])
        
        # 验证统计计算
        self.assertAlmostEqual(stats["avg_fps"], 25.8, places=1)
        self.assertEqual(stats["min_fps"], 20.0)
        self.assertEqual(stats["max_fps"], 30.0)
    
    def test_stats_thread_safety(self):
        """测试统计信息的线程安全（需求 13.4）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
        )
        
        renderer = DisplayRenderer(
            config=self.config,
            packager=packager,
            devices_list=self.devices_list,
        )
        
        # 创建多个线程同时访问统计信息
        results = []
        errors = []
        
        def read_stats():
            try:
                for _ in range(100):
                    stats = renderer.get_stats()
                    results.append(stats)
            except Exception as e:
                errors.append(e)
        
        def update_stats():
            try:
                for _ in range(100):
                    with renderer._stats_lock:
                        renderer._stats["frames_rendered"] += 1
                        renderer._stats["fps_history"].append(25.0)
            except Exception as e:
                errors.append(e)
        
        # 启动多个读写线程
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=read_stats))
            threads.append(threading.Thread(target=update_stats))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # 验证没有发生错误
        self.assertEqual(len(errors), 0, f"线程安全测试失败: {errors}")
        
        # 验证统计信息一致性
        final_stats = renderer.get_stats()
        self.assertEqual(final_stats["frames_rendered"], 500)  # 5个线程 × 100次
    
    def test_packager_stats_thread_safety(self):
        """测试 RenderPacketPackager 统计信息的线程安全（需求 13.4）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
        )
        
        errors = []
        
        def update_stats():
            try:
                for _ in range(100):
                    with packager._stats_lock:
                        packager._stats["render_packets"] += 1
            except Exception as e:
                errors.append(e)
        
        def read_stats():
            try:
                for _ in range(100):
                    with packager._stats_lock:
                        _ = packager._stats["render_packets"]
                        _ = packager._stats["drops"]
            except Exception as e:
                errors.append(e)
        
        # 启动多个读写线程
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=update_stats))
            threads.append(threading.Thread(target=read_stats))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # 验证没有发生错误
        self.assertEqual(len(errors), 0, f"线程安全测试失败: {errors}")
        
        # 验证统计信息一致性
        with packager._stats_lock:
            render_packets = packager._stats["render_packets"]
        
        self.assertEqual(render_packets, 500)  # 5个线程 × 100次
    
    def test_total_drops_calculation(self):
        """测试总丢弃数量的计算（需求 13.2）"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        
        # 模拟一些丢弃
        with manager._packager._stats_lock:
            manager._packager._stats["drops"] = 10
        
        # 模拟队列溢出丢弃
        # 注意：OverflowQueue 的 drop_count 需要通过实际溢出来增加
        # 这里我们只验证计算逻辑
        
        stats = manager.get_stats()
        
        # 验证总丢弃数量包含配对超时丢弃
        self.assertGreaterEqual(stats["total_drops"], 10)
        self.assertEqual(stats["packager"]["drops"], 10)


if __name__ == "__main__":
    unittest.main()
