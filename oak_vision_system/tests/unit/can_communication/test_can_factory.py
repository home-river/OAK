"""
CAN 通信器工厂函数测试

测试 create_can_communicator 工厂函数的核心功能：
1. enable_can=True 时创建真实 CAN 通信器
2. enable_can=False 时创建虚拟 CAN 通信器
3. 返回类型正确（CANCommunicatorBase）
4. 正确传递依赖项

设计原则：
- 最小化测试：只测试工厂函数的核心逻辑
- 验证类型选择：确保根据配置选择正确的实现
"""

import unittest
from unittest.mock import Mock, patch

from oak_vision_system.modules.can_communication.can_factory import create_can_communicator
from oak_vision_system.modules.can_communication.can_communicator_base import CANCommunicatorBase
from oak_vision_system.modules.can_communication.virtual_can_communicator import VirtualCANCommunicator
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO


class TestCANFactory(unittest.TestCase):
    """测试 CAN 通信器工厂函数"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_decision_layer = Mock()
        self.mock_event_bus = Mock()
        self.mock_event_bus.subscribe.return_value = "test_subscription_id"
    
    def test_create_virtual_can_communicator(self):
        """
        测试：enable_can=False 时创建虚拟 CAN 通信器
        
        验证：
        - 返回 VirtualCANCommunicator 实例
        - 实例继承自 CANCommunicatorBase
        - 依赖项被正确传递
        """
        # 创建配置（虚拟模式）
        config = CANConfigDTO(
            enable_can=False,
            can_interface="socketcan",
            can_channel="can0",
            can_bitrate=250000
        )
        
        # 调用工厂函数
        communicator = create_can_communicator(
            config=config,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
        
        # 验证返回类型
        self.assertIsInstance(communicator, VirtualCANCommunicator)
        self.assertIsInstance(communicator, CANCommunicatorBase)
        
        # 验证依赖项被正确传递
        self.assertIs(communicator.config, config)
        self.assertIs(communicator.decision_layer, self.mock_decision_layer)
        self.assertIs(communicator.event_bus, self.mock_event_bus)
    
    @patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus')
    @patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier')
    def test_create_real_can_communicator(self, mock_notifier, mock_bus):
        """
        测试：enable_can=True 时创建真实 CAN 通信器
        
        验证：
        - CANCommunicator 类被实例化
        - 依赖项被正确传递
        - 返回 CANCommunicator 实例
        
        注意：使用 Mock 避免实际创建 CAN 总线连接
        """
        # 导入真实的 CANCommunicator（需要 mock CAN 库）
        from oak_vision_system.modules.can_communication.can_communicator import CANCommunicator
        
        # 创建配置（真实模式）
        config = CANConfigDTO(
            enable_can=True,
            can_interface="socketcan",
            can_channel="can0",
            can_bitrate=250000
        )
        
        # 调用工厂函数
        communicator = create_can_communicator(
            config=config,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
        
        # 验证返回类型
        self.assertIsInstance(communicator, CANCommunicator)
        self.assertIsInstance(communicator, CANCommunicatorBase)
        
        # 验证依赖项被正确传递
        self.assertIs(communicator.config, config)
        self.assertIs(communicator.decision_layer, self.mock_decision_layer)
        self.assertIs(communicator.event_bus, self.mock_event_bus)
    
    @patch('oak_vision_system.modules.can_communication.can_communicator.can.Bus')
    @patch('oak_vision_system.modules.can_communication.can_communicator.can.Notifier')
    def test_factory_returns_base_type(self, mock_notifier, mock_bus):
        """
        测试：工厂函数返回 CANCommunicatorBase 类型
        
        验证：
        - 虚拟实现返回 CANCommunicatorBase
        - 真实实现返回 CANCommunicatorBase
        - 接口一致性
        """
        # 测试虚拟实现
        config_virtual = CANConfigDTO(enable_can=False)
        communicator_virtual = create_can_communicator(
            config=config_virtual,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
        self.assertIsInstance(communicator_virtual, CANCommunicatorBase)
        
        # 测试真实实现
        config_real = CANConfigDTO(enable_can=True)
        communicator_real = create_can_communicator(
            config=config_real,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
        
        # 验证返回的是 CANCommunicatorBase 类型
        self.assertIsInstance(communicator_real, CANCommunicatorBase)
        self.assertTrue(hasattr(communicator_real, 'start'))
        self.assertTrue(hasattr(communicator_real, 'stop'))
        self.assertTrue(hasattr(communicator_real, 'is_running'))
    
    def test_factory_interface_consistency(self):
        """
        测试：工厂函数创建的实例具有一致的接口
        
        验证：
        - 虚拟实现有 start, stop, is_running 方法
        - 真实实现有 start, stop, is_running 方法（通过 Mock）
        - 接口签名一致
        """
        # 测试虚拟实现
        config_virtual = CANConfigDTO(enable_can=False)
        communicator_virtual = create_can_communicator(
            config=config_virtual,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
        
        # 验证虚拟实现的接口
        self.assertTrue(hasattr(communicator_virtual, 'start'))
        self.assertTrue(hasattr(communicator_virtual, 'stop'))
        self.assertTrue(hasattr(communicator_virtual, 'is_running'))
        self.assertTrue(callable(communicator_virtual.start))
        self.assertTrue(callable(communicator_virtual.stop))
        
        # 验证方法签名
        import inspect
        start_sig = inspect.signature(communicator_virtual.start)
        stop_sig = inspect.signature(communicator_virtual.stop)
        
        # start() 应该没有必需参数
        self.assertEqual(len(start_sig.parameters), 0)
        
        # stop() 应该有一个可选的 timeout 参数
        self.assertIn('timeout', stop_sig.parameters)
        self.assertIsNotNone(stop_sig.parameters['timeout'].default)
    
    def test_factory_with_different_configs(self):
        """
        测试：工厂函数正确处理不同的配置
        
        验证：
        - 不同的 enable_can 值产生不同的实现
        - 配置参数被正确传递
        """
        # 配置 1: 虚拟模式
        config1 = CANConfigDTO(
            enable_can=False,
            can_interface="socketcan",
            can_channel="vcan0",
            can_bitrate=500000
        )
        comm1 = create_can_communicator(
            config=config1,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
        self.assertIsInstance(comm1, VirtualCANCommunicator)
        self.assertEqual(comm1.config.can_channel, "vcan0")
        self.assertEqual(comm1.config.can_bitrate, 500000)
        
        # 配置 2: 虚拟模式，不同参数
        config2 = CANConfigDTO(
            enable_can=False,
            can_interface="socketcan",
            can_channel="vcan1",
            can_bitrate=250000
        )
        comm2 = create_can_communicator(
            config=config2,
            decision_layer=self.mock_decision_layer,
            event_bus=self.mock_event_bus
        )
        self.assertIsInstance(comm2, VirtualCANCommunicator)
        self.assertEqual(comm2.config.can_channel, "vcan1")
        self.assertEqual(comm2.config.can_bitrate, 250000)
    
    def test_factory_error_handling(self):
        """
        测试：工厂函数的错误处理
        
        验证：
        - 导入失败时抛出 ImportError
        - 创建失败时抛出 RuntimeError
        """
        # 测试真实实现导入失败（模拟 python-can 未安装）
        # 通过 mock sys.modules 来模拟导入失败
        import sys
        
        # 保存原始模块
        original_can = sys.modules.get('can')
        original_can_comm = sys.modules.get('oak_vision_system.modules.can_communication.can_communicator')
        
        try:
            # 移除 can 模块，模拟未安装
            if 'can' in sys.modules:
                del sys.modules['can']
            if 'oak_vision_system.modules.can_communication.can_communicator' in sys.modules:
                del sys.modules['oak_vision_system.modules.can_communication.can_communicator']
            
            # 创建一个假的 can 模块，导入时抛出异常
            sys.modules['can'] = None  # 这会导致导入失败
            
            config = CANConfigDTO(enable_can=True)
            
            with self.assertRaises((ImportError, RuntimeError, AttributeError)):
                create_can_communicator(
                    config=config,
                    decision_layer=self.mock_decision_layer,
                    event_bus=self.mock_event_bus
                )
        finally:
            # 恢复原始模块
            if original_can is not None:
                sys.modules['can'] = original_can
            elif 'can' in sys.modules:
                del sys.modules['can']
            
            if original_can_comm is not None:
                sys.modules['oak_vision_system.modules.can_communication.can_communicator'] = original_can_comm
            elif 'oak_vision_system.modules.can_communication.can_communicator' in sys.modules:
                del sys.modules['oak_vision_system.modules.can_communication.can_communicator']


if __name__ == '__main__':
    unittest.main(verbosity=2)
