"""
显示模块配置DTO

管理所有与图像显示、UI渲染相关的配置。
"""

from dataclasses import dataclass
from typing import List, Tuple

from ..base_dto import validate_numeric_range
from .base_config_dto import BaseConfigDTO  


# 模块内维护的显示相关白名单（提取自 DTO 外部）
DISPLAY_MODES: tuple[str, ...] = ("rgb", "depth", "combined", "side_by_side")
DEPTH_COLORMAPS: tuple[str, ...] = ("JET", "RAINBOW", "BONE", "TURBO", "HOT", "COOL")


@dataclass(frozen=True)
class DisplayConfigDTO(BaseConfigDTO):
    """
    显示模块配置
    
    职责：
    - 窗口显示模式
    - 渲染参数
    - 叠加信息显示
    - 深度图显示样式
    """
    
    # ========== 显示开关 ==========
    enable_display: bool = True  # 是否启用图像显示
    
    # ========== 窗口配置 ==========
    default_display_mode: str = "combined"  # "rgb"/"depth"/"combined"/"side_by_side"
    enable_fullscreen: bool = False
    window_width: int = 1280
    window_height: int = 720
    window_position_x: int = 0  # 窗口初始位置
    window_position_y: int = 0
    
    # ========== 渲染参数 ==========
    target_fps: int = 20  # 目标显示帧率（可能低于硬件帧率以节省资源）
    enable_vsync: bool = False  # 垂直同步
    
    # ========== 叠加信息 ==========
    show_detection_boxes: bool = True  # 显示检测框
    show_labels: bool = True  # 显示标签
    show_confidence: bool = True  # 显示置信度
    show_coordinates: bool = True  # 显示3D坐标
    show_fps: bool = True  # 显示帧率
    show_device_info: bool = True  # 显示设备信息
    
    # ========== 深度图显示 ==========
    depth_colormap: str = "JET"  # 深度图颜色映射 (JET/RAINBOW/BONE等)
    depth_alpha: float = 0.6  # 深度图叠加透明度(0-1)
    normalize_depth: bool = True  # 归一化深度图显示
    
    # ========== 检测框样式 ==========
    bbox_thickness: int = 2  # 边框粗细
    bbox_color_by_label: bool = True  # 按标签着色
    text_scale: float = 0.6  # 文字大小
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        # 显示模式验证
        if self.default_display_mode not in DISPLAY_MODES:
            errors.append(f"default_display_mode必须为: {'/'.join(DISPLAY_MODES)}")
        
        # 窗口参数验证
        errors.extend(validate_numeric_range(
            self.window_width, 'window_width', min_value=320, max_value=3840
        ))
        errors.extend(validate_numeric_range(
            self.window_height, 'window_height', min_value=240, max_value=2160
        ))
        errors.extend(validate_numeric_range(
            self.target_fps, 'target_fps', min_value=1, max_value=120
        ))
        
        # 深度图参数验证
        errors.extend(validate_numeric_range(
            self.depth_alpha, 'depth_alpha', min_value=0.0, max_value=1.0
        ))
        
        if self.depth_colormap not in DEPTH_COLORMAPS:
            errors.append(f"depth_colormap必须为: {'/'.join(DEPTH_COLORMAPS)}")
        
        # 检测框样式验证
        errors.extend(validate_numeric_range(
            self.bbox_thickness, 'bbox_thickness', min_value=1, max_value=10
        ))
        errors.extend(validate_numeric_range(
            self.text_scale, 'text_scale', min_value=0.3, max_value=2.0
        ))
        
        return errors
