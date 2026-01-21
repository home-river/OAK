"""
决策层数据类型定义

包含决策层使用的枚举类型和数据类。
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional
import numpy as np


class PersonWarningState(Enum):
    """
    人员警告状态机状态
    
    状态转换：
    - SAFE -> PENDING: 人员距离 < d_in
    - PENDING -> ALARM: 危险持续时间 >= T_warn
    - PENDING -> SAFE: 人员距离 >= d_out
    - ALARM -> SAFE: 离开危险区持续时间 >= T_clear
    """
    SAFE = "safe"          # 安全状态
    PENDING = "pending"    # 潜在危险（正在累计时间）
    ALARM = "alarm"        # 危险告警


class PersonWarningStatus(Enum):
    """
    人员警告事件状态
    
    用于 PERSON_WARNING 事件的状态字段。
    """
    TRIGGERED = "triggered"  # 警告触发（PENDING -> ALARM）
    CLEARED = "cleared"      # 警告清除（ALARM -> SAFE）


class DetectionStatusLabel(IntEnum):
    """
    检测对象状态标签（整数枚举）
    
    使用整数值便于向量化计算：
    - 物体状态：0-99
    - 人员状态：100-199
    
    状态说明：
    - OBJECT_GRASPABLE: 物体在抓取区域内，可以抓取
    - OBJECT_DANGEROUS: 物体过于靠近车体（|y| < danger_y_threshold）
    - OBJECT_OUT_OF_RANGE: 物体超出抓取范围
    - OBJECT_PENDING_GRASP: 物体是当前的全局待抓取目标
    - HUMAN_SAFE: 人员距离安全（>= d_out）
    - HUMAN_DANGEROUS: 人员距离危险（< d_in 或处于 ALARM 状态）
    """
    
    # 物体状态 (0-99)
    OBJECT_GRASPABLE = 0        # 可抓取
    OBJECT_DANGEROUS = 1        # 危险（过于靠近车体）
    OBJECT_OUT_OF_RANGE = 2     # 超出抓取范围
    OBJECT_PENDING_GRASP = 3    # 待抓取（全局目标）
    
    # 人员状态 (100-199)
    HUMAN_SAFE = 100            # 安全
    HUMAN_DANGEROUS = 101       # 危险（距离过近）


@dataclass
class DeviceState:
    """
    设备状态信息
    
    每个设备维护独立的状态，包括人员警告状态和最近可抓取物体信息。
    
    Attributes:
        person_warning_state: 人员警告状态机的当前状态
        person_distance: 最近人员的距离（米）
        person_last_seen_time: 最后一次检测到人员的时间戳
        t_in: 危险持续时间（秒），用于 PENDING -> ALARM 转换
        t_out: 离开危险区持续时间（秒），用于 ALARM -> SAFE 转换
        nearest_object_coords: 最近可抓取物体的坐标，形状 (3,)
        nearest_object_distance: 最近可抓取物体的距离（米）
        last_update_time: 最后更新时间戳（用于状态过期检查）
    """
    
    # 人员相关状态
    person_warning_state: PersonWarningState = PersonWarningState.SAFE
    person_distance: Optional[float] = None
    person_last_seen_time: Optional[float] = None
    t_in: float = 0.0   # 危险持续时间
    t_out: float = 0.0  # 离开危险区持续时间
    
    # 物体相关状态
    nearest_object_coords: Optional[np.ndarray] = None
    nearest_object_distance: Optional[float] = None
    
    # 通用状态
    last_update_time: float = 0.0


@dataclass
class GlobalTargetObject:
    """
    全局待抓取目标对象
    
    从所有设备的最近可抓取物体中选择距离最近的作为全局目标。
    
    Attributes:
        coords: 目标坐标，形状 (3,)，单位：米
        distance: 目标距离，单位：米
        device_id: 目标来源的设备ID
    """
    coords: np.ndarray      # 坐标，形状 (3,)
    distance: float         # 距离（米）
    device_id: str          # 来源设备ID
