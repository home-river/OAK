"""
事件总线核心实现

高性能的发布-订阅（Pub-Sub）事件总线，用于模块间异步通信。

设计特点：
1. 同步执行：在发布者线程中直接调用订阅者回调（不使用独立线程）
2. 线程安全：使用锁保护订阅者列表
3. 错误隔离：单个订阅者异常不影响其他订阅者
4. 性能优化：针对15fps实时系统优化

性能目标：
- 事件分发延迟：< 5ms
- 支持并发订阅/发布
- CPU占用：< 5%（15fps场景）
"""

import logging
import threading
import uuid
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

from .event_types import Priority


# 订阅信息数据类
@dataclass
class Subscription:
    """订阅信息"""
    subscription_id: str
    event_type: str
    callback: Callable[[Any], None]
    priority: Priority = Priority.NORMAL
    
    def __hash__(self):
        return hash(self.subscription_id)


class EventBus:
    """
    事件总线核心类
    
    提供线程安全的发布-订阅机制，用于模块间解耦通信。
    
    使用示例：
        >>> event_bus = EventBus()
        >>> 
        >>> # 订阅事件
        >>> def handler(data):
        ...     print(f"收到数据: {data}")
        >>> 
        >>> sub_id = event_bus.subscribe("raw_frame_data", handler)
        >>> 
        >>> # 发布事件
        >>> event_bus.publish("raw_frame_data", frame_data)
        >>> 
        >>> # 取消订阅
        >>> event_bus.unsubscribe(sub_id)
    """
    
    def __init__(self):
        """初始化事件总线"""
        # 订阅者映射：event_type -> List[Subscription]
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        
        # 线程锁：保护订阅者列表
        self._lock = threading.RLock()
        
        # 日志
        self._logger = logging.getLogger(__name__)
        
        # 统计信息
        self._stats = {
            'total_published': 0,
            'total_delivered': 0,
            'total_errors': 0
        }
        
        self._logger.info("事件总线已初始化")
    
    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Any], None],
        priority: Priority = Priority.NORMAL
    ) -> str:
        """
        订阅事件
        
        Args:
            event_type: 事件类型（来自EventType类）
            callback: 回调函数，接收一个参数（事件数据）
            priority: 优先级（暂未实现优先级排序）
            
        Returns:
            str: 订阅ID，用于取消订阅
            
        Example:
            >>> def my_handler(data):
            ...     print(data)
            >>> sub_id = event_bus.subscribe("raw_frame_data", my_handler)
        """
        # 生成唯一订阅ID
        subscription_id = str(uuid.uuid4())
        
        # 创建订阅信息
        subscription = Subscription(
            subscription_id=subscription_id,
            event_type=event_type,
            callback=callback,
            priority=priority
        )
        
        # 线程安全地添加订阅
        with self._lock:
            self._subscriptions[event_type].append(subscription)
            
            self._logger.debug(
                f"新订阅: event_type={event_type}, "
                f"subscription_id={subscription_id}, "
                f"total_subscribers={len(self._subscriptions[event_type])}"
            )
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅
        
        Args:
            subscription_id: 订阅ID（由subscribe()返回）
            
        Returns:
            bool: True表示成功取消，False表示订阅不存在
            
        Example:
            >>> event_bus.unsubscribe(sub_id)
        """
        with self._lock:
            # 遍历所有事件类型，查找并移除订阅
            for event_type, subscriptions in self._subscriptions.items():
                for subscription in subscriptions:
                    if subscription.subscription_id == subscription_id:
                        subscriptions.remove(subscription)
                        
                        self._logger.debug(
                            f"取消订阅: event_type={event_type}, "
                            f"subscription_id={subscription_id}"
                        )
                        return True
        
        self._logger.warning(f"订阅不存在: subscription_id={subscription_id}")
        return False
    
    def publish(
        self,
        event_type: str,
        data: Any,
        priority: Priority = Priority.NORMAL
    ) -> int:
        """
        发布事件
        
        在当前线程中同步调用所有订阅者的回调函数。
        单个订阅者的异常不会影响其他订阅者。
        
        Args:
            event_type: 事件类型
            data: 事件数据（通常是DTO对象）
            priority: 优先级（暂未使用）
            
        Returns:
            int: 成功调用的订阅者数量
            
        Example:
            >>> event_bus.publish("raw_frame_data", frame_dto)
        """
        # 更新统计
        self._stats['total_published'] += 1
        
        # 获取订阅者列表（线程安全）
        with self._lock:
            subscriptions = self._subscriptions.get(event_type, []).copy()
        
        # 如果没有订阅者，直接返回
        if not subscriptions:
            self._logger.debug(f"无订阅者: event_type={event_type}")
            return 0
        
        # 调用所有订阅者
        success_count = 0
        for subscription in subscriptions:
            try:
                # 同步调用回调函数
                subscription.callback(data)
                success_count += 1
                self._stats['total_delivered'] += 1
                
            except Exception as e:
                # 错误隔离：单个订阅者异常不影响其他订阅者
                self._stats['total_errors'] += 1
                self._logger.error(
                    f"订阅者回调异常: "
                    f"event_type={event_type}, "
                    f"subscription_id={subscription.subscription_id}, "
                    f"error={str(e)}",
                    exc_info=True
                )
        
        return success_count
    
    def get_subscriber_count(self, event_type: str) -> int:
        """
        获取指定事件类型的订阅者数量
        
        Args:
            event_type: 事件类型
            
        Returns:
            int: 订阅者数量
        """
        with self._lock:
            return len(self._subscriptions.get(event_type, []))
    
    def get_all_event_types(self) -> List[str]:
        """
        获取所有已订阅的事件类型
        
        Returns:
            List[str]: 事件类型列表
        """
        with self._lock:
            return list(self._subscriptions.keys())
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取统计信息
        
        Returns:
            Dict[str, int]: 统计数据
        """
        return self._stats.copy()
    
    def clear_all_subscriptions(self):
        """
        清除所有订阅（主要用于测试）
        
        警告：此操作会清除所有订阅者，谨慎使用！
        """
        with self._lock:
            self._subscriptions.clear()
            self._logger.warning("已清除所有订阅")
    
    def __repr__(self) -> str:
        """字符串表示"""
        with self._lock:
            total_subscriptions = sum(
                len(subs) for subs in self._subscriptions.values()
            )
        
        return (
            f"EventBus("
            f"event_types={len(self._subscriptions)}, "
            f"total_subscriptions={total_subscriptions}, "
            f"published={self._stats['total_published']}, "
            f"delivered={self._stats['total_delivered']}, "
            f"errors={self._stats['total_errors']}"
            f")"
        )


# 全局单例（可选）
_global_event_bus: Optional[EventBus] = None


def get_global_event_bus() -> EventBus:
    """
    获取全局事件总线单例
    
    Returns:
        EventBus: 全局事件总线实例
        
    Example:
        >>> from core.event_bus import get_global_event_bus
        >>> event_bus = get_global_event_bus()
        >>> event_bus.subscribe(...)
    """
    global _global_event_bus
    
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    
    return _global_event_bus


def reset_global_event_bus():
    """
    重置全局事件总线（主要用于测试）
    """
    global _global_event_bus
    _global_event_bus = None

