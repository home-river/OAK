"""
背压模块 - 核心数据类型
"""
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Literal, Callable




class BackpressureState(IntEnum):
    """背压状态枚举"""
    UNKNOWN = 0      # 初始/未知状态，用于启动阶段
    NORMAL = 1        # 正常运行
    PRESSURED = 2  # 触发背压，需限流
    OVERLOADED = 3 # 过载，需暂停
    


class BackpressureAction(IntEnum):
    """
    背压信号动作
    
    含义：
    - NORMAL: 让上游恢复生产（解除暂停），常用于队列回落到低水位
    - THROTTLE: 让上游降速/限流（软控），可在介于高低水位之间时使用
    - PAUSE: 让上游暂停生产（硬停），常用于队列达到高水位
    """
    NORMAL = 0     # 正常生产，占位/默认值，避免发送空动作
    THROTTLE = 1 # 限流生产
    PAUSE = 2      # 暂停生产
    


@dataclass
class Watermarks:
    """高/低水位容量阈值，决定触发与解除背压，单位：个"""
    high: int
    low: int

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError("high 必须 >= low")
        if self.low < 0 or self.high < 0:
            raise ValueError("high/low 必须 >= 0")


@dataclass
class QueueMetrics:
    """队列指标快照，供策略决策使用"""
    queue_id: str       # 队列ID
    usage: float        # 使用率
    current_size: int   # 当前大小
    capacity: int       # 容量
    drop_count: int     # 丢弃数量
    drop_count_delta: int # 丢弃数量增量
    pressure_level: Literal["low", "medium", "high", "critical"] # 压力级别
    timestamp: float    # 时间戳

    def __post_init__(self) -> None:
        self.usage = max(0.0, min(1.0, self.usage)) # 使用率必须在0到1之间
        if self.capacity <= 0: # 容量必须大于0
            raise ValueError("capacity 必须 > 0")
        if self.current_size < 0: # 当前大小必须大于等于0
            raise ValueError("current_size 必须 >= 0")
        if self.drop_count < 0 or self.drop_count_delta < 0: # 丢弃数量必须大于等于0
            raise ValueError("drop_count/drop_count_delta 必须 >= 0")


MetricsProviderFn = Callable[[], QueueMetrics]
"""指标提供者函数类型：无参数，返回 QueueMetrics"""

@dataclass
class BackpressureEventPayload:
    """通过事件总线传播的背压信号载荷"""
    queue_id: str           # 队列ID
    action: BackpressureAction # 动作
    reason: str              # 原因
    timestamp: float         # 时间戳
    usage: float             # 使用率
    drop_count: int          # 丢弃数量
    pressure_level: Literal["low", "medium", "high", "critical"] # 压力级别
    state: BackpressureState # 状态


@dataclass
class BackpressureRegistration:
    """
    队列注册DTO：模块用于注册队列的DTO，用于返回规定格式的注册信息。
    """

    queue_id: str # 队列ID
    metrics_provider: MetricsProviderFn # 指标提供者函数
    capacity: int # 队列容量，单位：个