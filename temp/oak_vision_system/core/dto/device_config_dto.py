"""
设备配置相关的DTO定义

模块化配置系统，包含以下DTO类：
- DetectionConfigDTO: 检测模型和参数配置
- SystemConfigDTO: 系统功能配置（CAN通信等）
- DisplayConfigDTO: 显示和交互配置
- HardwareConfigDTO: 性能和硬件配置
- DataProcessingConfigDTO: 数据处理配置（预留扩展）
- DeviceConfigDTO: 设备配置
- OAKConfigDTO: 统一的OAK配置管理
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

from .base_dto import (
    BaseDTO,
    validate_string_length,
    validate_numeric_range,
)


class DeviceType(Enum):
    """OAK设备类型枚举"""
    OAK_D = "OAK-D"
    OAK_D_LITE = "OAK-D-Lite"
    OAK_D_PRO = "OAK-D-Pro"
    OAK_D_S2 = "OAK-D-S2"
    OAK_1 = "OAK-1"
    UNKNOWN = "Unknown"


class ConnectionStatus(Enum):
    """设备连接状态枚举"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    BOOTLOADER = "bootloader"
    UNBOOTED = "unbooted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class OAKConfigDTO(BaseDTO):
    """OAK设备配置数据传输对象 - 集中管理所有OAK相关配置"""
    
    # ===== 检测模型配置 =====
    model_path: Optional[str] = None
    label_map: List[str] = field(default_factory=lambda: ["durian", "person"])
    num_classes: int = 2
    confidence_threshold: float = 0.5      # 置信度阈值
    
    # ===== 检测参数配置 =====
    input_resolution: Tuple[int, int] = (512, 288)
    nms_threshold: float = 0.4      # 非极大值抑制阈值
    max_detections: int = -1  # -1表示不限制
    depth_min_threshold: float = 400.0  # mm
    depth_max_threshold: float = 7000.0  # mm
    
    # ===== 相机配置 =====
    preview_resolution: Tuple[int, int] = (512, 288)
    hardware_fps: int = 30      # 硬件帧率上限
    usb2_mode: bool = True
    
    # ===== 深度图配置 =====
    enable_depth_display: bool = True       # 是否启用深度图显示
    depth_display_resolution: Tuple[int, int] = (640, 480)
    depth_bbox_scale_factor: float = 0.5    # 深度图边界框缩放因子
    
    # ===== 显示配置 =====
    enable_fullscreen: bool = False       # 是否启用全屏显示
    default_display_mode: str = "combined"  # "oak_left", "oak_right", "combined"
    
    # ===== 队列配置 =====
    queue_max_size: int = 4       # 队列最大大小
    queue_blocking: bool = False       # 队列是否阻塞
    
    def _validate_data(self) -> List[str]:
        """OAK配置数据验证"""
        errors = []
        
        # ===== 检测模型验证 =====
        if self.model_path is not None:
            errors.extend(validate_string_length(
                self.model_path, 'model_path', min_length=1, max_length=500
            ))
        
        if not isinstance(self.label_map, list):
            errors.append("label_map必须为列表类型")
        elif len(self.label_map) == 0:
            errors.append("label_map不能为空列表")
        elif not all(isinstance(label, str) for label in self.label_map):
            errors.append("label_map中的所有元素必须为字符串类型")
        
        errors.extend(validate_numeric_range(
            self.num_classes, 'num_classes', min_value=1, max_value=100
        ))
        
        if isinstance(self.label_map, list) and len(self.label_map) != self.num_classes:
            errors.append(f"num_classes({self.num_classes})与label_map长度({len(self.label_map)})不一致")
        
        errors.extend(validate_numeric_range(
            self.confidence_threshold, 'confidence_threshold',
            min_value=0.0, max_value=1.0
        ))
        
        # ===== 检测参数验证 =====
        if not (isinstance(self.input_resolution, tuple) and 
                len(self.input_resolution) == 2 and
                all(isinstance(x, int) and x > 0 for x in self.input_resolution)):
            errors.append("input_resolution必须为正整数二元组 (width, height)")
        
        errors.extend(validate_numeric_range(
            self.nms_threshold, 'nms_threshold',
            min_value=0.0, max_value=1.0
        ))
        
        if self.max_detections != -1:
            errors.extend(validate_numeric_range(
                self.max_detections, 'max_detections',
                min_value=1, max_value=100
            ))
        elif not isinstance(self.max_detections, int):
            errors.append("max_detections必须为整数类型")
        
        
        errors.extend(validate_numeric_range(
            self.depth_min_threshold, 'depth_min_threshold',
            min_value=0.0, max_value=10000.0
        ))
        
        errors.extend(validate_numeric_range(
            self.depth_max_threshold, 'depth_max_threshold',
            min_value=0.0, max_value=10000.0
        ))
        
        if (isinstance(self.depth_min_threshold, (int, float)) and 
            isinstance(self.depth_max_threshold, (int, float)) and
            self.depth_min_threshold >= self.depth_max_threshold):
            errors.append("depth_min_threshold必须小于depth_max_threshold")
        
        # ===== 相机配置验证 =====
        if not (isinstance(self.preview_resolution, tuple) and 
                len(self.preview_resolution) == 2 and
                all(isinstance(x, int) and x > 0 for x in self.preview_resolution)):
            errors.append("preview_resolution必须为正整数二元组 (width, height)")
        
        errors.extend(validate_numeric_range(
            self.hardware_fps, 'hardware_fps',
            min_value=1, max_value=120
        ))
        
        # ===== 深度图配置验证 =====
        if not (isinstance(self.depth_display_resolution, tuple) and 
                len(self.depth_display_resolution) == 2 and
                all(isinstance(x, int) and x > 0 for x in self.depth_display_resolution)):
            errors.append("depth_display_resolution必须为正整数二元组 (width, height)")
        
        errors.extend(validate_numeric_range(
            self.depth_bbox_scale_factor, 'depth_bbox_scale_factor',
            min_value=0.1, max_value=5.0
        ))
        
        # ===== 显示配置验证 =====
        valid_modes = ["rgb", "depth", "combined"]
        if self.default_display_mode not in valid_modes:
            errors.append(f"default_display_mode必须为有效值之一: {valid_modes}")
        
        # ===== 队列配置验证 =====
        errors.extend(validate_numeric_range(
            self.queue_max_size, 'queue_max_size',
            min_value=1, max_value=50
        ))
        
        return errors


