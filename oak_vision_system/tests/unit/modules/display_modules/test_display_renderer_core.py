"""
测试 DisplayRenderer 核心功能

验证需求：
- 1.1: initialize() 初始化渲染器
- 1.5: cleanup() 清理渲染器资源
- 6.1: render_once() 执行一次渲染循环
- 6.2: render_once() 正常渲染返回 False
- 6.3: render_once() 按 'q' 键返回 True
- 13.1: get_stats() 返回统计信息
- 13.2: get_stats() 计算 FPS 指标
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import time
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO, DeviceRole
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacket,
    RenderPacketPackager,
)
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO


class TestDisplayRendererLifecycle(unittest.TestCase):
    """测试 DisplayRenderer 生命周期方法"""
    
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
    
    def test_initialize_sets_start_time(self):
        """测试 initialize() 设置统计信息（需求 1.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 调用 initialize()
        renderer.initialize()
        
        # 验证设置了 start_time
        self.assertGreater(renderer._stats["start_time"], 0)
        
        # 验证 _window_created 为 False
        self.assertFalse(renderer._window_created)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.destroyAllWindows')
    def test_cleanup_closes_windows(self, mock_destroy):
        """测试 cleanup() 关闭窗口（需求 1.5）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化并设置统计信息
        renderer.initialize()
        renderer._stats["frames_rendered"] = 100
        
        # 调用 cleanup()
        with self.assertLogs(level='INFO') as log_context:
            renderer.cleanup()
        
        # 验证调用了 cv2.destroyAllWindows()
        mock_destroy.assert_called_once()
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn('DisplayRenderer 已清理', log_output)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.destroyAllWindows')
    def test_cleanup_outputs_stats(self, mock_destroy):
        """测试 cleanup() 输出统计信息（需求 1.5）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化并设置统计信息
        renderer.initialize()
        renderer._stats["frames_rendered"] = 150
        time.sleep(0.1)  # 等待一小段时间以产生运行时长
        
        # 调用 cleanup()
        with self.assertLogs(level='INFO') as log_context:
            renderer.cleanup()
        
        # 验证日志包含帧数、时长、平均FPS
        log_output = '\n'.join(log_context.output)
        self.assertIn('帧数: 150', log_output)
        self.assertIn('时长:', log_output)
        self.assertIn('平均FPS:', log_output)


class TestDisplayRendererStats(unittest.TestCase):
    """测试 DisplayRenderer 统计信息"""
    
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
    
    def test_get_stats_returns_correct_format(self):
        """测试 get_stats() 返回正确格式（需求 13.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 获取统计信息
        stats = renderer.get_stats()
        
        # 验证返回字典包含所有必需字段
        self.assertIn('frames_rendered', stats)
        self.assertIn('fps', stats)
        self.assertIn('fps_history', stats)
        self.assertIn('avg_fps', stats)
        self.assertIn('min_fps', stats)
        self.assertIn('max_fps', stats)
        self.assertIn('runtime_sec', stats)
        
        # 验证字段类型
        self.assertIsInstance(stats['frames_rendered'], int)
        self.assertIsInstance(stats['fps'], float)
        self.assertIsInstance(stats['fps_history'], list)
        self.assertIsInstance(stats['avg_fps'], float)
        self.assertIsInstance(stats['min_fps'], float)
        self.assertIsInstance(stats['max_fps'], float)
        self.assertIsInstance(stats['runtime_sec'], float)
    
    def test_get_stats_calculates_fps_metrics(self):
        """测试 get_stats() 计算 FPS 指标（需求 13.2）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 设置 FPS 历史记录
        renderer._stats["fps_history"] = [25.0, 30.0, 28.0, 32.0, 29.0]
        
        # 获取统计信息
        stats = renderer.get_stats()
        
        # 验证 FPS 指标计算正确
        self.assertEqual(stats['avg_fps'], 28.8)  # (25+30+28+32+29)/5
        self.assertEqual(stats['min_fps'], 25.0)
        self.assertEqual(stats['max_fps'], 32.0)
        self.assertEqual(len(stats['fps_history']), 5)
    
    def test_get_stats_calculates_runtime(self):
        """测试 get_stats() 计算运行时长（需求 13.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 等待一小段时间
        time.sleep(0.1)
        
        # 获取统计信息
        stats = renderer.get_stats()
        
        # 验证运行时长大于 0
        self.assertGreater(stats['runtime_sec'], 0)
        self.assertLess(stats['runtime_sec'], 1.0)  # 应该小于 1 秒


class TestDisplayRendererRenderOnce(unittest.TestCase):
    """测试 DisplayRenderer.render_once() 方法"""
    
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
        
        # 创建空的检测数据（0个检测结果）
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
    def test_render_once_returns_false_on_normal_render(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试正常渲染时 render_once() 返回 False（需求 6.2）"""
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
        mock_wait_key.return_value = ord('a')  # 非 'q' 键
        
        # 调用 render_once()
        result = renderer.render_once()
        
        # 验证返回 False
        self.assertFalse(result)
        
        # 验证调用了相关方法
        self.mock_packager.get_packets.assert_called_once()
        mock_imshow.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_render_once_returns_true_on_q_key(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试按 'q' 键时 render_once() 返回 True（需求 6.3）"""
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
        
        # 验证返回 True
        self.assertTrue(result)
        
        # 验证记录了日志
        log_output = '\n'.join(log_context.output)
        self.assertIn("用户按下 'q' 键", log_output)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    def test_render_once_handles_no_data(self, mock_wait_key):
        """测试无数据时 render_once() 的处理（需求 6.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # Mock 返回空数据
        self.mock_packager.get_packets.return_value = {}
        mock_wait_key.return_value = ord('a')  # 非 'q' 键
        
        # 调用 render_once()
        result = renderer.render_once()
        
        # 验证返回 False
        self.assertFalse(result)
        
        # 验证调用了 waitKey（用于处理按键）
        mock_wait_key.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_render_once_creates_window_on_first_call(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试首次调用时创建窗口（需求 6.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 验证窗口未创建
        self.assertFalse(renderer._window_created)
        
        # Mock 依赖
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        self.mock_packager.get_packets.return_value = packets
        mock_wait_key.return_value = ord('a')
        
        # 调用 render_once()
        renderer.render_once()
        
        # 验证窗口已创建
        self.assertTrue(renderer._window_created)
        mock_named_window.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.waitKey')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.imshow')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.namedWindow')
    def test_render_once_updates_stats(self, mock_named_window, mock_imshow, mock_wait_key):
        """测试 render_once() 更新统计信息（需求 13.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 初始化
        renderer.initialize()
        
        # 记录初始帧数
        initial_frames = renderer._stats["frames_rendered"]
        
        # Mock 依赖
        packets = {
            "device_001": self._create_test_packet("device_001"),
            "device_002": self._create_test_packet("device_002"),
        }
        self.mock_packager.get_packets.return_value = packets
        mock_wait_key.return_value = ord('a')
        
        # 调用 render_once()
        renderer.render_once()
        
        # 验证帧数增加 1
        self.assertEqual(renderer._stats["frames_rendered"], initial_frames + 1)


if __name__ == '__main__':
    unittest.main()
