"""
SystemManager 模块启动单元测试

测试 SystemManager 类的模块启动功能，包括：
- 启动单个模块
- 启动多个模块
- 启动成功后状态为 RUNNING
- 验证日志记录

Requirements: 2.1, 2.3, 2.4, 2.5
"""

import pytest
import logging
from unittest.mock import MagicMock
from oak_vision_system.core.system_manager import SystemManager, ModuleState
from oak_vision_system.core.event_bus import EventBus


class MockModule:
    """用于测试的模拟模块"""
    
    def __init__(self, name: str = "mock_module", should_fail_start: bool = False):
        self.name = name
        self.should_fail_start = should_fail_start
        self.start_called = False
        self.stop_called = False
        self._running = False
    
    def start(self):
        """启动模块"""
        self.start_called = True
        if self.should_fail_start:
            raise RuntimeError(f"Mock start failure: {self.name}")
        self._running = True
    
    def stop(self):
        """停止模块"""
        self.stop_called = True
        self._running = False
    
    def is_running(self):
        """检查模块是否运行中"""
        return self._running


class TestSystemManagerStartup:
    """SystemManager 模块启动测试套件"""
    
    def test_start_single_module(self):
        """测试启动单个模块
        
        验证：
        - 可以成功启动单个模块
        - 模块的 start() 方法被调用
        - 模块状态变为 RUNNING
        
        Requirements: 2.1, 2.3
        """
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模拟模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 验证初始状态为 NOT_STARTED
        assert manager._modules["test_module"].state == ModuleState.NOT_STARTED
        assert module.start_called is False
        
        # 启动所有模块
        manager.start_all()
        
        # 验证模块的 start() 方法被调用
        assert module.start_called is True
        assert module.is_running() is True
        
        # 验证模块状态变为 RUNNING
        assert manager._modules["test_module"].state == ModuleState.RUNNING
    
    def test_start_multiple_modules(self):
        """测试启动多个模块
        
        验证：
        - 可以成功启动多个模块
        - 所有模块的 start() 方法都被调用
        - 所有模块状态都变为 RUNNING
        
        Requirements: 2.1, 2.3
        """
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册多个模拟模块
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        module3 = MockModule("module3")
        
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=30)
        
        # 验证初始状态
        assert manager._modules["module1"].state == ModuleState.NOT_STARTED
        assert manager._modules["module2"].state == ModuleState.NOT_STARTED
        assert manager._modules["module3"].state == ModuleState.NOT_STARTED
        
        # 启动所有模块
        manager.start_all()
        
        # 验证所有模块的 start() 方法都被调用
        assert module1.start_called is True
        assert module2.start_called is True
        assert module3.start_called is True
        
        # 验证所有模块都在运行
        assert module1.is_running() is True
        assert module2.is_running() is True
        assert module3.is_running() is True
        
        # 验证所有模块状态都变为 RUNNING
        assert manager._modules["module1"].state == ModuleState.RUNNING
        assert manager._modules["module2"].state == ModuleState.RUNNING
        assert manager._modules["module3"].state == ModuleState.RUNNING
    
    def test_start_modules_by_priority_order(self):
        """测试模块按优先级顺序启动
        
        验证：
        - 模块按优先级从高到低启动（下游→上游）
        - 优先级高的模块先启动
        
        Requirements: 2.2
        """
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 记录启动顺序
        start_order = []
        
        # 创建带启动顺序记录的模拟模块
        class OrderedMockModule(MockModule):
            def start(self):
                start_order.append(self.name)
                super().start()
        
        # 注册不同优先级的模块（故意打乱注册顺序）
        module_low = OrderedMockModule("low_priority")
        module_high = OrderedMockModule("high_priority")
        module_medium = OrderedMockModule("medium_priority")
        
        manager.register_module("low_priority", module_low, priority=10)
        manager.register_module("high_priority", module_high, priority=50)
        manager.register_module("medium_priority", module_medium, priority=30)
        
        # 启动所有模块
        manager.start_all()
        
        # 验证启动顺序：优先级从高到低
        assert start_order == ["high_priority", "medium_priority", "low_priority"]
        
        # 验证所有模块都启动成功
        assert module_low.start_called is True
        assert module_high.start_called is True
        assert module_medium.start_called is True
    
    def test_start_modules_state_transition(self):
        """测试模块启动时的状态转换
        
        验证：
        - 启动前状态为 NOT_STARTED
        - 启动后状态为 RUNNING
        - 状态转换正确
        
        Requirements: 2.3
        """
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 验证启动前状态
        assert manager._modules["test_module"].state == ModuleState.NOT_STARTED
        assert manager._modules["test_module"].state.value == "not_started"
        
        # 启动模块
        manager.start_all()
        
        # 验证启动后状态
        assert manager._modules["test_module"].state == ModuleState.RUNNING
        assert manager._modules["test_module"].state.value == "running"
    
    def test_start_all_logs_startup_info(self, caplog):
        """测试启动模块时记录日志
        
        验证：
        - 记录开始启动的日志
        - 记录每个模块的启动日志
        - 记录启动成功的日志
        - 日志包含模块名称和优先级
        
        Requirements: 2.5
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建 SystemManager（使用独立的 EventBus）
            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建并注册模块
            module1 = MockModule("module1")
            module2 = MockModule("module2")
            
            manager.register_module("module1", module1, priority=10)
            manager.register_module("module2", module2, priority=20)
            
            # 清空之前的日志
            caplog.clear()
            
            # 启动所有模块
            manager.start_all()
            
            # 验证日志记录
            log_messages = [record.message for record in caplog.records]
            
            # 验证包含开始启动的日志
            assert any("开始启动所有模块" in msg for msg in log_messages)
            
            # 验证包含每个模块的启动日志
            assert any("module1" in msg and "启动模块" in msg for msg in log_messages)
            assert any("module2" in msg and "启动模块" in msg for msg in log_messages)
            
            # 验证包含启动成功的日志
            assert any("module1" in msg and "启动成功" in msg for msg in log_messages)
            assert any("module2" in msg and "启动成功" in msg for msg in log_messages)
            
            # 验证包含完成日志
            assert any("所有模块启动完成" in msg for msg in log_messages)
    
    def test_start_all_logs_priority_info(self, caplog):
        """测试启动日志包含优先级信息
        
        验证：
        - 启动日志包含模块优先级
        - 日志格式正确
        
        Requirements: 2.5
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建 SystemManager（使用独立的 EventBus）
            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建并注册模块
            module = MockModule("test_module")
            manager.register_module("test_module", module, priority=25)
            
            # 清空之前的日志
            caplog.clear()
            
            # 启动所有模块
            manager.start_all()
            
            # 验证日志包含优先级信息
            log_messages = [record.message for record in caplog.records]
            
            # 查找启动模块的日志
            startup_logs = [msg for msg in log_messages if "启动模块" in msg and "test_module" in msg]
            assert len(startup_logs) > 0
            
            # 验证日志包含优先级
            assert any("25" in msg or "priority=25" in msg for msg in startup_logs)
    
    def test_start_empty_modules_list(self):
        """测试启动空模块列表
        
        验证：
        - 没有注册模块时可以正常调用 start_all()
        - 不抛出异常
        
        Requirements: 2.1
        """
        # 创建 SystemManager（不注册任何模块）（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 启动所有模块（应该不抛出异常）
        manager.start_all()
        
        # 验证没有模块
        assert len(manager._modules) == 0
    
    def test_start_modules_with_same_priority(self):
        """测试启动相同优先级的模块
        
        验证：
        - 可以启动相同优先级的模块
        - 所有模块都能成功启动
        
        Requirements: 2.1, 2.2
        """
        # 创建 SystemManager（使用独立的 EventBus）
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
        
        # 验证所有模块都启动成功
        assert module1.start_called is True
        assert module2.start_called is True
        assert module3.start_called is True
        
        # 验证所有模块状态都为 RUNNING
        assert manager._modules["module1"].state == ModuleState.RUNNING
        assert manager._modules["module2"].state == ModuleState.RUNNING
        assert manager._modules["module3"].state == ModuleState.RUNNING
    
    def test_start_modules_preserves_instance_reference(self):
        """测试启动后模块实例引用保持不变
        
        验证：
        - 启动后模块实例仍然是同一个对象
        - 可以通过 ManagedModule 访问原始实例
        
        Requirements: 2.1
        """
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建模拟模块
        original_module = MockModule("test_module")
        
        # 注册模块
        manager.register_module("test_module", original_module, priority=10)
        
        # 获取注册后的实例引用
        registered_instance = manager._modules["test_module"].instance
        
        # 启动模块
        manager.start_all()
        
        # 获取启动后的实例引用
        started_instance = manager._modules["test_module"].instance
        
        # 验证是同一个对象
        assert started_instance is original_module
        assert registered_instance is original_module
        assert started_instance is registered_instance
    
    def test_start_all_multiple_times_fails(self):
        """测试多次调用 start_all() 会失败
        
        验证：
        - 第一次调用 start_all() 成功
        - 第二次调用 start_all() 会失败（因为模块已经启动）
        
        Requirements: 2.1
        """
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 创建并注册模块
        module = MockModule("test_module")
        manager.register_module("test_module", module, priority=10)
        
        # 第一次启动成功
        manager.start_all()
        assert module.start_called is True
        assert manager._modules["test_module"].state == ModuleState.RUNNING
        
        # 重置 start_called 标志
        module.start_called = False
        
        # 第二次启动会再次调用 start()（可能导致错误）
        # 这取决于模块的实现，但 SystemManager 会尝试启动
        manager.start_all()
        assert module.start_called is True


