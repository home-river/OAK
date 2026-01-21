"""
滤波器池设计

持有多个滤波器实例，接收对应的bbox矩阵和坐标变换矩阵，
使用tracker模块提供的算法计算索引，并注入对应的滤波器中
获得返回值并输出。
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

import numpy as np

from oak_vision_system.core.dto.detection_dto import DetectionDTO, SpatialCoordinatesDTO

from .filter_base import BaseSpatialFilter, MovingAverageFilter
from .tracker import BaseTracker, HungarianTracker, IoUMatcher


class FilterPool:
    def __init__(
        self,
        *,
        pool_size: int = 32,
        filter_factory: Optional[Callable[[], BaseSpatialFilter]] = None,
        tracker: Optional[BaseTracker] = None,
        iou_threshold: float = 0.5,
    ) -> None:
        """
        初始化滤波器池
        
        Args:
            pool_size: 滤波器池的大小
            filter_factory: 滤波器工厂函数，用于创建滤波器实例
            tracker: 匹配算法实例
            iou_threshold: IoU匹配阈值
        """
        if pool_size <= 0:
            raise ValueError("pool_size must be > 0")

        if filter_factory is None:
            filter_factory = lambda: MovingAverageFilter()  # 使用默认的滑动平均滤波器

        self._filters: list[BaseSpatialFilter] = [filter_factory() for _ in range(pool_size)]  # 预分配所有滤波器槽位
        self._active_mask: np.ndarray = np.zeros(pool_size, dtype=bool)  # 活跃状态掩码，True表示该槽位正在跟踪目标
        self._tracker: BaseTracker = tracker if tracker is not None else HungarianTracker(iou_threshold=iou_threshold)  # 匹配算法

    @property
    def active_mask(self) -> np.ndarray:
        """
        获取活跃状态掩码
        
        Returns:
            np.ndarray: 布尔数组，形状为(pool_size,)，True表示对应槽位的滤波器当前正在跟踪目标
        """
        return self._active_mask

    @property
    def capacity(self) -> int:
        """
        获取滤波器池容量（总槽位数）
        
        Returns:
            int: 预分配的滤波器槽位数量
        """
        return len(self._filters)

    @property
    def active_count(self) -> int:
        """
        获取当前活跃的滤波器数量
        
        Returns:
            int: 正在跟踪目标的滤波器数量
        """
        return int(self._active_mask.sum())

    def reset(self) -> None:
        """
        重置所有滤波器状态
        
        清空所有滤波器的内部状态，并将所有槽位标记为非活跃。
        用于系统重启或清空所有跟踪目标。
        """
        for f in self._filters:
            f.reset()
        self._active_mask[:] = False
    
    def get_active_indices(self) -> np.ndarray:
        """
        获取所有活跃的滤波器索引
        
        Returns:
            np.ndarray: 形状为(N,)的数组，每个元素为活跃滤波器的索引
        """
        return np.flatnonzero(self._active_mask)

    def get_bbox_matrix(self) -> np.ndarray:
        """
        获取所有活跃滤波器的bbox矩阵
        
        用于提取历史帧的bbox信息，供匹配算法使用。
        
        Returns:
            np.ndarray: 形状为(N, 4)的矩阵，每行为[x_min, y_min, x_max, y_max]
                       N为当前活跃的滤波器数量
        """
        
        _, boxes = self._active_candidates_and_boxes()  # 提取对应的bbox矩阵
        return boxes

    def step(
        self,
        coordinates: np.ndarray,
        bboxes: np.ndarray,
        confidences: np.ndarray,
    ) -> list[SpatialCoordinatesDTO]:
        """
        处理一帧检测结果
        
        args:
            coordinates: np.ndarray，坐标矩阵,形状为(n,3)
            bboxes: np.ndarray，bbox矩阵,形状为(n,4)
            confidences: np.ndarray，置信度数组,形状为(n,)，顺序与坐标矩阵和bbox矩阵一致
        return:
            list[SpatialCoordinatesDTO]，滤波后的坐标数据，顺序与坐标矩阵和bbox矩阵一致
        """
        # 参数验证和转换
        coordinates = np.asarray(coordinates, dtype=np.float32)  # 确保是numpy数组
        bboxes = np.asarray(bboxes, dtype=np.float32)  # 确保是numpy数组
        confidences = np.asarray(confidences, dtype=np.float32)  # 确保是numpy数组
        
        n = len(coordinates)
        if len(bboxes) != n or len(confidences) != n:
            raise ValueError(f"coordinates({n}), bboxes({len(bboxes)}), confidences({len(confidences)})长度必须一致")

        if n == 0:
            # 如果没有检测结果，只处理未匹配的滤波器
            active_indices = np.flatnonzero(self._active_mask)
            for slot_idx in active_indices.tolist():
                # 调用未匹配一帧方法miss_one
                self._active_mask[slot_idx] = self._filters[slot_idx].miss()
            # 清理失效的滤波器
            self._cleanup_inactive()
            return []

        # 获取活跃滤波器索引和历史帧bbox矩阵
        active_indices, prev_bboxes = self._active_candidates_and_boxes()  

        
        if len(prev_bboxes) == 0 or len(bboxes) == 0:
            matches: dict[int, int] = {}  # 没有历史或当前帧，无法匹配
        else:
            # 计算匹配关系
            matches, _ = self._tracker.match(prev_bboxes, bboxes)  # matches : {prev_local_idx: curr_idx}

        # 处理匹配的检测结果：输入到对应的滤波器中
        used_curr: set[int] = set()  # 已使用的当前帧检测索引
        matched_slots: set[int] = set()  # 已匹配的滤波器槽位索引
        candidates_len = len(active_indices)  # 在循环外计算活跃滤波器数量，避免重复调用
        # 循环获取本地索引和当前帧索引，并输入到对应的滤波器中
        for prev_local_idx, curr_idx in matches.items():

            slot_idx = int(active_indices[prev_local_idx])  # 获取滤波器索引

            # 根据索引得到对应的滤波器实例，并把最新的坐标和bbox输入到滤波器中
            self._filters[slot_idx].input(coordinates[curr_idx], bboxes[curr_idx])  

            used_curr.add(curr_idx)  # 标记该检测结果已使用
            matched_slots.add(slot_idx)  # 标记槽位已匹配

    
        
        # 处理未匹配的活跃滤波器：调用miss更新未匹配计数器
        for slot_idx in active_indices:
            slot_i = int(slot_idx)
            if slot_i in matched_slots:
                continue  # 已匹配的跳过
            self._active_mask[slot_i] = self._filters[slot_i].miss()  # 调用未匹配更新方法并更新掩码

        # 处理未匹配的检测结果：分配到空闲槽位（新目标）
        free_slots = [i for i in np.flatnonzero(~self._active_mask)]  # 获取空闲槽位
        for curr_idx in range(n):  # 处理未匹配的检测结果（新目标）
            if curr_idx in used_curr:
                continue  # 已匹配的跳过
            if not free_slots:
                break  # 没有空闲槽位，无法分配新目标
            slot_idx = free_slots.pop(0)  # 分配空闲槽位
            self._filters[slot_idx].reset()  # 重置滤波器状态
            self._filters[slot_idx].input(coordinates[curr_idx], bboxes[curr_idx])  # 输入新目标数据
            self._active_mask[slot_idx] = True  # 标记为活跃
        self._cleanup_inactive()  # 清理失效的滤波器

        # 收集所有活跃滤波器的输出
        outputs: list[SpatialCoordinatesDTO] = []
        for i in np.flatnonzero(self._active_mask):
            v = self._filters[i].current_value
            if v is not None:
                outputs.append(v)
        return outputs


    def step_v2(
        self,
        coordinates: np.ndarray,
        bboxes: np.ndarray,
        confidences: np.ndarray,
    ) -> np.ndarray:
        """
        处理一帧检测结果
        
        args:
            coordinates: np.ndarray，坐标矩阵,形状为(n,3)
            bboxes: np.ndarray，bbox矩阵,形状为(n,4)
            confidences: np.ndarray，置信度数组,形状为(n,)，顺序与坐标矩阵和bbox矩阵一致
        return:
            np.ndarray，滤波后的坐标数据，形状为(n,3)
        """
        
        # 参数验证和转换
        coordinates = np.asarray(coordinates, dtype=np.float32)  # 确保是numpy数组
        bboxes = np.asarray(bboxes, dtype=np.float32)  # 确保是numpy数组
        confidences = np.asarray(confidences, dtype=np.float32)  # 确保是numpy数组
        
        n = len(coordinates)
        if len(bboxes) != n or len(confidences) != n:
            raise ValueError(f"coordinates({n}), bboxes({len(bboxes)}), confidences({len(confidences)})长度必须一致")

        if n == 0:
            # 如果没有检测结果，只处理未匹配的滤波器
            active_indices = np.flatnonzero(self._active_mask)
            for slot_idx in active_indices.tolist():
                # 调用未匹配一帧方法miss_one
                self._active_mask[slot_idx] = self._filters[slot_idx].miss()
            # 清理失效的滤波器
            self._cleanup_inactive()
            return []

        # 预分配输出数组
        outputs: np.ndarray =  np.zeros((n,3), dtype=np.float32)
        # 获取活跃滤波器索引和历史帧bbox矩阵
        active_indices, prev_bboxes = self._active_candidates_and_boxes()
        active_set = set(active_indices)  

        
        if len(prev_bboxes) == 0 or len(bboxes) == 0:
            matches: dict[int, int] = {}  # 没有历史或当前帧，无法匹配
        else:
            # 计算匹配关系
            matches, _ = self._tracker.match(prev_bboxes, bboxes)  # matches : {prev_local_idx: curr_idx}

        # 处理匹配的检测结果：输入到对应的滤波器中
        used_curr: set[int] = set()  # 已使用的当前帧检测索引
        matched_slots: set[int] = set()  # 已匹配的滤波器槽位索引
        # 循环获取本地索引和当前帧索引，并输入到对应的滤波器中
        for prev_local_idx, curr_idx in matches.items():

            slot_idx = active_indices[prev_local_idx] # 获取滤波器索引

            # 根据索引得到对应的滤波器实例，并把最新的坐标和bbox输入到滤波器中,获取输出导入到对应位置
            outputs[curr_idx] = self._filters[slot_idx].input(coordinates[curr_idx], bboxes[curr_idx])  
        
            used_curr.add(curr_idx)  # 标记该检测结果已使用
            matched_slots.add(slot_idx)  # 标记槽位已匹配

        # 获取未匹配的活跃滤波器的槽位索引
        unused_slots = active_set - matched_slots
        # 遍历未匹配的活跃滤波器，调用miss方法更新mask
        for slot_idx in unused_slots:
            # miss方法会返回滤波器活跃状态，内部会自动判断是否清空滤波器数据
            self._active_mask[slot_idx] = self._filters[slot_idx].miss()


        # 处理未匹配的检测结果：分配到空闲槽位（新目标）
        free_slots = [i for i in np.flatnonzero(~self._active_mask)]  # 获取空闲槽位索引
        unmatched_idxs = set(range(n)) - used_curr
        if unmatched_idxs:
            for idx in unmatched_idxs:
                if not free_slots:
                    break  # 停止分配
                # 取出一个槽位用于输入数据
                slot = free_slots.pop(0)
                outputs[idx] = self._filters[slot].input(coordinates[idx],bboxes[idx])
                # 状态掩码标记为活跃
                self._active_mask[slot] = True
        return outputs


    def _cleanup_inactive(self) -> None:
        """
        清理失效的滤波器
        
        检查所有活跃的滤波器，如果其内部状态已完全清空
        （current_value为None且队列为空），则将其标记为非活跃。
        这样失效的槽位可以被后续的新目标复用。
        """
        for i in np.flatnonzero(self._active_mask):  # 遍历所有活跃滤波器
            fi = self._filters[int(i)]
            if fi.current_value is None and len(fi.queue) == 0:  # 如果内部状态已清空
                self._active_mask[int(i)] = False  # 标记为非活跃，槽位可被复用

    

    def _active_candidates_and_boxes(self) -> tuple[np.ndarray, np.ndarray]:
        """
        获取活跃滤波器的槽位索引和bbox矩阵
        
        Args:
            active_indices: np.ndarray，活跃滤波器索引
        Returns:
            tuple[np.ndarray, np.ndarray]，活跃滤波器索引和bbox矩阵
        """
        active_indices = np.flatnonzero(self._active_mask)
        if len(active_indices) == 0:
            return active_indices, np.empty((0, 4), dtype=np.float32)

        candidate_indices: list[int] = []
        boxes: list[np.ndarray] = []
        for idx in active_indices:
            fi = self._filters[int(idx)]
            cb = fi.current_bbox
            if cb is None:
                self._active_mask[int(idx)] = False
                continue
            candidate_indices.append(int(idx))
            boxes.append(np.asarray(cb, dtype=np.float32).reshape(4,))

        if not boxes:
            return np.asarray([], dtype=int), np.empty((0, 4), dtype=np.float32)

        bbox = np.stack(boxes, axis=0).astype(np.float32, copy=False)
        return np.asarray(candidate_indices, dtype=int), bbox


    @staticmethod
    def _bbox_to_list(bbox: object) -> list[float]:
        """
        将bbox转换为list[float]
        
        Args:
            bbox: object，bbox对象
        Returns:
            list[float]，bbox列表
        """
        return [float(bbox.xmin), float(bbox.ymin), float(bbox.xmax), float(bbox.ymax)]  # 转换为[x_min, y_min, x_max, y_max]格式

    @staticmethod
    def _boxes_from_detections(detections: Sequence[DetectionDTO]) -> np.ndarray:
        """
        从检测结果列表中提取bbox矩阵
        
        Args:
            detections: 检测结果列表
        
        Returns:
            np.ndarray: 形状为(N, 4)的矩阵，每行为[x_min, y_min, x_max, y_max]
                       如果detections为空，返回形状为(0, 4)的空矩阵
        """
        if not detections:
            return np.empty((0, 4), dtype=np.float32)  # 返回空矩阵
        return np.asarray([FilterPool._bbox_to_list(d.bbox) for d in detections], dtype=np.float32)  # 提取所有bbox并转换为矩阵

    @staticmethod
    def _values_from_detections(detections: Sequence[DetectionDTO]) -> np.ndarray:
        """
        从检测结果列表中提取坐标值矩阵
        
        Args:
            detections: 检测结果列表
        
        Returns:
            np.ndarray: 形状为(N, 3)的矩阵，每行为[x, y, z]
                       如果detections为空，返回形状为(0, 3)的空矩阵
        """
        if not detections:
            return np.empty((0, 3), dtype=np.float32)  # 返回空矩阵
        return np.asarray(
            [
                [
                    float(d.spatial_coordinates.x),
                    float(d.spatial_coordinates.y),
                    float(d.spatial_coordinates.z),
                ]
                for d in detections
            ],
            dtype=np.float32,  # 提取所有坐标值并转换为矩阵，形状为(N, 3)
        )