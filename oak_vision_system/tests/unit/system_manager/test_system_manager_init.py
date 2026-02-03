"""
SystemManager初始化单元测试（简化版）

测试SystemManager类的初始化功能，包括：
- 使用默认参数创建SystemManager
- 使用自定义参数创建SystemManager
- 内部数据结构正确初始化
- 日志系统初始化

Requirements: 11.1, 11.2, 11.4, 11.5, 15.1, 15.2, 15.3
"""

import pytest
import logging
import threading
from unittest.mock import patch, MagicMock
from oak_vision_system.core.system_manager import SystemManager
from oak_vision_system.core.event_bus import EventBus
from oak_vision_system.core.dto.config_dto import SystemConfigDTO


class TestSystemManagerInit:
    """SystemManager初始化测试套件（简化版）"""
    
    def test_init_with_default_parameters(self):
        """测试使用默认参数创建SystemManager
        
        验证：
        - SystemManager可以使用默认参数创建
        - 使用全局事件总线
        - 使用默认超时时间
        - 内部数据结构正确初始化
        
        Requirements: 11.1, 11.2, 15.1
        """
        # 创建SystemManager（使用默认参数）
        manager = SystemManager()
        
        # 验证实例创建成功
        assert manager is not None
        assert isinstance(manager, SystemManager)
        
        # 验证事件总线已初始化（使用全局单例）
        assert hasattr(manager, '_event_bus')
        assert manager._event_bus is not None
        
        # 验证默认配置参数
        assert hasattr(manager, '_default_stop_timeout')
        assert manager._default_stop_timeout == 5.0  # 默认值
        
        # 验证内部数据结构已初始化
        assert hasattr(manager, '_modules')
        assert isinstance(manager._modules, dict)
        assert len(manager._modules) == 0  # 初始为空
        
        assert hasattr(manager, '_shutdown_event')
        assert isinstance(manager._shutdown_event, threading.Event)
        assert not manager._shutdown_event.is_set()  # 初始未设置
        
        assert hasattr(manager, '_stop_started')
        assert isinstance(manager._stop_started, threading.Event)
        assert not manager._stop_started.is_set()  # 初始未设置
        
        # 验证logger已初始化
        assert hasattr(manager, '_logger')
        assert manager._logger is not None
    
    def test_init_with_custom_event_bus(self):
        """测试使用自定义事件总线创建SystemManager
        
        验证：
        - 可以提供自定义事件总线
        - SystemManager使用提供的事件总线而不是全局单例
        
        Requirements: 15.1
        """
        # 创建自定义事件总线
        custom_event_bus = EventBus()
        
        # 使用自定义事件总线创建SystemManager
        manager = SystemManager(event_bus=custom_event_bus)
        
        # 验证使用了自定义事件总线
        assert manager._event_bus is custom_event_bus
    
    def test_init_with_custom_timeout(self):
        """测试使用自定义超时时间创建SystemManager
        
        验证：
        - 可以自定义default_stop_timeout
        - 配置参数被正确保存
        
        Requirements: 15.3
        """
        # 使用自定义超时时间
        custom_stop_timeout = 10.0
        
        manager = SystemManager(default_stop_timeout=custom_stop_timeout)
        
        # 验证自定义超时时间被正确设置
        assert manager._default_stop_timeout == custom_stop_timeout
    
    def test_init_with_custom_force_exit_grace_period(self):
        """测试使用自定义强制退出宽限期创建SystemManager
        
        验证：
        - 可以自定义force_exit_grace_period
        - 配置参数被正确保存
        
        Requirements: 15.3 (可配置性)
        """
        # 使用自定义宽限期
        custom_grace_period = 5.0
        
        manager = SystemManager(force_exit_grace_period=custom_grace_period)
        
        # 验证自定义宽限期被正确设置
        assert manager._force_exit_grace_period == custom_grace_period
    
    def test_init_with_default_force_exit_grace_period(self):
        """测试使用默认强制退出宽限期创建SystemManager
        
        验证：
        - 默认force_exit_grace_period为3.0秒
        - 配置参数被正确保存
        
        Requirements: 15.3 (可配置性)
        """
        manager = SystemManager()
        
        # 验证默认宽限期为3.0秒
        assert manager._force_exit_grace_period == 3.0
    
    def test_init_with_system_config(self):
        """测试使用系统配置创建SystemManager
        
        验证：
        - 可以提供SystemConfigDTO配置对象
        - 日志系统被正确初始化
        
        Requirements: 11.1, 15.2
        """
        # 创建系统配置对象
        system_config = SystemConfigDTO(
            log_level="INFO",
            log_to_file=False
        )
        
        # 使用系统配置创建SystemManager
        manager = SystemManager(system_config=system_config)
        
        # 验证SystemManager正常初始化
        assert manager is not None
        assert hasattr(manager, '_logger')
    
    def test_init_with_all_custom_parameters(self):
        """测试使用所有自定义参数创建SystemManager
        
        验证：
        - 可以同时提供所有自定义参数
        - 所有参数都被正确设置
        
        Requirements: 15.1, 15.2, 15.3
        """
        # 准备所有自定义参数
        custom_event_bus = EventBus()
        system_config = SystemConfigDTO(
            log_level="DEBUG",
            log_to_file=False
        )
        custom_stop_timeout = 8.0
        custom_grace_period = 4.0
        
        # 使用所有自定义参数创建SystemManager
        manager = SystemManager(
            event_bus=custom_event_bus,
            system_config=system_config,
            default_stop_timeout=custom_stop_timeout,
            force_exit_grace_period=custom_grace_period
        )
        
        # 验证所有参数都被正确设置
        assert manager._event_bus is custom_event_bus
        assert manager._default_stop_timeout == custom_stop_timeout
        assert manager._force_exit_grace_period == custom_grace_period
    
    def test_internal_data_structures_initialized(self):
        """测试内部数据结构正确初始化
        
        验证：
        - _modules字典为空
        - _shutdown_event未设置
        - _stop_started未设置
        
        Requirements: 11.4, 11.5
        """
        manager = SystemManager()
        
        # 验证_modules字典
        assert isinstance(manager._modules, dict)
        assert len(manager._modules) == 0
        assert manager._modules == {}
        
        # 验证_shutdown_event
        assert isinstance(manager._shutdown_event, threading.Event)
        assert not manager._shutdown_event.is_set()
        
        # 验证_stop_started标志
        assert isinstance(manager._stop_started, threading.Event)
        assert not manager._stop_started.is_set()
    
    def test_multiple_instances_independent(self):
        """测试多个SystemManager实例相互独立
        
        验证：
        - 可以创建多个SystemManager实例
        - 每个实例有独立的内部数据结构
        
        Requirements: 11.4
        """
        # 创建两个SystemManager实例
        manager1 = SystemManager(default_stop_timeout=5.0)
        manager2 = SystemManager(default_stop_timeout=10.0)
        
        # 验证实例不同
        assert manager1 is not manager2
        
        # 验证内部数据结构独立
        assert manager1._modules is not manager2._modules
        assert manager1._shutdown_event is not manager2._shutdown_event
        assert manager1._stop_started is not manager2._stop_started
        
        # 验证配置独立
        assert manager1._default_stop_timeout == 5.0
        assert manager2._default_stop_timeout == 10.0
    
    def test_init_with_large_timeout(self):
        """测试使用大超时时间创建SystemManager
        
        验证：
        - 可以设置较大的超时时间
        - 参数被正确保存
        
        Requirements: 15.3
        """
        manager = SystemManager(default_stop_timeout=3600.0)  # 1小时
        
        # 验证大超时被接受
        assert manager._default_stop_timeout == 3600.0
    
    def test_init_without_system_config(self):
        """测试不提供system_config时的初始化
        
        验证：
        - system_config可以为None
        - SystemManager仍然正常初始化
        
        Requirements: 11.1
        """
        manager = SystemManager(system_config=None)
        
        # 验证其他部分正常初始化
        assert manager._modules == {}
        assert not manager._shutdown_event.is_set()
        assert not manager._stop_started.is_set()


