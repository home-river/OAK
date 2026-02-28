"""
DeviceConfigManager 单元测试

测试策略：
- 测试配置加载/保存时 active_mxid 的清空逻辑
- 使用 mock 模拟设备发现器，避免依赖真实硬件
- 使用临时目录进行文件操作测试
- 遵循 AAA 模式（Arrange-Act-Assert）

注意：
- load_config() 在自动创建配置时会进行设备匹配
- 但如果匹配失败（如 DeviceMatchManager 调用错误），active_mxid 会保持为 None
- 这是预期行为，因为配置加载不应该因为匹配失败而失败
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import List

from oak_vision_system.modules.config_manager.device_config_manager import (
    DeviceConfigManager,
    ConfigValidationError,
    ConfigNotFoundError,
)
from oak_vision_system.core.dto.config_dto import (
    DeviceMetadataDTO,
    DeviceRoleBindingDTO,
    DeviceRole,
    ConnectionStatus,
)


# ==================== 测试数据 Fixtures ====================

@pytest.fixture
def device_left():
    """测试用左侧设备"""
    return DeviceMetadataDTO(
        mxid="14442C10D13D0D0000",
        product_name="OAK-D",
        connection_status=ConnectionStatus.CONNECTED,
        notes="测试用左侧设备",
        first_seen=time.time(),
        last_seen=time.time(),
    )


@pytest.fixture
def device_right():
    """测试用右侧设备"""
    return DeviceMetadataDTO(
        mxid="14442C10D13D0D0001",
        product_name="OAK-D-Lite",
        connection_status=ConnectionStatus.CONNECTED,
        notes="测试用右侧设备",
        first_seen=time.time(),
        last_seen=time.time(),
    )


@pytest.fixture
def two_devices(device_left, device_right):
    """两个在线设备"""
    return [device_left, device_right]


@pytest.fixture
def bindings_with_active_mxid(device_left, device_right):
    """带有 active_mxid 的绑定配置"""
    return {
        DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
            role=DeviceRole.LEFT_CAMERA,
            active_mxid=device_left.mxid,  # 有 active_mxid
            last_active_mxid=device_left.mxid,
            historical_mxids=[device_left.mxid],
        ),
        DeviceRole.RIGHT_CAMERA: DeviceRoleBindingDTO(
            role=DeviceRole.RIGHT_CAMERA,
            active_mxid=device_right.mxid,  # 有 active_mxid
            last_active_mxid=device_right.mxid,
            historical_mxids=[device_right.mxid],
        ),
    }


@pytest.fixture
def temp_config_path(tmp_path):
    """临时配置文件路径"""
    return str(tmp_path / "test_config.json")


# ==================== 1. _clear_active_mxids() 方法测试 ====================

class TestClearActiveMxids:
    """测试 _clear_active_mxids() 私有方法"""
    
    def test_clear_active_mxids_idempotent(self, temp_config_path, two_devices):
        """测试：_clear_active_mxids() 方法的幂等性"""
        # Arrange
        with patch('oak_vision_system.modules.config_manager.device_config_manager.OAKDeviceDiscovery.discover_devices') as mock_discover:
            mock_discover.return_value = two_devices
            
            manager = DeviceConfigManager(config_path=temp_config_path, auto_create=True)
            manager.load_config()
            
            config = manager.get_config()
            
            # Act - 多次调用
            config_1 = manager._clear_active_mxids(config)
            config_2 = manager._clear_active_mxids(config_1)
            config_3 = manager._clear_active_mxids(config_2)
            
            # Assert - 结果应该一致
            for binding_1, binding_2, binding_3 in zip(
                config_1.oak_module.role_bindings.values(),
                config_2.oak_module.role_bindings.values(),
                config_3.oak_module.role_bindings.values()
            ):
                assert binding_1.active_mxid is None
                assert binding_2.active_mxid is None
                assert binding_3.active_mxid is None
    
    def test_clear_active_mxids_preserves_history(self, temp_config_path, two_devices):
        """测试：清空 active_mxid 不影响历史记录"""
        # Arrange
        with patch('oak_vision_system.modules.config_manager.device_config_manager.OAKDeviceDiscovery.discover_devices') as mock_discover:
            mock_discover.return_value = two_devices
            
            manager = DeviceConfigManager(config_path=temp_config_path, auto_create=True)
            manager.load_config()
            
            config_before = manager.get_config()
            
            # 记录清空前的历史记录
            history_before = {
                role: (binding.last_active_mxid, list(binding.historical_mxids))
                for role, binding in config_before.oak_module.role_bindings.items()
            }
            
            # Act
            config_after = manager._clear_active_mxids(config_before)
            
            # Assert - 历史记录应该保持不变
            for role, binding in config_after.oak_module.role_bindings.items():
                last_active_before, historical_before = history_before[role]
                assert binding.last_active_mxid == last_active_before
                assert list(binding.historical_mxids) == historical_before


# ==================== 2. save_config() 测试 ====================

class TestSaveConfig:
    """测试 save_config() 方法"""
    
    def test_save_config_always_clears_active_mxid(self, temp_config_path, two_devices):
        """测试：保存配置时总是清空 active_mxid（无论内存中是否有）"""
        # Arrange
        with patch('oak_vision_system.modules.config_manager.device_config_manager.OAKDeviceDiscovery.discover_devices') as mock_discover:
            mock_discover.return_value = two_devices
            
            manager = DeviceConfigManager(config_path=temp_config_path, auto_create=True)
            manager.load_config()
            
            # Act
            manager.save_config()
            
            # Assert - 读取保存的文件，验证 active_mxid 都是 None
            with open(temp_config_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            role_bindings = saved_data['oak_module']['role_bindings']
            for role, binding_data in role_bindings.items():
                assert binding_data['active_mxid'] is None, \
                    f"角色 {role} 的 active_mxid 应该是 None，但实际是 {binding_data['active_mxid']}"
    
    def test_save_config_preserves_history_in_file(self, temp_config_path, two_devices):
        """测试：保存配置时保留历史记录"""
        # Arrange
        with patch('oak_vision_system.modules.config_manager.device_config_manager.OAKDeviceDiscovery.discover_devices') as mock_discover:
            mock_discover.return_value = two_devices
            
            manager = DeviceConfigManager(config_path=temp_config_path, auto_create=True)
            manager.load_config()
            
            # 记录历史记录
            config = manager.get_runnable_config()
            history_before = {
                role.value: {
                    'last_active_mxid': binding.last_active_mxid,
                    'historical_mxids': list(binding.historical_mxids)
                }
                for role, binding in config.oak_module.role_bindings.items()
            }
            
            # Act
            manager.save_config()
            
            # Assert - 读取保存的文件，验证历史记录保持不变
            with open(temp_config_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            role_bindings = saved_data['oak_module']['role_bindings']
            for role, binding_data in role_bindings.items():
                assert binding_data['last_active_mxid'] == history_before[role]['last_active_mxid']
                assert binding_data['historical_mxids'] == history_before[role]['historical_mxids']


# ==================== 3. load_config() 测试 ====================

class TestLoadConfig:
    """测试 load_config() 方法"""
    
    def test_load_config_clears_active_mxid_no_devices(self, temp_config_path, two_devices):
        """测试：加载配置后清空 active_mxid（无设备场景）"""
        # Arrange - 先创建一个配置文件
        with patch('oak_vision_system.modules.config_manager.device_config_manager.OAKDeviceDiscovery.discover_devices') as mock_discover:
            mock_discover.return_value = two_devices
            
            # 创建并保存配置
            manager1 = DeviceConfigManager(config_path=temp_config_path, auto_create=True)
            manager1.load_config()
            manager1.save_config()
            
            # Act - 重新加载配置，模拟无设备场景
            mock_discover.return_value = []  # 无设备
            manager2 = DeviceConfigManager(config_path=temp_config_path, auto_create=False)
            manager2.load_config()
            
            # Assert - 验证加载后所有 active_mxid 都是 None
            config = manager2.get_config()
            assert all(
                binding.active_mxid is None 
                for binding in config.oak_module.role_bindings.values()
            ), "加载配置后，所有 active_mxid 应该被清空"

    def test_load_config_overwrites_device_metadata_in_memory(self, temp_config_path, two_devices, device_left):
        """测试：每次 load_config 都会在内存中覆盖 device_metadata 为在线设备快照"""
        with patch('oak_vision_system.modules.config_manager.device_config_manager.OAKDeviceDiscovery.discover_devices') as mock_discover:
            # Arrange - 第一次创建配置，写入 two_devices
            mock_discover.return_value = two_devices
            manager1 = DeviceConfigManager(config_path=temp_config_path, auto_create=True)
            manager1.load_config(validate=False)

            # Act - 第二次加载配置时，只发现一个设备，应在内存中覆盖
            mock_discover.return_value = [device_left]
            manager2 = DeviceConfigManager(config_path=temp_config_path, auto_create=False)
            manager2.load_config(validate=False)

            # Assert - 内存中的配置应该只包含在线设备
            cfg = manager2.get_config()
            assert set(cfg.oak_module.device_metadata.keys()) == {device_left.mxid}, \
                "load_config 后，内存中的 device_metadata 应该只包含在线设备"
            
            # Assert - 文件中的配置仍然是旧的（load_config 不负责持久化）
            with open(temp_config_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            saved_metadata = saved_data['oak_module']['device_metadata']
            assert set(saved_metadata.keys()) == {d.mxid for d in two_devices}, \
                "load_config 不会自动保存，文件中的 device_metadata 应该保持不变"


class TestMatchConfigInternal:
    """测试 _match_config_internal() 内部匹配方法"""

    def test_match_config_internal_overwrites_device_metadata(self, two_devices, device_left):
        """测试：_match_config_internal 会将 device_metadata 覆盖为 online_devices 的快照"""
        base_config = DeviceConfigManager.get_default_config(two_devices)

        new_config, _ = DeviceConfigManager._match_config_internal(
            base_config,
            online_devices=[device_left],
            auto_bind_new_devices=True,
            require_at_least_one_binding=False,
        )

        assert set(new_config.oak_module.device_metadata.keys()) == {device_left.mxid}


# ==================== 4. 完整流程测试 ====================

class TestFullWorkflow:
    """测试完整的配置管理流程"""
    
    def test_multiple_save_cycles_no_active_mxid_leak(self, temp_config_path, two_devices):
        """测试：多次保存循环，验证 active_mxid 不会泄漏到文件"""
        with patch('oak_vision_system.modules.config_manager.device_config_manager.OAKDeviceDiscovery.discover_devices') as mock_discover:
            mock_discover.return_value = two_devices
            
            manager = DeviceConfigManager(config_path=temp_config_path, auto_create=True)
            manager.load_config()
            
            # 多次保存
            for i in range(5):
                manager.save_config()
                
                # 每次保存后验证文件中没有 active_mxid
                with open(temp_config_path, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                
                role_bindings = saved_data['oak_module']['role_bindings']
                for role, binding_data in role_bindings.items():
                    assert binding_data['active_mxid'] is None, \
                        f"第 {i+1} 次保存后，角色 {role} 的 active_mxid 应该是 None"
    
    def test_save_and_load_preserves_no_active_mxid(self, temp_config_path, two_devices):
        """测试：保存-加载循环，验证 active_mxid 始终不被持久化"""
        with patch('oak_vision_system.modules.config_manager.device_config_manager.OAKDeviceDiscovery.discover_devices') as mock_discover:
            # 第一次：创建配置并保存
            mock_discover.return_value = two_devices
            manager1 = DeviceConfigManager(config_path=temp_config_path, auto_create=True)
            manager1.load_config()
            manager1.save_config()
            
            # 第二次：重新加载配置（无设备）
            mock_discover.return_value = []
            manager2 = DeviceConfigManager(config_path=temp_config_path, auto_create=False)
            manager2.load_config()
            
            # 验证加载后 active_mxid 都是 None
            config2 = manager2.get_config()
            assert all(
                b.active_mxid is None 
                for b in config2.oak_module.role_bindings.values()
            ), "重新加载后，所有 active_mxid 应该是 None"
            
            # 第三次：再次保存
            manager2.save_config()
            
            # 验证文件中 active_mxid 仍然是 None
            with open(temp_config_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            role_bindings = saved_data['oak_module']['role_bindings']
            for role, binding_data in role_bindings.items():
                assert binding_data['active_mxid'] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
