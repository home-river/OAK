"""
SystemManager 端到端集成测试

测试 SystemManager 与子模块的完整集成，包括：
1. 正常启动和关闭流程
2. 模块停止失败场景（兜底机制）
3. 混合失败场景

使用 Mock 模块模拟真实模块行为，避免硬件依赖。
"""

import logging
import os
import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

from oak_vision_system.core.system_manager import (
    SystemManager,
    ModuleState,
    ShutdownEvent,
)
from oak_vision_system.core.event_bus import EventBus


class MockModule:
    """
    模拟模块类
    
    用于测试的模拟模块，可以配置启动/停止行为。
    """
    
    def __init__(
        self,
        name: str,
        should_fail_start: bool = False,
        should_fail_stop: bool = False,
        stop_timeout: bool = False,
        stop_return_false: bool = False
    ):
        """
        初始化模拟模块
        
        Args:
            name: 模块名称
            should_fail_start: 启动时是否抛出异常
            should_fail_stop: 停止时是否抛出异常
            stop_timeout: 停止时是否模拟超时（不返回）
            stop_return_false: 停止时是否返回 False
        """
        self.name = name
        self.should_fail_start = should_fail_start
        self.should_fail_stop = should_fail_stop
        self.stop_timeout = stop_timeout
        self.stop_return_false = stop_return_false
        
        self.start_called = False
        self.stop_called = False
        self._running = False
        self._lock = threading.Lock()
    
    def start(self):
        """启动模块"""
        with self._lock:
            if self.should_fail_start:
                raise RuntimeError(f"Mock start failure: {self.name}")
            
            self.start_called = True
            self._running = True
    
    def stop(self, timeout: float = 5.0) -> bool:
        """停止模块"""
        with self._lock:
            self.stop_called = True
            
            if self.stop_timeout:
                # 模拟超时：阻塞很长时间
                time.sleep(timeout + 1)
                return False
            
            if self.should_fail_stop:
                raise RuntimeError(f"Mock stop failure: {self.name}")
            
            if self.stop_return_false:
                return False
            
            self._running = False
            return True
    
    def is_running(self) -> bool:
        """检查是否运行中"""
        with self._lock:
            return self._running


class TestSystemManagerE2ENormalFlow(unittest.TestCase):
    """测试正常关闭流程"""
    
    def setUp(self):
        """测试前准备"""
        # 创建独立的事件总线
        self.event_bus = EventBus()
        
        # 创建 SystemManager（不初始化日志系统）
        self.manager = SystemManager(
            event_bus=self.event_bus,
            system_config=None,
            default_stop_timeout=5.0,
            force_exit_grace_period=1.0  # 缩短宽限期以加快测试
        )
        
        # 创建模拟模块
        self.collector = MockModule("collector")
        self.processor = MockModule("processor")
        self.display = MockModule("display")
    
    def tearDown(self):
        """测试后清理"""
        # 确保事件总线关闭
        try:
            self.event_bus.close(wait=False, cancel_pending=True)
        except:
            pass
    
    def test_normal_startup_and_shutdown(self):
        """测试正常启动和关闭流程"""
        # 注册模块
        self.manager.register_module("collector", self.collector, priority=10)
        self.manager.register_module("processor", self.processor, priority=30)
        self.manager.register_module("display", self.display, priority=50)
        
        # 启动所有模块
        self.manager.start_all()
        
        # 验证启动顺序（按优先级从高到低）
        self.assertTrue(self.display.start_called)
        self.assertTrue(self.processor.start_called)
        self.assertTrue(self.collector.start_called)
        
        # 验证所有模块状态为 RUNNING
        status = self.manager.get_status()
        self.assertEqual(status["collector"], "running")
        self.assertEqual(status["processor"], "running")
        self.assertEqual(status["display"], "running")
        
        # 关闭系统
        self.manager.shutdown()
        
        # 验证关闭顺序（按优先级从低到高）
        self.assertTrue(self.collector.stop_called)
        self.assertTrue(self.processor.stop_called)
        self.assertTrue(self.display.stop_called)
        
        # 验证所有模块状态为 STOPPED
        status = self.manager.get_status()
        self.assertEqual(status["collector"], "stopped")
        self.assertEqual(status["processor"], "stopped")
        self.assertEqual(status["display"], "stopped")
        
        # 验证系统正在关闭
        self.assertTrue(self.manager.is_shutting_down())
    
    def test_shutdown_idempotence(self):
        """测试 shutdown 方法的幂等性"""
        # 注册并启动模块
        self.manager.register_module("collector", self.collector, priority=10)
        self.manager.start_all()
        
        # 第一次关闭
        self.manager.shutdown()
        self.assertTrue(self.collector.stop_called)
        
        # 重置 stop_called 标志
        self.collector.stop_called = False
        
        # 第二次关闭（应该被跳过）
        self.manager.shutdown()
        self.assertFalse(self.collector.stop_called)  # 不应该再次调用
    
    def test_run_with_shutdown_event(self):
        """测试通过 SYSTEM_SHUTDOWN 事件退出"""
        # 注册并启动模块
        self.manager.register_module("collector", self.collector, priority=10)
        self.manager.start_all()
        
        # 在后台线程中运行 manager.run()
        run_thread = threading.Thread(
            target=lambda: self.manager.run(force_exit_on_shutdown_failure=False),
            daemon=True
        )
        run_thread.start()
        
        # 等待一小段时间确保 run() 进入主循环
        time.sleep(0.5)
        
        # 发布 SYSTEM_SHUTDOWN 事件
        self.event_bus.publish(
            "SYSTEM_SHUTDOWN",
            ShutdownEvent(reason="test_shutdown")
        )
        
        # 等待 run() 线程结束
        run_thread.join(timeout=5.0)
        
        # 验证线程已结束
        self.assertFalse(run_thread.is_alive())
        
        # 验证模块已停止
        self.assertTrue(self.collector.stop_called)
        self.assertTrue(self.manager.is_shutting_down())