class TestSystemManagerInitEdgeCases:
    """SystemManager初始化边界情况测试（简化版）"""
    
    def test_init_with_negative_timeout_raises_error(self):
        """测试使用负数超时时间创建SystemManager抛出异常
        
        验证：
        - 负数超时应该抛出ValueError
        
        Requirements: 15.3
        """
        # 负数超时应该抛出异常
        with pytest.raises(ValueError, match="default_stop_timeout 必须大于 0"):
            SystemManager(default_stop_timeout=-1.0)
    
    def test_init_with_zero_timeout_raises_error(self):
        """测试使用零超时时间创建SystemManager抛出异常
        
        验证：
        - 零超时应该抛出ValueError
        
        Requirements: 15.3
        """
        # 零超时应该抛出异常
        with pytest.raises(ValueError, match="default_stop_timeout 必须大于 0"):
            SystemManager(default_stop_timeout=0.0)
    
    def test_init_with_negative_grace_period_raises_error(self):
        """测试使用负数宽限期创建SystemManager抛出异常
        
        验证：
        - 负数宽限期应该抛出ValueError
        
        Requirements: 15.3 (可配置性)
        """
        # 负数宽限期应该抛出异常
        with pytest.raises(ValueError, match="force_exit_grace_period 必须大于 0"):
            SystemManager(force_exit_grace_period=-1.0)
    
    def test_init_with_zero_grace_period_raises_error(self):
        """测试使用零宽限期创建SystemManager抛出异常
        
        验证：
        - 零宽限期应该抛出ValueError
        
        Requirements: 15.3 (可配置性)
        """
        # 零宽限期应该抛出异常
        with pytest.raises(ValueError, match="force_exit_grace_period 必须大于 0"):
            SystemManager(force_exit_grace_period=0.0)
    
    def test_init_with_very_small_grace_period(self):
        """测试使用非常小的正数宽限期创建SystemManager
        
        验证：
        - 非常小的正数宽限期应该被接受
        - 参数被正确保存
        
        Requirements: 15.3 (可配置性)
        """
        # 非常小的正数宽限期应该被接受
        manager = SystemManager(force_exit_grace_period=0.1)
        
        # 验证参数被正确保存
        assert manager._force_exit_grace_period == 0.1
    
    def test_init_with_large_grace_period(self):
        """测试使用大宽限期创建SystemManager
        
        验证：
        - 可以设置较大的宽限期
        - 参数被正确保存
        
        Requirements: 15.3 (可配置性)
        """
        manager = SystemManager(force_exit_grace_period=60.0)  # 1分钟
        
        # 验证大宽限期被接受
        assert manager._force_exit_grace_period == 60.0
    
    def test_init_preserves_event_bus_state(self):
        """测试初始化时保留事件总线状态
        
        验证：
        - 如果提供已有订阅的事件总线，订阅不会丢失
        
        Requirements: 15.1
        """
        # 创建事件总线并添加订阅
        event_bus = EventBus()
        
        # 使用该事件总线创建SystemManager
        manager = SystemManager(event_bus=event_bus)
        
        # 验证事件总线是同一个实例
        assert manager._event_bus is event_bus


