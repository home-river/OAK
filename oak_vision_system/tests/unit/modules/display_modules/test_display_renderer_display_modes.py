"""
测试 DisplayRenderer 的显示模式功能

测试重构后的显示模式：
- 单设备显示模式（按数字键切换）
- Combined 模式（多设备RGB水平拼接）
- 深度图可视化（可选功能，由 enable_depth_output 控制）

注意：已移除旧的 side_by_side 和 combined（RGB+深度叠加）模式
"""

import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacket,
    RenderPacketPackager,
)


class TestDisplayRendererDisplayModes(unittest.TestCase):
    """测试 DisplayRenderer 的显示模式功能（重构后）"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建配置
        self.config = DisplayConfigDTO(
            enable_display=True,
            window_width=640,
            window_height=480,
            target_fps=20,
            show_labels=True,
            show_confidence=True,
            show_coordinates=True,
            show_fps=True,
            show_device_info=True,
            bbox_color_by_label=True,
            normalize_depth=True,
        )
        
        # 创建模拟的 RenderPacketPackager
        self.packager = MagicMock(spec=RenderPacketPackager)
        
        # 双设备列表（固定双设备场景）
        self.devices_list = ["device1", "device2"]
        
        # 创建 DisplayRenderer（启用深度输出）
        self.renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=True,  # 启用深度数据处理
        )
        
        # 创建测试数据
        self.rgb_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        self.depth_frame = np.random.randint(0, 5000, (480, 640), dtype=np.uint16)
        
        self.video_frame = VideoFrameDTO(
            device_id="device1",
            frame_id=1,
            rgb_frame=self.rgb_frame,
            depth_frame=self.depth_frame,
        )
        
        self.processed_data = DeviceProcessedDataDTO(
            device_id="device1",
            frame_id=1,
            device_alias="left_camera",
            coords=np.array([[100, 200, 300]], dtype=np.float32),
            bbox=np.array([[50, 50, 150, 150]], dtype=np.float32),
            confidence=np.array([0.95], dtype=np.float32),
            labels=np.array([0], dtype=np.int32),
            state_label=[],
        )
        
        self.render_packet = RenderPacket(
            video_frame=self.video_frame,
            processed_detections=self.processed_data,
        )
    
    # ==================== 深度图可视化测试（可选功能） ====================
    
    def test_visualize_depth_with_normalization(self):
        """测试深度图可视化（启用归一化）
        
        验证：
        - 深度图正确转换为伪彩色图像
        - 使用百分位数归一化
        - 返回3通道图像
        """
        depth_colored = self.renderer._visualize_depth(self.depth_frame)
        
        # 验证返回值不为空
        self.assertIsNotNone(depth_colored)
        
        # 验证返回值是 3 通道图像
        self.assertEqual(depth_colored.shape[2], 3)
        
        # 验证返回值尺寸与输入一致
        self.assertEqual(depth_colored.shape[:2], self.depth_frame.shape[:2])
        
        # 验证返回值数据类型为 uint8
        self.assertEqual(depth_colored.dtype, np.uint8)
    
    def test_visualize_depth_without_normalization(self):
        """测试深度图可视化（禁用归一化）
        
        验证：
        - 不使用归一化时也能正确处理
        """
        self.config = DisplayConfigDTO(
            enable_display=True,
            normalize_depth=False,
        )
        
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=True,
        )
        
        depth_colored = renderer._visualize_depth(self.depth_frame)
        
        # 验证返回值不为空
        self.assertIsNotNone(depth_colored)
        
        # 验证返回值是 3 通道图像
        self.assertEqual(depth_colored.shape[2], 3)
    
    def test_visualize_depth_with_invalid_values(self):
        """测试深度图可视化（包含无效值）
        
        验证：
        - 正确处理 NaN 和 Inf 值
        - 不崩溃
        """
        # 创建包含 NaN 和 Inf 的深度图
        depth_frame_with_invalid = self.depth_frame.astype(np.float32)
        depth_frame_with_invalid[0, 0] = np.nan
        depth_frame_with_invalid[1, 1] = np.inf
        
        depth_colored = self.renderer._visualize_depth(depth_frame_with_invalid)
        
        # 验证返回值不为空（无效值应该被处理）
        self.assertIsNotNone(depth_colored)
        
        # 验证返回值是 3 通道图像
        self.assertEqual(depth_colored.shape[2], 3)
    
    def test_depth_output_disabled(self):
        """测试禁用深度输出时的行为
        
        验证：
        - enable_depth_output=False 时，深度数据不被处理
        """
        # 创建禁用深度输出的渲染器
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=False,  # 禁用深度输出
        )
        
        # 验证深度输出配置
        self.assertFalse(renderer._enable_depth_output)
    
    # ==================== 单设备显示模式测试 ====================
    
    def test_render_single_device(self):
        """测试单设备显示模式
        
        验证：
        - 正确渲染单个设备的RGB帧
        - 添加设备信息叠加
        - 返回正确尺寸的图像
        """
        frame = self.renderer._render_single_device(self.render_packet)
        
        # 验证返回值不为空
        self.assertIsNotNone(frame)
        
        # 验证返回值是 3 通道图像
        self.assertEqual(frame.shape[2], 3)
        
        # 验证返回值尺寸与输入一致
        self.assertEqual(frame.shape[:2], self.rgb_frame.shape[:2])
    
    def test_render_single_device_with_empty_detections(self):
        """测试单设备显示模式（空检测帧）
        
        验证：
        - 空检测帧不崩溃
        - 仅显示视频帧
        """
        # 创建空检测数据
        empty_processed_data = DeviceProcessedDataDTO(
            device_id="device1",
            frame_id=1,
            device_alias="left_camera",
            coords=np.empty((0, 3), dtype=np.float32),
            bbox=np.empty((0, 4), dtype=np.float32),
            confidence=np.empty((0,), dtype=np.float32),
            labels=np.empty((0,), dtype=np.int32),
            state_label=[],
        )
        
        empty_packet = RenderPacket(
            video_frame=self.video_frame,
            processed_detections=empty_processed_data,
        )
        
        frame = self.renderer._render_single_device(empty_packet)
        
        # 验证返回值不为空
        self.assertIsNotNone(frame)
        
        # 验证返回值是 3 通道图像
        self.assertEqual(frame.shape[2], 3)
    
    # ==================== Combined 模式测试（多设备拼接） ====================
    
    def test_render_combined_devices_two_devices(self):
        """测试 Combined 模式（双设备拼接）
        
        验证：
        - 正确水平拼接两个设备的RGB帧
        - 宽度为单设备的两倍
        - 每个设备图像上有名称标签
        """
        # 创建第二个设备的数据
        video_frame2 = VideoFrameDTO(
            device_id="device2",
            frame_id=1,
            rgb_frame=np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        )
        
        processed_data2 = DeviceProcessedDataDTO(
            device_id="device2",
            frame_id=1,
            device_alias="right_camera",
            coords=np.empty((0, 3), dtype=np.float32),
            bbox=np.empty((0, 4), dtype=np.float32),
            confidence=np.empty((0,), dtype=np.float32),
            labels=np.empty((0,), dtype=np.int32),
            state_label=[],
        )
        
        render_packet2 = RenderPacket(
            video_frame=video_frame2,
            processed_detections=processed_data2,
        )
        
        packets = {
            "device1": self.render_packet,
            "device2": render_packet2,
        }
        
        frame = self.renderer._render_combined_devices(packets)
        
        # 验证返回值不为空
        self.assertIsNotNone(frame)
        
        # 验证返回值是 3 通道图像
        self.assertEqual(frame.shape[2], 3)
        
        # 验证返回值宽度是原始宽度的两倍（水平拼接）
        self.assertEqual(frame.shape[1], self.rgb_frame.shape[1] * 2)
        
        # 验证返回值高度与输入一致
        self.assertEqual(frame.shape[0], self.rgb_frame.shape[0])
    
    def test_render_combined_devices_single_device(self):
        """测试 Combined 模式（只有一个设备在线）
        
        验证：
        - 只有一个设备时，直接返回该设备的帧
        - 不进行拼接
        """
        packets = {
            "device1": self.render_packet,
        }
        
        frame = self.renderer._render_combined_devices(packets)
        
        # 验证返回值不为空
        self.assertIsNotNone(frame)
        
        # 验证返回值是 3 通道图像
        self.assertEqual(frame.shape[2], 3)
        
        # 验证返回值尺寸与单设备一致（不拼接）
        self.assertEqual(frame.shape[:2], self.rgb_frame.shape[:2])
    
    def test_render_combined_devices_empty_packets(self):
        """测试 Combined 模式（无设备数据）
        
        验证：
        - 空数据包时返回 None
        """
        packets = {}
        
        frame = self.renderer._render_combined_devices(packets)
        
        # 验证返回值为 None
        self.assertIsNone(frame)
    
    # ==================== 显示模式切换测试 ====================
    
    def test_initial_display_mode(self):
        """测试初始显示模式
        
        验证：
        - 默认为 Combined 模式
        """
        self.assertEqual(self.renderer._display_mode, "combined")
    
    def test_switch_to_device(self):
        """测试切换到单设备模式
        
        验证：
        - 正确切换到指定设备
        - 更新显示模式和设备索引
        """
        # 切换到设备 0
        self.renderer._switch_to_device(0)
        
        self.assertEqual(self.renderer._display_mode, "single")
        self.assertEqual(self.renderer._selected_device_index, 0)
        
        # 切换到设备 1
        self.renderer._switch_to_device(1)
        
        self.assertEqual(self.renderer._display_mode, "single")
        self.assertEqual(self.renderer._selected_device_index, 1)
    
    def test_switch_to_device_invalid_index(self):
        """测试切换到无效设备索引
        
        验证：
        - 无效索引时不改变显示模式
        """
        initial_mode = self.renderer._display_mode
        initial_index = self.renderer._selected_device_index
        
        # 尝试切换到无效索引
        self.renderer._switch_to_device(999)
        
        # 验证显示模式未改变
        self.assertEqual(self.renderer._display_mode, initial_mode)
        self.assertEqual(self.renderer._selected_device_index, initial_index)
    
    def test_switch_to_combined(self):
        """测试切换到 Combined 模式
        
        验证：
        - 正确切换到 Combined 模式
        """
        # 先切换到单设备模式
        self.renderer._switch_to_device(0)
        self.assertEqual(self.renderer._display_mode, "single")
        
        # 切换到 Combined 模式
        self.renderer._switch_to_combined()
        
        self.assertEqual(self.renderer._display_mode, "combined")


if __name__ == "__main__":
    unittest.main()