@dataclass(frozen=True)
class SystemConfigDTO(BaseDTO):
    """系统功能配置数据传输对象 - CAN通信和警报等系统级功能"""
    
    # 功能开关
    enable_can: bool = False  # 是否启用CAN通信
    enable_alert: bool = False # 是否启用警报
    
    # CAN通信配置
    can_bitrate: int = 250000 # CAN波特率
    can_interface: str = 'socketcan' # CAN接口
    can_channel: str = 'can0' # CAN通道
    
    # 人员检测超时配置（CAN通信相关）
    person_timeout_seconds: float = 5.0
    
    def _validate_data(self) -> List[str]:
        """系统功能配置数据验证"""
        errors = []
        
        # 验证CAN波特率
        valid_bitrates = [20000, 50000, 100000, 125000, 250000, 500000, 800000, 1000000]
        if self.can_bitrate not in valid_bitrates:
            errors.append(f"can_bitrate必须为有效值之一: {valid_bitrates}")
        
        # 验证CAN接口
        errors.extend(validate_string_length(
            self.can_interface, 'can_interface', min_length=1, max_length=50
        ))
        
        # 验证CAN通道
        errors.extend(validate_string_length(
            self.can_channel, 'can_channel', min_length=1, max_length=50
        ))
        
        # 验证人员超时时间
        errors.extend(validate_numeric_range(
            self.person_timeout_seconds, 'person_timeout_seconds',
            min_value=0.1, max_value=60.0
        ))
        
        return errors


@dataclass(frozen=True)
class DataProcessingConfigDTO(BaseDTO):
    """数据处理配置数据传输对象 - 预留扩展空间"""
    
    # 坐标变换参数（预留）
    coordinate_transform_params: Optional[Dict[str, Any]] = None
    
    # 滤波器参数（预留）
    filter_params: Optional[Dict[str, Any]] = None
    
    # 预留更多数据处理参数空间
    processing_pipeline_config: Optional[Dict[str, Any]] = None
    calibration_params: Optional[Dict[str, Any]] = None
    roi_config: Optional[Dict[str, Any]] = None
    
    def _validate_data(self) -> List[str]:
        """数据处理配置数据验证"""
        errors = []
        
        # 验证各个参数字典的类型
        param_fields = [
            'coordinate_transform_params',
            'filter_params', 
            'processing_pipeline_config',
            'calibration_params',
            'roi_config'
        ]
        
        for field_name in param_fields:
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, dict):
                errors.append(f"{field_name}必须为字典类型或None")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        # 为None的字典字段设置空字典默认值
        if self.coordinate_transform_params is None:
            object.__setattr__(self, 'coordinate_transform_params', {})
        
        if self.filter_params is None:
            object.__setattr__(self, 'filter_params', {})
        
        if self.processing_pipeline_config is None:
            object.__setattr__(self, 'processing_pipeline_config', {})
        
        if self.calibration_params is None:
            object.__setattr__(self, 'calibration_params', {})
        
        if self.roi_config is None:
            object.__setattr__(self, 'roi_config', {})