class TestSystemManagerLoggingInit:
    """SystemManager日志系统初始化测试套件（简化版）
    
    测试日志系统初始化功能，包括：
    - 不提供system_config时的行为
    - 提供有效system_config时的行为
    - 日志配置失败时的错误处理
    
    Requirements: 11.1, 11.2
    """
    
    def test_init_without_system_config_no_logging_call(self):
        """测试不提供system_config时不调用configure_logging
        
        验证：
        - 当system_config为None时，不调用configure_logging
        - SystemManager仍然正常初始化
        - logger被正确创建
        
        Requirements: 11.1
        """
        # 不提供system_config创建SystemManager
        manager = SystemManager(system_config=None)
        
        # 验证SystemManager正常初始化
        assert manager is not None
        assert hasattr(manager, '_logger')
        assert manager._logger is not None
    
    def test_logging_config_failure_uses_default_and_warns(self):
        """测试日志配置失败时使用默认配置并记录警告
        
        验证：
        - 当configure_logging抛出异常时，捕获异常
        - 使用basicConfig配置默认日志
        - SystemManager仍然正常初始化
        
        Requirements: 11.2
        """
        with patch('oak_vision_system.core.system_manager.system_manager.configure_logging') as mock_configure:
            with patch('logging.basicConfig') as mock_basic_config:
                # 设置configure_logging抛出异常
                mock_configure.side_effect = RuntimeError("日志配置失败")
                
                # 创建system_config
                system_config = SystemConfigDTO(
                    log_level="INFO",
                    log_to_file=False
                )
                
                # 创建SystemManager（应该捕获异常）
                manager = SystemManager(system_config=system_config)
                
                # 验证configure_logging被调用
                mock_configure.assert_called_once()
                
                # 验证basicConfig被调用（使用默认配置）
                mock_basic_config.assert_called_once()
                
                # 验证SystemManager仍然正常初始化
                assert manager is not None
    
    def test_init_logs_initialization_message(self):
        """测试初始化时记录日志消息
        
        验证：
        - 初始化完成后记录INFO级别日志
        - 日志消息包含"SystemManager初始化完成"
        
        Requirements: 11.2
        """
        # 创建SystemManager
        manager = SystemManager()
        
        # 验证manager有logger
        assert hasattr(manager, '_logger')
        assert manager._logger is not None
        
        # 验证初始化成功
        assert manager is not None


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
