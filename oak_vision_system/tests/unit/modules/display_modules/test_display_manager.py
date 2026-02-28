"""
测试 DisplayManager 主线程渲染重构（任务 4.4）

验证需求：
- 1.4: start() 不创建渲染线程
- 4.1: start() 创建打包线程
- 6.1: render_once() 执行一次渲染循环
- 6.2: render_once() 正常渲染返回 False
- 6.3: render_once() 按 'q' 键返回 True
- 6.4: render_once() 异常处理
- 9.1: 捕获异常并记录错误日志
- 9.2: 异常时返回 False 以继续运行
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import threading
import time

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO, DeviceRole
from oak_vision_system.modules.display_modules.display_manager import DisplayManager


class TestDisplayManagerMainThreadRendering(unittest.TestCase):
    """测试 DisplayManager 主线程渲染架构"""
    
    def setUp(self):
        """测试前准备"""
        self.device_id_left = "device_left_001"
        self.device_id_right = "device_right_002"
        self.devices_list = [self.device_id_left, self.device_id_right]
        
        # 创建配置
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
            window_width=640,
            window_height=480,
        )
        
        # 创建 role_bindings
        self.role_bindings = {
            DeviceRole.LEFT_CAMERA: self.device_id_left,
            DeviceRole.RIGHT_CAMERA: self.device_id_right,
        }
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_start_does_not_create_render_thread(self, mock_packager_class, mock_renderer_class):
        """测试 start() 不创建渲染线程（需求 1.4）"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer.initialize.return_value = None
        mock_renderer_class.return_value = mock_renderer
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 记录启动前的线程
        threads_before = set(t.name for t in threading.enumerate())
        
        # 启动
        result = display_manager.start()
        
        # 验证启动成功
        self.assertTrue(result)
        
        # 记录启动后的线程
        threads_after = set(t.name for t in threading.enumerate())
        
        # 验证没有创建名为 "DisplayRenderer" 的线程
        new_threads = threads_after - threads_before
        self.assertNotIn("DisplayRenderer", new_threads)
        
        # 验证调用了 initialize() 而不是 start()
        mock_renderer.initialize.assert_called_once()
        mock_renderer.start.assert_not_called()
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_start_creates_packager_thread(self, mock_packager_class, mock_renderer_class):
        """测试 start() 创建打包线程（需求 4.1）"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer.initialize.return_value = None
        mock_renderer_class.return_value = mock_renderer
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 启动
        result = display_manager.start()
        
        # 验证启动成功
        self.assertTrue(result)
        
        # 验证调用了 packager.start()
        mock_packager.start.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_render_once_returns_false_on_normal_render(self, mock_packager_class, mock_renderer_class):
        """测试正常渲染时 render_once() 返回 False（需求 6.2）"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer.initialize.return_value = None
        mock_renderer.render_once.return_value = False  # 正常渲染返回 False
        mock_renderer_class.return_value = mock_renderer
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 启动
        display_manager.start()
        
        # 调用 render_once()
        result = display_manager.render_once()
        
        # 验证返回 False
        self.assertFalse(result)
        
        # 验证调用了 renderer.render_once()
        mock_renderer.render_once.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_render_once_returns_true_on_q_key(self, mock_packager_class, mock_renderer_class):
        """测试按 'q' 键时 render_once() 返回 True（需求 6.3）"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer.initialize.return_value = None
        mock_renderer.render_once.return_value = True  # 按 'q' 键返回 True
        mock_renderer_class.return_value = mock_renderer
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 启动
        display_manager.start()
        
        # 调用 render_once()
        result = display_manager.render_once()
        
        # 验证返回 True
        self.assertTrue(result)
        
        # 验证调用了 renderer.render_once()
        mock_renderer.render_once.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_render_once_handles_exception(self, mock_packager_class, mock_renderer_class):
        """测试 render_once() 异常处理（需求 6.4, 9.1, 9.2）"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer.initialize.return_value = None
        # 模拟渲染时抛出异常
        mock_renderer.render_once.side_effect = RuntimeError("渲染错误")
        mock_renderer_class.return_value = mock_renderer
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 启动
        display_manager.start()
        
        # 调用 render_once()，应该捕获异常
        with self.assertLogs(level='ERROR') as log_context:
            result = display_manager.render_once()
        
        # 验证返回 False（需求 9.2）
        self.assertFalse(result)
        
        # 验证记录了错误日志（需求 9.1）
        self.assertTrue(any('渲染过程中发生异常' in msg for msg in log_context.output))
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_render_once_returns_false_when_display_disabled(self, mock_packager_class, mock_renderer_class):
        """测试禁用显示时 render_once() 返回 False（需求 6.5）"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer_class.return_value = mock_renderer
        
        # 创建禁用显示的配置
        config_disabled = DisplayConfigDTO(
            enable_display=False,
            target_fps=30,
        )
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=config_disabled,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 启动
        display_manager.start()
        
        # 调用 render_once()
        result = display_manager.render_once()
        
        # 验证返回 False
        self.assertFalse(result)
        
        # 验证没有调用 renderer.render_once()
        mock_renderer.render_once.assert_not_called()
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_stop_calls_cleanup_not_stop(self, mock_packager_class, mock_renderer_class):
        """测试 stop() 调用 cleanup() 而不是 stop()（需求 1.5, 4.2）"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager.stop.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer.initialize.return_value = None
        mock_renderer.cleanup.return_value = None
        mock_renderer.get_stats.return_value = {}
        mock_renderer_class.return_value = mock_renderer
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
            role_bindings=self.role_bindings,
        )
        
        # 启动
        display_manager.start()
        
        # 停止
        result = display_manager.stop()
        
        # 验证停止成功
        self.assertTrue(result)
        
        # 验证调用了 cleanup() 而不是 stop()
        mock_renderer.cleanup.assert_called_once()
        mock_renderer.stop.assert_not_called()
        
        # 验证调用了 packager.stop()
        mock_packager.stop.assert_called_once()


