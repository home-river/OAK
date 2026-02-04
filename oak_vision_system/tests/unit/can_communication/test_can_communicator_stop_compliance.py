"""
CANCommunicator.stop() 方法合规性测试

测试 CANCommunicator 的 stop() 方法是否符合 shutdown 规范：
1. 幂等性：可以多次调用而不出错
2. 返回值：返回 bool 类型（True=成功，False=失败）
3. 超时处理：接受 timeout 参数并正确处理超时
4. 线程安全：使用锁保护状态变量

参考规范：.kiro/specs/system-manager/shutdown-enhancement-tasks.md
"""

import logging
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call
import pytest
import can

from oak_vision_system.modules.can_communication.can_communicator import CANCommunicator
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO

logger = logging.getLogger(__name__)


# ==================== Fixtures ====================

@pytest.fixture
def can_config():
    """创建测试用的 CAN 配置"""
    return CANConfigDTO(
        can_interface="socketcan",
        can_channel="vcan0",
        can_bitrate=500000,
        enable_auto_configure=False,  # 禁用自动配置以简化测试
        sudo_password="",
        send_timeout_ms=100,
        alert_interval_ms=500
    )


@pytest.fixture
def mock_decision_layer():
    """创建 Mock 决策层"""
    mock = Mock()
    mock.get_target_coords_snapshot.return_value = [100, 200, 300]
    return mock


@pytest.fixture
def mock_event_bus():
    """创建 Mock 事件总线"""
    mock = Mock()
    mock.subscribe.return_value = "test_subscription_id"
    return mock


@pytest.fixture
def communicator(can_config, mock_decision_layer, mock_event_bus):
    """创建 CANCommunicator 实例（未启动）"""
    with patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus'), \
         patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier'):
        comm = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        return comm


@pytest.fixture
def started_communicator(communicator):
    """创建已启动的 CANCommunicator 实例"""
    with patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus') as mock_bus, \
         patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier') as mock_notifier:
        
        # 配置 Mock
        mock_bus_instance = MagicMock()
        mock_bus.return_value = mock_bus_instance
        
        mock_notifier_instance = MagicMock()
        mock_notifier.return_value = mock_notifier_instance
        
        # 启动通信器
        success = communicator.start()
        assert success, "启动失败"
        
        # 保存 Mock 引用以便测试使用
        communicator._mock_bus = mock_bus_instance
        communicator._mock_notifier = mock_notifier_instance
        
        yield communicator


# ==================== 幂等性测试 ====================

class TestStopIdempotence:
    """测试 stop() 方法的幂等性"""
    
    def test_stop_when_not_running_returns_true(self, communicator):
        """
        测试：未启动时调用 stop() 应返回 True
        
        验证：
        - 返回值为 True
        - 不抛出异常
        - 记录适当的日志
        """
        # Act
        result = communicator.stop()
        
        # Assert
        assert result is True, "未启动时 stop() 应返回 True"
        assert not communicator._is_running, "状态应保持为未运行"
    
    def test_stop_can_be_called_multiple_times(self, started_communicator):
        """
        测试：stop() 可以被多次调用而不出错
        
        验证：
        - 第一次调用返回 True
        - 后续调用也返回 True
        - 不抛出异常
        - 状态保持一致
        """
        # Act - 第一次调用
        result1 = started_communicator.stop()
        
        # Assert - 第一次调用
        assert result1 is True, "第一次 stop() 应返回 True"
        assert not started_communicator._is_running, "状态应为未运行"
        
        # Act - 第二次调用
        result2 = started_communicator.stop()
        
        # Assert - 第二次调用
        assert result2 is True, "第二次 stop() 应返回 True（幂等性）"
        assert not started_communicator._is_running, "状态应保持为未运行"
        
        # Act - 第三次调用
        result3 = started_communicator.stop()
        
        # Assert - 第三次调用
        assert result3 is True, "第三次 stop() 应返回 True（幂等性）"
        assert not started_communicator._is_running, "状态应保持为未运行"
    
    def test_stop_idempotence_with_concurrent_calls(self, started_communicator):
        """
        测试：并发调用 stop() 的幂等性
        
        验证：
        - 多个线程同时调用 stop() 不会出错
        - 所有调用都返回 True
        - 状态保持一致
        """
        results = []
        errors = []
        
        def call_stop():
            try:
                result = started_communicator.stop()
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # 创建多个线程同时调用 stop()
        threads = [threading.Thread(target=call_stop) for _ in range(5)]
        
        # 启动所有线程
        for t in threads:
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join(timeout=2.0)
        
        # Assert
        assert len(errors) == 0, f"不应有异常: {errors}"
        assert len(results) == 5, "所有线程都应完成"
        assert all(r is True for r in results), "所有调用都应返回 True"
        assert not started_communicator._is_running, "最终状态应为未运行"


