"""
测试 DisplayRenderer 交互功能

验证需求：
- 5.4: 'q' 键触发退出
- 5.5: 'f' 键切换全屏
- 5.7: '1'/'2'/'3' 键切换显示模式
- 8.1: _switch_to_device() 检查 role_bindings
- 8.2: _switch_to_device() 缺失角色时警告
- 8.3: _switch_to_combined() 切换到拼接模式
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
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO


class TestDisplayRendererKeyHandling(unittest.TestCase):
    """测试 DisplayRenderer 按键处理"""
    
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
    def test_key_q_triggers_exit(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试 'q' 键触发退出（需求 5.4）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # Mock 依赖
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        self.mock_packager.get_packets.return_value = packets
        mock_wait_key.return_value = ord('q')  # 'q' 键
        
        # 调用 render_once()
        with self.assertLogs(level='INFO') as log_context:
            result = renderer.render_once()
        
        # 验证返回 True（触发退出）
        self.assertTrue(result)
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("用户按下 'q' 键", log_output)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.setWindowProperty')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_key_f_toggles_fullscreen(self, mock_named_window, mock_imshow, mock_wait_key, mock_set_window_property):
        """测试 'f' 键切换全屏（需求 5.5）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # Mock 依赖
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        self.mock_packager.get_packets.return_value = packets
        mock_wait_key.return_value = ord('f')  # 'f' 键
        
        # 记录初始全屏状态
        initial_fullscreen = renderer._is_fullscreen
        
        # 调用 render_once()
        with self.assertLogs(level='INFO'):
            result = renderer.render_once()
        
        # 验证返回 False（继续运行）
        self.assertFalse(result)
        
        # 验证全屏状态已切换
        self.assertNotEqual(renderer._is_fullscreen, initial_fullscreen)
        
        # 验证调用了 setWindowProperty
        mock_set_window_property.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_key_1_switches_to_left_camera(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试 '1' 键切换到左相机（需求 5.7）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # Mock 依赖
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        self.mock_packager.get_packets.return_value = packets
        mock_wait_key.return_value = ord('1')  # '1' 键
        
        # 调用 render_once()
        with self.assertLogs(level='INFO') as log_context:
            result = renderer.render_once()
        
        # 验证返回 False（继续运行）
        self.assertFalse(result)
        
        # 验证切换到单设备模式
        self.assertEqual(renderer._display_mode, "single")
        self.assertEqual(renderer._selected_device_role, DeviceRole.LEFT_CAMERA)
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("切换到设备角色", log_output)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_key_2_switches_to_right_camera(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试 '2' 键切换到右相机（需求 5.7）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # Mock 依赖
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        self.mock_packager.get_packets.return_value = packets
        mock_wait_key.return_value = ord('2')  # '2' 键
        
        # 调用 render_once()
        with self.assertLogs(level='INFO') as log_context:
            result = renderer.render_once()
        
        # 验证返回 False（继续运行）
        self.assertFalse(result)
        
        # 验证切换到单设备模式
        self.assertEqual(renderer._display_mode, "single")
        self.assertEqual(renderer._selected_device_role, DeviceRole.RIGHT_CAMERA)
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("切换到设备角色", log_output)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_key_3_switches_to_combined_mode(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试 '3' 键切换到拼接模式（需求 5.7）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 先切换到单设备模式
        renderer._display_mode = "single"
        renderer._selected_device_role = DeviceRole.LEFT_CAMERA
        
        # Mock 依赖（单设备模式需要 mock get_packet_by_mxid）
        packet = self._create_test_packet("device_001")
        self.mock_packager.get_packet_by_mxid.return_value = packet
        mock_wait_key.return_value = ord('3')  # '3' 键
        
        # 调用 render_once()
        with self.assertLogs(level='INFO') as log_context:
            result = renderer.render_once()
        
        # 验证返回 False（继续运行）
        self.assertFalse(result)
        
        # 验证切换到拼接模式
        self.assertEqual(renderer._display_mode, "combined")
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("切换到 Combined 模式", log_output)


class TestDisplayRendererDeviceSwitching(unittest.TestCase):
    """测试 DisplayRenderer 设备切换"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
        )
        self.devices_list = ["device_001", "device_002"]
        self.role_bindings = {
            DeviceRole.LEFT_CAMERA: "device_001",
            DeviceRole.RIGHT_CAMERA: "device_002",
        }
        
        # 创建 mock packager
        self.mock_packager = Mock(spec=RenderPacketPackager)
        self.mock_packager.event_bus = Mock()
    
    def test_switch_to_device_checks_role_bindings(self):
        """测试 _switch_to_device() 检查 role_bindings（需求 8.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 调用 _switch_to_device()
        with self.assertLogs(level='INFO') as log_context:
            renderer._switch_to_device(DeviceRole.LEFT_CAMERA)
        
        # 验证切换成功
        self.assertEqual(renderer._display_mode, "single")
        self.assertEqual(renderer._selected_device_role, DeviceRole.LEFT_CAMERA)
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("切换到设备角色", log_output)
        self.assertIn("device_001", log_output)
    
    def test_switch_to_device_warns_on_missing_role(self):
        """测试 _switch_to_device() 缺失角色时警告（需求 8.2）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings={},  # 空的 role_bindings
        )
        
        # 初始化
        renderer.initialize()
        
        # 记录初始显示模式
        initial_mode = renderer._display_mode
        
        # 调用 _switch_to_device()
        with self.assertLogs(level='WARNING') as log_context:
            renderer._switch_to_device(DeviceRole.LEFT_CAMERA)
        
        # 验证显示模式未改变
        self.assertEqual(renderer._display_mode, initial_mode)
        
        # 验证记录了警告日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("不存在于 role_bindings 中", log_output)
    
    def test_switch_to_combined_mode(self):
        """测试 _switch_to_combined() 切换到拼接模式（需求 8.3）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 先切换到单设备模式
        renderer._display_mode = "single"
        
        # 调用 _switch_to_combined()
        with self.assertLogs(level='INFO') as log_context:
            renderer._switch_to_combined()
        
        # 验证切换到拼接模式
        self.assertEqual(renderer._display_mode, "combined")
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("切换到 Combined 模式", log_output)


class TestDisplayRendererFullscreen(unittest.TestCase):
    """测试 DisplayRenderer 全屏切换"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
        )
        self.devices_list = ["device_001"]
        
        # 创建 mock packager
        self.mock_packager = Mock(spec=RenderPacketPackager)
        self.mock_packager.event_bus = Mock()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.setWindowProperty')
    def test_toggle_fullscreen_from_window_to_fullscreen(self, mock_set_window_property):
        """测试从窗口模式切换到全屏模式（需求 5.5）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建窗口
        renderer._window_created = True
        renderer._is_fullscreen = False
        
        # 调用 _toggle_fullscreen()
        with self.assertLogs(level='INFO') as log_context:
            renderer._toggle_fullscreen()
        
        # 验证切换到全屏
        self.assertTrue(renderer._is_fullscreen)
        
        # 验证调用了 setWindowProperty
        mock_set_window_property.assert_called_once()
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("切换到全屏模式", log_output)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.setWindowProperty')
    def test_toggle_fullscreen_from_fullscreen_to_window(self, mock_set_window_property):
        """测试从全屏模式切换到窗口模式（需求 5.5）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建窗口（全屏模式）
        renderer._window_created = True
        renderer._is_fullscreen = True
        
        # 调用 _toggle_fullscreen()
        with self.assertLogs(level='INFO') as log_context:
            renderer._toggle_fullscreen()
        
        # 验证切换到窗口模式
        self.assertFalse(renderer._is_fullscreen)
        
        # 验证调用了 setWindowProperty
        mock_set_window_property.assert_called_once()
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("切换到窗口模式", log_output)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.setWindowProperty')
    def test_toggle_fullscreen_does_nothing_if_window_not_created(self, mock_set_window_property):
        """测试窗口未创建时不切换全屏（需求 5.5）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 窗口未创建
        renderer._window_created = False
        initial_fullscreen = renderer._is_fullscreen
        
        # 调用 _toggle_fullscreen()
        renderer._toggle_fullscreen()
        
        # 验证全屏状态未改变
        self.assertEqual(renderer._is_fullscreen, initial_fullscreen)
        
        # 验证没有调用 setWindowProperty
        mock_set_window_property.assert_not_called()


if __name__ == '__main__':
    unittest.main()
