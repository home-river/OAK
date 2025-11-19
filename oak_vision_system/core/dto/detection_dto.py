"""
数据采集模块相关的DTO定义

包含以下DTO类：
- SpatialCoordinatesDTO: 空间坐标数据传输对象
- BoundingBoxDTO: 边界框数据传输对象  
- DetectionDTO: 单个检测结果数据传输对象
- DeviceDetectionDataDTO: 单个设备的检测数据传输对象
- VideoFrameDTO: 视频帧数据传输对象
- OAKDataCollectionDTO: OAK数据采集模块综合数据传输对象
- RawFrameDataEvent: 原始帧数据事件DTO
- RawDetectionDataEvent: 原始检测数据事件DTO
"""

import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List

from .base_dto import (
    BaseDTO,
    validate_required_fields,
    validate_numeric_range,
    validate_string_length,
)


@dataclass(frozen=True)
class SpatialCoordinatesDTO(BaseDTO):
    """空间坐标数据传输对象"""
    
    x: float  # X轴坐标 (mm)
    y: float  # Y轴坐标 (mm) 
    z: float  # Z轴坐标 (mm)
    
    def _validate_data(self) -> List[str]:
        """坐标数据验证"""
        errors = []
        
        # 验证坐标值为数值类型
        for coord_name, coord_value in [('x', self.x), ('y', self.y), ('z', self.z)]:
            if not isinstance(coord_value, (int, float)):
                errors.append(f"坐标{coord_name}必须为数值类型，当前类型: {type(coord_value).__name__}")
        
        return errors
    
    @property
    def distance_from_origin(self) -> float:
        """计算距离原点的距离"""
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
    
    @property
    def distance_squared_from_origin(self) -> float:
        """计算距离原点的距离平方，避免开方运算"""
        return self.x * self.x + self.y * self.y + self.z * self.z
    
    def distance_to(self, other: 'SpatialCoordinatesDTO') -> float:
        """计算到另一个坐标点的距离"""
        if not isinstance(other, SpatialCoordinatesDTO):
            raise TypeError("参数必须为SpatialCoordinatesDTO类型")
        
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        # 使用math.sqrt比**0.5更快
        return math.sqrt(dx * dx + dy * dy + dz * dz)
    
    def distance_squared_to(self, other: 'SpatialCoordinatesDTO') -> float:
        """
        计算到另一个坐标点的距离平方
        
        在只需要比较距离大小时，使用距离平方可以避免开方运算，提高性能
        """
        if not isinstance(other, SpatialCoordinatesDTO):
            raise TypeError("参数必须为SpatialCoordinatesDTO类型")
        
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return dx * dx + dy * dy + dz * dz


@dataclass(frozen=True)
class BoundingBoxDTO(BaseDTO):
    """边界框数据传输对象"""
    
    xmin: float  # 左上角X坐标
    ymin: float  # 左上角Y坐标
    xmax: float  # 右下角X坐标
    ymax: float  # 右下角Y坐标
    
    def _validate_data(self) -> List[str]:
        """边界框数据验证"""
        errors = []
        
        # 验证坐标值为数值类型
        for coord_name, coord_value in [
            ('xmin', self.xmin), ('ymin', self.ymin), 
            ('xmax', self.xmax), ('ymax', self.ymax)
        ]:
            if not isinstance(coord_value, (int, float)):
                errors.append(f"边界框坐标{coord_name}必须为数值类型，当前类型: {type(coord_value).__name__}")
        
        # 验证边界框有效性
        if isinstance(self.xmin, (int, float)) and isinstance(self.xmax, (int, float)):
            if self.xmin >= self.xmax:
                errors.append(f"边界框X坐标无效：xmin({self.xmin})必须小于xmax({self.xmax})")
        
        if isinstance(self.ymin, (int, float)) and isinstance(self.ymax, (int, float)):
            if self.ymin >= self.ymax:
                errors.append(f"边界框Y坐标无效：ymin({self.ymin})必须小于ymax({self.ymax})")
        
        return errors
    
    @property
    def width(self) -> float:
        """边界框宽度"""
        return self.xmax - self.xmin
    
    @property
    def height(self) -> float:
        """边界框高度"""
        return self.ymax - self.ymin
    
    @property
    def area(self) -> float:
        """边界框面积"""
        return self.width * self.height
    
    @property
    def center_x(self) -> float:
        """边界框中心X坐标"""
        return (self.xmin + self.xmax) / 2
    
    @property
    def center_y(self) -> float:
        """边界框中心Y坐标"""
        return (self.ymin + self.ymax) / 2
    
    @property
    def center_point(self) -> tuple[float, float]:
        """边界框中心点坐标"""
        return (self.center_x, self.center_y)


