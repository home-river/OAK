"""
背压策略（纯函数）
"""
from __future__ import annotations

from typing import Iterable

from oak_vision_system.core.backpressure.config import BackpressureConfig
from oak_vision_system.core.backpressure.types import (
    BackpressureAction,
    BackpressureState,
    QueueMetrics,
    Watermarks,
)


def calculate_watermarks(capacity: int, config: BackpressureConfig) -> Watermarks:
    """
    根据队列容量和配置计算水位线（绝对值）
    
    小容量队列（< min_capacity）使用固定比例，避免水位线过小导致抖动。
    """
    if capacity < config.min_capacity:
        # 小容量队列保护：使用固定比例
        high = max(2, int(capacity * 0.9))
        low = max(1, int(capacity * 0.5))
    else:
        # 正常队列：使用配置比例
        high = int(capacity * config.high_ratio)
        low = int(capacity * config.low_ratio)
    
    return Watermarks(high=high, low=low)


def decide_state(
    metrics: QueueMetrics,
    watermarks: Watermarks,
    drop_threshold: int,
    pre_state: BackpressureState,
    high_hits: int,
    low_hits: int,
    high_hits_threshold: int,
    low_hits_threshold: int,
) -> tuple[BackpressureState, BackpressureAction, str]:
    """
    背压状态决策函数
    
    根据上一时刻状态、当前指标、水位线、阈值等决策新状态和动作
    
    Args:
        metrics: QueueMetrics
            当前队列的实时指标（队列长度、丢弃数等）
        watermarks: Watermarks
            队列高/低水位线（绝对值）
        drop_threshold: int
            窗口检测“背压过载”所需的丢弃数阈值
        pre_state: BackpressureState
            队列的上一时刻背压状态
        high_hits: int
            连续处于高水位线的命中次数计数
        low_hits: int
            连续处于低水位线的命中次数计数
        high_hits_threshold: int
            触发“高水位背压”所需的连续次数
        low_hits_threshold: int
            触发“滞后恢复正常”所需的连续低水位次数
    Returns:
        (state, action, reason): 新状态、动作、原因
    """
    

    # 1) 强制背压：丢弃过多
    if  metrics.drop_count_delta >= drop_threshold:
        return BackpressureState.OVERLOADED, BackpressureAction.PAUSE, "drop_rate"

    # 2) 过载状态下
    if pre_state == BackpressureState.OVERLOADED:
        if metrics.current_size < watermarks.low:
            return BackpressureState.NORMAL, BackpressureAction.NORMAL, "queue_low"
        else:
            return BackpressureState.OVERLOADED, BackpressureAction.PAUSE, "queue_overload"

        
    # 3) 已在背压
    if pre_state == BackpressureState.PRESSURED:
        # 当前在低水位且保持次数达标，则恢复正常状态
        if metrics.current_size <= watermarks.low and low_hits >= low_hits_threshold:
            return BackpressureState.NORMAL, BackpressureAction.NORMAL, "queue_low_hits"
        # 其余情况继续保持背压 弱限流
        return BackpressureState.PRESSURED, BackpressureAction.THROTTLE, "pressure_hold"


    # 4) 处于正常/未知：若开始丢弃则直接强限流，否则触发背压需连续命中
    if metrics.drop_count_delta > 0:
        return BackpressureState.PRESSURED, BackpressureAction.THROTTLE, "drop_warn"
    if metrics.current_size >= watermarks.high and high_hits >= high_hits_threshold:
        return BackpressureState.PRESSURED, BackpressureAction.THROTTLE, "queue_high_hits"

        
    # 5) 默认保持正常
    return BackpressureState.NORMAL, BackpressureAction.NORMAL, "queue_ok"











