"""
匹配算法文件，用于检测结果的追踪匹配，维护检测结果的轨迹，方便持续滤波
当前实现基于IoU
"""
import numpy as np
from abc import ABC, abstractmethod
from scipy.optimize import linear_sum_assignment

class BaseTracker(ABC):
    """目标跟踪器抽象基类"""
    
    def __init__(self, iou_threshold: float = 0.5):
        self.threshold = iou_threshold
    
    @abstractmethod
    def match(
        self, 
        prev_boxes: np.ndarray,
        curr_boxes: np.ndarray
    ) -> tuple[dict[int, int], np.ndarray]:
        """
        匹配算法的核心接口
        
        Args:
            prev_boxes: (N, 4) [x_min, y_min, x_max, y_max]，历史帧的边界框
            curr_boxes: (M, 4) [x_min, y_min, x_max, y_max]，当前帧的边界框
        
        Returns:
            matches: {prev_id: curr_id} 匹配字典
            iou_matrix: (N, M) IoU矩阵（用于调试）
        """
        pass
    
    def _batch_iou(self, boxes1: np.ndarray, boxes2: np.ndarray) -> np.ndarray:
        """向量化计算 IoU 矩阵
        
        Args:
            boxes1: (N, 4) [x_min, y_min, x_max, y_max]，第一组边界框
            boxes2: (M, 4) [x_min, y_min, x_max, y_max]，第二组边界框
        
        Returns:
            iou_matrix: (N, M)，每个元素表示boxes1中第i个框与boxes2中第j个框的IoU
        """
        # 处理空数组情况
        if len(boxes1) == 0 or len(boxes2) == 0:
            return np.zeros((len(boxes1), len(boxes2)))
        
        # 广播计算交集
        x1 = np.maximum(boxes1[:, None, 0], boxes2[None, :, 0])
        y1 = np.maximum(boxes1[:, None, 1], boxes2[None, :, 1])
        x2 = np.minimum(boxes1[:, None, 2], boxes2[None, :, 2])
        y2 = np.minimum(boxes1[:, None, 3], boxes2[None, :, 3])
        
        intersection = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        
        # 计算面积
        area1 = (boxes1[:, 2] - boxes1[:, 0]) * (boxes1[:, 3] - boxes1[:, 1])
        area2 = (boxes2[:, 2] - boxes2[:, 0]) * (boxes2[:, 3] - boxes2[:, 1])
        
        union = area1[:, None] + area2[None, :] - intersection
        
        # 返回一个（N,M）的矩阵，每个元素表示boxes1中第i个框与boxes2中第j个框的IoU
        return intersection / (union + 1e-6)  # 避免除零


class OptimizedGreedyTracker(BaseTracker):
    """
    优化的贪心匹配器（全局贪心，无第三方依赖）
    
    按 IoU 从大到小排序，依次分配，保证一对一匹配
    """
    
    def match(
        self, 
        prev_boxes: np.ndarray,
        curr_boxes: np.ndarray
    ) -> tuple[dict[int, int], np.ndarray]:
        """
        使用全局贪心策略进行一对一匹配
        
        Returns:
            matches: {prev_id: curr_id}
            iou_matrix: (N, M) IoU 相似度矩阵
        """
        if len(prev_boxes) == 0 or len(curr_boxes) == 0:
            return {}, np.array([])
        
        iou_matrix = self._batch_iou(prev_boxes, curr_boxes)
        
        # 收集所有候选匹配对 (iou, prev_id, curr_id)
        pairs = []
        for i in range(len(prev_boxes)):
            for j in range(len(curr_boxes)):
                if iou_matrix[i, j] >= self.threshold:
                    pairs.append((iou_matrix[i, j], i, j))
        
        # 按 IoU 降序排序
        pairs.sort(reverse=True, key=lambda x: x[0])
        
        # 贪心分配（保证一对一）
        matches = {}
        used_prev = set()
        used_curr = set()
        
        for _, prev_id, curr_id in pairs:
            if prev_id not in used_prev and curr_id not in used_curr:
                matches[int(prev_id)] = int(curr_id)
                used_prev.add(prev_id)
                used_curr.add(curr_id)
        
        return matches, iou_matrix

class HungarianTracker(BaseTracker):
    """基于匈牙利算法的全局最优匹配（推荐用于 < 100 个目标）"""
    
    def match(
        self, 
        prev_boxes: np.ndarray,
        curr_boxes: np.ndarray
    ) -> tuple[dict[int, int], np.ndarray]:
        if len(prev_boxes) == 0 or len(curr_boxes) == 0:
            return {}, np.array([])
        
        iou_matrix = self._batch_iou(prev_boxes, curr_boxes)
        cost_matrix = 1 - iou_matrix
        
        # 匈牙利算法求全局最优分配
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        matches = {
            int(prev_id): int(curr_id)
            for prev_id, curr_id in zip(row_ind, col_ind)
            if iou_matrix[prev_id, curr_id] >= self.threshold
        }
        
        return matches, iou_matrix

# 向后兼容的别名（保留原接口）
IoUMatcher = OptimizedGreedyTracker


def create_tracker(method: str = "greedy", **kwargs) -> BaseTracker:
    """
    Tracker 工厂函数
    
    Args:
        method: 匹配方法
            - "greedy": 优化贪心（推荐，默认）
            - "hungarian": 匈牙利算法（全局最优）
        **kwargs: 传递给 Tracker 的参数（如 iou_threshold）
    
    Returns:
        BaseTracker 实例
    """
    trackers = {
        "greedy": OptimizedGreedyTracker,
        "hungarian": HungarianTracker,
    }
    
    if method not in trackers:
        raise ValueError(f"Unknown method '{method}'. Available: {list(trackers.keys())}")
    
    return trackers[method](**kwargs)
