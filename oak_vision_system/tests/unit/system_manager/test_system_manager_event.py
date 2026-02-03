"""
SystemManager 事件处理单元测试

测试 SystemManager 的事件处理功能，包括：
- 接收 SYSTEM_SHUTDOWN 事件
- _shutdown_event 被正确设置
- 日志记录包含 reason
- 方法不抛出异常

Requirements: 5.2, 5.3, 5.4
"""

import logging
import pytest
from unittest.mock import Mock, patch

from oak_vision_system.core.system_manager import (
    SystemManager,
    ShutdownEvent,
)
from oak_vision_system.core.event_bus import EventBus


class TestSystemManagerEventHandling:
    """SystemManager 事件处理测试套件"""
    
    @pytest.fixture
    def event_bus(self):
        """创建事件总线实例"""
        return EventBus()
    
    @pytest.fixture
    def manager(self, event_bus):
        """创建 SystemManager 实例"""
        return SystemManager(event_bus=event_bus)
    
    def test_on_shutdown_event_sets_flag(self, manager):
        """测试 _on_shutdown_event 设置 _shutdown_event 标志"""
        # 验证初始状态：_shutdown_event 未设置
        assert not manager._shutdown_event.is_set()
        
        # 创建 ShutdownEvent
        event = ShutdownEvent(reason="user_quit")
        
        # 调用事件处理方法
        manager._on_shutdown_event(event)
        
        # 验证 _shutdown_event 被设置
        assert manager._shutdown_event.is_set()
    
    def test_on_shutdown_event_logs_reason(self, manager, caplog):
        """测试 _on_shutdown_event 记录日志包含 reason"""
        # 设置日志级别为 INFO
        caplog.set_level(logging.INFO)
        
        # 创建 ShutdownEvent
        event = ShutdownEvent(reason="window_closed")
        
        # 调用事件处理方法
        manager._on_shutdown_event(event)
        
        # 验证日志记录包含 reason
        assert any("window_closed" in record.message for record in caplog.records)
        assert any("接收到退出事件" in record.message for record in caplog.records)
    
    def test_on_shutdown_event_with_different_reasons(self, manager, caplog):
        """测试 _on_shutdown_event 处理不同的 reason"""
        caplog.set_level(logging.INFO)
        
        # 测试多个不同的 reason
        reasons = ["user_quit", "key_q", "ctrl_c", "error", "custom_reason"]
        
        for reason in reasons:
            # 清空日志记录
            caplog.clear()
            
            # 重置 _shutdown_event
            manager._shutdown_event.clear()
            
            # 创建事件并调用处理方法
            event = ShutdownEvent(reason=reason)
            manager._on_shutdown_event(event)
            
            # 验证标志被设置
            assert manager._shutdown_event.is_set()
            
            # 验证日志包含 reason
            assert any(reason in record.message for record in caplog.records)
    
    def test_on_shutdown_event_does_not_raise_exception(self, manager):
        """测试 _on_shutdown_event 不抛出异常"""
        # 创建正常的 ShutdownEvent
        event = ShutdownEvent(reason="user_quit")
        
        # 调用方法不应该抛出异常
        try:
            manager._on_shutdown_event(event)
        except Exception as e:
            pytest.fail(f"_on_shutdown_event 不应该抛出异常，但抛出了: {e}")
    
    def test_on_shutdown_event_with_missing_reason_attribute(self, manager, caplog):
        """测试 _on_shutdown_event 处理缺少 reason 属性的事件"""
        caplog.set_level(logging.INFO)
        
        # 创建一个没有 reason 属性的对象
        event = Mock(spec=[])  # 空 spec，没有任何属性
        
        # 调用方法不应该抛出异常
        try:
            manager._on_shutdown_event(event)
        except Exception as e:
            pytest.fail(f"_on_shutdown_event 应该处理缺少 reason 的情况，但抛出了: {e}")
        
        # 验证标志被设置
        assert manager._shutdown_event.is_set()
        
        # 验证日志包含 "unknown"（默认值）
        assert any("unknown" in record.message for record in caplog.records)
    
    def test_on_shutdown_event_idempotent(self, manager):
        """测试 _on_shutdown_event 可以被多次调用"""
        # 创建事件
        event = ShutdownEvent(reason="user_quit")
        
        # 第一次调用
        manager._on_shutdown_event(event)
        assert manager._shutdown_event.is_set()
        
        # 第二次调用（标志已经设置）
        manager._on_shutdown_event(event)
        assert manager._shutdown_event.is_set()
        
        # 第三次调用
        manager._on_shutdown_event(event)
        assert manager._shutdown_event.is_set()
    
    def test_system_shutdown_event_subscription(self, event_bus, manager):
        """测试 SystemManager 订阅了 SYSTEM_SHUTDOWN 事件"""
        # 验证初始状态
        assert not manager._shutdown_event.is_set()
        
        # 通过事件总线发布 SYSTEM_SHUTDOWN 事件
        event = ShutdownEvent(reason="test_subscription")
        event_bus.publish("SYSTEM_SHUTDOWN", event)
        
        # 等待事件处理（事件总线是异步的）
        import time
        time.sleep(0.1)
        
        # 验证 _shutdown_event 被设置
        assert manager._shutdown_event.is_set()
    
    def test_on_shutdown_event_only_sets_flag(self, manager):
        """测试 _on_shutdown_event 只做置位操作，不执行复杂逻辑"""
        # 创建事件
        event = ShutdownEvent(reason="user_quit")
        
        # 记录调用前的状态
        modules_before = dict(manager._modules)
        stop_started_before = manager._stop_started.is_set()
        
        # 调用事件处理方法
        manager._on_shutdown_event(event)
        
        # 验证只有 _shutdown_event 被设置
        assert manager._shutdown_event.is_set()
        
        # 验证其他状态没有改变
        assert manager._modules == modules_before
        assert manager._stop_started.is_set() == stop_started_before
    
    def test_on_shutdown_event_with_empty_reason(self, manager, caplog):
        """测试 _on_shutdown_event 处理空 reason"""
        caplog.set_level(logging.INFO)
        
        # 创建空 reason 的事件
        event = ShutdownEvent(reason="")
        
        # 调用方法不应该抛出异常
        manager._on_shutdown_event(event)
        
        # 验证标志被设置
        assert manager._shutdown_event.is_set()
        
        # 验证日志被记录（即使 reason 为空）
        assert any("接收到退出事件" in record.message for record in caplog.records)
    
    def test_on_shutdown_event_with_long_reason(self, manager, caplog):
        """测试 _on_shutdown_event 处理长 reason 字符串"""
        caplog.set_level(logging.INFO)
        
        # 创建长 reason 的事件
        long_reason = "系统检测到严重错误，需要立即停止所有模块以防止数据损坏" * 10
        event = ShutdownEvent(reason=long_reason)
        
        # 调用方法不应该抛出异常
        manager._on_shutdown_event(event)
        
        # 验证标志被设置
        assert manager._shutdown_event.is_set()
        
        # 验证日志包含部分 reason（可能被截断）
        assert any("接收到退出事件" in record.message for record in caplog.records)


