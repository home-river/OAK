"""
CAN通信模块Linux环境集成测试

专门测试CAN通信模块在Linux环境下的集成功能：
1. 端到端坐标请求响应测试
2. 人员警报流程测试
3. 接口配置流程测试

注意：此测试创建后不立即运行，留待Linux环境执行
运行环境：Linux（香橙派）+ socketCAN ⚠️

验证需求：
- 需求 2.1, 2.2, 2.3, 2.5: 坐标请求响应
- 需求 3.1, 3.2, 3.3, 3.5: 人员警报流程
- 需求 1.2, 1.8: 接口配置流程
"""

import os
import sys
import time
import threading
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from typing import Optional, List, Dict, Any
import can
import numpy as np

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from oak_vision_system.modules.can_communication.can_communicator import CANCommunicator
from oak_vision_system.modules.can_communication.can_protocol import CANProtocol
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
from oak_vision_system.modules.data_processing.decision_layer.types import PersonWarningStatus

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ==================== 测试辅助类 ====================

class MockDecisionLayer:
    """模拟决策层"""
    
    def __init__(self):
        self._target_coords = None
        self._lock = threading.Lock()
    
    def set_target_coords(self, coords: Optional[np.ndarray]):
        """设置目标坐标（测试用）"""
        with self._lock:
            self._target_coords = coords
    
    def get_target_coords_snapshot(self) -> Optional[np.ndarray]:
        """获取目标坐标快照"""
        with self._lock:
            return self._target_coords.copy() if self._target_coords is not None else None


class MockEventBus:
    """模拟事件总线"""
    
    def __init__(self):
        self._subscribers = {}
        self._subscription_counter = 0
    
    def subscribe(self, event_type, callback, subscriber_name: str) -> str:
        """订阅事件"""
        subscription_id = f"sub_{self._subscription_counter}"
        self._subscription_counter += 1
        self._subscribers[subscription_id] = {
            'event_type': event_type,
            'callback': callback,
            'subscriber_name': subscriber_name
        }
        return subscription_id
    
    def unsubscribe(self, subscription_id: str):
        """取消订阅"""
        if subscription_id in self._subscribers:
            del self._subscribers[subscription_id]
    
    def publish_person_warning(self, status: PersonWarningStatus):
        """发布人员警报事件（测试用）"""
        event_data = {
            'status': status,
            'timestamp': time.time()
        }
        
        # 通知所有订阅者
        from oak_vision_system.core.event_bus.event_types import EventType
        for sub_info in self._subscribers.values():
            if sub_info['event_type'] == EventType.PERSON_WARNING:
                try:
                    sub_info['callback'](event_data)
                except Exception as e:
                    logger.error(f"事件回调异常: {e}")


