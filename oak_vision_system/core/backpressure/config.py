"""
背压配置
"""
from dataclasses import dataclass


@dataclass
class BackpressureConfig:
    poll_interval_ms: int = 50  # 轮询间隔时间，单位：毫秒
    high_ratio: float = 0.8     # 高水位比例
    low_ratio: float = 0.5      # 低水位比例
    high_hits_threshold: int = 2 # 高水位命中次数阈值
    low_hits_threshold: int = 2  # 低水位命中次数阈值
    min_capacity: int = 10      # 最小容量
    drop_rate_threshold: float = 0.5 # 窗口期内丢弃率阈值（相对于队列容量的比例）


    def __post_init__(self) -> None:
        if not (0 < self.low_ratio < self.high_ratio <= 1.0):
            raise ValueError("0 < low_ratio < high_ratio <= 1.0")
        if self.poll_interval_ms <= 0:
            raise ValueError("poll_interval_ms 必须 > 0")
        if self.min_capacity < 0:
            raise ValueError("min_capacity 必须 >= 0")
        if self.drop_rate_threshold < 0:
            raise ValueError("drop_rate_threshold 必须 >= 0")
        
