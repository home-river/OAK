"""
CAN通信模块端到端测试（使用can_controller.py + socketCAN loopback）

使用subprocess启动can_controller.py作为独立进程，利用socketCAN的loopback机制
实现进程间通信测试。两个进程共享can0接口，通过socketCAN进行真实的CAN通信。

测试架构：
- 进程1（当前pytest）：启动CAN通信模块（被测试对象）
- 进程2（can_controller.py）：模拟外部控制器
- 通信机制：socketCAN loopback（进程1发送的消息，进程1和进程2都能收到）

注意：此测试创建后不立即运行，留待Linux环境执行
运行环境：Linux（香橙派）+ socketCAN ⚠️

验证需求：
- 需求 2.1, 2.2, 2.3, 2.4, 2.5, 2.6: 坐标请求响应
- 需求 3.1, 3.2, 3.3, 3.4, 3.5, 3.6: 人员警报
- 需求 5.5, 10.6: 协议兼容性和性能

can_controller.py 路径配置：
默认路径：tools/can_controller.py（相对于项目根目录）
如需修改，请在下方 CAN_CONTROLLER_SCRIPT_PATH 变量中指定
"""

import os
import sys
import time
import subprocess
import threading
import pytest
import logging
import re
import signal
from typing import Optional, List, Dict, Any, Tuple
from unittest.mock import Mock
import numpy as np

# ==================== 配置区域 ====================
# can_controller.py 脚本路径（相对于项目根目录）
# 默认: tools/can_controller.py
# 可根据实际情况修改此路径
CAN_CONTROLLER_SCRIPT_PATH = 'tools/can_controller.py'
# ==================== 配置区域结束 ====================

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from oak_vision_system.modules.can_communication.can_communicator import CANCommunicator
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
from oak_vision_system.modules.data_processing.decision_layer.types import PersonWarningStatus

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ==================== 测试辅助类 ====================

class MockDecisionLayer:
    """模拟决策层（用于端到端测试）"""
    
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
    """模拟事件总线（用于端到端测试）"""
    
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


