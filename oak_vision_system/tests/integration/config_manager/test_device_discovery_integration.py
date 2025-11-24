"""
设备发现器集成测试

测试策略：
- Mock 测试：验证发现器的完整工作流，总是运行
- 硬件测试：验证与真实 OAK 硬件的交互，自动检测设备

运行方式：
- 运行所有测试：pytest oak_vision_system/tests/integration/config_manager/test_device_discovery_integration.py -v
- 只运行硬件测试：pytest oak_vision_system/tests/integration/config_manager/test_device_discovery_integration.py -m hardware -v
- 排除硬件测试：pytest oak_vision_system/tests/integration/config_manager/test_device_discovery_integration.py -m "not hardware" -v
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
import depthai as dai

from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
from oak_vision_system.core.dto.config_dto import DeviceMetadataDTO, ConnectionStatus


# ==================== Mock 集成测试（总是运行）====================

class TestDeviceDiscoveryIntegrationMock:
    """使用 Mock 的集成测试 - 验证完整工作流逻辑"""
    
    @patch('depthai.Device')
    @patch.object(OAKDeviceDiscovery, 'get_all_available_devices')
    def test_full_discovery_workflow_mock(self, mock_get_devices, mock_device_class, mock_oak_device_info):
        """
        测试：完整的设备发现工作流（Mock）
        
        场景：
        1. 获取设备列表
        2. 解析设备信息
        3. 获取产品名称
        4. 转换为 DTO
        5. 返回结果
        """
        # Arrange
        mock_get_devices.return_value = [mock_oak_device_info]
        
        # Mock 产品名称获取
        mock_eeprom = Mock()
        mock_eeprom.productName = "OAK-D"
        mock_calib = Mock()
        mock_calib.getEepromData.return_value = mock_eeprom
        mock_device = MagicMock()
        mock_device.__enter__.return_value.readCalibration.return_value = mock_calib
        mock_device_class.return_value = mock_device
        
        # Act
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        
        # Assert
        assert len(devices) == 1
        assert isinstance(devices[0], DeviceMetadataDTO)
        assert devices[0].mxid == "14442C10D13D0D0000"
        assert devices[0].product_name == "OAK-D"
        assert devices[0].connection_status == ConnectionStatus.CONNECTED
    
    # TODO: 添加更多 Mock 集成测试


# ==================== 真实硬件测试（自动检测）====================

@pytest.mark.hardware
class TestDeviceDiscoveryIntegrationHardware:
    """真实硬件集成测试 - 验证与真实 OAK 设备的交互"""
    
    def test_discover_real_devices(self, has_oak_device):
        """
        测试：发现真实 OAK 设备
        
        验证：
        - 能够发现连接的设备
        - 设备数据完整
        - MXID 格式正确
        """
        # Skip if no device
        if not has_oak_device:
            pytest.skip("No OAK device connected")
        
        # Act
        devices = OAKDeviceDiscovery.discover_devices(verbose=True)
        
        # Assert
        assert len(devices) > 0, "未检测到 OAK 设备，请连接设备后重试"
        
        for device in devices:
            assert device.mxid is not None
            assert len(device.mxid) > 0
            assert device.connection_status == ConnectionStatus.CONNECTED
            assert device.first_seen > 0
            assert device.last_seen > 0
            
            print(f"✓ 发现设备: {device.mxid} ({device.product_name})")
    
    # TODO: 添加更多硬件测试

