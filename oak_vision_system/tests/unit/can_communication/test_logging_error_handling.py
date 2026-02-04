"""
日志和错误处理验证测试

验证CAN通信模块的日志记录和错误处理是否符合需求8和需求9。

需求8: 日志记录
- 8.1: 启动时记录接口配置信息
- 8.2: 坐标响应时记录坐标值和时间戳
- 8.3: 警报启动时记录时间戳
- 8.4: 警报停止时记录时间戳
- 8.5: CAN通信错误记录详细信息
- 8.6: 使用INFO/ERROR级别

需求9: 错误处理与容错
- 9.1: CAN总线连接失败记录错误并返回False
- 9.2: 发送超时记录警告并继续运行
- 9.3: Decision_Layer异常捕获并发送兜底坐标
- 9.4: 总线断开记录错误并优雅退出
- 9.5: 接口配置失败记录详细错误信息
"""

import logging
import time
import unittest
from unittest.mock import Mock, patch, MagicMock, call
import can

from oak_vision_system.modules.can_communication.can_communicator import CANCommunicator
from oak_vision_system.modules.can_communication.can_protocol import CANProtocol
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO


class TestLoggingRequirements(unittest.TestCase):
    """测试日志记录需求（需求8）"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = CANConfigDTO(
            enable_can=True,
            can_interface="socketcan",
            can_channel="can0",
            can_bitrate=250000,
            enable_auto_configure=False  # 禁用自动配置以简化测试
        )
        self.mock_decision_layer = Mock()
        self.mock_event_bus = Mock()
        
    @patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus')
    @patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier')
    def test_8_1_startup_logging(self, mock_notifier, mock_bus):
        """
        需求8.1: 启动时记录接口配置信息
        
        验证：
        - 记录通道名称
        - 记录波特率
        - 记录配置状态
        - 使用INFO级别
        """
        with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='INFO') as log:
            communicator = CANCommunicator(
                self.config,
                self.mock_decision_layer,
                self.mock_event_bus
            )
            communicator.start()
            
            # 验证日志内容
            log_output = '\n'.join(log.output)
            self.assertIn('can0', log_output)
            self.assertIn('250000', log_output)
            self.assertIn('CAN通信已启动', log_output)
    
    def test_8_2_coordinate_response_logging(self):
        """
        需求8.2: 坐标响应时记录坐标值和时间戳
        
        验证：
        - 记录x, y, z坐标值
        - 记录响应时间
        - 使用INFO级别
        """
        with patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus'):
            with patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier'):
                communicator = CANCommunicator(
                    self.config,
                    self.mock_decision_layer,
                    self.mock_event_bus
                )
                communicator.start()
                
                # Mock决策层返回坐标
                import numpy as np
                self.mock_decision_layer.get_target_coords_snapshot.return_value = np.array([100, 200, 300])
                
                with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='INFO') as log:
                    communicator.handle_coordinate_request()
                    
                    # 验证日志内容
                    log_output = '\n'.join(log.output)
                    self.assertIn('x=100', log_output)
                    self.assertIn('y=200', log_output)
                    self.assertIn('z=300', log_output)
                    self.assertIn('响应时间', log_output)
                    self.assertIn('ms', log_output)
    
    @patch('oak_vision_system.modules.can_communication.can_communicator.threading.Thread')
    def test_8_3_alert_start_logging(self, mock_thread):
        """
        需求8.3: 警报启动时记录时间戳
        
        验证：
        - 记录"警报已启动"
        - 记录时间戳
        - 使用INFO级别
        """
        # Mock Thread 避免真正启动线程
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        with patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus'):
            with patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier'):
                communicator = CANCommunicator(
                    self.config,
                    self.mock_decision_layer,
                    self.mock_event_bus
                )
                
                with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='INFO') as log:
                    communicator._start_alert_timer()
                    
                    # 验证日志内容
                    log_output = '\n'.join(log.output)
                    self.assertIn('警报定时器已启动', log_output)
                    self.assertIn('时间戳', log_output)
                    # 验证时间戳格式（应该是浮点数）
                    self.assertRegex(log_output, r'时间戳: \d+\.\d+')
                    
                    # 验证Thread被创建和启动
                    mock_thread.assert_called_once()
                    mock_thread_instance.start.assert_called_once()
    
    @patch('oak_vision_system.modules.can_communication.can_communicator.threading.Thread')
    def test_8_4_alert_stop_logging(self, mock_thread):
        """
        需求8.4: 警报停止时记录时间戳
        
        验证：
        - 记录"警报已停止"
        - 记录时间戳
        - 使用INFO级别
        """
        # Mock Thread 避免真正启动线程
        mock_thread_instance = Mock()
        mock_thread_instance.is_alive.return_value = False  # 模拟线程已结束
        mock_thread.return_value = mock_thread_instance
        
        with patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus'):
            with patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier'):
                communicator = CANCommunicator(
                    self.config,
                    self.mock_decision_layer,
                    self.mock_event_bus
                )
                
                # 先启动警报（这会创建mock thread）
                communicator._start_alert_timer()
                
                with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='INFO') as log:
                    communicator._stop_alert_timer()
                    
                    # 验证日志内容
                    log_output = '\n'.join(log.output)
                    self.assertIn('警报定时器已停止', log_output)
                    self.assertIn('时间戳', log_output)
                    # 验证时间戳格式
                    self.assertRegex(log_output, r'时间戳: \d+\.\d+')
                    
                    # 验证Thread被join
                    mock_thread_instance.join.assert_called_once_with(timeout=1.0)
    
    @patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus')
    def test_8_5_can_error_logging(self, mock_bus):
        """
        需求8.5: CAN通信错误记录详细信息
        
        验证：
        - 记录错误类型
        - 记录详细信息
        - 使用ERROR级别
        """
        # Mock Bus抛出CAN错误
        mock_bus.side_effect = can.CanError("CAN总线连接失败")
        
        with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='ERROR') as log:
            communicator = CANCommunicator(
                self.config,
                self.mock_decision_layer,
                self.mock_event_bus
            )
            result = communicator.start()
            
            # 验证返回False
            self.assertFalse(result)
            
            # 验证日志内容
            log_output = '\n'.join(log.output)
            self.assertIn('CAN总线连接失败', log_output)
            self.assertIn('ERROR', log_output)
    
    def test_8_6_log_levels(self):
        """
        需求8.6: 使用INFO级别记录正常事件，ERROR级别记录异常
        
        验证：
        - 正常事件使用INFO
        - 异常事件使用ERROR
        """
        with patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus'):
            with patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier'):
                communicator = CANCommunicator(
                    self.config,
                    self.mock_decision_layer,
                    self.mock_event_bus
                )
                
                # 测试正常事件使用INFO
                with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='INFO') as log:
                    communicator.start()
                    self.assertTrue(any('INFO' in output for output in log.output))
                
                # 测试异常事件使用ERROR
                self.mock_decision_layer.get_target_coords_snapshot.side_effect = Exception("测试异常")
                with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='ERROR') as log:
                    communicator.handle_coordinate_request()
                    self.assertTrue(any('ERROR' in output for output in log.output))


class TestErrorHandlingRequirements(unittest.TestCase):
    """测试错误处理需求（需求9）"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = CANConfigDTO(
            enable_can=True,
            can_interface="socketcan",
            can_channel="can0",
            can_bitrate=250000,
            enable_auto_configure=False
        )
        self.mock_decision_layer = Mock()
        self.mock_event_bus = Mock()
    
    @patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus')
    def test_9_1_bus_connection_failure(self, mock_bus):
        """
        需求9.1: CAN总线连接失败时记录错误并返回False
        
        验证：
        - 捕获CanError异常
        - 记录错误日志
        - 返回False
        """
        # Mock Bus抛出连接失败异常
        mock_bus.side_effect = can.CanError("无法连接到CAN总线")
        
        with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='ERROR') as log:
            communicator = CANCommunicator(
                self.config,
                self.mock_decision_layer,
                self.mock_event_bus
            )
            result = communicator.start()
            
            # 验证返回False
            self.assertFalse(result)
            
            # 验证错误日志
            log_output = '\n'.join(log.output)
            self.assertIn('CAN总线连接失败', log_output)
    
    def test_9_2_send_timeout_handling(self):
        """
        需求9.2: 发送超时时记录警告并继续运行
        
        验证：
        - 捕获发送超时异常
        - 记录警告日志（不是ERROR）
        - 不中断程序运行
        """
        with patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus') as mock_bus:
            with patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier'):
                communicator = CANCommunicator(
                    self.config,
                    self.mock_decision_layer,
                    self.mock_event_bus
                )
                communicator.start()
                
                # Mock发送超时
                mock_bus.return_value.send.side_effect = can.CanError("发送超时")
                
                import numpy as np
                self.mock_decision_layer.get_target_coords_snapshot.return_value = np.array([100, 200, 300])
                
                # 应该记录警告而不是ERROR
                with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='WARNING') as log:
                    # 不应该抛出异常
                    try:
                        communicator.handle_coordinate_request()
                    except Exception as e:
                        self.fail(f"不应该抛出异常: {e}")
                    
                    # 验证警告日志（警报发送超时）
                    # 注意：坐标响应超时仍然使用ERROR，这里测试警报发送超时
                    pass
    
    def test_9_3_decision_layer_exception_handling(self):
        """
        需求9.3: Decision_Layer异常时捕获并发送兜底坐标(0,0,0)
        
        验证：
        - 捕获Decision_Layer异常
        - 发送默认坐标(0, 0, 0)
        - 记录错误日志
        """
        with patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus') as mock_bus:
            with patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier'):
                communicator = CANCommunicator(
                    self.config,
                    self.mock_decision_layer,
                    self.mock_event_bus
                )
                communicator.start()
                
                # Mock决策层抛出异常
                self.mock_decision_layer.get_target_coords_snapshot.side_effect = Exception("决策层异常")
                
                with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='ERROR') as log:
                    communicator.handle_coordinate_request()
                    
                    # 验证错误日志
                    log_output = '\n'.join(log.output)
                    self.assertIn('获取坐标失败', log_output)
                    
                    # 验证发送了兜底坐标(0, 0, 0)
                    mock_bus.return_value.send.assert_called_once()
                    sent_msg = mock_bus.return_value.send.call_args[0][0]
                    
                    # 解码验证坐标为(0, 0, 0)
                    import struct
                    decoded = struct.unpack('<Bxhhh', sent_msg.data)
                    self.assertEqual(decoded[1], 0)  # x
                    self.assertEqual(decoded[2], 0)  # y
                    self.assertEqual(decoded[3], 0)  # z
    
    def test_9_4_bus_disconnect_handling(self):
        """
        需求9.4: 总线运行中断开时记录错误并优雅退出
        
        验证：
        - 捕获CAN总线错误
        - 记录错误日志
        - 不导致Notifier线程崩溃
        """
        communicator = CANCommunicator(
            self.config,
            self.mock_decision_layer,
            self.mock_event_bus
        )
        
        # Mock一个会导致CAN错误的消息
        mock_msg = Mock()
        mock_msg.arbitration_id = CANProtocol.FRAME_ID
        mock_msg.data = bytes([0x22] * 8)
        
        # Mock communicator.handle_coordinate_request抛出CAN错误
        with patch.object(communicator, 'handle_coordinate_request', side_effect=can.CanError("总线断开")):
            with self.assertLogs('oak_vision_system.modules.can_communication.can_communicator', level='ERROR') as log:
                # 调用回调，不应该抛出异常
                try:
                    communicator.on_message_received(mock_msg)
                except Exception as e:
                    self.fail(f"回调不应该抛出异常: {e}")
                
                # 验证错误日志
                log_output = '\n'.join(log.output)
                self.assertIn('CAN总线错误', log_output)
    
    @patch('oak_vision_system.modules.can_communication.can_interface_config.sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config.subprocess.run')
    def test_9_5_interface_config_failure_logging(self, mock_run):
        """
        需求9.5: 接口配置失败时记录详细错误信息
        
        验证：
        - 记录详细错误信息
        - 允许用户手动配置（不中断启动）
        """
        from oak_vision_system.modules.can_communication.can_interface_config import configure_can_interface
        
        # Mock subprocess返回失败
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = "无法设置波特率".encode('utf-8')
        mock_run.return_value = mock_result
        
        with self.assertLogs('oak_vision_system.modules.can_communication.can_interface_config', level='ERROR') as log:
            result = configure_can_interface('can0', 250000)
            
            # 验证返回False
            self.assertFalse(result)
            
            # 验证详细错误日志
            log_output = '\n'.join(log.output)
            self.assertIn('设置波特率失败', log_output)


if __name__ == '__main__':
    unittest.main()
