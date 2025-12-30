"""
数据处理模块 DTO 定义
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .detection_dto import DetectionDTO
from .base_dto import (
    BaseDTO,
    validate_required_fields,
    validate_numeric_range,
    validate_string_length,
)
 



class DetectionStatusLabel(Enum):
    """
    通用状态标签枚举：
    - 同时覆盖抓取物状态和人类状态
    - 渲染时可以按不同状态走不同颜色/样式
    """

    # 抓取物状态
    OBJECT_GRASPABLE = "object_graspable"             # 可抓取
    OBJECT_DANGEROUS = "object_dangerous"             # 不可抓取（危险状态）
    OBJECT_OUT_OF_RANGE = "object_out_of_range"       # 无法抓取（超出范围）
    OBJECT_PENDING_GRASP = "object_pending_grasp"     # 待抓取

    # 人类状态
    HUMAN_SAFE = "human_safe"                         # 无危险
    HUMAN_DANGEROUS = "human_dangerous"               # 危险（靠太近）


@dataclass(frozen=True)
class ProcessedDetectionDTO(DetectionDTO):
    """
    处理后的检测结果 DTO，继承基础 DetectionDTO，并新增状态信息。
    """

    # 新增状态标签字段
    status_label: Optional[DetectionStatusLabel] = None

    def _validate_data(self) -> List[str]:
        """在父类校验基础上，补充对状态标签的校验。"""
        errors = super()._validate_data()

        if (
            self.status_label is not None
            and not isinstance(self.status_label, DetectionStatusLabel)
        ):
            errors.append(
                "status_label 必须为 DetectionStatusLabel 类型，"
                f"当前类型: {type(self.status_label).__name__}"
            )

        return errors


@dataclass(frozen=True)
class DeviceProcessedDetectionDTO(BaseDTO):
    """单个设备的处理后的检测数据传输对象"""

    device_id: str  # 设备唯一标识符（MXid）
    frame_id: int  # 帧ID（主要标识符，用于与视频帧同步）
    device_alias: Optional[str] = None  # 设备别名
    detections: Optional[List[ProcessedDetectionDTO]] = None  # 处理后的检测结果列表
    # 注意：时间戳使用继承的 created_at 字段，无需重复定义
    
    def _validate_data(self) -> List[str]:
        """设备处理后的检测数据验证"""
        errors = []
        
        # 验证设备ID
        errors.extend(validate_string_length(
            self.device_id, 'device_id', min_length=1, max_length=100
        ))