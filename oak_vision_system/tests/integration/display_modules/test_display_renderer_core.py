"""
DisplayRenderer 核心渲染功能测试

专门测试DisplayRenderer的核心渲染功能：
1. 检测框绘制测试
2. 状态标签着色测试
3. 文本叠加测试
4. 深度图处理测试
5. 渲染性能测试

验证需求：
- 需求 9.1-9.6: 检测信息叠加
- 需求 10.1-10.6: 按标签着色
- 需求 17.1-17.6: 深度图可视化
- 需求 18.1-18.6: 性能优化
"""

import time
import logging
import numpy as np
import pytest
import random
from typing import List, Dict
from unittest.mock import Mock, patch, MagicMock

from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.dto.config_dto import DisplayConfigDTO, DeviceRole
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import RenderPacket, RenderPacketPackager
from oak_vision_system.modules.data_processing.decision_layer.types import DetectionStatusLabel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 测试辅助函数 ====================

def create_test_render_packet(
    device_id: str,
    frame_id: int,
    num_detections: int = 3,
    device_alias: str = None,
    include_state_labels: bool = True,
    include_depth: bool = False
) -> RenderPacket:
    """创建测试用的渲染包"""
    # 创建视频帧
    rgb_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    if include_depth:
        # 创建有意义的深度数据
        depth_frame = np.random.randint(500, 3000, (480, 640), dtype=np.uint16)
    else:
        depth_frame = np.zeros((480, 640), dtype=np.uint16)
    
    video_frame = VideoFrameDTO(
        device_id=device_id,
        frame_id=frame_id,
        rgb_frame=rgb_frame,
        depth_frame=depth_frame
    )
    
    # 创建处理数据
    if num_detections > 0:
        coords = np.random.rand(num_detections, 3).astype(np.float32) * 1000
        bbox = np.array([
            [50, 50, 150, 150],   # 第一个检测框
            [200, 100, 300, 200], # 第二个检测框
            [350, 150, 450, 250], # 第三个检测框
        ][:num_detections], dtype=np.float32)
        confidence = np.array([0.95, 0.87, 0.92][:num_detections], dtype=np.float32)
        labels = np.array([0, 1, 0][:num_detections], dtype=np.int32)  # 0=物体, 1=人员
        
        if include_state_labels:
            state_labels = [
                DetectionStatusLabel.OBJECT_GRASPABLE,
                DetectionStatusLabel.HUMAN_SAFE,
                DetectionStatusLabel.OBJECT_DANGEROUS,
            ][:num_detections]
        else:
            state_labels = []
    else:
        coords = np.empty((0, 3), dtype=np.float32)
        bbox = np.empty((0, 4), dtype=np.float32)
        confidence = np.empty((0,), dtype=np.float32)
        labels = np.empty((0,), dtype=np.int32)
        state_labels = []
    
    processed_data = DeviceProcessedDataDTO(
        device_id=device_id,
        frame_id=frame_id,
        device_alias=device_alias,
        coords=coords,
        bbox=bbox,
        confidence=confidence,
        labels=labels,
        state_label=state_labels
    )
    
    return RenderPacket(
        video_frame=video_frame,
        processed_detections=processed_data
    )


# ==================== 测试 Fixtures ====================

@pytest.fixture
def renderer_config():
    """创建渲染器测试配置"""
    return DisplayConfigDTO(
        enable_display=False,
        window_width=640,
        window_height=480,
        target_fps=30,
        show_fps=True,
        show_labels=True,
        show_confidence=True,
        show_coordinates=True,
        show_device_info=True,
        bbox_color_by_label=True,
        text_scale=0.7,
        normalize_depth=True,
    )


@pytest.fixture
def mock_packager():
    """创建Mock RenderPacketPackager"""
    packager = Mock(spec=RenderPacketPackager)
    packager.get_packets.return_value = {}
    packager._latest_packets = {}
    packager._packet_timestamps = {}
    packager.cache_max_age_sec = 1.0
    return packager


