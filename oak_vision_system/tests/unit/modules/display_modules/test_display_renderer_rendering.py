"""
测试 DisplayRenderer 渲染逻辑

验证需求：
- 7.1: _render_single_device() 窗口模式 resize
- 7.2: _render_single_device() 全屏模式 resize
- 7.3: _render_single_device() 绘制检测框
- 7.4: _render_single_device() 绘制叠加层
- 7.5: _render_combined_devices() 计算 ROI 尺寸
- 7.6: _render_combined_devices() 每个设备 resize
- 7.7: _render_combined_devices() 水平拼接
- 7.8: _render_combined_devices() 带偏移的检测框
- 7.10: _render_combined_devices() 空数据处理
- 13.1: render_once() 状态驱动渲染
- 13.3: render_once() 惰性渲染
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO, DeviceRole
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacket,
    RenderPacketPackager,
)
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import (
    DeviceProcessedDataDTO,
    DetectionStatusLabel,
)


class TestDisplayRendererSingleDevice(unittest.TestCase):
    """测试 DisplayRenderer 单设备渲染"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
            window_width=640,
            window_height=480,
        )
        self.devices_list = ["device_001"]
        self.role_bindings = {
            DeviceRole.LEFT_CAMERA: "device_001",
        }
        
        # 创建 mock packager
        self.mock_packager = Mock(spec=RenderPacketPackager)
        self.mock_packager.event_bus = Mock()
    
    def _create_test_packet(self, device_id: str, num_detections: int = 0) -> RenderPacket:
        """创建测试用的 RenderPacket
        
        Args:
            device_id: 设备ID
            num_detections: 检测结果数量（默认为0）
        """
        video_frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        
        if num_detections > 0:
            # 创建有检测结果的数据
            labels = np.array([0] * num_detections, dtype=np.int32)
            bbox = np.array([[0.1, 0.1, 0.3, 0.3]] * num_detections, dtype=np.float32)
            coords = np.array([[100, 200, 300]] * num_detections, dtype=np.float32)
            confidence = np.array([0.9] * num_detections, dtype=np.float32)
            state_label = [DetectionStatusLabel.OBJECT_GRASPABLE] * num_detections
        else:
            # 创建空的检测数据
            labels = np.array([], dtype=np.int32)
            bbox = np.zeros((0, 4), dtype=np.float32)
            coords = np.zeros((0, 3), dtype=np.float32)
            confidence = np.array([], dtype=np.float32)
            state_label = []
        
        processed_data = DeviceProcessedDataDTO(
            device_id=device_id,
            frame_id=1,
            labels=labels,
            bbox=bbox,
            coords=coords,
            confidence=confidence,
            state_label=state_label,
            device_alias=f"Device_{device_id}",
        )
        
        return RenderPacket(
            video_frame=video_frame,
            processed_detections=processed_data,
        )
    
    def test_render_single_device_stretch_resize_window_mode(self):
        """测试窗口模式下 _render_single_device() 的 resize（需求 7.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化（窗口模式）
        renderer.initialize()
        renderer._is_fullscreen = False
        
        # 创建测试包
        packet = self._create_test_packet("device_001")
        
        # 调用 _render_single_device()
        result = renderer._render_single_device(packet)
        
        # 验证返回的帧尺寸为窗口尺寸
        self.assertIsNotNone(result)
        self.assertEqual(result.shape[1], renderer._window_width)  # 宽度
        self.assertEqual(result.shape[0], renderer._window_height)  # 高度
    
    def test_render_single_device_stretch_resize_fullscreen_mode(self):
        """测试全屏模式下 _render_single_device() 的 resize（需求 7.2）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化（全屏模式）
        renderer.initialize()
        renderer._is_fullscreen = True
        
        # 创建测试包
        packet = self._create_test_packet("device_001")
        
        # 调用 _render_single_device()
        result = renderer._render_single_device(packet)
        
        # 验证返回的帧尺寸为全屏尺寸
        self.assertIsNotNone(result)
        self.assertEqual(result.shape[1], renderer._fullscreen_width)  # 宽度
        self.assertEqual(result.shape[0], renderer._fullscreen_height)  # 高度
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_render_single_device_draws_detection_boxes(self, mock_rectangle):
        """测试 _render_single_device() 绘制检测框（需求 7.3）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建带检测结果的测试包
        packet = self._create_test_packet("device_001", num_detections=2)
        
        # 调用 _render_single_device()
        result = renderer._render_single_device(packet)
        
        # 验证调用了 cv2.rectangle（绘制检测框）
        self.assertIsNotNone(result)
        self.assertGreater(mock_rectangle.call_count, 0)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer._draw_fps')
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer._draw_key_hints')
    def test_render_single_device_draws_overlays(self, mock_draw_key_hints, mock_draw_fps):
        """测试 _render_single_device() 绘制叠加层（需求 7.4）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试包
        packet = self._create_test_packet("device_001")
        
        # 调用 _render_single_device()
        result = renderer._render_single_device(packet)
        
        # 验证调用了叠加层绘制方法
        self.assertIsNotNone(result)
        mock_draw_fps.assert_called_once()
        mock_draw_key_hints.assert_called_once()


