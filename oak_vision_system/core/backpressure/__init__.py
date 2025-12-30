"""
背压模块对外导出
"""
from .config import BackpressureConfig
from .types import (
    BackpressureAction,
    BackpressureEventPayload,
    BackpressureState,
    QueueMetrics,
    Watermarks,
    BackpressureRegistration,
    MetricsProviderFn,
)
from .metrics_providers import OverflowQueueMetricsProvider
from .strategy import calculate_watermarks, decide_state
from .monitor import BackpressureMonitor, get_backpressure_monitor, initialize_backpressure_monitor

__all__ = [
    # 配置类
    "BackpressureConfig",              # 背压配置：轮询间隔、水位比例、阈值等参数
    
    # 枚举类型
    "BackpressureAction",              # 背压动作枚举：NORMAL/THROTTLE/PAUSE
    "BackpressureState",               # 背压状态枚举：UNKNOWN/NORMAL/PRESSURED/OVERLOADED
    
    # 数据类
    "BackpressureEventPayload",        # 背压事件载荷：通过事件总线传播的背压信号数据
    "QueueMetrics",                    # 队列指标快照：使用率、大小、容量、丢弃数、压力等级等
    "Watermarks",                      # 水位线：高/低水位容量阈值，用于触发与解除背压
    "BackpressureRegistration",        # 队列注册DTO：用于注册队列的注册信息
    
    # 类型别名
    "MetricsProviderFn",               # 指标提供者函数类型：无参数，返回 QueueMetrics
    
    # 指标提供者实现
    "OverflowQueueMetricsProvider",    # OverflowQueue 的指标提供者适配器
    
    # 策略函数
    "calculate_watermarks",            # 计算水位线：根据队列容量和配置计算高/低水位阈值
    "decide_state",                    # 背压状态决策：根据指标、水位线、阈值等决策背压状态和动作
    
    # 监控器
    "BackpressureMonitor",             # 背压监控器：周期性采样队列指标并发布背压事件
    "get_backpressure_monitor",
    "initialize_backpressure_monitor",
]