class TestDisplayManagerIdempotency(unittest.TestCase):
    """测试 DisplayManager 的幂等性"""
    
    def setUp(self):
        """测试前准备"""
        self.devices_list = ["device_001", "device_002"]
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
        )
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_start_idempotency(self, mock_packager_class, mock_renderer_class):
        """测试 start() 的幂等性"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer.initialize.return_value = None
        mock_renderer_class.return_value = mock_renderer
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        
        # 第一次启动
        result1 = display_manager.start()
        self.assertTrue(result1)
        
        # 第二次启动应该返回 False（已在运行）
        result2 = display_manager.start()
        self.assertFalse(result2)
        
        # 验证 packager.start() 只被调用一次
        self.assertEqual(mock_packager.start.call_count, 1)
    
    @patch('oak_vision_system.modules.display_modules.display_manager.DisplayRenderer')
    @patch('oak_vision_system.modules.display_modules.display_manager.RenderPacketPackager')
    def test_stop_idempotency(self, mock_packager_class, mock_renderer_class):
        """测试 stop() 的幂等性"""
        # 配置 mock
        mock_packager = Mock()
        mock_packager.start.return_value = True
        mock_packager.stop.return_value = True
        mock_packager_class.return_value = mock_packager
        
        mock_renderer = Mock()
        mock_renderer.initialize.return_value = None
        mock_renderer.cleanup.return_value = None
        mock_renderer.get_stats.return_value = {}
        mock_renderer_class.return_value = mock_renderer
        
        # 创建 DisplayManager
        display_manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        
        # 启动
        display_manager.start()
        
        # 第一次停止
        result1 = display_manager.stop()
        self.assertTrue(result1)
        
        # 第二次停止应该返回 True（未在运行）
        result2 = display_manager.stop()
        self.assertTrue(result2)
        
        # 验证 packager.stop() 只被调用一次
        self.assertEqual(mock_packager.stop.call_count, 1)


if __name__ == '__main__':
    unittest.main()
