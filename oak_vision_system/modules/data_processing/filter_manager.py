"""FilterManager 模块

FilterManager 是数据处理流水线中的核心协调组件，负责管理多个 FilterPool 实例，
并根据设备 ID 和标签对检测数据进行智能分发和处理。

设计特点：
1. 高性能：零运行时验证开销，使用 NumPy 向量化操作
2. 可扩展：支持多设备、多标签的灵活组合
3. 简洁接口：最小化依赖，只接受必要的配置参数
4. 自动管理：依赖 FilterPool 的自管理机制，无需手动重置
"""

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from oak_vision_system.core.dto.config_dto.device_binding_dto import DeviceMetadataDTO
from oak_vision_system.modules.data_processing.filter_base import (
    BaseSpatialFilter,
    MovingAverageFilter,
)
from oak_vision_system.modules.data_processing.filterpool import FilterPool
from oak_vision_system.modules.data_processing.tracker import BaseTracker, HungarianTracker


class FilterManager:
    """滤波器管理器
    
    管理多个 FilterPool 实例，按设备和标签分发检测数据。
    
    架构层次：
        FilterManager (协调层)
            ├─ 管理多个 FilterPool 实例
            ├─ 按设备和标签分发数据
            └─ 块状拼接输出结果
        
        FilterPool (池管理层)
            ├─ 管理多个 Filter 实例
            ├─ 使用 Tracker 进行目标匹配
            └─ 处理单个设备-标签组合
        
        BaseSpatialFilter (滤波层)
            └─ MovingAverageFilter
                └─ 滑动窗口平滑坐标
    
    使用示例：
        >>> device_metadata = {
        ...     "device_001": DeviceMetadataDTO(mxid="device_001", ...),
        ...     "device_002": DeviceMetadataDTO(mxid="device_002", ...),
        ... }
        >>> label_map = ["durian", "person"]
        >>> 
        >>> manager = FilterManager(
        ...     device_metadata=device_metadata,
        ...     label_map=label_map,
        ...     pool_size=32,
        ... )
        >>> 
        >>> # 处理数据
        >>> coords, bboxes, confs, labels = manager.process(
        ...     device_id="device_001",
        ...     coordinates=np.array([[1,2,3], [4,5,6]], dtype=np.float32),
        ...     bboxes=np.array([[0,0,10,10], [20,20,30,30]], dtype=np.float32),
        ...     confidences=np.array([0.9, 0.8], dtype=np.float32),
        ...     labels=np.array([0, 1], dtype=np.int32),
        ... )
    """
    
    def __init__(
        self,
        *,
        device_metadata: Dict[str, DeviceMetadataDTO],
        label_map: List[str],
        pool_size: int = 32,
        filter_factory: Optional[Callable[[], BaseSpatialFilter]] = None,
        tracker: Optional[BaseTracker] = None,
        iou_threshold: float = 0.5,
    ) -> None:
        """初始化 FilterManager
        
        Args:
            device_metadata: 设备元数据字典，映射 MXid 到 DeviceMetadataDTO
            label_map: 标签映射列表，定义所有检测类别
            pool_size: 每个 FilterPool 的大小（默认 32）
            filter_factory: 滤波器工厂函数（默认 MovingAverageFilter）
            tracker: 跟踪器实例（默认 HungarianTracker）
            iou_threshold: IoU 匹配阈值（默认 0.5）
        
        Raises:
            ValueError: 当配置参数无效时
        """
        # 验证配置参数
        self._validate_config(device_metadata, label_map, pool_size)
        
        # 存储配置参数
        self._device_ids: List[str] = list(device_metadata.keys())
        self._label_map: List[str] = label_map
        self._pool_size: int = pool_size
        self._filter_factory: Callable[[], BaseSpatialFilter] = (
            filter_factory if filter_factory is not None else lambda: MovingAverageFilter()
        )
        self._tracker: BaseTracker = (
            tracker if tracker is not None else HungarianTracker(iou_threshold=iou_threshold)
        )
        self._iou_threshold: float = iou_threshold
        
        # 预先创建所有 (device_id, label) 组合的 FilterPool 实例
        self._pools: Dict[Tuple[str, int], FilterPool] = {}
        self._create_all_pools()
    
    def _validate_config(
        self,
        device_metadata: Dict[str, DeviceMetadataDTO],
        label_map: List[str],
        pool_size: int,
    ) -> None:
        """验证配置参数
        
        Args:
            device_metadata: 设备元数据字典
            label_map: 标签映射列表
            pool_size: FilterPool 大小
        
        Raises:
            ValueError: 当配置参数无效时
        """
        # 验证 device_metadata
        if not device_metadata or len(device_metadata) == 0:
            raise ValueError("device_metadata 不能为 None 或空字典")
        
        # 验证 device_metadata 中的 MXid
        for mxid in device_metadata.keys():
            if not mxid or len(mxid) == 0:
                raise ValueError("device_metadata 中的 MXid 不能为空字符串")
        
        # 验证 label_map
        if not label_map or len(label_map) == 0:
            raise ValueError("label_map 不能为 None 或空列表")
        
        # 验证 pool_size
        if pool_size <= 0:
            raise ValueError("pool_size 必须大于 0")
    
    def _create_all_pools(self) -> None:
        """预先创建所有 (device_id, label) 组合的 FilterPool 实例
        
        为每个设备和标签组合创建一个独立的 FilterPool，
        避免运行时动态创建的开销。
        """
        for device_id in self._device_ids:
            for label_idx in range(len(self._label_map)):
                key = (device_id, label_idx)
                self._pools[key] = FilterPool(
                    pool_size=self._pool_size,
                    filter_factory=self._filter_factory,
                    tracker=self._tracker,
                    iou_threshold=self._iou_threshold,
                )
    
    def process(
        self,
        device_id: str,
        coordinates: np.ndarray,
        bboxes: np.ndarray,
        confidences: np.ndarray,
        labels: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """处理一帧检测数据
        
        Args:
            device_id: 设备 MXid
            coordinates: 坐标矩阵，形状 (n, 3)，dtype=float32
            bboxes: 边界框矩阵，形状 (n, 4)，dtype=float32
            confidences: 置信度数组，形状 (n,)，dtype=float32
            labels: 标签数组，形状 (n,)，dtype=int32
        
        Returns:
            Tuple[coordinates, bboxes, confidences, labels]:
                - coordinates: 滤波后的坐标矩阵，形状 (m, 3)，dtype=float32
                - bboxes: 对应的边界框矩阵，形状 (m, 4)，dtype=float32
                - confidences: 对应的置信度数组，形状 (m,)，dtype=float32
                - labels: 对应的标签数组，形状 (m,)，dtype=int32
        
        注意：
            - 不进行任何输入验证，假设调用方保证数据正确性
            - 使用 NumPy 向量化操作进行高效处理
        """
        # 处理空输入
        n = len(coordinates)
        if n == 0:
            return (
                np.empty((0, 3), dtype=np.float32),
                np.empty((0, 4), dtype=np.float32),
                np.empty((0,), dtype=np.float32),
                np.empty((0,), dtype=np.int32),
            )
        
        # 提取唯一标签
        unique_labels = np.unique(labels)
        
        # 收集所有 FilterPool 的输出
        output_coords_list: List[np.ndarray] = []
        output_bboxes_list: List[np.ndarray] = []
        output_confidences_list: List[np.ndarray] = []
        output_labels_list: List[np.ndarray] = []
        
        # 按标签分组处理
        for label in unique_labels:
            # 使用布尔索引提取该标签的数据
            mask = (labels == label)
            label_coords = coordinates[mask]
            label_bboxes = bboxes[mask]
            label_confidences = confidences[mask]
            
            # 获取对应的 FilterPool
            pool_key = (device_id, int(label))
            pool = self._pools.get(pool_key)
            
            if pool is None:
                # 如果没有对应的 FilterPool，跳过（不应该发生）
                continue
            
            # 调用 FilterPool 处理数据
            # step_v2 返回的坐标数组与输入长度相同（形状为 (n, 3)）
            filtered_coords = pool.step_v2(
                coordinates=label_coords,
                bboxes=label_bboxes,
                confidences=label_confidences,
            )
            
            # 收集输出
            # FilterPool.step_v2() 返回的数组长度与输入相同
            # 因此 filtered_coords、label_bboxes、label_confidences 长度一致
            if len(filtered_coords) > 0:
                output_coords_list.append(filtered_coords)
                output_bboxes_list.append(label_bboxes)
                output_confidences_list.append(label_confidences)
                # 为该标签的所有输出生成对应的 label 数组
                output_labels_list.append(np.full(len(filtered_coords), label, dtype=np.int32))
        
        # 块状拼接所有输出
        if len(output_coords_list) == 0:
            return (
                np.empty((0, 3), dtype=np.float32),
                np.empty((0, 4), dtype=np.float32),
                np.empty((0,), dtype=np.float32),
                np.empty((0,), dtype=np.int32),
            )
        
        result_coords = np.vstack(output_coords_list)
        result_bboxes = np.vstack(output_bboxes_list)
        result_confidences = np.concatenate(output_confidences_list)
        result_labels = np.concatenate(output_labels_list)
        
        return result_coords, result_bboxes, result_confidences, result_labels
    
    def get_pool_stats(self) -> Dict[Tuple[str, int], Dict[str, int]]:
        """获取所有滤波器池的统计信息
        
        Returns:
            字典格式: {(device_id, label): {"capacity": int, "active_count": int}}
        """
        stats: Dict[Tuple[str, int], Dict[str, int]] = {}
        
        for key, pool in self._pools.items():
            stats[key] = {
                "capacity": pool.capacity,
                "active_count": pool.active_count,
            }
        
        return stats
