"""
测试工具框架（Test Harness）

提供通用的测试工具基类，用于模块的单独测试和数据分析。

主要组件：
- BaseTestHarness: 测试工具基类，提供事件订阅、生命周期管理、日志记录框架
- CollectorReceiver: Collector 数据接收器，使用双队列处理视频帧和检测数据
"""

from oak_vision_system.tests.harness.base_harness import BaseTestHarness
from oak_vision_system.tests.harness.collector_receiver import CollectorReceiver

__all__ = [
    "BaseTestHarness",
    "CollectorReceiver",
]
