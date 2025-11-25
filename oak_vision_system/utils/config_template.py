"""
配置模板构建工具（硬编码默认参数 → 分层DTO装配）。

说明：
- 仅产出默认 DTO，不做文件 I/O。
- 可被配置管理器与后续 CLI 复用。
"""

from __future__ import annotations

from typing import Optional, List, Dict
import time

from oak_vision_system.core.dto.config_dto import (
    DeviceManagerConfigDTO,
    OAKModuleConfigDTO,
    OAKConfigDTO,
    DeviceRoleBindingDTO,
    DeviceMetadataDTO,
    DeviceRole,
    SystemConfigDTO,
    DisplayConfigDTO,
    CANConfigDTO,
    FrameIdConfigDTO,
    DataProcessingConfigDTO,
    CoordinateTransformConfigDTO,
    FilterConfigDTO,
    MovingAverageFilterConfigDTO,
    KalmanFilterConfigDTO,
    LowpassFilterConfigDTO,
    MedianFilterConfigDTO,
    FilterType,
)

from oak_vision_system.modules.config_manager.validators import (
    validate_dto_structure,
    run_all_validations,
)

__all__ = [
    # 规划中的对外函数名（后续实现）
    # 'build_template_device_manager_config',
    # 'build_default_device_manager_config',
    # 底层模板函数导出
    'template_SystemConfigDTO',
    'template_OAKConfigDTO',
    'template_DisplayConfigDTO',
    'template_FrameIdConfigDTO',
    'template_CANConfigDTO',
    'template_CoordinateTransformConfigDTO',
    'template_MovingAverageFilterConfigDTO',
    'template_KalmanFilterConfigDTO',
    'template_LowpassFilterConfigDTO',
    'template_MedianFilterConfigDTO',
    'template_FilterConfigDTO',
    'template_DataProcessingConfigDTO',
]


# 系统级配置模板工具函数
def template_SystemConfigDTO() -> SystemConfigDTO:
    return SystemConfigDTO(
        # ========== 日志配置 ==========
        log_level="INFO",                  # 日志等级: DEBUG/INFO/WARNING/ERROR/CRITICAL
        log_to_file=False,                 # 是否写入日志文件
        log_file_path=None,                # 日志文件路径
        log_max_size_mb=100,               # 单个日志文件最大大小(MB)
        log_backup_count=7,                # 日志文件备份数量
        log_rotate_mode="time",
        log_rotate_when="MIDNIGHT",
        log_rotate_interval=1,
        log_rotate_utc=False,

        # ========== 性能配置 ==========
        enable_profiling=False,            # 启用性能分析
        max_worker_threads=4,              # 最大工作线程数

        # ========== 系统行为 ==========
        auto_reconnect=True,               # 设备断开后自动重连
        reconnect_interval=5.0,            # 重连间隔(秒)
        max_reconnect_attempts=10,         # 最大重连次数
        graceful_shutdown_timeout=5.0,     # 优雅关闭超时(秒)
    )


# OAK 硬件配置模板
def template_OAKConfigDTO() -> OAKConfigDTO:
    return OAKConfigDTO(
        # ===== 推理模型 =====
        model_path=None,                          # 推理模型路径，None表明未指定
        label_map=["durian", "person"],           # 标签映射表，指定类别名列表
        num_classes=2,                            # 类别数量（需与label_map一致）
        confidence_threshold=0.5,                 # 置信度阈值，低于该值的目标会被过滤
        nms_threshold=0.4,                        # 非极大值抑制阈值
        max_detections=-1,                        # 最大检测目标数，-1表示不限制

        # ===== 视觉参数 =====
        rgb_resolution=(1920, 1080),              # 传感器RGB分辨率
        preview_resolution=(640, 480),            # 预览帧分辨率（显示或加速用）
        hardware_fps=20,                          # 期望相机运行帧率

        # ===== 硬件接口参数 =====
        usb2_mode=True,                           # 是否启用USB2兼容模式

        # ===== 深度相关 =====
        enable_depth_output=True,                        # 是否启用深度信息
        depth_resolution=(640, 480),              # 深度视图分辨率
        depth_min_threshold=400.0,                # 深度最小阈值（单位:mm）
        depth_max_threshold=6000.0,               # 深度最大阈值（单位:mm）
        align_depth_to_rgb=True,                  # 将深度图与RGB对齐
        median_filter=5,                          # 深度中值滤波内核大小（取值：5、7等奇数）
        left_right_check=True,                    # 是否启用左右视差检查优化遮挡
        extended_disparity=False,                 # 是否扩展视差范围
        subpixel=False,                           # 是否启用亚像素精度深度计算

        # ===== 队列相关 =====
        queue_max_size=4,                         # 数据队列最大长度
        queue_blocking=False,                     # 数据队列满时是否阻塞（否则丢弃旧数据）
    )
