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
    
    window_size: int = 10               # 窗口大小（历史数据点数量）
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        if self.window_size < 1:
            errors.append("window_size必须 >= 1")
        
        if self.window_size > 50:
            errors.append("window_size建议 <= 50（过大会导致响应延迟）")
        
        return errors


@dataclass(frozen=True)
class FilterConfigDTO(BaseConfigDTO):
    """
    滤波配置
    
    当前只支持滑动平均滤波器。
    """
    
    # 当前使用的滤波器类型（默认：滑动平均）
    filter_type: FilterType = FilterType.MOVING_AVERAGE
    
    # 滑动平均滤波器配置
    moving_average_config: Optional[MovingAverageFilterConfigDTO] = None
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        if not isinstance(self.filter_type, FilterType):
            errors.append("filter_type必须为FilterType枚举类型")
        
        # 验证滤波器配置必须存在
        if self.moving_average_config is None:
            errors.append("moving_average_config 不能为空")
        else: 
            errors.extend(self.moving_average_config._validate_data())

        return errors
    
    def _post_init_hook(self) -> None:
        """初始化时确保滤波器有默认配置"""
        if self.moving_average_config is None:
            object.__setattr__(self, 'moving_average_config', MovingAverageFilterConfigDTO())
    
    def get_active_filter_config(self) -> MovingAverageFilterConfigDTO:
        """
        获取当前激活的滤波器配置
        
        Returns:
            滑动平均滤波器配置对象
        """
        return self.moving_average_config


@dataclass(frozen=True)
class GraspZoneConfigDTO(BaseConfigDTO):
    """
    抓取区域配置
    
    支持两种模式：
    - 矩形模式 (mode="rect"): 使用 x_min, x_max, y_min, y_max 定义抓取范围
    - 半径模式 (mode="radius"): 使用 r_min, r_max 定义半径范围
    
    注意：所有距离单位为毫米（mm）
    """
    
    mode: str = "rect"  # "rect" 或 "radius"
    
    # 矩形模式参数（mm）
    x_min: float = -200.0
    x_max: float = 2000.0
    y_min: float = 1550.0
    y_max: float = 2500.0
    
    # 半径模式参数（可选，mm）
    r_min: Optional[float] = None
    r_max: Optional[float] = None
    
    def _validate_data(self) -> List[str]:
        """验证抓取区域配置"""
        errors = []
        
        if self.mode not in ("rect", "radius"):
            errors.append(f"不支持的抓取区域模式: {self.mode}")
            return errors
        
        if self.mode == "rect":
            if self.x_min >= self.x_max:
                errors.append("x_min 必须小于 x_max")
            if self.y_min >= self.y_max:
                errors.append("y_min 必须小于 y_max")
            
            errors.extend(validate_numeric_range(
                self.x_min, 'x_min', min_value=0.0, max_value=5000.0
            ))
            errors.extend(validate_numeric_range(
                self.x_max, 'x_max', min_value=0.0, max_value=5000.0
            ))
            errors.extend(validate_numeric_range(
                self.y_min, 'y_min', min_value=0.0, max_value=3000.0
            ))
            errors.extend(validate_numeric_range(
                self.y_max, 'y_max', min_value=0.0, max_value=3000.0
            ))
        
        elif self.mode == "radius":
            if self.r_min is None or self.r_max is None:
                errors.append("半径模式需要 r_min 和 r_max")
            elif self.r_min >= self.r_max:
                errors.append("r_min 必须小于 r_max")
            else:
                errors.extend(validate_numeric_range(
                    self.r_min, 'r_min', min_value=0.0, max_value=5000.0
                ))
                errors.extend(validate_numeric_range(
                    self.r_max, 'r_max', min_value=0.0, max_value=5000.0
                ))
        
        return errors


