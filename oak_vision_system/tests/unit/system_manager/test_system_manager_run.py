"""
SystemManager 主循环单元测试

测试 SystemManager 的 run() 方法功能，包括：
- 主循环阻塞（使用线程）
- SYSTEM_SHUTDOWN 事件触发退出
- finally 块调用 shutdown()
- 验证日志记录

Requirements: 6.3, 6.4, 6.6, 7.2, 7.3, 7.5, 7.6
"""

import logging
import threading
import time
import pytest
from unittest.mock import Mock, patch, MagicMock

from oak_vision_system.core.system_manager import (
    SystemManager,
    ShutdownEvent,
)
from oak_vision_system.core.event_bus import EventBus


class MockModule:
    """用于测试的模拟模块"""
    
    def __init__(self, name: str = "mock"):
        self.name = name
        self.start_called = False
        self.stop_called = False
        self._running = False
    
    def start(self):
        """启动模块"""
        self.start_called = True
        self._running = True
    
    def stop(self):
        """停止模块"""
        self.stop_called = True
        self._running = False
    
    def is_running(self):
        """检查模块是否运行中"""
        return self._running


class TestSystemManagerRun:
    """SystemManager run() 方法测试套件"""
    
    @pytest.fixture
    def event_bus(self):
        """创建事件总线实例"""
        return EventBus()
    
    @pytest.fixture
    def manager(self, event_bus):
        """创建 SystemManager 实例"""
        return SystemManager(event_bus=event_bus)
    
    def test_run_blocks_main_thread(self, manager):
        """测试 run() 方法阻塞主线程"""
        # 创建一个标志来跟踪 run() 是否在运行
        run_started = threading.Event()
        run_finished = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
            run_finished.set()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0), "run() 方法未能在 1 秒内启动"
        
        # 等待一小段时间，验证 run() 仍在阻塞
        time.sleep(0.2)
        assert thread.is_alive(), "run() 方法应该阻塞主线程"
        assert not run_finished.is_set(), "run() 方法不应该立即返回"
        
        # 触发退出信号
        manager._shutdown_event.set()
        
        # 等待 run() 完成
        assert run_finished.wait(timeout=2.0), "run() 方法未能在 2 秒内完成"
        thread.join(timeout=1.0)
    
    def test_run_exits_on_shutdown_event(self, event_bus, manager, caplog):
        """测试 SYSTEM_SHUTDOWN 事件触发 run() 退出"""
        caplog.set_level(logging.INFO)
        
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        run_finished = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
            run_finished.set()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 验证 run() 正在阻塞
        time.sleep(0.2)
        assert thread.is_alive()
        
        # 发布 SYSTEM_SHUTDOWN 事件
        event = ShutdownEvent(reason="test_exit")
        event_bus.publish("SYSTEM_SHUTDOWN", event)
        
        # 等待 run() 完成
        assert run_finished.wait(timeout=2.0), "run() 应该在接收到 SYSTEM_SHUTDOWN 事件后退出"
        thread.join(timeout=1.0)
        
        # 验证日志记录
        log_messages = [record.message for record in caplog.records]
        assert any("接收到退出事件" in msg for msg in log_messages)
        assert any("接收到退出信号" in msg or "准备关闭系统" in msg for msg in log_messages)
    
    def test_run_calls_shutdown_in_finally(self, manager):
        """测试 run() 在 finally 块中调用 shutdown()"""
        # Mock shutdown 方法
        original_shutdown = manager.shutdown
        shutdown_called = threading.Event()
        
        def mock_shutdown():
            """Mock shutdown 方法"""
            shutdown_called.set()
            # 设置 _stop_started 防止重复调用
            manager._stop_started.set()
        
        manager.shutdown = mock_shutdown
        
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        run_finished = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
            run_finished.set()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 触发退出信号
        manager._shutdown_event.set()
        
        # 等待 run() 完成
        assert run_finished.wait(timeout=2.0)
        thread.join(timeout=1.0)
        
        # 验证 shutdown() 被调用
        assert shutdown_called.is_set(), "shutdown() 应该在 finally 块中被调用"
        
        # 恢复原始方法
        manager.shutdown = original_shutdown
    
    def test_run_logs_startup_message(self, manager, caplog):
        """测试 run() 记录启动日志"""
        caplog.set_level(logging.INFO)
        
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 等待日志记录
        time.sleep(0.1)
        
        # 触发退出
        manager._shutdown_event.set()
        thread.join(timeout=2.0)
        
        # 验证启动日志
        log_messages = [record.message for record in caplog.records]
        assert any("SystemManager 开始运行" in msg for msg in log_messages)
        assert any("等待退出信号" in msg for msg in log_messages)
    
    def test_run_logs_exit_message(self, manager, caplog):
        """测试 run() 记录退出日志"""
        caplog.set_level(logging.INFO)
        
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 触发退出信号
        manager._shutdown_event.set()
        thread.join(timeout=2.0)
        
        # 验证退出日志
        log_messages = [record.message for record in caplog.records]
        assert any("接收到退出信号" in msg or "准备关闭系统" in msg for msg in log_messages)
    
    def test_run_prevents_duplicate_shutdown(self, manager):
        """测试 run() 防止重复调用 shutdown()"""
        # 预先设置 _stop_started 标志
        manager._stop_started.set()
        
        # Mock shutdown 方法
        shutdown_call_count = [0]
        original_shutdown = manager.shutdown
        
        def mock_shutdown():
            """Mock shutdown 方法"""
            shutdown_call_count[0] += 1
        
        manager.shutdown = mock_shutdown
        
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 触发退出信号
        manager._shutdown_event.set()
        thread.join(timeout=2.0)
        
        # 验证 shutdown() 没有被调用（因为 _stop_started 已设置）
        assert shutdown_call_count[0] == 0, "shutdown() 不应该被调用，因为 _stop_started 已设置"
        
        # 恢复原始方法
        manager.shutdown = original_shutdown
    
    def test_run_with_multiple_shutdown_events(self, event_bus, manager):
        """测试 run() 处理多个 SYSTEM_SHUTDOWN 事件"""
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        run_finished = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
            run_finished.set()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 发布多个 SYSTEM_SHUTDOWN 事件
        for i in range(5):
            event = ShutdownEvent(reason=f"event_{i}")
            event_bus.publish("SYSTEM_SHUTDOWN", event)
            time.sleep(0.05)
        
        # 等待 run() 完成
        assert run_finished.wait(timeout=2.0)
        thread.join(timeout=1.0)
    
    def test_run_waits_with_timeout(self, manager):
        """测试 run() 使用 timeout 等待，不消耗 CPU"""
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 等待一段时间，验证线程仍在运行
        time.sleep(1.0)
        assert thread.is_alive(), "run() 应该持续阻塞"
        
        # 触发退出
        manager._shutdown_event.set()
        thread.join(timeout=2.0)


