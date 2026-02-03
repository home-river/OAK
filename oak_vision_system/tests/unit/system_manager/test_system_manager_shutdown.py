"""
SystemManager 模块关闭单元测试

测试 SystemManager 类的模块关闭功能，包括：
- 关闭单个模块
- 关闭多个模块
- 防重复关闭
- 关闭失败不阻塞其他模块
- 事件总线关闭
- 验证日志记录

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.4
"""

import pytest
import logging
from unittest.mock import MagicMock, patch
from oak_vision_system.core.system_manager import SystemManager, ModuleState
from oak_vision_system.core.event_bus import EventBus


class MockModule:
    """用于测试的模拟模块"""
    
    def __init__(self, name: str = "mock_module", should_fail_stop: bool = False):
        self.name = name
        self.should_fail_stop = should_fail_stop
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
        if self.should_fail_stop:
            raise RuntimeError(f"Mock stop failure: {self.name}")
        self._running = False
    
    def is_running(self):
        """检查模块是否运行中"""
        return self._running


class TestSystemManagerShutdown:
    """SystemManager 模块关闭测试套件"""
    
    def test_shutdown_single_module(self):
        """测试关闭单个模块
        
        验证：
        - 可以成功关闭单个模块
        - 模块的 stop() 方法被调用
        - 模块状态变为 STOPPED
        
        Requirements: 8.1, 8.3, 8.4
        """
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模拟模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        assert module.start_called is True
        assert manager._modules["test_module"].state == ModuleState.RUNNING
        
        # 关闭系统
        manager.shutdown()
        
        # 验证模块的 stop() 方法被调用
        assert module.stop_called is True
        assert module.is_running() is False
        
        # 验证模块状态变为 STOPPED
        assert manager._modules["test_module"].state == ModuleState.STOPPED
    
    def test_shutdown_multiple_modules(self):
        """测试关闭多个模块
        
        验证：
        - 可以成功关闭多个模块
        - 所有模块的 stop() 方法都被调用
        - 所有模块状态都变为 STOPPED
        
        Requirements: 8.1, 8.3, 8.4
        """
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册多个模拟模块
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        module3 = MockModule("module3")
        
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=30)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统
        manager.shutdown()
        
        # 验证所有模块的 stop() 方法都被调用
        assert module1.stop_called is True
        assert module2.stop_called is True
        assert module3.stop_called is True
        
        # 验证所有模块都已停止
        assert module1.is_running() is False
        assert module2.is_running() is False
        assert module3.is_running() is False
        
        # 验证所有模块状态都变为 STOPPED
        assert manager._modules["module1"].state == ModuleState.STOPPED
        assert manager._modules["module2"].state == ModuleState.STOPPED
        assert manager._modules["module3"].state == ModuleState.STOPPED
    
    def test_shutdown_by_priority_order(self):
        """测试模块按优先级顺序关闭
        
        验证：
        - 模块按优先级从低到高关闭（上游→下游）
        - 优先级低的模块先关闭
        
        Requirements: 8.2
        """
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 记录关闭顺序
        stop_order = []
        
        # 创建带关闭顺序记录的模拟模块
        class OrderedMockModule(MockModule):
            def stop(self):
                stop_order.append(self.name)
                super().stop()
        
        # 注册不同优先级的模块（故意打乱注册顺序）
        module_low = OrderedMockModule("low_priority")
        module_high = OrderedMockModule("high_priority")
        module_medium = OrderedMockModule("medium_priority")
        
        manager.register_module("low_priority", module_low, priority=10)
        manager.register_module("high_priority", module_high, priority=50)
        manager.register_module("medium_priority", module_medium, priority=30)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统
        manager.shutdown()
        
        # 验证关闭顺序：优先级从低到高
        assert stop_order == ["low_priority", "medium_priority", "high_priority"]
        
        # 验证所有模块都关闭成功
        assert module_low.stop_called is True
        assert module_high.stop_called is True
        assert module_medium.stop_called is True
    
    def test_shutdown_prevents_duplicate_calls(self):
        """测试防重复关闭
        
        验证：
        - 第一次调用 shutdown() 正常执行
        - 第二次调用 shutdown() 直接返回，不重复关闭
        - 模块的 stop() 方法只被调用一次
        
        Requirements: 9.1, 9.2, 9.3, 9.4
        """
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        
        # 第一次关闭
        manager.shutdown()
        assert module.stop_called is True
        
        # 重置 stop_called 标志
        module.stop_called = False
        
        # 第二次关闭（应该直接返回）
        manager.shutdown()
        
        # 验证 stop() 方法没有被再次调用
        assert module.stop_called is False
    
    def test_shutdown_failure_does_not_block_other_modules(self):
        """测试关闭失败不阻塞其他模块
        
        验证：
        - 当一个模块关闭失败时，其他模块仍然被关闭
        - 失败的模块状态变为 ERROR
        - 成功的模块状态变为 STOPPED
        
        Requirements: 8.5, 9.5
        """
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模块：第二个模块会失败
        module1 = MockModule("module1", should_fail_stop=False)
        module2 = MockModule("module2", should_fail_stop=True)  # 会失败
        module3 = MockModule("module3", should_fail_stop=False)
        
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=30)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统（module2 会失败，但不应该抛出异常）
        manager.shutdown()
        
        # 验证所有模块的 stop() 方法都被调用
        assert module1.stop_called is True
        assert module2.stop_called is True
        assert module3.stop_called is True
        
        # 验证失败的模块状态为 ERROR
        assert manager._modules["module2"].state == ModuleState.ERROR
        
        # 验证成功的模块状态为 STOPPED
        assert manager._modules["module1"].state == ModuleState.STOPPED
        assert manager._modules["module3"].state == ModuleState.STOPPED
    
    def test_shutdown_closes_event_bus(self):
        """测试关闭事件总线
        
        验证：
        - shutdown() 调用事件总线的 close() 方法
        - 使用正确的参数（wait=True, cancel_pending=False）
        
        Requirements: 10.1, 10.2, 10.3
        """
        # 创建自定义事件总线（用于监控 close 调用）
        event_bus = EventBus()
        
        # 创建 SystemManager
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        
        # Mock 事件总线的 close 方法
        with patch.object(event_bus, 'close') as mock_close:
            # 关闭系统
            manager.shutdown()
            
            # 验证 close() 被调用，且参数正确
            mock_close.assert_called_once_with(wait=True, cancel_pending=False)
    
    def test_shutdown_event_bus_failure_does_not_raise(self):
        """测试事件总线关闭失败不抛出异常
        
        验证：
        - 当事件总线关闭失败时，捕获异常
        - shutdown() 方法不抛出异常
        - 继续执行后续清理
        
        Requirements: 10.4
        """
        # 创建自定义事件总线
        event_bus = EventBus()
        
        # 创建 SystemManager
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        
        # Mock 事件总线的 close 方法，使其抛出异常
        with patch.object(event_bus, 'close', side_effect=RuntimeError("Close failed")):
            # 关闭系统（不应该抛出异常）
            manager.shutdown()
            
            # 验证模块仍然被关闭
            assert module.stop_called is True
            assert manager._modules["test_module"].state == ModuleState.STOPPED
    
    def test_shutdown_logs_shutdown_info(self, caplog):
        """测试关闭时记录日志
        
        验证：
        - 记录开始关闭的日志
        - 记录每个模块的关闭日志
        - 记录关闭成功的日志
        - 日志包含模块名称和优先级
        
        Requirements: 13.2, 13.4
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建独立的事件总线和 SystemManager

            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建并注册模块
            module1 = MockModule("module1")
            module2 = MockModule("module2")
            
            manager.register_module("module1", module1, priority=10)
            manager.register_module("module2", module2, priority=20)
            
            # 启动所有模块
            manager.start_all()
            
            # 清空之前的日志
            caplog.clear()
            
            # 关闭系统
            manager.shutdown()
            
            # 验证日志记录
            log_messages = [record.message for record in caplog.records]
            
            # 验证包含开始关闭的日志
            assert any("开始关闭系统" in msg for msg in log_messages)
            
            # 验证包含每个模块的关闭日志
            assert any("module1" in msg and "停止模块" in msg for msg in log_messages)
            assert any("module2" in msg and "停止模块" in msg for msg in log_messages)
            
            # 验证包含关闭成功的日志
            assert any("module1" in msg and "停止成功" in msg for msg in log_messages)
            assert any("module2" in msg and "停止成功" in msg for msg in log_messages)
            
            # 验证包含完成日志
            assert any("关闭完成" in msg for msg in log_messages)
    
    def test_shutdown_logs_failure(self, caplog):
        """测试关闭失败时记录错误日志
        
        验证：
        - 当模块关闭失败时，记录 ERROR 级别日志
        - 日志包含模块名称和错误信息
        
        Requirements: 8.5, 13.4
        """
        # 设置日志级别为 ERROR
        with caplog.at_level(logging.ERROR):
            # 创建独立的事件总线和 SystemManager

            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建会失败的模块
            module = MockModule("failing_module", should_fail_stop=True)
            manager.register_module("failing_module", module, priority=10)
            
            # 启动模块
            manager.start_all()
            
            # 清空之前的日志
            caplog.clear()
            
            # 关闭系统
            manager.shutdown()
            
            # 验证有 ERROR 级别的日志
            error_logs = [record for record in caplog.records if record.levelno == logging.ERROR]
            assert len(error_logs) > 0
            
            # 验证错误日志包含模块名称
            error_messages = [record.message for record in error_logs]
            assert any("failing_module" in msg for msg in error_messages)
            assert any("停止模块失败" in msg for msg in error_messages)
    
    def test_shutdown_skips_non_running_modules(self):
        """测试关闭时跳过非 RUNNING 状态的模块
        
        验证：
        - 只关闭 RUNNING 状态的模块
        - 跳过 NOT_STARTED 状态的模块
        - 跳过 STOPPED 状态的模块
        
        Requirements: 8.1, 9.1
        """
        # 创建独立的事件总线和 SystemManager

        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模块
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        module3 = MockModule("module3")
        
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=30)
        
        # 只启动 module1 和 module2
        manager._modules["module1"].instance.start()
        manager._modules["module1"].state = ModuleState.RUNNING
        
        manager._modules["module2"].instance.start()
        manager._modules["module2"].state = ModuleState.RUNNING
        
        # module3 保持 NOT_STARTED 状态
        
        # 关闭系统
        manager.shutdown()
        
        # 验证只有 RUNNING 状态的模块被关闭
        assert module1.stop_called is True
        assert module2.stop_called is True
        assert module3.stop_called is False  # 未启动，不应该被关闭
        
        # 验证状态
        assert manager._modules["module1"].state == ModuleState.STOPPED
        assert manager._modules["module2"].state == ModuleState.STOPPED
        assert manager._modules["module3"].state == ModuleState.NOT_STARTED


class TestSystemManagerShutdownEdgeCases:
    """SystemManager 模块关闭边界情况测试"""
    
    def test_shutdown_empty_modules_list(self):
        """测试关闭空模块列表
        
        验证：
        - 没有注册模块时可以正常调用 shutdown()
        - 不抛出异常
        
        Requirements: 8.1
        """
        # 创建 SystemManager（不注册任何模块）
        manager = SystemManager()
        
        # 关闭系统（应该不抛出异常）
        manager.shutdown()
        
        # 验证没有模块
        assert len(manager._modules) == 0
    
    def test_shutdown_without_start(self):
        """测试未启动就关闭
        
        验证：
        - 可以在未调用 start_all() 的情况下调用 shutdown()
        - 不抛出异常
        - 模块的 stop() 方法不被调用（因为未启动）
        
        Requirements: 8.1, 9.1
        """
        # 创建独立的事件总线和 SystemManager

        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模块（但不启动）
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 验证模块未启动
        assert manager._modules["test_module"].state == ModuleState.NOT_STARTED
        
        # 关闭系统
        manager.shutdown()
        
        # 验证 stop() 方法未被调用（因为模块未启动）
        assert module.stop_called is False
        
        # 验证状态仍然是 NOT_STARTED
        assert manager._modules["test_module"].state == ModuleState.NOT_STARTED
    
    def test_shutdown_with_same_priority_modules(self):
        """测试关闭相同优先级的模块
        
        验证：
        - 可以关闭相同优先级的模块
        - 所有模块都能成功关闭
        
        Requirements: 8.1, 8.2
        """
        # 创建独立的事件总线和 SystemManager

        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册相同优先级的模块
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        module3 = MockModule("module3")
        
        manager.register_module("module1", module1, priority=20)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=20)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统
        manager.shutdown()
        
        # 验证所有模块都关闭成功
        assert module1.stop_called is True
        assert module2.stop_called is True
        assert module3.stop_called is True
        
        # 验证所有模块状态都为 STOPPED
        assert manager._modules["module1"].state == ModuleState.STOPPED
        assert manager._modules["module2"].state == ModuleState.STOPPED
        assert manager._modules["module3"].state == ModuleState.STOPPED
    
    def test_shutdown_many_modules(self):
        """测试关闭大量模块
        
        验证：
        - 可以关闭大量模块
        - 所有模块都能成功关闭
        - 性能可接受
        
        Requirements: 8.1
        """
        # 创建独立的事件总线和 SystemManager

        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册100个模块
        num_modules = 100
        modules = []
        for i in range(num_modules):
            module = MockModule(f"module_{i}")
            modules.append(module)
            manager.register_module(f"module_{i}", module, priority=i)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统
        manager.shutdown()
        
        # 验证所有模块都关闭成功
        for module in modules:
            assert module.stop_called is True
            assert module.is_running() is False
        
        # 验证所有模块状态都为 STOPPED
        for i in range(num_modules):
            assert manager._modules[f"module_{i}"].state == ModuleState.STOPPED
    
    def test_shutdown_all_modules_fail(self):
        """测试所有模块关闭都失败
        
        验证：
        - 当所有模块关闭都失败时，不抛出异常
        - 所有模块状态都变为 ERROR
        - 仍然尝试关闭事件总线
        
        Requirements: 8.5, 9.5
        """
        # 创建独立的事件总线和 SystemManager

        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建都会失败的模块
        module1 = MockModule("module1", should_fail_stop=True)
        module2 = MockModule("module2", should_fail_stop=True)
        module3 = MockModule("module3", should_fail_stop=True)
        
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=30)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭系统（不应该抛出异常）
        manager.shutdown()
        
        # 验证所有模块的 stop() 方法都被调用
        assert module1.stop_called is True
        assert module2.stop_called is True
        assert module3.stop_called is True
        
        # 验证所有模块状态都为 ERROR
        assert manager._modules["module1"].state == ModuleState.ERROR
        assert manager._modules["module2"].state == ModuleState.ERROR
        assert manager._modules["module3"].state == ModuleState.ERROR


class TestSystemManagerShutdownLogging:
    """SystemManager 模块关闭日志测试"""
    
    def test_shutdown_logs_at_info_level(self, caplog):
        """测试关闭日志使用 INFO 级别
        
        验证：
        - 关闭日志使用 INFO 级别
        - 不使用 DEBUG 或 WARNING 级别（除非有错误）
        
        Requirements: 13.2
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建独立的事件总线和 SystemManager

            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建并注册模块
            module = MockModule("test_module")
            manager.register_module("test_module", module, priority=10)
            
            # 启动模块
            manager.start_all()
            
            # 清空之前的日志
            caplog.clear()
            
            # 关闭系统
            manager.shutdown()
            
            # 验证有 INFO 级别的日志
            info_logs = [record for record in caplog.records if record.levelno == logging.INFO]
            assert len(info_logs) > 0
            
            # 验证关闭相关的日志都是 INFO 级别
            shutdown_logs = [
                record for record in caplog.records
                if "关闭" in record.message or "停止" in record.message
            ]
            for log in shutdown_logs:
                # 只要不是错误日志，应该是 INFO 级别
                if "失败" not in log.message:
                    assert log.levelno == logging.INFO
    
    def test_shutdown_logs_priority_info(self, caplog):
        """测试关闭日志包含优先级信息
        
        验证：
        - 关闭日志包含模块优先级
        - 日志格式正确
        
        Requirements: 13.2
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建独立的事件总线和 SystemManager

            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建并注册模块
            module = MockModule("test_module")
            manager.register_module("test_module", module, priority=25)
            
            # 启动模块
            manager.start_all()
            
            # 清空之前的日志
            caplog.clear()
            
            # 关闭系统
            manager.shutdown()
            
            # 验证日志包含优先级信息
            log_messages = [record.message for record in caplog.records]
            
            # 查找停止模块的日志
            stop_logs = [msg for msg in log_messages if "停止模块" in msg and "test_module" in msg]
            assert len(stop_logs) > 0
            
            # 验证日志包含优先级
            assert any("25" in msg or "priority=25" in msg for msg in stop_logs)
    
    def test_shutdown_logs_event_bus_closure(self, caplog):
        """测试关闭日志包含事件总线关闭信息
        
        验证：
        - 记录事件总线关闭的日志
        - 日志级别正确
        
        Requirements: 10.1, 13.2
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建独立的事件总线和 SystemManager

            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建并注册模块
            module = MockModule("test_module")
            manager.register_module("test_module", module, priority=10)
            
            # 启动模块
            manager.start_all()
            
            # 清空之前的日志
            caplog.clear()
            
            # 关闭系统
            manager.shutdown()
            
            # 验证日志包含事件总线关闭信息
            log_messages = [record.message for record in caplog.records]
            assert any("事件总线" in msg and "关闭" in msg for msg in log_messages)


class TestSystemManagerShutdownThreadSafety:
    """SystemManager 模块关闭线程安全测试"""
    
    def test_shutdown_can_be_called_from_multiple_threads(self):
        """测试 shutdown() 可以从多个线程安全调用
        
        验证：
        - 多个线程同时调用 shutdown() 不会导致错误
        - 模块的 stop() 方法只被调用一次
        - 防重复关闭机制正常工作
        
        Requirements: 9.5
        """
        import threading
        
        # 创建独立的事件总线和 SystemManager

        
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 启动模块
        manager.start_all()
        
        # 创建多个线程同时调用 shutdown()
        threads = []
        for i in range(5):
            thread = threading.Thread(target=manager.shutdown)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证 stop() 方法只被调用一次
        assert module.stop_called is True
        
        # 验证模块状态为 STOPPED
        assert manager._modules["test_module"].state == ModuleState.STOPPED


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