class TestSystemManagerEventIntegration:
    """SystemManager 事件处理集成测试"""
    
    @pytest.fixture
    def event_bus(self):
        """创建事件总线实例"""
        return EventBus()
    
    @pytest.fixture
    def manager(self, event_bus):
        """创建 SystemManager 实例"""
        return SystemManager(event_bus=event_bus)
    
    def test_multiple_shutdown_events(self, event_bus, manager):
        """测试多个 SYSTEM_SHUTDOWN 事件"""
        # 发布多个事件
        for i in range(5):
            event = ShutdownEvent(reason=f"event_{i}")
            event_bus.publish("SYSTEM_SHUTDOWN", event)
        
        # 等待事件处理
        import time
        time.sleep(0.2)
        
        # 验证标志被设置（只需要设置一次）
        assert manager._shutdown_event.is_set()
    
    def test_shutdown_event_from_different_threads(self, manager):
        """测试从不同线程调用 _on_shutdown_event"""
        import threading
        
        # 创建多个线程同时调用事件处理方法
        threads = []
        for i in range(10):
            event = ShutdownEvent(reason=f"thread_{i}")
            thread = threading.Thread(
                target=manager._on_shutdown_event,
                args=(event,)
            )
            threads.append(thread)
        
        # 启动所有线程
        for thread in threads:
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证标志被设置
        assert manager._shutdown_event.is_set()


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
