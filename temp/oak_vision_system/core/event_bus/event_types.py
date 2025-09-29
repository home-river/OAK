"""
事件类型定义
"""

from enum import Enum


class EventType:
    """事件类型常量定义"""
    
    # 数据采集模块事件
    RAW_FRAME_DATA = "raw_frame_data"
    RAW_DETECTION_DATA = "raw_detection_data"
    DEVICE_STATUS_CHANGE = "device_status_change"
    
    # 数据处理模块事件
    PROCESSED_DETECTION_DATA = "processed_detection_data"
    FILTERED_COORDINATES = "filtered_coordinates"
    CORRECTED_COORDINATES = "corrected_coordinates"
    
    # 显示模块事件
    DISPLAY_FRAME_READY = "display_frame_ready"
    
    # CAN通信模块事件
    CAN_DATA_RECEIVED = "can_data_received"
    CAN_DATA_SENT = "can_data_sent"
    CAN_ERROR = "can_error"
    
    # 控制器模块事件
    MOTION_COMMAND = "motion_command"
    GRASP_COMMAND = "grasp_command"
    SENSOR_FEEDBACK = "sensor_feedback"
    
    # 系统事件
    SYSTEM_STATUS = "system_status"
    PERFORMANCE_METRICS = "performance_metrics"
    ERROR_ALERT = "error_alert"


class Priority(Enum):
    """事件优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

