"""
OAK设备发现模块 - 精简版

只获取关键信息：设备名称、MxId、状态、产品名称
"""

import depthai as dai
from typing import List, Optional, Dict
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from core.dto.device_config_dto import (
    DeviceConfigDTO,
    DeviceType,
    ConnectionStatus
)


class OAKDeviceDiscovery:
    """OAK设备发现类 - 精简版"""
    
    @staticmethod
    def discover_devices() -> List[DeviceConfigDTO]:
        """
        发现所有可用的OAK设备，获取关键信息
        
        Returns:
            List[DeviceConfigDTO]: 发现的设备配置列表
        """
        print('正在搜索所有可用设备...\n')
        
        # 查询所有可用设备
        infos: List[dai.DeviceInfo] = dai.DeviceBootloader.getAllAvailableDevices()
        
        if len(infos) == 0:
            print("未找到任何可用设备。")
            return []
        
        discovered_devices = []
        
        for i, info in enumerate(infos):
            try:
                # 转换状态枚举
                state_str = str(info.state).split('X_LINK_')[1]
                connection_state = OAKDeviceDiscovery._parse_connection_state(state_str)
                
                print(f"发现设备 '{info.name}', MxId: '{info.mxid}', 状态: '{state_str}'")
                
                # 尝试获取产品名称（如果设备可连接）
                product_name = None
                if connection_state in [ConnectionStatus.CONNECTED, ConnectionStatus.UNBOOTED]:
                    product_name = OAKDeviceDiscovery._get_product_name(info)
                
                # 创建设备配置
                device_config = DeviceConfigDTO(
                    mxid=info.mxid,
                    alias=f"oak_device_{i+1:02d}",
                    device_name=info.name,
                    connection_state=connection_state,
                    product_name=product_name,
                    device_type=OAKDeviceDiscovery._detect_device_type(product_name or info.name),
                    enabled=True,
                    properties={
                        "discovered_at": str(dai.MonotonicClock.now()),
                        "auto_discovered": True
                    }
                )
                
                discovered_devices.append(device_config)
                
            except Exception as e:
                print(f"处理设备 {info.mxid} 时出错: {e}")
                continue
        
        print(f"\n总共发现 {len(discovered_devices)} 个设备")
        return discovered_devices
    
    @staticmethod
    def _get_product_name(device_info: dai.DeviceInfo) -> Optional[str]:
        """
        尝试获取产品名称（需要连接设备）
        
        Args:
            device_info: depthai设备信息对象
            
        Returns:
            Optional[str]: 产品名称，获取失败时返回None
        """
        try:
            with dai.Device(dai.Pipeline(), device_info, usb2Mode=True) as device:
                calib = device.readCalibration()
                eeprom = calib.getEepromData()
                return eeprom.productName
        except Exception as e:
            print(f"  获取产品名称失败: {e}")
            return None
    
    @staticmethod
    def _parse_connection_state(state_str: str) -> ConnectionStatus:
        """解析连接状态字符串"""
        state_mapping = {
            'UNBOOTED': ConnectionStatus.UNBOOTED,
            'BOOTLOADER': ConnectionStatus.BOOTLOADER,
            'BOOTED': ConnectionStatus.CONNECTED,
            'CONNECTED': ConnectionStatus.CONNECTED,
        }
        return state_mapping.get(state_str, ConnectionStatus.UNKNOWN)
    
    @staticmethod
    def _detect_device_type(device_name: str) -> DeviceType:
        """根据设备名称自动检测设备类型"""
        device_name_lower = device_name.lower()
        
        if 'oak-d-lite' in device_name_lower:
            return DeviceType.OAK_D_LITE
        elif 'oak-d-pro' in device_name_lower:
            return DeviceType.OAK_D_PRO
        elif 'oak-d-s2' in device_name_lower:
            return DeviceType.OAK_D_S2
        elif 'oak-d' in device_name_lower:
            return DeviceType.OAK_D
        elif 'oak-1' in device_name_lower:
            return DeviceType.OAK_1
        else:
            return DeviceType.UNKNOWN
    
    @staticmethod
    def print_device_summary(devices: List[DeviceConfigDTO]) -> None:
        """打印设备摘要信息"""
        if not devices:
            print("没有发现任何设备。")
            return
        
        print("\n=== 设备摘要（关键信息）===")
        for device in devices:
            print(f"\n设备别名: {device.alias}")
            print(f"  MX ID: {device.mxid}")
            print(f"  设备名称: {device.device_name}")
            print(f"  连接状态: {device.connection_state.value}")
            print(f"  产品名称: {device.product_name or 'N/A'}")
            print(f"  设备类型: {device.device_type.value}")
            print(f"  是否启用: {device.enabled}")


def main():
    """主函数 - 演示设备发现功能"""
    try:
        print("=== OAK设备发现（精简版）===")
        
        # 发现设备
        devices = OAKDeviceDiscovery.discover_devices()
        
        # 打印摘要
        OAKDeviceDiscovery.print_device_summary(devices)
        
        # 验证配置
        print(f"\n{'='*50}")
        print("=== 配置验证 ===")
        for device in devices:
            if device.is_data_valid():
                print(f"✅ {device.alias}: 配置有效")
            else:
                print(f"❌ {device.alias}: 配置无效")
                for error in device.get_validation_errors():
                    print(f"    - {error}")
        
        # 生成配置字典
        if devices:
            device_dict = {device.alias: device for device in devices}
            print(f"\n生成的设备配置字典包含 {len(device_dict)} 个设备")
            
    except Exception as e:
        print(f"设备发现过程中出错: {e}")


if __name__ == "__main__":
    main()
