"""
SystemManager 启动回滚单元测试

测试 SystemManager 类的启动失败回滚功能，包括：
- 测试启动失败触发回滚
- 测试回滚按相反顺序执行
- 测试回滚后模块状态为 STOPPED
- 测试回滚中的异常不阻塞其他模块
- 验证日志记录

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import pytest
import logging
from oak_vision_system.core.system_manager import SystemManager, ModuleState


class MockModule:
    """用于测试的模拟模块"""
    
    def __init__(self, name: str = "mock_module", should_fail_start: bool = False, should_fail_stop: bool = False):
        self.name = name
        self.should_fail_start = should_fail_start
        self.should_fail_stop = should_fail_stop
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
        if self.should_fail_stop:
            raise RuntimeError(f"Mock stop failure: {self.name}")
        self._running = False
    
    def is_running(self):
        """检查模块是否运行中"""
        return self._running


class OrderTrackingModule(MockModule):
    """用于跟踪停止顺序的模拟模块"""
    
    # 类级别的停止顺序记录器
    _stop_order = []
    
    @classmethod
    def reset_order(cls):
        """重置停止顺序记录"""
        cls._stop_order = []
    
    @classmethod
    def get_order(cls):
        """获取停止顺序"""
        return cls._stop_order.copy()
    
    def stop(self):
        """停止模块并记录停止顺序"""
        OrderTrackingModule._stop_order.append(self.name)
        super().stop()


class TestSystemManagerRollback:
    """SystemManager 启动回滚测试套件"""
    
    def test_startup_failure_triggers_rollback(self):
        """
        测试启动失败触发回滚
        
        验证：
        - 当某个模块启动失败时，触发回滚机制
        - 已启动的模块被停止
        - 失败模块的状态为 ERROR
        - 抛出 RuntimeError 异常
        
        Requirements: 3.1, 3.2
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模块：第二个模块启动失败
        module1 = MockModule("module1", should_fail_start=False)
        module2 = MockModule("module2", should_fail_start=True)  # 启动失败
        module3 = MockModule("module3", should_fail_start=False)
        
        # 注册模块（按优先级）
        manager.register_module("module1", module1, priority=30)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=10)
        
        # 尝试启动所有模块，应该失败
        with pytest.raises(RuntimeError) as exc_info:
            manager.start_all()
        
        # 验证异常消息包含失败模块名称
        assert "module2" in str(exc_info.value)
        
        # 验证 module1 被启动了（优先级高，先启动）
        assert module1.start_called is True
        
        # 验证 module2 尝试启动但失败
        assert module2.start_called is True
        
        # 验证 module3 没有被启动（因为 module2 失败了）
        assert module3.start_called is False
        
        # 验证 module1 被回滚停止
        assert module1.stop_called is True
        assert module1.is_running() is False
        
        # 验证失败模块状态为 ERROR
        assert manager._modules["module2"].state == ModuleState.ERROR
        
        # 验证已启动模块状态为 STOPPED（回滚后）
        assert manager._modules["module1"].state == ModuleState.STOPPED
        
        # 验证未启动模块状态仍为 NOT_STARTED
        assert manager._modules["module3"].state == ModuleState.NOT_STARTED
    
    def test_rollback_executes_in_reverse_order(self):
        """
        测试回滚按相反顺序执行
        
        验证：
        - 回滚时按启动的相反顺序停止模块
        - 最后启动的模块最先停止
        
        Requirements: 3.3
        """
        # 重置停止顺序记录
        OrderTrackingModule.reset_order()
        
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模块：第四个模块启动失败
        module1 = OrderTrackingModule("module1", should_fail_start=False)
        module2 = OrderTrackingModule("module2", should_fail_start=False)
        module3 = OrderTrackingModule("module3", should_fail_start=False)
        module4 = OrderTrackingModule("module4", should_fail_start=True)  # 启动失败
        
        # 注册模块（按优先级：40 → 30 → 20 → 10）
        manager.register_module("module1", module1, priority=40)
        manager.register_module("module2", module2, priority=30)
        manager.register_module("module3", module3, priority=20)
        manager.register_module("module4", module4, priority=10)
        
        # 尝试启动所有模块，应该失败
        with pytest.raises(RuntimeError):
            manager.start_all()
        
        # 获取停止顺序
        stop_order = OrderTrackingModule.get_order()
        
        # 验证停止顺序是启动的相反顺序
        # 启动顺序：module1(40) → module2(30) → module3(20) → module4(10失败)
        # 回滚顺序：module3 → module2 → module1
        assert stop_order == ["module3", "module2", "module1"]
        
        # 验证所有已启动的模块都被停止
        assert module1.stop_called is True
        assert module2.stop_called is True
        assert module3.stop_called is True
        
        # 验证失败的模块没有被停止（因为它没有启动成功）
        assert module4.stop_called is False
    
    def test_rollback_sets_module_state_to_stopped(self):
        """
        测试回滚后模块状态为 STOPPED
        
        验证：
        - 回滚成功的模块状态为 STOPPED
        - 失败的模块状态为 ERROR
        - 未启动的模块状态为 NOT_STARTED
        
        Requirements: 3.4
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模块：第三个模块启动失败
        module1 = MockModule("module1", should_fail_start=False)
        module2 = MockModule("module2", should_fail_start=False)
        module3 = MockModule("module3", should_fail_start=True)  # 启动失败
        module4 = MockModule("module4", should_fail_start=False)
        
        # 注册模块
        manager.register_module("module1", module1, priority=40)
        manager.register_module("module2", module2, priority=30)
        manager.register_module("module3", module3, priority=20)
        manager.register_module("module4", module4, priority=10)
        
        # 尝试启动所有模块，应该失败
        with pytest.raises(RuntimeError):
            manager.start_all()
        
        # 验证已启动并回滚的模块状态为 STOPPED
        assert manager._modules["module1"].state == ModuleState.STOPPED
        assert manager._modules["module2"].state == ModuleState.STOPPED
        
        # 验证失败的模块状态为 ERROR
        assert manager._modules["module3"].state == ModuleState.ERROR
        
        # 验证未启动的模块状态为 NOT_STARTED
        assert manager._modules["module4"].state == ModuleState.NOT_STARTED
    
    def test_rollback_exception_does_not_block_other_modules(self):
        """
        测试回滚中的异常不阻塞其他模块
        
        验证：
        - 即使某个模块停止失败，其他模块仍然被停止
        - 停止失败的模块状态为 ERROR
        - 其他模块状态为 STOPPED
        - 回滚继续执行，不抛出异常
        
        Requirements: 3.4, 3.5
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模块：module2 停止失败，module4 启动失败
        module1 = MockModule("module1", should_fail_start=False, should_fail_stop=False)
        module2 = MockModule("module2", should_fail_start=False, should_fail_stop=True)  # 停止失败
        module3 = MockModule("module3", should_fail_start=False, should_fail_stop=False)
        module4 = MockModule("module4", should_fail_start=True, should_fail_stop=False)  # 启动失败
        
        # 注册模块（启动顺序：40 → 30 → 20 → 10）
        manager.register_module("module1", module1, priority=40)
        manager.register_module("module2", module2, priority=30)
        manager.register_module("module3", module3, priority=20)
        manager.register_module("module4", module4, priority=10)
        
        # 尝试启动所有模块，应该失败
        with pytest.raises(RuntimeError):
            manager.start_all()
        
        # 验证所有已启动的模块都尝试停止
        assert module1.stop_called is True
        assert module2.stop_called is True
        assert module3.stop_called is True
        
        # 验证停止成功的模块状态为 STOPPED
        assert manager._modules["module1"].state == ModuleState.STOPPED
        assert manager._modules["module3"].state == ModuleState.STOPPED
        
        # 验证停止失败的模块状态为 ERROR
        assert manager._modules["module2"].state == ModuleState.ERROR
        
        # 验证启动失败的模块状态为 ERROR
        assert manager._modules["module4"].state == ModuleState.ERROR
    
    def test_rollback_logs_warning_and_info(self, caplog):
        """
        测试回滚记录日志
        
        验证：
        - 记录开始回滚的警告日志
        - 记录每个模块的回滚停止日志
        - 记录回滚完成的警告日志
        - 日志包含模块名称
        
        Requirements: 3.2, 13.4
        """
        # 设置日志级别为 INFO
        with caplog.at_level(logging.INFO):
            # 创建 SystemManager
            manager = SystemManager()
            
            # 创建模块：第三个模块启动失败
            module1 = MockModule("module1", should_fail_start=False)
            module2 = MockModule("module2", should_fail_start=False)
            module3 = MockModule("module3", should_fail_start=True)  # 启动失败
            
            # 注册模块
            manager.register_module("module1", module1, priority=30)
            manager.register_module("module2", module2, priority=20)
            manager.register_module("module3", module3, priority=10)
            
            # 清空之前的日志
            caplog.clear()
            
            # 尝试启动所有模块，应该失败并触发回滚
            with pytest.raises(RuntimeError):
                manager.start_all()
            
            # 验证日志记录
            log_messages = [record.message for record in caplog.records]
            
            # 验证包含开始回滚的日志
            assert any("开始回滚启动" in msg for msg in log_messages)
            assert any("停止 2 个已启动的模块" in msg for msg in log_messages)
            
            # 验证包含每个模块的回滚停止日志
            assert any("回滚停止模块: module1" in msg for msg in log_messages)
            assert any("回滚停止模块: module2" in msg for msg in log_messages)
            
            # 验证包含回滚成功的日志
            assert any("模块回滚停止成功: module1" in msg for msg in log_messages)
            assert any("模块回滚停止成功: module2" in msg for msg in log_messages)
            
            # 验证包含回滚完成的日志
            assert any("启动回滚完成" in msg for msg in log_messages)
    
    def test_rollback_logs_error_on_stop_failure(self, caplog):
        """
        测试回滚停止失败时记录错误日志
        
        验证：
        - 停止失败时记录 ERROR 级别日志
        - 日志包含模块名称和错误信息
        - 回滚继续执行
        
        Requirements: 3.4, 13.4
        """
        # 设置日志级别为 ERROR
        with caplog.at_level(logging.ERROR):
            # 创建 SystemManager
            manager = SystemManager()
            
            # 创建模块：module1 停止失败，module2 启动失败
            module1 = MockModule("module1", should_fail_start=False, should_fail_stop=True)  # 停止失败
            module2 = MockModule("module2", should_fail_start=True, should_fail_stop=False)  # 启动失败
            
            # 注册模块
            manager.register_module("module1", module1, priority=20)
            manager.register_module("module2", module2, priority=10)
            
            # 清空之前的日志
            caplog.clear()
            
            # 尝试启动所有模块，应该失败并触发回滚
            with pytest.raises(RuntimeError):
                manager.start_all()
            
            # 验证错误日志
            error_logs = [
                record for record in caplog.records
                if record.levelno == logging.ERROR
            ]
            
            # 验证包含启动失败的错误日志
            assert any("模块启动失败: module2" in record.message for record in error_logs)
            
            # 验证包含回滚停止失败的错误日志
            assert any("回滚停止模块失败: module1" in record.message for record in error_logs)
    
    def test_rollback_with_empty_started_modules_list(self, caplog):
        """
        测试空的已启动模块列表不触发回滚
        
        验证：
        - 当第一个模块启动失败时，没有模块需要回滚
        - 记录 DEBUG 日志
        - 不执行回滚操作
        
        Requirements: 3.1
        """
        # 设置日志级别为 DEBUG
        with caplog.at_level(logging.DEBUG):
            # 创建 SystemManager
            manager = SystemManager()
            
            # 创建模块：第一个模块启动失败
            module1 = MockModule("module1", should_fail_start=True)  # 启动失败
            
            # 注册模块
            manager.register_module("module1", module1, priority=10)
            
            # 清空之前的日志
            caplog.clear()
            
            # 尝试启动所有模块，应该失败
            with pytest.raises(RuntimeError):
                manager.start_all()
            
            # 验证日志包含"没有需要回滚的模块"
            log_messages = [record.message for record in caplog.records]
            assert any("没有需要回滚的模块" in msg for msg in log_messages)
            
            # 验证模块状态为 ERROR
            assert manager._modules["module1"].state == ModuleState.ERROR