class CANTestHelper:
    """CAN测试辅助工具"""
    
    @staticmethod
    def create_coordinate_request_message() -> can.Message:
        """创建坐标请求消息"""
        return can.Message(
            arbitration_id=CANProtocol.FRAME_ID,
            data=[CANProtocol.MSG_TYPE_REQUEST, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
            is_extended_id=False
        )
    
    @staticmethod
    def decode_coordinate_response(msg: can.Message) -> tuple[int, int, int]:
        """解码坐标响应消息"""
        if len(msg.data) < 8:
            raise ValueError("响应消息长度不足")
        
        if msg.data[0] != CANProtocol.MSG_TYPE_RESPONSE:
            raise ValueError(f"无效的响应消息类型: {msg.data[0]}")
        
        # 解码坐标（小端序，有符号16位）
        x = int.from_bytes(msg.data[2:4], byteorder='little', signed=True)
        y = int.from_bytes(msg.data[4:6], byteorder='little', signed=True)
        z = int.from_bytes(msg.data[6:8], byteorder='little', signed=True)
        
        return x, y, z
    
    @staticmethod
    def is_alert_message(msg: can.Message) -> bool:
        """检查是否为警报消息"""
        return (len(msg.data) >= 1 and 
                msg.data[0] == CANProtocol.MSG_TYPE_ALERT and
                msg.arbitration_id == CANProtocol.FRAME_ID)


# ==================== 平台检测测试 ====================

class TestLinuxPlatformRequirements:
    """Linux平台要求测试"""
    
    def test_linux_platform_detection(self):
        """
        测试Linux平台检测
        
        验证需求：
        - 需求 1.2: CAN接口自动配置（仅Linux）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: Linux平台检测")
        logger.info("=" * 60)
        
        # 检查当前平台
        current_platform = sys.platform
        logger.info(f"当前平台: {current_platform}")
        
        # 验证平台检测逻辑
        is_linux = current_platform in ['linux', 'linux2']
        
        if is_linux:
            logger.info("✅ 检测到Linux平台，CAN集成测试可以运行")
            # 检查是否有can模块
            try:
                import can
                logger.info("✅ python-can模块可用")
            except ImportError:
                logger.warning("⚠️ python-can模块不可用，请安装: pip install python-can")
        else:
            logger.warning(f"⚠️ 非Linux平台（{current_platform}），CAN集成测试不可用")
        
        # 这个测试总是通过，只是记录平台信息
        assert isinstance(is_linux, bool), "平台检测应该返回布尔值"


# ==================== 端到端坐标请求响应测试 ====================

class TestCoordinateRequestResponse:
    """端到端坐标请求响应测试"""
    
    @pytest.fixture
    def can_config(self):
        """创建测试用CAN配置"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='vcan0',  # 使用虚拟CAN接口进行测试
            can_bitrate=250000,
            enable_auto_configure=False,  # 测试中不自动配置
            sudo_password=None,
            alert_interval_ms=100,
            send_timeout_ms=50,
            receive_timeout_ms=10
        )
    
    @pytest.fixture
    def mock_decision_layer(self):
        """创建模拟决策层"""
        return MockDecisionLayer()
    
    @pytest.fixture
    def mock_event_bus(self):
        """创建模拟事件总线"""
        return MockEventBus()
    
    def test_coordinate_request_response_basic(self, can_config, mock_decision_layer, mock_event_bus):
        """
        测试基本的坐标请求响应
        
        验证需求：
        - 需求 2.1: 接收坐标请求
        - 需求 2.2: 调用决策层获取坐标
        - 需求 2.3: 发送坐标响应
        - 需求 2.5: 响应格式正确
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 基本坐标请求响应")
        logger.info("=" * 60)
        
        # 设置测试坐标
        test_coords = np.array([100, 200, 300], dtype=np.float32)
        mock_decision_layer.set_target_coords(test_coords)
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 模拟CAN总线和消息发送
        mock_bus = Mock()
        mock_sent_messages = []
        
        def capture_sent_message(msg, timeout=None):
            mock_sent_messages.append(msg)
        
        mock_bus.send = capture_sent_message
        communicator.bus = mock_bus
        
        # 创建坐标请求消息
        request_msg = CANTestHelper.create_coordinate_request_message()
        
        # 处理请求
        start_time = time.time()
        communicator.on_message_received(request_msg)
        response_time = (time.time() - start_time) * 1000
        
        # 验证响应时间 < 10ms
        assert response_time < 10, f"响应时间应该 < 10ms，实际: {response_time:.2f}ms"
        
        # 验证发送了响应消息
        assert len(mock_sent_messages) == 1, f"应该发送1条响应消息，实际: {len(mock_sent_messages)}"
        
        response_msg = mock_sent_messages[0]
        
        # 验证响应消息格式
        assert response_msg.arbitration_id == CANProtocol.FRAME_ID, "响应消息ID应该正确"
        assert len(response_msg.data) == 8, "响应消息长度应该为8字节"
        assert response_msg.data[0] == CANProtocol.MSG_TYPE_RESPONSE, "响应消息类型应该正确"
        assert response_msg.data[1] == 0x00, "响应消息保留字节应该为0"
        
        # 解码并验证坐标
        x, y, z = CANTestHelper.decode_coordinate_response(response_msg)
        assert x == 100, f"X坐标应该为100，实际: {x}"
        assert y == 200, f"Y坐标应该为200，实际: {y}"
        assert z == 300, f"Z坐标应该为300，实际: {z}"
        
        logger.info(f"✅ 基本坐标请求响应测试通过，响应时间: {response_time:.2f}ms")
    
    def test_coordinate_request_response_none_coords(self, can_config, mock_decision_layer, mock_event_bus):
        """
        测试决策层返回None时的兜底逻辑
        
        验证需求：
        - 需求 2.4: 兜底逻辑（返回0,0,0）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 决策层返回None的兜底逻辑")
        logger.info("=" * 60)
        
        # 设置决策层返回None
        mock_decision_layer.set_target_coords(None)
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 模拟CAN总线
        mock_bus = Mock()
        mock_sent_messages = []
        mock_bus.send = lambda msg, timeout=None: mock_sent_messages.append(msg)
        communicator.bus = mock_bus
        
        # 创建坐标请求消息
        request_msg = CANTestHelper.create_coordinate_request_message()
        
        # 处理请求
        communicator.on_message_received(request_msg)
        
        # 验证发送了响应消息
        assert len(mock_sent_messages) == 1, "应该发送兜底响应消息"
        
        # 解码并验证兜底坐标
        response_msg = mock_sent_messages[0]
        x, y, z = CANTestHelper.decode_coordinate_response(response_msg)
        assert x == 0, f"兜底X坐标应该为0，实际: {x}"
        assert y == 0, f"兜底Y坐标应该为0，实际: {y}"
        assert z == 0, f"兜底Z坐标应该为0，实际: {z}"
        
        logger.info("✅ 决策层返回None的兜底逻辑测试通过")
    
    def test_coordinate_request_response_exception_handling(self, can_config, mock_event_bus):
        """
        测试决策层抛异常时的兜底逻辑
        
        验证需求：
        - 需求 2.4: 兜底逻辑（异常处理）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 决策层异常的兜底逻辑")
        logger.info("=" * 60)
        
        # 创建会抛异常的决策层
        mock_decision_layer = Mock()
        mock_decision_layer.get_target_coords_snapshot.side_effect = RuntimeError("决策层异常")
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 模拟CAN总线
        mock_bus = Mock()
        mock_sent_messages = []
        mock_bus.send = lambda msg, timeout=None: mock_sent_messages.append(msg)
        communicator.bus = mock_bus
        
        # 创建坐标请求消息
        request_msg = CANTestHelper.create_coordinate_request_message()
        
        # 处理请求（应该不抛异常）
        communicator.on_message_received(request_msg)
        
        # 验证发送了兜底响应消息
        assert len(mock_sent_messages) == 1, "应该发送兜底响应消息"
        
        # 解码并验证兜底坐标
        response_msg = mock_sent_messages[0]
        x, y, z = CANTestHelper.decode_coordinate_response(response_msg)
        assert x == 0, f"异常兜底X坐标应该为0，实际: {x}"
        assert y == 0, f"异常兜底Y坐标应该为0，实际: {y}"
        assert z == 0, f"异常兜底Z坐标应该为0，实际: {z}"
        
        logger.info("✅ 决策层异常的兜底逻辑测试通过")
    
    def test_coordinate_request_response_boundary_values(self, can_config, mock_decision_layer, mock_event_bus):
        """
        测试边界值坐标的编解码
        
        验证需求：
        - 需求 2.5: 响应格式正确（边界值处理）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 边界值坐标编解码")
        logger.info("=" * 60)
        
        # 测试用例：边界值坐标
        test_cases = [
            (32767, 32767, 32767),    # 最大正值
            (-32768, -32768, -32768), # 最大负值
            (32767, -32768, 0),       # 混合边界值
            (-100, -200, -300),       # 负数坐标
        ]
        
        for expected_x, expected_y, expected_z in test_cases:
            logger.info(f"测试坐标: ({expected_x}, {expected_y}, {expected_z})")
            
            # 设置测试坐标
            test_coords = np.array([expected_x, expected_y, expected_z], dtype=np.float32)
            mock_decision_layer.set_target_coords(test_coords)
            
            # 创建CAN通信器
            communicator = CANCommunicator(
                config=can_config,
                decision_layer=mock_decision_layer,
                event_bus=mock_event_bus
            )
            
            # 模拟CAN总线
            mock_bus = Mock()
            mock_sent_messages = []
            mock_bus.send = lambda msg, timeout=None: mock_sent_messages.append(msg)
            communicator.bus = mock_bus
            
            # 创建坐标请求消息
            request_msg = CANTestHelper.create_coordinate_request_message()
            
            # 处理请求
            communicator.on_message_received(request_msg)
            
            # 验证响应
            assert len(mock_sent_messages) == 1, f"应该发送1条响应消息"
            
            response_msg = mock_sent_messages[0]
            x, y, z = CANTestHelper.decode_coordinate_response(response_msg)
            
            assert x == expected_x, f"X坐标不匹配: 期望{expected_x}, 实际{x}"
            assert y == expected_y, f"Y坐标不匹配: 期望{expected_y}, 实际{y}"
            assert z == expected_z, f"Z坐标不匹配: 期望{expected_z}, 实际{z}"
        
        logger.info("✅ 边界值坐标编解码测试通过")


