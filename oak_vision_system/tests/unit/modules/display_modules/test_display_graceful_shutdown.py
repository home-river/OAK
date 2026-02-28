"""
测试显示模块的优雅关闭功能

验证需求 14（优雅关闭）的所有验收标准：
- 14.1: DisplayManager.stop() 调用子模块的清理方法
- 14.4: DisplayRenderer.cleanup() 关闭所有 OpenCV 窗口
- 14.7: 记录关闭统计信息
"""

import time
import unittest
from unittest.mock import MagicMock, Mock, patch
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacketPackager,
)
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer


class TestDisplayRendererCleanup(unittest.TestCase):
    """测试 DisplayRenderer 清理功能"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=True,
            target_fps=30,
        )
        self.devices_list = ["device_001"]
        
        # 创建 mock packager
        self.mock_packager = Mock(spec=RenderPacketPackager)
        self.mock_packager.event_bus = Mock()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.destroyAllWindows')
    def test_cleanup_closes_all_windows(self, mock_destroy):
        """测试 cleanup() 关闭所有窗口（需求 14.4）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 调用 cleanup()
        renderer.cleanup()
        
        # 验证调用了 cv2.destroyAllWindows()
        mock_destroy.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.cv2.destroyAllWindows')
    def test_cleanup_outputs_statistics(self, mock_destroy):
        """测试 cleanup() 输出统计信息（需求 14.7）"""
        renderer = DisplayRenderer(
            config=self.config,
            packager=self.mock_packager,
            devices_list=self.devices_list,
        )
        
        # 初始化
        renderer.initialize()
        
        # 设置一些统计信息
        renderer._stats["frames_rendered"] = 100
        
        # 调用 cleanup()
        with self.assertLogs(level='INFO') as log_context:
            renderer.cleanup()
        
        # 验证输出了统计信息
        log_output = '\n'.join(log_context.output)
        self.assertIn('DisplayRenderer 已清理', log_output)
        self.assertIn('帧数: 100', log_output)