@dataclass(frozen=True)
class DetectionDTO(BaseDTO):
    """单个检测结果数据传输对象"""
    
    label: str  # 检测物体标签
    confidence: float  # 检测置信度 (0.0-1.0)
    bbox: BoundingBoxDTO  # 边界框信息
    spatial_coordinates: SpatialCoordinatesDTO  # 空间坐标信息
    detection_id: Optional[str] = None  # 检测唯一标识符
    # 注意：时间戳使用继承的 created_at 字段
    
    def _validate_data(self) -> List[str]:
        """检测数据验证"""
        errors = []
        
        # 验证标签
        errors.extend(validate_string_length(
            self.label, 'label', min_length=1, max_length=100
        ))
        
        # 验证置信度
        errors.extend(validate_numeric_range(
            self.confidence, 'confidence', min_value=0.0, max_value=1.0
        ))
        
        # 验证边界框和空间坐标（它们有自己的验证逻辑）
        if not isinstance(self.bbox, BoundingBoxDTO):
            errors.append("bbox必须为BoundingBoxDTO类型")
        
        if not isinstance(self.spatial_coordinates, SpatialCoordinatesDTO):
            errors.append("spatial_coordinates必须为SpatialCoordinatesDTO类型")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，如果detection_id为None则生成基于标签和时间戳的唯一ID"""
        if self.detection_id is None:
            # 生成基于标签和时间戳的唯一ID，使用继承的created_at字段
            timestamp_ms = int(self.created_at * 1000)
            detection_id = f"{self.label}_{timestamp_ms}_{str(uuid.uuid4())[:8]}"
            object.__setattr__(self, 'detection_id', detection_id)


@dataclass(frozen=True)
class DeviceDetectionDataDTO(BaseDTO):
    """单个设备的检测数据传输对象"""
    
    device_id: str  # 设备唯一标识符（MXid）
    frame_id: int  # 帧ID（主要标识符，用于与视频帧同步）
    device_alias: Optional[str] = None  # 设备别名
    detections: Optional[List[DetectionDTO]] = None  # 检测结果列表
    # 注意：时间戳使用继承的 created_at 字段，无需重复定义
    
    def _validate_data(self) -> List[str]:
        """设备检测数据验证"""
        errors = []
        
        # 验证设备ID
        errors.extend(validate_string_length(
            self.device_id, 'device_id', min_length=1, max_length=100
        ))
        
        # 验证设备别名（可选）
        if self.device_alias is not None:
            errors.extend(validate_string_length(
                self.device_alias, 'device_alias', min_length=1, max_length=50
            ))
        
        # 验证帧ID（必需）
        errors.extend(validate_numeric_range(
            self.frame_id, 'frame_id', min_value=0
        ))
        
        # 验证检测结果列表
        if self.detections is not None:
            if not isinstance(self.detections, list):
                errors.append("detections必须为列表类型")
            else:
                for i, detection in enumerate(self.detections):
                    if not isinstance(detection, DetectionDTO):
                        errors.append(f"detections[{i}]必须为DetectionDTO类型")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子, 如果detections为None则设置默认值"""
        if self.detections is None:
            object.__setattr__(self, 'detections', [])
    
    @property
    def detection_count(self) -> int:
        """检测结果数量"""
        return len(self.detections) if self.detections else 0
    
    def get_detections_by_label(self, label: str) -> List[DetectionDTO]:
        """根据标签筛选检测结果"""
        if not self.detections:
            return []
        return [det for det in self.detections if det.label == label]
    
    def get_high_confidence_detections(self, threshold: float = 0.5) -> List[DetectionDTO]:
        """获取高置信度检测结果"""
        if not self.detections:
            return []
        return [det for det in self.detections if det.confidence >= threshold]
    
    def get_detection_by_id(self, detection_id: str) -> Optional[DetectionDTO]:
        """根据ID获取检测结果"""
        if not self.detections:
            return None
        for detection in self.detections:
            if detection.detection_id == detection_id:
                return detection
        return None


@dataclass(frozen=True)
class VideoFrameDTO(BaseDTO):
    """视频帧数据传输对象"""
    
    device_id: str  # 设备ID
    frame_id: int  # 帧ID
    rgb_frame: Optional[Any] = None  # RGB图像数据 (numpy.ndarray)
    depth_frame: Optional[Any] = None  # 深度图像数据 (numpy.ndarray)
    frame_width: Optional[int] = None  # 帧宽度
    frame_height: Optional[int] = None  # 帧高度
    # 注意：时间戳使用继承的 created_at 字段
    
    def _validate_data(self) -> List[str]:
        """视频帧数据验证"""
        errors = []
        
        # 验证设备ID
        errors.extend(validate_string_length(
            self.device_id, 'device_id', min_length=1, max_length=100
        ))
        
        # 验证帧ID
        errors.extend(validate_numeric_range(
            self.frame_id, 'frame_id', min_value=0
        ))
        
        # 验证帧尺寸（可选）
        if self.frame_width is not None:
            errors.extend(validate_numeric_range(
                self.frame_width, 'frame_width', min_value=1, max_value=10000
            ))
        
        if self.frame_height is not None:
            errors.extend(validate_numeric_range(
                self.frame_height, 'frame_height', min_value=1, max_value=10000
            ))
        
        # 验证至少有一种帧数据
        if self.rgb_frame is None and self.depth_frame is None:
            errors.append("rgb_frame和depth_frame不能同时为None")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        pass  # 使用继承的 created_at 字段，无需额外初始化
    
    @property
    def has_rgb(self) -> bool:
        """是否包含RGB数据"""
        return self.rgb_frame is not None
    
    @property
    def has_depth(self) -> bool:
        """是否包含深度数据"""
        return self.depth_frame is not None
    
    @property
    def frame_size(self) -> Optional[tuple[int, int]]:
        """帧尺寸 (width, height)"""
        if self.frame_width is not None and self.frame_height is not None:
            return (self.frame_width, self.frame_height)
        return None


