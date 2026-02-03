"""
DeviceMatchManager 单元测试

测试策略：
- 使用真实的 DTO 对象作为测试数据
- 使用 Pytest Fixture 组织共享的测试数据
- 遵循 AAA 模式（Arrange-Act-Assert）
- 覆盖核心功能和边界情况
"""

import pytest
import time
from typing import List

from oak_vision_system.modules.config_manager.device_match import (
    DeviceMatchManager,
    DeviceMatchResult,
    MatchResultType,
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
    """真实的左侧设备 DTO"""
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
    """真实的右侧设备 DTO"""
    return DeviceMetadataDTO(
        mxid="14442C10D13D0D0001",
        product_name="OAK-D-Lite",
        connection_status=ConnectionStatus.CONNECTED,
        notes="测试用右侧设备",
        first_seen=time.time(),
        last_seen=time.time(),
    )


@pytest.fixture
def device_new():
    """真实的新设备 DTO（历史记录中不存在）"""
    return DeviceMetadataDTO(
        mxid="14442C10D13D0D9999",
        product_name="OAK-D",
        connection_status=ConnectionStatus.CONNECTED,
        notes="测试用新设备",
        first_seen=time.time(),
        last_seen=time.time(),
    )


@pytest.fixture
def two_devices(device_left, device_right):
    """两个在线设备"""
    return [device_left, device_right]


@pytest.fixture
def bindings_with_history(device_left, device_right):
    """有历史记录的绑定配置"""
    return [
        DeviceRoleBindingDTO(
            role=DeviceRole.LEFT_CAMERA,
            last_active_mxid=device_left.mxid,
            historical_mxids=[device_left.mxid],
        ),
        DeviceRoleBindingDTO(
            role=DeviceRole.RIGHT_CAMERA,
            last_active_mxid=device_right.mxid,
            historical_mxids=[device_right.mxid],
        ),
    ]


@pytest.fixture
def bindings_empty():
    """空的绑定配置（使用默认配置）"""
    return DeviceRoleBindingDTO.create_default_bingdings()


# ==================== 1. 初始化测试 ====================

class TestDeviceMatchManagerInit:
    """测试设备匹配管理器的初始化"""
    
    def test_init_with_valid_bindings(self, bindings_with_history):
        """测试：使用有效的绑定配置初始化"""
        # Arrange & Act
        matcher = DeviceMatchManager(bindings=bindings_with_history)
        
        # Assert
        assert matcher.bindings == bindings_with_history
        assert matcher.enable_auto_bind_new_devices is True
        assert matcher.match_result.result_type == MatchResultType.NO_MATCH
    
    def test_init_with_empty_bindings_creates_default(self):
        """测试：空绑定配置会创建默认配置"""
        # Arrange & Act
        matcher = DeviceMatchManager(bindings=None)
        
        # Assert
        default_bindings = DeviceRoleBindingDTO.create_default_bingdings()
        assert len(matcher.bindings) == len(default_bindings)
        assert all(b.role in [DeviceRole.LEFT_CAMERA, DeviceRole.RIGHT_CAMERA] 
                   for b in matcher.bindings)
    
    def test_init_with_invalid_bindings_raises_error(self):
        """测试：无效的绑定配置应抛出异常"""
        # Arrange
        invalid_bindings = [
            DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                historical_mxids=["device1"]
            ),
            DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,  # 重复角色！
                historical_mxids=["device2"]
            ),
        ]
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid bindings"):
            DeviceMatchManager(bindings=invalid_bindings)
    
    def test_init_with_online_devices(self, bindings_with_history, two_devices):
        """测试：初始化时提供在线设备"""
        # Arrange & Act
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        
        # Assert
        assert matcher.online_devices == two_devices
        assert len(matcher.match_result.available_devices) == 2


# ==================== 2. 核心匹配功能测试 ====================

