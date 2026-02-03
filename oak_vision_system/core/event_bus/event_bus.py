import logging
import os
import threading
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, Future, wait as futures_wait


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

        return：
            True: 需要投递
            False: 不需要投递
        """
        # 如果没有过滤函数，则直接投递
        if self.filter_func is None:
            return True
        try:
            # 执行过滤函数
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
    并行事件总线，支持：
    - 订阅/取消订阅
    - 并行发布（订阅者并行执行，提升多核利用率）
    - 简单优先级（高优先级订阅者先执行）
    - 流量控制（按事件类型开关）
    - 统计信息（发布数/投递数/错误数/在途事件）
    - 可选：同步/异步模式（wait_all 参数）
    """

    def __init__(self, max_workers: Optional[int] = None) -> None:
        # event_type -> List[Subscription]
        self._subscriptions: Dict[str, List[Subscription]] = {}

        # 线程安全锁
        self._lock = threading.RLock()

        self._closed = False

        # 流量控制：某些事件类型可以临时禁用（例如背压时暂停 RAW_FRAME_DATA）
        self._flow_control: Dict[str, bool] = {}

        # 并行执行线程池（动态配置大小）
        if max_workers is None:
            # IO密集型场景建议2倍核心数
            cpu_count = os.cpu_count() or 4
            max_workers = cpu_count * 2
        # 创建线程池
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="EventBusWorker"
        )

    # -------- 单例接口（兼容旧调用） --------
    @classmethod
    def get_instance(cls) -> "EventBus":
        return get_event_bus()

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
        with self._lock:
            if self._closed:
                raise RuntimeError("EventBus 已关闭，无法订阅事件。")

        # 获取订阅者名称
        if subscriber_name is None:
            owner = getattr(callback, "__self__",None)
            if owner is not None:
                subscriber_name = f"{type(owner).__name__}.{callback.__name__}"
        else:
            subscriber_name = callback.__name__

        # 生成 subscription_id
        subscription_id = f"{event_type}:{id(callback)}:{time.time_ns()}"

        # 创建订阅对象
        sub = Subscription(
            subscription_id=subscription_id,
            event_type=event_type,
            callback=callback,
            priority=priority,
            filter_func=filter_func,
            subscriber_name=subscriber_name,
        )

        # 添加订阅对象到订阅列表
        with self._lock:
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = []
            self._subscriptions[event_type].append(sub)

            # 按优先级排序（值越大优先级越高）
            self._subscriptions[event_type].sort(
                key=lambda s: s.priority, reverse=True
            )

        # 记录订阅事件
        logger.info(
            "订阅事件: event_type=%s, subscription_id=%s, priority=%s, subscriber_name=%s",
            event_type,
            subscription_id,
            priority.name,
            subscriber_name,
        )

        # 返回 subscription_id
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        根据 subscription_id 取消订阅。

        :return: 是否成功取消
        """
        with self._lock:
            if self._closed:
                return False
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

    # -------- 辅助方法：安全调用订阅者 --------
    def _safe_call(self, sub: Subscription, data: Any) -> bool:
        """
        安全调用订阅者回调，捕获异常并更新统计信息。

        :param sub: 订阅对象
        :param data: 事件数据
        :return: 是否成功执行
        """
        try:
            sub.callback(data)
            return True
        except Exception:
            sub.error_count += 1
            logger.exception(
                "订阅回调执行异常: event_type=%s, subscription_id=%s, subscriber_name=%s",
                sub.event_type,
                sub.subscription_id,
                sub.subscriber_name,
            )
            return False

    # -------- 发布事件（并行执行） --------
    def publish(
        self,
        event_type: str,
        data: Any,
        priority: Priority = Priority.NORMAL,
        wait_all: bool = False,
        timeout: Optional[float] = None,
    ) -> int:
        """
        并行发布事件，所有订阅者回调在线程池中并行执行。

        :param event_type: 事件类型
        :param data: 事件数据
        :param priority: 优先级（暂未使用）
        :param wait_all: 是否等待所有订阅者完成（True=同步模式，False=异步模式）
        :param timeout: 等待超时时间（秒），仅在 wait_all=True 时有效
        :return: 成功投递的订阅者数量
        """
        with self._lock:
            if self._closed:
                return 0

        # 流量控制检查（例如底层背压时关闭某类事件）
        if self.is_flow_controlled(event_type):
            logger.debug("事件被流量控制丢弃: event_type=%s", event_type)
            return 0

        # 获取订阅者列表
        with self._lock:
            subscribers = list(self._subscriptions.get(event_type, []))

        # 过滤并准备有效的订阅者
        valid_subs = []
        for sub in subscribers:
            if sub.should_deliver(data):
                sub.total_calls += 1
                valid_subs.append(sub)

        if not valid_subs:
            return 0

        # 并行提交所有订阅者任务到线程池
        futures = []
        for sub in valid_subs:
            future = self._executor.submit(self._safe_call, sub, data)
            futures.append(future)

        delivered = 0

        if wait_all:
            # 同步模式：等待所有订阅者完成
            if timeout is None:
                timeout = 5.0  # 默认5秒超时
            # 等待所有订阅者完成
            done, not_done = futures_wait(futures, timeout=timeout)
            
            # 统计成功执行的订阅者数量
            for f in done:
                try:
                    if f.result() is True:
                        delivered += 1
                except Exception:
                    # 异常已在 _safe_call 中处理，这里只统计
                    pass

            if not_done:
                logger.warning(
                    "事件分发超时: event_type=%s, 超时订阅者数量=%d, 超时时间=%.1fs",
                    event_type,
                    len(not_done),
                    timeout,
                )
        else:
            # 异步模式：fire-and-forget，不等待完成
            # 注意：这里无法立即知道成功数量，返回提交的任务数
            delivered = len(futures)

        return delivered

    # -------- 异步发布（便捷方法） --------
    def publish_async(
        self,
        event_type: str,
        data: Any,
        priority: Priority = Priority.NORMAL,
    ) -> Future:
        """
        异步发布事件：在后台线程池中执行 publish(wait_all=False)，
        调用方无需等待订阅者处理完成。

        这是 publish(wait_all=False) 的便捷方法，保持向后兼容。

        :return: Future 对象，可用于查询执行状态
        """
        with self._lock:
            if self._closed:
                f: Future = Future()
                f.set_result(0)
                return f

        return self._executor.submit(
            self.publish, event_type, data, priority, wait_all=False
        )


    def close(self, wait: bool = True, cancel_pending: bool = False) -> None:
        """
        关闭 EventBus，取消所有订阅。

        :param wait: 是否等待所有正在执行的订阅者完成，否则立即返回。
                     注意：这里的“正在执行”指的是异步模式下的未完成任务。
        :param cancel_pending: 是否取消等待执行的任务。
                                注意：这里的“等待执行”指的是异步模式下的未开始执行的任务。
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._subscriptions.clear()
            self._flow_control.clear()

        try:
            self._executor.shutdown(wait=wait, cancel_pending=cancel_pending)
        except TypeError:
            # 兼容 Python 3.7 之前的版本，没有 cancel_pending 参数
            self._executor.shutdown(wait=wait)


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