class TestSystemManagerRollbackEdgeCases:
    """SystemManager 启动回滚边界情况测试"""
    
    def test_rollback_with_multiple_stop_failures(self):
        """
        测试多个模块停止失败的情况
        
        验证：
        - 即使多个模块停止失败，回滚仍然继续
        - 所有停止失败的模块状态为 ERROR
        - 记录所有错误日志
        
        Requirements: 3.4, 3.5
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模块：module1 和 module2 停止失败，module4 启动失败
        module1 = MockModule("module1", should_fail_start=False, should_fail_stop=True)  # 停止失败
        module2 = MockModule("module2", should_fail_start=False, should_fail_stop=True)  # 停止失败
        module3 = MockModule("module3", should_fail_start=False, should_fail_stop=False)
        module4 = MockModule("module4", should_fail_start=True, should_fail_stop=False)  # 启动失败
        
        # 注册模块
        manager.register_module("module1", module1, priority=40)
        manager.register_module("module2", module2, priority=30)
        manager.register_module("module3", module3, priority=20)
        manager.register_module("module4", module4, priority=10)
        
        # 尝试启动所有模块，应该失败
        with pytest.raises(RuntimeError):
            manager.start_all()
        
        # 验证所有已启动的模块都尝试停止
        assert module1.stop_called is True
        assert module2.stop_called is True
        assert module3.stop_called is True
        
        # 验证停止失败的模块状态为 ERROR
        assert manager._modules["module1"].state == ModuleState.ERROR
        assert manager._modules["module2"].state == ModuleState.ERROR
        
        # 验证停止成功的模块状态为 STOPPED
        assert manager._modules["module3"].state == ModuleState.STOPPED
        
        # 验证启动失败的模块状态为 ERROR
        assert manager._modules["module4"].state == ModuleState.ERROR
    
    def test_rollback_with_all_modules_stop_failure(self):
        """
        测试所有模块停止都失败的情况
        
        验证：
        - 即使所有模块停止都失败，回滚仍然完成
        - 所有模块状态为 ERROR
        - 不抛出异常（只记录日志）
        
        Requirements: 3.4, 3.5
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模块：所有模块停止都失败，最后一个启动失败
        module1 = MockModule("module1", should_fail_start=False, should_fail_stop=True)
        module2 = MockModule("module2", should_fail_start=False, should_fail_stop=True)
        module3 = MockModule("module3", should_fail_start=True, should_fail_stop=False)  # 启动失败
        
        # 注册模块
        manager.register_module("module1", module1, priority=30)
        manager.register_module("module2", module2, priority=20)
        manager.register_module("module3", module3, priority=10)
        
        # 尝试启动所有模块，应该失败
        with pytest.raises(RuntimeError):
            manager.start_all()
        
        # 验证所有已启动的模块都尝试停止
        assert module1.stop_called is True
        assert module2.stop_called is True
        
        # 验证所有停止失败的模块状态为 ERROR
        assert manager._modules["module1"].state == ModuleState.ERROR
        assert manager._modules["module2"].state == ModuleState.ERROR
        assert manager._modules["module3"].state == ModuleState.ERROR
    
    def test_rollback_preserves_original_exception(self):
        """
        测试回滚后重新抛出原始异常
        
        验证：
        - 回滚完成后重新抛出原始的启动失败异常
        - 异常类型为 RuntimeError
        - 异常消息包含失败模块名称
        - 异常链保留原始异常
        
        Requirements: 3.5
        """
        # 创建 SystemManager
        manager = SystemManager()
        
        # 创建模块：module2 启动失败
        module1 = MockModule("module1", should_fail_start=False)
        module2 = MockModule("module2", should_fail_start=True)  # 启动失败
        
        # 注册模块
        manager.register_module("module1", module1, priority=20)
        manager.register_module("module2", module2, priority=10)
        
        # 尝试启动所有模块，应该失败
        with pytest.raises(RuntimeError) as exc_info:
            manager.start_all()
        
        # 验证异常类型
        assert isinstance(exc_info.value, RuntimeError)
        
        # 验证异常消息包含失败模块名称
        assert "module2" in str(exc_info.value)
        
        # 验证异常链保留原始异常
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert "Mock start failure: module2" in str(exc_info.value.__cause__)


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