@dataclass(frozen=True)
class ObjectZonesConfigDTO(BaseConfigDTO):
    """
    物体区域配置
    
    定义危险区域和抓取区域的参数。
    
    注意：所有距离单位为毫米（mm）
    """
    
    danger_y_threshold: float = 1500.0  # 危险区 y 坐标绝对值阈值（mm），判断条件为 |y| < danger_y_threshold
    grasp_zone: GraspZoneConfigDTO = field(default_factory=GraspZoneConfigDTO)
    
    def _validate_data(self) -> List[str]:
        """验证物体区域配置"""
        errors = []
        
        errors.extend(validate_numeric_range(
            self.danger_y_threshold, 'danger_y_threshold',
            min_value=0.0, max_value=2000.0
        ))
        
        errors.extend(self.grasp_zone._validate_data())
        
        return errors


@dataclass(frozen=True)
class PersonWarningConfigDTO(BaseConfigDTO):
    """
    人员警告配置
    
    定义人员危险区域判断和警告触发的参数。
    
    注意：距离单位为毫米（mm），时间单位为秒（s）
    """
    
    d_in: float = 3000.0        # 进入危险区距离（mm）
    d_out: float = 3050.0       # 离开危险区距离（mm）
    T_warn: float = 3.0         # 警告触发时间（秒）
    T_clear: float = 3.0        # 警告清除时间（秒）
    grace_time: float = 0.5     # 目标消失宽限期（秒）
    
    def _validate_data(self) -> List[str]:
        """验证人员警告配置"""
        errors = []
        
        if self.d_out <= self.d_in:
            errors.append("d_out 必须大于 d_in")
        
        errors.extend(validate_numeric_range(
            self.d_in, 'd_in', min_value=0.0, max_value=10000.0
        ))
        errors.extend(validate_numeric_range(
            self.d_out, 'd_out', min_value=0.0, max_value=10000.0
        ))
        errors.extend(validate_numeric_range(
            self.T_warn, 'T_warn', min_value=0.0, max_value=10.0
        ))
        errors.extend(validate_numeric_range(
            self.T_clear, 'T_clear', min_value=0.0, max_value=10.0
        ))
        errors.extend(validate_numeric_range(
            self.grace_time, 'grace_time', min_value=0.0, max_value=5.0
        ))
        
        return errors


@dataclass(frozen=True)
class DecisionLayerConfigDTO(BaseConfigDTO):
    """
    决策层配置 DTO
    
    作为 DataProcessingConfigDTO 的子配置，管理决策层的所有参数。
    """
    
    # 标签映射
    person_label_ids: List[int] = field(default_factory=lambda: [0])
    
    # 人员警告配置
    person_warning: PersonWarningConfigDTO = field(default_factory=PersonWarningConfigDTO)
    
    # 物体区域配置
    object_zones: ObjectZonesConfigDTO = field(default_factory=ObjectZonesConfigDTO)
    
    # 状态过期时间
    state_expiration_time: float = 1.0  # 秒
    
    def _validate_data(self) -> List[str]:
        """验证配置参数"""
        errors = []
        
        if not isinstance(self.person_label_ids, list):
            errors.append("person_label_ids 必须为列表类型")
        
        errors.extend(validate_numeric_range(
            self.state_expiration_time, 'state_expiration_time',
            min_value=0.1, max_value=10.0
        ))
        
        # 验证子配置
        errors.extend(self.person_warning._validate_data())
        errors.extend(self.object_zones._validate_data())
        
        return errors


@dataclass(frozen=True)
class DataProcessingConfigDTO(BaseConfigDTO):
    """
    数据处理模块配置（容器）
    
    管理坐标变换、滤波、决策层等所有数据处理相关配置。
    """
    
    # =====子配置=======
    # 坐标变换配置
    coordinate_transforms: Dict[DeviceRole, CoordinateTransformConfigDTO] = field(default_factory=dict)
    # 滤波配置
    filter_config: FilterConfigDTO = field(default_factory=FilterConfigDTO)
    # 决策层配置
    decision_layer_config: DecisionLayerConfigDTO = field(default_factory=DecisionLayerConfigDTO)
    
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
        
        # 验证决策层配置
        if not isinstance(self.decision_layer_config, DecisionLayerConfigDTO):
            errors.append("decision_layer_config必须为DecisionLayerConfigDTO类型")
        else:
            errors.extend(self.decision_layer_config._validate_data())
        
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