class TestSystemManagerE2EFailureScenarios(unittest.TestCase):
    """测试模块停止失败场景（兜底机制）"""
    
    def setUp(self):
        """测试前准备"""
        # 创建独立的事件总线
        self.event_bus = EventBus()
        
        # 创建 SystemManager（不初始化日志系统）
        self.manager = SystemManager(
            event_bus=self.event_bus,
            system_config=None,
            default_stop_timeout=5.0,
            force_exit_grace_period=0.5  # 缩短宽限期以加快测试
        )
    
    def tearDown(self):
        """测试后清理"""
        # 确保事件总线关闭
        try:
            self.event_bus.close(wait=False, cancel_pending=True)
        except:
            pass
    
    def test_module_stop_returns_false(self):
        """测试模块 stop() 返回 False 时 shutdown 返回 False"""
        # 创建一个会返回 False 的模块
        failing_module = MockModule("failing_module", stop_return_false=True)
        
        # 注册并启动模块
        self.manager.register_module("failing_module", failing_module, priority=10)
        self.manager.start_all()
        
        # 关闭系统
        result = self.manager.shutdown()
        
        # 验证 shutdown 返回 False（表示失败）
        self.assertFalse(result)
        
        # 验证模块状态为 ERROR
        status = self.manager.get_status()
        self.assertEqual(status["failing_module"], "error")
    
    def test_module_stop_raises_exception(self):
        """测试模块 stop() 抛出异常时 shutdown 返回 False"""
        # 创建一个会抛出异常的模块
        failing_module = MockModule("failing_module", should_fail_stop=True)
        
        # 注册并启动模块
        self.manager.register_module("failing_module", failing_module, priority=10)
        self.manager.start_all()
        
        # 关闭系统
        result = self.manager.shutdown()
        
        # 验证 shutdown 返回 False（表示失败）
        self.assertFalse(result)
        
        # 验证模块状态为 ERROR
        status = self.manager.get_status()
        self.assertEqual(status["failing_module"], "error")
    
    def test_multiple_modules_fail(self):
        """测试多个模块停止失败时 shutdown 返回 False"""
        # 创建多个会失败的模块
        failing_module1 = MockModule("failing1", stop_return_false=True)
        failing_module2 = MockModule("failing2", should_fail_stop=True)
        
        # 注册并启动模块
        self.manager.register_module("failing1", failing_module1, priority=10)
        self.manager.register_module("failing2", failing_module2, priority=20)
        self.manager.start_all()
        
        # 关闭系统
        result = self.manager.shutdown()
        
        # 验证 shutdown 返回 False（表示失败）
        self.assertFalse(result)
        
        # 验证所有失败模块状态为 ERROR
        status = self.manager.get_status()
        self.assertEqual(status["failing1"], "error")
        self.assertEqual(status["failing2"], "error")


