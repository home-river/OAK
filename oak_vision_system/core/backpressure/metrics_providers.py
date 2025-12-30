"""
MetricsProvider 实现：基于 OverflowQueue
"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from oak_vision_system.core.backpressure.types import QueueMetrics

if TYPE_CHECKING:
    from oak_vision_system.utils.data_structures.Queue import OverflowQueue


class OverflowQueueMetricsProvider:
    """
    OverflowQueue 的指标提供者（适配器模式）
    
    将 OverflowQueue 适配为背压系统所需的指标接口，提供统一的指标获取方法。
    主要功能：
    - 聚合队列的多个指标（使用率、大小、丢弃数等）
    - 计算丢弃增量（drop_count_delta），用于判断单轮是否丢弃过多
    - 线程安全的增量计算
    """

    def __init__(self, queue: "OverflowQueue", queue_id: str) -> None:
        """
        初始化指标提供者
        
        Args:
            queue: OverflowQueue 实例（需要监控的队列）
            queue_id: 队列唯一标识（用于日志和事件）
        """
        self._queue = queue
        self._queue_id = queue_id
        self._lock = threading.Lock()  # 保护 drop_count_delta 计算的线程安全
        self._last_drop_count = 0  # 上次的丢弃计数，用于计算增量

    def get_metrics(self) -> QueueMetrics:
        """
        获取队列当前指标快照
        
        聚合队列的多个指标，并计算丢弃增量。增量用于判断单轮是否丢弃过多
        （超过 drop_rate_threshold 时触发强制背压）。
        
        Returns:
            QueueMetrics: 包含队列使用率、大小、容量、丢弃数、压力等级等指标
            
        注意:
            - 线程安全：drop_count_delta 的计算受锁保护
            - 性能：尽量快速返回（建议 < 1ms），避免阻塞监控循环
        """
        # 计算丢弃增量（线程安全）
        with self._lock:
            current_drop = self._queue.get_drop_count()
            drop_delta = current_drop - self._last_drop_count
            # 防御性检查：如果计数器被重置，drop_delta 可能为负，修正为 0
            if drop_delta < 0:
                drop_delta = 0
            self._last_drop_count = current_drop

        # 获取其他指标（这些方法本身是线程安全的，无需额外锁）
        usage = self._queue.get_usage_ratio()
        
        return QueueMetrics(
            queue_id=self._queue_id,
            usage=usage,  # 使用率：current_size / capacity
            current_size=self._queue.qsize(),  # 当前队列大小
            capacity=self._queue.maxsize,  # 队列最大容量
            drop_count=current_drop,  # 累计丢弃次数
            drop_count_delta=drop_delta,  # 本轮新增丢弃次数（用于策略决策）
            pressure_level=self._queue.get_pressure_level(),  # 压力等级（low/medium/high/critical）
            timestamp=time.time(),  # 指标采集时间戳
        )