# ==================== 人员警报流程测试 ====================

class TestPersonAlertFlow:
    """人员警报流程测试"""
    
    @pytest.fixture
    def can_config(self):
        """创建测试用CAN配置（快速警报间隔）"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='vcan0',
            can_bitrate=250000,
            enable_auto_configure=False,
            sudo_password=None,
            alert_interval_ms=50,  # 50ms间隔，便于测试
            send_timeout_ms=50,
            receive_timeout_ms=10
        )
    
    @pytest.fixture
    def mock_decision_layer(self):
        """创建模拟决策层"""
        return MockDecisionLayer()
    
    @pytest.fixture
    def mock_event_bus(self):
        """创建模拟事件总线"""
        return MockEventBus()
    
    def test_person_alert_triggered_flow(self, can_config, mock_decision_layer, mock_event_bus):
        """
        测试人员警报触发流程
        
        验证需求：
        - 需求 3.1: 事件订阅
        - 需求 3.2: 警报启动
        - 需求 3.3: 周期发送
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 人员警报触发流程")
        logger.info("=" * 60)
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 模拟CAN总线
        mock_bus = Mock()
        mock_sent_messages = []
        mock_bus.send = lambda msg, timeout=None: mock_sent_messages.append(msg)
        communicator.bus = mock_bus
        
        # 验证初始状态
        assert not communicator._alert_active, "初始状态警报应该未激活"
        assert communicator._alert_thread is None, "初始状态线程应该为None"
        
        # 发布TRIGGERED事件
        mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
        
        # 等待事件处理
        time.sleep(0.01)
        
        # 验证警报已启动
        assert communicator._alert_active, "警报应该已激活"
        assert communicator._alert_thread is not None, "线程应该已创建"
        
        # 等待几个警报周期
        time.sleep(0.2)  # 等待200ms，应该收到约4次警报
        
        # 验证发送了警报消息
        alert_count = len([msg for msg in mock_sent_messages if CANTestHelper.is_alert_message(msg)])
        assert alert_count >= 2, f"应该发送至少2次警报，实际: {alert_count}"
        assert alert_count <= 6, f"警报次数不应该过多，实际: {alert_count}"
        
        # 验证警报消息格式
        for msg in mock_sent_messages:
            if CANTestHelper.is_alert_message(msg):
                assert msg.arbitration_id == CANProtocol.FRAME_ID, "警报消息ID应该正确"
                assert len(msg.data) >= 1, "警报消息应该有数据"
                assert msg.data[0] == CANProtocol.MSG_TYPE_ALERT, "警报消息类型应该正确"
        
        logger.info(f"✅ 人员警报触发流程测试通过，发送了{alert_count}次警报")
    
    def test_person_alert_cleared_flow(self, can_config, mock_decision_layer, mock_event_bus):
        """
        测试人员警报清除流程
        
        验证需求：
        - 需求 3.5: 警报停止
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 人员警报清除流程")
        logger.info("=" * 60)
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 模拟CAN总线
        mock_bus = Mock()
        mock_sent_messages = []
        mock_bus.send = lambda msg, timeout=None: mock_sent_messages.append(msg)
        communicator.bus = mock_bus
        
        # 先触发警报
        mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
        time.sleep(0.01)
        
        # 验证警报已启动
        assert communicator._alert_active, "警报应该已激活"
        
        # 等待一些警报发送
        time.sleep(0.1)
        initial_alert_count = len([msg for msg in mock_sent_messages if CANTestHelper.is_alert_message(msg)])
        
        # 发布CLEARED事件
        mock_event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
        time.sleep(0.01)
        
        # 验证警报已停止
        assert not communicator._alert_active, "警报应该已停止"
        assert communicator._alert_thread is None, "线程应该已结束"
        
        # 等待一段时间，确认不再发送警报
        time.sleep(0.15)
        final_alert_count = len([msg for msg in mock_sent_messages if CANTestHelper.is_alert_message(msg)])
        
        # 验证警报计数没有显著增加（可能有1-2个延迟的警报）
        alert_increase = final_alert_count - initial_alert_count
        assert alert_increase <= 2, f"警报停止后不应该继续发送，增加了{alert_increase}次"
        
        logger.info(f"✅ 人员警报清除流程测试通过，初始{initial_alert_count}次，最终{final_alert_count}次")
    
    def test_person_alert_timing_accuracy(self, can_config, mock_decision_layer, mock_event_bus):
        """
        测试人员警报时间间隔准确性
        
        验证需求：
        - 需求 3.4: 警报间隔准确性
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 人员警报时间间隔准确性")
        logger.info("=" * 60)
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 记录警报时间戳
        alert_timestamps = []
        
        def capture_alert_with_timestamp(msg, timeout=None):
            if CANTestHelper.is_alert_message(msg):
                alert_timestamps.append(time.time())
        
        mock_bus = Mock()
        mock_bus.send = capture_alert_with_timestamp
        communicator.bus = mock_bus
        
        # 触发警报
        mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
        
        # 等待收集足够的时间戳
        time.sleep(0.3)  # 等待300ms，应该收到约6次警报
        
        # 停止警报
        mock_event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
        
        # 验证时间戳数量
        assert len(alert_timestamps) >= 3, f"应该收到至少3次警报，实际: {len(alert_timestamps)}"
        
        # 计算时间间隔
        intervals = []
        for i in range(1, len(alert_timestamps)):
            interval = (alert_timestamps[i] - alert_timestamps[i-1]) * 1000  # 转换为毫秒
            intervals.append(interval)
        
        # 验证间隔准确性（允许±20ms误差）
        expected_interval = can_config.alert_interval_ms
        for i, interval in enumerate(intervals):
            assert abs(interval - expected_interval) <= 20, \
                f"第{i+1}个间隔不准确: 期望{expected_interval}ms±20ms, 实际{interval:.2f}ms"
        
        # 计算平均间隔
        avg_interval = sum(intervals) / len(intervals)
        logger.info(f"平均警报间隔: {avg_interval:.2f}ms (期望: {expected_interval}ms)")
        
        assert abs(avg_interval - expected_interval) <= 10, \
            f"平均间隔不准确: 期望{expected_interval}ms±10ms, 实际{avg_interval:.2f}ms"
        
        logger.info("✅ 人员警报时间间隔准确性测试通过")


