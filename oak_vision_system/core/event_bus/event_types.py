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
    
    # 数据调度器模块事件（对外发布）
    PROCESSED_DISPLAY_DATA = "processed_display_data"    # 发送给显示模块
    TARGET_COORDINATES = "target_coordinates"            # 发送给控制模块
    
    # 注意：数据调度器内部的处理步骤（滤波、修正等）不作为事件发布
    # 这些是模块内部实现细节，应该在模块内部流动
    
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