class TestDeviceMatching:
    """测试设备匹配的核心功能"""
    
    def test_full_match_with_history(self, bindings_with_history, two_devices):
        """测试：完全匹配 - 所有设备都在历史记录中"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        
        # Act
        result = matcher.default_match_devices(online_devices=two_devices)
        
        # Assert
        assert result.result_type == MatchResultType.FULL_MATCH
        assert len(result.matched_bindings) == 2
        assert len(result.unmatched_bindings) == 0
        assert len(result.available_devices) == 0
        
        # 验证具体的匹配关系
        left_binding = matcher.get_matched_binding_by_role(DeviceRole.LEFT_CAMERA)
        right_binding = matcher.get_matched_binding_by_role(DeviceRole.RIGHT_CAMERA)
        assert left_binding.active_mxid == "14442C10D13D0D0000"
        assert right_binding.active_mxid == "14442C10D13D0D0001"
    
    def test_partial_match_one_device_offline(self, bindings_with_history, device_left):
        """测试：部分匹配 - 只有一个设备在线"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[device_left]  # 只提供左侧设备
        )
        
        # Act
        result = matcher.default_match_devices(online_devices=[device_left])
        
        # Assert
        assert result.result_type == MatchResultType.PARTIAL_MATCH
        assert len(result.matched_bindings) == 1
        assert len(result.unmatched_bindings) == 1
        assert len(result.available_devices) == 0
        
        # 验证匹配的是左侧设备
        matched_roles = [b.role for b in result.matched_bindings]
        unmatched_roles = [b.role for b in result.unmatched_bindings]
        assert DeviceRole.LEFT_CAMERA in matched_roles
        assert DeviceRole.RIGHT_CAMERA in unmatched_roles
    
    def test_no_match_all_devices_offline(self, bindings_with_history):
        """测试：无匹配 - 所有设备都离线"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[]  # 没有设备
        )
        
        # Act
        result = matcher.default_match_devices(online_devices=[])
        
        # Assert
        assert result.result_type == MatchResultType.NO_MATCH
        assert len(result.matched_bindings) == 0
        assert len(result.unmatched_bindings) == 2
        assert len(result.available_devices) == 0
    
    def test_auto_bind_new_devices_enabled(self, bindings_empty, two_devices):
        """测试：自动绑定新设备 - 开关启用"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_empty,
            auto_bind_new_devices=True,
            online_devices=two_devices
        )
        
        # Act
        result = matcher.default_match_devices(online_devices=two_devices)
        
        # Assert
        assert result.result_type == MatchResultType.FULL_MATCH
        assert len(result.matched_bindings) == 2
        assert len(result.available_devices) == 0
        
        # 验证设备被自动绑定到了正确的角色
        left_binding = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA)
        right_binding = matcher.get_binding_by_role(DeviceRole.RIGHT_CAMERA)
        assert left_binding.active_mxid in [d.mxid for d in two_devices]
        assert right_binding.active_mxid in [d.mxid for d in two_devices]
    
    def test_auto_bind_new_devices_disabled(self, bindings_empty, two_devices):
        """测试：自动绑定新设备 - 开关禁用"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_empty,
            auto_bind_new_devices=False,  # 禁用自动绑定
            online_devices=two_devices
        )
        
        # Act
        result = matcher.default_match_devices(online_devices=two_devices)
        
        # Assert
        assert result.result_type == MatchResultType.NO_MATCH
        assert len(result.matched_bindings) == 0
        assert len(result.unmatched_bindings) == 2
        assert len(result.available_devices) == 2  # 所有设备都是空闲的
    
    def test_match_priority_last_active_over_historical(self):
        """测试：匹配优先级 - last_active_mxid 优先于 historical_mxids"""
        # Arrange
        devices = [
            DeviceMetadataDTO(mxid="device1", product_name="OAK-D"),
            DeviceMetadataDTO(mxid="device2", product_name="OAK-D"),
        ]
        
        bindings = [
            DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                last_active_mxid="device2",  # 上次使用 device2
                historical_mxids=["device1", "device2"],  # 历史中有 device1 和 device2
            ),
            DeviceRoleBindingDTO(
                role=DeviceRole.RIGHT_CAMERA,
                last_active_mxid="device1",
                historical_mxids=["device1"],
            ),
        ]
        
        matcher = DeviceMatchManager(bindings=bindings, online_devices=devices)
        
        # Act
        result = matcher.default_match_devices(online_devices=devices)
        
        # Assert
        assert result.result_type == MatchResultType.FULL_MATCH
        # 验证优先匹配 last_active_mxid
        left_binding = matcher.get_matched_binding_by_role(DeviceRole.LEFT_CAMERA)
        assert left_binding.active_mxid == "device2"  # 匹配 last_active


# ==================== 3. 手动绑定操作测试 ====================

class TestManualBinding:
    """测试手动绑定操作"""
    
    def test_manual_bind_device_success(self, bindings_empty, device_left):
        """测试：手动绑定设备成功"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_empty,
            online_devices=[device_left]
        )
        
        # Act
        success, msg = matcher.manual_bind_device(
            role=DeviceRole.LEFT_CAMERA,
            mxid=device_left.mxid
        )
        
        # Assert
        assert success is True
        assert "成功" in msg
        assert matcher.is_role_matched(DeviceRole.LEFT_CAMERA)
        
        # 验证绑定详情
        binding = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA)
        assert binding.active_mxid == device_left.mxid
        assert device_left.mxid in binding.historical_mxids
    
    def test_manual_bind_device_not_online(self, bindings_empty):
        """测试：手动绑定离线设备失败"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_empty,
            online_devices=[]  # 没有在线设备
        )
        
        # Act
        success, msg = matcher.manual_bind_device(
            role=DeviceRole.LEFT_CAMERA,
            mxid="offline_device_123"
        )
        
        # Assert
        assert success is False
        assert "不在线" in msg
    
    def test_manual_bind_device_rebind_from_another_role(self, bindings_empty, two_devices):
        """测试：手动绑定已被其他角色使用的设备"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_empty,
            online_devices=two_devices
        )
        
        # 先绑定 device_left 到左相机
        matcher.manual_bind_device(DeviceRole.LEFT_CAMERA, two_devices[0].mxid)
        
        # Act - 将同一设备绑定到右相机
        success, msg = matcher.manual_bind_device(
            DeviceRole.RIGHT_CAMERA,
            two_devices[0].mxid
        )
        
        # Assert
        assert success is True
        # 左相机应该被自动解绑
        assert not matcher.is_role_matched(DeviceRole.LEFT_CAMERA)
        # 右相机绑定了该设备
        assert matcher.get_binding_by_role(DeviceRole.RIGHT_CAMERA).active_mxid == two_devices[0].mxid
    
    def test_unbind_role_success(self, bindings_with_history, two_devices):
        """测试：解除角色绑定成功"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # Act
        success, msg = matcher.unbind_role(DeviceRole.LEFT_CAMERA)
        
        # Assert
        assert success is True
        assert not matcher.is_role_matched(DeviceRole.LEFT_CAMERA)
        
        # 验证历史记录仍然保留
        binding = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA)
        assert binding.active_mxid is None
        assert len(binding.historical_mxids) > 0
    
    def test_unbind_all_devices(self, bindings_with_history, two_devices):
        """测试：解除所有设备绑定"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # Act
        success, msg = matcher.unbind_all_devices()
        
        # Assert
        assert success is True
        assert not matcher.is_role_matched(DeviceRole.LEFT_CAMERA)
        assert not matcher.is_role_matched(DeviceRole.RIGHT_CAMERA)
        assert len(matcher.match_result.matched_bindings) == 0
        assert len(matcher.match_result.available_devices) == 2
    
    def test_swap_devices_success(self, bindings_with_history, two_devices):
        """测试：交换两个角色的设备"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # 记录交换前的绑定
        left_mxid_before = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA).active_mxid
        right_mxid_before = matcher.get_binding_by_role(DeviceRole.RIGHT_CAMERA).active_mxid
        
        # Act
        success, msg = matcher.swap_devices(
            DeviceRole.LEFT_CAMERA,
            DeviceRole.RIGHT_CAMERA
        )
        
        # Assert
        assert success is True
        
        # 验证交换结果
        left_mxid_after = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA).active_mxid
        right_mxid_after = matcher.get_binding_by_role(DeviceRole.RIGHT_CAMERA).active_mxid
        
        assert left_mxid_after == right_mxid_before
        assert right_mxid_after == left_mxid_before
    
    def test_swap_devices_one_not_bound(self, bindings_with_history, device_left):
        """测试：交换设备时一个角色未绑定"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[device_left]  # 只有一个设备
        )
        matcher.default_match_devices(online_devices=[device_left])  # 只有左相机匹配
        
        # Act
        success, msg = matcher.swap_devices(
            DeviceRole.LEFT_CAMERA,
            DeviceRole.RIGHT_CAMERA  # 右相机未绑定
        )
        
        # Assert
        assert success is False
        assert "未绑定设备" in msg


