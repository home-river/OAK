"""
CAN 通信器抽象基类测试

测试 CANCommunicatorBase 抽象基类的核心功能：
1. 不能直接实例化抽象类
2. 子类必须实现所有抽象方法
3. 基类正确初始化依赖项

设计原则：
- 最小化测试：只测试抽象类的核心约束
- 验证接口契约：确保子类必须实现所有抽象方法
"""

import unittest
from unittest.mock import Mock
from abc import ABC

from oak_vision_system.modules.can_communication.can_communicator_base import CANCommunicatorBase
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO


class TestCANCommunicatorBaseAbstraction(unittest.TestCase):
    """测试抽象基类的抽象性"""
    
    def test_cannot_instantiate_abstract_class(self):
        """
        测试：不能直接实例化抽象类
        
        验证：
        - 尝试实例化 CANCommunicatorBase 会抛出 TypeError
        - 错误信息提示缺少抽象方法实现
        """
        # 创建测试配置和依赖
        config = CANConfigDTO(enable_can=False)
        mock_decision_layer = Mock()
        mock_event_bus = Mock()
        
        # 尝试实例化抽象类应该失败
        with self.assertRaises(TypeError) as context:
            CANCommunicatorBase(config, mock_decision_layer, mock_event_bus)
        
        # 验证错误信息提到抽象方法
        error_msg = str(context.exception)
        self.assertIn("abstract", error_msg.lower())
    
    def test_subclass_must_implement_start(self):
        """
        测试：子类必须实现 start() 方法
        
        验证：
        - 未实现 start() 的子类无法实例化
        """
        # 创建一个不完整的子类（缺少 start 方法）
        class IncompleteSubclass(CANCommunicatorBase):
            def stop(self, timeout: float = 5.0) -> bool:
                return True
            
            @property
            def is_running(self) -> bool:
                return False
        
        config = CANConfigDTO(enable_can=False)
        mock_decision_layer = Mock()
        mock_event_bus = Mock()
        
        # 尝试实例化应该失败
        with self.assertRaises(TypeError) as context:
            IncompleteSubclass(config, mock_decision_layer, mock_event_bus)
        
        # 验证错误信息提到 start 方法
        error_msg = str(context.exception)
        self.assertIn("start", error_msg.lower())
    
    def test_subclass_must_implement_stop(self):
        """
        测试：子类必须实现 stop() 方法
        
        验证：
        - 未实现 stop() 的子类无法实例化
        """
        # 创建一个不完整的子类（缺少 stop 方法）
        class IncompleteSubclass(CANCommunicatorBase):
            def start(self) -> bool:
                return True
            
            @property
            def is_running(self) -> bool:
                return False
        
        config = CANConfigDTO(enable_can=False)
        mock_decision_layer = Mock()
        mock_event_bus = Mock()
        
        # 尝试实例化应该失败
        with self.assertRaises(TypeError) as context:
            IncompleteSubclass(config, mock_decision_layer, mock_event_bus)
        
        # 验证错误信息提到 stop 方法
        error_msg = str(context.exception)
        self.assertIn("stop", error_msg.lower())
    
    def test_subclass_must_implement_is_running(self):
        """
        测试：子类必须实现 is_running 属性
        
        验证：
        - 未实现 is_running 的子类无法实例化
        """
        # 创建一个不完整的子类（缺少 is_running 属性）
        class IncompleteSubclass(CANCommunicatorBase):
            def start(self) -> bool:
                return True
            
            def stop(self, timeout: float = 5.0) -> bool:
                return True
        
        config = CANConfigDTO(enable_can=False)
        mock_decision_layer = Mock()
        mock_event_bus = Mock()
        
        # 尝试实例化应该失败
        with self.assertRaises(TypeError) as context:
            IncompleteSubclass(config, mock_decision_layer, mock_event_bus)
        
        # 验证错误信息提到 is_running
        error_msg = str(context.exception)
        self.assertIn("is_running", error_msg.lower())
    
    def test_complete_subclass_can_be_instantiated(self):
        """
        测试：实现所有抽象方法的子类可以被实例化
        
        验证：
        - 完整实现的子类可以正常实例化
        - 基类初始化正确保存依赖项
        """
        # 创建一个完整的子类
        class CompleteSubclass(CANCommunicatorBase):
            def start(self) -> bool:
                return True
            
            def stop(self, timeout: float = 5.0) -> bool:
                return True
            
            @property
            def is_running(self) -> bool:
                return False
        
        config = CANConfigDTO(enable_can=False)
        mock_decision_layer = Mock()
        mock_event_bus = Mock()
        
        # 应该可以成功实例化
        instance = CompleteSubclass(config, mock_decision_layer, mock_event_bus)
        
        # 验证基类正确保存了依赖项
        self.assertIs(instance.config, config)
        self.assertIs(instance.decision_layer, mock_decision_layer)
        self.assertIs(instance.event_bus, mock_event_bus)


class TestCANCommunicatorBaseInitialization(unittest.TestCase):
    """测试抽象基类的初始化"""
    
    def test_base_class_stores_dependencies(self):
        """
        测试：基类正确存储依赖项
        
        验证：
        - config 被正确保存
        - decision_layer 被正确保存
        - event_bus 被正确保存
        """
        # 创建一个完整的子类用于测试
        class TestSubclass(CANCommunicatorBase):
            def start(self) -> bool:
                return True
            
            def stop(self, timeout: float = 5.0) -> bool:
                return True
            
            @property
            def is_running(self) -> bool:
                return False
        
        config = CANConfigDTO(
            enable_can=False,
            can_interface="socketcan",
            can_channel="can0",
            can_bitrate=250000
        )
        mock_decision_layer = Mock()
        mock_event_bus = Mock()
        
        # 实例化子类
        instance = TestSubclass(config, mock_decision_layer, mock_event_bus)
        
        # 验证依赖项被正确保存
        self.assertIs(instance.config, config)
        self.assertEqual(instance.config.can_interface, "socketcan")
        self.assertEqual(instance.config.can_channel, "can0")
        self.assertEqual(instance.config.can_bitrate, 250000)
        
        self.assertIs(instance.decision_layer, mock_decision_layer)
        self.assertIs(instance.event_bus, mock_event_bus)


if __name__ == '__main__':
    unittest.main(verbosity=2)