@dataclass(frozen=True)
class OAKDataCollectionDTO(BaseDTO):
    """OAK数据采集模块综合数据传输对象"""
    
    collection_id: str  # 采集批次ID
    devices_data: Optional[Dict[str, DeviceDetectionDataDTO]] = None  # 设备检测数据字典
    video_frames: Optional[Dict[str, VideoFrameDTO]] = None  # 视频帧字典
    # 注意：时间戳使用继承的 created_at 字段
    
    def _validate_data(self) -> List[str]:
        """数据采集DTO验证"""
        errors = []
        
        # 验证采集批次ID
        errors.extend(validate_string_length(
            self.collection_id, 'collection_id', min_length=1, max_length=100
        ))
        
        # 验证设备数据字典
        if self.devices_data is not None:
            if not isinstance(self.devices_data, dict):
                errors.append("devices_data必须为字典类型")
            else:
                for device_id, device_data in self.devices_data.items():
                    if not isinstance(device_id, str):
                        errors.append(f"devices_data的键必须为字符串类型")
                    if not isinstance(device_data, DeviceDetectionDataDTO):
                        errors.append(f"devices_data[{device_id}]必须为DeviceDetectionDataDTO类型")
        
        # 验证视频帧字典
        if self.video_frames is not None:
            if not isinstance(self.video_frames, dict):
                errors.append("video_frames必须为字典类型")
            else:
                for device_id, video_frame in self.video_frames.items():
                    if not isinstance(device_id, str):
                        errors.append(f"video_frames的键必须为字符串类型")
                    if not isinstance(video_frame, VideoFrameDTO):
                        errors.append(f"video_frames[{device_id}]必须为VideoFrameDTO类型")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        if self.devices_data is None:
            object.__setattr__(self, 'devices_data', {})
        
        if self.video_frames is None:
            object.__setattr__(self, 'video_frames', {})
    
    @property
    def available_devices(self) -> List[str]:
        """获取可用设备列表（有数据的设备）"""
        devices = set()
        if self.devices_data:
            devices.update(self.devices_data.keys())
        if self.video_frames:
            devices.update(self.video_frames.keys())
        return sorted(list(devices))
    
    @property
    def total_detections(self) -> int:
        """获取总检测数量"""
        if not self.devices_data:
            return 0
        return sum(data.detection_count for data in self.devices_data.values())
    
    def get_device_data(self, device_id: str) -> Optional[DeviceDetectionDataDTO]:
        """根据设备ID获取检测数据"""
        if not self.devices_data:
            return None
        return self.devices_data.get(device_id)
    
    def get_video_frame(self, device_id: str) -> Optional[VideoFrameDTO]:
        """根据设备ID获取视频帧"""
        if not self.video_frames:
            return None
        return self.video_frames.get(device_id)
    
    def has_device_data(self, device_id: str) -> bool:
        """检查是否有指定设备的数据"""
        return device_id in self.available_devices


# 事件数据DTO
@dataclass(frozen=True)
class RawFrameDataEvent(BaseDTO):
    """原始帧数据事件DTO"""
    
    event_type: str = field(default="raw_frame_data", init=False)
    device_id: str = ""
    video_frame: Optional[VideoFrameDTO] = None
    # 注意：时间戳使用继承的 created_at 字段
    
    def _validate_data(self) -> List[str]:
        """事件数据验证"""
        errors = []
        
        # 验证设备ID
        errors.extend(validate_string_length(
            self.device_id, 'device_id', min_length=1, max_length=100
        ))
        
        # 验证视频帧
        if self.video_frame is not None and not isinstance(self.video_frame, VideoFrameDTO):
            errors.append("video_frame必须为VideoFrameDTO类型")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        pass  # 使用继承的 created_at 字段，无需额外初始化


@dataclass(frozen=True)
class RawDetectionDataEvent(BaseDTO):
    """原始检测数据事件DTO"""
    
    event_type: str = field(default="raw_detection_data", init=False)
    device_id: str = ""
    detection_data: Optional[DeviceDetectionDataDTO] = None
    # 注意：时间戳使用继承的 created_at 字段
    
    def _validate_data(self) -> List[str]:
        """事件数据验证"""
        errors = []
        
        # 验证设备ID
        errors.extend(validate_string_length(
            self.device_id, 'device_id', min_length=1, max_length=100
        ))
        
        # 验证检测数据
        if self.detection_data is not None and not isinstance(self.detection_data, DeviceDetectionDataDTO):
            errors.append("detection_data必须为DeviceDetectionDataDTO类型")
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        pass  # 使用继承的 created_at 字段，无需额外初始化
