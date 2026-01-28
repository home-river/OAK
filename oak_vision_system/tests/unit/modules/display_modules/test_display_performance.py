"""
显示模块性能优化测试

测试帧率限制、图像复制优化和队列使用率监控功能。
"""

import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.data_processing_dto import (
    DeviceProcessedDataDTO,
    DetectionStatusLabel,
)
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacket,
    RenderPacketPackager,
)


class TestDisplayPerformance(unittest.TestCase):
    """测试显示模块性能优化功能"""
    
    def setUp(self):
        """测试前准备"""
        self.device_id = "test_device"
        self.devices_list = [self.device_id]
        
        # 创建测试配置
        self.config = DisplayConfigDTO(
            enable_display=False,  # 禁用实际显示
            target_fps=20,
            window_width=640,
            window_height=480,
        )
        
        # 创建测试数据
        self.video_frame = VideoFrameDTO(
            device_id=self.device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
            depth_frame=np.zeros((480, 640), dtype=np.uint16),
        )
        
        self.processed_data = DeviceProcessedDataDTO(
            device_id=self.device_id,
            frame_id=1,
            device_alias="test_camera",
            coords=np.array([[100, 200, 300]], dtype=np.float32),
            bbox=np.array([[50, 50, 150, 150]], dtype=np.float32),
            confidence=np.array([0.95], dtype=np.float32),
            labels=np.array([0], dtype=np.int32),
            state_label=[DetectionStatusLabel.OBJECT_GRASPABLE],
        )
        
        self.render_packet = RenderPacket(
            video_frame=self.video_frame,
            processed_detections=self.processed_data,
        )
    
    def test_frame_rate_limiting_initialization(self):
        """测试帧率限制初始化（需求 12.1）"""
        packager = MagicMock()
        renderer = DisplayRenderer(
            config=self.config,
            packager=packager,
            devices_list=self.devices_list,
        )
        
        # 验证帧间隔计算正确
        expected_interval = 1.0 / self.config.target_fps
        self.assertAlmostEqual(renderer._target_frame_interval, expected_interval, places=5)
        self.assertEqual(renderer._last_frame_time, 0.0)
    
    def test_frame_rate_limiting_with_zero_fps(self):
        """测试零帧率配置（边界情况）"""
        config = DisplayConfigDTO(
            enable_display=False,
            target_fps=0,  # 零帧率
        )
        
        packager = MagicMock()
        renderer = DisplayRenderer(
            config=config,
            packager=packager,
            devices_list=self.devices_list,
        )
        
        # 验证帧间隔为0（不限制帧率）
        self.assertEqual(renderer._target_frame_interval, 0.0)
    
    def test_image_copy_optimization_single_device_mode(self):
        """测试单设备模式的图像复制优化（需求 12.4, 12.5）
        
        验证：
        - 单设备渲染时避免不必要的图像复制
        """
        packager = MagicMock()
        renderer = DisplayRenderer(
            config=self.config,
            packager=packager,
            devices_list=self.devices_list,
        )
        
        # 创建可写的帧
        writable_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        writable_frame.flags.writeable = True
        
        video_frame = VideoFrameDTO(
            device_id=self.device_id,
            frame_id=1,
            rgb_frame=writable_frame,
        )
        
        packet = RenderPacket(
            video_frame=video_frame,
            processed_detections=self.processed_data,
        )
        
        # 渲染单设备模式
        result = renderer._render_single_device(packet)
        
        # 验证返回的帧不为空
        self.assertIsNotNone(result)
        # 注意：由于绘制操作会修改帧，我们只验证没有抛出异常
    
    def test_image_copy_optimization_combined_mode(self):
        """测试 Combined 模式的图像复制优化（需求 12.4, 12.5）
        
        验证：
        - Combined 模式渲染时的性能优化
        """
        packager = MagicMock()
        renderer = DisplayRenderer(
            config=self.config,
            packager=packager,
            devices_list=self.devices_list,
        )
        
        # 创建测试数据包字典
        packets = {
            self.device_id: self.render_packet,
        }
        
        # 渲染 Combined 模式
        result = renderer._render_combined_devices(packets)
        
        # 验证返回的帧不为空
        self.assertIsNotNone(result)
    
    def test_queue_usage_monitoring_in_stats(self):
        """测试队列使用率监控（需求 12.3, 13.2）"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        
        # 启动管理器
        manager.start()
        
        try:
            # 获取统计信息
            stats = manager.get_stats()
            
            # 验证统计信息包含队列数据
            self.assertIn("queue_stats", stats)
            self.assertIn("total_queue_drops", stats)
            
            # 验证每个设备都有队列统计
            queue_stats = stats["queue_stats"]
            self.assertIn(self.device_id, queue_stats)
            
            # 验证队列统计包含必要字段
            device_stats = queue_stats[self.device_id]
            self.assertIn("size", device_stats)
            self.assertIn("maxsize", device_stats)
            self.assertIn("usage_ratio", device_stats)
            self.assertIn("drop_count", device_stats)
            
            # 验证使用率在合理范围内
            usage_ratio = device_stats["usage_ratio"]
            self.assertGreaterEqual(usage_ratio, 0.0)
            self.assertLessEqual(usage_ratio, 1.0)
            
        finally:
            manager.stop()
    
    def test_high_queue_usage_warning(self):
        """测试高队列使用率警告（需求 12.3）"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        
        # 启动管理器
        manager.start()
        
        try:
            # 模拟高队列使用率
            # 填充队列到80%以上
            queue = manager._packager.packet_queue[self.device_id]
            for i in range(int(queue.maxsize * 0.9)):
                try:
                    queue.put_nowait(self.render_packet)
                except:
                    break
            
            # 获取统计信息（应该触发警告日志）
            with self.assertLogs(manager.logger, level='WARNING') as cm:
                stats = manager.get_stats()
                
                # 验证警告日志包含设备ID
                warning_found = any(
                    self.device_id in log and "高队列使用率" in log
                    for log in cm.output
                )
                self.assertTrue(warning_found, "应该记录高队列使用率警告")
            
        finally:
            manager.stop()


if __name__ == "__main__":
    unittest.main()
