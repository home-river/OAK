"""
OAK设备管理模块 - 重构版

重构后的设备管理器，专注于：
1. 设备发现和连接管理
2. 配置文件的读取和写入
3. 设备状态监控
4. 与新的DTO架构集成

不负责：
- 数据处理逻辑
- 坐标变换
- 数据滤波
"""

import json
import logging
import tempfile
import os
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime

try:
    import depthai as dai
    import cv2
    DEPTHAI_AVAILABLE = True
except ImportError:
    DEPTHAI_AVAILABLE = False
    logging.warning("DepthAI not available, device discovery will be limited")

from ...core.dto.device_config_dto import (
    DeviceConfigDTO,
    DeviceManagerConfigDTO,
    OAKConfigDTO,
    SystemConfigDTO,
    DeviceType,
    ConnectionStatus
)
from ...core.dto.base_dto import BaseDTO


class OAKDeviceManager:
    """
    OAK设备管理器 - 重构版
    
    负责设备的发现、配置管理和状态监控
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化设备管理器
        
        Args:
            config_path: 配置文件路径，默认使用相对路径
        """
        # 配置文件路径
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(__file__).parent / "config" / "device_config.json"
        

        # 创建配置文件目录
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 设备管理配置
        self._config: Optional[DeviceManagerConfigDTO] = None
        
        # 设备别名到MXid的双向映射（快速查询）
        self._alias_to_mxid: Dict[str, str] = {}
        self._mxid_to_alias: Dict[str, str] = {}
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 初始化配置：先尝试加载，失败时使用默认配置
        self._initialize_config()
    
    def _initialize_config(self) -> None:
        """
        初始化配置：先尝试加载已有配置，失败时使用默认配置
        """
        # 尝试加载已有配置
        if not self.load_config():
            self.logger.info("配置文件不存在或加载失败，使用默认配置")
            self._initialize_default_config()
    
    def _initialize_default_config(self) -> None:
        """初始化默认的设备管理配置"""
        self._config = DeviceManagerConfigDTO(
            config_version="2.0.0",
            oak_config=OAKConfigDTO(),  # 使用默认OAK配置
            system=SystemConfigDTO(),   # 使用默认系统配置
            devices={}  # 空的设备字典
        )
    
    # ==================== 设备发现和连接管理 ====================
    
    def discover_devices(self) -> List[DeviceConfigDTO]:
        """
        发现所有可用的OAK设备
        
        Returns:
            List[DeviceConfigDTO]: 发现的设备配置列表
        """
        if not DEPTHAI_AVAILABLE:
            self.logger.warning("DepthAI不可用，无法进行设备发现")
            return []
        
        try:
            self.logger.info("开始设备发现...")
            
            # 使用depthai发现设备
            device_infos = dai.DeviceBootloader.getAllAvailableDevices()
            
            if not device_infos:
                self.logger.info("未发现任何设备")
                return []
            
            discovered_devices = []
            
            for i, info in enumerate(device_infos):
                try:
                    # 解析连接状态
                    state_str = str(info.state).split('X_LINK_')[1]
                    connection_state = self._parse_connection_status(state_str)
                    
                    # 推断设备类型
                    device_type = self._infer_device_type(info.name)
                    
                    # 尝试获取产品名称
                    product_name = self._get_product_name(info) if connection_state != ConnectionStatus.DISCONNECTED else None
                    
                    # 生成别名
                    alias = f"oak_device_{i+1:02d}"
                    
                    # 创建设备配置
                    device_config = DeviceConfigDTO(
                        mxid=info.mxid,
                        alias=alias,
                        device_type=device_type,
                        device_name=info.name,
                        connection_state=connection_state,
                        product_name=product_name,
                        enabled=True,
                        properties={
                            "discovered_at": datetime.now().isoformat(),
                            "auto_discovered": True
                        }
                    )
                    
                    discovered_devices.append(device_config)
                    self.logger.info(f"发现设备: {alias} ({info.mxid}) - {device_type.value}")
                    
                except Exception as e:
                    self.logger.error(f"处理设备 {info.mxid} 时出错: {e}")
                    continue
            
            self.logger.info(f"设备发现完成，共发现 {len(discovered_devices)} 个设备")
            return discovered_devices
            
        except Exception as e:
            self.logger.error(f"设备发现失败: {e}")
            return []
    
    def _infer_device_type(self, device_name: str) -> DeviceType:
        """根据设备名称推断设备类型"""
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
    
    def _parse_connection_status(self, state_str: str) -> ConnectionStatus:
        """解析连接状态"""
        state_mapping = {
            'UNBOOTED': ConnectionStatus.UNBOOTED,
            'BOOTLOADER': ConnectionStatus.BOOTLOADER,
            'BOOTED': ConnectionStatus.CONNECTED,
            'CONNECTED': ConnectionStatus.CONNECTED,
        }
        return state_mapping.get(state_str, ConnectionStatus.UNKNOWN)
    
    def _get_product_name(self, device_info) -> Optional[str]:
        """尝试获取产品名称"""
        if not DEPTHAI_AVAILABLE:
            return None
            
        try:
            with dai.Device(dai.Pipeline(), device_info, usb2Mode=True) as device:
                calib = device.readCalibration()
                eeprom = calib.getEepromData()
                return eeprom.productName
        except Exception as e:
            self.logger.debug(f"获取产品名称失败: {e}")
            return None
    
    def check_device_connection(self, mxid: str) -> ConnectionStatus:
        """
        检查指定设备的连接状态
        
        Args:
            mxid: 设备MXid
            
        Returns:
            设备连接状态
        """
        if not DEPTHAI_AVAILABLE:
            return ConnectionStatus.UNKNOWN
        
        try:
            device_infos = dai.DeviceBootloader.getAllAvailableDevices()
            
            for info in device_infos:
                if info.mxid == mxid:
                    state_str = str(info.state).split('X_LINK_')[1]
                    return self._parse_connection_status(state_str)
            
            return ConnectionStatus.DISCONNECTED
            
        except Exception as e:
            self.logger.error(f"检查设备连接状态失败: {e}")
            return ConnectionStatus.UNKNOWN
    
    # ==================== 配置文件操作 ====================
    
    def load_config(self, path: Optional[str] = None) -> bool:
        """
        从JSON文件加载配置
        
        Args:
            path: 配置文件路径，默认使用初始化时的路径
            
        Returns:
            是否成功加载
        """
        config_path = Path(path) if path else self.config_path
        
        try:
            if not config_path.exists():
                self.logger.info(f"配置文件不存在: {config_path}，使用默认配置")
                return True
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 从字典创建DTO
            self._config = DeviceManagerConfigDTO.from_dict(config_data)
            
            # 同步别名映射
            self._sync_alias_mappings()
            
            self.logger.info(f"配置加载成功: {config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            return False
    
    def save_config(self, path: Optional[str] = None, atomic: bool = True) -> bool:
        """
        保存设备配置到JSON文件
        
        Args:
            path: 配置文件路径，默认使用初始化时的路径
            atomic: 是否使用原子化写入
            
        Returns:
            是否成功保存
        """
        config_path = Path(path) if path else self.config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if self._config is None:
                self.logger.warning("没有配置数据可保存")
                return False
            
            config_dict = self._config.to_dict()
            
            if atomic:
                # 原子化写入
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding='utf-8',
                    dir=config_path.parent,
                    delete=False,
                    suffix='.tmp'
                ) as temp_file:
                    json.dump(config_dict, temp_file, indent=2, ensure_ascii=False)
                    temp_path = temp_file.name
                
                # 原子化移动
                os.replace(temp_path, config_path)
            else:
                # 直接写入
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"配置保存成功: {config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"配置保存失败: {e}")
            # 清理临时文件
            if atomic and 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except:
                    pass
            return False
    
    def _sync_alias_mappings(self) -> None:
        """同步别名映射"""
        self._alias_to_mxid.clear()
        self._mxid_to_alias.clear()
        
        if self._config and self._config.devices:
            for alias, device_config in self._config.devices.items():
                mxid = device_config.mxid
                self._alias_to_mxid[alias] = mxid
                self._mxid_to_alias[mxid] = alias
    
    # ==================== 设备配置操作 ====================
    
    def add_device(self, device_config: DeviceConfigDTO) -> bool:
        """
        添加设备配置
        
        Args:
            device_config: 设备配置DTO
            
        Returns:
            是否成功添加
        """
        try:
            if self._config is None:
                self._initialize_default_config()
            
            # 检查重复
            if device_config.alias in self._config.devices:
                raise ValueError(f"别名 '{device_config.alias}' 已存在")
            
            if device_config.mxid in self._mxid_to_alias:
                raise ValueError(f"MXid '{device_config.mxid}' 已存在")
            
            # 验证DTO
            if not device_config.is_data_valid():
                raise ValueError(f"设备配置无效: {device_config.get_validation_errors()}")
            
            # 添加到配置
            updated_devices = dict(self._config.devices)
            updated_devices[device_config.alias] = device_config
            
            # 创建新的配置
            self._config = DeviceManagerConfigDTO(
                config_version=self._config.config_version,
                oak_config=self._config.oak_config,
                system=self._config.system,
                data_processing=self._config.data_processing,
                devices=updated_devices
            )
            
            # 更新别名映射
            self._alias_to_mxid[device_config.alias] = device_config.mxid
            self._mxid_to_alias[device_config.mxid] = device_config.alias
            
            self.logger.info(f"设备添加成功: {device_config.alias} ({device_config.mxid})")
            return True
            
        except Exception as e:
            self.logger.error(f"添加设备失败: {e}")
            return False
    
    def remove_device(self, alias: str) -> bool:
        """
        移除设备配置
        
        Args:
            alias: 设备别名
            
        Returns:
            是否成功移除
        """
        try:
            if self._config is None or alias not in self._config.devices:
                raise ValueError(f"设备别名不存在: {alias}")
            
            # 获取MXid用于清理映射
            mxid = self._config.devices[alias].mxid
            
            # 移除设备
            updated_devices = dict(self._config.devices)
            del updated_devices[alias]
            
            # 创建新的配置
            self._config = DeviceManagerConfigDTO(
                config_version=self._config.config_version,
                oak_config=self._config.oak_config,
                system=self._config.system,
                data_processing=self._config.data_processing,
                devices=updated_devices
            )
            
            # 清理别名映射
            if alias in self._alias_to_mxid:
                del self._alias_to_mxid[alias]
            if mxid in self._mxid_to_alias:
                del self._mxid_to_alias[mxid]
            
            self.logger.info(f"设备移除成功: {alias}")
            return True
            
        except Exception as e:
            self.logger.error(f"移除设备失败: {e}")
            return False
    
    def get_device_config(self, alias: str) -> Optional[DeviceConfigDTO]:
        """
        获取设备配置
        
        Args:
            alias: 设备别名
            
        Returns:
            设备配置DTO，不存在时返回None
        """
        if self._config is None:
            return None
        return self._config.devices.get(alias)
    
    def list_devices(self) -> List[DeviceConfigDTO]:
        """获取所有设备配置列表"""
        if self._config is None or not self._config.devices:
            return []
        return list(self._config.devices.values())
    
    def list_enabled_devices(self) -> List[DeviceConfigDTO]:
        """获取所有启用的设备配置列表"""
        return [device for device in self.list_devices() if device.enabled]
    
    # ==================== OAK配置管理 ====================
    
    def get_oak_config(self) -> OAKConfigDTO:
        """
        获取OAK配置
        
        Returns:
            OAK配置DTO
        """
        if self._config is None:
            self._initialize_default_config()
        return self._config.oak_config
    
    def set_oak_config(self, oak_config: OAKConfigDTO) -> bool:
        """
        设置OAK配置
        
        Args:
            oak_config: OAK配置DTO
            
        Returns:
            是否成功设置
        """
        try:
            if self._config is None:
                self._initialize_default_config()
            
            # 验证配置
            if not oak_config.is_data_valid():
                raise ValueError(f"OAK配置无效: {oak_config.get_validation_errors()}")
            
            # 更新配置
            self._config = DeviceManagerConfigDTO(
                config_version=self._config.config_version,
                oak_config=oak_config,
                system=self._config.system,
                data_processing=self._config.data_processing,
                devices=self._config.devices
            )
            
            self.logger.info("OAK配置更新成功")
            return True
            
        except Exception as e:
            self.logger.error(f"设置OAK配置失败: {e}")
            return False
    
    def get_system_config(self) -> SystemConfigDTO:
        """获取系统配置"""
        if self._config is None:
            self._initialize_default_config()
        return self._config.system
    
    def set_system_config(self, system_config: SystemConfigDTO) -> bool:
        """设置系统配置"""
        try:
            if self._config is None:
                self._initialize_default_config()
            
            # 验证配置
            if not system_config.is_data_valid():
                raise ValueError(f"系统配置无效: {system_config.get_validation_errors()}")
            
            # 更新配置
            self._config = DeviceManagerConfigDTO(
                config_version=self._config.config_version,
                oak_config=self._config.oak_config,
                system=system_config,
                data_processing=self._config.data_processing,
                devices=self._config.devices
            )
            
            self.logger.info("系统配置更新成功")
            return True
            
        except Exception as e:
            self.logger.error(f"设置系统配置失败: {e}")
            return False
    
    # ==================== 便捷方法 ====================
    
    def get_device_count(self) -> int:
        """获取设备数量"""
        return len(self.list_devices())
    
    def get_enabled_device_count(self) -> int:
        """获取启用设备数量"""
        return len(self.list_enabled_devices())
    
    def get_aliases(self) -> List[str]:
        """获取所有设备别名列表"""
        if self._config is None:
            return []
        return list(self._config.devices.keys())
    
    def mxid_to_alias(self, mxid: str) -> Optional[str]:
        """MXid转别名"""
        return self._mxid_to_alias.get(mxid)
    
    def alias_to_mxid(self, alias: str) -> Optional[str]:
        """别名转MXid"""
        return self._alias_to_mxid.get(alias)
    
    def auto_discover_and_add(self) -> int:
        """
        自动发现设备并添加到配置中
        
        Returns:
            成功添加的设备数量
        """
        discovered_devices = self.discover_devices()
        added_count = 0
        
        for device_config in discovered_devices:
            # 检查是否已存在
            if device_config.mxid not in self._mxid_to_alias:
                if self.add_device(device_config):
                    added_count += 1
        
        self.logger.info(f"自动发现并添加了 {added_count} 个设备")
        return added_count
    
    # ==================== 交互式设备配置 ====================
    
    def interactive_device_binding(self, 
                                 predefined_aliases: Optional[List[str]] = None,
                                 save_after_binding: bool = True) -> bool:
        """
        交互式设备别名绑定流程
        
        流程：
        1. 获取所有连接的设备
        2. 依次显示每个设备的RGB图像
        3. 用户观察后输入别名或选择预定义别名
        4. 完成后保存配置
        
        Args:
            predefined_aliases: 预定义的别名列表，用户可以选择
            save_after_binding: 绑定完成后是否自动保存配置
            
        Returns:
            是否成功完成绑定
        """
        if not DEPTHAI_AVAILABLE:
            self.logger.error("DepthAI不可用，无法进行交互式绑定")
            return False
        
        try:
            # 1. 获取所有连接的设备
            print("🔍 正在搜索连接的设备...")
            device_infos = dai.DeviceBootloader.getAllAvailableDevices()
            
            if not device_infos:
                print("❌ 未发现任何连接的设备")
                return False
            
            # 过滤出可连接的设备
            connectable_devices = []
            for info in device_infos:
                state_str = str(info.state).split('X_LINK_')[1]
                if state_str in ['UNBOOTED', 'BOOTED', 'CONNECTED']:
                    connectable_devices.append(info)
            
            if not connectable_devices:
                print("❌ 没有可连接的设备")
                return False
            
            print(f"✅ 发现 {len(connectable_devices)} 个可连接的设备")
            print("=" * 50)
            
            # 存储绑定结果
            bound_devices = []
            
            # 2. 依次处理每个设备
            for i, device_info in enumerate(connectable_devices):
                print(f"\n📷 正在处理设备 {i+1}/{len(connectable_devices)}")
                print(f"   MX ID: {device_info.mxid}")
                print(f"   设备名: {device_info.name}")
                
                # 显示RGB预览
                print("   正在启动RGB预览...")
                device_config = self._show_device_preview_and_get_alias(
                    device_info, 
                    predefined_aliases,
                    i + 1
                )
                
                if device_config:
                    bound_devices.append(device_config)
                    print(f"✅ 设备绑定成功: {device_config.alias}")
                else:
                    print("⚠️  跳过该设备")
                
                print("-" * 30)
            
            # 3. 添加绑定的设备到配置
            if bound_devices:
                success_count = 0
                for device_config in bound_devices:
                    if self.add_device(device_config):
                        success_count += 1
                
                print(f"\n🎉 成功绑定 {success_count}/{len(bound_devices)} 个设备")
                
                # 4. 保存配置
                if save_after_binding and success_count > 0:
                    if self.save_config():
                        print("💾 配置已保存")
                    else:
                        print("⚠️  配置保存失败")
                
                return success_count > 0
            else:
                print("\n❌ 没有成功绑定任何设备")
                return False
                
        except Exception as e:
            self.logger.error(f"交互式设备绑定失败: {e}")
            print(f"❌ 绑定过程出错: {e}")
            return False
    
    def _show_device_preview_and_get_alias(self, 
                                         device_info, 
                                         predefined_aliases: Optional[List[str]],
                                         device_index: int) -> Optional[DeviceConfigDTO]:
        """
        显示设备预览并获取用户输入的别名
        
        Args:
            device_info: depthai设备信息
            predefined_aliases: 预定义别名列表
            device_index: 设备索引（用于显示）
            
        Returns:
            配置好的DeviceConfigDTO，取消时返回None
        """
        try:
            print(f"   启动设备预览窗口...")
            print(f"   请观察RGB图像以确定设备位置")
            print(f"   按 'q' 键退出预览并进行别名设置")
            
            # 显示RGB预览（这里调用您稍后提供的pipeline方法）
            preview_result = self._create_preview_pipeline(device_info)
            
            if not preview_result:
                print("   ⚠️  预览启动失败")
                return None
            
            # 获取设备类型和产品名称
            device_type = self._infer_device_type(device_info.name)
            product_name = self._get_product_name(device_info)
            
            # 获取用户输入的别名
            alias = self._get_user_alias_input(predefined_aliases, device_index)
            
            if not alias:
                return None
            
            # 创建设备配置
            device_config = DeviceConfigDTO(
                mxid=device_info.mxid,
                alias=alias,
                device_type=device_type,
                device_name=device_info.name,
                connection_state=ConnectionStatus.CONNECTED,
                product_name=product_name,
                enabled=True,
                properties={
                    "configured_at": datetime.now().isoformat(),
                    "interactive_binding": True,
                    "device_index": device_index
                }
            )
            
            return device_config
            
        except Exception as e:
            print(f"   ❌ 设备预览失败: {e}")
            return None
    
    def _create_preview_pipeline(self, device_info) -> bool:
        """
        创建预览pipeline并显示RGB图像
        
        Args:
            device_info: depthai设备信息
            
        Returns:
            是否成功显示预览
        """
        try:
            # 创建RGB预览pipeline
            pipeline = dai.Pipeline()

            # Define source and output
            camRgb = pipeline.create(dai.node.ColorCamera)
            xoutRgb = pipeline.create(dai.node.XLinkOut)

            xoutRgb.setStreamName("rgb")

            # Properties
            camRgb.setPreviewSize(640, 480)
            camRgb.setInterleaved(False)
            camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
            camRgb.setFps(30)

            # Linking
            camRgb.preview.link(xoutRgb.input)
            
            # 通过 MxId 连接设备
            with dai.Device(pipeline, device_info.mxid) as device:
                print(f"   ✅ 已连接到设备: {device_info.mxid}")
                
                # 显示设备信息
                print(f'   连接的相机: {device.getConnectedCameraFeatures()}')
                print(f'   USB速度: {device.getUsbSpeed().name}')
                print(f'   设备名称: {device.getDeviceName()}')
                print(f'   产品名称: {device.getProductName()}')
                print()
                print("   📷 RGB预览已启动")
                print("   💡 按 'q' 键退出预览")
                print("   " + "-" * 40)

                # Output queue will be used to get the rgb frames from the output defined above
                qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)

                while True:
                    inRgb = qRgb.get()  # blocking call, will wait until a new data has arrived

                    # Retrieve 'bgr' (opencv format) frame
                    frame = inRgb.getCvFrame()
                    
                    # 添加设备信息到图像上
                    cv2.putText(frame, f"Device: {device_info.mxid}", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(frame, "Press 'q' to quit", (10, frame.shape[0] - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    cv2.putText(frame, f"Product: {device.getProductName()}", (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                    cv2.imshow(f"RGB Preview - {device_info.mxid}", frame)

                    if cv2.waitKey(1) == ord('q'):
                        break
                
                cv2.destroyAllWindows()
                print("   ✅ 预览已关闭")
                return True
                
        except Exception as e:
            print(f"   ❌ 预览启动失败: {e}")
            return False
    
    def _get_user_alias_input(self, 
                             predefined_aliases: Optional[List[str]], 
                             device_index: int) -> Optional[str]:
        """
        获取用户输入的设备别名
        
        Args:
            predefined_aliases: 预定义别名列表
            device_index: 设备索引
            
        Returns:
            用户选择的别名，取消时返回None
        """
        print(f"\n📝 请为设备 #{device_index} 设置别名:")
        
        # 显示预定义别名选项
        if predefined_aliases:
            print("   预定义别名选项:")
            for i, alias in enumerate(predefined_aliases, 1):
                # 检查别名是否已被使用
                if alias in self._alias_to_mxid:
                    print(f"   {i}. {alias} (已使用)")
                else:
                    print(f"   {i}. {alias}")
            print(f"   {len(predefined_aliases) + 1}. 自定义别名")
            print("   0. 跳过此设备")
            
            while True:
                try:
                    choice = input("   请选择 (0-{0}): ".format(len(predefined_aliases) + 1))
                    choice_num = int(choice)
                    
                    if choice_num == 0:
                        return None
                    elif choice_num == len(predefined_aliases) + 1:
                        # 自定义别名
                        break
                    elif 1 <= choice_num <= len(predefined_aliases):
                        selected_alias = predefined_aliases[choice_num - 1]
                        if selected_alias in self._alias_to_mxid:
                            print("   ⚠️  该别名已被使用，请选择其他选项")
                            continue
                        return selected_alias
                    else:
                        print("   ❌ 无效选择，请重新输入")
                        continue
                        
                except ValueError:
                    print("   ❌ 请输入有效数字")
                    continue
        
        # 自定义别名输入
        while True:
            alias = input("   请输入自定义别名 (或输入 'skip' 跳过): ").strip()
            
            if alias.lower() == 'skip':
                return None
            
            if not alias:
                print("   ❌ 别名不能为空")
                continue
            
            if alias in self._alias_to_mxid:
                print(f"   ⚠️  别名 '{alias}' 已被使用，请使用其他名称")
                continue
            
            # 简单验证别名格式
            if not alias.replace('_', '').replace('-', '').isalnum():
                print("   ⚠️  别名只能包含字母、数字、下划线和连字符")
                continue
            
            return alias