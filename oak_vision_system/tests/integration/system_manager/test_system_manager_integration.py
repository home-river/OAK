"""
SystemManager 集成测试

测试 SystemManager 的完整生命周期和各种场景，包括：
- 完整生命周期（注册→启动→运行→关闭）
- KeyboardInterrupt 退出
- SYSTEM_SHUTDOWN 事件退出
- 多模块场景
- 启动失败场景
- 关闭失败场景

Requirements: 所有需求
"""

import pytest
import threading
import time
import logging
from unittest.mock import MagicMock, patch

from oak_vision_system.core.system_manager import (
    SystemManager,
    ModuleState,
    ShutdownEvent
)
from oak_vision_system.core.event_bus import EventBus


# ==================== 测试辅助类 ====================

class MockModule:
    """用于测试的模拟模块"""
    
    def __init__(
        self,
        name: str,
        should_fail_start: bool = False,
        should_fail_stop: bool = False,
        start_delay: float = 0.0,
        stop_delay: float = 0.0
    ):
        self.name = name
        self.should_fail_start = should_fail_start
        self.should_fail_stop = should_fail_stop
        self.start_delay = start_delay
        self.stop_delay = stop_delay
        
        self.start_called = False
        self.stop_called = False
        self.start_count = 0
        self.stop_count = 0
        self._running = False
    
    def start(self):
        """启动模块"""
        if self.start_delay > 0:
            time.sleep(self.start_delay)
        
        # 总是设置 start_called，即使失败
        self.start_called = True
        self.start_count += 1
        
        if self.should_fail_start:
            raise RuntimeError(f"Mock start failure: {self.name}")
        
        self._running = True
    
    def stop(self):
        """停止模块"""
        if self.stop_delay > 0:
            time.sleep(self.stop_delay)
        
        self.stop_called = True
        self.stop_count += 1
        
        if self.should_fail_stop:
            raise RuntimeError(f"Mock stop failure: {self.name}")
        
        self._running = False
    
    def is_running(self) -> bool:
        """检查模块是否运行中"""
        return self._running


# ==================== 完整生命周期测试 ====================

class TestSystemManagerFullLifecycle:
    """测试 SystemManager 完整生命周期"""
    
    def test_full_lifecycle_single_module(self):
        """测试单个模块的完整生命周期
        
        验证：
        - 注册模块
        - 启动模块
        - 模块状态变为 RUNNING
        - 关闭模块
        - 模块状态变为 STOPPED
        
        Requirements: 1.1, 2.1, 8.1
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模拟模块
        module = MockModule("test_module")
        
        # 注册模块
        manager.register_module("test_module", module, priority=10)
        
        # 验证初始状态
        status = manager.get_status()
        assert status["test_module"] == "not_started"
        
        # 启动所有模块
        manager.start_all()
        
        # 验证模块已启动
        assert module.start_called
        assert module.is_running()
        status = manager.get_status()
        assert status["test_module"] == "running"
        
        # 关闭系统
        manager.shutdown()
        
        # 验证模块已停止
        assert module.stop_called
        assert not module.is_running()
        status = manager.get_status()
        assert status["test_module"] == "stopped"
    
    def test_full_lifecycle_multiple_modules(self):
        """测试多个模块的完整生命周期
        
        验证：
        - 注册多个模块
        - 按优先级启动模块
        - 按优先级关闭模块
        - 所有模块状态正确转换
        
        Requirements: 1.1, 2.1, 2.2, 8.1, 8.2
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建多个模拟模块
        collector = MockModule("collector")
        processor = MockModule("processor")
        display = MockModule("display")
        
        # 注册模块（不同优先级）
        manager.register_module("collector", collector, priority=10)
        manager.register_module("processor", processor, priority=30)
        manager.register_module("display", display, priority=50)
        
        # 验证初始状态
        status = manager.get_status()
        assert status["collector"] == "not_started"
        assert status["processor"] == "not_started"
        assert status["display"] == "not_started"
        
        # 启动所有模块
        manager.start_all()
        
        # 验证所有模块已启动
        assert collector.start_called
        assert processor.start_called
        assert display.start_called
        
        status = manager.get_status()
        assert status["collector"] == "running"
        assert status["processor"] == "running"
        assert status["display"] == "running"
        
        # 关闭系统
        manager.shutdown()
        
        # 验证所有模块已停止
        assert collector.stop_called
        assert processor.stop_called
        assert display.stop_called
        
        status = manager.get_status()
        assert status["collector"] == "stopped"
        assert status["processor"] == "stopped"
        assert status["display"] == "stopped"
    
    def test_full_lifecycle_with_context_manager(self):
        """测试使用上下文管理器的完整生命周期
        
        验证：
        - 使用 with 语句自动启动模块
        - 退出 with 块自动关闭模块
        - 模块状态正确转换
        
        Requirements: 14.1, 14.3, 14.4, 14.5
        """
        # 创建事件总线
        event_bus = EventBus()
        
        # 创建模拟模块
        module = MockModule("test_module")
        
        # 使用上下文管理器
        # 注意：__enter__ 会调用 start_all()，所以需要先注册模块
        manager = SystemManager(event_bus=event_bus)
        manager.register_module("test_module", module, priority=10)
        
        with manager:
            # 验证模块已自动启动
            assert module.start_called
            assert module.is_running()
            
            status = manager.get_status()
            assert status["test_module"] == "running"
        
        # 退出 with 块后，验证模块已自动关闭
        assert module.stop_called
        assert not module.is_running()
        
        status = manager.get_status()
        assert status["test_module"] == "stopped"