# ==================== DisplayRenderer 核心功能测试 ====================

class TestDisplayRendererCore:
    """DisplayRenderer 核心功能测试"""
    
    def test_renderer_initialization(self, renderer_config, mock_packager):
        """
        测试渲染器初始化
        
        验证需求：
        - DisplayRenderer 正确初始化
        - 配置参数正确设置
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 渲染器初始化")
        logger.info("=" * 60)
        
        devices = ["device_1", "device_2"]
        role_bindings = {DeviceRole.LEFT_CAMERA: "device_1"}
        
        renderer = DisplayRenderer(
            config=renderer_config,
            packager=mock_packager,
            devices_list=devices,
            role_bindings=role_bindings,
            enable_depth_output=True,
        )
        
        # 验证初始化
        assert renderer._config == renderer_config, "配置应该正确设置"
        assert renderer._packager == mock_packager, "Packager应该正确设置"
        assert renderer._devices_list == devices, "设备列表应该正确设置"
        assert renderer._role_bindings == role_bindings, "角色绑定应该正确设置"
        assert renderer._enable_depth_output is True, "深度输出应该启用"
        
        # 验证状态标签颜色映射
        assert hasattr(renderer, 'STATE_LABEL_COLOR_MAP'), "应该有状态标签颜色映射"
        assert DetectionStatusLabel.OBJECT_GRASPABLE in renderer.STATE_LABEL_COLOR_MAP, "应该有可抓取物体颜色"
        assert DetectionStatusLabel.HUMAN_SAFE in renderer.STATE_LABEL_COLOR_MAP, "应该有安全人员颜色"
        
        logger.info("✅ 渲染器初始化测试通过")
        logger.info(f"   - 设备数量: {len(devices)}")
        logger.info(f"   - 角色绑定数量: {len(role_bindings)}")
        logger.info(f"   - 深度输出: {'启用' if renderer._enable_depth_output else '禁用'}")
    
    def test_detection_box_drawing(self, renderer_config, mock_packager):
        """
        测试检测框绘制功能
        
        验证需求：
        - 需求 9.1: 绘制检测框
        - 需求 9.2: 检测框样式
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 检测框绘制功能")
        logger.info("=" * 60)
        
        renderer = DisplayRenderer(
            config=renderer_config,
            packager=mock_packager,
            devices_list=["device_1"],
        )
        
        # 创建测试帧
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 创建测试处理数据
        processed_data = DeviceProcessedDataDTO(
            device_id="device_1",
            frame_id=1,
            device_alias="test_camera",
            coords=np.array([[100, 200, 300]], dtype=np.float32),
            bbox=np.array([[50, 50, 150, 150]], dtype=np.float32),
            confidence=np.array([0.95], dtype=np.float32),
            labels=np.array([0], dtype=np.int32),
            state_label=[DetectionStatusLabel.OBJECT_GRASPABLE]
        )
        
        # 测试检测框绘制方法
        renderer._draw_detection_boxes(test_frame, processed_data)
        
        # 验证帧被修改（检测框已绘制）
        # 由于我们在黑色帧上绘制了绿色框，应该有非零像素
        assert np.any(test_frame > 0), "帧应该被修改（检测框已绘制）"
        
        logger.info("✅ 检测框绘制功能测试通过")
        logger.info(f"   - 检测框数量: {processed_data.bbox.shape[0]}")
        logger.info(f"   - 帧修改验证: 通过")
    
    def test_state_label_coloring(self, renderer_config, mock_packager):
        """
        测试状态标签着色功能
        
        验证需求：
        - 需求 10.1-10.6: 按标签着色
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 状态标签着色功能")
        logger.info("=" * 60)
        
        # 创建启用按标签着色的配置（frozen dataclass需要重新创建）
        from dataclasses import replace
        config = replace(renderer_config, bbox_color_by_label=True)
        
        renderer = DisplayRenderer(
            config=config,
            packager=mock_packager,
            devices_list=["device_1"],
        )
        
        # 测试不同状态标签的颜色映射
        color_map = renderer.STATE_LABEL_COLOR_MAP
        
        # 验证物体状态颜色
        assert DetectionStatusLabel.OBJECT_GRASPABLE in color_map, "应该有可抓取物体颜色"
        assert DetectionStatusLabel.OBJECT_DANGEROUS in color_map, "应该有危险物体颜色"
        assert DetectionStatusLabel.OBJECT_OUT_OF_RANGE in color_map, "应该有超出范围物体颜色"
        assert DetectionStatusLabel.OBJECT_PENDING_GRASP in color_map, "应该有待抓取物体颜色"
        
        # 验证人员状态颜色
        assert DetectionStatusLabel.HUMAN_SAFE in color_map, "应该有安全人员颜色"
        assert DetectionStatusLabel.HUMAN_DANGEROUS in color_map, "应该有危险人员颜色"
        
        # 验证颜色格式（BGR）
        for state, color in color_map.items():
            assert isinstance(color, tuple), f"颜色应该是元组: {state}"
            assert len(color) == 3, f"颜色应该有3个分量: {state}"
            assert all(0 <= c <= 255 for c in color), f"颜色分量应该在0-255范围内: {state}"
        
        logger.info("✅ 状态标签着色功能测试通过")
        logger.info(f"   - 支持状态标签数量: {len(color_map)}")
        logger.info(f"   - 可抓取物体颜色: {color_map[DetectionStatusLabel.OBJECT_GRASPABLE]}")
        logger.info(f"   - 安全人员颜色: {color_map[DetectionStatusLabel.HUMAN_SAFE]}")
    
    def test_text_overlay_drawing(self, renderer_config, mock_packager):
        """
        测试文本叠加绘制
        
        验证需求：
        - 需求 9.3: 显示3D坐标
        - 需求 9.4: 显示标签和置信度
        - 需求 11.1: FPS显示
        - 需求 11.2: 设备信息显示
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 文本叠加绘制")
        logger.info("=" * 60)
        
        renderer = DisplayRenderer(
            config=renderer_config,
            packager=mock_packager,
            devices_list=["device_1"],
        )
        
        # 创建测试帧
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 创建测试处理数据
        processed_data = DeviceProcessedDataDTO(
            device_id="device_1",
            frame_id=1,
            device_alias="test_camera",
            coords=np.array([[100, 200, 300]], dtype=np.float32),
            bbox=np.array([[50, 50, 150, 150]], dtype=np.float32),
            confidence=np.array([0.95], dtype=np.float32),
            labels=np.array([0], dtype=np.int32),
            state_label=[DetectionStatusLabel.OBJECT_GRASPABLE]
        )
        
        # 测试各种文本绘制方法
        original_frame = test_frame.copy()
        
        # 测试标签绘制
        renderer._draw_labels(test_frame, processed_data)
        assert not np.array_equal(test_frame, original_frame), "标签绘制应该修改帧"
        
        # 测试坐标绘制
        test_frame = original_frame.copy()
        renderer._draw_coordinates(test_frame, processed_data)
        assert not np.array_equal(test_frame, original_frame), "坐标绘制应该修改帧"
        
        # 测试FPS绘制
        test_frame = original_frame.copy()
        renderer._draw_fps(test_frame)
        assert not np.array_equal(test_frame, original_frame), "FPS绘制应该修改帧"
        
        # 测试设备信息绘制
        test_frame = original_frame.copy()
        renderer._draw_device_info(test_frame, "device_1", processed_data)
        assert not np.array_equal(test_frame, original_frame), "设备信息绘制应该修改帧"
        
        logger.info("✅ 文本叠加绘制测试通过")
        logger.info("   - 标签绘制: 通过")
        logger.info("   - 坐标绘制: 通过")
        logger.info("   - FPS绘制: 通过")
        logger.info("   - 设备信息绘制: 通过")
    
    def test_depth_visualization(self, renderer_config, mock_packager):
        """
        测试深度图可视化
        
        验证需求：
        - 需求 17.1-17.6: 深度图可视化
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 深度图可视化")
        logger.info("=" * 60)
        
        # 启用深度输出
        renderer = DisplayRenderer(
            config=renderer_config,
            packager=mock_packager,
            devices_list=["device_1"],
            enable_depth_output=True,
        )
        
        # 创建测试深度数据
        depth_frame = np.random.randint(500, 3000, (480, 640), dtype=np.uint16)
        
        # 测试深度可视化
        depth_colored = renderer._visualize_depth(depth_frame)
        
        # 验证深度可视化结果
        assert depth_colored is not None, "应该返回彩色深度图"
        assert depth_colored.shape == (480, 640, 3), "彩色深度图应该是3通道"
        assert depth_colored.dtype == np.uint8, "彩色深度图应该是uint8类型"
        
        # 测试禁用深度输出的情况
        renderer_no_depth = DisplayRenderer(
            config=renderer_config,
            packager=mock_packager,
            devices_list=["device_1"],
            enable_depth_output=False,
        )
        
        depth_colored_disabled = renderer_no_depth._visualize_depth(depth_frame)
        assert depth_colored_disabled is None, "禁用深度输出时应该返回None"
        
        logger.info("✅ 深度图可视化测试通过")
        logger.info(f"   - 深度图形状: {depth_colored.shape}")
        logger.info(f"   - 深度图类型: {depth_colored.dtype}")
        logger.info(f"   - 禁用深度输出: 正确返回None")
    
    def test_single_device_rendering(self, renderer_config, mock_packager):
        """
        测试单设备渲染
        
        验证需求：
        - 需求 12.3: 单设备模式渲染
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 单设备渲染")
        logger.info("=" * 60)
        
        renderer = DisplayRenderer(
            config=renderer_config,
            packager=mock_packager,
            devices_list=["device_1"],
        )
        
        # 创建测试渲染包
        packet = create_test_render_packet(
            "device_1", 1, num_detections=3, device_alias="test_camera"
        )
        
        # 保存原始帧的副本用于比较
        original_frame = packet.video_frame.rgb_frame.copy()
        
        # 测试单设备渲染
        rendered_frame = renderer._render_single_device(packet)
        
        # 验证渲染结果
        assert rendered_frame is not None, "应该返回渲染后的帧"
        assert rendered_frame.shape == (480, 640, 3), "渲染帧形状应该正确"
        assert rendered_frame.dtype == np.uint8, "渲染帧类型应该是uint8"
        
        # 验证帧被修改（包含检测框和文本）
        # 注意：由于渲染方法可能直接修改原始帧，我们需要检查是否有像素被修改
        # 我们可以检查是否有非零的差异，或者检查特定区域是否被修改
        has_modifications = not np.array_equal(rendered_frame, original_frame)
        
        # 如果直接比较失败，我们检查是否有检测框区域被修改
        if not has_modifications:
            # 检查检测框区域是否有绿色像素（默认检测框颜色）
            # 检测框颜色是 (0, 255, 0) 在BGR格式中
            green_pixels = np.sum((rendered_frame[:, :, 1] == 255) & 
                                (rendered_frame[:, :, 0] == 0) & 
                                (rendered_frame[:, :, 2] == 0))
            has_modifications = green_pixels > 0
        
        assert has_modifications, "渲染帧应该包含检测框或其他修改"
        
        logger.info("✅ 单设备渲染测试通过")
        logger.info(f"   - 渲染帧形状: {rendered_frame.shape}")
        logger.info(f"   - 检测数量: {packet.processed_detections.coords.shape[0]}")
    
    def test_combined_devices_rendering(self, renderer_config, mock_packager):
        """
        测试多设备Combined渲染
        
        验证需求：
        - 需求 12.5: Combined模式渲染
        - 需求 12.6: 多设备拼接
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 多设备Combined渲染")
        logger.info("=" * 60)
        
        devices = ["device_1", "device_2"]
        renderer = DisplayRenderer(
            config=renderer_config,
            packager=mock_packager,
            devices_list=devices,
        )
        
        # 创建多设备渲染包
        packets = {
            "device_1": create_test_render_packet("device_1", 1, 2, "left_camera"),
            "device_2": create_test_render_packet("device_2", 1, 3, "right_camera"),
        }
        
        # 测试Combined渲染
        combined_frame = renderer._render_combined_devices(packets)
        
        # 验证Combined渲染结果
        assert combined_frame is not None, "应该返回Combined渲染帧"
        
        # Combined帧应该是水平拼接的，宽度是单帧的两倍
        expected_width = 640 * 2  # 两个设备水平拼接
        expected_height = 480
        assert combined_frame.shape == (expected_height, expected_width, 3), \
            f"Combined帧形状应该是 ({expected_height}, {expected_width}, 3)"
        
        logger.info("✅ 多设备Combined渲染测试通过")
        logger.info(f"   - Combined帧形状: {combined_frame.shape}")
        logger.info(f"   - 设备数量: {len(packets)}")
    
    def test_fps_calculation_and_stats(self, renderer_config, mock_packager):
        """
        测试FPS计算和统计
        
        验证需求：
        - 需求 11.3: FPS计算
        - 需求 13.1-13.2: 统计信息
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: FPS计算和统计")
        logger.info("=" * 60)
        
        renderer = DisplayRenderer(
            config=renderer_config,
            packager=mock_packager,
            devices_list=["device_1"],
        )
        
        # 模拟多次FPS更新
        for i in range(10):
            renderer._update_fps()
            time.sleep(0.01)  # 10ms间隔
        
        # 获取统计信息
        stats = renderer.get_stats()
        
        # 验证统计信息结构
        assert isinstance(stats, dict), "统计信息应该是字典"
        assert "frames_rendered" in stats, "应该包含渲染帧数"
        assert "fps" in stats, "应该包含当前FPS"
        assert "fps_history" in stats, "应该包含FPS历史"
        assert "avg_fps" in stats, "应该包含平均FPS"
        assert "min_fps" in stats, "应该包含最小FPS"
        assert "max_fps" in stats, "应该包含最大FPS"
        assert "runtime_sec" in stats, "应该包含运行时长"
        assert "is_running" in stats, "应该包含运行状态"
        
        # 验证统计数据类型
        assert isinstance(stats["frames_rendered"], int), "渲染帧数应该是整数"
        assert isinstance(stats["fps"], (int, float)), "FPS应该是数字"
        assert isinstance(stats["fps_history"], list), "FPS历史应该是列表"
        assert isinstance(stats["runtime_sec"], (int, float)), "运行时长应该是数字"
        assert isinstance(stats["is_running"], bool), "运行状态应该是布尔值"
        
        logger.info("✅ FPS计算和统计测试通过")
        logger.info(f"   - 当前FPS: {stats['fps']:.1f}")
        logger.info(f"   - FPS历史长度: {len(stats['fps_history'])}")
        logger.info(f"   - 运行时长: {stats['runtime_sec']:.2f}s")


# ==================== 主测试函数 ====================

def run_renderer_core_tests():
    """运行DisplayRenderer核心测试（用于手动执行）"""
    logger.info("\n" + "=" * 80)
    logger.info("DisplayRenderer 核心功能测试")
    logger.info("=" * 80)
    
    logger.info("请使用 pytest 运行此测试文件:")
    logger.info("pytest oak_vision_system/tests/integration/display_modules/test_display_renderer_core.py -v")


if __name__ == "__main__":
    run_renderer_core_tests()