@dataclass(frozen=True)
class DeviceConfigDTO(BaseDTO):
    """设备配置数据传输对象"""
    
    mxid: str  # 设备MXid
    alias: str  # 设备别名
    device_type: DeviceType = DeviceType.UNKNOWN  # 设备类型
    enabled: bool = True  # 是否启用该设备
    
    # 设备发现的关键信息
    device_name: Optional[str] = None  # 设备名称 (从dai.DeviceInfo.name获取)
    connection_state: ConnectionStatus = ConnectionStatus.UNKNOWN  # 连接状态
    product_name: Optional[str] = None  # 产品名称 (从EEPROM获取)
    
    properties: Optional[Dict[str, Any]] = None  # 设备属性（扩展字段）
    
    def _validate_data(self) -> List[str]:
        """设备配置数据验证"""
        errors = []
        
        # 验证MXid
        errors.extend(validate_string_length(
            self.mxid, 'mxid', min_length=10, max_length=100
        ))
        
        # 验证别名
        errors.extend(validate_string_length(
            self.alias, 'alias', min_length=1, max_length=50
        ))
        
        # 验证设备类型
        if not isinstance(self.device_type, DeviceType):
            errors.append("device_type必须为DeviceType枚举类型")
        
        # 验证连接状态
        if not isinstance(self.connection_state, ConnectionStatus):
            errors.append("connection_state必须为ConnectionStatus枚举类型")
        
        # 验证设备名称
        if self.device_name is not None:
            errors.extend(validate_string_length(
                self.device_name, 'device_name', min_length=1, max_length=100
            ))
        
        # 验证产品名称
        if self.product_name is not None:
            errors.extend(validate_string_length(
                self.product_name, 'product_name', min_length=1, max_length=100
            ))
        
        # 验证属性字典
        if self.properties is not None:
            if not isinstance(self.properties, dict):
                errors.append("properties必须为字典类型")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认属性"""
        if self.properties is None:
            object.__setattr__(self, 'properties', {})
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """获取设备属性"""
        if self.properties is None:
            return default
        return self.properties.get(key, default)
    
    def has_property(self, key: str) -> bool:
        """检查是否有指定属性"""
        return self.properties is not None and key in self.properties


@dataclass(frozen=True)
class DeviceManagerConfigDTO(BaseDTO):
    """设备管理器配置数据传输对象 - 统一的配置管理"""
    
    config_version: str = "2.0.0"  # 配置版本
    
    # OAK设备配置（集中管理）
    oak_config: OAKConfigDTO = field(default_factory=OAKConfigDTO)
    
    # 系统功能配置
    system: SystemConfigDTO = field(default_factory=SystemConfigDTO)
    
    # 预留配置模块（等待后续实现）
    data_processing: DataProcessingConfigDTO = field(default_factory=DataProcessingConfigDTO)
    
    # 设备配置
    devices: Dict[str, DeviceConfigDTO] = field(default_factory=dict)
    
    def _validate_data(self) -> List[str]:
        """设备管理器配置数据验证"""
        errors = []
        
        # 验证配置版本
        errors.extend(validate_string_length(
            self.config_version, 'config_version', min_length=1, max_length=20
        ))
        
        # 验证各个配置模块
        config_modules = [
            ('oak_config', self.oak_config, OAKConfigDTO),
            ('system', self.system, SystemConfigDTO),
            ('data_processing', self.data_processing, DataProcessingConfigDTO)
        ]
        
        for config_name, config_obj, expected_type in config_modules:
            if config_obj is not None and not isinstance(config_obj, expected_type):
                errors.append(f"{config_name}配置必须为{expected_type.__name__}类型")
        
        # 验证设备配置字典
        if self.devices is not None:
            if not isinstance(self.devices, dict):
                errors.append("devices必须为字典类型")
            else:
                for alias, device_config in self.devices.items():
                    if not isinstance(alias, str):
                        errors.append("devices的键必须为字符串类型")
                    if not isinstance(device_config, DeviceConfigDTO):
                        errors.append(f"devices[{alias}]必须为DeviceConfigDTO类型")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        if self.oak_config is None:
            object.__setattr__(self, 'oak_config', OAKConfigDTO())
        
        if self.system is None:
            object.__setattr__(self, 'system', SystemConfigDTO())
        
        if self.data_processing is None:
            object.__setattr__(self, 'data_processing', DataProcessingConfigDTO())
        
        if self.devices is None:
            object.__setattr__(self, 'devices', {})
    
    # 属性方法
    @property
    def device_count(self) -> int:
        """获取设备数量"""
        return len(self.devices) if self.devices else 0
    
    @property
    def enabled_device_count(self) -> int:
        """获取启用的设备数量"""
        if not self.devices:
            return 0
        return sum(1 for device in self.devices.values() if device.enabled)
    
    def get_device_config(self, alias: str) -> Optional[DeviceConfigDTO]:
        """根据别名获取设备配置"""
        if not self.devices:
            return None
        return self.devices.get(alias)
    
    def get_aliases(self) -> List[str]:
        """获取所有设备别名列表"""
        if not self.devices:
            return []
        return list(self.devices.keys())
    
    # 便捷方法，获取各配置模块
    def get_oak_config(self) -> OAKConfigDTO:
        """获取OAK配置"""
        return self.oak_config or OAKConfigDTO()
    
    def get_system_config(self) -> SystemConfigDTO:
        """获取系统配置"""
        return self.system or SystemConfigDTO()
    
    def get_data_processing_config(self) -> DataProcessingConfigDTO:
        """获取数据处理配置"""
        return self.data_processing or DataProcessingConfigDTO()
    
    # 便捷访问OAK配置的具体参数
    @property
    def model_path(self) -> Optional[str]:
        """获取模型路径"""
        return self.oak_config.model_path if self.oak_config else None
    
    @property
    def confidence_threshold(self) -> float:
        """获取置信度阈值"""
        return self.oak_config.confidence_threshold if self.oak_config else 0.5
    
    @property
    def hardware_fps(self) -> int:
        """获取硬件帧率"""
        return self.oak_config.hardware_fps if self.oak_config else 30
    
    @property
    def enable_can(self) -> bool:
        """获取CAN启用状态"""
        return self.system.enable_can if self.system else False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceManagerConfigDTO':
        """
        从字典创建DeviceManagerConfigDTO实例，正确处理嵌套DTO对象
        
        Args:
            data: 包含配置数据的字典
            
        Returns:
            DeviceManagerConfigDTO: 配置实例
            
        Raises:
            ValueError: 当数据格式不正确时
        """
        try:
            # 复制数据以避免修改原始字典
            config_data = data.copy()
            
            # 处理 oak_config
            if 'oak_config' in config_data and isinstance(config_data['oak_config'], dict):
                config_data['oak_config'] = OAKConfigDTO.from_dict(config_data['oak_config'])
            
            # 处理 system
            if 'system' in config_data and isinstance(config_data['system'], dict):
                config_data['system'] = SystemConfigDTO.from_dict(config_data['system'])
            
            # 处理 data_processing
            if 'data_processing' in config_data and isinstance(config_data['data_processing'], dict):
                config_data['data_processing'] = DataProcessingConfigDTO.from_dict(config_data['data_processing'])
            
            # 处理 devices 字典
            if 'devices' in config_data and isinstance(config_data['devices'], dict):
                config_data['devices'] = cls._convert_devices_dict(config_data['devices'])
            
            # 过滤掉不属于该类的字段
            valid_fields = cls._get_init_fields()
            filtered_data = {k: v for k, v in config_data.items() if k in valid_fields}
            
            return cls(**filtered_data)
            
        except Exception as e:
            raise ValueError(f"无法从字典创建DeviceManagerConfigDTO实例: {str(e)}")
    
    @classmethod
    def _convert_devices_dict(cls, devices_data: Dict[str, Any]) -> Dict[str, DeviceConfigDTO]:
        """
        转换设备字典，将字典格式的设备配置转换为DeviceConfigDTO对象
        
        Args:
            devices_data: 设备配置字典
            
        Returns:
            Dict[str, DeviceConfigDTO]: 转换后的设备配置字典
        """
        converted_devices = {}
        
        for alias, device_data in devices_data.items():
            if isinstance(device_data, dict):
                # 创建设备数据的副本以避免修改原始数据
                device_copy = device_data.copy()
                
                # 转换枚举类型
                cls._convert_device_enums(device_copy)
                
                # 创建DeviceConfigDTO实例
                converted_devices[alias] = DeviceConfigDTO.from_dict(device_copy)
            else:
                # 已经是DTO对象，直接使用
                converted_devices[alias] = device_data
        
        return converted_devices
    
    @classmethod
    def _convert_device_enums(cls, device_data: Dict[str, Any]) -> None:
        """
        转换设备配置中的枚举类型
        
        Args:
            device_data: 设备配置数据字典（会被就地修改）
        """
        # 转换设备类型枚举
        if 'device_type' in device_data and isinstance(device_data['device_type'], str):
            try:
                device_data['device_type'] = DeviceType(device_data['device_type'])
            except ValueError:
                # 如果枚举值无效，使用UNKNOWN作为默认值
                device_data['device_type'] = DeviceType.UNKNOWN
        
        # 转换连接状态枚举
        if 'connection_state' in device_data and isinstance(device_data['connection_state'], str):
            try:
                device_data['connection_state'] = ConnectionStatus(device_data['connection_state'])
            except ValueError:
                # 如果枚举值无效，使用UNKNOWN作为默认值
                device_data['connection_state'] = ConnectionStatus.UNKNOWN