# role_bindings默认模板函数
def template_DeviceRoleBindingDTO(
    roles: Optional[List[DeviceRole]] = None,
) -> Dict[DeviceRole, DeviceRoleBindingDTO]:
    """
    构建 DeviceRole 到 DeviceRoleBindingDTO 的默认映射。

    Args:
        roles: 可选的角色列表；未提供时使用稳定顺序的默认角色列表。

    Returns:
        Dict[DeviceRole, DeviceRoleBindingDTO]: 以 DeviceRole 为键、DeviceRoleBindingDTO 为值的映射字典。
    """
    selected_roles = roles if roles is not None else DeviceRole.get_expected_roles_ordered()
    role_bindings = {role: DeviceRoleBindingDTO(role=role) for role in selected_roles}
    return role_bindings

# OAK模块配置模板工具
def template_OAKModuleConfigDTO(devices: Optional[List[DeviceMetadataDTO]] = None) -> OAKModuleConfigDTO:
    """
    构建 OAKModuleConfigDTO 的默认模板。

    Args:
        devices: 设备元数据列表。

    Returns:
        OAKModuleConfigDTO: 默认的 OAKModuleConfigDTO 模板。
    """
    role_bindings = template_DeviceRoleBindingDTO()
    hardware_config = template_OAKConfigDTO()
    if devices is None:
        device_metadata = {}
    else:   
        device_metadata = {d.mxid: d for d in devices}
    return OAKModuleConfigDTO(
        role_bindings=role_bindings,
        hardware_config=hardware_config,
        device_metadata=device_metadata,
    )



# Display 配置模板
def template_DisplayConfigDTO() -> DisplayConfigDTO:
    return DisplayConfigDTO(
        # ===== 显示开关 =====
        enable_display=True,                 # 是否启用图像显示

        # ===== 窗口配置 =====
        default_display_mode="combined",    # 窗口显示模式: rgb/depth/combined/side_by_side
        enable_fullscreen=False,             # 是否全屏
        window_width=1280,                   # 窗口宽度
        window_height=720,                   # 窗口高度
        window_position_x=0,                 # 窗口位置 X
        window_position_y=0,                 # 窗口位置 Y

        # ===== 渲染参数 =====
        target_fps=20,                       # 目标显示帧率
        enable_vsync=False,                  # 是否启用垂直同步

        # ===== 叠加信息 =====
        show_detection_boxes=True,           # 显示检测框
        show_labels=True,                    # 显示标签
        show_confidence=True,                # 显示置信度
        show_coordinates=True,               # 显示3D坐标
        show_fps=True,                       # 显示帧率
        show_device_info=True,               # 显示设备信息

        # ===== 深度图显示 =====
        depth_colormap="JET",               # 深度图颜色映射: JET/RAINBOW/BONE/TURBO/HOT/COOL
        depth_alpha=0.6,                     # 深度图叠加透明度(0-1)
        normalize_depth=True,                # 是否归一化深度显示

        # ===== 检测框样式 =====
        bbox_thickness=2,                    # 边框粗细
        bbox_color_by_label=True,            # 按标签着色
        text_scale=0.6,                      # 文字大小
    )


# CAN 帧ID模板（最小：空表）
def template_FrameIdConfigDTO() -> FrameIdConfigDTO:
    # 帧ID配置（传空字典以满足最小模板需求）
    return FrameIdConfigDTO(frames={})


# CAN 配置模板
def template_CANConfigDTO() -> CANConfigDTO:
    return CANConfigDTO(
        enable_can=False,                  # 是否启用CAN总线
        can_interface='socketcan',         # CAN接口类型（如 socketcan）
        can_channel='can0',                # CAN通道（如 can0）
        can_bitrate=250000,                # CAN比特率
        send_timeout_ms=100,               # 发送超时时间（毫秒）
        receive_timeout_ms=200,            # 接收超时时间（毫秒）
        frame_ids=template_FrameIdConfigDTO(),  # 帧ID详细配置
    )