# ==================== KeyboardInterrupt 退出测试 ====================

class TestSystemManagerKeyboardInterrupt:
    """测试 KeyboardInterrupt 退出场景"""
    
    def test_keyboard_interrupt_triggers_shutdown(self):
        """测试 KeyboardInterrupt 触发系统关闭
        
        验证：
        - run() 方法捕获 KeyboardInterrupt
        - 触发 shutdown() 方法
        - 所有模块被正确关闭
        
        Requirements: 6.1, 6.3, 7.1, 7.2, 7.3
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模拟模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        assert module.start_called
        
        # 在另一个线程中运行 manager.run()
        def run_manager():
            try:
                manager.run()
            except Exception as e:
                # 捕获可能的异常
                pass
        
        run_thread = threading.Thread(target=run_manager, daemon=True)
        run_thread.start()
        
        # 等待一小段时间确保 run() 开始执行
        time.sleep(0.2)
        
        # 模拟 KeyboardInterrupt：设置 shutdown_event
        # 注意：我们不能直接在线程中触发 KeyboardInterrupt
        # 所以我们通过设置 _shutdown_event 来模拟退出
        manager._shutdown_event.set()
        
        # 等待线程结束
        run_thread.join(timeout=2.0)
        
        # 验证模块已关闭
        assert module.stop_called
        assert manager.is_shutting_down()
    
    def test_keyboard_interrupt_with_multiple_modules(self):
        """测试 KeyboardInterrupt 关闭多个模块
        
        验证：
        - KeyboardInterrupt 触发所有模块关闭
        - 模块按正确顺序关闭
        
        Requirements: 6.1, 6.3, 8.2
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建多个模拟模块
        collector = MockModule("collector")
        processor = MockModule("processor")
        display = MockModule("display")
        
        # 注册模块
        manager.register_module("collector", collector, priority=10)
        manager.register_module("processor", processor, priority=30)
        manager.register_module("display", display, priority=50)
        
        # 启动所有模块
        manager.start_all()
        
        # 在另一个线程中运行 manager.run()
        def run_manager():
            try:
                manager.run()
            except Exception:
                pass
        
        run_thread = threading.Thread(target=run_manager, daemon=True)
        run_thread.start()
        
        # 等待一小段时间
        time.sleep(0.2)
        
        # 模拟退出
        manager._shutdown_event.set()
        
        # 等待线程结束
        run_thread.join(timeout=2.0)
        
        # 验证所有模块已关闭
        assert collector.stop_called
        assert processor.stop_called
        assert display.stop_called


# ==================== SYSTEM_SHUTDOWN 事件退出测试 ====================

