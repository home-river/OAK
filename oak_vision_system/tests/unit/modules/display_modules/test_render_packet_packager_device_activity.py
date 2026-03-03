"""
测试 RenderPacketPackager 设备活跃性检查功能

验证需求：
- is_device_active() 判断设备是否在指定时间窗口内有数据接收
- 支持自定义时间窗口大小
- 支持传入当前时间戳（用于测试）
"""

import unittest
import time
from unittest.mock import Mock

from oak_vision_system.modules.display_modules.render_packet_packager import RenderPacketPackager
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
import numpy as np


class TestRenderPacketPackagerDeviceActivity(unittest.TestCase):
    """测试 RenderPacketPackager 设备活跃性检查"""
    
    def setUp(self):
        """测试前准备"""
        self.devices_list = ["device_001", "device_002", "device_003"]
        self.packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0
        )
    
    def test_device_active_within_window(self):
        """测试设备在时间窗口内活跃"""
        device_id = "device_001"
        
        # 模拟接收视频帧（会更新 _device_last_seen_ts）
        frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        self.packager._handle_video_frame(frame)
        
        # 立即检查（应该活跃）
        is_active = self.packager.is_device_active(device_id, window_sec=1.0)
        self.assertTrue(is_active, "设备应该在时间窗口内活跃")
    
    def test_device_inactive_outside_window(self):
        """测试设备超出时间窗口后不活跃"""
        device_id = "device_001"
        
        # 模拟接收视频帧
        frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        self.packager._handle_video_frame(frame)
        
        # 使用未来时间戳检查（模拟时间流逝）
        future_time = time.time() + 2.0  # 2秒后
        is_active = self.packager.is_device_active(
            device_id, 
            window_sec=1.0,  # 1秒窗口
            now_ts=future_time
        )
        self.assertFalse(is_active, "设备应该在时间窗口外不活跃")
    
    def test_device_never_seen_is_inactive(self):
        """测试从未接收过数据的设备不活跃"""
        device_id = "device_999"  # 不在 devices_list 中
        
        is_active = self.packager.is_device_active(device_id, window_sec=1.0)
        self.assertFalse(is_active, "从未接收过数据的设备应该不活跃")
    
    def test_device_active_with_custom_window(self):
        """测试自定义时间窗口大小"""
        device_id = "device_002"
        
        # 模拟接收视频帧
        frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        self.packager._handle_video_frame(frame)
        
        # 使用较大的时间窗口（5秒）
        future_time = time.time() + 3.0  # 3秒后
        is_active = self.packager.is_device_active(
            device_id,
            window_sec=5.0,  # 5秒窗口
            now_ts=future_time
        )
        self.assertTrue(is_active, "设备应该在5秒窗口内活跃")
        
        # 使用较小的时间窗口（1秒）
        is_active_small_window = self.packager.is_device_active(
            device_id,
            window_sec=1.0,  # 1秒窗口
            now_ts=future_time
        )
        self.assertFalse(is_active_small_window, "设备应该在1秒窗口外不活跃")
    
    def test_device_activity_boundary_condition(self):
        """测试边界条件：刚好在时间窗口边缘"""
        device_id = "device_003"
        
        # 模拟接收视频帧
        frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        self.packager._handle_video_frame(frame)
        
        # 获取当前时间戳
        current_time = time.time()
        
        # 刚好在窗口边缘（0.999秒后）
        edge_time = current_time + 0.999
        is_active_edge = self.packager.is_device_active(
            device_id,
            window_sec=1.0,
            now_ts=edge_time
        )
        self.assertTrue(is_active_edge, "设备应该在窗口边缘内活跃")
        
        # 刚好超出窗口（1.001秒后）
        outside_time = current_time + 1.001
        is_active_outside = self.packager.is_device_active(
            device_id,
            window_sec=1.0,
            now_ts=outside_time
        )
        self.assertFalse(is_active_outside, "设备应该在窗口边缘外不活跃")
    
    def test_multiple_devices_activity(self):
        """测试多个设备的活跃性检查"""
        # 模拟多个设备接收数据
        for i, device_id in enumerate(self.devices_list):
            frame = VideoFrameDTO(
                device_id=device_id,
                frame_id=i + 1,
                rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
            )
            self.packager._handle_video_frame(frame)
            
            # 每个设备之间间隔0.5秒
            if i < len(self.devices_list) - 1:
                time.sleep(0.5)
        
        # 检查所有设备（应该都活跃，因为在2秒窗口内）
        for device_id in self.devices_list:
            is_active = self.packager.is_device_active(device_id, window_sec=2.0)
            self.assertTrue(is_active, f"设备 {device_id} 应该活跃")
    
    def test_device_activity_after_multiple_frames(self):
        """测试接收多帧后的活跃性（应该使用最新时间戳）"""
        device_id = "device_001"
        
        # 模拟接收第一帧
        frame1 = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        self.packager._handle_video_frame(frame1)
        
        # 等待0.5秒
        time.sleep(0.5)
        
        # 模拟接收第二帧
        frame2 = VideoFrameDTO(
            device_id=device_id,
            frame_id=2,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        self.packager._handle_video_frame(frame2)
        
        # 检查活跃性（应该基于最新帧的时间戳）
        is_active = self.packager.is_device_active(device_id, window_sec=1.0)
        self.assertTrue(is_active, "设备应该基于最新帧的时间戳判断活跃")
    
    def test_device_activity_default_now_timestamp(self):
        """测试默认使用当前时间戳"""
        device_id = "device_001"
        
        # 模拟接收视频帧
        frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        self.packager._handle_video_frame(frame)
        
        # 不传入 now_ts 参数（应该使用当前时间）
        is_active = self.packager.is_device_active(device_id, window_sec=1.0)
        self.assertTrue(is_active, "设备应该使用当前时间戳判断活跃")


if __name__ == '__main__':
    unittest.main()