# 坐标变换配置模板（硬编码左右相机参数，返回映射）
def template_CoordinateTransformConfigDTO() -> Dict[DeviceRole, CoordinateTransformConfigDTO]:
    date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    return {
        DeviceRole.LEFT_CAMERA: CoordinateTransformConfigDTO(
            role=DeviceRole.LEFT_CAMERA,
            translation_x=-50.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0,
            calibration_date=date_str,
            calibration_method=None,
        ),
        DeviceRole.RIGHT_CAMERA: CoordinateTransformConfigDTO(
            role=DeviceRole.RIGHT_CAMERA,
            translation_x=50.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0,
            calibration_date=date_str,
            calibration_method=None,
        ),
    }


# 各滤波器模板
def template_MovingAverageFilterConfigDTO() -> MovingAverageFilterConfigDTO:
    return MovingAverageFilterConfigDTO(window_size=5, weighted=False)


def template_KalmanFilterConfigDTO() -> KalmanFilterConfigDTO:
    return KalmanFilterConfigDTO(kalman_gain=0.5, process_noise=0.1, measurement_noise=0.5)


def template_LowpassFilterConfigDTO() -> LowpassFilterConfigDTO:
    return LowpassFilterConfigDTO(cutoff_frequency=5.0)


def template_MedianFilterConfigDTO() -> MedianFilterConfigDTO:
    return MedianFilterConfigDTO(window_size=5)


def template_FilterConfigDTO(filter_type: FilterType = FilterType.MOVING_AVERAGE) -> FilterConfigDTO:
    # 显式提供与类型匹配的子配置，尽管 DTO 的 _post_init_hook 也会兜底
    if filter_type == FilterType.MOVING_AVERAGE:
        return FilterConfigDTO(
            filter_type=FilterType.MOVING_AVERAGE,
            moving_average_config=template_MovingAverageFilterConfigDTO(),
        )
    if filter_type == FilterType.KALMAN:
        return FilterConfigDTO(
            filter_type=FilterType.KALMAN,
            kalman_config=template_KalmanFilterConfigDTO(),
        )
    if filter_type == FilterType.LOWPASS:
        return FilterConfigDTO(
            filter_type=FilterType.LOWPASS,
            lowpass_config=template_LowpassFilterConfigDTO(),
        )
    if filter_type == FilterType.MEDIAN:
        return FilterConfigDTO(
            filter_type=FilterType.MEDIAN,
            median_config=template_MedianFilterConfigDTO(),
        )
    # 兜底：返回默认滑动平均
    return FilterConfigDTO(
        filter_type=FilterType.MOVING_AVERAGE,
        moving_average_config=template_MovingAverageFilterConfigDTO(),
    )


# 数据处理配置模板（含坐标变换与滤波）
def template_DataProcessingConfigDTO(roles: Optional[List[DeviceRole]] = None) -> DataProcessingConfigDTO:
    all_transforms = template_CoordinateTransformConfigDTO()
    if roles is None:
        transforms = all_transforms
    else:
        transforms = {role: all_transforms[role] for role in roles if role in all_transforms}
    # 构造并返回 DataProcessingConfigDTO，包含坐标变换配置、滤波器配置等核心参数
    return DataProcessingConfigDTO(
        coordinate_transforms=transforms,  # 坐标变换配置，按设备角色映射
        filter_config=template_FilterConfigDTO(FilterType.MOVING_AVERAGE),  # 默认使用滑动平均滤波
        enable_data_logging=False,  # 是否开启数据日志记录
        processing_thread_priority=5,  # 处理线程优先级（越高优先级越高，5为中等）
        person_timeout_seconds=5.0,  # 人员跟踪数据超时时间（秒）
    )



# 设备管理器配置模板
def template_DeviceManagerConfigDTO(devices: List[DeviceMetadataDTO]) -> DeviceManagerConfigDTO:
    """
    构建 DeviceManagerConfigDTO 的默认模板。外部必须进行验证。

    Args:
        devices: 设备元数据列表。

    Returns:
        DeviceManagerConfigDTO: 默认的 DeviceManagerConfigDTO 模板。
    """
    return DeviceManagerConfigDTO(
        config_version="2.0.0",
        oak_module=template_OAKModuleConfigDTO(devices),
        data_processing_config=template_DataProcessingConfigDTO(),
        can_config=template_CANConfigDTO(),
        display_config=template_DisplayConfigDTO(),
        system_config=template_SystemConfigDTO(),
    )