class TestSystemManagerRunWithKeyboardInterrupt:
    """SystemManager run() 方法 KeyboardInterrupt 测试套件"""
    
    @pytest.fixture
    def event_bus(self):
        """创建事件总线实例"""
        return EventBus()
    
    @pytest.fixture
    def manager(self, event_bus):
        """创建 SystemManager 实例"""
        return SystemManager(event_bus=event_bus)
    
    def test_run_catches_keyboard_interrupt(self, manager, caplog):
        """测试 run() 捕获 KeyboardInterrupt"""
        caplog.set_level(logging.INFO)
        
        # Mock Event.wait 方法抛出 KeyboardInterrupt
        original_wait = manager._shutdown_event.wait
        
        def mock_wait(timeout=None):
            """Mock wait 方法，抛出 KeyboardInterrupt"""
            raise KeyboardInterrupt()
        
        manager._shutdown_event.wait = mock_wait
        
        # Mock shutdown 方法
        shutdown_called = threading.Event()
        
        def mock_shutdown():
            """Mock shutdown 方法"""
            shutdown_called.set()
            manager._stop_started.set()
        
        manager.shutdown = mock_shutdown
        
        # 调用 run() 不应该抛出异常
        try:
            manager.run()
        except KeyboardInterrupt:
            pytest.fail("run() 应该捕获 KeyboardInterrupt，不应该向外抛出")
        
        # 验证 shutdown() 被调用
        assert shutdown_called.is_set(), "shutdown() 应该在 finally 块中被调用"
        
        # 验证日志记录
        log_messages = [record.message for record in caplog.records]
        assert any("KeyboardInterrupt" in msg or "Ctrl+C" in msg for msg in log_messages)
    
    def test_run_logs_keyboard_interrupt(self, manager, caplog):
        """测试 run() 记录 KeyboardInterrupt 日志"""
        caplog.set_level(logging.INFO)
        
        # Mock Event.wait 方法抛出 KeyboardInterrupt
        def mock_wait(timeout=None):
            """Mock wait 方法，抛出 KeyboardInterrupt"""
            raise KeyboardInterrupt()
        
        manager._shutdown_event.wait = mock_wait
        
        # Mock shutdown 方法
        def mock_shutdown():
            """Mock shutdown 方法"""
            manager._stop_started.set()
        
        manager.shutdown = mock_shutdown
        
        # 调用 run()
        manager.run()
        
        # 验证日志记录
        log_messages = [record.message for record in caplog.records]
        assert any("KeyboardInterrupt" in msg for msg in log_messages)
        assert any("Ctrl+C" in msg for msg in log_messages)
        assert any("准备关闭系统" in msg for msg in log_messages)