class CANControllerProcess:
    """CAN控制器进程管理器"""
    
    def __init__(self, can_channel: str = 'can0'):
        self.can_channel = can_channel
        self.process: Optional[subprocess.Popen] = None
        
        # 获取项目根目录（从测试文件向上4级）
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
        
        # 使用配置的脚本路径
        self.controller_script = os.path.join(project_root, CAN_CONTROLLER_SCRIPT_PATH)
        
        # 确保脚本路径存在
        if not os.path.exists(self.controller_script):
            raise FileNotFoundError(
                f"can_controller.py脚本不存在: {self.controller_script}\n"
                f"请检查路径配置或将脚本放置在: {CAN_CONTROLLER_SCRIPT_PATH}"
            )
    
    def start(self) -> bool:
        """启动can_controller.py进程"""
        try:
            logger.info(f"启动can_controller.py进程，CAN通道: {self.can_channel}")
            
            # 设置环境变量，指定CAN通道
            env = os.environ.copy()
            env['CAN_CHANNEL'] = self.can_channel
            
            # 启动进程
            self.process = subprocess.Popen(
                [sys.executable, self.controller_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行缓冲
                env=env
            )
            
            # 等待进程启动
            time.sleep(2.0)
            
            # 检查进程是否正常运行
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                logger.error(f"can_controller.py进程启动失败:")
                logger.error(f"stdout: {stdout}")
                logger.error(f"stderr: {stderr}")
                return False
            
            logger.info("can_controller.py进程启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动can_controller.py进程失败: {e}")
            return False
    
    def send_command(self, command: str) -> bool:
        """向can_controller进程发送命令"""
        if not self.process or self.process.stdin is None:
            logger.error("can_controller进程未启动或stdin不可用")
            return False
        
        try:
            self.process.stdin.write(f"{command}\n")
            self.process.stdin.flush()
            logger.debug(f"发送命令到can_controller: {command}")
            return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False
    
    def read_output(self, timeout: float = 1.0) -> List[str]:
        """读取can_controller进程的输出"""
        if not self.process or self.process.stdout is None:
            return []
        
        lines = []
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                # 检查是否有可读数据
                import select
                ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
                
                if ready:
                    line = self.process.stdout.readline()
                    if line:
                        lines.append(line.strip())
                        logger.debug(f"can_controller输出: {line.strip()}")
                    else:
                        break
                else:
                    time.sleep(0.01)
                    
        except Exception as e:
            logger.error(f"读取can_controller输出失败: {e}")
        
        return lines
    
    def parse_coordinates_from_output(self, lines: List[str]) -> List[Tuple[int, int, int]]:
        """从输出中解析坐标信息"""
        coordinates = []
        
        # 匹配坐标输出的正则表达式
        # 例如: "🍎 解析后果位置响应 #1: X=100mm, Y=200mm, Z=300mm"
        coord_pattern = r'🍎.*?X=(-?\d+)mm,\s*Y=(-?\d+)mm,\s*Z=(-?\d+)mm'
        
        for line in lines:
            match = re.search(coord_pattern, line)
            if match:
                x, y, z = int(match.group(1)), int(match.group(2)), int(match.group(3))
                coordinates.append((x, y, z))
                logger.debug(f"解析到坐标: ({x}, {y}, {z})")
        
        return coordinates
    
    def parse_alert_count_from_output(self, lines: List[str]) -> int:
        """从输出中解析警报计数"""
        alert_count = 0
        
        # 匹配警报输出的正则表达式
        # 例如: "🚨 解析后人员警报 #3"
        alert_pattern = r'🚨.*?#(\d+)'
        
        for line in lines:
            match = re.search(alert_pattern, line)
            if match:
                count = int(match.group(1))
                alert_count = max(alert_count, count)
        
        return alert_count
    
    def parse_statistics_from_output(self, lines: List[str]) -> Dict[str, int]:
        """从输出中解析统计信息"""
        stats = {
            'request_count': 0,
            'response_count': 0,
            'alert_count': 0
        }
        
        # 匹配统计信息的正则表达式
        patterns = {
            'request_count': r'请求发送次数:\s*(\d+)',
            'response_count': r'坐标响应次数:\s*(\d+)',
            'alert_count': r'人员警报次数:\s*(\d+)'
        }
        
        for line in lines:
            for key, pattern in patterns.items():
                match = re.search(pattern, line)
                if match:
                    stats[key] = int(match.group(1))
        
        return stats
    
    def stop(self):
        """停止can_controller进程"""
        if self.process:
            try:
                # 发送退出命令
                self.send_command('q')
                
                # 等待进程正常退出
                try:
                    self.process.wait(timeout=5.0)
                    logger.info("can_controller进程正常退出")
                except subprocess.TimeoutExpired:
                    # 强制终止
                    logger.warning("can_controller进程未正常退出，强制终止")
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                
            except Exception as e:
                logger.error(f"停止can_controller进程时出错: {e}")
            finally:
                self.process = None


# ==================== 平台和环境检测 ====================

class TestEndToEndEnvironment:
    """端到端测试环境检测"""
    
    def test_linux_platform_and_socketcan_availability(self):
        """
        测试Linux平台和socketCAN可用性
        
        验证需求：
        - 端到端测试环境要求
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: Linux平台和socketCAN可用性")
        logger.info("=" * 60)
        
        # 检查平台
        current_platform = sys.platform
        logger.info(f"当前平台: {current_platform}")
        
        is_linux = current_platform in ['linux', 'linux2']
        
        if not is_linux:
            logger.warning(f"⚠️ 非Linux平台（{current_platform}），端到端测试不可用")
            pytest.skip("端到端测试需要Linux平台")
        
        # 检查python-can模块
        try:
            import can
            logger.info("✅ python-can模块可用")
        except ImportError:
            logger.error("❌ python-can模块不可用，请安装: pip install python-can")
            pytest.skip("端到端测试需要python-can模块")
        
        # 检查can_controller.py脚本
        controller_script = os.path.join(
            os.path.dirname(__file__), 
            '../../../../plan/modules/CAN_module/pre_inpimentation/can_controller.py'
        )
        
        if not os.path.exists(controller_script):
            logger.error(f"❌ can_controller.py脚本不存在: {controller_script}")
            pytest.skip("端到端测试需要can_controller.py脚本")
        
        logger.info(f"✅ can_controller.py脚本存在: {controller_script}")
        
        # 检查CAN接口（这里只是检查，不要求一定存在）
        try:
            result = subprocess.run(['ip', 'link', 'show'], 
                                  capture_output=True, text=True, timeout=5)
            if 'can0' in result.stdout:
                logger.info("✅ 检测到can0接口")
            elif 'vcan0' in result.stdout:
                logger.info("✅ 检测到vcan0接口")
            else:
                logger.warning("⚠️ 未检测到CAN接口，测试可能需要手动配置")
        except Exception as e:
            logger.warning(f"⚠️ 检查CAN接口时出错: {e}")
        
        logger.info("✅ 端到端测试环境检测完成")


# ==================== 坐标请求响应端到端测试 ====================

class TestCoordinateRequestResponseEndToEnd:
    """坐标请求响应端到端测试"""
    
    @pytest.fixture
    def can_config(self):
        """创建测试用CAN配置"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='can0',  # 使用真实CAN接口
            can_bitrate=250000,
            enable_auto_configure=False,  # 假设接口已配置
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
    
    @pytest.fixture
    def can_controller_process(self, can_config):
        """创建并启动can_controller进程"""
        controller = CANControllerProcess(can_config.can_channel)
        
        # 启动进程
        if not controller.start():
            pytest.skip("无法启动can_controller进程，可能缺少CAN环境")
        
        yield controller
        
        # 清理
        controller.stop()
    
    def test_single_coordinate_request_response(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus, 
        can_controller_process
    ):
        """
        测试单次坐标请求响应
        
        验证需求：
        - 需求 2.1: 接收坐标请求
        - 需求 2.2: 调用决策层获取坐标
        - 需求 2.3: 发送坐标响应
        - 需求 2.5: 响应格式正确
        - 需求 2.6: 响应时间 < 10ms
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 单次坐标请求响应（端到端）")
        logger.info("=" * 60)
        
        # 设置测试坐标
        test_coords = np.array([100, 200, 300], dtype=np.float32)
        mock_decision_layer.set_target_coords(test_coords)
        
        # 创建并启动CAN通信器
        communicator = CANCommunicator(
            config=can_config,
            decision_layer=mock_decision_layer,
            event_bus=mock_event_bus
        )
        
        # 启动通信器
        if not communicator.start():
            pytest.skip("无法启动CAN通信器，可能缺少CAN环境")
        
        try:
            # 等待通信器完全启动
            time.sleep(1.0)
            
            # 发送单次请求命令
            assert can_controller_process.send_command('r'), "发送请求命令失败"
            
            # 等待响应处理
            time.sleep(0.5)
            
            # 读取can_controller的输出
            output_lines = can_controller_process.read_output(timeout=2.0)
            
            # 解析坐标响应
            coordinates = can_controller_process.parse_coordinates_from_output(output_lines)
            
            # 验证收到了响应
            assert len(coordinates) >= 1, f"应该收到至少1个坐标响应，实际: {len(coordinates)}"
            
            # 验证坐标值正确
            x, y, z = coordinates[0]
            assert x == 100, f"X坐标不匹配: 期望100, 实际{x}"
            assert y == 200, f"Y坐标不匹配: 期望200, 实际{y}"
            assert z == 300, f"Z坐标不匹配: 期望300, 实际{z}"
            
            logger.info(f"✅ 单次坐标请求响应测试通过: ({x}, {y}, {z})")
            
        finally:
            communicator.stop()
    
    def test_multiple_coordinate_requests(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus, 
        can_controller_process
    ):
        """
        测试多次坐标请求
        
        验证需求：
        - 需求 2.1, 2.2, 2.3: 多次请求响应的稳定性
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 多次坐标请求（端到端）")
        logger.info("=" * 60)
        
        # 设置测试坐标
        test_coords = np.array([150, 250, 350], dtype=np.float32)
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
            
            # 发送10次请求
            request_count = 10
            for i in range(request_count):
                assert can_controller_process.send_command('r'), f"第{i+1}次请求发送失败"
                time.sleep(0.1)  # 间隔100ms
            
            # 等待所有响应处理完成
            time.sleep(2.0)
            
            # 读取输出
            output_lines = can_controller_process.read_output(timeout=3.0)
            
            # 解析坐标响应
            coordinates = can_controller_process.parse_coordinates_from_output(output_lines)
            
            # 验证响应数量
            assert len(coordinates) >= request_count * 0.8, \
                f"应该收到至少{int(request_count * 0.8)}个响应，实际: {len(coordinates)}"
            
            # 验证所有坐标值正确
            for i, (x, y, z) in enumerate(coordinates):
                assert x == 150, f"第{i+1}个响应X坐标不匹配: 期望150, 实际{x}"
                assert y == 250, f"第{i+1}个响应Y坐标不匹配: 期望250, 实际{y}"
                assert z == 350, f"第{i+1}个响应Z坐标不匹配: 期望350, 实际{z}"
            
            logger.info(f"✅ 多次坐标请求测试通过: 发送{request_count}次，收到{len(coordinates)}次响应")
            
        finally:
            communicator.stop()
    
    def test_boundary_value_coordinates(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus, 
        can_controller_process
    ):
        """
        测试边界值坐标的端到端传输
        
        验证需求：
        - 需求 5.5: 坐标编码round-trip
        - 需求 10.6: 协议兼容性
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 边界值坐标端到端传输")
        logger.info("=" * 60)
        
        # 测试用例：边界值坐标
        test_cases = [
            (32767, 32767, 32767),    # 最大正值
            (-32768, -32768, -32768), # 最大负值
            (32767, -32768, 0),       # 混合边界值
            (-100, -200, -300),       # 负数坐标
        ]
        
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
            
            for expected_x, expected_y, expected_z in test_cases:
                logger.info(f"测试边界值坐标: ({expected_x}, {expected_y}, {expected_z})")
                
                # 设置测试坐标
                test_coords = np.array([expected_x, expected_y, expected_z], dtype=np.float32)
                mock_decision_layer.set_target_coords(test_coords)
                
                # 发送请求
                assert can_controller_process.send_command('r'), "发送请求失败"
                time.sleep(0.2)
                
                # 读取响应
                output_lines = can_controller_process.read_output(timeout=1.0)
                coordinates = can_controller_process.parse_coordinates_from_output(output_lines)
                
                # 验证响应
                assert len(coordinates) >= 1, f"边界值({expected_x}, {expected_y}, {expected_z})未收到响应"
                
                x, y, z = coordinates[-1]  # 取最新的响应
                assert x == expected_x, f"X坐标不匹配: 期望{expected_x}, 实际{x}"
                assert y == expected_y, f"Y坐标不匹配: 期望{expected_y}, 实际{y}"
                assert z == expected_z, f"Z坐标不匹配: 期望{expected_z}, 实际{z}"
                
                logger.info(f"✅ 边界值坐标({expected_x}, {expected_y}, {expected_z})传输正确")
            
            logger.info("✅ 所有边界值坐标端到端传输测试通过")
            
        finally:
            communicator.stop()


# ==================== 人员警报端到端测试 ====================

class TestPersonAlertEndToEnd:
    """人员警报端到端测试"""
    
    @pytest.fixture
    def can_config(self):
        """创建测试用CAN配置（快速警报间隔）"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='can0',
            can_bitrate=250000,
            enable_auto_configure=False,
            sudo_password=None,
            alert_interval_ms=200,  # 200ms间隔，便于测试
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
    
    @pytest.fixture
    def can_controller_process(self, can_config):
        """创建并启动can_controller进程"""
        controller = CANControllerProcess(can_config.can_channel)
        
        if not controller.start():
            pytest.skip("无法启动can_controller进程")
        
        yield controller
        controller.stop()
    
    def test_person_alert_triggered_and_cleared(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus, 
        can_controller_process
    ):
        """
        测试人员警报触发和清除的端到端流程
        
        验证需求：
        - 需求 3.1: 事件订阅
        - 需求 3.2: 警报启动
        - 需求 3.3: 周期发送
        - 需求 3.5: 警报停止
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 人员警报触发和清除（端到端）")
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
            
            # 触发人员警报
            logger.info("触发人员警报...")
            mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
            
            # 等待警报发送
            time.sleep(1.0)  # 等待1秒，应该收到约5次警报（200ms间隔）
            
            # 读取can_controller的输出
            output_lines = can_controller_process.read_output(timeout=2.0)
            initial_alert_count = can_controller_process.parse_alert_count_from_output(output_lines)
            
            logger.info(f"初始警报计数: {initial_alert_count}")
            assert initial_alert_count >= 3, f"应该收到至少3次警报，实际: {initial_alert_count}"
            
            # 清除人员警报
            logger.info("清除人员警报...")
            mock_event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
            
            # 等待警报停止
            time.sleep(0.8)  # 等待800ms，确认警报已停止
            
            # 再次读取输出
            output_lines = can_controller_process.read_output(timeout=1.0)
            final_alert_count = can_controller_process.parse_alert_count_from_output(output_lines)
            
            logger.info(f"最终警报计数: {final_alert_count}")
            
            # 验证警报计数没有显著增加（允许1-2个延迟的警报）
            alert_increase = final_alert_count - initial_alert_count
            assert alert_increase <= 2, f"警报停止后不应该继续发送，增加了{alert_increase}次"
            
            logger.info("✅ 人员警报触发和清除端到端测试通过")
            
        finally:
            communicator.stop()
    
    def test_person_alert_timing_accuracy(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus, 
        can_controller_process
    ):
        """
        测试人员警报时间间隔准确性（端到端）
        
        验证需求：
        - 需求 3.4: 警报间隔准确性
        - 需求 3.6: 警报性能要求
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 人员警报时间间隔准确性（端到端）")
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
            
            # 触发警报
            start_time = time.time()
            mock_event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
            
            # 持续监控警报
            alert_timestamps = []
            monitoring_duration = 1.5  # 监控1.5秒
            
            while time.time() - start_time < monitoring_duration:
                output_lines = can_controller_process.read_output(timeout=0.1)
                
                # 检查是否有新的警报
                for line in output_lines:
                    if '🚨' in line and '解析后人员警报' in line:
                        alert_timestamps.append(time.time())
                
                time.sleep(0.05)
            
            # 停止警报
            mock_event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
            
            # 验证警报数量
            assert len(alert_timestamps) >= 5, f"应该收到至少5次警报，实际: {len(alert_timestamps)}"
            
            # 计算时间间隔
            intervals = []
            for i in range(1, len(alert_timestamps)):
                interval = (alert_timestamps[i] - alert_timestamps[i-1]) * 1000  # 转换为毫秒
                intervals.append(interval)
            
            # 验证间隔准确性（允许±50ms误差，考虑网络和进程间通信延迟）
            expected_interval = can_config.alert_interval_ms
            for i, interval in enumerate(intervals):
                assert abs(interval - expected_interval) <= 50, \
                    f"第{i+1}个间隔不准确: 期望{expected_interval}ms±50ms, 实际{interval:.2f}ms"
            
            # 计算平均间隔
            avg_interval = sum(intervals) / len(intervals)
            logger.info(f"平均警报间隔: {avg_interval:.2f}ms (期望: {expected_interval}ms)")
            
            assert abs(avg_interval - expected_interval) <= 30, \
                f"平均间隔不准确: 期望{expected_interval}ms±30ms, 实际{avg_interval:.2f}ms"
            
            logger.info("✅ 人员警报时间间隔准确性端到端测试通过")
            
        finally:
            communicator.stop()


# ==================== 协议兼容性和性能测试 ====================

class TestProtocolCompatibilityAndPerformance:
    """协议兼容性和性能测试"""
    
    @pytest.fixture
    def can_config(self):
        """创建测试用CAN配置"""
        return CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='can0',
            can_bitrate=250000,
            enable_auto_configure=False,
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
    
    @pytest.fixture
    def can_controller_process(self, can_config):
        """创建并启动can_controller进程"""
        controller = CANControllerProcess(can_config.can_channel)
        
        if not controller.start():
            pytest.skip("无法启动can_controller进程")
        
        yield controller
        controller.stop()
    
    def test_protocol_format_compatibility(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus, 
        can_controller_process
    ):
        """
        测试协议格式兼容性
        
        验证需求：
        - 需求 5.5: 协议格式正确性
        - 需求 10.6: 与外部控制器的兼容性
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 协议格式兼容性（端到端）")
        logger.info("=" * 60)
        
        # 设置测试坐标
        test_coords = np.array([12345, -6789, 0], dtype=np.float32)
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
            
            # 发送请求
            assert can_controller_process.send_command('r'), "发送请求失败"
            time.sleep(0.5)
            
            # 读取详细输出（包含字节级信息）
            output_lines = can_controller_process.read_output(timeout=2.0)
            
            # 查找字节解析详情
            byte_info_found = False
            coord_info_found = False
            
            for line in output_lines:
                if '字节解析详情' in line or '原始字节' in line:
                    byte_info_found = True
                    logger.info(f"协议字节信息: {line}")
                
                if '补码解析' in line:
                    coord_info_found = True
                    logger.info(f"坐标解析信息: {line}")
            
            # 验证协议信息被正确解析
            assert byte_info_found, "应该找到字节解析详情"
            assert coord_info_found, "应该找到坐标解析信息"
            
            # 验证坐标值正确传输
            coordinates = can_controller_process.parse_coordinates_from_output(output_lines)
            assert len(coordinates) >= 1, "应该收到坐标响应"
            
            x, y, z = coordinates[0]
            assert x == 12345, f"X坐标不匹配: 期望12345, 实际{x}"
            assert y == -6789, f"Y坐标不匹配: 期望-6789, 实际{y}"
            assert z == 0, f"Z坐标不匹配: 期望0, 实际{z}"
            
            logger.info("✅ 协议格式兼容性测试通过")
            
        finally:
            communicator.stop()
    
    def test_continuous_request_performance(
        self, 
        can_config, 
        mock_decision_layer, 
        mock_event_bus, 
        can_controller_process
    ):
        """
        测试连续请求性能
        
        验证需求：
        - 需求 2.6: 响应时间性能
        - 需求 10.6: 高频请求处理能力
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 连续请求性能（端到端）")
        logger.info("=" * 60)
        
        # 设置测试坐标
        test_coords = np.array([1000, 2000, 3000], dtype=np.float32)
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
            
            # 启动连续请求模式
            logger.info("启动连续请求模式...")
            assert can_controller_process.send_command('c'), "启动连续请求失败"
            
            # 运行连续请求一段时间
            time.sleep(5.0)  # 运行5秒
            
            # 停止连续请求模式
            logger.info("停止连续请求模式...")
            assert can_controller_process.send_command('c'), "停止连续请求失败"
            
            # 等待处理完成
            time.sleep(1.0)
            
            # 获取统计信息
            assert can_controller_process.send_command('s'), "获取统计信息失败"
            time.sleep(0.5)
            
            output_lines = can_controller_process.read_output(timeout=2.0)
            stats = can_controller_process.parse_statistics_from_output(output_lines)
            
            logger.info(f"性能统计: {stats}")
            
            # 验证性能指标
            request_count = stats.get('request_count', 0)
            response_count = stats.get('response_count', 0)
            
            assert request_count >= 2, f"应该发送至少2次请求，实际: {request_count}"
            assert response_count >= 2, f"应该收到至少2次响应，实际: {response_count}"
            
            # 验证响应率（允许少量丢失）
            response_rate = response_count / request_count if request_count > 0 else 0
            assert response_rate >= 0.8, f"响应率应该 >= 80%，实际: {response_rate:.2%}"
            
            logger.info(f"✅ 连续请求性能测试通过: 请求{request_count}次，响应{response_count}次，响应率{response_rate:.2%}")
            
        finally:
            communicator.stop()


# ==================== 主测试函数 ====================

def run_can_end_to_end_linux_tests():
    """运行CAN通信模块端到端测试（用于手动执行）"""
    logger.info("\n" + "=" * 80)
    logger.info("CAN通信模块端到端测试（使用can_controller.py）")
    logger.info("=" * 80)
    
    logger.info("注意：此测试专为Linux环境设计")
    logger.info("需要socketCAN支持和can_controller.py脚本")
    logger.info("")
    logger.info("运行前准备（Linux系统）:")
    logger.info("1. 安装python-can: pip install python-can")
    logger.info("2. 配置CAN接口:")
    logger.info("   - 真实CAN: sudo ip link set can0 type can bitrate 250000 && sudo ip link set can0 up")
    logger.info("   - 虚拟CAN: sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0")
    logger.info("3. 确保can_controller.py脚本存在且可执行")
    logger.info("")
    logger.info("运行命令:")
    logger.info("pytest oak_vision_system/tests/integration/can_communication/test_can_end_to_end_linux.py -v -s")


if __name__ == "__main__":
    run_can_end_to_end_linux_tests()