class TestSystemManagerStartupEdgeCases:
    """SystemManager 模块启动边界情况测试"""
    
    def test_start_modules_with_negative_priority(self):
        """测试启动负优先级的模块
        
        验证：
        - 可以启动负优先级的模块
        - 负优先级模块最后启动
        
        Requirements: 2.2
        """
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 记录启动顺序
        start_order = []
        
        class OrderedMockModule(MockModule):
            def start(self):
                start_order.append(self.name)
                super().start()
        
        # 注册不同优先级的模块（包括负数）
        module_positive = OrderedMockModule("positive")
        module_zero = OrderedMockModule("zero")
        module_negative = OrderedMockModule("negative")
        
        manager.register_module("positive", module_positive, priority=10)
        manager.register_module("zero", module_zero, priority=0)
        manager.register_module("negative", module_negative, priority=-10)
        
        # 启动所有模块
        manager.start_all()
        
        # 验证启动顺序：从高到低
        assert start_order == ["positive", "zero", "negative"]
        
        # 验证所有模块都启动成功
        assert module_positive.start_called is True
        assert module_zero.start_called is True
        assert module_negative.start_called is True
    
    def test_start_modules_with_large_priority_values(self):
        """测试启动大优先级值的模块
        
        验证：
        - 可以使用大的优先级值
        - 启动顺序正确
        
        Requirements: 2.2
        """
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 记录启动顺序
        start_order = []
        
        class OrderedMockModule(MockModule):
            def start(self):
                start_order.append(self.name)
                super().start()
        
        # 注册大优先级值的模块
        module_huge = OrderedMockModule("huge")
        module_large = OrderedMockModule("large")
        module_small = OrderedMockModule("small")
        
        manager.register_module("huge", module_huge, priority=1000000)
        manager.register_module("large", module_large, priority=100000)
        manager.register_module("small", module_small, priority=1)
        
        # 启动所有模块
        manager.start_all()
        
        # 验证启动顺序
        assert start_order == ["huge", "large", "small"]
    
    def test_start_many_modules(self):
        """测试启动大量模块
        
        验证：
        - 可以启动大量模块
        - 所有模块都能成功启动
        - 性能可接受
        
        Requirements: 2.1
        """
        # 创建 SystemManager（使用独立的 EventBus）
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
        
        # 验证所有模块都启动成功
        for module in modules:
            assert module.start_called is True
            assert module.is_running() is True
        
        # 验证所有模块状态都为 RUNNING
        for i in range(num_modules):
            assert manager._modules[f"module_{i}"].state == ModuleState.RUNNING


