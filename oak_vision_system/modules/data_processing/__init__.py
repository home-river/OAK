"""
数据处理模块

提供目标跟踪、空间滤波、坐标变换和决策层等功能。

主要组件：
- DataProcessor: 数据处理流水线的顶层协调组件
- DecisionLayer: 决策层模块，负责状态判断和全局决策
- Tracker: 目标跟踪匹配算法
- Filter: 空间坐标滤波器
- Transformer: 坐标变换工具
"""

# DataProcessor 相关
from .data_processor import DataProcessor

# DecisionLayer 相关
from .decision_layer import (
    DecisionLayer,
    states_to_labels,
    PersonWarningState,
    PersonWarningStatus,
    DetectionStatusLabel,
    DeviceState,
    GlobalTargetObject,
)

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
)

from .filterpool import FilterPool

# FilterManager 相关
from .filter_manager import FilterManager

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
    # DataProcessor
    "DataProcessor",
    # DecisionLayer
    "DecisionLayer",
    "states_to_labels",
    "PersonWarningState",
    "PersonWarningStatus",
    "DetectionStatusLabel",
    "DeviceState",
    "GlobalTargetObject",
    # Tracker
    "BaseTracker",
    "OptimizedGreedyTracker",
    "HungarianTracker",
    "IoUMatcher",
    "create_tracker",
    # Filter
    "BaseSpatialFilter",
    "MovingAverageFilter",
    "FilterPool",
    "FilterManager",
    # Transformer
    "CoordinateTransfomer",
    # Transform Utils
    "build_oak_to_xyz_homogeneous",
    "build_translation_homogeneous",
    "create_rotation_x_matrix",
    "create_rotation_y_matrix",
    "create_rotation_z_matrix",
]
