"""
SystemManager状态查询单元测试

测试SystemManager类的状态查询功能，包括：
- get_status() 方法返回正确状态
- is_shutting_down() 方法在不同阶段的返回值
- 状态字符串格式验证

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
"""

import pytest
import threading
from oak_vision_system.core.system_manager import SystemManager, ModuleState
from oak_vision_system.core.event_bus import EventBus


class MockModule:
    """用于测试的模拟模块"""
    
    def __init__(self, should_fail_start=False, should_fail_stop=False):
        self.should_fail_start = should_fail_start
        self.should_fail_stop = should_fail_stop
        self.start_called = False
        self.stop_called = False
        self._running = False
    
    def start(self):
        if self.should_fail_start:
            raise RuntimeError("Mock start failure")
        self.start_called = True
        self._running = True
    
    def stop(self):
        self.stop_called = True
        if self.should_fail_stop:
            raise RuntimeError("Mock stop failure")
        self._running = False
    
    def is_running(self):
        return self._running


class TestGetStatus:
    """get_status() 方法测试套件
    
    测试 get_status() 方法返回正确的模块状态信息。
    
    Requirements: 12.1, 12.2, 12.3
    """
    
    def test_get_status_empty_modules(self):
        """测试没有注册模块时的状态查询
        
        验证：
        - 未注册任何模块时，get_status() 返回空字典
        
        Requirements: 12.1, 12.2
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 获取状态
        status = manager.get_status()
        
        # 验证返回空字典
        assert isinstance(status, dict)
        assert len(status) == 0
        assert status == {}
    
    def test_get_status_single_module_not_started(self):
        """测试单个未启动模块的状态查询
        
        验证：
        - 注册但未启动的模块状态为 "not_started"
        - 返回的字典包含正确的模块名称和状态
        
        Requirements: 12.1, 12.2, 12.3
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册模块（未启动）
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        
        # 获取状态
        status = manager.get_status()
        
        # 验证状态
        assert isinstance(status, dict)
        assert len(status) == 1
        assert "test_module" in status
        assert status["test_module"] == "not_started"
    
    def test_get_status_single_module_running(self):
        """测试单个运行中模块的状态查询
        
        验证：
        - 启动后的模块状态为 "running"
        - 状态字符串格式正确
        
        Requirements: 12.1, 12.2, 12.3
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册并启动模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        manager.start_all()
        
        # 获取状态
        status = manager.get_status()
        
        # 验证状态
        assert status["test_module"] == "running"
    
    def test_get_status_single_module_stopped(self):
        """测试单个已停止模块的状态查询
        
        验证：
        - 关闭后的模块状态为 "stopped"
        
        Requirements: 12.1, 12.2, 12.3
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册、启动、关闭模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        manager.start_all()
        manager.shutdown()
        
        # 获取状态
        status = manager.get_status()
        
        # 验证状态
        assert status["test_module"] == "stopped"
    
    def test_get_status_multiple_modules(self):
        """测试多个模块的状态查询
        
        验证：
        - 可以同时查询多个模块的状态
        - 每个模块的状态都正确返回
        
        Requirements: 12.1, 12.2, 12.3
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册多个模块
        module1 = MockModule()
        module2 = MockModule()
        module3 = MockModule()
        
        manager.register_module("collector", module1, priority=10)
        manager.register_module("processor", module2, priority=30)
        manager.register_module("display", module3, priority=50)
        
        # 获取状态（未启动）
        status = manager.get_status()
        
        # 验证所有模块状态
        assert len(status) == 3
        assert status["collector"] == "not_started"
        assert status["processor"] == "not_started"
        assert status["display"] == "not_started"
    
    def test_get_status_multiple_modules_running(self):
        """测试多个运行中模块的状态查询
        
        验证：
        - 启动后所有模块状态都为 "running"
        
        Requirements: 12.1, 12.2, 12.3
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册并启动多个模块
        module1 = MockModule()
        module2 = MockModule()
        module3 = MockModule()
        
        manager.register_module("collector", module1, priority=10)
        manager.register_module("processor", module2, priority=30)
        manager.register_module("display", module3, priority=50)
        manager.start_all()
        
        # 获取状态
        status = manager.get_status()
        
        # 验证所有模块状态
        assert len(status) == 3
        assert status["collector"] == "running"
        assert status["processor"] == "running"
        assert status["display"] == "running"
    
    def test_get_status_mixed_states(self):
        """测试混合状态的模块查询
        
        验证：
        - 可以正确返回处于不同状态的模块
        - 每个模块的状态独立且正确
        
        Requirements: 12.1, 12.2, 12.3
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册多个模块
        module1 = MockModule()
        module2 = MockModule()
        module3 = MockModule()
        
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=30)
        
        # 只启动部分模块（通过直接修改状态模拟）
        manager._modules["module1"].state = ModuleState.NOT_STARTED
        manager._modules["module2"].state = ModuleState.RUNNING
        manager._modules["module3"].state = ModuleState.STOPPED
        
        # 获取状态
        status = manager.get_status()
        
        # 验证混合状态
        assert status["module1"] == "not_started"
        assert status["module2"] == "running"
        assert status["module3"] == "stopped"
    
    def test_get_status_with_error_state(self):
        """测试包含错误状态的模块查询
        
        验证：
        - 错误状态的模块返回 "error"
        
        Requirements: 12.1, 12.2, 12.3
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        
        # 手动设置为错误状态
        manager._modules["test_module"].state = ModuleState.ERROR
        
        # 获取状态
        status = manager.get_status()
        
        # 验证错误状态
        assert status["test_module"] == "error"
    
    def test_get_status_returns_new_dict(self):
        """测试 get_status() 返回新字典
        
        验证：
        - 每次调用返回新的字典对象
        - 修改返回的字典不影响内部状态
        
        Requirements: 12.1, 12.2
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        
        # 获取状态两次
        status1 = manager.get_status()
        status2 = manager.get_status()
        
        # 验证返回不同的字典对象
        assert status1 is not status2
        assert status1 == status2
        
        # 修改返回的字典不应影响内部状态
        status1["test_module"] = "modified"
        status3 = manager.get_status()
        assert status3["test_module"] == "not_started"
    
    def test_get_status_string_format(self):
        """测试状态字符串格式
        
        验证：
        - 所有状态字符串都是小写
        - 使用下划线分隔单词
        - 符合预期的格式
        
        Requirements: 12.3
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册模块并设置不同状态
        for i, state in enumerate(ModuleState):
            module = MockModule()
            manager.register_module(f"module_{i}", module, priority=10 + i)
            manager._modules[f"module_{i}"].state = state
        
        # 获取状态
        status = manager.get_status()
        
        # 验证所有状态字符串格式
        expected_formats = ["not_started", "running", "stopped", "error"]
        for state_str in status.values():
            assert state_str in expected_formats
            assert state_str.islower()  # 全部小写
            assert " " not in state_str  # 不包含空格


