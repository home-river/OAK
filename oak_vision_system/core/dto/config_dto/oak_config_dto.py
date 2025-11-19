"""
OAK模块配置DTO

管理OAK设备硬件及DepthAI Pipeline的配置。
职责明确，与display、data_processing等模块平级。

配置范围：
- 检测模型配置
- 相机硬件参数  
- 深度计算参数
- Pipeline队列配置（OAK设备输出队列）

不包括：
- 显示相关配置（由DisplayConfigDTO负责）
- 数据处理配置（由DataProcessingConfigDTO负责）
- 应用层配置（由SystemConfigDTO负责）
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import os

from ..base_dto import validate_string_length, validate_numeric_range
from .base_config_dto import BaseConfigDTO
import depthai as dai

# 模块内维护的默认标签与中值滤波核大小（提取自 DTO 外部）
DEFAULT_LABEL_MAP: tuple[str, ...] = ("durian", "person")
MEDIAN_FILTER_KERNEL_SIZES: tuple[int, ...] = (3, 5, 7)


@dataclass(frozen=True)
class OAKConfigDTO(BaseConfigDTO):
    """
    OAK硬件与Pipeline配置
    
    职责：
    - 检测模型配置
    - 相机硬件参数
    - 深度计算参数
    - Pipeline队列配置（OAK设备输出队列）
    
    注意：
    - 这里的queue配置是OAK DepthAI pipeline的输出队列
    - 显示相关配置在 DisplayConfigDTO
    - 数据处理配置在 DataProcessingConfigDTO
    - 应用层配置在 SystemConfigDTO
    """
    
    # ========== 检测模型配置 ==========
    model_path: Optional[str] = None
    label_map: List[str] = field(default_factory=lambda: list(DEFAULT_LABEL_MAP))
    num_classes: int = 2
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.4
    max_detections: int = -1  # -1表示不限制
    
    # ========== 相机硬件配置 ==========
    # RGB相机
    rgb_resolution: Tuple[int, int] = (1920, 1080)  # 相机实际分辨率
    preview_resolution: Tuple[int, int] = (640, 480)  # 预览分辨率
    hardware_fps: int = 20  # 硬件帧率
    
    # 连接模式
    usb2_mode: bool = True  # USB2模式（兼容性好但带宽受限）
    
    # ========== 深度计算配置 ==========
    # 深度感知参数
    enable_depth: bool = False  # 是否启用深度图绘制功能
    depth_resolution: Tuple[int, int] = (640, 400)  # 深度图分辨率，深度相机分辨率
    depth_min_threshold: float = 400.0   # 最小有效深度(mm)
    depth_max_threshold: float = 6000.0  # 最大有效深度(mm)
    
    # 深度对齐
    align_depth_to_rgb: bool = True  # 深度图对齐到RGB
    
    # 立体匹配参数
    median_filter: int = 5  # 中值滤波核大小 (3/5/7)
    left_right_check: bool = True  # 左右一致性检查
    extended_disparity: bool = False  # 扩展视差范围（近距离检测）
    subpixel: bool = False  # 亚像素精度（提升精度但降低性能）
    
    # ========== Pipeline队列配置 ==========
    # OAK设备输出队列的配置
    queue_max_size: int = 4  # 输出队列最大长度
    queue_blocking: bool = False  # 队列满时是否阻塞
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        # 模型配置验证
        if self.model_path is not None:
            errors.extend(validate_string_length(
                self.model_path, 'model_path', min_length=1, max_length=500
            ))
            # 文件存在性校验
            if not os.path.isfile(self.model_path):
                errors.append("model_path指向的模型文件不存在或不可读")
        
        # 标签映射配置验证
        if not isinstance(self.label_map, list):
            errors.append("label_map必须为列表类型")
        elif len(self.label_map) == 0:
            errors.append("label_map不能为空列表")
        
        # 类别数量与标签映射长度一致性验证
        # 类别数量需与标签映射长度一致
        if isinstance(self.label_map, list) and len(self.label_map) > 0:
            if self.num_classes != len(self.label_map):
                errors.append(f"num_classes必须等于label_map长度({len(self.label_map)})")
        
        # 置信度阈值配置验证
        errors.extend(validate_numeric_range(
            self.confidence_threshold, 'confidence_threshold',
            min_value=0.0, max_value=1.0
        ))
        
        # NMS阈值配置验证
        errors.extend(validate_numeric_range(
            self.nms_threshold, 'nms_threshold',
            min_value=0.0, max_value=1.0
        ))
        
        # 硬件帧率配置验证
        errors.extend(validate_numeric_range(
            self.hardware_fps, 'hardware_fps',
            min_value=1, max_value=120
        ))
        
        # 深度阈值配置验证
        if self.depth_min_threshold >= self.depth_max_threshold:
            errors.append("depth_min_threshold必须小于depth_max_threshold")
        
        # 中值滤波核大小配置验证
        if self.median_filter not in MEDIAN_FILTER_KERNEL_SIZES:
            errors.append("median_filter必须为3、5或7")
        
        # Pipeline队列配置验证
        errors.extend(validate_numeric_range(
            self.queue_max_size, 'queue_max_size', min_value=1, max_value=30
        ))
        
        return errors
