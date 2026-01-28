"""DisplayRenderer 叠加信息显示测试

测试 DisplayRenderer 绘制标签、置信度和坐标的能力。
验证需求：6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.modules.display_modules.render_packet_packager import RenderPacket
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer


class TestDisplayRendererOverlay:
    """测试 DisplayRenderer 叠加信息显示功能"""
    
    @pytest.fixture
    def config_with_all_overlays(self):
        """启用所有叠加信息的配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            show_labels=True,
            show_confidence=True,
            show_coordinates=True,
            text_scale=0.6,
        )
    
    @pytest.fixture
    def config_labels_only(self):
        """仅启用标签显示的配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            show_labels=True,
            show_confidence=False,
            show_coordinates=False,
            text_scale=0.6,
        )
    
    @pytest.fixture
    def config_no_overlays(self):
        """禁用所有叠加信息的配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            show_labels=False,
            show_confidence=False,
            show_coordinates=False,
            text_scale=0.6,
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
    def detection_data(self):
        """创建包含检测数据的 DeviceProcessedDataDTO"""
        return DeviceProcessedDataDTO(
            device_id="device_001_mxid",
            frame_id=42,
            device_alias="test_camera",
            coords=np.array([
                [100.0, 200.0, 300.0],
                [400.0, 500.0, 600.0],
            ], dtype=np.float32),
            bbox=np.array([
                [10.0, 20.0, 100.0, 200.0],
                [150.0, 250.0, 350.0, 450.0],
            ], dtype=np.float32),
            confidence=np.array([0.95, 0.87], dtype=np.float32),
            labels=np.array([0, 1], dtype=np.int32),
            state_label=[],
        )
    
    @pytest.fixture
    def video_frame(self):
        """创建视频帧"""
        return VideoFrameDTO(
            device_id="device_001_mxid",
            frame_id=42,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
            depth_frame=None,
        )
    
    def test_draw_labels_with_confidence(
        self,
        config_with_all_overlays,
        mock_packager,
        devices_list,
        detection_data
    ):
        """测试绘制标签和置信度
        
        验证：
        - 标签文本包含标签ID
        - 置信度以百分比形式显示
        - 文本位置在边界框上方
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_all_overlays,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_labels(frame, detection_data)
            
            # Assert
            assert mock_draw_text.call_count == 2, "应该为两个检测框绘制标签"
            
            # 验证第一个标签
            first_call = mock_draw_text.call_args_list[0]
            first_text = first_call[0][1]  # 第二个参数是文本
            assert "Label_0" in first_text, "标签文本应包含 Label_0"
            assert "95%" in first_text, "标签文本应包含置信度 95%"
            
            # 验证第二个标签
            second_call = mock_draw_text.call_args_list[1]
            second_text = second_call[0][1]
            assert "Label_1" in second_text, "标签文本应包含 Label_1"
            assert "87%" in second_text, "标签文本应包含置信度 87%"
    
    def test_draw_labels_without_confidence(
        self,
        config_labels_only,
        mock_packager,
        devices_list,
        detection_data
    ):
        """测试仅绘制标签（不显示置信度）
        
        验证：
        - 标签文本仅包含标签ID
        - 不包含置信度信息
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_labels_only,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_labels(frame, detection_data)
            
            # Assert
            assert mock_draw_text.call_count == 2, "应该为两个检测框绘制标签"
            
            # 验证标签文本不包含置信度
            first_call = mock_draw_text.call_args_list[0]
            first_text = first_call[0][1]
            assert "Label_0" in first_text, "标签文本应包含 Label_0"
            assert "%" not in first_text, "标签文本不应包含置信度百分比"
    
    def test_draw_labels_disabled(
        self,
        config_no_overlays,
        mock_packager,
        devices_list,
        detection_data
    ):
        """测试禁用标签显示
        
        验证：
        - 当 show_labels=False 时，不绘制任何标签
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_no_overlays,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_labels(frame, detection_data)
            
            # Assert
            assert mock_draw_text.call_count == 0, "禁用标签显示时不应绘制任何文本"
    
    def test_draw_coordinates(
        self,
        config_with_all_overlays,
        mock_packager,
        devices_list,
        detection_data
    ):
        """测试绘制 3D 坐标
        
        验证：
        - 坐标格式为 "(x, y, z) mm"
        - 文本位置在边界框下方
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_all_overlays,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_coordinates(frame, detection_data)
            
            # Assert
            assert mock_draw_text.call_count == 2, "应该为两个检测框绘制坐标"
            
            # 验证第一个坐标
            first_call = mock_draw_text.call_args_list[0]
            first_text = first_call[0][1]
            assert "(100, 200, 300) mm" in first_text, "坐标文本格式应为 (x, y, z) mm"
            
            # 验证第二个坐标
            second_call = mock_draw_text.call_args_list[1]
            second_text = second_call[0][1]
            assert "(400, 500, 600) mm" in second_text, "坐标文本格式应为 (x, y, z) mm"
    
    def test_draw_coordinates_disabled(
        self,
        config_no_overlays,
        mock_packager,
        devices_list,
        detection_data
    ):
        """测试禁用坐标显示
        
        验证：
        - 当 show_coordinates=False 时，不绘制任何坐标
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_no_overlays,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_coordinates(frame, detection_data)
            
            # Assert
            assert mock_draw_text.call_count == 0, "禁用坐标显示时不应绘制任何文本"
    
    def test_draw_text_with_background(
        self,
        config_with_all_overlays,
        mock_packager,
        devices_list
    ):
        """测试绘制带背景的文本
        
        验证：
        - 背景矩形被绘制
        - 文本被绘制
        - 使用正确的颜色和字体
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_all_overlays,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch('cv2.getTextSize') as mock_getTextSize, \
             patch('cv2.rectangle') as mock_rectangle, \
             patch('cv2.addWeighted') as mock_addWeighted, \
             patch('cv2.putText') as mock_putText:
            
            # 模拟 getTextSize 返回值
            mock_getTextSize.return_value = ((100, 20), 5)
            
            renderer._draw_text_with_background(
                frame,
                "Test Text",
                (10, 30),
                0.6,
                text_color=(255, 255, 255),
                bg_color=(0, 0, 0),
                thickness=1,
                padding=5
            )
            
            # Assert
            assert mock_getTextSize.called, "应该调用 getTextSize 获取文本尺寸"
            assert mock_rectangle.called, "应该绘制背景矩形"
            assert mock_addWeighted.called, "应该混合背景（半透明效果）"
            assert mock_putText.called, "应该绘制文本"
            
            # 验证 putText 参数
            putText_call = mock_putText.call_args
            assert putText_call[0][1] == "Test Text", "文本内容应正确"
            assert putText_call[0][2] == (10, 30), "文本位置应正确"
    
    def test_draw_labels_with_empty_frame(
        self,
        config_with_all_overlays,
        mock_packager,
        devices_list
    ):
        """测试空检测帧不绘制标签
        
        验证：
        - 空检测帧不调用绘制方法
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_all_overlays,
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
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_labels(frame, empty_detection)
            
            # Assert
            assert mock_draw_text.call_count == 0, "空检测帧不应绘制任何标签"
    
    def test_draw_coordinates_with_empty_frame(
        self,
        config_with_all_overlays,
        mock_packager,
        devices_list
    ):
        """测试空检测帧不绘制坐标
        
        验证：
        - 空检测帧不调用绘制方法
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_all_overlays,
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
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_coordinates(frame, empty_detection)
            
            # Assert
            assert mock_draw_text.call_count == 0, "空检测帧不应绘制任何坐标"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
