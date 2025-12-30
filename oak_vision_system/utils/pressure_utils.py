from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from oak_vision_system.core.backpressure import BackpressureMonitor
"""
背压模块工具函数
"""

def register_all(monitor: BackpressureMonitor, *modules) -> None:
    """
    注册所有模块的背压队列到背压监控器
    """
    for module in modules:
        for reg in module.get_backpressure_registrations():
            monitor.register_queue(reg.queue_id, reg.metrics_provider, reg.capacity)

def unregister_all(monitor:BackpressureMonitor, *modules) -> None:
    """
    注销所有模块的背压队列到背压监控器
    """
    for module in modules:
        for reg in module.get_backpressure_registrations():
            monitor.unregister_queue(reg.queue_id)
