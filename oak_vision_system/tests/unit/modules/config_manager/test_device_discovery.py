"""
OAK设备发现器单元测试

测试策略：
- 使用 Mock 替身模拟 depthai 库，不依赖真实硬件
- 测试所有公有和私有方法的逻辑正确性
- 覆盖正常情况和异常情况
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import depthai as dai
import time

from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
from oak_vision_system.core.dto.config_dto import DeviceMetadataDTO, ConnectionStatus


# ==================== Fixtures ====================

@pytest.fixture
def mock_device_info():
    """单个 Mock 设备信息"""
    mock_device = Mock(spec=dai.DeviceInfo)
    mock_device.mxid = "14442C10D13D0D0000"
    mock_device.state = "X_LINK_BOOTED"
    return mock_device


@pytest.fixture
def mock_device_info_list():
    """多个 Mock 设备信息列表"""
    mock_device1 = Mock(spec=dai.DeviceInfo)
    mock_device1.mxid = "14442C10D13D0D0000"
    mock_device1.state = "X_LINK_BOOTED"
    
    mock_device2 = Mock(spec=dai.DeviceInfo)
    mock_device2.mxid = "14442C10D13D0D0001"
    mock_device2.state = "X_LINK_UNBOOTED"
    
    return [mock_device1, mock_device2]


@pytest.fixture
def mock_device_metadata_list():
    """预期的设备元数据 DTO 列表"""
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


# ==================== 1. get_all_available_devices 测试 ====================

class TestGetAllAvailableDevices:
    """测试 get_all_available_devices 方法"""
    
    @patch('depthai.DeviceBootloader.getAllAvailableDevices')
    def test_get_all_available_devices_with_devices(self, mock_get_all, mock_device_info_list):
        """测试：成功发现多个设备"""
        # Arrange
        mock_get_all.return_value = mock_device_info_list
        
        # Act
        devices = OAKDeviceDiscovery.get_all_available_devices(verbose=False)
        
        # Assert
        assert len(devices) == 2
        assert devices[0].mxid == "14442C10D13D0D0000"
        assert devices[1].mxid == "14442C10D13D0D0001"
        mock_get_all.assert_called_once()
    
    @patch('depthai.DeviceBootloader.getAllAvailableDevices')
    def test_get_all_available_devices_single_device(self, mock_get_all, mock_device_info):
        """测试：发现单个设备"""
        # Arrange
        mock_get_all.return_value = [mock_device_info]
        
        # Act
        devices = OAKDeviceDiscovery.get_all_available_devices(verbose=False)
        
        # Assert
        assert len(devices) == 1
        assert isinstance(devices[0], dai.DeviceInfo)
        assert devices[0].mxid == "14442C10D13D0D0000"
    
    @patch('depthai.DeviceBootloader.getAllAvailableDevices')
    def test_get_all_available_devices_no_devices(self, mock_get_all):
        """测试：没有设备时返回空列表"""
        # Arrange
        mock_get_all.return_value = []
        
        # Act
        devices = OAKDeviceDiscovery.get_all_available_devices(verbose=False)
        
        # Assert
        assert devices == []
        mock_get_all.assert_called_once()
    
    @patch('depthai.DeviceBootloader.getAllAvailableDevices')
    def test_get_all_available_devices_exception_handling(self, mock_get_all):
        """测试：获取设备时发生异常，应返回空列表"""
        # Arrange
        mock_get_all.side_effect = RuntimeError("USB communication error")
        
        # Act
        devices = OAKDeviceDiscovery.get_all_available_devices(verbose=False)
        
        # Assert
        assert devices == []
    
    @patch('depthai.DeviceBootloader.getAllAvailableDevices')
    def test_get_all_available_devices_verbose_mode(self, mock_get_all, capsys):
        """测试：verbose 模式下输出信息"""
        # Arrange
        mock_get_all.return_value = []
        
        # Act
        devices = OAKDeviceDiscovery.get_all_available_devices(verbose=True)
        
        # Assert
        captured = capsys.readouterr()
        assert "未发现任何设备" in captured.out
        assert devices == []


# ==================== 2. discover_devices 测试 ====================

class TestDiscoverDevices:
    """测试 discover_devices 方法"""
    
    @patch.object(OAKDeviceDiscovery, '_get_product_name')
    @patch.object(OAKDeviceDiscovery, 'get_all_available_devices')
    def test_discover_devices_success(self, mock_get_devices, mock_get_product, mock_device_info):
        """测试：成功发现设备并转换为 DTO"""
        # Arrange
        mock_get_devices.return_value = [mock_device_info]
        mock_get_product.return_value = "OAK-D"
        
        # Act
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        
        # Assert
        assert len(devices) == 1
        assert isinstance(devices[0], DeviceMetadataDTO)
        assert devices[0].mxid == "14442C10D13D0D0000"
        assert devices[0].product_name == "OAK-D"
        assert devices[0].connection_status == ConnectionStatus.CONNECTED
        assert devices[0].first_seen > 0
        assert devices[0].last_seen > 0
    
    @patch.object(OAKDeviceDiscovery, '_get_product_name')
    @patch.object(OAKDeviceDiscovery, 'get_all_available_devices')
    def test_discover_devices_multiple(self, mock_get_devices, mock_get_product, mock_device_info_list):
        """测试：发现多个设备"""
        # Arrange
        mock_get_devices.return_value = mock_device_info_list
        mock_get_product.side_effect = ["OAK-D", "OAK-D-Lite"]
        
        # Act
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        
        # Assert
        assert len(devices) == 2
        assert devices[0].mxid == "14442C10D13D0D0000"
        assert devices[0].product_name == "OAK-D"
        assert devices[1].mxid == "14442C10D13D0D0001"
        assert devices[1].product_name == "OAK-D-Lite"
    
    @patch.object(OAKDeviceDiscovery, 'get_all_available_devices')
    def test_discover_devices_no_devices(self, mock_get_devices):
        """测试：没有设备时返回空列表"""
        # Arrange
        mock_get_devices.return_value = []
        
        # Act
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        
        # Assert
        assert devices == []
    
    @patch.object(OAKDeviceDiscovery, '_get_product_name')
    @patch.object(OAKDeviceDiscovery, 'get_all_available_devices')
    def test_discover_devices_product_name_failure(self, mock_get_devices, mock_get_product, mock_device_info):
        """测试：获取产品名称失败时，产品名称为 None"""
        # Arrange
        mock_get_devices.return_value = [mock_device_info]
        mock_get_product.return_value = None
        
        # Act
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        
        # Assert
        assert len(devices) == 1
        assert devices[0].product_name is None
    
    @patch.object(OAKDeviceDiscovery, '_print_devices_summary')
    @patch.object(OAKDeviceDiscovery, '_get_product_name')
    @patch.object(OAKDeviceDiscovery, 'get_all_available_devices')
    def test_discover_devices_verbose_mode(self, mock_get_devices, mock_get_product, mock_print, mock_device_info):
        """测试：verbose 模式下调用打印摘要"""
        # Arrange
        mock_get_devices.return_value = [mock_device_info]
        mock_get_product.return_value = "OAK-D"
        
        # Act
        devices = OAKDeviceDiscovery.discover_devices(verbose=True)
        
        # Assert
        mock_print.assert_called_once()
        assert len(mock_print.call_args[0][0]) == 1  # 传入的设备列表长度为 1
    
    @patch.object(OAKDeviceDiscovery, '_get_product_name')
    @patch.object(OAKDeviceDiscovery, 'get_all_available_devices')
    def test_discover_devices_exception_handling(self, mock_get_devices, mock_get_product):
        """测试：处理设备时发生异常，应跳过该设备继续处理"""
        # Arrange
        mock_device1 = Mock(spec=dai.DeviceInfo)
        mock_device1.mxid = "device1"
        mock_device1.state = "X_LINK_BOOTED"
        
        mock_device2 = Mock(spec=dai.DeviceInfo)
        mock_device2.mxid = "device2"
        mock_device2.state = "X_LINK_BOOTED"
        
        mock_get_devices.return_value = [mock_device1, mock_device2]
        # 第一个设备处理失败，第二个成功
        mock_get_product.side_effect = [Exception("Error"), "OAK-D"]
        
        # Act
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        
        # Assert
        assert len(devices) == 1  # 只有第二个设备成功
        assert devices[0].mxid == "device2"


# ==================== 3. _parse_connection_state 测试 ====================

class TestParseConnectionState:
    """测试 _parse_connection_state 方法"""
    
    def test_parse_booted_state(self):
        """测试：解析 BOOTED 状态"""
        status = OAKDeviceDiscovery._parse_connection_state("BOOTED")
        assert status == ConnectionStatus.CONNECTED
    
    def test_parse_connected_state(self):
        """测试：解析 CONNECTED 状态"""
        status = OAKDeviceDiscovery._parse_connection_state("CONNECTED")
        assert status == ConnectionStatus.CONNECTED
    
    def test_parse_unbooted_state(self):
        """测试：解析 UNBOOTED 状态"""
        status = OAKDeviceDiscovery._parse_connection_state("UNBOOTED")
        assert status == ConnectionStatus.CONNECTED
    
    def test_parse_bootloader_state(self):
        """测试：解析 BOOTLOADER 状态"""
        status = OAKDeviceDiscovery._parse_connection_state("BOOTLOADER")
        assert status == ConnectionStatus.CONNECTED
    
    def test_parse_unknown_state(self):
        """测试：解析未知状态"""
        status = OAKDeviceDiscovery._parse_connection_state("UNKNOWN_STATE")
        assert status == ConnectionStatus.UNKNOWN
    
    def test_parse_empty_state(self):
        """测试：解析空字符串"""
        status = OAKDeviceDiscovery._parse_connection_state("")
        assert status == ConnectionStatus.UNKNOWN


# ==================== 4. _get_product_name 测试 ====================

class TestGetProductName:
    """测试 _get_product_name 方法"""
    
    @patch('depthai.Device')
    def test_get_product_name_success(self, mock_device_class):
        """测试：成功获取产品名称"""
        # Arrange
        mock_device_info = Mock(spec=dai.DeviceInfo)
        mock_device_info.mxid = "14442C10D13D0D0000"
        
        # Mock EEPROM 数据
        mock_eeprom = Mock()
        mock_eeprom.productName = "OAK-D"
        
        # Mock 校准数据
        mock_calib = Mock()
        mock_calib.getEepromData.return_value = mock_eeprom
        
        # Mock Device 上下文管理器
        mock_device = MagicMock()
        mock_device.__enter__.return_value.readCalibration.return_value = mock_calib
        mock_device_class.return_value = mock_device
        
        # Act
        product_name = OAKDeviceDiscovery._get_product_name(mock_device_info, verbose=False)
        
        # Assert
        assert product_name == "OAK-D"
        mock_device_class.assert_called_once()
    
    @patch('depthai.Device')
    def test_get_product_name_different_products(self, mock_device_class):
        """测试：获取不同产品名称"""
        # Arrange
        mock_device_info = Mock(spec=dai.DeviceInfo)
        
        for product in ["OAK-D", "OAK-D-Lite", "OAK-D-Pro"]:
            mock_eeprom = Mock()
            mock_eeprom.productName = product
            mock_calib = Mock()
            mock_calib.getEepromData.return_value = mock_eeprom
            mock_device = MagicMock()
            mock_device.__enter__.return_value.readCalibration.return_value = mock_calib
            mock_device_class.return_value = mock_device
            
            # Act
            product_name = OAKDeviceDiscovery._get_product_name(mock_device_info, verbose=False)
            
            # Assert
            assert product_name == product
    
    @patch('depthai.Device')
    def test_get_product_name_device_connection_error(self, mock_device_class):
        """测试：设备连接失败时返回 None"""
        # Arrange
        mock_device_info = Mock(spec=dai.DeviceInfo)
        mock_device_class.side_effect = RuntimeError("Device connection failed")
        
        # Act
        product_name = OAKDeviceDiscovery._get_product_name(mock_device_info, verbose=False)
        
        # Assert
        assert product_name is None
    
    @patch('depthai.Device')
    def test_get_product_name_read_calibration_error(self, mock_device_class):
        """测试：读取校准数据失败时返回 None"""
        # Arrange
        mock_device_info = Mock(spec=dai.DeviceInfo)
        mock_device = MagicMock()
        mock_device.__enter__.return_value.readCalibration.side_effect = Exception("Read error")
        mock_device_class.return_value = mock_device
        
        # Act
        product_name = OAKDeviceDiscovery._get_product_name(mock_device_info, verbose=False)
        
        # Assert
        assert product_name is None
    
    @patch('depthai.Device')
    def test_get_product_name_verbose_mode(self, mock_device_class, capsys):
        """测试：verbose 模式下输出错误信息"""
        # Arrange
        mock_device_info = Mock(spec=dai.DeviceInfo)
        mock_device_class.side_effect = RuntimeError("USB error")
        
        # Act
        product_name = OAKDeviceDiscovery._get_product_name(mock_device_info, verbose=True)
        
        # Assert
        captured = capsys.readouterr()
        assert "获取产品名称失败" in captured.out
        assert product_name is None


# ==================== 5. _print_devices_summary 测试 ====================

class TestPrintDevicesSummary:
    """测试 _print_devices_summary 方法"""
    
    def test_print_devices_summary_with_devices(self, mock_device_metadata_list, capsys):
        """测试：打印设备摘要（有设备）"""
        # Act
        OAKDeviceDiscovery._print_devices_summary(mock_device_metadata_list)
        
        # Assert
        captured = capsys.readouterr()
        assert "设备发现摘要" in captured.out
        assert "共发现 2 台设备" in captured.out
        assert "14442C10D13D0D0000" in captured.out
        assert "14442C10D13D0D0001" in captured.out
        assert "OAK-D" in captured.out
    
    def test_print_devices_summary_no_devices(self, capsys):
        """测试：打印设备摘要（无设备）"""
        # Act
        OAKDeviceDiscovery._print_devices_summary([])
        
        # Assert
        captured = capsys.readouterr()
        assert "未找到任何可用设备" in captured.out
    
    def test_print_devices_summary_single_device(self, capsys):
        """测试：打印单个设备摘要"""
        # Arrange
        single_device = [
            DeviceMetadataDTO(
                mxid="14442C10D13D0D0000",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
                notes="Test device",
                first_seen=time.time(),
                last_seen=time.time(),
            )
        ]
        
        # Act
        OAKDeviceDiscovery._print_devices_summary(single_device)
        
        # Assert
        captured = capsys.readouterr()
        assert "共发现 1 台设备" in captured.out
        assert "[1] 设备信息" in captured.out
    
    def test_print_devices_summary_no_product_name(self, capsys):
        """测试：打印设备摘要（产品名称未知）"""
        # Arrange
        device_without_name = [
            DeviceMetadataDTO(
                mxid="14442C10D13D0D0000",
                product_name=None,  # 产品名称未知
                connection_status=ConnectionStatus.CONNECTED,
                notes="Test device",
                first_seen=time.time(),
                last_seen=time.time(),
            )
        ]
        
        # Act
        OAKDeviceDiscovery._print_devices_summary(device_without_name)
        
        # Assert
        captured = capsys.readouterr()
        assert "产品名: 未知" in captured.out
