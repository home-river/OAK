"""
数据处理模块 DTO 定义
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional
import numpy as np

from .detection_dto import DetectionDTO
from .transport_dto import TransportDTO
from .base_dto import validate_numeric_range, validate_string_length
 



class DetectionStatusLabel(IntEnum):
    """
    通用状态标签枚举（整数类型）：
    - 同时覆盖抓取物状态和人类状态
    - 使用整数值便于向量化计算和高效的 ndarray 操作
    - 渲染时可以按不同状态走不同颜色/样式
    - 整数值按类别分段：物体状态 (0-99)，人类状态 (100-199)
    """

    # 抓取物状态 (0-99)
    OBJECT_GRASPABLE = 0        # 可抓取
    OBJECT_DANGEROUS = 1        # 不可抓取（危险状态）
    OBJECT_OUT_OF_RANGE = 2     # 无法抓取（超出范围）
    OBJECT_PENDING_GRASP = 3    # 待抓取

    # 人类状态 (100-199)
    HUMAN_SAFE = 100            # 无危险
    HUMAN_DANGEROUS = 101       # 危险（靠太近）


def states_to_labels(states: np.ndarray) -> List[DetectionStatusLabel]:
    """
    将整数状态数组转换为枚举标签列表
    
    该函数用于决策层输出时，将向量化计算得到的整数状态数组
    高效转换为 DetectionStatusLabel 枚举列表。
    
    Args:
        states: 整数状态数组，形状 (N,)，dtype 应为整数类型
    
    Returns:
        枚举标签列表，长度 N
        
    Example:
        >>> states = np.array([0, 100, 2, 101])
        >>> labels = states_to_labels(states)
        >>> labels
        [<DetectionStatusLabel.OBJECT_GRASPABLE: 0>,
         <DetectionStatusLabel.HUMAN_SAFE: 100>,
         <DetectionStatusLabel.OBJECT_OUT_OF_RANGE: 2>,
         <DetectionStatusLabel.HUMAN_DANGEROUS: 101>]
    """
    return [DetectionStatusLabel(int(state)) for state in states]


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
class DeviceProcessedDetectionDTO(TransportDTO):
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

        errors.extend(validate_numeric_range(
            self.frame_id, 'frame_id', min_value=0
        ))

        if self.device_alias is not None:
            errors.extend(validate_string_length(
                self.device_alias, 'device_alias', min_length=1, max_length=50
            ))

        if self.detections is not None:
            if not isinstance(self.detections, list):
                errors.append("detections必须为列表类型")
            else:
                for i, det in enumerate(self.detections):
                    if not isinstance(det, ProcessedDetectionDTO):
                        errors.append(f"detections[{i}]必须为ProcessedDetectionDTO类型")

        return errors

# 新设计
@dataclass(frozen=True)
class DeviceProcessedDataDTO(TransportDTO):
    """单个设备处理后的检测数据DTO,用于数据处理模块输出"""
    device_id : str # 设备的mxid
    frame_id : int # 帧id
    labels : np.ndarray # 检测结果的标签数组，形状 (n,)，dtype=int32
    bbox: np.ndarray # 检测结果的边界框数组，形状 (n, 4)，dtype=float32
    coords: np.ndarray # 检测结果的坐标数组，形状 (n, 3)，dtype=float32
    confidence : np.ndarray # 检测结果的置信度数组，形状 (n,)，dtype=float32
    state_label: List[DetectionStatusLabel] # 检测结果的状态标签列表
    device_alias : Optional[str] = None # 设备别名

    def _validate_data(self) -> List[str]:
        """
        处理后设备检测数据的完整性与类型验证方法。
        检查 device_id/frame_id/device_alias/labels/confidence/state_label/bbox/coords 的数据类型及长度一致性。
        返回所有发现的问题描述字符串列表。
        """
        errors: List[str] = []

        # 检查 device_id 是合法字符串
        errors.extend(validate_string_length(
            self.device_id, 'device_id', min_length=1, max_length=100
        ))
        # 检查 frame_id 是非负数值
        errors.extend(validate_numeric_range(
            self.frame_id, 'frame_id', min_value=0
        ))

        # 可选字段：device_alias 校验
        if self.device_alias is not None:
            errors.extend(validate_string_length(
                self.device_alias, 'device_alias', min_length=1, max_length=50
            ))

        # 检查 labels 是否为一维整数型 np.ndarray
        if not isinstance(self.labels, np.ndarray):
            errors.append("labels必须为np.ndarray类型")
            n = None
        else:
            if self.labels.ndim != 1:
                errors.append("labels的shape必须为(N,)")
            if not np.issubdtype(self.labels.dtype, np.integer):
                errors.append("labels必须为整数数组")
            n = len(self.labels)
            # 检查标签值范围
            if n > 0 and (self.labels < 0).any():
                errors.append("labels中的值必须非负")

        # 检查 confidence 是否为一维浮点型 np.ndarray
        if not isinstance(self.confidence, np.ndarray):
            errors.append("confidence必须为np.ndarray类型")
        else:
            if self.confidence.ndim != 1:
                errors.append("confidence的shape必须为(N,)")
            if not np.issubdtype(self.confidence.dtype, np.floating):
                errors.append("confidence必须为浮点数组")
            # 检查置信度值域
            if len(self.confidence) > 0:
                if (self.confidence < 0.0).any() or (self.confidence > 1.0).any():
                    errors.append("confidence中的值必须在[0.0, 1.0]范围内")

        # 检查 state_label 状态标签列表及元素类型
        if not isinstance(self.state_label, list):
            errors.append("state_label必须为列表类型")
        else:
            for i, s in enumerate(self.state_label):
                if not isinstance(s, DetectionStatusLabel):
                    errors.append(f"state_label[{i}]必须为DetectionStatusLabel类型")

        # 校验 bbox 是否为二维4列的数值型 np.ndarray
        if not isinstance(self.bbox, np.ndarray):
            errors.append("bbox必须为np.ndarray类型")
        else:
            if self.bbox.ndim != 2 or self.bbox.shape[1] != 4:
                errors.append("bbox的shape必须为(N,4)")
            if not np.issubdtype(self.bbox.dtype, np.number):
                errors.append("bbox必须为数值数组")

        # 校验 coords 是否为二维3列的数值型 np.ndarray
        if not isinstance(self.coords, np.ndarray):
            errors.append("coords必须为np.ndarray类型")
        else:
            if self.coords.ndim != 2 or self.coords.shape[1] != 3:
                errors.append("coords的shape必须为(N,3)")
            if not np.issubdtype(self.coords.dtype, np.number):
                errors.append("coords必须为数值数组")

        # 检查所有 ndarray/list 的长度/行数一致性
        if n is not None:
            # confidence 长度需与 labels 一致
            if isinstance(self.confidence, np.ndarray) and len(self.confidence) != n:
                errors.append("confidence长度必须与labels一致")
            # state_label 列表长度需与 labels 一致
            if isinstance(self.state_label, list) and len(self.state_label) != n:
                errors.append("state_label长度必须与labels一致")
            # bbox 行数需与 labels 长度一致
            if isinstance(self.bbox, np.ndarray) and self.bbox.ndim == 2 and self.bbox.shape[0] != n:
                errors.append("bbox的行数必须与labels长度一致")
            # coords 行数需与 labels 长度一致
            if isinstance(self.coords, np.ndarray) and self.coords.ndim == 2 and self.coords.shape[0] != n:
                errors.append("coords的行数必须与labels长度一致")

        return errors
