"""
背压监控线程：周期性采样队列指标并发布背压事件
"""
from __future__ import annotations

import threading
import time
import logging
from dataclasses import dataclass
from typing import Dict

from oak_vision_system.core.backpressure.config import BackpressureConfig
from oak_vision_system.core.backpressure.strategy import calculate_watermarks, decide_state
from oak_vision_system.core.backpressure.types import (
    BackpressureAction,
    BackpressureState,
    BackpressureEventPayload,
    QueueMetrics,
    Watermarks,
    MetricsProviderFn,
)
from oak_vision_system.core.event_bus import EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class _Registration:
    """队列注册信息（内部数据结构）"""
    queue_id: str  # 队列唯一标识
    metrics_provider: MetricsProviderFn  # 指标获取函数
    capacity: int  # 队列容量
    watermarks: Watermarks  # 高/低水位线
    drop_threshold: int     # 丢弃阈值
    state: BackpressureState = BackpressureState.UNKNOWN  # 当前背压状态
    high_hits: int = 0  # 连续高水位命中次数
    low_hits: int = 0   # 连续低水位命中次数


class BackpressureMonitor:
    """
    集中背压监控器
    
    职责：
    - 周期性轮询已注册队列的指标
    - 根据策略决策背压状态和动作
    - 状态变化时发布背压事件到事件总线
    
    特点：
    - 单线程运行，轻量级循环
    - 异常隔离（单个队列错误不影响整体）
    - 幂等发布（状态变化或需要动作时才发布）
    """

    def __init__(
        self,
        config: BackpressureConfig | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """
        初始化背压监控器
        
        Args:
            config: 背压配置（轮询间隔、阈值等），不传则使用默认配置
            event_bus: 事件总线实例，不传则使用全局单例
        """
        self.config = config or BackpressureConfig()
        self._event_bus = event_bus or get_event_bus()

        self._registrations: Dict[str, _Registration] = {}  # 已注册的队列
        self._lock = threading.Lock()  # 保护注册表的线程安全
        self._running = False  # 监控循环运行标志
        self._thread: threading.Thread | None = None  # 监控线程

    def register_queue(self, queue_id: str, metrics_provider: MetricsProviderFn, capacity: int) -> None:
        """
        注册队列到背压监控
        
        Args:
            queue_id: 队列唯一标识（不能重复）
            metrics_provider: 指标提供者函数（调用后返回 QueueMetrics）
            capacity: 队列最大容量（用于计算水位线）
            
        Raises:
            ValueError: 如果 queue_id 已存在
        """
        with self._lock:
            if queue_id in self._registrations:
                raise ValueError(f"queue_id 已存在: {queue_id}")
            # 根据容量和配置计算水位线
            watermarks = calculate_watermarks(capacity, self.config)
            # 计算丢弃阈值
            drop_threshold = int(self.config.drop_rate_threshold*capacity)
            self._registrations[queue_id] = _Registration(
                queue_id=queue_id,
                metrics_provider=metrics_provider,
                capacity=capacity,
                watermarks=watermarks,
                drop_threshold=drop_threshold,   
            )
            logger.info("注册队列: %s, watermarks=%s", queue_id, watermarks)

    def unregister_queue(self, queue_id: str) -> None:
        """
        注销队列（停止监控）
        
        Args:
            queue_id: 要注销的队列ID
        """
        with self._lock:
            self._registrations.pop(queue_id, None)
            logger.info("注销队列: %s", queue_id)

    def start(self) -> None:
        """
        启动监控循环
        
        创建并启动独立的监控线程，周期性检查所有已注册队列。
        线程为守护线程（daemon），主进程退出时自动结束。
        """
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="BackpressureMonitor", daemon=True)
        self._thread.start()
        logger.info("BackpressureMonitor started, interval=%sms", self.config.poll_interval_ms)

    def stop(self, timeout: float = 1.0) -> None:
        """
        停止监控循环
        
        Args:
            timeout: 等待线程退出的超时时间（秒），默认 1.0 秒
        """
        if not self._running:
            return
        self._running = False
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("BackpressureMonitor stopped")

    # ========== 内部逻辑 ==========
    def _loop(self) -> None:
        """
        监控循环（在独立线程中运行）
        
        周期性检查所有已注册队列的指标，并根据策略决策背压状态。
        使用快照机制减少持锁时间，异常隔离确保单个队列错误不影响整体。
        """
        interval = self.config.poll_interval_ms / 1000.0  # 转换为秒
        pre_state = BackpressureState.UNKNOWN
        pre_action = BackpressureAction.NORMAL
        while self._running:
            best_queue_id = ""
            best_state = BackpressureState.UNKNOWN
            best_action = BackpressureAction.NORMAL
            best_reason = ""
            best_metrics: QueueMetrics | None = None

            # 快照注册表（减少持锁时间，避免长时间阻塞注册/注销操作）
            with self._lock:
                snapshot = list(self._registrations.values())
            
            # 检查每个队列（在锁外执行，避免阻塞）
            for reg in snapshot:
                try:
                    new_state, new_action, reason, metrics = self._check(reg)
                    if (new_action.value, new_state.value) > (best_action.value, best_state.value):
                        best_queue_id = reg.queue_id
                        best_state = new_state
                        best_action = new_action
                        best_reason = reason
                        best_metrics = metrics

                except Exception:  # 防御性隔离：单个队列错误不影响其他队列
                    logger.exception("检查队列出错: %s", reg.queue_id)
            
            if best_metrics is not None and (best_state != pre_state or best_action != pre_action):
                self._publish(
                    BackpressureEventPayload(
                        queue_id=best_queue_id,
                        action=best_action,
                        reason=best_reason,
                        timestamp=time.time(),
                        usage=best_metrics.usage,
                        drop_count=best_metrics.drop_count,
                        pressure_level=best_metrics.pressure_level,
                        state=best_state,
                    )
                )
                pre_state = best_state
                pre_action = best_action
            
            time.sleep(interval)

    def _check(self, reg: _Registration) -> tuple[BackpressureState, BackpressureAction, str, QueueMetrics]:
        """
        检查单个队列并决策
        
        流程：
        1. 获取队列当前指标
        2. 调用策略函数决策新状态和动作
        3. 状态变化或需要动作时发布事件
        
        Args:
            reg: 队列注册信息
        """
        # 1. 获取当前指标
        metrics = reg.metrics_provider()
        
        # 1.1 维护连续命中计数
        if reg.state in (BackpressureState.NORMAL, BackpressureState.UNKNOWN):
            if metrics.current_size >= reg.watermarks.high:
                reg.high_hits += 1
            else:
                reg.high_hits = 0
            reg.low_hits = 0  # 低水位命中次数计数清零，避免误判
        elif reg.state == BackpressureState.PRESSURED:
            if metrics.current_size <= reg.watermarks.low:
                reg.low_hits += 1
            else:
                reg.low_hits = 0
            reg.high_hits = 0  # 高水位命中次数计数清零，避免误判
        else:
            reg.high_hits = 0
            reg.low_hits = 0

        # 2. 决策新状态和动作
        state, action, reason = decide_state(
            metrics=metrics,
            watermarks=reg.watermarks,
            drop_threshold=reg.drop_threshold,
            pre_state=reg.state,
            high_hits=reg.high_hits,
            low_hits=reg.low_hits,
            high_hits_threshold=self.config.high_hits_threshold,
            low_hits_threshold=self.config.low_hits_threshold,
        )
        
        # 3. 返回状态动作值和原因
        reg.state = state
        return state, action, reason, metrics

    def _publish(self, payload: BackpressureEventPayload) -> None:
        """
        发布背压事件到事件总线
        
        Args:
            payload: 背压事件载荷（包含队列ID、动作、原因、指标等）
        """
        try:
            self._event_bus.publish(EventType.BACKPRESSURE_SIGNAL, payload)
            logger.info(
                "背压事件: queue=%s action=%s reason=%s usage=%.2f drops=%d level=%s state=%s",
                payload.queue_id,
                payload.action,
                payload.reason,
                payload.usage,
                payload.drop_count,
                payload.pressure_level,
                payload.state.value,
            )
        except Exception:
            logger.exception("发布背压事件失败: %s", payload.queue_id)