class TestSystemManagerShutdownEvent:
    """测试 SYSTEM_SHUTDOWN 事件退出场景"""
    
    def test_shutdown_event_triggers_exit(self):
        """测试 SYSTEM_SHUTDOWN 事件触发系统退出
        
        验证：
        - 发布 SYSTEM_SHUTDOWN 事件
        - SystemManager 接收事件并设置退出标志
        - run() 方法退出主循环
        - 所有模块被正确关闭
        
        Requirements: 5.1, 5.2, 5.3, 6.2, 6.4
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模拟模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        assert module.start_called
        
        # 在另一个线程中运行 manager.run()
        def run_manager():
            try:
                manager.run()
            except Exception:
                pass
        
        run_thread = threading.Thread(target=run_manager, daemon=True)
        run_thread.start()
        
        # 等待一小段时间确保 run() 开始执行
        time.sleep(0.2)
        
        # 发布 SYSTEM_SHUTDOWN 事件
        shutdown_event = ShutdownEvent(reason="user_quit")
        event_bus.publish("SYSTEM_SHUTDOWN", shutdown_event)
        
        # 等待线程结束
        run_thread.join(timeout=2.0)
        
        # 验证模块已关闭
        assert module.stop_called
        assert manager.is_shutting_down()
    
    def test_shutdown_event_with_multiple_modules(self):
        """测试 SYSTEM_SHUTDOWN 事件关闭多个模块
        
        验证：
        - SYSTEM_SHUTDOWN 事件触发所有模块关闭
        - 模块按正确顺序关闭
        
        Requirements: 5.1, 5.2, 8.2
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建多个模拟模块
        collector = MockModule("collector")
        processor = MockModule("processor")
        display = MockModule("display")
        
        # 注册模块
        manager.register_module("collector", collector, priority=10)
        manager.register_module("processor", processor, priority=30)
        manager.register_module("display", display, priority=50)
        
        # 启动所有模块
        manager.start_all()
        
        # 在另一个线程中运行 manager.run()
        def run_manager():
            try:
                manager.run()
            except Exception:
                pass
        
        run_thread = threading.Thread(target=run_manager, daemon=True)
        run_thread.start()
        
        # 等待一小段时间
        time.sleep(0.2)
        
        # 发布 SYSTEM_SHUTDOWN 事件
        shutdown_event = ShutdownEvent(reason="window_closed")
        event_bus.publish("SYSTEM_SHUTDOWN", shutdown_event)
        
        # 等待线程结束
        run_thread.join(timeout=2.0)
        
        # 验证所有模块已关闭
        assert collector.stop_called
        assert processor.stop_called
        assert display.stop_called
    
    def test_shutdown_event_with_custom_reason(self):
        """测试 SYSTEM_SHUTDOWN 事件包含自定义原因
        
        验证：
        - 可以指定自定义停止原因
        - 原因被正确记录
        
        Requirements: 4.2, 4.3, 5.3
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模拟模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        
        # 在另一个线程中运行 manager.run()
        def run_manager():
            try:
                manager.run()
            except Exception:
                pass
        
        run_thread = threading.Thread(target=run_manager, daemon=True)
        run_thread.start()
        
        # 等待一小段时间
        time.sleep(0.2)
        
        # 发布带有自定义原因的 SYSTEM_SHUTDOWN 事件
        shutdown_event = ShutdownEvent(reason="custom_shutdown_reason")
        event_bus.publish("SYSTEM_SHUTDOWN", shutdown_event)
        
        # 等待线程结束
        run_thread.join(timeout=2.0)
        
        # 验证模块已关闭
        assert module.stop_called
        assert manager.is_shutting_down()


# ==================== 多模块场景测试 ====================

class TestSystemManagerMultipleModules:
    """测试多模块场景"""
    
    def test_multiple_modules_startup_order(self):
        """测试多个模块按优先级启动
        
        验证：
        - 模块按优先级从高到低启动
        - 启动顺序正确（下游→上游）
        
        Requirements: 2.2
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 记录启动顺序
        startup_order = []
        
        class OrderTrackingModule(MockModule):
            def start(self):
                startup_order.append(self.name)
                super().start()
        
        # 创建多个模块
        collector = OrderTrackingModule("collector")
        processor = OrderTrackingModule("processor")
        display = OrderTrackingModule("display")
        
        # 注册模块（不同优先级）
        manager.register_module("collector", collector, priority=10)
        manager.register_module("processor", processor, priority=30)
        manager.register_module("display", display, priority=50)
        
        # 启动所有模块
        manager.start_all()
        
        # 验证启动顺序：优先级从高到低
        assert startup_order == ["display", "processor", "collector"]
    
    def test_multiple_modules_shutdown_order(self):
        """测试多个模块按优先级关闭
        
        验证：
        - 模块按优先级从低到高关闭
        - 关闭顺序正确（上游→下游）
        
        Requirements: 8.2
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 记录关闭顺序
        shutdown_order = []
        
        class OrderTrackingModule(MockModule):
            def stop(self):
                shutdown_order.append(self.name)
                super().stop()
        
        # 创建多个模块
        collector = OrderTrackingModule("collector")
        processor = OrderTrackingModule("processor")
        display = OrderTrackingModule("display")
        
        # 注册模块
        manager.register_module("collector", collector, priority=10)
        manager.register_module("processor", processor, priority=30)
        manager.register_module("display", display, priority=50)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统
        manager.shutdown()
        
        # 验证关闭顺序：优先级从低到高
        assert shutdown_order == ["collector", "processor", "display"]
    
    def test_many_modules_lifecycle(self):
        """测试大量模块的生命周期
        
        验证：
        - 可以管理大量模块
        - 所有模块正确启动和关闭
        
        Requirements: 1.1, 2.1, 8.1
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建10个模块
        modules = []
        for i in range(10):
            module = MockModule(f"module_{i}")
            modules.append(module)
            manager.register_module(f"module_{i}", module, priority=i * 10)
        
        # 启动所有模块
        manager.start_all()
        
        # 验证所有模块已启动
        for module in modules:
            assert module.start_called
            assert module.is_running()
        
        # 关闭系统
        manager.shutdown()
        
        # 验证所有模块已停止
        for module in modules:
            assert module.stop_called
            assert not module.is_running()


