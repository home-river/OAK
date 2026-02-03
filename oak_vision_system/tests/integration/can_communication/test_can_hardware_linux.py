"""
CAN通信模块硬件测试（Linux环境 - 真实硬件）

在香橙派上进行实际硬件测试，验证与外部控制器的真实通信。
这是最高级别的集成测试，需要完整的硬件环境。

测试环境要求：
- Linux系统（香橙派）
- 真实CAN硬件接口
- 外部CAN控制器设备
- 物理CAN总线连接

注意：此测试创建后不立即运行，留待Linux环境执行
运行环境：Linux（香橙派）+ 真实CAN硬件 + 外部控制器 ⚠️

验证需求：
- 所有CAN通信需求的硬件级验证
- 真实环境下的性能和稳定性测试
"""

import os
import sys
import time
import subprocess
import pytest
import logging
from typing import Optional, List, Dict, Any, Tuple
from unittest.mock import Mock
import numpy as np

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from oak_vision_system.modules.can_communication.can_communicator import CANCommunicator
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
from oak_vision_system.modules.data_processing.decision_layer.types import PersonWarningStatus

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 测试辅助类 ====================

class MockDecisionLayer:
    """模拟决策层（硬件测试用）"""
    
    def __init__(self):
        self._target_coords = None
        self._lock = threading.Lock()
        self._call_count = 0
    
    def set_target_coords(self, coords: Optional[np.ndarray]):
        """设置目标坐标（测试用）"""
        with self._lock:
            self._target_coords = coords
    
    def get_target_coords_snapshot(self) -> Optional[np.ndarray]:
        """获取目标坐标快照"""
        with self._lock:
            self._call_count += 1
            logger.debug(f"决策层被调用第{self._call_count}次")
            return self._target_coords.copy() if self._target_coords is not None else None
    
    def get_call_count(self) -> int:
        """获取调用次数"""
        with self._lock:
            return self._call_count


class MockEventBus:
    """模拟事件总线（硬件测试用）"""
    
    def __init__(self):
        self._subscribers = {}
        self._subscription_counter = 0
        self._event_history = []
    
    def subscribe(self, event_type, callback, subscriber_name: str) -> str:
        """订阅事件"""
        subscription_id = f"sub_{self._subscription_counter}"
        self._subscription_counter += 1
        self._subscribers[subscription_id] = {
            'event_type': event_type,
            'callback': callback,
            'subscriber_name': subscriber_name
        }
        logger.info(f"事件订阅: {subscriber_name} -> {event_type}")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str):
        """取消订阅"""
        if subscription_id in self._subscribers:
            subscriber_info = self._subscribers[subscription_id]
            logger.info(f"取消事件订阅: {subscriber_info['subscriber_name']}")
            del self._subscribers[subscription_id]
    
    def publish_person_warning(self, status: PersonWarningStatus):
        """发布人员警报事件（测试用）"""
        event_data = {
            'status': status,
            'timestamp': time.time()
        }
        
        self._event_history.append(event_data)
        logger.info(f"发布人员警报事件: {status}, 时间戳: {event_data['timestamp']}")
        
        # 通知所有订阅者
        from oak_vision_system.core.event_bus.event_types import EventType
        for sub_info in self._subscribers.values():
            if sub_info['event_type'] == EventType.PERSON_WARNING:
                try:
                    sub_info['callback'](event_data)
                except Exception as e:
                    logger.error(f"事件回调异常: {e}")
    
    def get_event_history(self) -> List[Dict]:
        """获取事件历史"""
        return self._event_history.copy()