# 单例实例和锁，用于保证 BackpressureMonitor 只被创建一次，线程安全
_monitor_instance: BackpressureMonitor | None = None
_monitor_lock = threading.Lock()


def initialize_backpressure_monitor(
    config: BackpressureConfig | None = None,
    event_bus: EventBus | None = None,
) -> BackpressureMonitor:
    """
    初始化并返回全局唯一的 BackpressureMonitor 实例。

    - 若未初始化，使用给定参数创建实例。
    - 若已存在实例，传入的 config/event_bus 必须与已存在的保持一致，否则抛出异常。

    Args:
        config: 可选，背压配置。如果已初始化则不可与历史配置不同。
        event_bus: 可选，事件总线。如果已初始化则不可与历史实例不同。

    Returns:
        BackpressureMonitor 单例实例。
    
    Raises:
        ValueError: 初始化参数与已存在实例冲突时抛出。
    """
    global _monitor_instance
    with _monitor_lock:
        if _monitor_instance is None:
            _monitor_instance = BackpressureMonitor(config=config, event_bus=event_bus)
            return _monitor_instance

        # 已有实例，如传入 config 或 event_bus 与已有的不一致，说明使用方式有冲突
        if config is not None and _monitor_instance.config != config:
            raise ValueError("BackpressureMonitor 已初始化，不能重复指定不同 config")
        if event_bus is not None and _monitor_instance._event_bus is not event_bus:
            raise ValueError("BackpressureMonitor 已初始化，不能重复指定不同 event_bus")
        return _monitor_instance


def get_backpressure_monitor() -> BackpressureMonitor:
    """
    获取全局唯一的 BackpressureMonitor 实例。
    
    优先保证只初始化一次，线程安全。
    """
    return initialize_backpressure_monitor()
