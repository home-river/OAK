"""
配置管理模块集成测试的专用 fixtures

提供：
- Mock 设备数据
- 临时配置文件
- 测试用的绑定配置
"""

import pytest
import time
from unittest.mock import Mock
import depthai as dai

from oak_vision_system.core.dto.config_dto import (
    DeviceMetadataDTO,
    DeviceRoleBindingDTO,
    DeviceRole,
    ConnectionStatus,
)


# ==================== Mock 设备数据 ====================

@pytest.fixture
def mock_oak_device_info():
    """Mock 的单个 OAK 设备信息"""
    mock_device = Mock(spec=dai.DeviceInfo)
    mock_device.mxid = "14442C10D13D0D0000"
    mock_device.state = "X_LINK_BOOTED"
    return mock_device


@pytest.fixture
def mock_oak_device_info_list():
    """Mock 的多个 OAK 设备信息列表"""
    mock_device1 = Mock(spec=dai.DeviceInfo)
    mock_device1.mxid = "14442C10D13D0D0000"
    mock_device1.state = "X_LINK_BOOTED"
    
    mock_device2 = Mock(spec=dai.DeviceInfo)
    mock_device2.mxid = "14442C10D13D0D0001"
    mock_device2.state = "X_LINK_UNBOOTED"
    
    return [mock_device1, mock_device2]


# ==================== 测试用设备元数据 ====================

@pytest.fixture
def test_device_metadata_list():
    """测试用的设备元数据 DTO 列表"""
    current_time = time.time()
    return [
        DeviceMetadataDTO(
            mxid="14442C10D13D0D0000",
            product_name="OAK-D",
            connection_status=ConnectionStatus.CONNECTED,
            notes="Test device 1",
            first_seen=current_time,
            last_seen=current_time,
        ),
        DeviceMetadataDTO(
            mxid="14442C10D13D0D0001",
            product_name="OAK-D-Lite",
            connection_status=ConnectionStatus.CONNECTED,
            notes="Test device 2",
            first_seen=current_time,
            last_seen=current_time,
        ),
    ]


@pytest.fixture
def single_device_metadata():
    """单个测试设备元数据"""
    return DeviceMetadataDTO(
        mxid="14442C10D13D0D0000",
        product_name="OAK-D",
        connection_status=ConnectionStatus.CONNECTED,
        notes="Single test device",
        first_seen=time.time(),
        last_seen=time.time(),
    )


# ==================== 测试用绑定配置 ====================

@pytest.fixture
def test_bindings_with_history():
    """测试用的绑定配置（有历史记录）"""
    return [
        DeviceRoleBindingDTO(
            role=DeviceRole.LEFT_CAMERA,
            last_active_mxid="14442C10D13D0D0000",
            historical_mxids=["14442C10D13D0D0000"],
        ),
        DeviceRoleBindingDTO(
            role=DeviceRole.RIGHT_CAMERA,
            last_active_mxid="14442C10D13D0D0001",
            historical_mxids=["14442C10D13D0D0001"],
        ),
    ]


@pytest.fixture
def test_bindings_empty():
    """测试用的空绑定配置"""
    return DeviceRoleBindingDTO.create_default_bingdings()


# ==================== 临时配置文件 ====================

@pytest.fixture
def temp_config_file(temp_config_dir):
    """临时配置文件路径"""
    config_path = temp_config_dir / "test_config.json"
    yield config_path
    # 清理
    if config_path.exists():
        config_path.unlink()