class TestIsShuttingDown:
    """is_shutting_down() 方法测试套件
    
    测试 is_shutting_down() 方法在不同阶段的返回值。
    
    Requirements: 12.4, 12.5
    """
    
    def test_is_shutting_down_initial_state(self):
        """测试初始状态下 is_shutting_down() 返回 False
        
        验证：
        - SystemManager 初始化后，is_shutting_down() 返回 False
        
        Requirements: 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 验证初始状态
        assert manager.is_shutting_down() is False
    
    def test_is_shutting_down_after_registration(self):
        """测试注册模块后 is_shutting_down() 返回 False
        
        验证：
        - 注册模块不影响 is_shutting_down() 的返回值
        
        Requirements: 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        
        # 验证仍然返回 False
        assert manager.is_shutting_down() is False
    
    def test_is_shutting_down_after_start(self):
        """测试启动模块后 is_shutting_down() 返回 False
        
        验证：
        - 启动模块不影响 is_shutting_down() 的返回值
        
        Requirements: 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册并启动模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        manager.start_all()
        
        # 验证仍然返回 False
        assert manager.is_shutting_down() is False
    
    def test_is_shutting_down_during_shutdown(self):
        """测试关闭过程中 is_shutting_down() 返回 True
        
        验证：
        - 调用 shutdown() 后，is_shutting_down() 返回 True
        
        Requirements: 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册并启动模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        manager.start_all()
        
        # 调用 shutdown()
        manager.shutdown()
        
        # 验证返回 True
        assert manager.is_shutting_down() is True
    
    def test_is_shutting_down_after_shutdown(self):
        """测试关闭完成后 is_shutting_down() 仍返回 True
        
        验证：
        - shutdown() 完成后，is_shutting_down() 持续返回 True
        
        Requirements: 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册并启动模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        manager.start_all()
        
        # 关闭系统
        manager.shutdown()
        
        # 验证持续返回 True
        assert manager.is_shutting_down() is True
        assert manager.is_shutting_down() is True  # 多次调用
    
    def test_is_shutting_down_prevents_duplicate_shutdown(self):
        """测试 is_shutting_down() 可用于防止重复关闭
        
        验证：
        - 可以使用 is_shutting_down() 检查是否已经开始关闭
        - 防止重复调用 shutdown()
        
        Requirements: 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册并启动模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        manager.start_all()
        
        # 第一次关闭
        assert manager.is_shutting_down() is False
        manager.shutdown()
        assert manager.is_shutting_down() is True
        
        # 尝试第二次关闭（应该被防止）
        manager.shutdown()  # 不应该抛出异常
        assert manager.is_shutting_down() is True
    
    def test_is_shutting_down_thread_safe(self):
        """测试 is_shutting_down() 的线程安全性
        
        验证：
        - 可以从多个线程安全调用 is_shutting_down()
        
        Requirements: 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册并启动模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        manager.start_all()
        
        # 从多个线程调用 is_shutting_down()
        results = []
        
        def check_shutting_down():
            for _ in range(10):
                results.append(manager.is_shutting_down())
        
        threads = [threading.Thread(target=check_shutting_down) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证所有调用都返回 False（未关闭）
        assert all(result is False for result in results)
        
        # 关闭后再次测试
        manager.shutdown()
        results.clear()
        
        threads = [threading.Thread(target=check_shutting_down) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证所有调用都返回 True（已关闭）
        assert all(result is True for result in results)


class TestStatusQueryIntegration:
    """状态查询集成测试
    
    测试 get_status() 和 is_shutting_down() 的组合使用场景。
    
    Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
    """
    
    def test_status_query_full_lifecycle(self):
        """测试完整生命周期的状态查询
        
        验证：
        - 在系统的各个阶段，状态查询都返回正确结果
        
        Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 阶段1：初始化
        assert manager.get_status() == {}
        assert manager.is_shutting_down() is False
        
        # 阶段2：注册模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        
        status = manager.get_status()
        assert status["test_module"] == "not_started"
        assert manager.is_shutting_down() is False
        
        # 阶段3：启动模块
        manager.start_all()
        
        status = manager.get_status()
        assert status["test_module"] == "running"
        assert manager.is_shutting_down() is False
        
        # 阶段4：关闭系统
        manager.shutdown()
        
        status = manager.get_status()
        assert status["test_module"] == "stopped"
        assert manager.is_shutting_down() is True
    
    def test_status_query_with_multiple_modules_lifecycle(self):
        """测试多模块完整生命周期的状态查询
        
        验证：
        - 多个模块在各个阶段的状态都正确
        
        Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册多个模块
        modules = {
            "collector": MockModule(),
            "processor": MockModule(),
            "display": MockModule()
        }
        
        manager.register_module("collector", modules["collector"], priority=10)
        manager.register_module("processor", modules["processor"], priority=30)
        manager.register_module("display", modules["display"], priority=50)
        
        # 验证注册后状态
        status = manager.get_status()
        assert all(state == "not_started" for state in status.values())
        assert manager.is_shutting_down() is False
        
        # 启动所有模块
        manager.start_all()
        
        # 验证运行状态
        status = manager.get_status()
        assert all(state == "running" for state in status.values())
        assert manager.is_shutting_down() is False
        
        # 关闭系统
        manager.shutdown()
        
        # 验证停止状态
        status = manager.get_status()
        assert all(state == "stopped" for state in status.values())
        assert manager.is_shutting_down() is True
    
    def test_status_consistency_during_operations(self):
        """测试操作过程中状态的一致性
        
        验证：
        - get_status() 和实际模块状态保持一致
        - is_shutting_down() 准确反映系统状态
        
        Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
        """
        # 创建独立的事件总线
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册模块
        module = MockModule()
        manager.register_module("test_module", module, priority=10)
        
        # 验证状态一致性
        status = manager.get_status()
        internal_state = manager._modules["test_module"].state
        assert status["test_module"] == internal_state.value
        
        # 启动后验证
        manager.start_all()
        status = manager.get_status()
        internal_state = manager._modules["test_module"].state
        assert status["test_module"] == internal_state.value
        assert status["test_module"] == "running"
        
        # 关闭后验证
        manager.shutdown()
        status = manager.get_status()
        internal_state = manager._modules["test_module"].state
        assert status["test_module"] == internal_state.value
        assert status["test_module"] == "stopped"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
