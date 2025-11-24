"""
数据处理模块配置DTO

包含坐标变换、滤波等所有数据处理相关配置。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..base_dto import  validate_numeric_range
from .base_config_dto import BaseConfigDTO
from .enums import DeviceRole, FilterType


# 模块内维护的标定方式白名单（提取自 DTO 外部）
CALIBRATION_METHODS: tuple[str, ...] = ("manual", "auto")


@dataclass(frozen=True)
class CoordinateTransformConfigDTO(BaseConfigDTO):
    """
    坐标变换配置
    
    参数绑定到角色（role），设备更换后无需重新标定。
    """
    
    role: DeviceRole
    
    # 平移变换参数
    translation_x: float = 0.0    # mm
    translation_y: float = 0.0    # mm
    translation_z: float = 0.0    # mm
    # 旋转变换参数
    roll: float = 0.0             # 滚转角 单位：度
    pitch: float = 0.0             # 俯仰角 单位：度
    yaw: float = 0.0               # 偏航角 单位：度
    
    # 标定信息
    calibration_date: Optional[str] = None
    calibration_method: Optional[str] = None  # "manual"/"auto"
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        if not isinstance(self.role, DeviceRole):
            errors.append("role必须为DeviceRole枚举类型")
        
        if self.calibration_method is not None:
            if self.calibration_method not in CALIBRATION_METHODS:
                errors.append(f"calibration_method必须为: {'/'.join(CALIBRATION_METHODS)}")
        
        return errors
    
    # 生成矩阵的逻辑由 utils.transform_utils 管理


@dataclass(frozen=True)
class MovingAverageFilterConfigDTO(BaseConfigDTO):
    """滑动平均滤波器配置（默认推荐）"""
    
    window_size: int = 5               # 窗口大小（历史数据点数量）
    weighted: bool = False             # 是否使用加权平均
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        if self.window_size < 1:
            errors.append("window_size必须 >= 1")
        
        if self.window_size > 50:
            errors.append("window_size建议 <= 50（过大会导致响应延迟）")
        
        return errors


@dataclass(frozen=True)
class KalmanFilterConfigDTO(BaseConfigDTO):
    """卡尔曼滤波器配置"""
    
    kalman_gain: float = 0.5           # 卡尔曼增益
    process_noise: float = 0.1         # 过程噪声
    measurement_noise: float = 0.5     # 测量噪声
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        errors.extend(validate_numeric_range(
            self.kalman_gain, 'kalman_gain', min_value=0.0, max_value=1.0
        ))
        errors.extend(validate_numeric_range(
            self.process_noise, 'process_noise', min_value=0.0, max_value=10.0
        ))
        errors.extend(validate_numeric_range(
            self.measurement_noise, 'measurement_noise', min_value=0.0, max_value=10.0
        ))
        
        return errors


@dataclass(frozen=True)
class LowpassFilterConfigDTO(BaseConfigDTO):
    """低通滤波器配置"""
    
    cutoff_frequency: float = 5.0      # 截止频率 (Hz)
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        errors.extend(validate_numeric_range(
            self.cutoff_frequency, 'cutoff_frequency', min_value=0.1, max_value=100.0
        ))
        
        return errors


@dataclass(frozen=True)
class MedianFilterConfigDTO(BaseConfigDTO):
    """中值滤波器配置"""
    
    window_size: int = 5               # 窗口大小（必须为奇数）
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        if self.window_size < 3:
            errors.append("window_size必须 >= 3")
        
        if self.window_size % 2 == 0:
            errors.append("window_size必须为奇数")
        
        return errors


@dataclass(frozen=True)
class FilterConfigDTO(BaseConfigDTO):
    """
    滤波配置（策略模式）
    
    根据 filter_type 选择对应的滤波器配置。
    每个滤波器维护自己独立的参数。
    """
    
    # 当前使用的滤波器类型（默认：滑动平均）
    filter_type: FilterType = FilterType.MOVING_AVERAGE
    
    # 各滤波器的配置（按需初始化）
    moving_average_config: Optional[MovingAverageFilterConfigDTO] = None
    kalman_config: Optional[KalmanFilterConfigDTO] = None
    lowpass_config: Optional[LowpassFilterConfigDTO] = None
    median_config: Optional[MedianFilterConfigDTO] = None
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        if not isinstance(self.filter_type, FilterType):
            errors.append("filter_type必须为FilterType枚举类型")
        
        # 验证当前选中的滤波器配置必须存在
        active_config = self.get_active_filter_config()
        if active_config is None:
            errors.append(f"当前滤波器类型 {self.filter_type.value} 的配置不能为空")

        else: 
            errors.extend(active_config._validate_data())

        return errors
    
    def _post_init_hook(self) -> None:
        """初始化时确保当前选中的滤波器有默认配置"""
        if self.filter_type == FilterType.MOVING_AVERAGE and self.moving_average_config is None:
            object.__setattr__(self, 'moving_average_config', MovingAverageFilterConfigDTO())
        elif self.filter_type == FilterType.KALMAN and self.kalman_config is None:
            object.__setattr__(self, 'kalman_config', KalmanFilterConfigDTO())
        elif self.filter_type == FilterType.LOWPASS and self.lowpass_config is None:
            object.__setattr__(self, 'lowpass_config', LowpassFilterConfigDTO())
        elif self.filter_type == FilterType.MEDIAN and self.median_config is None:
            object.__setattr__(self, 'median_config', MedianFilterConfigDTO())
    
    def get_active_filter_config(self):
        """
        获取当前激活的滤波器配置
        
        Returns:
            当前滤波器类型对应的配置对象
        """
        if self.filter_type == FilterType.MOVING_AVERAGE:
            return self.moving_average_config
        elif self.filter_type == FilterType.KALMAN:
            return self.kalman_config
        elif self.filter_type == FilterType.LOWPASS:
            return self.lowpass_config
        elif self.filter_type == FilterType.MEDIAN:
            return self.median_config
        else:
            return None


@dataclass(frozen=True)
class DataProcessingConfigDTO(BaseConfigDTO):
    """
    数据处理模块配置（容器）
    
    管理坐标变换、滤波等所有数据处理相关配置。
    """
    
    # =====子配置=======
    # 坐标变换配置
    coordinate_transforms: Dict[DeviceRole, CoordinateTransformConfigDTO] = field(default_factory=dict)
    # 滤波配置
    filter_config: FilterConfigDTO = field(default_factory=FilterConfigDTO)
    
    # 模块级配置
    enable_data_logging: bool = False
    processing_thread_priority: int = 5
    
    # 策略配置
    person_timeout_seconds: float = 5.0  # 目标跟踪超时（业务逻辑层）
    
    def _validate_data(self) -> List[str]:
        errors = []
        errors.extend(validate_numeric_range(
            self.person_timeout_seconds, 'person_timeout_seconds',
            min_value=0.1, max_value=10.0
        ))
        if not isinstance(self.coordinate_transforms, dict):
            errors.append("coordinate_transforms必须为字典类型")
        else:
            for role, transform in self.coordinate_transforms.items():
                if transform.role != role:
                    errors.append(f"坐标变换的role和rolebinding的role不一致：{transform.role}!={role}")
                errors.extend(transform._validate_data())
        
        if not isinstance(self.filter_config, FilterConfigDTO):
            errors.append("filter_config必须为FilterConfigDTO类型")
        else:
            errors.extend(self.filter_config._validate_data())
        
        
        return errors
    
    def _post_init_hook(self) -> None:
        if self.filter_config is None:
            object.__setattr__(self, 'filter_config', FilterConfigDTO())
    
    def get_coordinate_transform(self, role: DeviceRole) -> CoordinateTransformConfigDTO:
        """获取指定角色的坐标变换配置"""
        if role not in self.coordinate_transforms:
            return CoordinateTransformConfigDTO(role=role)
        return self.coordinate_transforms[role]
    
    def add_coordinate_transform(self, config: CoordinateTransformConfigDTO) -> None:
        """添加坐标变换配置"""
        self.coordinate_transforms[config.role] = config
