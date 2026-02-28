"""
测试 DisplayRenderer 绘制功能

验证需求：
- 7.10: _draw_detection_boxes_normalized() 坐标映射
- 12.1: _draw_detection_boxes_normalized() 偏移应用
- 12.2: _draw_detection_boxes_normalized() 状态颜色
- 12.3: _draw_detection_boxes_normalized() 默认颜色
- 12.4: _draw_detection_boxes_normalized() 绘制标签
- 12.5: _draw_detection_boxes_normalized() 绘制置信度
- 12.7: _draw_detection_boxes_normalized() 绘制坐标
- 12.8: _draw_detection_boxes_normalized() 空检测处理
- 13.2: _draw_fps() 显示当前 FPS
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO, DeviceRole
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import RenderPacketPackager
from oak_vision_system.core.dto.data_processing_dto import (
    DeviceProcessedDataDTO,
    DetectionStatusLabel,
)
from oak_vision_system.modules.display_modules.render_config import (
    STATUS_COLOR_MAP,
    DEFAULT_DETECTION_COLOR,
)


class TestDisplayRendererDetectionBoxes(unittest.TestCase):
    """测试 DisplayRenderer 检测框绘制"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
            show_labels=True,
            show_confidence=True,
            show_coordinates=True,
            bbox_color_by_label=True,
        )
        self.devices_list = ["device_001"]
        
        # 创建 mock packager
        self.mock_packager = Mock(spec=RenderPacketPackager)
        self.mock_packager.event_bus = Mock()
    
    def _create_test_processed_data(
        self, 
        device_id: str, 
        num_detections: int = 1,
        status_label: DetectionStatusLabel = DetectionStatusLabel.OBJECT_GRASPABLE
    ) -> DeviceProcessedDataDTO:
        """创建测试用的 DeviceProcessedDataDTO"""
        if num_detections > 0:
            labels = np.array([0] * num_detections, dtype=np.int32)
            bbox = np.array([[0.1, 0.1, 0.3, 0.3]] * num_detections, dtype=np.float32)
            coords = np.array([[100, 200, 300]] * num_detections, dtype=np.float32)
            confidence = np.array([0.9] * num_detections, dtype=np.float32)
            state_labels = [status_label] * num_detections
        else:
            labels = np.array([], dtype=np.int32)
            bbox = np.zeros((0, 4), dtype=np.float32)
            coords = np.zeros((0, 3), dtype=np.float32)
            confidence = np.array([], dtype=np.float32)
            state_labels = []
        
        return DeviceProcessedDataDTO(
            device_id=device_id,
            frame_id=1,
            labels=labels,
            bbox=bbox,
            coords=coords,
            confidence=confidence,
            state_label=state_labels,
            device_alias=f"Device_{device_id}",
        )
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_draw_detection_boxes_normalized_maps_coordinates(self, mock_rectangle):
        """测试 _draw_detection_boxes_normalized() 坐标映射（需求 7.10）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试数据
        processed_data = self._create_test_processed_data("device_001", num_detections=1)
        
        # 创建测试画布
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_detection_boxes_normalized()
        renderer._draw_detection_boxes_normalized(
            canvas, processed_data,
            roiW=640, roiH=480, offsetX=0
        )
        
        # 验证调用了 cv2.rectangle
        self.assertGreater(mock_rectangle.call_count, 0)
        
        # 验证坐标映射正确（归一化坐标 0.1, 0.1, 0.3, 0.3 映射到 640x480）
        # 预期：(64, 48) 到 (192, 144)
        call_args = mock_rectangle.call_args_list[0]
        canvas_arg, pt1, pt2, color, thickness = call_args[0]
        
        # 验证坐标（允许一定误差）
        self.assertAlmostEqual(pt1[0], 64, delta=5)  # xmin
        self.assertAlmostEqual(pt1[1], 48, delta=5)  # ymin
        self.assertAlmostEqual(pt2[0], 192, delta=5)  # xmax
        self.assertAlmostEqual(pt2[1], 144, delta=5)  # ymax
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_draw_detection_boxes_normalized_applies_offset(self, mock_rectangle):
        """测试 _draw_detection_boxes_normalized() 偏移应用（需求 12.1）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试数据
        processed_data = self._create_test_processed_data("device_001", num_detections=1)
        
        # 创建测试画布
        canvas = np.zeros((480, 1280, 3), dtype=np.uint8)
        
        # 调用 _draw_detection_boxes_normalized()（带偏移）
        offsetX = 640
        renderer._draw_detection_boxes_normalized(
            canvas, processed_data,
            roiW=640, roiH=480, offsetX=offsetX
        )
        
        # 验证调用了 cv2.rectangle
        self.assertGreater(mock_rectangle.call_count, 0)
        
        # 验证偏移应用正确
        call_args = mock_rectangle.call_args_list[0]
        canvas_arg, pt1, pt2, color, thickness = call_args[0]
        
        # 验证 x 坐标包含偏移
        self.assertGreater(pt1[0], offsetX)  # xmin 应该大于 offsetX
        self.assertGreater(pt2[0], offsetX)  # xmax 应该大于 offsetX
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_draw_detection_boxes_normalized_uses_status_color(self, mock_rectangle):
        """测试 _draw_detection_boxes_normalized() 使用状态颜色（需求 12.2）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试数据（使用 OBJECT_GRASPABLE 状态）
        processed_data = self._create_test_processed_data(
            "device_001", 
            num_detections=1,
            status_label=DetectionStatusLabel.OBJECT_GRASPABLE
        )
        
        # 创建测试画布
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_detection_boxes_normalized()
        renderer._draw_detection_boxes_normalized(
            canvas, processed_data,
            roiW=640, roiH=480, offsetX=0
        )
        
        # 验证调用了 cv2.rectangle
        self.assertGreater(mock_rectangle.call_count, 0)
        
        # 验证使用了正确的颜色
        call_args = mock_rectangle.call_args_list[0]
        canvas_arg, pt1, pt2, color, thickness = call_args[0]
        
        expected_color = STATUS_COLOR_MAP[DetectionStatusLabel.OBJECT_GRASPABLE]
        self.assertEqual(color, expected_color)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_draw_detection_boxes_normalized_uses_default_color_for_unknown_status(self, mock_rectangle):
        """测试 _draw_detection_boxes_normalized() 对未知状态使用默认颜色（需求 12.3）"""
        # 创建禁用按标签着色的配置
        config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
            show_labels=True,
            show_confidence=True,
            show_coordinates=True,
            bbox_color_by_label=False,  # 禁用按标签着色
        )
        
        renderer = DisplayRenderer(
            config=config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试数据
        processed_data = self._create_test_processed_data("device_001", num_detections=1)
        
        # 创建测试画布
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_detection_boxes_normalized()
        renderer._draw_detection_boxes_normalized(
            canvas, processed_data,
            roiW=640, roiH=480, offsetX=0
        )
        
        # 验证调用了 cv2.rectangle
        self.assertGreater(mock_rectangle.call_count, 0)
        
        # 验证使用了默认颜色
        call_args = mock_rectangle.call_args_list[0]
        canvas_arg, pt1, pt2, color, thickness = call_args[0]
        
        self.assertEqual(color, DEFAULT_DETECTION_COLOR)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.putText')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_draw_detection_boxes_normalized_draws_labels(self, mock_rectangle, mock_put_text):
        """测试 _draw_detection_boxes_normalized() 绘制标签（需求 12.4）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试数据
        processed_data = self._create_test_processed_data("device_001", num_detections=1)
        
        # 创建测试画布
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_detection_boxes_normalized()
        renderer._draw_detection_boxes_normalized(
            canvas, processed_data,
            roiW=640, roiH=480, offsetX=0
        )
        
        # 验证调用了 cv2.putText（绘制标签文字）
        self.assertGreater(mock_put_text.call_count, 0)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.putText')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_draw_detection_boxes_normalized_draws_confidence(self, mock_rectangle, mock_put_text):
        """测试 _draw_detection_boxes_normalized() 绘制置信度（需求 12.5）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试数据（置信度 0.9）
        processed_data = self._create_test_processed_data("device_001", num_detections=1)
        
        # 创建测试画布
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_detection_boxes_normalized()
        renderer._draw_detection_boxes_normalized(
            canvas, processed_data,
            roiW=640, roiH=480, offsetX=0
        )
        
        # 验证调用了 cv2.putText
        self.assertGreater(mock_put_text.call_count, 0)
        
        # 验证标签文本包含置信度（90%）
        call_args = mock_put_text.call_args_list[0]
        canvas_arg, text, position, font, font_scale, color, thickness = call_args[0]
        
        self.assertIn("90%", text)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer._draw_text_with_background')
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_draw_detection_boxes_normalized_draws_coordinates(self, mock_rectangle, mock_draw_text):
        """测试 _draw_detection_boxes_normalized() 绘制坐标（需求 12.7）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试数据（坐标 100, 200, 300）
        processed_data = self._create_test_processed_data("device_001", num_detections=1)
        
        # 创建测试画布
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_detection_boxes_normalized()
        renderer._draw_detection_boxes_normalized(
            canvas, processed_data,
            roiW=640, roiH=480, offsetX=0
        )
        
        # 验证调用了 _draw_text_with_background（绘制坐标）
        self.assertGreater(mock_draw_text.call_count, 0)
        
        # 验证坐标文本
        call_args = mock_draw_text.call_args_list[-1]  # 最后一次调用应该是坐标
        canvas_arg, text = call_args[0][:2]
        
        self.assertIn("100", text)
        self.assertIn("200", text)
        self.assertIn("300", text)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.rectangle')
    def test_draw_detection_boxes_normalized_handles_empty_detections(self, mock_rectangle):
        """测试 _draw_detection_boxes_normalized() 空检测处理（需求 12.8）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建空检测数据
        processed_data = self._create_test_processed_data("device_001", num_detections=0)
        
        # 创建测试画布
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_detection_boxes_normalized()
        renderer._draw_detection_boxes_normalized(
            canvas, processed_data,
            roiW=640, roiH=480, offsetX=0
        )
        
        # 验证没有调用 cv2.rectangle（因为没有检测结果）
        mock_rectangle.assert_not_called()


class TestDisplayRendererColorMapping(unittest.TestCase):
    """测试 DisplayRenderer 颜色映射"""
    
    def test_color_map_imports_from_render_config(self):
        """测试从 render_config 导入颜色映射（需求 12.2）"""
        # 验证 STATUS_COLOR_MAP 已导入
        from oak_vision_system.modules.display_modules.render_config import STATUS_COLOR_MAP
        
        self.assertIsNotNone(STATUS_COLOR_MAP)
        self.assertIsInstance(STATUS_COLOR_MAP, dict)
    
    def test_color_map_contains_all_status_labels(self):
        """测试颜色映射包含所有状态标签（需求 12.2）"""
        from oak_vision_system.modules.display_modules.render_config import STATUS_COLOR_MAP
        
        # 验证包含所有物体状态
        self.assertIn(DetectionStatusLabel.OBJECT_GRASPABLE, STATUS_COLOR_MAP)
        self.assertIn(DetectionStatusLabel.OBJECT_DANGEROUS, STATUS_COLOR_MAP)
        self.assertIn(DetectionStatusLabel.OBJECT_OUT_OF_RANGE, STATUS_COLOR_MAP)
        self.assertIn(DetectionStatusLabel.OBJECT_PENDING_GRASP, STATUS_COLOR_MAP)
        
        # 验证包含所有人类状态
        self.assertIn(DetectionStatusLabel.HUMAN_SAFE, STATUS_COLOR_MAP)
        self.assertIn(DetectionStatusLabel.HUMAN_DANGEROUS, STATUS_COLOR_MAP)


class TestDisplayRendererOverlays(unittest.TestCase):
    """测试 DisplayRenderer 叠加层绘制"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
            show_fps=True,
            show_device_info=True,
        )
        self.devices_list = ["device_001"]
        
        # 创建 mock packager
        self.mock_packager = Mock(spec=RenderPacketPackager)
        self.mock_packager.event_bus = Mock()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer._draw_text_with_background')
    def test_draw_fps_displays_current_fps(self, mock_draw_text):
        """测试 _draw_fps() 显示当前 FPS（需求 13.2）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 设置 FPS
        renderer._stats["fps"] = 30.5
        
        # 创建测试画布
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_fps()
        renderer._draw_fps(frame)
        
        # 验证调用了 _draw_text_with_background
        mock_draw_text.assert_called_once()
        
        # 验证 FPS 文本
        call_args = mock_draw_text.call_args[0]
        frame_arg, text = call_args[:2]
        
        self.assertIn("FPS", text)
        self.assertIn("30.5", text)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer._draw_text_with_background')
    def test_draw_device_info_displays_device_alias(self, mock_draw_text):
        """测试 _draw_device_info() 显示设备别名（需求 12.2）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试数据
        processed_data = DeviceProcessedDataDTO(
            device_id="device_001",
            frame_id=1,
            labels=np.array([], dtype=np.int32),
            bbox=np.zeros((0, 4), dtype=np.float32),
            coords=np.zeros((0, 3), dtype=np.float32),
            confidence=np.array([], dtype=np.float32),
            state_label=[],
            device_alias="Left Camera",
        )
        
        # 创建测试画布
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_device_info()
        renderer._draw_device_info(frame, "device_001", processed_data)
        
        # 验证调用了 _draw_text_with_background
        mock_draw_text.assert_called_once()
        
        # 验证设备信息文本
        call_args = mock_draw_text.call_args[0]
        frame_arg, text = call_args[:2]
        
        self.assertIn("Left Camera", text)
        self.assertIn("device_001", text)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer._draw_text_with_background')
    def test_draw_key_hints_displays_all_keys(self, mock_draw_text):
        """测试 _draw_key_hints() 显示所有按键提示（需求 12.2）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=["device_001", "device_002"],
        )
        
        # 初始化
        renderer.initialize()
        
        # 创建测试画布
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用 _draw_key_hints()
        renderer._draw_key_hints(frame)
        
        # 验证调用了 _draw_text_with_background
        mock_draw_text.assert_called_once()
        
        # 验证按键提示文本
        call_args = mock_draw_text.call_args[0]
        frame_arg, text = call_args[:2]
        
        # 验证包含所有按键提示
        self.assertIn("1:", text)
        self.assertIn("2:", text)
        self.assertIn("3:Combined", text)
        self.assertIn("F:Fullscreen", text)
        self.assertIn("Q:Quit", text)


if __name__ == '__main__':
    unittest.main()
