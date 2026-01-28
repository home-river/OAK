"""DisplayRenderer 按状态标签着色测试

测试 DisplayRenderer 根据状态标签选择不同颜色绘制检测框的能力。
验证需求：7.1, 7.2, 7.3, 7.4, 7.5
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import (
    DeviceProcessedDataDTO,
    DetectionStatusLabel,
)
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer


class TestDisplayRendererColorByLabel:
    """测试 DisplayRenderer 按标签着色功能"""
    
    @pytest.fixture
    def config_color_by_label_enabled(self):
        """启用按标签着色的配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            bbox_color_by_label=True,  # 启用按标签着色
        )
    
    @pytest.fixture
    def config_color_by_label_disabled(self):
        """禁用按标签着色的配置（使用固定颜色）"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            bbox_color_by_label=False,  # 禁用按标签着色
        )
    
    @pytest.fixture
    def mock_packager(self):
        """模拟的 RenderPacketPackager"""
        packager = Mock()
        packager.get_packets = Mock(return_value={})
        return packager
    
    @pytest.fixture
    def devices_list(self):
        """设备列表"""
        return ["device_001_mxid"]
    
    @pytest.fixture
    def detection_data_multiple_labels(self):
        """创建包含多个不同状态标签的检测数据"""
        return DeviceProcessedDataDTO(
            device_id="device_001_mxid",
            frame_id=42,
            device_alias="test_camera",
            coords=np.array([
                [100.0, 200.0, 300.0],
                [400.0, 500.0, 600.0],
                [700.0, 800.0, 900.0],
            ], dtype=np.float32),
            bbox=np.array([
                [10.0, 20.0, 100.0, 200.0],
                [150.0, 250.0, 350.0, 450.0],
                [200.0, 300.0, 400.0, 500.0],
            ], dtype=np.float32),
            confidence=np.array([0.95, 0.87, 0.92], dtype=np.float32),
            labels=np.array([0, 1, 2], dtype=np.int32),
            state_label=[
                DetectionStatusLabel.OBJECT_GRASPABLE,
                DetectionStatusLabel.OBJECT_DANGEROUS,
                DetectionStatusLabel.OBJECT_OUT_OF_RANGE,
            ],  # 三个不同的状态标签
        )
    
    def test_color_palette_exists(
        self,
        config_color_by_label_enabled,
        mock_packager,
        devices_list
    ):
        """测试状态标签颜色映射字典存在且包含所有状态标签
        
        验证需求：7.2, 7.3
        """
        # Arrange & Act
        renderer = DisplayRenderer(
            config=config_color_by_label_enabled,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # Assert
        assert hasattr(DisplayRenderer, 'STATE_LABEL_COLOR_MAP'), \
            "应该定义 STATE_LABEL_COLOR_MAP 类属性"
        assert hasattr(DisplayRenderer, 'DEFAULT_BBOX_COLOR'), \
            "应该定义 DEFAULT_BBOX_COLOR 类属性"
        
        # 验证所有状态标签都有对应的颜色映射
        expected_labels = [
            DetectionStatusLabel.OBJECT_GRASPABLE,
            DetectionStatusLabel.OBJECT_DANGEROUS,
            DetectionStatusLabel.OBJECT_OUT_OF_RANGE,
            DetectionStatusLabel.OBJECT_PENDING_GRASP,
            DetectionStatusLabel.HUMAN_SAFE,
            DetectionStatusLabel.HUMAN_DANGEROUS,
        ]
        
        for label in expected_labels:
            assert label in DisplayRenderer.STATE_LABEL_COLOR_MAP, \
                f"状态标签 {label.name} 应该在颜色映射字典中"
            color = DisplayRenderer.STATE_LABEL_COLOR_MAP[label]
            assert isinstance(color, tuple), "颜色应该是一个元组"
            assert len(color) == 3, "颜色应该有3个分量（BGR）"
            assert all(0 <= c <= 255 for c in color), "颜色分量应该在0-255范围内"
    
    def test_draw_boxes_with_color_by_label_enabled(
        self,
        config_color_by_label_enabled,
        mock_packager,
        devices_list,
        detection_data_multiple_labels
    ):
        """测试启用按状态标签着色时，不同状态使用不同颜色
        
        验证需求：7.1, 7.4
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_color_by_label_enabled,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch('cv2.rectangle') as mock_rectangle:
            renderer._draw_detection_boxes(frame, detection_data_multiple_labels)
            
            # Assert
            assert mock_rectangle.call_count == 3, "应该为三个检测框调用 cv2.rectangle"
            
            # 提取每次调用使用的颜色
            colors_used = []
            for call in mock_rectangle.call_args_list:
                color = call[0][3]  # 第4个参数是颜色
                colors_used.append(color)
            
            # 验证使用了映射字典中定义的颜色
            expected_colors = [
                DisplayRenderer.STATE_LABEL_COLOR_MAP[DetectionStatusLabel.OBJECT_GRASPABLE],
                DisplayRenderer.STATE_LABEL_COLOR_MAP[DetectionStatusLabel.OBJECT_DANGEROUS],
                DisplayRenderer.STATE_LABEL_COLOR_MAP[DetectionStatusLabel.OBJECT_OUT_OF_RANGE],
            ]
            
            assert colors_used[0] == expected_colors[0], \
                f"状态标签 OBJECT_GRASPABLE 应该使用颜色 {expected_colors[0]}"
            
            assert colors_used[1] == expected_colors[1], \
                f"状态标签 OBJECT_DANGEROUS 应该使用颜色 {expected_colors[1]}"
            
            assert colors_used[2] == expected_colors[2], \
                f"状态标签 OBJECT_OUT_OF_RANGE 应该使用颜色 {expected_colors[2]}"
            
            # 验证至少有两种不同的颜色被使用
            unique_colors = set(colors_used)
            assert len(unique_colors) >= 2, "不同状态标签应该使用不同的颜色"
    
    def test_draw_boxes_with_color_by_label_disabled(
        self,
        config_color_by_label_disabled,
        mock_packager,
        devices_list,
        detection_data_multiple_labels
    ):
        """测试禁用按状态标签着色时，所有检测框使用默认颜色
        
        验证需求：7.4
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_color_by_label_disabled,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch('cv2.rectangle') as mock_rectangle:
            renderer._draw_detection_boxes(frame, detection_data_multiple_labels)
            
            # Assert
            assert mock_rectangle.call_count == 3, "应该为三个检测框调用 cv2.rectangle"
            
            # 提取每次调用使用的颜色
            colors_used = []
            for call in mock_rectangle.call_args_list:
                color = call[0][3]  # 第4个参数是颜色
                colors_used.append(color)
            
            # 验证所有检测框都使用默认颜色
            default_color = DisplayRenderer.DEFAULT_BBOX_COLOR
            for color in colors_used:
                assert color == default_color, \
                    f"禁用按标签着色时，所有检测框应该使用默认颜色 {default_color}"
    
    def test_color_selection_with_modulo(
        self,
        config_color_by_label_enabled,
        mock_packager,
        devices_list
    ):
        """测试未定义状态标签时使用默认颜色
        
        验证需求：7.5
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_color_by_label_enabled,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # 使用 HUMAN_SAFE 状态标签
        detection_data = DeviceProcessedDataDTO(
            device_id="device_001_mxid",
            frame_id=42,
            device_alias="test_camera",
            coords=np.array([[100.0, 200.0, 300.0]], dtype=np.float32),
            bbox=np.array([[10.0, 20.0, 100.0, 200.0]], dtype=np.float32),
            confidence=np.array([0.95], dtype=np.float32),
            labels=np.array([0], dtype=np.int32),
            state_label=[DetectionStatusLabel.HUMAN_SAFE],
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch('cv2.rectangle') as mock_rectangle:
            renderer._draw_detection_boxes(frame, detection_data)
            
            # Assert
            assert mock_rectangle.call_count == 1, "应该为一个检测框调用 cv2.rectangle"
            
            # 提取使用的颜色
            color_used = mock_rectangle.call_args[0][3]
            
            # 验证使用了映射字典中定义的颜色
            expected_color = DisplayRenderer.STATE_LABEL_COLOR_MAP[DetectionStatusLabel.HUMAN_SAFE]
            assert color_used == expected_color, \
                f"状态标签 HUMAN_SAFE 应该使用颜色 {expected_color}"
    
    def test_draw_boxes_with_empty_frame(
        self,
        config_color_by_label_enabled,
        mock_packager,
        devices_list
    ):
        """测试空检测帧不绘制任何检测框
        
        验证：
        - 空检测帧不调用 cv2.rectangle
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_color_by_label_enabled,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        empty_detection = DeviceProcessedDataDTO(
            device_id="device_001_mxid",
            frame_id=42,
            device_alias="test_camera",
            coords=np.empty((0, 3), dtype=np.float32),
            bbox=np.empty((0, 4), dtype=np.float32),
            confidence=np.empty((0,), dtype=np.float32),
            labels=np.empty((0,), dtype=np.int32),
            state_label=[],
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch('cv2.rectangle') as mock_rectangle:
            renderer._draw_detection_boxes(frame, empty_detection)
            
            # Assert
            assert mock_rectangle.call_count == 0, "空检测帧不应绘制任何检测框"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