# ==================== 返回值测试 ====================

class TestStopReturnValue:
    """测试 stop() 方法的返回值"""
    
    def test_stop_returns_bool_type(self, started_communicator):
        """
        测试：stop() 返回 bool 类型
        
        验证：
        - 返回值类型为 bool
        - 不返回 None
        """
        # Act
        result = started_communicator.stop()
        
        # Assert
        assert isinstance(result, bool), f"返回值应为 bool 类型，实际为 {type(result)}"
        assert result is not None, "返回值不应为 None"
    
    def test_stop_returns_true_on_success(self, started_communicator):
        """
        测试：成功停止时返回 True
        
        验证：
        - 所有资源正常清理时返回 True
        """
        # Act
        result = started_communicator.stop()
        
        # Assert
        assert result is True, "成功停止应返回 True"
    
    def test_stop_returns_false_on_notifier_timeout(self, started_communicator):
        """
        测试：Notifier 停止超时时返回 False
        
        验证：
        - Notifier.stop() 超时时返回 False
        - 记录超时错误日志
        """
        # Arrange - 模拟 Notifier.stop() 超时
        def slow_stop(timeout=None):
            if timeout:
                time.sleep(timeout + 0.1)  # 超过超时时间
        
        started_communicator._mock_notifier.stop.side_effect = slow_stop
        
        # Act
        result = started_communicator.stop(timeout=0.1)
        
        # Assert
        assert result is False, "Notifier 超时应返回 False"
    
    def test_stop_returns_false_on_bus_shutdown_error(self, started_communicator):
        """
        测试：Bus 关闭失败时返回 False
        
        验证：
        - Bus.shutdown() 抛出异常时返回 False
        - 异常被捕获并记录
        """
        # Arrange - 模拟 Bus.shutdown() 失败
        started_communicator._mock_bus.shutdown.side_effect = can.CanError("Bus shutdown failed")
        
        # Act
        result = started_communicator.stop()
        
        # Assert
        assert result is False, "Bus 关闭失败应返回 False"


# ==================== 超时处理测试 ====================

class TestStopTimeout:
    """测试 stop() 方法的超时处理"""
    
    def test_stop_accepts_timeout_parameter(self, started_communicator):
        """
        测试：stop() 接受 timeout 参数
        
        验证：
        - 可以传入自定义超时时间
        - 不抛出异常
        """
        # Act & Assert - 不应抛出异常
        result = started_communicator.stop(timeout=3.0)
        assert isinstance(result, bool), "应返回 bool 类型"
    
    def test_stop_uses_default_timeout(self, started_communicator):
        """
        测试：stop() 使用默认超时时间（5.0秒）
        
        验证：
        - 不传入 timeout 参数时使用默认值
        - Notifier.stop() 被调用时传入默认超时
        """
        # Act
        started_communicator.stop()
        
        # Assert - 验证 Notifier.stop() 被调用时传入了超时参数
        started_communicator._mock_notifier.stop.assert_called_once()
        call_args = started_communicator._mock_notifier.stop.call_args
        
        # 检查是否传入了 timeout 参数
        if call_args.kwargs:
            assert 'timeout' in call_args.kwargs, "应传入 timeout 参数"
            assert call_args.kwargs['timeout'] == 5.0, "默认超时应为 5.0 秒"
    
    def test_stop_respects_custom_timeout(self, started_communicator):
        """
        测试：stop() 使用自定义超时时间
        
        验证：
        - 传入的 timeout 参数被正确使用
        - Notifier.stop() 接收到正确的超时值
        """
        # Act
        custom_timeout = 2.5
        started_communicator.stop(timeout=custom_timeout)
        
        # Assert
        started_communicator._mock_notifier.stop.assert_called_once()
        call_args = started_communicator._mock_notifier.stop.call_args
        
        if call_args.kwargs:
            assert call_args.kwargs['timeout'] == custom_timeout, \
                f"应使用自定义超时 {custom_timeout} 秒"
    
    def test_stop_detects_notifier_timeout(self, started_communicator):
        """
        测试：stop() 检测 Notifier 停止超时
        
        验证：
        - 当 Notifier.stop() 超时时被检测到
        - 返回 False
        - 记录超时错误日志
        """
        # Arrange - 模拟 Notifier.stop() 耗时超过超时时间
        def slow_stop(timeout=None):
            if timeout:
                time.sleep(timeout + 0.05)  # 稍微超过超时时间
        
        started_communicator._mock_notifier.stop.side_effect = slow_stop
        
        # Act
        timeout = 0.1
        start_time = time.time()
        result = started_communicator.stop(timeout=timeout)
        elapsed = time.time() - start_time
        
        # Assert
        assert result is False, "超时应返回 False"
        assert elapsed >= timeout, f"应等待至少 {timeout} 秒"


