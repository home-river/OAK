"""
DisplayRenderer 单窗口管理功能测试

测试新的单窗口策略：
- 单个主窗口创建和管理
- 全屏模式启用/禁用
- 全屏切换功能
- 窗口位置设置
- 窗口标题更新（根据显示模式）

注意：新的单窗口策略只有一个主窗口，通过切换显示内容而不是切换窗口。
"""

import unittest
from unittest.mock import MagicMock, Mock, patch, call
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacket,
    RenderPacketPackager,
)


class TestDisplayRendererWindowManagement(unittest.TestCase):
    """测试 DisplayRenderer 的单窗口管理功能"""
    
    def setUp(self):
        """测试前准备"""
        # 创建配置对象
        self.config = DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            window_position_x=100,
            window_position_y=50,
            enable_fullscreen=False,
            target_fps=20,
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
    
    def tearDown(self):
        """测试后清理"""
        # 停止渲染器（如果正在运行）
        if self.renderer.is_running:
            self.renderer.stop(timeout=1.0)
    
    def _create_test_packet(
        self,
        device_id: str = "device1",
        device_alias: str = "test_camera",
        frame_id: int = 1,
        has_detections: bool = True
    ) -> RenderPacket:
        """创建测试用的渲染包
        
        Args:
            device_id: 设备ID
            device_alias: 设备别名
            frame_id: 帧ID
            has_detections: 是否包含检测数据
            
        Returns:
            RenderPacket: 测试用的渲染包
        """
        # 创建视频帧
        rgb_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        depth_frame = np.zeros((480, 640), dtype=np.uint16)
        
        video_frame = VideoFrameDTO(
            device_id=device_id,
            frame_id=frame_id,
            rgb_frame=rgb_frame,
            depth_frame=depth_frame,
        )
        
        # 创建处理后的检测数据
        if has_detections:
            coords = np.array([[100, 200, 300]], dtype=np.float32)
            bbox = np.array([[50, 50, 150, 150]], dtype=np.float32)
            confidence = np.array([0.95], dtype=np.float32)
            labels = np.array([0], dtype=np.int32)
        else:
            coords = np.empty((0, 3), dtype=np.float32)
            bbox = np.empty((0, 4), dtype=np.float32)
            confidence = np.empty((0,), dtype=np.float32)
            labels = np.empty((0,), dtype=np.int32)
        
        processed_data = DeviceProcessedDataDTO(
            device_id=device_id,
            frame_id=frame_id,
            device_alias=device_alias,
            coords=coords,
            bbox=bbox,
            confidence=confidence,
            labels=labels,
            state_label=[],
        )
        
        # 创建渲染包
        return RenderPacket(
            video_frame=video_frame,
            processed_detections=processed_data,
        )
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_main_window_creation(self, mock_cv2):
        """测试主窗口创建
        
        验证创建单个主窗口，名称为 "OAK Display"
        """
        # 调用 _create_main_window 方法
        self.renderer._create_main_window()
        
        # 验证窗口名称
        self.assertEqual(self.renderer._main_window_name, "OAK Display")
        
        # 验证 cv2.namedWindow 被调用
        mock_cv2.namedWindow.assert_called_once_with(
            "OAK Display",
            mock_cv2.WINDOW_NORMAL
        )
        
        # 验证窗口已创建标志
        self.assertTrue(self.renderer._window_created)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_window_size_single_device_mode(self, mock_cv2):
        """测试单设备模式的窗口大小
        
        验证单设备模式使用配置的窗口大小（640x480）
        """
        # 设置为单设备模式
        self.renderer._display_mode = "single"
        
        # 调用 _create_main_window 方法
        self.renderer._create_main_window()
        
        # 验证窗口大小（单设备：640x480）
        mock_cv2.resizeWindow.assert_called_once_with(
            "OAK Display",
            640,  # window_width
            480   # window_height
        )
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_window_size_combined_mode(self, mock_cv2):
        """测试 Combined 模式的窗口大小
        
        验证 Combined 模式使用双倍宽度（1280x480）
        """
        # 设置为 Combined 模式
        self.renderer._display_mode = "combined"
        
        # 调用 _create_main_window 方法
        self.renderer._create_main_window()
        
        # 验证窗口大小（Combined：1280x480）
        mock_cv2.resizeWindow.assert_called_once_with(
            "OAK Display",
            1280,  # window_width * 2
            480    # window_height
        )
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_window_position_setting(self, mock_cv2):
        """测试窗口位置设置
        
        验证从配置读取 window_position_x 和 window_position_y，
        并使用 cv2.moveWindow() 设置窗口位置
        """
        # 调用 _create_main_window 方法
        self.renderer._create_main_window()
        
        # 验证 cv2.moveWindow 被调用，参数为配置的位置
        mock_cv2.moveWindow.assert_called_once_with(
            "OAK Display",
            100,  # window_position_x
            50    # window_position_y
        )
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_window_position_not_set_when_zero(self, mock_cv2):
        """测试窗口位置为零时不设置
        
        验证当窗口位置为 (0, 0) 时，不调用 cv2.moveWindow()
        """
        # 创建配置对象（位置为 0, 0）
        config = DisplayConfigDTO(
            enable_display=True,
            window_position_x=0,
            window_position_y=0,
        )
        
        renderer = DisplayRenderer(
            config=config,
            packager=self.packager,
            devices_list=self.devices_list,
        )
        
        # 调用 _create_main_window 方法
        renderer._create_main_window()
        
        # 验证 cv2.moveWindow 未被调用
        mock_cv2.moveWindow.assert_not_called()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_fullscreen_mode_enabled(self, mock_cv2):
        """测试全屏模式启用
        
        验证从配置读取 enable_fullscreen，
        如果为 True，使用 cv2.setWindowProperty() 设置全屏
        """
        # 创建配置对象（启用全屏）
        config = DisplayConfigDTO(
            enable_display=True,
            enable_fullscreen=True,
        )
        
        renderer = DisplayRenderer(
            config=config,
            packager=self.packager,
            devices_list=self.devices_list,
        )
        
        # 调用 _create_main_window 方法
        renderer._create_main_window()
        
        # 验证 cv2.setWindowProperty 被调用，设置全屏
        mock_cv2.setWindowProperty.assert_called_with(
            "OAK Display",
            mock_cv2.WND_PROP_FULLSCREEN,
            mock_cv2.WINDOW_FULLSCREEN
        )
        
        # 验证全屏状态被记录
        self.assertTrue(renderer._is_fullscreen)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_fullscreen_mode_disabled(self, mock_cv2):
        """测试全屏模式禁用
        
        验证当 enable_fullscreen 为 False 时，不设置全屏
        """
        # 创建配置对象（禁用全屏）
        config = DisplayConfigDTO(
            enable_display=True,
            enable_fullscreen=False,
        )
        
        renderer = DisplayRenderer(
            config=config,
            packager=self.packager,
            devices_list=self.devices_list,
        )
        
        # 调用 _create_main_window 方法
        renderer._create_main_window()
        
        # 验证全屏状态被记录为 False
        self.assertFalse(renderer._is_fullscreen)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_toggle_fullscreen_to_fullscreen(self, mock_cv2):
        """测试切换到全屏模式
        
        验证检测 'f' 键，切换全屏/窗口模式
        使用 cv2.WINDOW_FULLSCREEN
        """
        # 创建主窗口（初始为非全屏）
        self.renderer._create_main_window()
        
        # 验证初始状态为非全屏
        self.assertFalse(self.renderer._is_fullscreen)
        
        # 重置 mock 调用记录
        mock_cv2.setWindowProperty.reset_mock()
        
        # 调用 _toggle_fullscreen 方法
        self.renderer._toggle_fullscreen()
        
        # 验证 cv2.setWindowProperty 被调用，切换到全屏
        mock_cv2.setWindowProperty.assert_called_once_with(
            "OAK Display",
            mock_cv2.WND_PROP_FULLSCREEN,
            mock_cv2.WINDOW_FULLSCREEN
        )
        
        # 验证全屏状态被更新
        self.assertTrue(self.renderer._is_fullscreen)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_toggle_fullscreen_to_windowed(self, mock_cv2):
        """测试切换到窗口模式
        
        验证从全屏模式切换回窗口模式
        """
        # 创建配置对象（启用全屏）
        config = DisplayConfigDTO(
            enable_display=True,
            enable_fullscreen=True,
        )
        
        renderer = DisplayRenderer(
            config=config,
            packager=self.packager,
            devices_list=self.devices_list,
        )
        
        # 创建主窗口（初始为全屏）
        renderer._create_main_window()
        
        # 验证初始状态为全屏
        self.assertTrue(renderer._is_fullscreen)
        
        # 重置 mock 调用记录
        mock_cv2.setWindowProperty.reset_mock()
        
        # 调用 _toggle_fullscreen 方法
        renderer._toggle_fullscreen()
        
        # 验证 cv2.setWindowProperty 被调用，切换到窗口模式
        mock_cv2.setWindowProperty.assert_called_once_with(
            "OAK Display",
            mock_cv2.WND_PROP_FULLSCREEN,
            mock_cv2.WINDOW_NORMAL
        )
        
        # 验证全屏状态被更新
        self.assertFalse(renderer._is_fullscreen)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2')
    def test_toggle_fullscreen_without_window(self, mock_cv2):
        """测试在窗口未创建时切换全屏
        
        验证如果窗口未创建，_toggle_fullscreen 不执行任何操作
        """
        # 确保窗口未创建
        self.assertFalse(self.renderer._window_created)
        
        # 调用 _toggle_fullscreen 方法
        self.renderer._toggle_fullscreen()
        
        # 验证 cv2.setWindowProperty 未被调用
        mock_cv2.setWindowProperty.assert_not_called()


if __name__ == '__main__':
    unittest.main()