# ==================== 接口配置流程测试 ====================

class TestInterfaceConfigurationFlow:
    """接口配置流程测试"""
    
    @pytest.fixture
    def can_config_with_auto_configure(self):
        """创建启用自动配置的CAN配置"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='vcan0',
            can_bitrate=250000,
            enable_auto_configure=True,  # 启用自动配置
            sudo_password='test_password',
            alert_interval_ms=100,
            send_timeout_ms=50,
            receive_timeout_ms=10
        )
    
    @pytest.fixture
    def mock_decision_layer(self):
        """创建模拟决策层"""
        return MockDecisionLayer()
    
    @pytest.fixture
    def mock_event_bus(self):
        """创建模拟事件总线"""
        return MockEventBus()
    
    @patch('sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config.configure_can_interface')
    @patch('oak_vision_system.modules.can_communication.can_interface_config.reset_can_interface')
    @patch('can.Bus')
    @patch('can.Notifier')
    def test_interface_configuration_success_flow(
        self, 
        mock_notifier_class, 
        mock_bus_class, 
        mock_reset_interface, 
        mock_configure_interface,
        can_config_with_auto_configure, 
        mock_decision_layer, 
        mock_event_bus
    ):
        """
        测试接口配置成功流程
        
        验证需求：
        - 需求 1.2: CAN接口自动配置
        - 需求 1.8: 接口重置
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 接口配置成功流程")
        logger.info("=" * 60)
        
        # 模拟配置成功
        mock_configure_interface.return_value = True
        mock_reset_interface.return_value = True
        
        # 模拟CAN总线和Notifier
        mock_bus = Mock()
        mock_notifier = Mock()
        mock_bus_class.return_value = mock_bus
        mock_notifier_class.return_value = mock_notifier
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config_with_auto_configure,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 启动通信器
        result = communicator.start()
        
        # 验证启动成功
        assert result is True, "通信器启动应该成功"
        
        # 验证调用了接口配置
        mock_configure_interface.assert_called_once_with(
            channel='vcan0',
            bitrate=250000,
            sudo_password='test_password'
        )
        
        # 验证创建了CAN总线
        mock_bus_class.assert_called_once_with(
            interface='socketcan',
            channel='vcan0',
            bitrate=250000
        )
        
        # 验证创建了Notifier
        mock_notifier_class.assert_called_once()
        
        # 停止通信器
        communicator.stop()
        
        # 验证调用了接口重置
        mock_reset_interface.assert_called_once_with(
            channel='vcan0',
            sudo_password='test_password'
        )
        
        # 验证停止了Notifier和Bus
        mock_notifier.stop.assert_called_once()
        mock_bus.shutdown.assert_called_once()
        
        logger.info("✅ 接口配置成功流程测试通过")
    
    @patch('sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config.configure_can_interface')
    def test_interface_configuration_failure_flow(
        self, 
        mock_configure_interface,
        can_config_with_auto_configure, 
        mock_decision_layer, 
        mock_event_bus
    ):
        """
        测试接口配置失败流程
        
        验证需求：
        - 需求 1.2: CAN接口自动配置（失败处理）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 接口配置失败流程")
        logger.info("=" * 60)
        
        # 模拟配置失败
        mock_configure_interface.return_value = False
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config_with_auto_configure,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 启动通信器（配置失败但仍尝试连接）
        with patch('can.Bus') as mock_bus_class:
            mock_bus_class.side_effect = can.CanError("接口未配置")
            
            result = communicator.start()
            
            # 验证启动失败
            assert result is False, "接口配置失败时启动应该失败"
            
            # 验证调用了接口配置
            mock_configure_interface.assert_called_once_with(
                channel='vcan0',
                bitrate=250000,
                sudo_password='test_password'
            )
        
        logger.info("✅ 接口配置失败流程测试通过")
    
    @patch('sys.platform', 'win32')
    def test_non_linux_platform_flow(
        self, 
        can_config_with_auto_configure, 
        mock_decision_layer, 
        mock_event_bus
    ):
        """
        测试非Linux平台流程
        
        验证需求：
        - 需求 1.2: CAN接口自动配置（平台检查）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 非Linux平台流程")
        logger.info("=" * 60)
        
        # 创建CAN通信器
        communicator = CANCommunicator(
            config=can_config_with_auto_configure,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 启动通信器（应该跳过接口配置）
        with patch('can.Bus') as mock_bus_class:
            mock_bus = Mock()
            mock_bus_class.return_value = mock_bus
            
            with patch('can.Notifier') as mock_notifier_class:
                mock_notifier = Mock()
                mock_notifier_class.return_value = mock_notifier
                
                result = communicator.start()
                
                # 验证启动成功（跳过了接口配置）
                assert result is True, "非Linux平台启动应该成功（跳过接口配置）"
                
                # 验证创建了CAN总线
                mock_bus_class.assert_called_once()
        
        logger.info("✅ 非Linux平台流程测试通过")


# ==================== 主测试函数 ====================

def run_can_integration_linux_tests():
    """运行CAN通信模块Linux环境集成测试（用于手动执行）"""
    logger.info("\n" + "=" * 80)
    logger.info("CAN通信模块Linux环境集成测试")
    logger.info("=" * 80)
    
    logger.info("注意：此测试专为Linux环境设计")
    logger.info("需要socketCAN支持（真实CAN或虚拟CAN）")
    logger.info("")
    logger.info("运行前准备（Linux系统）:")
    logger.info("1. 安装python-can: pip install python-can")
    logger.info("2. 创建虚拟CAN接口: sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0")
    logger.info("3. 或使用真实CAN接口（需要硬件支持）")
    logger.info("")
    logger.info("运行命令:")
    logger.info("pytest oak_vision_system/tests/integration/can_communication/test_can_integration_linux.py -v")


if __name__ == "__main__":
    run_can_integration_linux_tests()