# ==================== 4. 配置验证测试 ====================

class TestConfigValidation:
    """测试配置验证功能"""
    
    def test_check_bindings_roles_valid(self, bindings_with_history):
        """测试：验证有效的绑定配置"""
        # Act
        is_valid, errors = DeviceMatchManager.check_bindings_roles(bindings_with_history)
        
        # Assert
        assert is_valid is True
        assert len(errors) == 0
    
    def test_check_bindings_roles_duplicate_role(self):
        """测试：检测重复角色"""
        # Arrange
        invalid_bindings = [
            DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                historical_mxids=["device1"]
            ),
            DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,  # 重复！
                historical_mxids=["device2"]
            ),
        ]
        
        # Act
        is_valid, errors = DeviceMatchManager.check_bindings_roles(invalid_bindings)
        
        # Assert
        assert is_valid is False
        assert any("重复角色" in err for err in errors)
    
    def test_check_bindings_roles_missing_role(self):
        """测试：检测缺失角色"""
        # Arrange
        incomplete_bindings = [
            DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                historical_mxids=["device1"]
            ),
            # 缺少 RIGHT_CAMERA
        ]
        
        # Act
        is_valid, errors = DeviceMatchManager.check_bindings_roles(incomplete_bindings)
        
        # Assert
        assert is_valid is False
        assert any("缺失角色" in err for err in errors)
    
    def test_validate_match_result_can_start(self, bindings_with_history, two_devices):
        """测试：验证匹配结果是否满足启动条件 - 完全匹配"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        result = matcher.default_match_devices(online_devices=two_devices)
        
        # Act
        can_start, issues = matcher.validate_match_result(result)
        
        # Assert
        assert can_start is True
        assert len(issues) == 0
    
    def test_validate_match_result_partial_match_with_warning(
        self, bindings_with_history, device_left
    ):
        """测试：验证匹配结果 - 部分匹配（有警告但可启动）"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[device_left]
        )
        result = matcher.default_match_devices(online_devices=[device_left])
        
        # Act
        can_start, issues = matcher.validate_match_result(result)
        
        # Assert
        assert can_start is True  # 部分匹配可以启动
        assert len(issues) > 0  # 但有警告
        assert any("警告" in issue for issue in issues)
    
    def test_validate_match_result_no_match_cannot_start(self, bindings_with_history):
        """测试：验证匹配结果 - 无匹配（不能启动）"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[]
        )
        result = matcher.default_match_devices(online_devices=[])
        
        # Act
        can_start, issues = matcher.validate_match_result(result)
        
        # Assert
        assert can_start is False
        assert len(issues) > 0
        assert any("没有任何设备" in issue for issue in issues)


# ==================== 5. 查询接口测试 ====================

class TestQueryInterfaces:
    """测试查询接口"""
    
    def test_get_device_by_mxid(self, two_devices):
        """测试：根据 MXID 查找设备"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=DeviceRoleBindingDTO.create_default_bingdings(),
            online_devices=two_devices
        )
        
        # Act
        device = matcher.get_device_by_mxid(two_devices[0].mxid)
        
        # Assert
        assert device is not None
        assert device.mxid == two_devices[0].mxid
    
    def test_get_device_by_mxid_not_found(self):
        """测试：查找不存在的设备"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=DeviceRoleBindingDTO.create_default_bingdings(),
            online_devices=[]
        )
        
        # Act
        device = matcher.get_device_by_mxid("nonexistent_device")
        
        # Assert
        assert device is None
    
    def test_get_binding_by_role(self, bindings_with_history):
        """测试：根据角色查找绑定"""
        # Arrange
        matcher = DeviceMatchManager(bindings=bindings_with_history)
        
        # Act
        binding = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA)
        
        # Assert
        assert binding is not None
        assert binding.role == DeviceRole.LEFT_CAMERA
    
    def test_is_role_matched(self, bindings_with_history, two_devices):
        """测试：检查角色是否已匹配"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # Act & Assert
        assert matcher.is_role_matched(DeviceRole.LEFT_CAMERA) is True
        assert matcher.is_role_matched(DeviceRole.RIGHT_CAMERA) is True
    
    def test_is_device_bound(self, bindings_with_history, two_devices):
        """测试：检查设备是否已绑定"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # Act & Assert
        assert matcher.is_device_bound(two_devices[0].mxid) is True
        assert matcher.is_device_bound("nonexistent_device") is False
    
    def test_list_matched_devices(self, bindings_with_history, two_devices):
        """测试：列出所有已匹配设备"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # Act
        matched = matcher.list_matched_devices()
        
        # Assert
        assert len(matched) == 2
        assert all(isinstance(item, tuple) for item in matched)
        assert all(len(item) == 2 for item in matched)
    
    def test_list_available_devices(self, bindings_with_history, two_devices, device_new):
        """测试：列出所有空闲设备"""
        # Arrange
        all_devices = two_devices + [device_new]  # 3个设备，只有2个会被匹配
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=all_devices,
            auto_bind_new_devices=False  # 禁用自动绑定
        )
        matcher.default_match_devices(online_devices=all_devices)
        
        # Act
        available = matcher.list_available_devices()
        
        # Assert
        assert len(available) == 1
        assert available[0].mxid == device_new.mxid
    
    def test_get_unmatched_roles(self, bindings_with_history, device_left):
        """测试：获取未匹配的角色"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[device_left]  # 只有一个设备
        )
        matcher.default_match_devices(online_devices=[device_left])
        
        # Act
        unmatched = matcher.get_unmatched_roles()
        
        # Assert
        assert len(unmatched) == 1
        assert DeviceRole.RIGHT_CAMERA in unmatched


# ==================== 6. 状态导出测试 ====================

class TestStateExport:
    """测试状态导出功能"""
    
    def test_get_current_status(self, bindings_with_history, two_devices):
        """测试：获取当前状态快照"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # Act
        status = matcher.get_current_status()
        
        # Assert
        assert isinstance(status, dict)
        assert "result_type" in status
        assert "can_start" in status
        assert "matched_devices" in status
        assert "unmatched_roles" in status
        assert "available_devices" in status
        assert "errors" in status
        
        # 验证具体值
        assert status["result_type"] == "full_match"
        assert status["can_start"] is True
        assert len(status["matched_devices"]) == 2
        assert len(status["unmatched_roles"]) == 0
    
    def test_export_bindings(self, bindings_with_history, two_devices):
        """测试：导出绑定配置"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # Act
        exported = matcher.export_bindings()
        
        # Assert
        assert isinstance(exported, list)
        assert len(exported) == 2
        assert all(isinstance(b, DeviceRoleBindingDTO) for b in exported)
    
    def test_get_match_summary(self, bindings_with_history, two_devices):
        """测试：生成匹配摘要"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        result = matcher.default_match_devices(online_devices=two_devices)
        
        # Act
        summary = matcher.get_match_summary(result)
        
        # Assert
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "完全匹配" in summary
        assert "已匹配角色" in summary