# =========================
# 全局单例管理
# =========================
# 全局 EventBus 单例实例
_event_bus_instance: Optional[EventBus] = None
# 线程锁，用于保护单例初始化的线程安全
_event_bus_lock = threading.Lock()
# 记录初始化时的 max_workers 参数，用于防止重复初始化时参数不一致
_event_bus_init_max_workers: Optional[int] = None


def initialize_event_bus(max_workers: Optional[int] = None) -> EventBus:
    """
    初始化全局 EventBus 单例实例。

    如果已经初始化过，则返回现有实例。如果尝试使用不同的 max_workers 参数
    重复初始化，将抛出 RuntimeError。

    :param max_workers: 线程池最大工作线程数，None 时使用默认值（CPU核心数 * 2）
    :return: EventBus 实例
    :raises RuntimeError: 当尝试使用不同的 max_workers 重复初始化时
    """
    global _event_bus_instance
    global _event_bus_init_max_workers

    with _event_bus_lock:
        if _event_bus_instance is None:
            _event_bus_instance = EventBus(max_workers=max_workers)
            _event_bus_init_max_workers = max_workers
            return _event_bus_instance

        if max_workers is not None and _event_bus_init_max_workers != max_workers:
            raise RuntimeError(
                "EventBus 已初始化，禁止使用不同 max_workers 重复初始化。"
            )

        return _event_bus_instance


def get_event_bus() -> EventBus:
    """
    获取全局 EventBus 单例实例。

    如果尚未初始化，则自动使用默认参数初始化。

    :return: EventBus 实例
    """
    if _event_bus_instance is None:
        return initialize_event_bus()
    return _event_bus_instance


def reset_event_bus() -> None:
    """
    重置全局 EventBus 单例实例。

    将单例实例和初始化参数重置为 None，主要用于测试场景。
    注意：重置后需要重新调用 initialize_event_bus() 或 get_event_bus() 来创建新实例。
    """
    global _event_bus_instance
    global _event_bus_init_max_workers

    with _event_bus_lock:
        _event_bus_instance = None
        _event_bus_init_max_workers = None


def get_global_event_bus() -> EventBus:
    """
    获取全局 EventBus 单例实例（get_event_bus 的别名）。

    提供此函数以保持 API 的一致性，实际功能与 get_event_bus() 相同。

    :return: EventBus 实例
    """
    return get_event_bus()


def reset_global_event_bus() -> None:
    """
    重置全局 EventBus 单例实例（reset_event_bus 的别名）。

    提供此函数以保持 API 的一致性，实际功能与 reset_event_bus() 相同。
    """
    reset_event_bus()


def shutdown_event_bus(
    *,
    wait: bool = True,
    cancel_pending: bool = False,
    reset_instance: bool = True,
) -> None:
    global _event_bus_instance
    global _event_bus_init_max_workers

    with _event_bus_lock:
        if _event_bus_instance is None:
            return

        _event_bus_instance.close(wait=wait, cancel_pending=cancel_pending)

        if reset_instance:
            _event_bus_instance = None
            _event_bus_init_max_workers = None