class TestSystemManagerRunIntegration:
    """SystemManager run() 方法集成测试"""
    
    @pytest.fixture
    def event_bus(self):
        """创建事件总线实例"""
        return EventBus()
    
    @pytest.fixture
    def manager(self, event_bus):
        """创建 SystemManager 实例"""
        return SystemManager(event_bus=event_bus)
    
    def test_run_with_registered_modules(self, manager):
        """测试 run() 与注册的模块一起工作"""
        # 注册模块
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        
        # 启动模块
        manager.start_all()
        
        # 验证模块已启动
        assert module1.start_called
        assert module2.start_called
        
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 验证 run() 正在阻塞
        time.sleep(0.2)
        assert thread.is_alive()
        
        # 触发退出
        manager._shutdown_event.set()
        thread.join(timeout=2.0)
    
    def test_run_complete_lifecycle(self, event_bus, manager, caplog):
        """测试 run() 完整生命周期"""
        caplog.set_level(logging.INFO)
        
        # 注册模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        
        # 创建标志跟踪 run() 状态
        run_started = threading.Event()
        run_finished = threading.Event()
        
        def run_in_thread():
            """在线程中运行 run() 方法"""
            run_started.set()
            manager.run()
            run_finished.set()
        
        # 在新线程中启动 run()
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # 等待 run() 开始执行
        assert run_started.wait(timeout=1.0)
        
        # 发布 SYSTEM_SHUTDOWN 事件
        event = ShutdownEvent(reason="test_complete")
        event_bus.publish("SYSTEM_SHUTDOWN", event)
        
        # 等待 run() 完成
        assert run_finished.wait(timeout=2.0)
        thread.join(timeout=1.0)
        
        # 验证日志记录了完整流程
        log_messages = [record.message for record in caplog.records]
        assert any("SystemManager 开始运行" in msg for msg in log_messages)
        assert any("接收到退出事件" in msg for msg in log_messages)
        assert any("接收到退出信号" in msg or "准备关闭系统" in msg for msg in log_messages)


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
