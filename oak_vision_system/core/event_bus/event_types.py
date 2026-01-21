class EventType:
    """
    事件类型枚举（用字符串常量即可，便于日志和跨模块引用）
    """

    # 摄像头 / 数据源相关
    RAW_FRAME_DATA = "raw_frame_data"          # 数据源模块发布的原始帧（视频帧)
    RAW_DETECTION_DATA = "raw_detection_data"  # 数据源模块发布的原始检测数据（检测数据）
    CAMERA_HEARTBEAT = "camera_heartbeat"      # 可选：摄像头心跳/状态上报

    # 数据处理相关
    PROCESSED_DATA = "processed_data"          # 数据处理模块输出，用于显示模块
    PROCESSING_ERROR = "processing_error"      # 可选：处理异常

    # 数据处理：决策 / 业务相关
    PERSON_WARNING = "person_warning"          # 人员危险警告事件

    # 显示相关
    DISPLAY_RENDER = "display_render"          # 可选：通知显示模块渲染
    DISPLAY_STATS = "display_stats"            # 可选：显示性能统计

    # 系统状态 / 性能监控
    PERFORMANCE_METRICS = "performance_metrics"  # 延迟、FPS 等统计

    # 背压 / 流量控制
    BACKPRESSURE_SIGNAL = "backpressure_signal"
    """
    背压控制信号，典型 payload 例如：
    {
        "action": "PAUSE" | "RESUME",
        "source": "display" | "processor",
        "reason": "queue_high" | "queue_low" | ...
    }
    """
    

    # 其它业务事件（示例）
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"