# ==================== 7. 边界情况测试 ====================

class TestEdgeCases:
    """测试边界情况和异常场景"""
    
    def test_empty_online_devices(self, bindings_with_history):
        """测试：没有在线设备"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[]
        )
        
        # Act
        result = matcher.default_match_devices(online_devices=[])
        
        # Assert
        assert result.result_type == MatchResultType.NO_MATCH
        assert len(result.matched_bindings) == 0
        assert len(result.available_devices) == 0
    
    def test_more_devices_than_roles(self, bindings_with_history):
        """测试：设备数量多于角色数量"""
        # Arrange
        many_devices = [
            DeviceMetadataDTO(mxid=f"device{i}", product_name="OAK-D")
            for i in range(5)  # 5个设备，只有2个角色
        ]
        
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=many_devices,
            auto_bind_new_devices=True
        )
        
        # Act
        result = matcher.default_match_devices(online_devices=many_devices)
        
        # Assert
        assert result.result_type == MatchResultType.FULL_MATCH
        assert len(result.matched_bindings) == 2  # 只匹配2个角色
        assert len(result.available_devices) == 3  # 剩余3个空闲设备
    
    def test_rematch_after_device_change(self, bindings_with_history, device_left, device_new):
        """测试：设备更换后重新匹配"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[device_left]
        )
        
        # 第一次匹配
        result1 = matcher.default_match_devices(online_devices=[device_left])
        assert result1.result_type == MatchResultType.PARTIAL_MATCH
        
        # Act - 添加新设备并重新匹配
        success = matcher.auto_rematch_devices(online_devices=[device_left, device_new])
        
        # Assert
        assert success is True
        assert matcher.match_result.result_type == MatchResultType.FULL_MATCH
    
    def test_set_bindings_after_init(self, bindings_with_history, bindings_empty):
        """测试：初始化后更改绑定配置"""
        # Arrange
        matcher = DeviceMatchManager(bindings=bindings_empty)
        
        # Act
        matcher.set_bindings(bindings_with_history)
        
        # Assert
        assert matcher.bindings == bindings_with_history
    
    def test_toggle_auto_bind_switch(self, bindings_empty, two_devices):
        """测试：切换自动绑定开关"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_empty,
            online_devices=two_devices,
            auto_bind_new_devices=False
        )
        
        # 禁用状态下不应自动绑定
        result1 = matcher.default_match_devices(online_devices=two_devices)
        assert result1.result_type == MatchResultType.NO_MATCH
        
        # Act - 启用自动绑定
        matcher.set_auto_bind_new_devices(True)
        result2 = matcher.default_match_devices(online_devices=two_devices)
        
        # Assert
        assert result2.result_type == MatchResultType.FULL_MATCH
    
    def test_reset_to_default_bindings_result(self, bindings_with_history, two_devices):
        """测试：重置匹配结果"""
        # Arrange
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=two_devices
        )
        matcher.default_match_devices(online_devices=two_devices)
        
        # Act
        matcher.reset_to_default_bindingsResult()
        
        # Assert
        assert len(matcher.match_result.matched_bindings) == 0
        assert len(matcher.match_result.unmatched_bindings) == 0
        assert matcher.match_result.result_type == MatchResultType.NO_MATCH


# ==================== 8. 集成场景测试 ====================

class TestIntegrationScenarios:
    """测试真实使用场景的集成测试"""
    
    def test_typical_startup_flow(self):
        """测试：典型的系统启动流程"""
        # 1. 创建默认配置
        bindings = DeviceRoleBindingDTO.create_default_bingdings()
        
        # 2. 发现设备（模拟）
        discovered_devices = [
            DeviceMetadataDTO(mxid="device1", product_name="OAK-D"),
            DeviceMetadataDTO(mxid="device2", product_name="OAK-D"),
        ]
        
        # 3. 创建匹配器
        matcher = DeviceMatchManager(
            bindings=bindings,
            online_devices=discovered_devices,
            auto_bind_new_devices=True
        )
        
        # 4. 执行匹配
        result = matcher.default_match_devices(online_devices=discovered_devices)
        
        # 5. 验证是否可以启动
        can_start, issues = matcher.validate_match_result(result)
        
        # Assert
        assert can_start is True
        assert result.result_type == MatchResultType.FULL_MATCH
    
    def test_device_swap_scenario(self, bindings_with_history, device_left, device_right):
        """测试：设备接反场景（左右相机接反了）"""
        # Arrange - 初始匹配（按历史记录正常匹配）
        matcher = DeviceMatchManager(
            bindings=bindings_with_history,
            online_devices=[device_left, device_right]
        )
        
        # 第一次匹配：按历史记录正常匹配
        matcher.default_match_devices(online_devices=[device_left, device_right])
        
        # 记录交换前的状态
        left_mxid_before = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA).active_mxid
        right_mxid_before = matcher.get_binding_by_role(DeviceRole.RIGHT_CAMERA).active_mxid
        
        # Act - 用户发现设备接反了，手动交换
        matcher.swap_devices(DeviceRole.LEFT_CAMERA, DeviceRole.RIGHT_CAMERA)
        
        # Assert - 交换后设备绑定应该互换
        left_binding = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA)
        right_binding = matcher.get_binding_by_role(DeviceRole.RIGHT_CAMERA)
        
        # 交换后的绑定应该与交换前相反
        assert left_binding.active_mxid == right_mxid_before  # 左相机现在绑定原来右相机的设备
        assert right_binding.active_mxid == left_mxid_before  # 右相机现在绑定原来左相机的设备
    
    def test_device_replacement_scenario(self):
        """测试：设备更换场景（旧设备坏了，换了新设备）"""
        # Arrange - 旧设备的配置
        old_bindings = [
            DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                last_active_mxid="old_device_123",
                historical_mxids=["old_device_123"]
            ),
            DeviceRoleBindingDTO(
                role=DeviceRole.RIGHT_CAMERA,
                last_active_mxid="old_device_456",
                historical_mxids=["old_device_456"]
            ),
        ]
        
        # 新设备上线
        new_devices = [
            DeviceMetadataDTO(mxid="new_device_789", product_name="OAK-D"),
            DeviceMetadataDTO(mxid="new_device_012", product_name="OAK-D"),
        ]
        
        matcher = DeviceMatchManager(
            bindings=old_bindings,
            online_devices=new_devices,
            auto_bind_new_devices=True  # 自动绑定新设备
        )
        
        # Act
        result = matcher.default_match_devices(online_devices=new_devices)
        
        # Assert - 新设备应该被自动绑定
        assert result.result_type == MatchResultType.FULL_MATCH
        assert all(
            "new_device" in b.active_mxid 
            for b in result.matched_bindings
        )
        
        # 导出配置（用于保存）
        exported = matcher.export_bindings()
        assert len(exported) == 2