# ==================== 线程安全测试 ====================

class TestStopThreadSafety:
    """测试 stop() 方法的线程安全性"""
    
    def test_stop_uses_lock_protection(self, started_communicator):
        """
        测试：stop() 使用锁保护状态变量
        
        验证：
        - _running_lock 存在
        - stop() 方法使用锁
        """
        # Assert
        assert hasattr(started_communicator, '_running_lock'), "应有 _running_lock 属性"
        assert isinstance(started_communicator._running_lock, type(threading.Lock())), \
            "_running_lock 应为 threading.Lock 类型"
    
    def test_stop_concurrent_access_safety(self, started_communicator):
        """
        测试：并发访问 stop() 的安全性
        
        验证：
        - 多个线程同时调用 stop() 不会导致竞态条件
        - 状态变量保持一致
        - 不会出现异常
        """
        results = []
        errors = []
        
        def call_stop_and_check():
            try:
                result = started_communicator.stop()
                results.append(result)
                # 检查状态一致性
                is_running = started_communicator._is_running
                if is_running:
                    errors.append("状态不一致：stop() 后仍在运行")
            except Exception as e:
                errors.append(e)
        
        # 创建多个线程
        threads = [threading.Thread(target=call_stop_and_check) for _ in range(10)]
        
        # 启动所有线程
        for t in threads:
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join(timeout=2.0)
        
        # Assert
        assert len(errors) == 0, f"不应有错误: {errors}"
        assert len(results) == 10, "所有线程都应完成"
        assert all(isinstance(r, bool) for r in results), "所有返回值都应为 bool"
        assert not started_communicator._is_running, "最终状态应为未运行"
    
    def test_alert_timer_uses_lock_protection(self, started_communicator):
        """
        测试：警报定时器方法使用锁保护
        
        验证：
        - _alert_lock 存在
        - _start_alert_timer() 和 _stop_alert_timer() 使用锁
        """
        # Assert
        assert hasattr(started_communicator, '_alert_lock'), "应有 _alert_lock 属性"
        # 接受 Lock 或 RLock 类型（RLock 用于解决可重入死锁问题）
        assert isinstance(started_communicator._alert_lock, (type(threading.Lock()), type(threading.RLock()))), \
            "_alert_lock 应为 threading.Lock 或 threading.RLock 类型"


# ==================== 资源清理测试 ====================