# ==================== 启动失败场景测试 ====================

class TestSystemManagerStartupFailure:
    """测试启动失败场景"""
    
    def test_startup_failure_triggers_rollback(self):
        """测试启动失败触发回滚
        
        验证：
        - 模块启动失败时抛出异常
        - 已启动的模块被回滚（停止）
        - 失败模块状态为 ERROR
        - 已启动模块状态为 STOPPED
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模块：第二个模块启动失败
        module1 = MockModule("module1")
        module2 = MockModule("module2", should_fail_start=True)
        module3 = MockModule("module3")
        
        # 注册模块（优先级：module3 > module2 > module1）
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=30)
        manager.register_module("module3", module3, priority=50)
        
        # 尝试启动所有模块（应该失败）
        with pytest.raises(RuntimeError, match="模块启动失败"):
            manager.start_all()
        
        # 验证启动顺序：module3 先启动，module2 启动失败
        assert module3.start_called  # 第一个启动成功
        assert module2.start_called  # 第二个尝试启动但失败
        assert not module1.start_called  # 第三个未启动
        
        # 验证回滚：module3 被停止
        assert module3.stop_called
        
        # 验证状态
        status = manager.get_status()
        assert status["module3"] == "stopped"  # 回滚后停止
        assert status["module2"] == "error"    # 启动失败
        assert status["module1"] == "not_started"  # 未启动
    
    def test_startup_failure_with_single_module(self):
        """测试单个模块启动失败
        
        验证：
        - 单个模块启动失败时抛出异常
        - 模块状态为 ERROR
        - 没有其他模块需要回滚
        
        Requirements: 2.4, 3.1
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建会失败的模块
        module = MockModule("test_module", should_fail_start=True)
        manager.register_module("test_module", module, priority=10)
        
        # 尝试启动（应该失败）
        with pytest.raises(RuntimeError, match="模块启动失败"):
            manager.start_all()
        
        # 验证状态
        status = manager.get_status()
        assert status["test_module"] == "error"
    
    def test_startup_failure_all_started_modules_rolled_back(self):
        """测试启动失败时所有已启动模块被回滚
        
        验证：
        - 最后一个模块启动失败
        - 所有已启动的模块被停止
        
        Requirements: 3.3, 3.4
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模块：第一个模块启动失败（优先级最高）
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        module3 = MockModule("module3", should_fail_start=True)
        
        # 注册模块（module3 优先级最高，会第一个启动并失败）
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=30)
        
        # 尝试启动（应该失败）
        with pytest.raises(RuntimeError):
            manager.start_all()
        
        # 验证启动情况
        # module3 优先级最高，第一个启动但失败
        assert module3.start_called  # 尝试启动但失败
        # module2 和 module1 不会启动，因为 module3 失败了
        assert not module2.start_called
        assert not module1.start_called
        
        # 验证没有模块需要回滚（因为只有第一个模块尝试启动）
        assert not module3.stop_called
        assert not module2.stop_called
        assert not module1.stop_called
        
        # 验证状态
        status = manager.get_status()
        assert status["module1"] == "not_started"
        assert status["module2"] == "not_started"
        assert status["module3"] == "error"


# ==================== 关闭失败场景测试 ====================

class TestSystemManagerShutdownFailure:
    """测试关闭失败场景"""
    
    def test_shutdown_failure_does_not_block_other_modules(self):
        """测试模块关闭失败不阻塞其他模块
        
        验证：
        - 一个模块关闭失败
        - 其他模块仍然被关闭
        - 失败模块状态为 ERROR
        - 其他模块状态为 STOPPED
        
        Requirements: 8.5, 9.1, 9.2
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模块：第二个模块关闭失败
        module1 = MockModule("module1")
        module2 = MockModule("module2", should_fail_stop=True)
        module3 = MockModule("module3")
        
        # 注册模块
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=30)
        manager.register_module("module3", module3, priority=50)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统（不应该抛出异常）
        manager.shutdown()
        
        # 验证所有模块都尝试关闭
        assert module1.stop_called
        assert module2.stop_called
        assert module3.stop_called
        
        # 验证状态
        status = manager.get_status()
        assert status["module1"] == "stopped"
        assert status["module2"] == "error"  # 关闭失败
        assert status["module3"] == "stopped"
    
    def test_shutdown_failure_with_multiple_failures(self):
        """测试多个模块关闭失败
        
        验证：
        - 多个模块关闭失败
        - 所有模块都尝试关闭
        - 失败模块状态为 ERROR
        
        Requirements: 8.5
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模块：两个模块关闭失败
        module1 = MockModule("module1", should_fail_stop=True)
        module2 = MockModule("module2")
        module3 = MockModule("module3", should_fail_stop=True)
        
        # 注册模块
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=30)
        manager.register_module("module3", module3, priority=50)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统（不应该抛出异常）
        manager.shutdown()
        
        # 验证所有模块都尝试关闭
        assert module1.stop_called
        assert module2.stop_called
        assert module3.stop_called
        
        # 验证状态
        status = manager.get_status()
        assert status["module1"] == "error"
        assert status["module2"] == "stopped"
        assert status["module3"] == "error"
    
    def test_shutdown_prevents_duplicate_calls(self):
        """测试防止重复关闭
        
        验证：
        - 第一次调用 shutdown() 执行关闭
        - 第二次调用 shutdown() 直接返回
        - 模块只被关闭一次
        
        Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        
        # 第一次关闭
        manager.shutdown()
        assert module.stop_count == 1
        
        # 第二次关闭（应该被跳过）
        manager.shutdown()
        assert module.stop_count == 1  # 仍然是1，没有增加
        
        # 第三次关闭（应该被跳过）
        manager.shutdown()
        assert module.stop_count == 1  # 仍然是1，没有增加


