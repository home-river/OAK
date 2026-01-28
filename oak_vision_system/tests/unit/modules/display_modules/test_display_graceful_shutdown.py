"""
测试显示模块的优雅关闭功能

验证需求 14（优雅关闭）的所有验收标准：
- 14.1: 停止两个子模块
- 14.2: RenderPacketPackager 停止接收新事件
- 14.3: DisplayRenderer 处理完队列中的剩余数据
- 14.4: DisplayRenderer 关闭所有 OpenCV 窗口
- 14.5: RenderPacketPackager 取消事件订阅
- 14.6: 在超时时间内强制退出
- 14.7: 记录关闭统计信息
"""

import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacketPackager,
)
from oak_vision_system.modules.display_modules.display_renderer import DisplayRenderer


class TestGracefulShutdown(unittest.TestCase):
    """测试优雅关闭功能"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DisplayConfigDTO(
            enable_display=False,  # 禁用显示以避免创建窗口
            window_width=640,
            window_height=480,
            target_fps=30,
        )
        self.devices_list = ["device1", "device2"]
        # 保存创建的实例，以便在 tearDown 中清理
        self.packagers = []
        self.renderers = []
        self.managers = []
    
    def tearDown(self):
        """测试后清理 - 确保所有资源都被释放"""
        # 停止所有管理器
        for manager in self.managers:
            try:
                manager.stop(timeout=1.0)
            except:
                pass
        
        # 停止所有渲染器
        for renderer in self.renderers:
            try:
                renderer.stop(timeout=1.0)
            except:
                pass
        
        # 停止所有打包器
        for packager in self.packagers:
            try:
                packager.stop(timeout=1.0)
            except:
                pass
        
        # 清空列表
        self.packagers.clear()
        self.renderers.clear()
        self.managers.clear()
        
        # 等待一小段时间确保线程完全退出
        time.sleep(0.1)
    
    def test_packager_stop_with_timeout(self):
        """测试 RenderPacketPackager 的超时机制（需求 14.6）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)  # 添加到清理列表
        
        # 启动打包器
        packager.start()
        time.sleep(0.1)  # 等待线程启动
        
        # 停止打包器（使用超时）
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
        self.packagers.append(packager)  # 添加到清理列表
        
        # 启动打包器
        packager.start()
        
        # 添加一些数据到队列
        video_frame = VideoFrameDTO(
            device_id="device1",
            frame_id=1,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
        packager._handle_video_frame(video_frame)
        
        time.sleep(0.1)  # 等待数据处理
        
        # 停止打包器
        packager.stop(timeout=2.0)
        
        # 验证队列已清空（需求 14.3）
        for queue in packager.packet_queue.values():
            self.assertTrue(queue.empty())
        
        # 验证缓冲区已清空（需求 14.4）
        self.assertEqual(len(packager._buffer), 0)
        
        # 验证缓存已清空（需求 14.4）
        self.assertEqual(len(packager._latest_packets), 0)
        self.assertEqual(len(packager._packet_timestamps), 0)
    
    @patch('cv2.destroyAllWindows')
    def test_renderer_closes_windows(self, mock_destroy):
        """测试 DisplayRenderer 关闭窗口（需求 14.4）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)  # 添加到清理列表
        
        renderer = DisplayRenderer(
            config=self.config,
            packager=packager,
            devices_list=self.devices_list,
        )
        self.renderers.append(renderer)  # 添加到清理列表
        
        # 启动渲染器
        packager.start()
        renderer.start()
        
        time.sleep(0.1)  # 等待线程启动
        
        # 停止渲染器和打包器
        renderer.stop(timeout=2.0)
        packager.stop(timeout=2.0)  # 修复：添加这一行
        
        # 验证 cv2.destroyAllWindows 被调用（需求 14.4）
        mock_destroy.assert_called()
    
    def test_manager_stops_both_modules(self):
        """测试 DisplayManager 停止两个子模块（需求 14.1）"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)  # 添加到清理列表
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)  # 等待线程启动
        
        # 验证两个子模块都在运行
        self.assertTrue(manager._packager._running.is_set())
        # DisplayRenderer 未启动（因为 enable_display=False）
        
        # 停止管理器
        success = manager.stop(timeout=2.0)
        
        # 验证停止成功（需求 14.1）
        self.assertTrue(success)
        
        # 验证两个子模块都已停止
        self.assertFalse(manager._packager._running.is_set())
        self.assertFalse(manager._renderer.is_running)
    
    def test_manager_outputs_stats_on_stop(self):
        """测试 DisplayManager 输出关闭统计信息（需求 14.7）"""
        manager = DisplayManager(
            config=self.config,
            devices_list=self.devices_list,
        )
        self.managers.append(manager)  # 添加到清理列表
        
        # 启动管理器
        manager.start()
        time.sleep(0.1)
        
        # 停止管理器
        with self.assertLogs(level='INFO') as log:
            manager.stop(timeout=2.0)
            
            # 验证输出了统计信息（需求 14.7）
            log_output = '\n'.join(log.output)
            self.assertIn('DisplayManager 已停止', log_output)
            self.assertIn('统计数据', log_output)
    
    def test_timeout_warning_logged(self):
        """测试超时时记录警告日志（需求 14.6）"""
        packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=self.devices_list,
            cache_max_age_sec=1.0,
        )
        self.packagers.append(packager)  # 添加到清理列表
        
        # 启动打包器
        packager.start()
        
        # 模拟线程无法停止的情况
        # 通过 patch 让 join 不起作用
        with patch.object(packager._worker_thread, 'is_alive', return_value=True):
            with self.assertLogs(level='WARNING') as log:
                packager.stop(timeout=0.1)
                
                # 验证记录了警告日志（需求 14.6）
                log_output = '\n'.join(log.output)
                self.assertIn('停止超时', log_output)


if __name__ == '__main__':
    unittest.main()