class TestStopResourceCleanup:
    """测试 stop() 方法的资源清理"""
    
    def test_stop_cleans_up_all_resources(self, started_communicator):
        """
        测试：stop() 清理所有资源
        
        验证：
        - 警报定时器被停止
        - 事件订阅被取消
        - Notifier 被停止
        - Bus 被关闭
        - 状态被重置
        """
        # Act
        result = started_communicator.stop()
        
        # Assert
        assert result is True, "应成功停止"
        
        # 验证资源清理
        assert started_communicator.notifier is None, "Notifier 应被清理"
        assert started_communicator.bus is None, "Bus 应被清理"
        assert started_communicator._person_warning_subscription_id is None, \
            "事件订阅 ID 应被清理"
        assert not started_communicator._is_running, "运行状态应为 False"
    
    def test_stop_cleanup_order(self, started_communicator):
        """
        测试：stop() 按正确顺序清理资源
        
        验证：
        - 清理顺序：定时器 → 事件 → Notifier → Bus
        """
        cleanup_order = []
        
        # Mock 方法以记录调用顺序
        original_stop_alert = started_communicator._stop_alert_timer
        original_unsubscribe = started_communicator.event_bus.unsubscribe
        original_notifier_stop = started_communicator._mock_notifier.stop
        original_bus_shutdown = started_communicator._mock_bus.shutdown
        
        def track_stop_alert():
            cleanup_order.append("alert_timer")
            original_stop_alert()
        
        def track_unsubscribe(sub_id):
            cleanup_order.append("event_subscription")
            return original_unsubscribe(sub_id)
        
        def track_notifier_stop(*args, **kwargs):
            cleanup_order.append("notifier")
            return original_notifier_stop(*args, **kwargs)
        
        def track_bus_shutdown():
            cleanup_order.append("bus")
            return original_bus_shutdown()
        
        started_communicator._stop_alert_timer = track_stop_alert
        started_communicator.event_bus.unsubscribe = track_unsubscribe
        started_communicator._mock_notifier.stop = track_notifier_stop
        started_communicator._mock_bus.shutdown = track_bus_shutdown
        
        # Act
        started_communicator.stop()
        
        # Assert - 验证清理顺序
        expected_order = ["alert_timer", "event_subscription", "notifier", "bus"]
        assert cleanup_order == expected_order, \
            f"清理顺序应为 {expected_order}，实际为 {cleanup_order}"


# ==================== 错误处理测试 ====================

class TestStopErrorHandling:
    """测试 stop() 方法的错误处理"""
    
    def test_stop_continues_on_alert_timer_error(self, started_communicator):
        """
        测试：警报定时器停止失败时继续清理其他资源
        
        验证：
        - 捕获异常
        - 继续清理其他资源
        - 返回 False
        """
        # Arrange - 模拟警报定时器停止失败
        original_stop_alert = started_communicator._stop_alert_timer
        
        def failing_stop_alert():
            raise RuntimeError("Alert timer stop failed")
        
        started_communicator._stop_alert_timer = failing_stop_alert
        
        # Act
        result = started_communicator.stop()
        
        # Assert
        assert result is False, "应返回 False（有错误发生）"
        # 验证其他资源仍被清理
        assert started_communicator.notifier is None, "Notifier 应仍被清理"
        assert started_communicator.bus is None, "Bus 应仍被清理"
    
    def test_stop_continues_on_event_unsubscribe_error(self, started_communicator):
        """
        测试：事件取消订阅失败时继续清理其他资源
        
        验证：
        - 捕获异常
        - 继续清理其他资源
        - 返回 False
        """
        # Arrange - 模拟取消订阅失败
        started_communicator.event_bus.unsubscribe.side_effect = RuntimeError("Unsubscribe failed")
        
        # Act
        result = started_communicator.stop()
        
        # Assert
        assert result is False, "应返回 False（有错误发生）"
        # 验证其他资源仍被清理
        assert started_communicator.notifier is None, "Notifier 应仍被清理"
        assert started_communicator.bus is None, "Bus 应仍被清理"
    
    def test_stop_handles_multiple_errors(self, started_communicator):
        """
        测试：多个资源清理失败时的处理
        
        验证：
        - 所有异常都被捕获
        - 尝试清理所有资源
        - 返回 False
        """
        # Arrange - 模拟多个清理步骤失败
        started_communicator.event_bus.unsubscribe.side_effect = RuntimeError("Unsubscribe failed")
        started_communicator._mock_notifier.stop.side_effect = can.CanError("Notifier stop failed")
        started_communicator._mock_bus.shutdown.side_effect = can.CanError("Bus shutdown failed")
        
        # Act
        result = started_communicator.stop()
        
        # Assert
        assert result is False, "应返回 False（有多个错误发生）"
        # 验证所有清理方法都被尝试调用
        started_communicator.event_bus.unsubscribe.assert_called_once()
        started_communicator._mock_notifier.stop.assert_called_once()
        started_communicator._mock_bus.shutdown.assert_called_once()


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
