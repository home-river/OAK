"""
SystemManager基础数据结构单元测试（简化版）

测试SystemManager模块的基础数据结构，包括：
- ModuleState枚举的所有值（简化版：4个状态）
- ManagedModule数据类的创建和字段访问（简化版：无stop_timeout字段）
- ShutdownEvent数据类的创建和字段访问

Requirements: 1.2, 1.3, 4.2
"""

import pytest
from oak_vision_system.core.system_manager import (
    ModuleState,
    ManagedModule,
    ShutdownEvent,
)


class TestModuleState:
    """ModuleState枚举测试套件（简化版：4个状态）"""
    
    def test_module_state_values(self):
        """测试ModuleState枚举的所有值（简化版：4个状态）"""
        # 验证所有状态值存在
        assert ModuleState.NOT_STARTED.value == "not_started"
        assert ModuleState.RUNNING.value == "running"
        assert ModuleState.STOPPED.value == "stopped"
        assert ModuleState.ERROR.value == "error"
    
    def test_module_state_count(self):
        """测试ModuleState枚举包含正确数量的状态"""
        # 简化版应该有4个状态
        assert len(ModuleState) == 4
    
    def test_module_state_comparison(self):
        """测试ModuleState枚举的比较"""
        # 枚举成员应该可以比较相等性
        state1 = ModuleState.RUNNING
        state2 = ModuleState.RUNNING
        state3 = ModuleState.STOPPED
        
        assert state1 == state2
        assert state1 != state3
    
    def test_module_state_from_value(self):
        """测试从字符串值创建ModuleState"""
        # 可以从字符串值创建枚举
        state = ModuleState("running")
        assert state == ModuleState.RUNNING
        
        # 无效值应该抛出异常
        with pytest.raises(ValueError):
            ModuleState("invalid_state")


class TestManagedModule:
    """ManagedModule数据类测试套件（简化版：无stop_timeout字段）"""
    
    def test_managed_module_creation(self):
        """测试ManagedModule数据类的创建"""
        # 创建一个模拟模块实例
        class MockModule:
            def start(self):
                pass
            
            def stop(self):
                pass
        
        mock_instance = MockModule()
        
        # 创建ManagedModule（简化版：无stop_timeout字段）
        managed = ManagedModule(
            name="test_module",
            instance=mock_instance,
            priority=50,
            state=ModuleState.NOT_STARTED
        )
        
        # 验证所有字段
        assert managed.name == "test_module"
        assert managed.instance is mock_instance
        assert managed.priority == 50
        assert managed.state == ModuleState.NOT_STARTED
    
    def test_managed_module_field_access(self):
        """测试ManagedModule字段访问"""
        class MockModule:
            pass
        
        managed = ManagedModule(
            name="collector",
            instance=MockModule(),
            priority=10,
            state=ModuleState.RUNNING
        )
        
        # 验证可以访问所有字段
        assert managed.name == "collector"
        assert isinstance(managed.instance, MockModule)
        assert managed.priority == 10
        assert managed.state == ModuleState.RUNNING
    
    def test_managed_module_state_update(self):
        """测试ManagedModule状态更新"""
        class MockModule:
            pass
        
        managed = ManagedModule(
            name="processor",
            instance=MockModule(),
            priority=30,
            state=ModuleState.NOT_STARTED
        )
        
        # 数据类默认是可变的，可以更新状态
        managed.state = ModuleState.RUNNING
        assert managed.state == ModuleState.RUNNING
        
        managed.state = ModuleState.STOPPED
        assert managed.state == ModuleState.STOPPED
    
    def test_managed_module_with_different_priorities(self):
        """测试不同优先级的ManagedModule"""
        class MockModule:
            pass
        
        # 创建不同优先级的模块
        low_priority = ManagedModule(
            name="data_source",
            instance=MockModule(),
            priority=10,
            state=ModuleState.NOT_STARTED
        )
        
        high_priority = ManagedModule(
            name="output",
            instance=MockModule(),
            priority=100,
            state=ModuleState.NOT_STARTED
        )
        
        # 验证优先级
        assert low_priority.priority < high_priority.priority
        assert low_priority.priority == 10
        assert high_priority.priority == 100


class TestShutdownEvent:
    """ShutdownEvent数据类测试套件"""
    
    def test_shutdown_event_creation(self):
        """测试ShutdownEvent数据类的创建"""
        # 创建ShutdownEvent
        event = ShutdownEvent(reason="user_quit")
        
        # 验证字段
        assert event.reason == "user_quit"
    
    def test_shutdown_event_with_different_reasons(self):
        """测试不同原因的ShutdownEvent"""
        # 测试常见的停止原因
        reasons = [
            "user_quit",
            "ctrl_c",
            "sigterm",
            "error",
            "custom_reason"
        ]
        
        for reason in reasons:
            event = ShutdownEvent(reason=reason)
            assert event.reason == reason
    
    def test_shutdown_event_field_access(self):
        """测试ShutdownEvent字段访问"""
        event = ShutdownEvent(reason="ctrl_c")
        
        # 验证可以访问reason字段
        assert hasattr(event, "reason")
        assert event.reason == "ctrl_c"
    
    def test_shutdown_event_with_empty_reason(self):
        """测试空原因的ShutdownEvent"""
        # 空字符串也是有效的reason
        event = ShutdownEvent(reason="")
        assert event.reason == ""
    
    def test_shutdown_event_with_long_reason(self):
        """测试长原因字符串的ShutdownEvent"""
        # 长字符串也应该被接受
        long_reason = "系统检测到严重错误，需要立即停止所有模块以防止数据损坏"
        event = ShutdownEvent(reason=long_reason)
        assert event.reason == long_reason


class TestDataStructureIntegration:
    """数据结构集成测试（简化版）"""
    
    def test_managed_module_with_all_states(self):
        """测试ManagedModule与所有ModuleState的组合"""
        class MockModule:
            pass
        
        # 测试所有状态（简化版：4个状态）
        for state in ModuleState:
            managed = ManagedModule(
                name=f"module_{state.value}",
                instance=MockModule(),
                priority=50,
                state=state
            )
            assert managed.state == state
    
    def test_multiple_managed_modules(self):
        """测试创建多个ManagedModule"""
        class MockModule:
            pass
        
        # 创建多个模块
        modules = []
        for i in range(5):
            module = ManagedModule(
                name=f"module_{i}",
                instance=MockModule(),
                priority=i * 10,
                state=ModuleState.NOT_STARTED
            )
            modules.append(module)
        
        # 验证所有模块都被正确创建
        assert len(modules) == 5
        for i, module in enumerate(modules):
            assert module.name == f"module_{i}"
            assert module.priority == i * 10
    
    def test_shutdown_event_in_error_scenario(self):
        """测试错误场景下的ShutdownEvent"""
        # 模拟错误场景
        error_message = "未捕获的异常: ValueError"
        event = ShutdownEvent(reason=f"error: {error_message}")
        
        assert "error" in event.reason
        assert "ValueError" in event.reason


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