class TestSystemManagerE2EMixedScenarios(unittest.TestCase):
    """测试混合失败场景"""
    
    def setUp(self):
        """测试前准备"""
        # 创建独立的事件总线
        self.event_bus = EventBus()
        
        # 创建 SystemManager（不初始化日志系统）
        self.manager = SystemManager(
            event_bus=self.event_bus,
            system_config=None,
            default_stop_timeout=5.0,
            force_exit_grace_period=0.5  # 缩短宽限期以加快测试
        )
    
    def tearDown(self):
        """测试后清理"""
        # 确保事件总线关闭
        try:
            self.event_bus.close(wait=False, cancel_pending=True)
        except:
            pass
    
    def test_partial_failure(self):
        """测试部分模块成功、部分失败时 shutdown 返回 False"""
        # 创建模块：一个成功，两个失败
        success_module = MockModule("success")
        failing_module1 = MockModule("failing1", stop_return_false=True)
        failing_module2 = MockModule("failing2", should_fail_stop=True)
        
        # 注册并启动模块
        self.manager.register_module("success", success_module, priority=10)
        self.manager.register_module("failing1", failing_module1, priority=20)
        self.manager.register_module("failing2", failing_module2, priority=30)
        self.manager.start_all()
        
        # 关闭系统
        result = self.manager.shutdown()
        
        # 验证 shutdown 返回 False（表示失败）
        self.assertFalse(result)
        
        # 验证成功的模块正常关闭
        self.assertTrue(success_module.stop_called)
        status = self.manager.get_status()
        self.assertEqual(status["success"], "stopped")
        
        # 验证失败的模块状态为 ERROR
        self.assertEqual(status["failing1"], "error")
        self.assertEqual(status["failing2"], "error")
    
    def test_failure_does_not_block_other_modules(self):
        """测试失败的模块不会阻塞其他模块的关闭"""
        # 创建模块：第一个失败，后面的应该继续执行
        failing_module = MockModule("failing", should_fail_stop=True)
        module1 = MockModule("module1")
        module2 = MockModule("module2")
        
        # 注册并启动模块（按优先级：failing=10, module1=20, module2=30）
        self.manager.register_module("failing", failing_module, priority=10)
        self.manager.register_module("module1", module1, priority=20)
        self.manager.register_module("module2", module2, priority=30)
        self.manager.start_all()
        
        # 关闭系统
        result = self.manager.shutdown()
        
        # 验证 shutdown 返回 False（表示失败）
        self.assertFalse(result)
        
        # 验证所有模块的 stop() 都被调用（即使第一个失败）
        self.assertTrue(failing_module.stop_called)
        self.assertTrue(module1.stop_called)
        self.assertTrue(module2.stop_called)
        
        # 验证成功的模块状态为 STOPPED
        status = self.manager.get_status()
        self.assertEqual(status["module1"], "stopped")
        self.assertEqual(status["module2"], "stopped")
        
        # 验证失败的模块状态为 ERROR
        self.assertEqual(status["failing"], "error")


class TestSystemManagerE2EStartupFailure(unittest.TestCase):
    """测试启动失败和回滚场景"""
    
    def setUp(self):
        """测试前准备"""
        # 创建独立的事件总线
        self.event_bus = EventBus()
        
        # 创建 SystemManager（不初始化日志系统）
        self.manager = SystemManager(
            event_bus=self.event_bus,
            system_config=None,
            default_stop_timeout=5.0,
            force_exit_grace_period=1.0
        )
    
    def tearDown(self):
        """测试后清理"""
        # 确保事件总线关闭
        try:
            self.event_bus.close(wait=False, cancel_pending=True)
        except:
            pass
    
    def test_startup_failure_triggers_rollback(self):
        """测试启动失败触发回滚"""
        # 创建模块：第二个会启动失败
        module1 = MockModule("module1")
        failing_module = MockModule("failing", should_fail_start=True)
        module3 = MockModule("module3")
        
        # 注册模块（按优先级：module3=30, failing=20, module1=10）
        self.manager.register_module("module1", module1, priority=10)
        self.manager.register_module("failing", failing_module, priority=20)
        self.manager.register_module("module3", module3, priority=30)
        
        # 尝试启动所有模块（应该失败）
        with self.assertRaises(RuntimeError):
            self.manager.start_all()
        
        # 验证启动顺序：module3(30) → failing(20) → module1(10)
        # module3 应该启动成功
        self.assertTrue(module3.start_called)
        
        # failing 应该启动失败
        self.assertFalse(failing_module.start_called)  # start() 抛出异常
        
        # module1 不应该被启动（因为 failing 失败了）
        self.assertFalse(module1.start_called)
        
        # 验证回滚：module3 应该被停止
        self.assertTrue(module3.stop_called)
        
        # 验证模块状态
        status = self.manager.get_status()
        self.assertEqual(status["module3"], "stopped")  # 回滚停止
        self.assertEqual(status["failing"], "error")    # 启动失败
        self.assertEqual(status["module1"], "not_started")  # 未启动