class TestDisplayManagerGracefulShutdown(unittest.TestCase):
    """测试 DisplayManager 优雅关闭"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=False,  # 禁用显示以避免创建窗口
            target_fps=30,
        )
        self.devices_list = ["device_001", "device_002"]
        self.managers = []  # 保存创建的管理器实例
    
    def tearDown(self):
        """测试后清理 - 确保所有资源都被释放"""
        for manager in self.managers:
            try:
                # 强制停止管理器
                if hasattr(manager, '_packager') and manager._packager is not None:
                    try:
                        manager._packager.stop(timeout=1.0)
                    except:
                        pass
            except:
                pass
        self.managers.clear()
        time.sleep(0.1)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer.cleanup')
    @patch('oak_vision_system.modules.display_modules.render_packet_packager.RenderPacketPackager.stop')
    def test_stop_calls_renderer_cleanup(self, mock_packager_stop, mock_renderer_cleanup):
        """测试 stop() 调用 renderer.cleanup()（需求 14.1）"""
        # Mock packager.stop 返回 True
        mock_packager_stop.return_value = True
        
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 停止管理器
        manager.stop(timeout=2.0)
        
        # 验证调用了 renderer.cleanup()
        mock_renderer_cleanup.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer.cleanup')
    @patch('oak_vision_system.modules.display_modules.render_packet_packager.RenderPacketPackager.stop')
    def test_stop_calls_packager_stop(self, mock_packager_stop, mock_renderer_cleanup):
        """测试 stop() 调用 packager.stop()（需求 14.1）"""
        # Mock packager.stop 返回 True
        mock_packager_stop.return_value = True
        
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 停止管理器
        manager.stop(timeout=2.0)
        
        # 验证调用了 packager.stop()
        mock_packager_stop.assert_called_once()
    
    @patch('oak_vision_system.modules.display_modules.render_packet_packager.RenderPacketPackager.stop')
    def test_stop_handles_renderer_cleanup_exception(self, mock_packager_stop):
        """测试 stop() 处理 cleanup 异常（需求 14.1）"""
        # Mock packager.stop 返回 True（确保线程能正常停止）
        mock_packager_stop.return_value = True
        
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # Mock renderer.cleanup 抛出异常
        with patch.object(manager._renderer, 'cleanup', side_effect=Exception("Cleanup failed")):
            # 停止管理器（应该捕获异常）
            with self.assertLogs(level='ERROR') as log_context:
                result = manager.stop(timeout=2.0)
            
            # 验证记录了错误日志（使用实际的日志文案）
            log_output = '\n'.join(log_context.output)
            self.assertIn('清理 DisplayRenderer 时发生异常', log_output)
            
            # 验证返回 False（表示停止失败）
            self.assertFalse(result)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer.cleanup')
    def test_stop_handles_packager_stop_exception(self, mock_renderer_cleanup):
        """测试 stop() 处理 packager.stop 异常（需求 14.1）"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # Mock packager.stop 返回 False（表示停止失败）
        with patch.object(manager._packager, 'stop', return_value=False):
            # 停止管理器
            result = manager.stop(timeout=2.0)
            
            # 验证返回 False（表示停止失败）
            self.assertFalse(result)
    
    def test_stop_outputs_statistics(self):
        """测试 stop() 输出统计信息（需求 14.7）"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 停止管理器
        with self.assertLogs(level='INFO') as log_context:
            manager.stop(timeout=2.0)
        
        # 验证输出了统计信息
        log_output = '\n'.join(log_context.output)
        self.assertIn('DisplayManager 已停止', log_output)
    
    @patch('oak_vision_system.modules.display_modules.display_renderer.DisplayRenderer.cleanup')
    @patch('oak_vision_system.modules.display_modules.render_packet_packager.RenderPacketPackager.stop')
    def test_stop_returns_true_on_success(self, mock_packager_stop, mock_renderer_cleanup):
        """测试 stop() 成功时返回 True（需求 14.1）"""
        # Mock packager.stop 返回 True
        mock_packager_stop.return_value = True
        
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 停止管理器
        result = manager.stop(timeout=2.0)
        
        # 验证返回 True
        self.assertTrue(result)
    
    @patch('oak_vision_system.modules.display_modules.render_packet_packager.RenderPacketPackager.stop')
    def test_stop_returns_false_on_failure(self, mock_packager_stop):
        """测试 stop() 失败时返回 False（需求 14.1）"""
        # Mock packager.stop 返回 True（确保线程能正常停止）
        mock_packager_stop.return_value = True
        
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # Mock renderer.cleanup 抛出异常
        with patch.object(manager._renderer, 'cleanup', side_effect=Exception("Cleanup failed")):
            # 停止管理器
            with self.assertLogs(level='ERROR'):
                result = manager.stop(timeout=2.0)
            
            # 验证返回 False
            self.assertFalse(result)


class TestRenderPacketPackagerGracefulShutdown(unittest.TestCase):
    """测试 RenderPacketPackager 优雅关闭"""
    
    def setUp(self):
        """测试前准备"""
        self.devices_list = ["device_001", "device_002"]
        self.packagers = []
    
    def tearDown(self):
        """测试后清理"""
        for packager in self.packagers:
            try:
                packager.stop(timeout=1.0)
            except:
                pass
        self.packagers.clear()
        time.sleep(0.1)
    
    def test_packager_stop_with_timeout(self):
        """测试 RenderPacketPackager 的超时机制（需求 14.6）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)
        
        # 启动打包器
        packager.start()
        time.sleep(0.1)
        
        # 停止打包器
        packager.stop(timeout=2.0)
        
        # 验证线程已停止
        self.assertFalse(packager._running.is_set())
        self.assertIsNone(packager._worker_thread)
    
    def test_packager_clears_resources(self):
        """测试 RenderPacketPackager 清理资源（需求 14.3, 14.4, 14.5）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)
        
        # 启动打包器
        packager.start()
        
        # 添加一些数据到队列
        video_frame = VideoFrameDTO(
            device_id="device_001",
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        packager._handle_video_frame(video_frame)
        
        time.sleep(0.1)
        
        # 停止打包器
        packager.stop(timeout=2.0)
        
        # 验证队列已清空
        for queue in packager.packet_queue.values():
            self.assertTrue(queue.empty())
        
        # 验证缓冲区已清空
        self.assertEqual(len(packager._buffer), 0)
        
        # 验证缓存已清空
        for device_id, packet in packager._latest_packets.items():
            self.assertIsNone(packet)
        for device_id, timestamp in packager._packet_timestamps.items():
            self.assertEqual(timestamp, 0.0)
    
    def test_timeout_warning_logged(self):
        """测试超时时记录警告日志（需求 14.6）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)
        
        # 启动打包器
        packager.start()
        
        # 模拟线程无法停止的情况
        with patch.object(packager._worker_thread, 'is_alive', return_value=True):
            with self.assertLogs(level='WARNING') as log_context:
                packager.stop(timeout=0.1)
                
                # 验证记录了警告日志
                log_output = '\n'.join(log_context.output)
                self.assertIn('停止超时', log_output)


if __name__ == '__main__':
    unittest.main()
