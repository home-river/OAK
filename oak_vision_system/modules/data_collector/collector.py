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
from typing import Optional, Dict, Union, List
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
from oak_vision_system.core.dto.config_dto import DeviceRoleBindingDTO
from oak_vision_system.core.event_bus import EventBus, EventType, get_event_bus
import logging
import depthai as dai




class OAKDataCollector:
    def __init__(self,config:OAKModuleConfigDTO,event_bus: Optional[EventBus]=None) -> None:
        """初始化采集器，注入 PipelineManager、事件总线与系统配置"""
        self.config = config
        self.pipeline_manager = PipelineManager(config.hardware_config)
        self.event_bus = event_bus or get_event_bus()
        self.running: Dict[str, bool] = self._init_running_from_config()
        self._worker_threads: Dict[str, threading.Thread] = {}
        self._running_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

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
    
    def _init_pipeline(self) -> None:
        """
        初始化 DepthAI Pipeline。

        根据配置中的 enable_depth_output 决定使用哪个方法创建pipeline。
        创建后的 pipeline 将保存在 PipelineManager 中（self.pipeline_manager.pipeline）。

        Raises:
            RuntimeError: 管线创建失败时抛出异常
        """
        enable_depth_output = self.config.hardware_config.enable_depth_output
        if enable_depth_output:
            self.pipeline_manager.create_pipeline()
        else:
            self.pipeline_manager.create_pipeline_with_no_depth_output()

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



    def _start_OAK_with_device(self, device_binding: DeviceRoleBindingDTO) -> None:

        """
        通过使用device_binding中的MXid启动OAK设备，组装视频帧和数据帧并发布，开启OAK检测循环。

        Args:
            device_binding: 设备角色绑定信息

        Raises:
            ValueError: 设备未绑定MXid，无法启动采集
            RuntimeError: 启动OAK设备失败
        """
        if self.pipeline_manager.pipeline is None:
            self._init_pipeline()
            self.logger.warning("Pipeline 尚未创建，已使用默认创建pipeline")

        if device_binding.active_mxid is None:
            self.logger.error("设备%s未绑定MXid，无法启动采集", device_binding.role)
            raise ValueError(f"设备{device_binding.role}未绑定MXid，无法启动采集")

        # 使用dai.Device启动OAK设备
        pipeline = self.pipeline_manager.pipeline
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


    
    


    def start(self) -> Dict[str, Union[List[str], Dict[str, str]]]:
        """
        启动采集流程，按设备角色启动对应的线程。

        Returns:
            Dict: 结构化结果，包含以下键：
                - started: List[str]，成功启动的角色列表（role.value）
                - skipped: Dict[str, str]，跳过的角色及原因（例如 "no_active_mxid"）
        """
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