"""
OAK数据采集模块，负责启动OAK设备的pipeline并采集数据，发布视频帧事件和数据帧事件。

接收配置管理器处理过的OAKModuleConfigDTO（绑定设备之后的），根据配置创建pipeline，并启动采集流程。
发布视频帧事件和数据帧事件。

职责：
- 启动OAK设备的pipeline并采集数据
- 发布视频帧事件和数据帧事件
- 获取采集器当前状态信息



"""
from __future__ import annotations
from typing import Optional, Dict, Union, List, Set
import threading
import time
from oak_vision_system.modules.data_collector.pipelinemanager import PipelineManager
from oak_vision_system.core.backpressure import (
    BackpressureState,
    BackpressureAction,
    BackpressureEventPayload,
)
from oak_vision_system.core.dto import (
    SpatialCoordinatesDTO,
    BoundingBoxDTO,
    DetectionDTO,
    DeviceDetectionDataDTO,
    VideoFrameDTO,
)
from oak_vision_system.core.dto.config_dto.oak_module_config_dto import OAKModuleConfigDTO
from oak_vision_system.core.dto.config_dto import DeviceRoleBindingDTO, DeviceMetadataDTO
from oak_vision_system.core.event_bus import EventBus, EventType, get_event_bus
import logging
import depthai as dai
from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery


class OAKDataCollector:
    def __init__(
        self,
        config: OAKModuleConfigDTO,
        event_bus: Optional[EventBus] = None,
        available_devices: Optional[List[DeviceMetadataDTO]] = None
    ) -> None:
        """
        初始化采集器，注入 PipelineManager、事件总线与系统配置
        
        Args:
            config: OAK模块配置
            event_bus: 事件总线实例（可选，默认使用全局单例）
            available_devices: 可用设备元数据列表（可选）
                用于在 start() 时预检设备可用性，避免启动不可用的设备
                如果为 None，则跳过预检（向后兼容）
        """
        self.config = config
        self.pipeline_manager = PipelineManager(config.hardware_config)
        self.event_bus = event_bus or get_event_bus()
        self.running: Dict[str, bool] = self._init_running_from_config()
        self._worker_threads: Dict[str, threading.Thread] = {}
        self._running_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

        # 存储可用设备列表（用于启动前预检）
        self._available_devices = available_devices
        self._available_mxids: Set[str] = set()
        if available_devices is not None:
            self._available_mxids = {device.mxid for device in available_devices}
            self.logger.debug(
                "初始化时提供了 %d 个可用设备: %s",
                len(self._available_mxids),
                list(self._available_mxids)
            )
            # 执行设备可用性检查
            self._validate_device_availability()

        # 背压配置
        self._bp_lock = threading.Lock()
        self._bp_action = BackpressureAction.NORMAL

        fps = getattr(self.config.hardware_config, "hardware_fps", 20)
        fps = max(1, int(fps))

        # 时间闸门（单位：秒）
        self._pause_min_interval_s = 1.0 / fps          # PAUSE = 暂停
        self._pressure_time_interval_s = 2.0 / fps        # THROTTLE = 半速

        self._gate_lock = threading.Lock()
        self._next_allowed_ts: Dict[str, float] = {}

        self._init_subscribers()
        
        # 帧计数器（按设备绑定管理）
        self._frame_counters: Dict[str, int] = {}
        for role in self.running.keys():
            self._frame_counters[role] = 0
            self._next_allowed_ts[role] = 0.0

    def _set_running_state(self, binding: DeviceRoleBindingDTO | str, value: bool) -> None:
        """线程安全地更新设备运行状态"""
        key = binding.role.value if hasattr(binding, "role") else binding
        with self._running_lock:
            self.running[key] = value

    def _is_running(self, binding: DeviceRoleBindingDTO | str) -> bool:
        """线程安全地读取设备运行状态"""
        key = binding.role.value if hasattr(binding, "role") else binding
        with self._running_lock:
            return self.running.get(key, False)
    
    def _init_running_from_config(self) -> Dict[str, bool]:
        """
        从配置中的 role_bindings 初始化running字典，使用 role.value 作为 key。
        
        Returns:
            Dict[DeviceRole.value, bool]: 设备角色绑定到运行状态的映射，初始值都为False
        """
        running_dict: Dict[str, bool] = {}
        
        # 从 role_bindings 中获取所有绑定，初始化运行状态
        for binding in self.config.role_bindings.values():
            role_key = binding.role.value
            running_dict[role_key] = False
        
        return running_dict
    
    def _validate_device_availability(self) -> None:
        """
        验证配置中的设备是否在可用设备列表中
        
        在初始化时调用，如果所有配置的设备都不可用，则抛出异常。
        这样可以在创建实例时就发现配置错误，而不是等到 start() 时才失败。
        
        Raises:
            RuntimeError: 如果所有配置的设备都不可用
        """
        # 收集所有需要的设备 MXID
        required_mxids = set()
        for binding in self.config.role_bindings.values():
            if binding.active_mxid:
                required_mxids.add(binding.active_mxid)
        
        # 如果没有配置任何设备，跳过检查
        if not required_mxids:
            self.logger.warning("配置中没有绑定任何设备")
            return
        
        # 检查是否有任何设备可用
        unavailable_mxids = required_mxids - self._available_mxids
        available_mxids = required_mxids & self._available_mxids
        
        if unavailable_mxids:
            self.logger.warning(
                "检测到不可用的设备: %s",
                list(unavailable_mxids)
            )
        
        if not available_mxids:
            # 所有设备都不可用，抛出异常
            error_msg = (
                f"所有配置的设备都不可用。"
                f"需要的设备: {list(required_mxids)}, "
                f"可用设备: {list(self._available_mxids)}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        self.logger.info(
            "设备可用性检查通过: %d/%d 个设备可用",
            len(available_mxids),
            len(required_mxids)
        )
    
    def _init_subscribers(self) -> None:
        """
        初始化内部订阅

        当前订阅包括：
        订阅背压事件
        """
        self.event_bus.subscribe(EventType.BACKPRESSURE_SIGNAL, self._handle_backpressure_signal)
    
    def _handle_backpressure_signal(self, event: BackpressureEventPayload) -> None:
        """处理背压事件"""
        with self._bp_lock:
            self._bp_action = event.action


    def _publish_data(self, data: Union[VideoFrameDTO, DeviceDetectionDataDTO]) -> None:
        """发布视频帧或检测数据的私有方法"""
        if isinstance(data, VideoFrameDTO):
            self.event_bus.publish(EventType.RAW_FRAME_DATA, data)
        elif isinstance(data, DeviceDetectionDataDTO):
            self.event_bus.publish(EventType.RAW_DETECTION_DATA, data)
        else:
            self.logger.error("不支持的数据类型: %s", type(data))
            raise ValueError(f"不支持的数据类型: {type(data)}")

    def _assemble_frame_data(
        self,
        device_binding: DeviceRoleBindingDTO,
        rgb_frame: dai.ImgFrame,
        depth_frame: Optional[dai.ImgFrame] = None,
        frame_id: Optional[int] = None
    ) -> Optional[VideoFrameDTO]:
        """
        组装原始视频帧数据 DTO。

        将 DepthAI 的 ImgFrame 转换为 VideoFrameDTO。

        Args:
            device_binding: 设备角色绑定信息
            rgb_frame: DepthAI 的 ImgFrame 对象（RGB 帧）
            depth_frame: DepthAI 的 ImgFrame 对象（深度帧），可选
                        如果配置中 enable_depth_output=True，则此参数必须提供
            frame_id: 采集循环级别的帧ID，用于数据对齐。如果未提供则使用计数器
        
        Returns:
            VideoFrameDTO 对象，如果转换失败返回 None
        """
        enable_depth_output = self.config.hardware_config.enable_depth_output
        
        # RGB 帧是必需的
        if rgb_frame is None:
            self.logger.warning("RGB帧为空，无法组装帧数据: device=%s", device_binding.role.value)
            return None
        
        # 如果启用了深度，则必须提供深度数据
        if enable_depth_output:
            if depth_frame is None:
                self.logger.warning(
                    "启用深度模式但未提供深度数据: device=%s",
                    device_binding.role.value
                )
                return None
        
        try:
            # 获取设备ID
            device_id = device_binding.active_mxid
            if device_id is None:
                self.logger.error("设备ID为空，无法组装帧数据: %s", device_binding.role.value)
                return None
            
            # 使用传入的frame_id，如果未提供则使用计数器（向后兼容）
            if frame_id is None:
                role_key = device_binding.role.value
                frame_id = self._frame_counters.get(role_key, 0)
            
            # 从 DepthAI ImgFrame 转换为 OpenCV 格式
            cv_frame = rgb_frame.getCvFrame()
            if cv_frame is None:
                self.logger.warning("无法从 ImgFrame 获取 OpenCV 帧: device=%s", device_binding.role.value)
                return None
            
            
            # 处理深度数据（如果启用）
            depth_frame_data = None
            if enable_depth_output:
                # 此时 depth_frame 已经确保不为 None（前面已检查）
                try:
                    # 从 DepthAI ImgFrame 获取深度数据（numpy.ndarray，uint16，单位：毫米）
                    depth_frame_data = depth_frame.getFrame()
                    if depth_frame_data is None:
                        self.logger.warning(
                            "无法从深度 ImgFrame 获取深度数据: device=%s",
                            device_binding.role.value
                        )
                        # 如果深度数据获取失败，返回 None（因为配置要求启用深度）
                        return None
                except Exception as e:
                    self.logger.error(
                        "获取深度数据失败: device=%s, error=%s",
                        device_binding.role.value,
                        e
                    )
                    # 如果深度数据获取失败，返回 None（因为配置要求启用深度）
                    return None
            # 如果未启用深度，depth_frame_data 保持为 None，即使传入了 depth_frame 也不会使用
            
            # 创建 VideoFrameDTO
            video_frame = VideoFrameDTO(
                device_id=device_id,
                frame_id=frame_id,
                rgb_frame=cv_frame,
                depth_frame=depth_frame_data
            )
            
            return video_frame
            
        except Exception as e:
            self.logger.exception(
                "组装视频帧事件数据失败: device=%s, error=%s",
                device_binding.role.value,
                e
            )
            return None

    def _assemble_detection_data(
        self,
        device_binding: DeviceRoleBindingDTO,
        detections_data: dai.SpatialImgDetections,
        frame_id: Optional[int] = None
    ) -> Optional[DeviceDetectionDataDTO]:
        """
        组装原始检测数据 DTO。

        将 DepthAI 的 SpatialImgDetections 转换为 DeviceDetectionDataDTO。

        Args:
            device_binding: 设备角色绑定信息
            detections_data: DepthAI 的 SpatialImgDetections 对象
            frame_id: 采集循环级别的帧ID，用于数据对齐。如果未提供则使用计数器
        
        Returns:
            DeviceDetectionDataDTO 对象，如果转换失败返回 None
        """
        if detections_data is None:
            return None
        
        try:
            # 获取设备ID
            device_id = device_binding.active_mxid
            if device_id is None:
                self.logger.error("设备ID为空，无法组装检测数据: %s", device_binding.role)
                return None
            
            # 使用传入的frame_id，如果未提供则使用计数器（向后兼容）
            if frame_id is None:
                role_key = device_binding.role.value
                frame_id = self._frame_counters.get(role_key, 0)
            
            # 获取设备别名（使用角色枚举的value）
            device_alias = device_binding.role.value
            
            # 转换检测结果列表
            detections_list: List[DetectionDTO] = []
            
            for detection in detections_data.detections:
                try:
                    # 提取边界框坐标
                    # dai.SpatialImgDetection 的 xmin/ymin/xmax/ymax 已为 float 类型，无需强制转换
                    
                    
                    # 创建边界框 DTO
                    bbox = BoundingBoxDTO(
                        xmin=detection.xmin,
                        ymin=detection.ymin,
                        xmax=detection.xmax,
                        ymax=detection.ymax
                    )
                    
                    # 提取空间坐标（毫米单位）
                    # 创建空间坐标 DTO
                    spatial_coords = SpatialCoordinatesDTO(
                        x=detection.spatialCoordinates.x,
                        y=detection.spatialCoordinates.y,
                        z=detection.spatialCoordinates.z
                    )
                    
                    # 获取类别ID
                    label = detection.label if hasattr(detection, 'label') else 0
                    
                    
                    
                    # 创建 DetectionDTO
                    detection_dto = DetectionDTO(
                        label=label,
                        confidence=detection.confidence,
                        bbox=bbox,
                        spatial_coordinates=spatial_coords
                    )
                    
                    detections_list.append(detection_dto)
                    
                except Exception as e:
                    self.logger.warning(
                        "转换单个检测结果失败: device=%s, error=%s",
                        device_binding.role.value,
                        e
                    )
                    continue
            
            # 创建 DeviceDetectionDataDTO
            device_detection_dto = DeviceDetectionDataDTO(
                device_id=device_id,
                frame_id=frame_id,
                device_alias=device_alias,
                detections=detections_list
            )
            
            return device_detection_dto
            
        except Exception as e:
            self.logger.exception(
                "组装检测数据事件失败: device=%s, error=%s",
                device_binding.role.value,
                e
            )
            return None

    def _create_pipeline_for_device(self, device_binding: DeviceRoleBindingDTO) -> dai.Pipeline:
        """
        为指定设备创建 pipeline（根据配置选择创建方式）
        
        当前策略：优先使用旧版 pipeline 进行调试，验证线程内创建方案的可行性。
        等旧版 pipeline 调试通过后，再启用根据配置创建的逻辑。
        
        Args:
            device_binding: 设备角色绑定信息
            
        Returns:
            dai.Pipeline: 创建的 pipeline 对象
            
        Raises:
            RuntimeError: pipeline 创建失败
        """
        # ========== 调试阶段：使用旧版 pipeline ==========
        # 旧版 pipeline 已验证可行，用于测试线程内创建方案
        # self.logger.info(
        #     f"[调试模式] 为设备 {device_binding.role.value} 创建旧版风格 pipeline"
        # )
        # pipeline = self.pipeline_manager.create_pipeline_legacy()
        # return pipeline
        
        
        enable_depth_output = self.config.hardware_config.enable_depth_output
        
        if enable_depth_output:
            self.logger.info(
                f"为设备 {device_binding.role.value} 创建带深度输出的 pipeline"
            )
            pipeline = self.pipeline_manager.create_pipeline_new()
        else:
            self.logger.info(
                f"为设备 {device_binding.role.value} 创建不带深度输出的 pipeline"
            )
            pipeline = self.pipeline_manager.create_pipeline_new_no_depth()
        
        return pipeline


    def _start_OAK_with_device(self, device_binding: DeviceRoleBindingDTO) -> None:

        """
        通过使用device_binding中的MXid启动OAK设备，组装视频帧和数据帧并发布，开启OAK检测循环。

        Args:
            device_binding: 设备角色绑定信息

        Raises:
            ValueError: 设备未绑定MXid，无法启动采集
            RuntimeError: 启动OAK设备失败，包括 pipeline 创建失败
        """
        # 验证设备绑定
        if device_binding.active_mxid is None:
            self.logger.error("设备%s未绑定MXid，无法启动采集", device_binding.role)
            raise ValueError(f"设备{device_binding.role}未绑定MXid，无法启动采集")

        # 线程内创建 pipeline（局部变量）
        try:
            self.logger.info(f"为设备 {device_binding.role.value} 创建 pipeline...")
            pipeline = self._create_pipeline_for_device(device_binding)
            self.logger.info(f"设备 {device_binding.role.value} 的 pipeline 创建成功")
        except Exception as e:
            self.logger.error(
                f"为设备 {device_binding.role.value} 创建 pipeline 失败: {e}",
                exc_info=True
            )
            raise RuntimeError(f"创建 pipeline 失败: {e}") from e

        # 使用dai.Device启动OAK设备
        device_info = dai.DeviceInfo(device_binding.active_mxid)
        usb_mode = self.config.hardware_config.usb2_mode
        enable_depth_output = self.config.hardware_config.enable_depth_output
        queue_max_size = self.config.hardware_config.queue_max_size
        queue_blocking = self.config.hardware_config.queue_blocking
        self._set_running_state(device_binding, True)
        
        # 添加调试信息
        self.logger.info(f"尝试连接设备: MXID={device_binding.active_mxid}, USB2模式={usb_mode}")
        
        try:
            with dai.Device(pipeline, device_info, usb2Mode=usb_mode) as device:
                rgb_queue = device.getOutputQueue(name="rgb", maxSize=queue_max_size, blocking=queue_blocking)
                detections_queue = device.getOutputQueue(name="detections", maxSize=queue_max_size, blocking=queue_blocking)
                
                # 根据配置决定是否创建深度队列
                depth_queue = None
                if enable_depth_output:
                    depth_queue = device.getOutputQueue(name="depth", maxSize=queue_max_size, blocking=queue_blocking)

                while self._is_running(device_binding):
                    # 背压处理：根据当前系统压力（由 BACKPRESSURE_SIGNAL 事件更新）动态调整采样行为
                    # - NORMAL   : 正常频率采样
                    # - THROTTLE : 降低采样频率，减轻后端处理压力
                    # - PAUSE    : 暂停采样，只做最小休眠，不再从队列取新数据
                    with self._bp_lock:
                        action = self._bp_action
                    if action == BackpressureAction.PAUSE:
                        # 处于 PAUSE 状态时，不再继续后续处理，直接按最小间隔 sleep
                        time.sleep(self._pause_min_interval_s)
                        continue

                    # interval_s 表示当前循环允许的采样间隔（秒）
                    # NORMAL 下为 _pause_min_interval_s；THROTTLE 下使用更大的 _pressure_time_interval_s 以实现限流
                    interval_s = self._pause_min_interval_s
                    if action == BackpressureAction.THROTTLE:
                        interval_s = self._pressure_time_interval_s

                    # 时间闸门：为每个设备角色维护“下一次允许拉取/处理数据的时间戳”
                    now_ts = time.time()
                    role_key = device_binding.role.value
                    # 读出当前角色的下一次允许时间戳；若尚未设置，则默认 0.0（立即允许）
                    with self._gate_lock:
                        next_allowed_ts = self._next_allowed_ts.get(role_key, 0.0)
                    if now_ts < next_allowed_ts:
                        # 若当前时间尚未到达下一允许时间，则睡眠剩余时间并跳过本轮循环，从而实现节流
                        time.sleep(next_allowed_ts - now_ts)
                        continue
                    # 已到允许时间：更新该角色的下一次允许时间 = 当前时间 + interval_s
                    # 不同角色使用独立的 key，实现“按设备角色维度”的节流控制
                    with self._gate_lock:
                        self._next_allowed_ts[role_key] = now_ts + interval_s

                    # 使用 tryGet() 非阻塞获取数据，避免 stop() 后线程阻塞在 get() 上
                    rgb_frame = rgb_queue.tryGet()
                    det_frame = detections_queue.tryGet()
                    
                    # 获取深度数据（如果启用）
                    depth_frame = None
                    if enable_depth_output and depth_queue is not None:
                        depth_frame = depth_queue.tryGet()
                    
                    # 如果所有队列都为空，检查运行状态并短暂休眠，避免 CPU 空转
                    if rgb_frame is None and det_frame is None:
                        if not self._is_running(device_binding):
                            break  # 如果已停止，立即退出循环
                        # 短暂休眠，避免 CPU 空转
                        time.sleep(0.01)  # 10ms
                        continue
                    
                    # 为本轮循环分配统一的frame_id，确保RGB帧和检测数据使用相同的ID进行对齐
                    # 只在至少获取到一个数据时递增计数器
                    current_frame_id = self._frame_counters.get(role_key, 0)
                    self._frame_counters[role_key] = current_frame_id + 1
                    
                    # 组装视频帧数据（仅在获取到数据时）
                    if rgb_frame is not None:
                        frame_dto = self._assemble_frame_data(
                            device_binding, rgb_frame, depth_frame,
                            frame_id=current_frame_id
                        )
                        if frame_dto is not None:
                            self._publish_data(frame_dto)
                    
                    # 组装检测数据（仅在获取到数据时）
                    if det_frame is not None:
                        detection_dto = self._assemble_detection_data(
                            device_binding, det_frame,
                            frame_id=current_frame_id
                        )
                        if detection_dto is not None:
                            self._publish_data(detection_dto)        
                

                
        
        except Exception as e:
            self.logger.exception("启动OAK设备%s失败: %s", device_binding.role, e)
            raise RuntimeError(f"启动OAK设备{device_binding.role}失败: {e}")


    
    


    def _wait_for_required_mxids_visible(
        self,
        required_mxids: Set[str],
        timeout_sec: float,
        poll_interval_sec: float,
    ) -> bool:
        """
        等待所有指定的 MXID 都可见，或超时。
        
        注意：该方法是阻塞的，直到所有 MXID 都可见，或超时。
        
        Args:
            required_mxids (Set[str]): 要等待的 MXID 集合
            timeout_sec (float): 等待超时时间（秒）
            poll_interval_sec (float): 检查设备状态的间隔时间（秒）
            
        Returns:
            bool: 是否成功等待所有 MXID 可见
        """
        if not required_mxids:
            return True

        t0 = time.perf_counter()
        while True:
            elapsed = time.perf_counter() - t0
            if elapsed >= timeout_sec:
                return False

            infos = OAKDeviceDiscovery.get_all_available_devices(verbose=False)
            present_mxids = {info.mxid for info in infos}
            missing = required_mxids - present_mxids
            if not missing:
                return True

            time.sleep(poll_interval_sec)


    def start(self) -> Union[Dict[str, Union[List[str], Dict[str, str]]], bool]:
        """
        启动采集流程，按设备角色启动对应的线程。
        
        注意：设备可用性检查已在 __init__() 中完成。
        如果所有设备都不可用，__init__() 会抛出异常。
        这里只处理部分设备不可用的情况（跳过不可用的设备）。

        Returns:
            Dict: 结构化结果，包含以下键：
                - started: List[str]，成功启动的角色列表（role.value）
                - skipped: Dict[str, str]，跳过的角色及原因
                    - "no_active_mxid": 未绑定 MXid
                    - "device_not_available": 设备不可用
        """
        required_mxids: Set[str] = set()
        for role, binding in self.config.role_bindings.items():
            if binding.active_mxid:
                if self._available_devices is not None and binding.active_mxid not in self._available_mxids:
                    continue
                required_mxids.add(binding.active_mxid)

        if required_mxids:
            wait_timeout_sec = 20.0
            wait_poll_interval_sec = 0.2
            ok = self._wait_for_required_mxids_visible(
                required_mxids=required_mxids,
                timeout_sec=wait_timeout_sec,
                poll_interval_sec=wait_poll_interval_sec,
            )
            if not ok:
                infos = OAKDeviceDiscovery.get_all_available_devices(verbose=False)
                present_mxids = {info.mxid for info in infos}
                missing = required_mxids - present_mxids
                self.logger.error(
                    "启动前等待设备可见超时(timeout=%ss): missing=%s",
                    wait_timeout_sec,
                    sorted(list(missing)),
                )
                return False

        # 遍历 binding，启动对应的设备
        self._worker_threads.clear()
        result: Dict[str, Union[List[str], Dict[str, str]]] = {
            "started": [],
            "skipped": {},
        }
        for role, binding in self.config.role_bindings.items():
            role_key = role.value
            if not binding.active_mxid:
                # 未绑定有效的 MXid，跳过
                cast_skipped = result["skipped"]  # type: ignore[assignment]
                assert isinstance(cast_skipped, dict)
                cast_skipped[role_key] = "no_active_mxid"
                continue
            
            # 如果提供了可用设备列表，检查设备是否可用
            if self._available_devices is not None:
                if binding.active_mxid not in self._available_mxids:
                    # 设备不可用，跳过
                    cast_skipped = result["skipped"]  # type: ignore[assignment]
                    assert isinstance(cast_skipped, dict)
                    cast_skipped[role_key] = "device_not_available"
                    self.logger.warning(
                        "跳过设备 %s (role=%s): 设备不可用",
                        binding.active_mxid,
                        role_key
                    )
                    continue

            t = threading.Thread(
                target=self._start_OAK_with_device,
                args=(binding,),
                name=f"OAKWorker-{binding.role.value}",
                daemon=True,
            )
            t.start()
            self._worker_threads[role_key] = t
            cast_started = result["started"]  # type: ignore[assignment]
            assert isinstance(cast_started, list)
            cast_started.append(role_key)
            
            # 可选：在设备线程启动之间添加短暂间隔（额外的保险措施）
            # 理论上不需要，因为每个线程独立创建 pipeline，但这可以进一步降低并发压力
            if len(self._worker_threads) < len(self.config.role_bindings):
                time.sleep(0.1)  # 100ms
        
        # 检查是否至少启动了一个设备
        if not result["started"]:
            self.logger.error("没有启动任何设备")
            return False
        
        return result

    def stop(self, timeout: float = 5.0) -> bool:
        """停止所有设备的采集流程
        
        Args:
            timeout: 等待线程停止的超时时间（秒），默认5.0秒
            
        Returns:
            bool: 是否成功停止所有设备
                - True: 所有设备成功停止
                - False: 至少有一个设备停止超时或失败
        """
        with self._running_lock:
            # 1. 幂等性检查：如果所有设备都已停止，直接返回成功
            if not any(self.running.values()):
                self.logger.info("OAKDataCollector 未在运行或已停止")
                return True
            
            self.logger.info("正在停止 OAKDataCollector...")
            
            # 2. 设置停止信号：将所有设备的运行状态设置为 False
            for role_key in list(self.running.keys()):
                self.running[role_key] = False
        
        # 3. 等待所有线程结束（带超时）
        all_stopped = True
        for role_key, thread in list(self._worker_threads.items()):
            if thread.is_alive():
                try:
                    thread.join(timeout=timeout)
                    
                    if thread.is_alive():
                        self.logger.error(
                            "设备线程停止超时 (%ss): device=%s",
                            timeout,
                            role_key
                        )
                        all_stopped = False
                        # 注意：超时时不清理引用，保持状态一致性
                except Exception as e:
                    self.logger.error(
                        "等待设备线程退出失败: device=%s, error=%s",
                        role_key,
                        e
                    )
                    all_stopped = False
        
        # 4. 清理状态（只在所有线程成功停止时执行）
        if all_stopped:
            self._worker_threads.clear()
            self.logger.info("OAKDataCollector 已停止")
        else:
            self.logger.error("OAKDataCollector 停止失败：部分线程未能在超时时间内停止")
        
        return all_stopped