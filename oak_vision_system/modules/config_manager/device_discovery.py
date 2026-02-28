"""
OAK设备发现模块

功能：
- 自动发现通过USB连接的OAK设备
- 获取设备元数据（MXid、类型、产品名称等）
- 返回结构化的设备元数据DTO供配置管理器使用

设计理念：
- 单一职责：仅负责硬件扫描和信息提取
- 无状态：所有方法为静态方法
- 纯API：不包含配置逻辑、用户交互、文件操作
"""

import depthai as dai
import time
from typing import List, Optional
import logging

from oak_vision_system.core.dto.config_dto import (
    DeviceMetadataDTO,
    ConnectionStatus,
)


class OAKDeviceDiscovery:
    """
    OAK设备发现类
    
    职责：
    - 扫描USB连接的OAK设备
    - 提取设备元数据（MXid、设备类型、产品名称等）
    - 返回标准化的DeviceMetadataDTO列表
    
    不包含：
    - 角色绑定逻辑（应在配置管理器中）
    - 配置文件操作（应在配置管理器中）
    - 用户交互（应在CLI工具中）
    """
    


    
    @staticmethod
    def get_all_available_devices(verbose: bool = False) -> List[dai.DeviceInfo]:
        """
        获取所有可用的OAK设备列表
        """
        logger = logging.getLogger(__name__)
        try: 
            # infos = dai.DeviceBootloader.getAllAvailableDevices()
            infos = dai.Device.getAllAvailableDevices()
        except Exception as e:
            if verbose:
                print(f"获取所有可用的OAK设备失败: {e}")
            logger.warning("getAllAvailableDevices failed: %s", e, exc_info=True)
            return []
        if not infos:
            if verbose:
                print("未发现任何设备")
            return []

        return infos

    # 公有接口：发现所有可用的OAK设备
    @staticmethod
    def discover_devices(verbose: bool = False) -> List[DeviceMetadataDTO]:
        """
        发现所有可用的OAK设备，并返回设备元数据列表
        
        Args:
            verbose: 是否打印发现过程详细信息（默认静默）
            
        Returns:
            List[DeviceMetadataDTO]: 发现的设备元数据列表
        """
        # 查询所有可用设备
        logger = logging.getLogger(__name__)
        logger.info("开始发现OAK设备")
        infos: List[dai.DeviceInfo] = OAKDeviceDiscovery.get_all_available_devices(verbose)
        
        if len(infos) == 0:
            logger.info("未发现任何可用的OAK设备")
            return []
        
        discovered_devices = []
        current_time = time.time()
        logger.debug("检测到候选设备数量: %d", len(infos))
        
        for i, info in enumerate(infos):
            try:
                # 解析连接状态
                state_str = str(info.state).split('X_LINK_')[1] if 'X_LINK_' in str(info.state) else str(info.state)
                connection_state = OAKDeviceDiscovery._parse_connection_state(state_str)
                logger.debug("处理设备[%s] 状态: %s -> %s", getattr(info, 'mxid', 'unknown'), state_str, connection_state.value)
                
                # 尝试获取产品名称（如果设备可连接）
                # 注意：DepthAI返回的状态可能是UNBOOTED/BOOTLOADER/BOOTED等
                # 这些状态下通常可以连接设备获取信息
                product_name = None
                if connection_state == ConnectionStatus.CONNECTED or state_str in ['UNBOOTED', 'BOOTED']:
                    product_name = OAKDeviceDiscovery._get_product_name(info, verbose=False)
                logger.debug("设备[%s] 产品名: %s", info.mxid, (product_name if product_name else "未知"))
                
                # 创建设备元数据
                metadata = DeviceMetadataDTO(
                    mxid=info.mxid,
                    product_name=product_name,
                    connection_status=connection_state,
                    notes=f"自动发现于 {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    first_seen=current_time,
                    last_seen=current_time,
                )
                
                discovered_devices.append(metadata)
                
            except Exception as e:
                if verbose:
                    print(f"处理设备 {info.mxid} 时出错: {e}")
                logger.warning("处理设备 %s 时出错: %s", getattr(info, 'mxid', 'unknown'), e, exc_info=True)
                continue
        
        # 统一打印发现结果
        logger.info("发现OAK设备 %d 台", len(discovered_devices))
        if verbose:
            OAKDeviceDiscovery._print_devices_summary(discovered_devices)
        
        return discovered_devices
    
    @staticmethod
    def _print_devices_summary(devices: List[DeviceMetadataDTO]) -> None:
        """
        打印设备发现摘要（内部私有方法）
        
        Args:
            devices: 发现的设备元数据列表
        """
        if not devices:
            print("未找到任何可用设备。")
            return
        
        print("=" * 80)
        print(f"设备发现摘要 - 共发现 {len(devices)} 台设备")
        print("=" * 80)
        
        for idx, device in enumerate(devices, start=1):
            print(f"\n[{idx}] 设备信息:")
            print(f"  MXid: {device.mxid}")
            print(f"  产品名: {device.product_name or '未知'}")
            print(f"  连接状态: {device.connection_status.value}")
            print(f"  首次发现: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(device.first_seen))}")
            if device.notes:
                print(f"  备注: {device.notes}")
        
        print("\n" + "=" * 80)
    
    @staticmethod
    def _get_product_name(device_info: dai.DeviceInfo, verbose: bool = True) -> Optional[str]:
        """
        尝试获取产品名称（需要连接设备）
        
        Args:
            device_info: depthai设备信息对象
            verbose: 是否打印详细信息
            
        Returns:
            Optional[str]: 产品名称，获取失败时返回None
        """
        logger = logging.getLogger(__name__)
        try:
            with dai.Device(dai.Pipeline(), device_info, usb2Mode=True) as device:
                calib = device.readCalibration()
                eeprom = calib.getEepromData()
                return eeprom.productName
        except Exception as e:
            if verbose:
                print(f"  获取产品名称失败: {e}")
            logger.debug("获取产品名称失败: %s", e, exc_info=True)
            return None
    
    @staticmethod
    def _parse_connection_state(state_str: str) -> ConnectionStatus:
        """
        解析连接状态字符串
        
        注意：DepthAI返回的状态（UNBOOTED/BOOTLOADER/BOOTED）
        与我们配置系统中的ConnectionStatus不完全对应。
        这里做简化映射，主要判断设备是否可用。
        """
        # BOOTED 和 CONNECTED 都表示设备已连接可用
        if state_str in ['BOOTED', 'CONNECTED']:
            return ConnectionStatus.CONNECTED
        # UNBOOTED 可以连接，但需要引导
        elif state_str == 'UNBOOTED':
            return ConnectionStatus.CONNECTED
        # BOOTLOADER 模式下设备在引导加载器中
        elif state_str == 'BOOTLOADER':
            return ConnectionStatus.CONNECTED
        else:
            return ConnectionStatus.UNKNOWN
    
   
    
    
 