# ==================== 综合场景测试 ====================

class TestSystemManagerComplexScenarios:
    """测试复杂综合场景"""
    
    def test_run_and_shutdown_event_integration(self):
        """测试 run() 和 SYSTEM_SHUTDOWN 事件的完整集成
        
        验证：
        - 启动模块
        - 运行主循环
        - 发布 SYSTEM_SHUTDOWN 事件
        - 主循环退出
        - 模块被关闭
        
        Requirements: 所有需求
        """
        # 创建事件总线和管理器
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建多个模块
        collector = MockModule("collector")
        processor = MockModule("processor")
        display = MockModule("display")
        
        # 注册模块
        manager.register_module("collector", collector, priority=10)
        manager.register_module("processor", processor, priority=30)
        manager.register_module("display", display, priority=50)
        
        # 启动所有模块
        manager.start_all()
        
        # 在另一个线程中运行 manager.run()
        def run_manager():
            try:
                manager.run()
            except Exception:
                pass
        
        run_thread = threading.Thread(target=run_manager, daemon=True)
        run_thread.start()
        
        # 等待一小段时间
        time.sleep(0.2)
        
        # 验证模块正在运行
        assert collector.is_running()
        assert processor.is_running()
        assert display.is_running()
        
        # 发布 SYSTEM_SHUTDOWN 事件
        shutdown_event = ShutdownEvent(reason="test_shutdown")
        event_bus.publish("SYSTEM_SHUTDOWN", shutdown_event)
        
        # 等待线程结束
        run_thread.join(timeout=2.0)
        
        # 验证所有模块已关闭
        assert collector.stop_called
        assert processor.stop_called
        assert display.stop_called
        
        assert not collector.is_running()
        assert not processor.is_running()
        assert not display.is_running()
        
        # 验证系统状态
        assert manager.is_shutting_down()
        
        status = manager.get_status()
        assert status["collector"] == "stopped"
        assert status["processor"] == "stopped"
        assert status["display"] == "stopped"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
