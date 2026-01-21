"""空间滤波器模块

提供多种空间坐标滤波器实现，用于平滑和稳定三维坐标数据。
"""

from abc import ABC, abstractmethod
from collections import deque
from typing import Optional

import numpy as np




class BaseSpatialFilter(ABC):
    """空间滤波器的基类"""
    
    # 添加 __slots__ 减少内存占用
    __slots__ = ('_current_value', '_current_bbox', '_missed_count', '_max_missed_count','active_state')
    
    def __init__(self, *, max_missed_count: int = 5) -> None:
        # 预分配 NumPy 数组（原地修改的基础）
        self._current_value = np.zeros(3, dtype=np.float32)
        self._current_bbox: Optional[np.ndarray] = None
        self._missed_count = 0
        self._max_missed_count = max_missed_count
        self.active_state: bool = False

    @abstractmethod
    def input(
        self, values: np.ndarray, iou_info: np.ndarray,
    ) -> Optional[np.ndarray]:
        """输入新的坐标值
        
        Args:
            values: 输入的坐标数组，至少包含3个元素 [x, y, z]
            iou_info: 边界框信息
            
        Returns:
            过滤后的坐标值，如果滤波器失效则返回 None
        """

    def miss(self) -> bool:
        """处理丢失的检测
        
        当检测丢失时调用，增加丢失计数。如果连续丢失次数超过阈值，
        滤波器将失效并返回 False。
        
        Returns:
            bool: 当前的过滤值，如果失效则返回 False
        """
        self._missed_count += 1
        if self._missed_count >= self._max_missed_count:
            self.active_state = False
            self.reset()
            return self.active_state
        
        return self.active_state

    def reset(self) -> None:
        """重置滤波器状态
        
        清空所有历史数据和状态，将滤波器恢复到初始状态。
        """
        # 原地清零（避免创建新对象）
        self._current_value[:] = 0.0
        self._current_bbox = None
        self._missed_count = 0
        self.active_state = False

    @property
    def current_value(self) -> Optional[np.ndarray]:
        """获取当前过滤后的坐标值
        
        Returns:
            当前的过滤坐标值，如果滤波器失效则返回 None
        """
        # 如果没有有效值，返回 None
        if self._missed_count >= self._max_missed_count:
            return None
        return self._current_value

    @property
    def current_bbox(self) -> Optional[np.ndarray]:
        """获取当前的边界框信息
        
        Returns:
            当前的边界框数组，如果没有则返回 None
        """
        return self._current_bbox


class MovingAverageFilter(BaseSpatialFilter):
    """移动平均滤波器
    
    使用滑动窗口计算坐标的移动平均值，适用于需要平滑处理的场景。
    使用增量更新算法，时间复杂度为 O(1)。
    
    Attributes:
        _queue: 存储历史坐标的队列
        _recalc_interval: 重新计算总和的间隔
        _next_recalc: 距离下次重算的计数器
        _queue_maxsize: 队列的最大大小
        active_state: 滤波器是否激活
    """
    
    __slots__ = ('_queue', '_recalc_interval', '_next_recalc','active_state','_queue_maxsize')
    
    def __init__(self, *, queue_maxsize: int = 8, max_missed_count: int = 5) -> None:
        """初始化移动平均滤波器
        
        Args:
            queue_maxsize: 滑动窗口的最大大小
            max_missed_count: 允许的最大连续丢失次数
        """
        super().__init__(max_missed_count=max_missed_count)
        self._queue: deque[np.ndarray] = deque(maxlen=queue_maxsize)
        self._queue_maxsize = queue_maxsize
        
        
        
        # 定期重新计算总和以消除浮点误差累积
        self._recalc_interval = max(queue_maxsize * 2, 10)

        # 使用计数器替代取余操作
        self._next_recalc = self._recalc_interval

        # 初始化时滤波器未激活
        self.active_state = False
    def input(
        self, values: np.ndarray, iou_info: np.ndarray,
    ) -> Optional[np.ndarray]:
        """输入新的坐标值并返回过滤结果
        
        Args:
            values: 输入的坐标数组 [x, y, z, ...]
            iou_info: 边界框信息
            
        Returns:
            过滤后的坐标值
        """
        self._missed_count = 0
        self.active_state = True
        
        # 直接使用 values[:3]，避免不必要的 copy
        coord = values[:3].astype(np.float32, copy=False)
        
        old_value = self._queue[0] if len(self._queue) == self._queue_maxsize else None

        self._queue.append(coord)
        n = len(self._queue)

        if old_value is not None:
            self._current_value += (coord - old_value)/n

        else:
            # 队列未满：直接计算均值
            coords_array = np.vstack(self._queue)
            np.mean(coords_array, axis=0, out=self._current_value)
            # 队列未满不用考虑精度问题
            return self._current_value
        
        # 使用计数器判断是否需要重算
        self._next_recalc -= 1
        if self._next_recalc <= 0:
            coords_array = np.vstack(self._queue)
            np.mean(coords_array, axis=0, out=self._current_value)
            self._next_recalc = self._recalc_interval

        
        self._current_bbox = iou_info
        return self._current_value

    
    def reset(self) -> None:
        """重置滤波器到初始状态"""
        super().reset()
        self._queue.clear()
        self._next_recalc = self._recalc_interval


