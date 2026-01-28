"""DisplayRenderer FPS 和设备信息显示测试

测试 DisplayRenderer 绘制 FPS 和设备信息的能力。
验证需求：8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch, MagicMock

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.modules.display_modules.render_packet_packager import RenderPacket
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer


class TestDisplayRendererFPSDeviceInfo:
    """测试 DisplayRenderer FPS 和设备信息显示功能"""
    
    @pytest.fixture
    def config_with_fps_and_device_info(self):
        """启用 FPS 和设备信息显示的配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            show_fps=True,
            show_device_info=True,
        )
    
    @pytest.fixture
    def config_fps_only(self):
        """仅启用 FPS 显示的配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            show_fps=True,
            show_device_info=False,
        )
    
    @pytest.fixture
    def config_device_info_only(self):
        """仅启用设备信息显示的配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            show_fps=False,
            show_device_info=True,
        )
    
    @pytest.fixture
    def config_no_info(self):
        """禁用 FPS 和设备信息显示的配置"""
        return DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            show_fps=False,
            show_device_info=False,
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
            device_alias="left_camera",
            coords=np.array([[100.0, 200.0, 300.0]], dtype=np.float32),
            bbox=np.array([[10.0, 20.0, 100.0, 200.0]], dtype=np.float32),
            confidence=np.array([0.95], dtype=np.float32),
            labels=np.array([0], dtype=np.int32),
            state_label=[],
        )
    
    def test_update_fps_calculation(
        self,
        config_with_fps_and_device_info,
        mock_packager,
        devices_list
    ):
        """测试 FPS 计算
        
        验证：
        - 帧时间戳队列正确维护
        - FPS 计算正确
        - 每秒更新一次 FPS 值
        
        需求：8.3, 8.4
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_fps_and_device_info,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # Act - 模拟多次帧更新
        with patch('time.time') as mock_time:
            # 模拟 20 帧，每帧间隔 0.05 秒（20 FPS）
            base_time = 1000.0
            
            # 初始化时间戳
            mock_time.return_value = base_time
            renderer._last_fps_update_time = base_time
            
            # 添加 20 帧
            for i in range(20):
                mock_time.return_value = base_time + i * 0.05
                renderer._update_fps()
            
            # 等待 1 秒后再更新一次（触发 FPS 计算）
            mock_time.return_value = base_time + 1.0
            renderer._update_fps()
            
            # Assert
            # 验证 FPS 值已更新
            stats = renderer.get_stats()
            fps = stats["fps"]
            
            # FPS 应该接近 20
            # 注意：由于时间戳队列只保留最近 1 秒的数据，
            # 实际 FPS 会根据保留的帧数计算
            assert fps > 0, "FPS 应该大于 0"
            assert 15 < fps < 25, f"FPS 应该接近 20，实际值: {fps}"
    
    def test_update_fps_removes_old_timestamps(
        self,
        config_with_fps_and_device_info,
        mock_packager,
        devices_list
    ):
        """测试 FPS 计算移除旧时间戳
        
        验证：
        - 超过 1 秒的时间戳被移除
        - 仅保留最近 1 秒的时间戳
        
        需求：8.3
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_fps_and_device_info,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # Act
        with patch('time.time') as mock_time:
            # 添加一些旧时间戳
            base_time = 1000.0
            mock_time.return_value = base_time
            renderer._update_fps()
            
            mock_time.return_value = base_time + 0.5
            renderer._update_fps()
            
            # 添加一个超过 1 秒的时间戳
            mock_time.return_value = base_time + 1.5
            renderer._update_fps()
            
            # Assert
            # 验证旧时间戳被移除
            assert len(renderer._frame_timestamps) <= 2, "应该移除超过 1 秒的旧时间戳"
            
            # 验证所有时间戳都在最近 1 秒内
            current_time = base_time + 1.5
            for ts in renderer._frame_timestamps:
                assert ts > current_time - 1.0, "所有时间戳应该在最近 1 秒内"
    
    def test_draw_fps_enabled(
        self,
        config_with_fps_and_device_info,
        mock_packager,
        devices_list
    ):
        """测试绘制 FPS（启用）
        
        验证：
        - FPS 文本格式正确
        - 文本位置在左上角
        - 使用半透明背景
        
        需求：8.1, 8.6
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_fps_and_device_info,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # 设置 FPS 值
        with renderer._stats_lock:
            renderer._stats["fps"] = 25.3
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_fps(frame)
            
            # Assert
            assert mock_draw_text.called, "应该调用 _draw_text_with_background"
            
            # 验证文本格式
            call_args = mock_draw_text.call_args
            text = call_args[0][1]  # 第二个参数是文本
            assert "FPS: 25.3" in text, f"FPS 文本格式应为 'FPS: 25.3'，实际: {text}"
            
            # 验证文本位置（左上角）
            position = call_args[0][2]  # 第三个参数是位置
            assert position[0] == 10, "FPS 文本 X 坐标应为 10"
            assert position[1] == 30, "FPS 文本 Y 坐标应为 30"
    
    def test_draw_fps_disabled(
        self,
        config_no_info,
        mock_packager,
        devices_list
    ):
        """测试绘制 FPS（禁用）
        
        验证：
        - 当 show_fps=False 时，不绘制 FPS
        
        需求：8.1
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_no_info,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_fps(frame)
            
            # Assert
            assert not mock_draw_text.called, "禁用 FPS 显示时不应绘制文本"
    
    def test_draw_device_info_with_alias(
        self,
        config_with_fps_and_device_info,
        mock_packager,
        devices_list,
        detection_data
    ):
        """测试绘制设备信息（有别名）
        
        验证：
        - 设备信息文本格式正确
        - 包含设备别名和设备ID
        - 文本位置在右上角
        
        需求：8.2, 8.5, 8.6
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_fps_and_device_info,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        device_id = "device_001_mxid"
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text, \
             patch('cv2.getTextSize') as mock_getTextSize:
            
            # 模拟 getTextSize 返回值
            mock_getTextSize.return_value = ((200, 20), 5)
            
            renderer._draw_device_info(frame, device_id, detection_data)
            
            # Assert
            assert mock_draw_text.called, "应该调用 _draw_text_with_background"
            
            # 验证文本格式
            call_args = mock_draw_text.call_args
            text = call_args[0][1]  # 第二个参数是文本
            assert "Device: left_camera (device_001_mxid)" in text, \
                f"设备信息文本格式应为 'Device: left_camera (device_001_mxid)'，实际: {text}"
            
            # 验证文本位置（右上角）
            position = call_args[0][2]  # 第三个参数是位置
            # 右上角：frame.shape[1] - text_width - 10
            expected_x = 640 - 200 - 10
            assert position[0] == expected_x, f"设备信息文本 X 坐标应为 {expected_x}"
            assert position[1] == 30, "设备信息文本 Y 坐标应为 30"
    
    def test_draw_device_info_without_alias(
        self,
        config_with_fps_and_device_info,
        mock_packager,
        devices_list
    ):
        """测试绘制设备信息（无别名）
        
        验证：
        - 设备信息文本仅包含设备ID
        - 不包含别名
        
        需求：8.2, 8.5
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_fps_and_device_info,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # 创建无别名的检测数据
        detection_data_no_alias = DeviceProcessedDataDTO(
            device_id="device_001_mxid",
            frame_id=42,
            device_alias=None,  # 无别名
            coords=np.array([[100.0, 200.0, 300.0]], dtype=np.float32),
            bbox=np.array([[10.0, 20.0, 100.0, 200.0]], dtype=np.float32),
            confidence=np.array([0.95], dtype=np.float32),
            labels=np.array([0], dtype=np.int32),
            state_label=[],
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        device_id = "device_001_mxid"
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text, \
             patch('cv2.getTextSize') as mock_getTextSize:
            
            # 模拟 getTextSize 返回值
            mock_getTextSize.return_value = ((150, 20), 5)
            
            renderer._draw_device_info(frame, device_id, detection_data_no_alias)
            
            # Assert
            assert mock_draw_text.called, "应该调用 _draw_text_with_background"
            
            # 验证文本格式
            call_args = mock_draw_text.call_args
            text = call_args[0][1]
            assert "Device: device_001_mxid" in text, \
                f"设备信息文本格式应为 'Device: device_001_mxid'，实际: {text}"
            assert "left_camera" not in text, "无别名时不应包含别名"
    
    def test_draw_device_info_disabled(
        self,
        config_no_info,
        mock_packager,
        devices_list,
        detection_data
    ):
        """测试绘制设备信息（禁用）
        
        验证：
        - 当 show_device_info=False 时，不绘制设备信息
        
        需求：8.2
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_no_info,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        device_id = "device_001_mxid"
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text:
            renderer._draw_device_info(frame, device_id, detection_data)
            
            # Assert
            assert not mock_draw_text.called, "禁用设备信息显示时不应绘制文本"
    
    def test_fps_and_device_info_together(
        self,
        config_with_fps_and_device_info,
        mock_packager,
        devices_list,
        detection_data
    ):
        """测试同时显示 FPS 和设备信息
        
        验证：
        - FPS 显示在左上角
        - 设备信息显示在右上角
        - 两者不重叠
        
        需求：8.1, 8.2, 8.6
        """
        # Arrange
        renderer = DisplayRenderer(
            config=config_with_fps_and_device_info,
            packager=mock_packager,
            devices_list=devices_list,
        )
        
        # 设置 FPS 值
        with renderer._stats_lock:
            renderer._stats["fps"] = 25.3
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        device_id = "device_001_mxid"
        
        # Act
        with patch.object(renderer, '_draw_text_with_background') as mock_draw_text, \
             patch('cv2.getTextSize') as mock_getTextSize:
            
            # 模拟 getTextSize 返回值
            mock_getTextSize.return_value = ((200, 20), 5)
            
            # 绘制 FPS
            renderer._draw_fps(frame)
            fps_call_count = mock_draw_text.call_count
            
            # 绘制设备信息
            renderer._draw_device_info(frame, device_id, detection_data)
            device_info_call_count = mock_draw_text.call_count
            
            # Assert
            assert fps_call_count == 1, "应该绘制 FPS"
            assert device_info_call_count == 2, "应该绘制设备信息"
            
            # 验证 FPS 位置（左上角）
            fps_call = mock_draw_text.call_args_list[0]
            fps_position = fps_call[0][2]
            assert fps_position[0] == 10, "FPS 应该在左上角"
            
            # 验证设备信息位置（右上角）
            device_info_call = mock_draw_text.call_args_list[1]
            device_info_position = device_info_call[0][2]
            assert device_info_position[0] > 400, "设备信息应该在右上角"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
