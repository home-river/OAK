"""测试显示模块的按键切换功能

测试任务 4：实现按键切换逻辑
- 子任务 4.1：修改 _run_main_loop() 的按键处理
- 子任务 4.2：实现 _switch_to_device() 方法
- 子任务 4.3：实现 _switch_to_combined() 方法
- 子任务 4.4：添加按键提示信息显示
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacket,
    RenderPacketPackager,
)


class TestDisplayKeySwitching(unittest.TestCase):
    """测试显示模块的按键切换功能"""
    
    def setUp(self):
        """测试前准备"""
        # 创建配置对象
        self.config = DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=30,
        )
        
        # 创建模拟的 RenderPacketPackager
        self.packager = MagicMock(spec=RenderPacketPackager)
        
        # 设备列表
        self.devices_list = ["device1", "device2"]
        
        # 创建 DisplayRenderer 实例
        self.renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
        )
    
    def _create_test_packet(
        self,
        device_id: str = "device1",
        device_alias: str = "camera1"
    ) -> RenderPacket:
        """创建测试用的渲染包"""
        # 创建视频帧
        rgb_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        video_frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=rgb_frame,
        )
        
        # 创建处理后的检测数据（空检测）
        processed_data = DeviceProcessedDataDTO(
            device_id=device_id,
            frame_id=1,
            device_alias=device_alias,
            coords=np.empty((0, 3), dtype=np.float32),
            bbox=np.empty((0, 4), dtype=np.float32),
            confidence=np.empty((0,), dtype=np.float32),
            labels=np.empty((0,), dtype=np.int32),
            state_label=[],
        )
        
        return RenderPacket(
            video_frame=video_frame,
            processed_detections=processed_data,
        )
    
    def test_switch_to_device_method(self):
        """测试子任务 4.2：_switch_to_device() 方法
        
        验证：
        - 切换到指定设备的单设备显示
        - 更新显示模式为 "single"
        - 更新选中的设备索引
        """
        # 初始状态应该是 Combined 模式
        self.assertEqual(self.renderer._display_mode, "combined")
        
        # 切换到设备 0
        self.renderer._switch_to_device(0)
        
        # 验证显示模式已切换
        self.assertEqual(self.renderer._display_mode, "single")
        self.assertEqual(self.renderer._selected_device_index, 0)
        
        # 切换到设备 1
        self.renderer._switch_to_device(1)
        
        # 验证显示模式和索引已更新
        self.assertEqual(self.renderer._display_mode, "single")
        self.assertEqual(self.renderer._selected_device_index, 1)
    
    def test_switch_to_device_invalid_index(self):
        """测试切换到无效的设备索引
        
        验证：
        - 当设备索引超出范围时，不改变显示模式
        """
        # 初始状态
        initial_mode = self.renderer._display_mode
        initial_index = self.renderer._selected_device_index
        
        # 尝试切换到无效索引
        self.renderer._switch_to_device(999)
        
        # 验证显示模式未改变
        self.assertEqual(self.renderer._display_mode, initial_mode)
        self.assertEqual(self.renderer._selected_device_index, initial_index)
    
    def test_switch_to_combined_method(self):
        """测试子任务 4.3：_switch_to_combined() 方法
        
        验证：
        - 切换到 Combined 模式
        - 更新显示模式为 "combined"
        """
        # 先切换到单设备模式
        self.renderer._switch_to_device(0)
        self.assertEqual(self.renderer._display_mode, "single")
        
        # 切换到 Combined 模式
        self.renderer._switch_to_combined()
        
        # 验证显示模式已切换
        self.assertEqual(self.renderer._display_mode, "combined")
    
    def test_draw_key_hints_method(self):
        """测试子任务 4.4：_draw_key_hints() 方法
        
        验证：
        - 方法存在且可调用
        - 在帧上绘制按键提示信息
        """
        # 创建测试帧
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用方法（不应该抛出异常）
        try:
            self.renderer._draw_key_hints(frame)
        except Exception as e:
            self.fail(f"_draw_key_hints() 抛出异常: {e}")
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_draw_key_hints_with_device_aliases(self, mock_cv2):
        """测试按键提示信息包含设备别名
        
        验证：
        - 按键提示信息包含设备名称
        - 格式正确："1:Device1 2:Device2 3:Combined F:Fullscreen Q:Quit"
        """
        # 模拟 cv2.getTextSize 返回值
        mock_cv2.getTextSize.return_value = ((100, 20), 5)
        
        # 创建测试帧
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 模拟 packager 的缓存数据
        packet1 = self._create_test_packet("device1", "left_camera")
        packet2 = self._create_test_packet("device2", "right_camera")
        
        self.packager._latest_packets = {
            "device1": packet1,
            "device2": packet2,
        }
        
        # 调用方法
        self.renderer._draw_key_hints(frame)
        
        # 验证 cv2.putText 被调用
        self.assertTrue(mock_cv2.putText.called)
        
        # 获取绘制的文本
        call_args = mock_cv2.putText.call_args
        if call_args:
            text = call_args[0][1]  # 第二个参数是文本
            
            # 验证文本包含关键信息
            self.assertIn("1:", text)
            self.assertIn("2:", text)
            self.assertIn("3:Combined", text)
            self.assertIn("F:Fullscreen", text)
            self.assertIn("Q:Quit", text)
    
    def test_render_single_device_includes_key_hints(self):
        """测试单设备渲染包含按键提示
        
        验证：
        - _render_single_device() 调用 _draw_key_hints()
        """
        # 创建测试数据包
        packet = self._create_test_packet()
        
        # 使用 patch 监控 _draw_key_hints 调用
        with patch.object(self.renderer, '_draw_key_hints') as mock_draw_hints:
            # 调用渲染方法
            frame = self.renderer._render_single_device(packet)
            
            # 验证 _draw_key_hints 被调用
            self.assertTrue(mock_draw_hints.called)
            self.assertIsNotNone(frame)
    
    def test_render_combined_devices_includes_key_hints(self):
        """测试 Combined 模式渲染包含按键提示
        
        验证：
        - _render_combined_devices() 调用 _draw_key_hints()
        """
        # 创建测试数据包
        packets = {
            "device1": self._create_test_packet("device1", "camera1"),
            "device2": self._create_test_packet("device2", "camera2"),
        }
        
        # 使用 patch 监控 _draw_key_hints 调用
        with patch.object(self.renderer, '_draw_key_hints') as mock_draw_hints:
            # 调用渲染方法
            frame = self.renderer._render_combined_devices(packets)
            
            # 验证 _draw_key_hints 被调用
            self.assertTrue(mock_draw_hints.called)
            self.assertIsNotNone(frame)


if __name__ == '__main__':
    unittest.main()