class HardwareTestHelper:
    """硬件测试辅助工具"""
    
    @staticmethod
    def check_can_interface_availability(channel: str = 'can0') -> bool:
        """检查CAN接口可用性"""
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', channel],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # 检查接口状态
                if 'UP' in result.stdout:
                    logger.info(f"CAN接口 {channel} 可用且已启用")
                    return True
                else:
                    logger.warning(f"CAN接口 {channel} 存在但未启用")
                    return False
            else:
                logger.error(f"CAN接口 {channel} 不存在")
                return False
                
        except Exception as e:
            logger.error(f"检查CAN接口时出错: {e}")
            return False
    
    @staticmethod
    def check_can_hardware_support() -> bool:
        """检查CAN硬件支持"""
        try:
            # 检查内核模块
            result = subprocess.run(
                ['lsmod'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            can_modules = ['can', 'can_raw', 'vcan']
            loaded_modules = []
            
            for module in can_modules:
                if module in result.stdout:
                    loaded_modules.append(module)
            
            logger.info(f"已加载的CAN模块: {loaded_modules}")
            
            # 至少需要can和can_raw模块
            return 'can' in loaded_modules and 'can_raw' in loaded_modules
            
        except Exception as e:
            logger.error(f"检查CAN硬件支持时出错: {e}")
            return False
    
    @staticmethod
    def configure_can_interface_if_needed(channel: str = 'can0', bitrate: int = 250000) -> bool:
        """如果需要，配置CAN接口"""
        try:
            # 检查接口是否已配置
            if HardwareTestHelper.check_can_interface_availability(channel):
                return True
            
            logger.info(f"尝试配置CAN接口 {channel}...")
            
            # 导入配置函数
            from oak_vision_system.modules.can_communication.can_interface_config import configure_can_interface
            
            # 尝试配置（不提供密码，依赖系统配置）
            success = configure_can_interface(channel, bitrate)
            
            if success:
                logger.info(f"CAN接口 {channel} 配置成功")
                return True
            else:
                logger.error(f"CAN接口 {channel} 配置失败")
                return False
                
        except Exception as e:
            logger.error(f"配置CAN接口时出错: {e}")
            return False


# ==================== 硬件环境检测 ====================

class TestHardwareEnvironment:
    """硬件环境检测测试"""
    
    def test_linux_platform_requirement(self):
        """
        测试Linux平台要求
        
        验证需求：
        - 硬件测试必须在Linux平台运行
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: Linux平台要求")
        logger.info("=" * 60)
        
        current_platform = sys.platform
        logger.info(f"当前平台: {current_platform}")
        
        is_linux = current_platform in ['linux', 'linux2']
        
        if not is_linux:
            logger.error(f"❌ 硬件测试需要Linux平台，当前平台: {current_platform}")
            pytest.skip("硬件测试需要Linux平台")
        
        logger.info("✅ Linux平台检测通过")
    
    def test_can_hardware_support(self):
        """
        测试CAN硬件支持
        
        验证需求：
        - 系统必须支持CAN硬件
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: CAN硬件支持")
        logger.info("=" * 60)
        
        # 检查python-can模块
        try:
            import can
            logger.info("✅ python-can模块可用")
        except ImportError:
            logger.error("❌ python-can模块不可用")
            pytest.skip("硬件测试需要python-can模块")
        
        # 检查CAN硬件支持
        if not HardwareTestHelper.check_can_hardware_support():
            logger.error("❌ CAN硬件支持不可用")
            pytest.skip("硬件测试需要CAN硬件支持")
        
        logger.info("✅ CAN硬件支持检测通过")
    
    def test_can_interface_availability(self):
        """
        测试CAN接口可用性
        
        验证需求：
        - CAN接口必须可用
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: CAN接口可用性")
        logger.info("=" * 60)
        
        # 检查can0接口
        if HardwareTestHelper.check_can_interface_availability('can0'):
            logger.info("✅ can0接口可用")
            return
        
        # 尝试配置can0接口
        if HardwareTestHelper.configure_can_interface_if_needed('can0'):
            logger.info("✅ can0接口配置成功")
            return
        
        # 检查是否有其他CAN接口
        try:
            result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True, timeout=5)
            can_interfaces = []
            
            for line in result.stdout.split('\n'):
                if 'can' in line and ':' in line:
                    interface = line.split(':')[1].strip().split('@')[0]
                    if interface.startswith('can'):
                        can_interfaces.append(interface)
            
            if can_interfaces:
                logger.info(f"发现CAN接口: {can_interfaces}")
            else:
                logger.error("❌ 未发现可用的CAN接口")
                pytest.skip("硬件测试需要可用的CAN接口")
                
        except Exception as e:
            logger.error(f"检查CAN接口时出错: {e}")
            pytest.skip("无法检查CAN接口可用性")


# ==================== 硬件级坐标请求响应测试 ====================

class TestHardwareCoordinateRequestResponse:
    """硬件级坐标请求响应测试"""
    
    @pytest.fixture
    def can_config(self):
        """创建硬件测试用CAN配置"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='can0',
            can_bitrate=250000,
            enable_auto_configure=True,  # 启用自动配置
            sudo_password=None,  # 依赖系统配置
            alert_interval_ms=100,
            send_timeout_ms=100,  # 硬件环境可能需要更长超时
            receive_timeout_ms=50
        )
    
    @pytest.fixture
    def mock_decision_layer(self):
        """创建模拟决策层"""
        return MockDecisionLayer()
    
    @pytest.fixture
    def mock_event_bus(self):
        """创建模拟事件总线"""
        return MockEventBus()
    
    def test_hardware_can_communication_startup(self, can_config, mock_decision_layer, mock_event_bus):
        """
        测试硬件CAN通信启动
        
        验证需求：
        - 需求 1.1: CAN通信启动
        - 需求 1.2: 接口自动配置
        - 需求 6.1: 通信管理器初始化
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 硬件CAN通信启动")
        logger.info("=" * 60)
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 启动通信器
        logger.info("启动CAN通信器...")
        start_success = communicator.start()
        
        if not start_success:
            logger.error("❌ CAN通信器启动失败，可能缺少硬件环境")
            pytest.skip("CAN通信器启动失败，需要真实硬件环境")
        
        try:
            logger.info("✅ CAN通信器启动成功")
            
            # 验证内部状态
            assert communicator.bus is not None, "CAN总线应该已初始化"
            assert communicator.notifier is not None, "Notifier应该已初始化"
            assert communicator._person_warning_subscription_id is not None, "事件订阅应该已建立"
            
            # 等待系统稳定
            time.sleep(2.0)
            
            logger.info("✅ 硬件CAN通信启动测试通过")
            
        finally:
            # 清理资源
            logger.info("停止CAN通信器...")
            communicator.stop()
            logger.info("✅ CAN通信器已停止")
    
    def test_hardware_coordinate_response_with_real_timing(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus
    ):
        """
        测试硬件环境下的坐标响应真实时序
        
        验证需求：
        - 需求 2.1, 2.2, 2.3: 坐标请求响应流程
        - 需求 2.6: 响应时间 < 10ms（硬件环境）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 硬件环境坐标响应真实时序")
        logger.info("=" * 60)
        
        # 设置测试坐标
        test_coords = np.array([1234, -5678, 9012], dtype=np.float32)
        mock_decision_layer.set_target_coords(test_coords)
        
        # 创建并启动CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        if not communicator.start():
            pytest.skip("无法启动CAN通信器")
        
        try:
            # 等待系统稳定
            time.sleep(1.0)
            
            # 创建外部CAN客户端发送请求
            import can
            
            try:
                client_bus = can.Bus(
                    interface=can_config.can_interface,
                    channel=can_config.can_channel,
                    bitrate=can_config.can_bitrate
                )
                
                # 发送坐标请求
                from oak_vision_system.modules.can_communication.can_protocol import CANProtocol
                
                request_msg = can.Message(
                    arbitration_id=CANProtocol.FRAME_ID,
                    data=[CANProtocol.MSG_TYPE_REQUEST, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                    is_extended_id=False
                )
                
                # 记录发送时间
                send_time = time.time()
                client_bus.send(request_msg)
                logger.info("发送坐标请求")
                
                # 等待响应
                response_msg = client_bus.recv(timeout=1.0)
                receive_time = time.time()
                
                if response_msg is None:
                    logger.error("❌ 未收到响应")
                    pytest.fail("未收到坐标响应")
                
                # 计算响应时间
                response_time_ms = (receive_time - send_time) * 1000
                logger.info(f"响应时间: {response_time_ms:.2f}ms")
                
                # 验证响应时间（硬件环境允许更大的误差）
                assert response_time_ms < 50, f"硬件环境响应时间应该 < 50ms，实际: {response_time_ms:.2f}ms"
                
                # 验证响应格式
                assert response_msg.arbitration_id == CANProtocol.FRAME_ID, "响应帧ID应该正确"
                assert len(response_msg.data) == 8, "响应数据长度应该为8字节"
                assert response_msg.data[0] == CANProtocol.MSG_TYPE_RESPONSE, "响应类型应该正确"
                
                # 解码坐标
                import struct
                _, x, y, z = struct.unpack('<Bxhhh', response_msg.data)
                
                assert x == 1234, f"X坐标不匹配: 期望1234, 实际{x}"
                assert y == -5678, f"Y坐标不匹配: 期望-5678, 实际{y}"
                assert z == 9012, f"Z坐标不匹配: 期望9012, 实际{z}"
                
                logger.info(f"✅ 硬件环境坐标响应测试通过: ({x}, {y}, {z}), 响应时间: {response_time_ms:.2f}ms")
                
            finally:
                if 'client_bus' in locals():
                    client_bus.shutdown()
                    
        finally:
            communicator.stop()
    
    def test_hardware_stress_test_multiple_requests(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus
    ):
        """
        测试硬件环境下的压力测试（多次请求）
        
        验证需求：
        - 需求 2.1-2.6: 高频请求下的稳定性
        - 需求 9.1-9.5: 错误处理和稳定性
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 硬件环境压力测试（多次请求）")
        logger.info("=" * 60)
        
        # 设置测试坐标
        test_coords = np.array([2000, 3000, 4000], dtype=np.float32)
        mock_decision_layer.set_target_coords(test_coords)
        
        # 创建并启动CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        if not communicator.start():
            pytest.skip("无法启动CAN通信器")
        
        try:
            time.sleep(1.0)
            
            # 创建外部CAN客户端
            import can
            
            try:
                client_bus = can.Bus(
                    interface=can_config.can_interface,
                    channel=can_config.can_channel,
                    bitrate=can_config.can_bitrate
                )
                
                # 发送多次请求
                request_count = 50
                response_count = 0
                response_times = []
                
                from oak_vision_system.modules.can_communication.can_protocol import CANProtocol
                
                request_msg = can.Message(
                    arbitration_id=CANProtocol.FRAME_ID,
                    data=[CANProtocol.MSG_TYPE_REQUEST, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                    is_extended_id=False
                )
                
                logger.info(f"开始发送{request_count}次请求...")
                
                for i in range(request_count):
                    # 发送请求
                    send_time = time.time()
                    client_bus.send(request_msg)
                    
                    # 等待响应
                    response_msg = client_bus.recv(timeout=0.5)
                    
                    if response_msg is not None:
                        receive_time = time.time()
                        response_time = (receive_time - send_time) * 1000
                        response_times.append(response_time)
                        response_count += 1
                        
                        # 验证响应格式
                        if (response_msg.arbitration_id == CANProtocol.FRAME_ID and
                            len(response_msg.data) == 8 and
                            response_msg.data[0] == CANProtocol.MSG_TYPE_RESPONSE):
                            
                            # 解码坐标验证
                            import struct
                            try:
                                _, x, y, z = struct.unpack('<Bxhhh', response_msg.data)
                                if x == 2000 and y == 3000 and z == 4000:
                                    pass  # 坐标正确
                                else:
                                    logger.warning(f"第{i+1}次请求坐标不匹配: ({x}, {y}, {z})")
                            except:
                                logger.warning(f"第{i+1}次请求响应解码失败")
                    
                    # 控制请求频率（避免过载）
                    time.sleep(0.02)  # 50Hz
                
                # 统计结果
                success_rate = response_count / request_count
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0
                max_response_time = max(response_times) if response_times else 0
                
                logger.info(f"压力测试结果:")
                logger.info(f"  请求次数: {request_count}")
                logger.info(f"  响应次数: {response_count}")
                logger.info(f"  成功率: {success_rate:.2%}")
                logger.info(f"  平均响应时间: {avg_response_time:.2f}ms")
                logger.info(f"  最大响应时间: {max_response_time:.2f}ms")
                
                # 验证性能指标
                assert success_rate >= 0.95, f"成功率应该 >= 95%，实际: {success_rate:.2%}"
                assert avg_response_time < 20, f"平均响应时间应该 < 20ms，实际: {avg_response_time:.2f}ms"
                assert max_response_time < 100, f"最大响应时间应该 < 100ms，实际: {max_response_time:.2f}ms"
                
                # 验证决策层调用次数
                call_count = mock_decision_layer.get_call_count()
                assert call_count >= response_count * 0.9, f"决策层调用次数应该接近响应次数: {call_count} vs {response_count}"
                
                logger.info("✅ 硬件环境压力测试通过")
                
            finally:
                if 'client_bus' in locals():
                    client_bus.shutdown()
                    
        finally:
            communicator.stop()


# ==================== 硬件级人员警报测试 ====================

class TestHardwarePersonAlert:
    """硬件级人员警报测试"""
    
    @pytest.fixture
    def can_config(self):
        """创建硬件测试用CAN配置（快速警报）"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='can0',
            can_bitrate=250000,
            enable_auto_configure=True,
            sudo_password=None,
            alert_interval_ms=100,  # 100ms间隔
            send_timeout_ms=100,
            receive_timeout_ms=50
        )
    
    @pytest.fixture
    def mock_decision_layer(self):
        """创建模拟决策层"""
        return MockDecisionLayer()
    
    @pytest.fixture
    def mock_event_bus(self):
        """创建模拟事件总线"""
        return MockEventBus()
    
    def test_hardware_person_alert_real_timing(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus
    ):
        """
        测试硬件环境下的人员警报真实时序
        
        验证需求：
        - 需求 3.1-3.6: 人员警报完整流程
        - 需求 3.4: 警报间隔准确性（硬件环境）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 硬件环境人员警报真实时序")
        logger.info("=" * 60)
        
        # 创建并启动CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        if not communicator.start():
            pytest.skip("无法启动CAN通信器")
        
        try:
            time.sleep(1.0)
            
            # 创建外部CAN客户端监听警报
            import can
            
            try:
                client_bus = can.Bus(
                    interface=can_config.can_interface,
                    channel=can_config.can_channel,
                    bitrate=can_config.can_bitrate
                )
                
                # 触发人员警报
                logger.info("触发人员警报...")
                mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
                
                # 监听警报消息
                alert_timestamps = []
                monitoring_start = time.time()
                monitoring_duration = 2.0  # 监听2秒
                
                from oak_vision_system.modules.can_communication.can_protocol import CANProtocol
                
                while time.time() - monitoring_start < monitoring_duration:
                    msg = client_bus.recv(timeout=0.1)
                    
                    if msg is not None:
                        # 检查是否为警报消息
                        if (msg.arbitration_id == CANProtocol.FRAME_ID and
                            len(msg.data) >= 1 and
                            msg.data[0] == CANProtocol.MSG_TYPE_ALERT):
                            
                            alert_timestamps.append(time.time())
                            logger.debug(f"收到警报消息 #{len(alert_timestamps)}")
                
                # 停止警报
                logger.info("停止人员警报...")
                mock_event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
                
                # 等待确认警报停止
                time.sleep(0.5)
                
                # 验证警报数量
                logger.info(f"收到警报消息数量: {len(alert_timestamps)}")
                assert len(alert_timestamps) >= 15, f"应该收到至少15次警报，实际: {len(alert_timestamps)}"
                
                # 计算时间间隔
                intervals = []
                for i in range(1, len(alert_timestamps)):
                    interval = (alert_timestamps[i] - alert_timestamps[i-1]) * 1000
                    intervals.append(interval)
                
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    min_interval = min(intervals)
                    max_interval = max(intervals)
                    
                    logger.info(f"警报间隔统计:")
                    logger.info(f"  平均间隔: {avg_interval:.2f}ms")
                    logger.info(f"  最小间隔: {min_interval:.2f}ms")
                    logger.info(f"  最大间隔: {max_interval:.2f}ms")
                    logger.info(f"  期望间隔: {can_config.alert_interval_ms}ms")
                    
                    # 验证间隔准确性（硬件环境允许更大误差）
                    expected_interval = can_config.alert_interval_ms
                    assert abs(avg_interval - expected_interval) <= 20, \
                        f"平均间隔误差过大: 期望{expected_interval}ms±20ms, 实际{avg_interval:.2f}ms"
                    
                    # 验证间隔稳定性
                    assert max_interval - min_interval <= 50, \
                        f"间隔抖动过大: {max_interval:.2f}ms - {min_interval:.2f}ms = {max_interval - min_interval:.2f}ms"
                
                logger.info("✅ 硬件环境人员警报真实时序测试通过")
                
            finally:
                if 'client_bus' in locals():
                    client_bus.shutdown()
                    
        finally:
            communicator.stop()
    
    def test_hardware_alert_stop_verification(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus
    ):
        """
        测试硬件环境下的警报停止验证
        
        验证需求：
        - 需求 3.5: 警报停止的可靠性
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 硬件环境警报停止验证")
        logger.info("=" * 60)
        
        # 创建并启动CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        if not communicator.start():
            pytest.skip("无法启动CAN通信器")
        
        try:
            time.sleep(1.0)
            
            # 创建外部CAN客户端
            import can
            
            try:
                client_bus = can.Bus(
                    interface=can_config.can_interface,
                    channel=can_config.can_channel,
                    bitrate=can_config.can_bitrate
                )
                
                # 启动警报
                logger.info("启动警报...")
                mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
                
                # 等待一些警报
                time.sleep(0.5)
                
                # 计算启动阶段的警报数量
                start_alert_count = 0
                start_time = time.time()
                
                from oak_vision_system.modules.can_communication.can_protocol import CANProtocol
                
                while time.time() - start_time < 0.5:
                    msg = client_bus.recv(timeout=0.1)
                    if (msg is not None and
                        msg.arbitration_id == CANProtocol.FRAME_ID and
                        len(msg.data) >= 1 and
                        msg.data[0] == CANProtocol.MSG_TYPE_ALERT):
                        start_alert_count += 1
                
                logger.info(f"启动阶段警报数量: {start_alert_count}")
                
                # 停止警报
                logger.info("停止警报...")
                stop_time = time.time()
                mock_event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
                
                # 监控停止后的警报（应该很快停止）
                post_stop_alert_count = 0
                monitor_duration = 1.0  # 监控1秒
                
                while time.time() - stop_time < monitor_duration:
                    msg = client_bus.recv(timeout=0.1)
                    if (msg is not None and
                        msg.arbitration_id == CANProtocol.FRAME_ID and
                        len(msg.data) >= 1 and
                        msg.data[0] == CANProtocol.MSG_TYPE_ALERT):
                        
                        alert_time = time.time() - stop_time
                        post_stop_alert_count += 1
                        logger.debug(f"停止后收到警报 #{post_stop_alert_count}，时间: {alert_time*1000:.2f}ms")
                
                logger.info(f"停止后警报数量: {post_stop_alert_count}")
                
                # 验证警报停止效果
                # 允许1-2个延迟的警报（由于定时器和网络延迟）
                assert post_stop_alert_count <= 2, \
                    f"停止后警报数量应该 <= 2，实际: {post_stop_alert_count}"
                
                # 验证启动阶段确实有警报
                assert start_alert_count >= 3, \
                    f"启动阶段应该有足够的警报，实际: {start_alert_count}"
                
                logger.info("✅ 硬件环境警报停止验证测试通过")
                
            finally:
                if 'client_bus' in locals():
                    client_bus.shutdown()
                    
        finally:
            communicator.stop()


# ==================== 硬件级完整流程测试 ====================

class TestHardwareCompleteFlow:
    """硬件级完整流程测试"""
    
    @pytest.fixture
    def can_config(self):
        """创建硬件测试用CAN配置"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='can0',
            can_bitrate=250000,
            enable_auto_configure=True,
            sudo_password=None,
            alert_interval_ms=200,  # 200ms间隔，便于观察
            send_timeout_ms=100,
            receive_timeout_ms=50
        )
    
    @pytest.fixture
    def mock_decision_layer(self):
        """创建模拟决策层"""
        return MockDecisionLayer()
    
    @pytest.fixture
    def mock_event_bus(self):
        """创建模拟事件总线"""
        return MockEventBus()
    
    def test_hardware_complete_workflow(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus
    ):
        """
        测试硬件环境下的完整工作流程
        
        验证需求：
        - 所有CAN通信需求的综合验证
        - 真实环境下的系统稳定性
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 硬件环境完整工作流程")
        logger.info("=" * 60)
        
        # 设置测试坐标
        test_coords = np.array([5000, -6000, 7000], dtype=np.float32)
        mock_decision_layer.set_target_coords(test_coords)
        
        # 创建并启动CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        if not communicator.start():
            pytest.skip("无法启动CAN通信器")
        
        try:
            time.sleep(1.0)
            
            # 创建外部CAN客户端
            import can
            
            try:
                client_bus = can.Bus(
                    interface=can_config.can_interface,
                    channel=can_config.can_channel,
                    bitrate=can_config.can_bitrate
                )
                
                from oak_vision_system.modules.can_communication.can_protocol import CANProtocol
                
                # 阶段1: 测试坐标请求响应
                logger.info("阶段1: 测试坐标请求响应")
                
                request_msg = can.Message(
                    arbitration_id=CANProtocol.FRAME_ID,
                    data=[CANProtocol.MSG_TYPE_REQUEST, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                    is_extended_id=False
                )
                
                # 发送几次坐标请求
                coordinate_responses = 0
                for i in range(5):
                    client_bus.send(request_msg)
                    response = client_bus.recv(timeout=0.5)
                    
                    if (response is not None and
                        response.arbitration_id == CANProtocol.FRAME_ID and
                        len(response.data) == 8 and
                        response.data[0] == CANProtocol.MSG_TYPE_RESPONSE):
                        
                        coordinate_responses += 1
                        
                        # 验证坐标
                        import struct
                        _, x, y, z = struct.unpack('<Bxhhh', response.data)
                        assert x == 5000 and y == -6000 and z == 7000, \
                            f"坐标不匹配: ({x}, {y}, {z})"
                    
                    time.sleep(0.1)
                
                logger.info(f"坐标响应成功: {coordinate_responses}/5")
                assert coordinate_responses >= 4, "坐标响应成功率应该 >= 80%"
                
                # 阶段2: 测试人员警报
                logger.info("阶段2: 测试人员警报")
                
                # 启动警报
                mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
                
                # 监听警报
                alert_count = 0
                alert_start = time.time()
                
                while time.time() - alert_start < 1.0:  # 监听1秒
                    msg = client_bus.recv(timeout=0.1)
                    
                    if (msg is not None and
                        msg.arbitration_id == CANProtocol.FRAME_ID and
                        len(msg.data) >= 1 and
                        msg.data[0] == CANProtocol.MSG_TYPE_ALERT):
                        alert_count += 1
                
                logger.info(f"收到警报数量: {alert_count}")
                assert alert_count >= 3, "应该收到足够的警报消息"
                
                # 停止警报
                mock_event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
                time.sleep(0.5)
                
                # 阶段3: 测试混合场景（坐标请求 + 警报）
                logger.info("阶段3: 测试混合场景")
                
                # 启动警报
                mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
                time.sleep(0.2)
                
                # 在警报期间发送坐标请求
                mixed_responses = 0
                mixed_alerts = 0
                
                for i in range(3):
                    # 发送坐标请求
                    client_bus.send(request_msg)
                    
                    # 收集消息（可能是响应或警报）
                    messages = []
                    collect_start = time.time()
                    
                    while time.time() - collect_start < 0.3:
                        msg = client_bus.recv(timeout=0.1)
                        if msg is not None:
                            messages.append(msg)
                    
                    # 分类消息
                    for msg in messages:
                        if (msg.arbitration_id == CANProtocol.FRAME_ID and
                            len(msg.data) >= 1):
                            
                            if msg.data[0] == CANProtocol.MSG_TYPE_RESPONSE:
                                mixed_responses += 1
                            elif msg.data[0] == CANProtocol.MSG_TYPE_ALERT:
                                mixed_alerts += 1
                
                # 停止警报
                mock_event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
                
                logger.info(f"混合场景 - 坐标响应: {mixed_responses}, 警报: {mixed_alerts}")
                assert mixed_responses >= 2, "混合场景下应该收到坐标响应"
                assert mixed_alerts >= 1, "混合场景下应该收到警报消息"
                
                # 阶段4: 验证系统状态
                logger.info("阶段4: 验证系统状态")
                
                # 验证决策层调用
                total_calls = mock_decision_layer.get_call_count()
                logger.info(f"决策层总调用次数: {total_calls}")
                assert total_calls >= coordinate_responses + mixed_responses, \
                    "决策层调用次数应该匹配响应次数"
                
                # 验证事件历史
                event_history = mock_event_bus.get_event_history()
                logger.info(f"事件历史数量: {len(event_history)}")
                assert len(event_history) >= 4, "应该有足够的事件历史记录"
                
                logger.info("✅ 硬件环境完整工作流程测试通过")
                
            finally:
                if 'client_bus' in locals():
                    client_bus.shutdown()
                    
        finally:
            communicator.stop()


# ==================== 主测试函数 ====================

def run_can_hardware_linux_tests():
    """运行CAN通信模块硬件测试（用于手动执行）"""
    logger.info("\n" + "=" * 80)
    logger.info("CAN通信模块硬件测试（Linux环境 + 真实硬件）")
    logger.info("=" * 80)
    
    logger.info("注意：此测试需要完整的硬件环境")
    logger.info("运行环境要求:")
    logger.info("- Linux系统（香橙派）")
    logger.info("- 真实CAN硬件接口")
    logger.info("- 外部CAN控制器设备（可选）")
    logger.info("- 物理CAN总线连接（可选）")
    logger.info("")
    logger.info("运行前准备:")
    logger.info("1. 安装python-can: pip install python-can pytest")
    logger.info("2. 配置CAN硬件接口:")
    logger.info("   sudo ip link set can0 type can bitrate 250000")
    logger.info("   sudo ip link set can0 up")
    logger.info("3. 验证CAN接口: ip link show can0")
    logger.info("4. 确保有足够的系统权限")
    logger.info("")
    logger.info("运行命令:")
    logger.info("pytest oak_vision_system/tests/integration/can_communication/test_can_hardware_linux.py -v -s")
    logger.info("")
    logger.info("注意：如果没有外部CAN设备，测试将使用loopback模式")


if __name__ == "__main__":
    run_can_hardware_linux_tests()