class TestSystemManagerE2EContextManager(unittest.TestCase):
    """测试上下文管理器"""
    
    def setUp(self):
        """测试前准备"""
        # 创建独立的事件总线
        self.event_bus = EventBus()
    
    def tearDown(self):
        """测试后清理"""
        # 确保事件总线关闭
        try:
            self.event_bus.close(wait=False, cancel_pending=True)
        except:
            pass
    
    def test_context_manager_normal_flow(self):
        """测试上下文管理器正常流程"""
        # 创建模块
        module = MockModule("module")
        
        # 创建 SystemManager 并注册模块
        manager = SystemManager(
            event_bus=self.event_bus,
            system_config=None
        )
        manager.register_module("module", module, priority=10)
        
        # 使用上下文管理器
        with manager:
            # 手动调用 start_all()（__enter__ 不再自动调用）
            manager.start_all()
            # 验证模块已启动
            self.assertTrue(module.start_called)
        
        # __exit__ 会自动调用 shutdown()
        # 验证模块已停止
        self.assertTrue(module.stop_called)
    
    @patch('os._exit')
    def test_context_manager_with_exception(self, mock_exit):
        """测试上下文管理器在异常情况下的行为"""
        # 创建模块
        module = MockModule("module")
        
        # 创建 SystemManager 并注册模块
        manager = SystemManager(
            event_bus=self.event_bus,
            system_config=None
        )
        manager.register_module("module", module, priority=10)
        
        # 使用上下文管理器，并在内部抛出异常
        with self.assertRaises(ValueError):
            with manager:
                # 手动调用 start_all()（__enter__ 不再自动调用）
                manager.start_all()
                # 验证模块已启动
                self.assertTrue(module.start_called)
                
                # 抛出异常
                raise ValueError("Test exception")
        
        # __exit__ 仍然会调用 shutdown()
        # 验证模块已停止
        self.assertTrue(module.stop_called)


