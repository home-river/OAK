"""
事件总线系统模块

提供高性能的发布-订阅（Pub-Sub）事件总线，用于模块间解耦通信。

使用示例：
    >>> from core.event_bus import EventBus, EventType, Priority
    >>> 
    >>> # 创建事件总线
    >>> event_bus = EventBus()
    >>> 
    >>> # 订阅事件
    >>> def handler(data):
    ...     print(f"收到: {data}")
    >>> 
    >>> sub_id = event_bus.subscribe(EventType.RAW_FRAME_DATA, handler)
    >>> 
    >>> # 发布事件
    >>> event_bus.publish(EventType.RAW_FRAME_DATA, frame_data)
    >>> 
    >>> # 取消订阅
    >>> event_bus.unsubscribe(sub_id)
"""

from .event_bus import (
    EventBus,
    Subscription,
    get_global_event_bus,
    reset_global_event_bus
)
from .event_types import EventType, Priority

__all__ = [
    'EventBus',
    'Subscription',
    'EventType',
    'Priority',
    'get_global_event_bus',
    'reset_global_event_bus'
]

