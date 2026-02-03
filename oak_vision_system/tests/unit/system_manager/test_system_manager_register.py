"""
SystemManager 模块注册单元测试

测试 SystemManager 类的模块注册功能，包括：
- 成功注册单个模块
- 注册多个模块
- 重复注册抛出异常
- 模块初始状态为 NOT_STARTED
- 验证日志记录

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

import pytest
import logging
from unittest.mock import MagicMock, patch
from oak_vision_system.core.system_manager import SystemManager, ModuleState, ManagedModule
from oak_vision_system.core.event_bus import EventBus


class MockModule:
    """用于测试的模拟模块"""
    
    def __init__(self, name: str = "mock_module"):
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


class TestSystemManagerRegister:
    """SystemManager 模块注册测试套件"""
    
    def test_register_single_module(self):
        """测试成功注册单个模块
        
        验证：
        - 可以成功注册一个模块
        - 模块被存储到 _modules 字典
        - 模块名称作为键
        - 模块被包装为 ManagedModule 对象
        
        Requirements: 1.1, 1.2
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模拟模块
        module = MockModule("test_module")
        
        # 注册模块
        manager.register_module(
            name="test_module",
            instance=module,
            priority=10
        )
        
        # 验证模块被存储
        assert "test_module" in manager._modules
        
        # 验证存储的是 ManagedModule 对象
        managed_module = manager._modules["test_module"]
        assert isinstance(managed_module, ManagedModule)
        
        # 验证 ManagedModule 的属性
        assert managed_module.name == "test_module"
        assert managed_module.instance is module
        assert managed_module.priority == 10
    
    def test_register_multiple_modules(self):
        """测试注册多个模块
        
        验证：
        - 可以注册多个不同名称的模块
        - 所有模块都被正确存储
        - 每个模块保持独立
        
        Requirements: 1.1, 1.2
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建多个模拟模块
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        module3 = MockModule("module3")
        
        # 注册多个模块
        manager.register_module("module1", module1, priority=10)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=30)
        
        # 验证所有模块都被存储
        assert len(manager._modules) == 3
        assert "module1" in manager._modules
        assert "module2" in manager._modules
        assert "module3" in manager._modules
        
        # 验证每个模块的属性
        assert manager._modules["module1"].instance is module1
        assert manager._modules["module1"].priority == 10
        
        assert manager._modules["module2"].instance is module2
        assert manager._modules["module2"].priority == 20
        
        assert manager._modules["module3"].instance is module3
        assert manager._modules["module3"].priority == 30
    
    def test_register_duplicate_name_raises_error(self):
        """测试重复注册同名模块抛出异常
        
        验证：
        - 注册同名模块时抛出 ValueError
        - 异常消息包含模块名称
        - 第一个模块仍然保留在 _modules 中
        
        Requirements: 1.5
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建两个模拟模块
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        
        # 注册第一个模块
        manager.register_module("duplicate_name", module1, priority=10)
        
        # 尝试注册同名模块，应该抛出 ValueError
        with pytest.raises(ValueError) as exc_info:
            manager.register_module("duplicate_name", module2, priority=20)
        
        # 验证异常消息包含模块名称
        assert "duplicate_name" in str(exc_info.value)
        assert "已存在" in str(exc_info.value)
        
        # 验证第一个模块仍然存在
        assert "duplicate_name" in manager._modules
        assert manager._modules["duplicate_name"].instance is module1
        assert manager._modules["duplicate_name"].priority == 10
    
    def test_register_module_initial_state_not_started(self):
        """测试模块初始状态为 NOT_STARTED
        
        验证：
        - 注册后模块状态为 NOT_STARTED
        - 状态值正确
        
        Requirements: 1.3
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模拟模块
        module = MockModule("test_module")
        
        # 注册模块
        manager.register_module("test_module", module, priority=10)
        
        # 验证模块状态为 NOT_STARTED
        managed_module = manager._modules["test_module"]
        assert managed_module.state == ModuleState.NOT_STARTED
        assert managed_module.state.value == "not_started"
    
    def test_register_module_with_different_priorities(self):
        """测试注册不同优先级的模块
        
        验证：
        - 可以注册不同优先级的模块
        - 优先级被正确保存
        - 支持各种优先级值（正数、零、负数）
        
        Requirements: 1.1, 1.2
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 注册不同优先级的模块
        manager.register_module("high_priority", MockModule(), priority=100)
        manager.register_module("medium_priority", MockModule(), priority=50)
        manager.register_module("low_priority", MockModule(), priority=10)
        manager.register_module("zero_priority", MockModule(), priority=0)
        manager.register_module("negative_priority", MockModule(), priority=-10)
        
        # 验证优先级被正确保存
        assert manager._modules["high_priority"].priority == 100
        assert manager._modules["medium_priority"].priority == 50
        assert manager._modules["low_priority"].priority == 10
        assert manager._modules["zero_priority"].priority == 0
        assert manager._modules["negative_priority"].priority == -10
    
    def test_register_module_logs_registration(self, caplog):
        """测试注册模块时记录日志
        
        验证：
        - 注册模块时记录 INFO 级别日志
        - 日志包含模块名称
        - 日志包含优先级
        - 日志包含初始状态
        
        Requirements: 1.4
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建 SystemManager
            manager = SystemManager()
            
            # 清空之前的日志
            caplog.clear()
            
            # 注册模块
            manager.register_module("test_module", MockModule(), priority=25)
            
            # 验证日志记录
            assert len(caplog.records) > 0
            
            # 查找注册日志
            registration_logs = [
                record for record in caplog.records
                if "注册模块" in record.message
            ]
            
            assert len(registration_logs) > 0
            log_message = registration_logs[0].message
            
            # 验证日志包含必要信息
            assert "test_module" in log_message
            assert "25" in log_message or "priority=25" in log_message
            assert "not_started" in log_message or "NOT_STARTED" in log_message
    
    def test_register_module_with_various_instance_types(self):
        """测试注册不同类型的模块实例
        
        验证：
        - 可以注册任何类型的对象作为模块
        - 不验证模块是否有 start/stop 方法（在启动时验证）
        
        Requirements: 1.1, 1.2
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 注册不同类型的模块实例
        manager.register_module("mock_module", MockModule(), priority=10)
        manager.register_module("dict_module", {"type": "dict"}, priority=20)
        manager.register_module("string_module", "string_instance", priority=30)
        manager.register_module("int_module", 42, priority=40)
        
        # 验证所有模块都被注册
        assert len(manager._modules) == 4
        assert isinstance(manager._modules["mock_module"].instance, MockModule)
        assert isinstance(manager._modules["dict_module"].instance, dict)
        assert isinstance(manager._modules["string_module"].instance, str)
        assert isinstance(manager._modules["int_module"].instance, int)
    
    def test_register_module_preserves_instance_reference(self):
        """测试注册模块保持实例引用
        
        验证：
        - 注册的模块实例是同一个对象（不是副本）
        - 可以通过 ManagedModule 访问原始实例
        
        Requirements: 1.2
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模拟模块
        original_module = MockModule("original")
        
        # 注册模块
        manager.register_module("test_module", original_module, priority=10)
        
        # 获取存储的模块实例
        stored_instance = manager._modules["test_module"].instance
        
        # 验证是同一个对象（不是副本）
        assert stored_instance is original_module
        
        # 修改原始实例，验证存储的实例也改变
        original_module.start()
        assert stored_instance.start_called is True
        assert stored_instance.is_running() is True


class TestSystemManagerRegisterEdgeCases:
    """SystemManager 模块注册边界情况测试"""
    
    def test_register_module_with_empty_name(self):
        """测试注册空名称的模块
        
        验证：
        - 可以注册空字符串名称的模块（虽然不推荐）
        
        Requirements: 1.1
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 注册空名称模块
        manager.register_module("", MockModule(), priority=10)
        
        # 验证模块被注册
        assert "" in manager._modules
    
    def test_register_module_with_special_characters_in_name(self):
        """测试注册包含特殊字符的模块名称
        
        验证：
        - 可以注册包含特殊字符的模块名称
        
        Requirements: 1.1
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 注册包含特殊字符的模块
        special_names = [
            "module-with-dash",
            "module_with_underscore",
            "module.with.dot",
            "module:with:colon",
            "模块中文名称",
            "module with spaces"
        ]
        
        for i, name in enumerate(special_names):
            manager.register_module(name, MockModule(), priority=i)
        
        # 验证所有模块都被注册
        assert len(manager._modules) == len(special_names)
        for name in special_names:
            assert name in manager._modules
    
    def test_register_module_with_none_instance(self):
        """测试注册 None 作为模块实例
        
        验证：
        - 可以注册 None 作为模块实例（虽然不推荐）
        - 在启动时会失败
        
        Requirements: 1.2
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 注册 None 作为模块实例
        manager.register_module("none_module", None, priority=10)
        
        # 验证模块被注册
        assert "none_module" in manager._modules
        assert manager._modules["none_module"].instance is None
    
    def test_register_many_modules(self):
        """测试注册大量模块
        
        验证：
        - 可以注册大量模块
        - 性能可接受
        
        Requirements: 1.1, 1.2
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 注册100个模块
        num_modules = 100
        for i in range(num_modules):
            manager.register_module(f"module_{i}", MockModule(), priority=i)
        
        # 验证所有模块都被注册
        assert len(manager._modules) == num_modules
        
        # 验证可以访问所有模块
        for i in range(num_modules):
            assert f"module_{i}" in manager._modules
            assert manager._modules[f"module_{i}"].priority == i
    
    def test_register_after_duplicate_error(self):
        """测试重复注册错误后可以继续注册其他模块
        
        验证：
        - 重复注册错误不影响后续注册
        - SystemManager 状态保持一致
        
        Requirements: 1.5
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 注册第一个模块
        manager.register_module("module1", MockModule(), priority=10)
        
        # 尝试重复注册（应该失败）
        with pytest.raises(ValueError):
            manager.register_module("module1", MockModule(), priority=20)
        
        # 注册其他模块（应该成功）
        manager.register_module("module2", MockModule(), priority=30)
        manager.register_module("module3", MockModule(), priority=40)
        
        # 验证状态正确
        assert len(manager._modules) == 3
        assert "module1" in manager._modules
        assert "module2" in manager._modules
        assert "module3" in manager._modules