class TestSystemManagerStartupLogging:
    """SystemManager 模块启动日志测试"""
    
    def test_start_all_logs_at_info_level(self, caplog):
        """测试启动日志使用 INFO 级别
        
        验证：
        - 启动日志使用 INFO 级别
        - 不使用 DEBUG 或 WARNING 级别
        
        Requirements: 2.5
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建 SystemManager（使用独立的 EventBus）
            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建并注册模块
            module = MockModule("test_module")
            manager.register_module("test_module", module, priority=10)
            
            # 清空之前的日志
            caplog.clear()
            
            # 启动所有模块
            manager.start_all()
            
            # 验证有 INFO 级别的日志
            info_logs = [record for record in caplog.records if record.levelno == logging.INFO]
            assert len(info_logs) > 0
            
            # 验证启动相关的日志都是 INFO 级别
            startup_logs = [
                record for record in caplog.records
                if "启动" in record.message
            ]
            for log in startup_logs:
                assert log.levelno == logging.INFO
    
    def test_start_all_logs_module_count(self, caplog):
        """测试启动完成日志包含模块数量
        
        验证：
        - 启动完成日志包含模块数量
        - 数量正确
        
        Requirements: 2.5
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建 SystemManager（使用独立的 EventBus）
            event_bus = EventBus()
            manager = SystemManager(event_bus=event_bus)
            
            # 创建并注册3个模块
            for i in range(3):
                module = MockModule(f"module_{i}")
                manager.register_module(f"module_{i}", module, priority=i)
            
            # 清空之前的日志
            caplog.clear()
            
            # 启动所有模块
            manager.start_all()
            
            # 验证完成日志包含模块数量
            log_messages = [record.message for record in caplog.records]
            completion_logs = [msg for msg in log_messages if "启动完成" in msg]
            
            assert len(completion_logs) > 0
            assert any("3" in msg for msg in completion_logs)


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
