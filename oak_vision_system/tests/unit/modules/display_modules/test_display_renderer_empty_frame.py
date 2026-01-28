"""DisplayRenderer 空检测帧处理测试

测试 DisplayRenderer 正确处理空检测帧的能力。
验证需求：3.5, 3.6, 15.1, 15.2
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.modules.display_modules.render_packet_packager import RenderPacket
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer


class TestDisplayRendererEmptyFrame:
    """测试 DisplayRenderer 处理空检测帧"""
    
    @pytest.fixture
    def valid_config(self):
        """有效的显示配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
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
    def empty_detection_frame(self):
        """创建空检测帧的 DeviceProcessedDataDTO"""
        return DeviceProcessedDataDTO(
            device_id="device_001_mxid",
            frame_id=42,
            device_alias="test_camera",
            coords=np.empty((0, 3), dtype=np.float32),  # 空数组
            bbox=np.empty((0, 4), dtype=np.float32),
            confidence=np.empty((0,), dtype=np.float32),
            labels=np.empty((0,), dtype=np.int32),
            state_label=[],  # 空列表
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
    
    @pytest.fixture
    def empty_render_packet(self, video_frame, empty_detection_frame):
        """创建包含空检测帧的渲染包"""
        return RenderPacket(
            video_frame=video_frame,
            processed_detections=empty_detection_frame,
        )
    
    def test_draw_detection_boxes_with_empty_frame(
        self,
        valid_config,
        mock_packager,
        devices_list,
        empty_detection_frame
    ):
        """测试 _draw_detection_boxes 方法处理空检测帧
        
        验证：
        - 空检测帧不崩溃
        - 不绘制任何内容
        - 方法正常返回
        """
        # Arrange
        renderer = DisplayRenderer(
            config=valid_config,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # 创建一个测试帧
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_copy = frame.copy()
        
        # Act - 调用绘制方法
        renderer._draw_detection_boxes(frame, empty_detection_frame)
        
        # Assert - 验证帧未被修改（没有绘制任何内容）
        assert np.array_equal(frame, frame_copy), "空检测帧不应修改视频帧"
    
    def test_render_single_device_with_empty_detection(
        self,
        valid_config,
        mock_packager,
        devices_list,
        empty_render_packet
    ):
        """测试 _render_single_device 方法处理空检测帧
        
        验证：
        - 空检测帧不崩溃
        - 仅显示视频帧
        - 不抛出异常
        """
        # Arrange
        renderer = DisplayRenderer(
            config=valid_config,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # Act - 调用渲染方法（不应崩溃）
        try:
            frame = renderer._render_single_device(empty_render_packet)
            success = True
            error_msg = ""
        except Exception as e:
            success = False
            error_msg = str(e)
        
        # Assert
        assert success, f"渲染空检测帧时不应抛出异常，但抛出了: {error_msg}"
        
        # 验证返回的帧不为空
        assert frame is not None, "应该返回渲染后的帧"
        assert frame.shape[2] == 3, "应该返回3通道图像"
    
    def test_empty_frame_validation(self, empty_detection_frame):
        """测试空检测帧的数据验证
        
        验证：
        - 空检测帧是有效的 DeviceProcessedDataDTO
        - 所有数组形状正确
        """
        # Act
        errors = empty_detection_frame._validate_data()
        
        # Assert
        assert len(errors) == 0, f"空检测帧应该是有效的，但发现错误: {errors}"
        assert empty_detection_frame.coords.shape == (0, 3), "coords 应该是空的 (0, 3) 数组"
        assert empty_detection_frame.bbox.shape == (0, 4), "bbox 应该是空的 (0, 4) 数组"
        assert empty_detection_frame.confidence.shape == (0,), "confidence 应该是空的 (0,) 数组"
        assert empty_detection_frame.labels.shape == (0,), "labels 应该是空的 (0,) 数组"
        assert len(empty_detection_frame.state_label) == 0, "state_label 应该是空列表"
    
    def test_empty_render_packet_validation(self, empty_render_packet):
        """测试包含空检测帧的渲染包验证
        
        验证：
        - 包含空检测帧的渲染包是有效的
        - device_id 和 frame_id 一致
        """
        # Act
        errors = empty_render_packet._validate_data()
        
        # Assert
        assert len(errors) == 0, f"包含空检测帧的渲染包应该是有效的，但发现错误: {errors}"
        assert empty_render_packet.video_frame.device_id == empty_render_packet.processed_detections.device_id
        assert empty_render_packet.video_frame.frame_id == empty_render_packet.processed_detections.frame_id
    
    def test_mixed_empty_and_non_empty_frames(
        self,
        valid_config,
        mock_packager,
        devices_list,
        video_frame,
        empty_detection_frame
    ):
        """测试混合空帧和非空帧的场景
        
        验证：
        - 系统能够处理空帧和非空帧的交替
        - 不会因为空帧而影响后续帧的处理
        """
        # Arrange
        renderer = DisplayRenderer(
            config=valid_config,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # 创建非空检测帧
        non_empty_detection = DeviceProcessedDataDTO(
            device_id="device_001_mxid",
            frame_id=43,
            device_alias="test_camera",
            coords=np.array([[100.0, 200.0, 300.0]], dtype=np.float32),
            bbox=np.array([[10.0, 20.0, 100.0, 200.0]], dtype=np.float32),
            confidence=np.array([0.95], dtype=np.float32),
            labels=np.array([0], dtype=np.int32),
            state_label=[],
        )
        
        # 创建测试帧
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2 = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act - 先处理空帧，再处理非空帧
        with patch('cv2.rectangle') as mock_rectangle:
            renderer._draw_detection_boxes(frame1, empty_detection_frame)
            empty_frame_calls = mock_rectangle.call_count
            
            renderer._draw_detection_boxes(frame2, non_empty_detection)
            non_empty_frame_calls = mock_rectangle.call_count
        
        # Assert
        assert empty_frame_calls == 0, "空帧不应调用 cv2.rectangle"
        assert non_empty_frame_calls == 1, "非空帧应调用 cv2.rectangle 一次"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