class TestSystemManagerRegisterMultipleInstances:
    """SystemManager 多实例模块注册测试"""
    
    def test_different_managers_independent_registrations(self):
        """测试不同 SystemManager 实例的注册相互独立
        
        验证：
        - 不同 SystemManager 实例的模块注册互不影响
        - 每个实例维护独立的 _modules 字典
        
        Requirements: 1.1, 1.2
        """
        # 创建两个 SystemManager 实例
        manager1 = SystemManager()
        manager2 = SystemManager()
        
        # 在第一个管理器中注册模块
        manager1.register_module("module1", MockModule(), priority=10)
        manager1.register_module("module2", MockModule(), priority=20)
        
        # 在第二个管理器中注册模块
        manager2.register_module("module3", MockModule(), priority=30)
        
        # 验证注册相互独立
        assert len(manager1._modules) == 2
        assert len(manager2._modules) == 1
        
        assert "module1" in manager1._modules
        assert "module2" in manager1._modules
        assert "module1" not in manager2._modules
        assert "module2" not in manager2._modules
        
        assert "module3" in manager2._modules
        assert "module3" not in manager1._modules
    
    def test_same_module_name_in_different_managers(self):
        """测试不同管理器可以注册同名模块
        
        验证：
        - 不同 SystemManager 实例可以注册同名模块
        - 模块实例相互独立
        
        Requirements: 1.1, 1.2
        """
        # 创建两个 SystemManager 实例
        manager1 = SystemManager()
        manager2 = SystemManager()
        
        # 创建两个不同的模块实例
        module1 = MockModule("instance1")
        module2 = MockModule("instance2")
        
        # 在两个管理器中注册同名模块
        manager1.register_module("same_name", module1, priority=10)
        manager2.register_module("same_name", module2, priority=20)
        
        # 验证两个管理器都有同名模块
        assert "same_name" in manager1._modules
        assert "same_name" in manager2._modules
        
        # 验证模块实例不同
        assert manager1._modules["same_name"].instance is module1
        assert manager2._modules["same_name"].instance is module2
        assert manager1._modules["same_name"].instance is not manager2._modules["same_name"].instance
        
        # 验证优先级不同
        assert manager1._modules["same_name"].priority == 10
        assert manager2._modules["same_name"].priority == 20


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
