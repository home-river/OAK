from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from collections import deque

from oak_vision_system.core.dto.detection_dto import SpatialCoordinatesDTO, BoundingBoxDTO

import numpy as np
Coord3 = tuple[float, float, float]


class BaseSpatialFilter(ABC):
    """
    自定义滤波器基类
    规定了滤波器的基本功能接口
    """
    
    def __init__(self, *, queue_maxsize: int = 8, max_missed_count: int = 5) -> None:
        """初始化滤波器基类
        
        Args:
            queue_maxsize: 历史数据队列的最大容量
        """
        # 使用 deque 自动处理溢出（单线程场景性能更好）
        self._queue: deque[Coord3] = deque(maxlen=queue_maxsize)
        self._maxsize: int = queue_maxsize
        
        # 当前滤波结果
        self._current_value: Optional[SpatialCoordinatesDTO] = None

        
        # IOU 信息
        self._current_bbox: Optional[BoundingBoxDTO] = None

        # 生命周期
        self._missed_count: int = 0
        self._max_missed_count: int = max_missed_count

    @property
    def queue(self) -> deque[Coord3]:
        """历史数据队列"""
        return self._queue
    
    @property
    def maxsize(self) -> int:
        """队列最大容量"""
        return self._maxsize

    @property
    def current_value(self) -> Optional[SpatialCoordinatesDTO]:
        """当前滤波结果"""
        return self._current_value

    @property
    def current_bbox(self) -> Optional[BoundingBoxDTO]:
        """bbox 信息"""
        return self._current_bbox

    def predict(self) -> Optional[SpatialCoordinatesDTO]:
        """获取滤波结果 - 直接返回内部属性（性能优化）"""
        # 未匹配计数器自增
        self._missed_count +=1

        # 如果未匹配计数器大于最大未匹配计数，则返回None
        if self._missed_count > self._max_missed_count:
            # 清空内部状态
            self.reset()
            return None

        # 返回当前滤波结果
        return self._current_value

    def is_valid(self) -> bool:
        """
        
        检查滤波器是否有效
        
        Returns:
            True: 滤波器有效
            False: 滤波器无效(长时间无有效数据输入,内部状态清空)
        """
        return self._missed_count <= self._max_missed_count

    def input(
        self, 
        values: np.ndarray, 
        iou_info: Optional[BoundingBoxDTO] = None
    ) -> Optional[SpatialCoordinatesDTO]:
        """
        输入新的空间坐标值和 (可选的) IOU 信息，处理滤波逻辑,并重置未匹配计数器。

        Args:
            value: 新的空间坐标数据
            iou_info: 相关的 IOU 或边界框信息，默认为 None

        Returns:
            当前的滤波结果
        """
        # 重置未匹配计数器
        self._missed_count = 0

        coord: Coord3 = (float(values[0]), float(values[1]), float(values[2]))

        old_value: Optional[Coord3] = None
        if len(self._queue) == self._maxsize:
            old_value = self._queue[0]

        # deque 会自动处理溢出（移除最旧元素）
        self._queue.append(coord)
        
        # 保存当前的 IOU 信息
        self._current_bbox = iou_info
        
        # 更新内部状态（由子类实现具体滤波逻辑）
        self._update_state(coord, iou_info, old_value)
        
        # 返回最新滤波结果（直接访问内部属性）
        return self._current_value

    @abstractmethod
    def _update_state(
        self, 
        value: Coord3, 
        iou_info: Optional[BoundingBoxDTO],
        old_value: Optional[Coord3]
    ) -> None:
        """更新滤波器内部状态（子类实现）"""
        ...

    def reset(self) -> None:
        """重置滤波器状态"""
        self._queue.clear()
        self._current_value = None
        self._current_coord = None
        self._current_bbox = None
        self._missed_count = 0