class TestSystemManagerE2EDisplayModule(unittest.TestCase):
    """测试 SystemManager 与显示模块的集成"""
    
    def setUp(self):
        """测试前准备"""
        # 创建独立的事件总线
        self.event_bus = EventBus()
        
        # 创建 SystemManager
        self.manager = SystemManager(
            event_bus=self.event_bus,
            system_config=None,
            default_stop_timeout=5.0,
            force_exit_grace_period=1.0
        )
    
    def tearDown(self):
        """测试后清理"""
        # 确保事件总线关闭
        try:
            self.event_bus.close(wait=False, cancel_pending=True)
        except:
            pass
    
    def test_register_display_module(self):
        """测试注册显示模块"""
        # 创建模拟显示模块
        display_module = MockModule("display")
        
        # 注册显示模块
        self.manager.register_display_module("display", display_module, priority=50)
        
        # 验证模块已注册
        status = self.manager.get_status()
        self.assertEqual(status["display"], "not_started")
        
        # 验证 _display_module 被设置
        self.assertIsNotNone(self.manager._display_module)
        self.assertEqual(self.manager._display_module, display_module)
    
    def test_cannot_register_multiple_display_modules(self):
        """测试不能重复注册显示模块"""
        # 创建两个模拟显示模块
        display1 = MockModule("display1")
        display2 = MockModule("display2")
        
        # 注册第一个显示模块
        self.manager.register_display_module("display1", display1, priority=50)
        
        # 尝试注册第二个显示模块（应该失败）
        with self.assertRaises(ValueError) as context:
            self.manager.register_display_module("display2", display2, priority=50)
        
        # 验证错误消息
        self.assertIn("已经注册了显示模块", str(context.exception))
    
    def test_run_with_display_module_calls_render_once(self):
        """测试 run() 循环调用 display_module.render_once()"""
        # 创建模拟显示模块
        display_module = Mock()
        display_module.start.return_value = True
        display_module.stop.return_value = True
        
        # 配置 render_once：前几次返回 False，最后返回 True 触发退出
        render_calls = [False, False, False, True]
        display_module.render_once.side_effect = render_calls
        
        # 注册并启动显示模块
        self.manager.register_display_module("display", display_module, priority=50)
        self.manager.start_all()
        
        # 在后台线程中运行 run()
        run_thread = threading.Thread(
            target=lambda: self.manager.run(force_exit_on_shutdown_failure=False),
            daemon=True
        )
        run_thread.start()
        
        # 等待 run() 线程结束
        run_thread.join(timeout=5.0)
        
        # 验证线程已结束
        self.assertFalse(run_thread.is_alive())
        
        # 验证 render_once() 被调用了 4 次
        self.assertEqual(display_module.render_once.call_count, 4)
        
        # 验证模块已停止
        self.assertTrue(display_module.stop.called)
    
    def test_render_once_returns_true_triggers_shutdown(self):
        """测试 render_once() 返回 True 触发系统关闭"""
        # 创建模拟显示模块
        display_module = Mock()
        display_module.start.return_value = True
        display_module.stop.return_value = True
        display_module.render_once.return_value = True  # 立即返回 True
        
        # 注册并启动显示模块
        self.manager.register_display_module("display", display_module, priority=50)
        self.manager.start_all()
        
        # 在后台线程中运行 run()
        run_thread = threading.Thread(
            target=lambda: self.manager.run(force_exit_on_shutdown_failure=False),
            daemon=True
        )
        run_thread.start()
        
        # 等待 run() 线程结束
        run_thread.join(timeout=5.0)
        
        # 验证线程已结束
        self.assertFalse(run_thread.is_alive())
        
        # 验证 render_once() 被调用
        self.assertTrue(display_module.render_once.called)
        
        # 验证系统正在关闭
        self.assertTrue(self.manager.is_shutting_down())
        
        # 验证模块已停止
        self.assertTrue(display_module.stop.called)
    
    def test_render_once_exception_does_not_stop_loop(self):
        """测试 render_once() 异常不会中断主循环"""
        # 创建模拟显示模块
        display_module = Mock()
        display_module.start.return_value = True
        display_module.stop.return_value = True
        
        # 配置 render_once：前两次抛异常，第三次返回 True 触发退出
        render_calls = [
            RuntimeError("渲染错误1"),
            RuntimeError("渲染错误2"),
            True
        ]
        display_module.render_once.side_effect = render_calls
        
        # 注册并启动显示模块
        self.manager.register_display_module("display", display_module, priority=50)
        self.manager.start_all()
        
        # 在后台线程中运行 run()
        run_thread = threading.Thread(
            target=lambda: self.manager.run(force_exit_on_shutdown_failure=False),
            daemon=True
        )
        run_thread.start()
        
        # 等待 run() 线程结束
        run_thread.join(timeout=5.0)
        
        # 验证线程已结束
        self.assertFalse(run_thread.is_alive())
        
        # 验证 render_once() 被调用了 3 次（异常后继续运行）
        self.assertEqual(display_module.render_once.call_count, 3)
        
        # 验证模块已停止
        self.assertTrue(display_module.stop.called)
    
    def test_run_without_display_module_uses_wait_logic(self):
        """测试没有显示模块时使用等待逻辑"""
        # 创建普通模块（非显示模块）
        module = MockModule("module")
        
        # 注册并启动模块
        self.manager.register_module("module", module, priority=10)
        self.manager.start_all()
        
        # 在后台线程中运行 run()
        run_thread = threading.Thread(
            target=lambda: self.manager.run(force_exit_on_shutdown_failure=False),
            daemon=True
        )
        run_thread.start()
        
        # 等待一小段时间确保 run() 进入主循环
        time.sleep(0.5)
        
        # 发布 SYSTEM_SHUTDOWN 事件触发退出
        self.event_bus.publish(
            "SYSTEM_SHUTDOWN",
            ShutdownEvent(reason="test_shutdown")
        )
        
        # 等待 run() 线程结束
        run_thread.join(timeout=5.0)
        
        # 验证线程已结束
        self.assertFalse(run_thread.is_alive())
        
        # 验证模块已停止
        self.assertTrue(module.stop_called)


if __name__ == "__main__":
    # 配置日志（仅用于调试）
    logging.basicConfig(
        level=logging.WARNING,  # 设置为 WARNING 以减少测试输出
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    unittest.main()