class TestDisplayRendererCombinedDevices(unittest.TestCase):
    """测试 DisplayRenderer 合并设备渲染"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
            window_width=640,
            window_height=480,
        )
        self.devices_list = ["device_001", "device_002"]
        self.role_bindings = {
            DeviceRole.LEFT_CAMERA: "device_001",
            DeviceRole.RIGHT_CAMERA: "device_002",
        }
        
        # 创建 mock packager
        self.mock_packager = Mock(spec=RenderPacketPackager)
        self.mock_packager.event_bus = Mock()
    
    def _create_test_packet(self, device_id: str, num_detections: int = 0) -> RenderPacket:
        """创建测试用的 RenderPacket"""
        video_frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        
        if num_detections > 0:
            labels = np.array([0] * num_detections, dtype=np.int32)
            bbox = np.array([[0.1, 0.1, 0.3, 0.3]] * num_detections, dtype=np.float32)
            coords = np.array([[100, 200, 300]] * num_detections, dtype=np.float32)
            confidence = np.array([0.9] * num_detections, dtype=np.float32)
            state_label = [DetectionStatusLabel.OBJECT_GRASPABLE] * num_detections
        else:
            labels = np.array([], dtype=np.int32)
            bbox = np.zeros((0, 4), dtype=np.float32)
            coords = np.zeros((0, 3), dtype=np.float32)
            confidence = np.array([], dtype=np.float32)
            state_label = []
        
        processed_data = DeviceProcessedDataDTO(
            device_id=device_id,
            frame_id=1,
            labels=labels,
            bbox=bbox,
            coords=coords,
            confidence=confidence,
            state_label=state_label,
            device_alias=f"Device_{device_id}",
        )
        
        return RenderPacket(
            video_frame=video_frame,
            processed_detections=processed_data,
        )
    
    def test_render_combined_devices_calculates_roi_sizes(self):
        """测试 _render_combined_devices() 计算 ROI 尺寸（需求 7.5）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化（窗口模式）
        renderer.initialize()
        renderer._is_fullscreen = False
        
        # 创建测试包
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        
        # 调用 _render_combined_devices()
        result = renderer._render_combined_devices(packets)
        
        # 验证返回的帧尺寸为窗口尺寸
        self.assertIsNotNone(result)
        self.assertEqual(result.shape[1], renderer._window_width)  # 总宽度
        self.assertEqual(result.shape[0], renderer._window_height)  # 高度
    
    def test_render_combined_devices_stretch_resize_each_device(self):
        """测试 _render_combined_devices() 对每个设备进行 resize（需求 7.6）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试包
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        
        # 调用 _render_combined_devices()
        result = renderer._render_combined_devices(packets)
        
        # 验证返回的帧不为空
        self.assertIsNotNone(result)
        # 验证帧的形状正确（3通道彩色图像）
        self.assertEqual(len(result.shape), 3)
        self.assertEqual(result.shape[2], 3)
    
    def test_render_combined_devices_horizontal_concat(self):
        """测试 _render_combined_devices() 水平拼接（需求 7.7）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试包（使用不同的帧数据以便区分）
        video_frame_1 = VideoFrameDTO(
            device_id="device_001",
            frame_id=1,
            rgb_frame=np.ones((480, 640, 3), dtype=np.uint8) * 100,  # 灰色
        )
        video_frame_2 = VideoFrameDTO(
            device_id="device_002",
            frame_id=1,
            rgb_frame=np.ones((480, 640, 3), dtype=np.uint8) * 200,  # 更亮的灰色
        )
        
        processed_data_1 = DeviceProcessedDataDTO(
            device_id="device_001",
            frame_id=1,
            labels=np.array([], dtype=np.int32),
            bbox=np.zeros((0, 4), dtype=np.float32),
            coords=np.zeros((0, 3), dtype=np.float32),
            confidence=np.array([], dtype=np.float32),
            state_label=[],
            device_alias="Device_001",
        )
        
        processed_data_2 = DeviceProcessedDataDTO(
            device_id="device_002",
            frame_id=1,
            labels=np.array([], dtype=np.int32),
            bbox=np.zeros((0, 4), dtype=np.float32),
            coords=np.zeros((0, 3), dtype=np.float32),
            confidence=np.array([], dtype=np.float32),
            state_label=[],
            device_alias="Device_002",
        )
        
        packets = {
            "device_001": RenderPacket(video_frame=video_frame_1, processed_detections=processed_data_1),
            "device_002": RenderPacket(video_frame=video_frame_2, processed_detections=processed_data_2),
        }
        
        # 调用 _render_combined_devices()
        result = renderer._render_combined_devices(packets)
        
        # 验证拼接后的帧宽度等于窗口宽度
        self.assertIsNotNone(result)
        self.assertEqual(result.shape[1], renderer._window_width)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_render_combined_devices_draws_detection_boxes_with_offset(self, mock_rectangle):
        """测试 _render_combined_devices() 绘制带偏移的检测框（需求 7.8）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建带检测结果的测试包
        packets = {
            "device_001": self._create_test_packet("device_001", num_detections=1),
            "device_002": self._create_test_packet("device_002", num_detections=1),
        }
        
        # 调用 _render_combined_devices()
        result = renderer._render_combined_devices(packets)
        
        # 验证调用了 cv2.rectangle（绘制检测框）
        self.assertIsNotNone(result)
        # 应该为每个设备的每个检测结果调用一次 rectangle
        self.assertGreaterEqual(mock_rectangle.call_count, 2)
    
    def test_render_combined_devices_returns_none_on_empty_packets(self):
        """测试 _render_combined_devices() 空数据处理（需求 7.10）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 传入空的 packets
        packets = {}
        
        # 调用 _render_combined_devices()
        result = renderer._render_combined_devices(packets)
        
        # 验证返回 None
        self.assertIsNone(result)


