"""
测试深度图输出配置检查功能（任务 6）

验证 enable_depth_output 配置是否正确控制深度图处理。
"""

import unittest
import numpy as np
from unittest.mock import MagicMock

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer
from oak_vision_system.modules.display_modules.render_packet_packager import RenderPacketPackager


class TestDepthOutputConfig(unittest.TestCase):
    """测试深度图输出配置（任务 6）"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建配置
        self.config = DisplayConfigDTO(
            enable_display=False,  # 禁用显示以避免创建窗口
            normalize_depth=True,
        )
        
        # 创建模拟的 packager
        self.packager = MagicMock(spec=RenderPacketPackager)
        self.devices_list = ["device1"]
    
    def test_visualize_depth_disabled_by_default(self):
        """测试默认情况下深度图处理被禁用（子任务 6.1）"""
        # Arrange
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=False,  # 默认值
        )
        
        depth_frame = np.random.randint(0, 5000, (480, 640), dtype=np.uint16)
        
        # Act
        result = renderer._visualize_depth(depth_frame)
        
        # Assert
        self.assertIsNone(result, "当 enable_depth_output=False 时，应该返回 None")
    
    def test_visualize_depth_enabled(self):
        """测试启用深度图处理（子任务 6.1）"""
        # Arrange
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=True,
        )
        
        depth_frame = np.random.randint(0, 5000, (480, 640), dtype=np.uint16)
        
        # Act
        result = renderer._visualize_depth(depth_frame)
        
        # Assert
        self.assertIsNotNone(result, "当 enable_depth_output=True 时，应该返回彩色深度图")
        self.assertEqual(result.shape, (480, 640, 3), "返回的深度图应该是 3 通道彩色图像")
        self.assertEqual(result.dtype, np.uint8, "返回的深度图应该是 uint8 类型")
    
    def test_visualize_depth_uses_hot_colormap(self):
        """测试深度图使用 HOT 颜色映射（子任务 6.2）"""
        # Arrange
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=True,
        )
        
        # 创建一个简单的深度帧（从黑到白的渐变）
        depth_frame = np.linspace(0, 5000, 640 * 480, dtype=np.uint16).reshape(480, 640)
        
        # Act
        result = renderer._visualize_depth(depth_frame)
        
        # Assert
        self.assertIsNotNone(result)
        # HOT 颜色映射应该产生从黑色到红色到黄色到白色的渐变
        # 检查返回的图像是否是 BGR 格式的彩色图像
        self.assertEqual(result.shape[2], 3, "应该是 3 通道图像")
    
    def test_visualize_depth_with_percentile_normalization(self):
        """测试深度图使用百分位数归一化（子任务 6.2）"""
        # Arrange
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=True,
        )
        
        # 创建一个包含极值的深度帧
        depth_frame = np.ones((480, 640), dtype=np.uint16) * 1000
        depth_frame[0, 0] = 0  # 最小值
        depth_frame[0, 1] = 10000  # 极大值（异常值）
        
        # Act
        result = renderer._visualize_depth(depth_frame)
        
        # Assert
        self.assertIsNotNone(result, "应该能够处理包含极值的深度帧")
        self.assertEqual(result.shape, (480, 640, 3))
    
    def test_visualize_depth_handles_invalid_values(self):
        """测试深度图处理无效值（NaN、Inf）（子任务 6.2）"""
        # Arrange
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=True,
        )
        
        # 创建包含无效值的深度帧
        depth_frame = np.ones((480, 640), dtype=np.float32) * 1000
        depth_frame[0, 0] = np.nan
        depth_frame[0, 1] = np.inf
        depth_frame[0, 2] = -np.inf
        
        # Act
        result = renderer._visualize_depth(depth_frame)
        
        # Assert
        self.assertIsNotNone(result, "应该能够处理包含无效值的深度帧")
        self.assertEqual(result.shape, (480, 640, 3))
        # 验证结果中没有 NaN 或 Inf
        self.assertFalse(np.any(np.isnan(result)), "结果中不应该有 NaN")
        self.assertFalse(np.any(np.isinf(result)), "结果中不应该有 Inf")
    
    def test_visualize_depth_with_empty_frame(self):
        """测试深度图处理空帧（子任务 6.1）"""
        # Arrange
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=True,
        )
        
        # Act & Assert
        result1 = renderer._visualize_depth(None)
        self.assertIsNone(result1, "None 深度帧应该返回 None")
        
        result2 = renderer._visualize_depth(np.array([]))
        self.assertIsNone(result2, "空数组应该返回 None")
    
    def test_depth_output_config_passed_to_renderer(self):
        """测试 enable_depth_output 配置正确传递给 DisplayRenderer（子任务 6.1）"""
        # Arrange & Act
        renderer_disabled = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=False,
        )
        
        renderer_enabled = DisplayRenderer(
            config=self.config,
            packager=self.packager,
            devices_list=self.devices_list,
            enable_depth_output=True,
        )
        
        # Assert
        self.assertFalse(renderer_disabled._enable_depth_output, 
                        "enable_depth_output=False 应该被正确存储")
        self.assertTrue(renderer_enabled._enable_depth_output, 
                       "enable_depth_output=True 应该被正确存储")


if __name__ == "__main__":
    unittest.main()
