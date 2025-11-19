"""
集成测试全局配置

提供：
- 设备检测 fixtures
- 临时测试数据目录
- 全局测试配置
"""

import pytest
import depthai as dai
from pathlib import Path


# ==================== 设备检测 ====================

def is_oak_device_available():
    """
    检测是否有 OAK 设备连接
    
    Returns:
        bool: True 如果检测到设备，否则 False
    """
    try:
        devices = dai.DeviceBootloader.getAllAvailableDevices()
        return len(devices) > 0
    except Exception:
        return False


@pytest.fixture(scope="session")
def has_oak_device():
    """
    Session 级别的设备检测 fixture
    
    使用示例：
        def test_something(has_oak_device):
            if not has_oak_device:
                pytest.skip("No OAK device connected")
            # 测试代码...
    """
    return is_oak_device_available()


# ==================== 测试数据目录 ====================

@pytest.fixture(scope="session")
def integration_test_data_dir(tmp_path_factory):
    """
    集成测试的临时数据目录（session 级别）
    
    用途：
    - 存储临时配置文件
    - 存储测试日志
    - 其他测试数据
    """
    return tmp_path_factory.mktemp("integration_data")


@pytest.fixture
def temp_config_dir(integration_test_data_dir):
    """
    每个测试的临时配置目录（function 级别）
    
    每个测试都有独立的配置目录，测试结束后自动清理
    """
    config_dir = integration_test_data_dir / f"config_{id(object())}"
    config_dir.mkdir(exist_ok=True)
    yield config_dir
    # 清理（可选，tmp_path_factory 会自动清理）


# ==================== pytest 配置钩子 ====================

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line(
        "markers", "hardware: tests that require real OAK hardware devices"
    )
    config.addinivalue_line(
        "markers", "slow: tests that take a long time to run"
    )