class TestDisplayRendererStateDriven(unittest.TestCase):
    """测试 DisplayRenderer 状态驱动渲染"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
            window_width=640,
            window_height=480,
        )
        self.devices_list = ["device_001", "device_002"]
        self.role_bindings = {
            DeviceRole.LEFT_CAMERA: "device_001",
            DeviceRole.RIGHT_CAMERA: "device_002",
        }
        
        # 创建 mock packager
        self.mock_packager = Mock(spec=RenderPacketPackager)
        self.mock_packager.event_bus = Mock()
    
    def _create_test_packet(self, device_id: str) -> RenderPacket:
        """创建测试用的 RenderPacket"""
        video_frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        
        processed_data = DeviceProcessedDataDTO(
            device_id=device_id,
            frame_id=1,
            labels=np.array([], dtype=np.int32),
            bbox=np.zeros((0, 4), dtype=np.float32),
            coords=np.zeros((0, 3), dtype=np.float32),
            confidence=np.array([], dtype=np.float32),
            state_label=[],
            device_alias=f"Device_{device_id}",
        )
        
        return RenderPacket(
            video_frame=video_frame,
            processed_detections=processed_data,
        )
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_render_once_combined_mode_calls_get_packets(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试拼接模式下 render_once() 调用 get_packets（需求 13.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 设置为拼接模式
        renderer._display_mode = "combined"
        
        # Mock 依赖
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        self.mock_packager.get_packets.return_value = packets
        mock_wait_key.return_value = ord('a')
        
        # 调用 render_once()
        renderer.render_once()
        
        # 验证调用了 get_packets
        self.mock_packager.get_packets.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_render_once_single_mode_calls_get_packet_by_mxid(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试单设备模式下 render_once() 调用 get_packet_by_mxid（需求 13.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 设置为单设备模式
        renderer._display_mode = "single"
        renderer._selected_device_role = DeviceRole.LEFT_CAMERA
        
        # Mock 依赖
        packet = self._create_test_packet("device_001")
        self.mock_packager.get_packet_by_mxid.return_value = packet
        mock_wait_key.return_value = ord('a')
        
        # 调用 render_once()
        renderer.render_once()
        
        # 验证调用了 get_packet_by_mxid
        self.mock_packager.get_packet_by_mxid.assert_called_once_with("device_001", timeout=0.01)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    def test_render_once_single_mode_lazy_rendering(self, mock_wait_key):
        """测试单设备模式下的惰性渲染（需求 13.3）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 设置为单设备模式
        renderer._display_mode = "single"
        renderer._selected_device_role = DeviceRole.LEFT_CAMERA
        
        # Mock 返回 None（无数据）
        self.mock_packager.get_packet_by_mxid.return_value = None
        mock_wait_key.return_value = ord('a')
        
        # 调用 render_once()
        result = renderer.render_once()
        
        # 验证返回 False（继续运行）
        self.assertFalse(result)
        
        # 验证调用了 get_packet_by_mxid（惰性渲染：只获取当前设备的数据）
        self.mock_packager.get_packet_by_mxid.assert_called_once()
        
        # 验证没有调用 get_packets（不获取所有设备的数据）
        self.mock_packager.get_packets.assert_not_called()


if __name__ == '__main__':
    unittest.main()