class MovingAverageFilter(BaseSpatialFilter):
    """
    滑动平均滤波器
     
    """
    
    def __init__(
        self, 
        *, 
        queue_maxsize: int = 8,
        recalc_interval: int = 10,
        max_missed_count: int = 5
    ) -> None:
        """初始化滑动平均滤波器
        
        Args:
            queue_maxsize: 滑动窗口大小，值越大平滑效果越强但延迟越大
            recalc_interval: 重新计算间隔倍数，实际间隔 = queue_maxsize * recalc_interval
        """
        super().__init__(queue_maxsize=queue_maxsize, max_missed_count=max_missed_count)
        
        # 维护三个轴的累加和（递推优化）
        self._sum_x: float = 0.0
        self._sum_y: float = 0.0
        self._sum_z: float = 0.0
        
        # 手动维护当前窗口大小（避免 len() 调用）
        self._size: int = 0
        
        # 更新计数器（用于定期重算）
        self._update_count: int = 0
        self._recalc_interval: int = queue_maxsize * recalc_interval
    
    def _update_state(
        self, 
        value: Coord3, 
        iou_info: Optional[BoundingBoxDTO] = None,
        old_value: Optional[Coord3] = None
    ) -> None:
        """更新滤波状态 - 使用递推公式 O(1) 复杂度"""
        # 如果队列为空，重置状态
        if not self._queue:
            self._current_value = None
            self._size = 0
            self._sum_x = self._sum_y = self._sum_z = 0.0
            return
        
        self._update_count += 1
        
        # 定期重新精确计算（防止浮点误差累积）
        if self._update_count % self._recalc_interval == 0:
            self._sum_x = sum(coord[0] for coord in self._queue)
            self._sum_y = sum(coord[1] for coord in self._queue)
            self._sum_z = sum(coord[2] for coord in self._queue)
            self._size = len(self._queue)
        else:
            # 递推更新（快速路径）
            # 如果窗口已满，减去被移除的旧值
            if self._size == self._maxsize:
                if old_value is not None:
                    self._sum_x -= old_value[0]
                    self._sum_y -= old_value[1]
                    self._sum_z -= old_value[2]
            else:
                # 窗口未满，递增大小
                self._size += 1
            
            # 加上新值
            self._sum_x += value[0]
            self._sum_y += value[1]
            self._sum_z += value[2]
        
        # O(1) 计算平均值（使用内部维护的大小）
        self._current_coord = (
            self._sum_x / self._size,
            self._sum_y / self._size,
            self._sum_z / self._size,
        )
        self._current_value = SpatialCoordinatesDTO(
            x=self._current_coord[0],
            y=self._current_coord[1],
            z=self._current_coord[2]
        )
    
    def reset(self) -> None:
        """重置滤波器状态"""
        super().reset()
        self._sum_x = 0.0
        self._sum_y = 0.0
        self._sum_z = 0.0
        self._size = 0
        self._update_count = 0
    
    def is_warmed_up(self) -> bool:
        """检查滤波器是否已预热（窗口填满）"""
        return self._size == self._maxsize


class WeightedMovingAverageFilter(BaseSpatialFilter):
    """加权滑动平均滤波器
    
    对最近的数据赋予更高权重，使滤波器对新数据更敏感。
    
    特点：
    - 最近数据权重更大（线性递增）
    - 响应速度比简单平均更快
    - 适合需要快速跟踪变化的场景
    
    注意：
    - 此实现未使用递推优化（加权平均的递推较复杂）
    - 对于小窗口（<20）性能仍可接受
    """
    
    def __init__(self, *, queue_maxsize: int = 8, max_missed_count: int = 5) -> None:
        """初始化加权滑动平均滤波器
        
        Args:
            queue_maxsize: 滑动窗口大小
        """
        super().__init__(queue_maxsize=queue_maxsize, max_missed_count=max_missed_count)
        # 预计算权重（线性递增）
        self._weights = self._compute_weights(queue_maxsize)
    
    @staticmethod
    def _compute_weights(n: int) -> list[float]:
        """计算归一化的线性递增权重"""
        import numpy as np
        weights = np.arange(1, n + 1, dtype=np.float32)
        weights = weights / weights.sum()
        return weights.tolist()
    
    def _update_state(
        self, 
        value: Coord3, 
        iou_info: Optional[BoundingBoxDTO] = None,
        old_value: Optional[Coord3] = None
    ) -> None:
        """更新滤波状态 - 使用线性递增权重计算加权平均"""
        if not self._queue:
            self._current_value = None
            return
        
        # 根据实际队列长度调整权重
        n = len(self._queue)
        if n != len(self._weights):
            weights = self._compute_weights(n)
        else:
            weights = self._weights
        
        # 提取坐标并计算加权平均
        avg_x = sum(coord[0] * w for coord, w in zip(self._queue, weights))
        avg_y = sum(coord[1] * w for coord, w in zip(self._queue, weights))
        avg_z = sum(coord[2] * w for coord, w in zip(self._queue, weights))
        
        self._current_coord = (avg_x, avg_y, avg_z)
        self._current_value = SpatialCoordinatesDTO(
            x=self._current_coord[0],
            y=self._current_coord[1],
            z=self._current_coord[2]
        )
