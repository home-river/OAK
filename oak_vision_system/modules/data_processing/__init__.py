"""
数据处理模块

提供目标跟踪、空间滤波和坐标变换等功能。

主要组件：
- Tracker: 目标跟踪匹配算法
- Filter: 空间坐标滤波器
- Transformer: 坐标变换工具
"""

# Tracker 相关
from .tracker import (
    BaseTracker,
    OptimizedGreedyTracker,
    HungarianTracker,
    IoUMatcher,  # 向后兼容别名
    create_tracker,
)

# Filter 相关
from .filter_base import (
    BaseSpatialFilter,
    MovingAverageFilter,
    WeightedMovingAverageFilter,
)

# Transform 相关
from .transform_module import CoordinateTransfomer

from .trans_utils import (
    build_oak_to_xyz_homogeneous,
    build_translation_homogeneous,
    create_rotation_x_matrix,
    create_rotation_y_matrix,
    create_rotation_z_matrix,
)

__all__ = [
    # Tracker
    "BaseTracker",
    "OptimizedGreedyTracker",
    "HungarianTracker",
    "IoUMatcher",
    "create_tracker",
    # Filter
    "BaseSpatialFilter",
    "MovingAverageFilter",
    "WeightedMovingAverageFilter",
    # Transformer
    "CoordinateTransfomer",
    # Transform Utils
    "build_oak_to_xyz_homogeneous",
    "build_translation_homogeneous",
    "create_rotation_x_matrix",
    "create_rotation_y_matrix",
    "create_rotation_z_matrix",
]

