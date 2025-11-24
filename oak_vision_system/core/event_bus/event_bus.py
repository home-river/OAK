import logging
import threading
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, Future


logger = logging.getLogger(__name__)


# =========================
# 优先级定义
# =========================
class Priority(IntEnum):
    HIGH = 3
    NORMAL = 2
    LOW = 1


# =========================
# 订阅对象
# =========================
@dataclass
class Subscription:
    """
    单个订阅关系
    """
    subscription_id: str
    event_type: str
    callback: Callable[[Any], None]
    priority: Priority = Priority.NORMAL
    filter_func: Optional[Callable[[Any], bool]] = None

    # 新增：订阅者名称，用于记录订阅者名称
    subscriber_name: Optional[str] = None

    # 健康状态（可选，用于统计，逻辑简单化）
    total_calls: int = 0
    error_count: int = 0

    def should_deliver(self, data: Any) -> bool:
        """
        通过过滤函数判断是否需要投递该事件给此订阅者。
        有过滤函数时先经过过滤，否则直接投递。
        """
        if self.filter_func is None:
            return True
        try:
            return bool(self.filter_func(data))
        except Exception:
            # 过滤函数异常时，为了安全起见仍然投递
            logger.exception(
                "订阅过滤函数执行异常，仍然投递事件: subscription_id=%s",
                self.subscription_id,
            )
            return True


# =========================
# 事件总线实现
# =========================
class EventBus:
    """
    同步事件总线，支持：
    - 订阅/取消订阅
    - 同步发布
    - 简单优先级（高优先级订阅者先执行）
    - 流量控制（按事件类型开关）
    - 统计信息（发布数/投递数/错误数/在途事件）
    - 可选：异步发布（后台线程池）
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        # event_type -> List[Subscription]
        self._subscriptions: Dict[str, List[Subscription]] = {}

        # 线程安全锁
        self._lock = threading.RLock()

        # 流量控制：某些事件类型可以临时禁用（例如背压时暂停 RAW_FRAME_DATA）
        self._flow_control: Dict[str, bool] = {}

        # 可选：异步发布线程池（懒初始化）
        self._async_executor: Optional[ThreadPoolExecutor] = None

    # -------- 单例接口（可选） --------
    @classmethod
    def get_instance(cls) -> "EventBus":
        """
        全局单例（如果你项目里已经有单例逻辑，可以替换/删除）
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # -------- 订阅相关 --------
    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Any], None],
        priority: Priority = Priority.NORMAL,
        filter_func: Optional[Callable[[Any], bool]] = None,
        subscriber_name: Optional[str] = None,
    ) -> str:
        """
        订阅某个事件类型，返回 subscription_id。

        :param event_type: 事件类型字符串
        :param callback:   回调函数，形如 fn(data) -> None
        :param priority:   优先级，高优先级先执行
        :param filter_func: 可选过滤函数，形如 fn(data) -> bool
        """
        if subscriber_name is None:
            owner = getattr(callback, "__self__",None)
            if owner is not None:
                subscriber_name = f"{type(owner).__name__}.{callback.__name__}"
        else:
            subscriber_name = callback.__name__
        subscription_id = f"{event_type}:{id(callback)}:{time.time_ns()}"
        sub = Subscription(
            subscription_id=subscription_id,
            event_type=event_type,
            callback=callback,
            priority=priority,
            filter_func=filter_func,
        )

        with self._lock:
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = []
            self._subscriptions[event_type].append(sub)

            # 按优先级排序（值越大优先级越高）
            self._subscriptions[event_type].sort(
                key=lambda s: s.priority, reverse=True
            )

        logger.info(
            "订阅事件: event_type=%s, subscription_id=%s, priority=%s, subscriber_name=%s",
            event_type,
            subscription_id,
            priority.name,
            subscriber_name,
        )
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        根据 subscription_id 取消订阅。

        :return: 是否成功取消
        """
        with self._lock:
            removed = False
            for event_type, subs in list(self._subscriptions.items()):
                new_list = [s for s in subs if s.subscription_id != subscription_id]
                if len(new_list) != len(subs):
                    self._subscriptions[event_type] = new_list
                    removed = True

                    logger.info(
                        "取消订阅: event_type=%s, subscription_id=%s",
                        event_type,
                        subscription_id,
                    )

            return removed

    # -------- 流量控制（背压用） --------
    def set_flow_control(self, event_type: str, enabled: bool) -> None:
        """
        设置指定事件类型是否被流量控制（禁止发布）。

        对于背压方案，可以在收到背压事件时：
        - set_flow_control(EventType.RAW_FRAME_DATA, True)  暂停推送
        - set_flow_control(EventType.RAW_FRAME_DATA, False) 恢复推送
        """
        with self._lock:
            self._flow_control[event_type] = enabled

        logger.info(
            "设置流量控制: event_type=%s, enabled=%s",
            event_type,
            enabled,
        )

    def is_flow_controlled(self, event_type: str) -> bool:
        """
        某事件类型是否被流量控制（禁止发布）。
        """
        with self._lock:
            return self._flow_control.get(event_type, False)

    # -------- 发布事件（同步） --------
    def publish(
        self,
        event_type: str,
        data: Any,
        priority: Priority = Priority.NORMAL,
    ) -> int:
        """
        同步发布事件，立即在当前线程调用所有订阅者回调。
        （暂时未使用优先级）

        :return: 成功投递的订阅者数量
        """
        # 流量控制检查（例如底层背压时关闭某类事件）
        if self.is_flow_controlled(event_type):
            logger.debug("事件被流量控制丢弃: event_type=%s", event_type)
            return 0

        with self._lock:
            subscribers = list(self._subscriptions.get(event_type, []))

        delivered = 0

        # 遍历订阅者（已按优先级排序）
        for sub in subscribers:
            # 过滤逻辑
            if not sub.should_deliver(data):
                continue

            sub.total_calls += 1

            try:
                sub.callback(data)
                delivered += 1

            except Exception:
                sub.error_count += 1
                logger.exception(
                    "订阅回调执行异常: event_type=%s, subscription_id=%s, subscriber_name=%s",
                    event_type,
                    sub.subscription_id,
                    sub.subscriber_name,
                )

        return delivered
    # -------- 异步发布（可选） --------
    def publish_async(
        self,
        event_type: str,
        data: Any,
        priority: Priority = Priority.NORMAL,
    ) -> Future:
        """
        异步发布事件：在后台线程池中执行 publish，
        调用方无需等待订阅者处理完成。

        注意：如果你的使用场景非常追求可控的执行顺序，
        或对线程数量敏感，可以不用这个方法。
        """
        with self._lock:
            if self._async_executor is None:
                self._async_executor = ThreadPoolExecutor(
                    max_workers=4, thread_name_prefix="EventBusWorker"
                )

            executor = self._async_executor

        return executor.submit(self.publish, event_type, data, priority)

    # -------- 调试用 --------
    def list_subscriptions(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        调试用：列出当前注册的订阅关系。
        :param event_type: 如果指定，只返回该事件类型的订阅，否则返回全部
        """
        with self._lock:
            result: List[Dict[str, Any]] = []
            for et, subs in self._subscriptions.items():
                if event_type is not None and et != event_type:
                    continue
                for s in subs:
                    result.append(
                        {
                            "event_type": et,
                            "subscription_id": s.subscription_id,
                            "subscriber_name": s.subscriber_name,
                            "priority": s.priority.name,
                            "total_calls": s.total_calls,
                            "error_count": s.error_count,
                        }
                    )
            return result
