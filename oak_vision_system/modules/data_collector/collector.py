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
from typing import Optional, Dict, Any, Union, List
from oak_vision_system.modules.data_collector.pipelinemanager import PipelineManager
from oak_vision_system.core.dto import VideoFrameDTO, DeviceDetectionDataDTO
from oak_vision_system.core.dto.config_dto.oak_module_config_dto import OAKModuleConfigDTO
from oak_vision_system.core.dto.config_dto import DeviceRoleBindingDTO
from oak_vision_system.core.dto.detection_dto import (
    SpatialCoordinatesDTO,BoundingBoxDTO,DetectionDTO,
    DeviceDetectionDataDTO,VideoFrameDTO,OAKDataCollectionDTO,
)
from oak_vision_system.core.event_bus import EventBus, EventType
import logging
import depthai as dai



class OAKDataCollector:
    def __init__(self,config:OAKModuleConfigDTO,event_bus: Optional[EventBus]=None) -> None:
        """初始化采集器，注入 PipelineManager、事件总线与系统配置"""
        self.config = config
        self.pipeline_manager = PipelineManager(config.hardware_config)

        self.event_bus = event_bus or EventBus.get_instance()
        # 使用配置中的角色绑定（DeviceRoleBindingDTO）初始化running字典
        self.running: Dict[DeviceRoleBindingDTO, bool] = self._init_running_from_config()
        self.logger = logging.getLogger(__name__)
        
        # 帧计数器（按设备绑定管理）
        self._frame_counters: Dict[DeviceRoleBindingDTO, int] = {}
        for binding in self.running.keys():
            self._frame_counters[binding] = 0

    def _init_running_from_config(self) -> Dict[DeviceRoleBindingDTO, bool]:
        """
        从配置中的 role_bindings 初始化running字典，使用 DeviceRoleBindingDTO 作为 key。
        
        这样设计的优势：
        - DeviceRoleBindingDTO 包含完整的绑定信息（role、active_mxid、historical_mxids等）
        - 可以直接通过 binding 访问当前激活的 MXid 和角色信息
        - 即使物理设备更换（MXid变化），binding 对象仍然可以正常工作
        
        Returns:
            Dict[DeviceRoleBindingDTO, bool]: 设备角色绑定到运行状态的映射，初始值都为False
        """
        running_dict: Dict[DeviceRoleBindingDTO, bool] = {}
        
        # 从 role_bindings 中获取所有绑定，初始化运行状态
        for binding in self.config.role_bindings.values():
            running_dict[binding] = False
        
        return running_dict
    
    def _init_pipeline(self) -> None:
        """
        初始化 DepthAI Pipeline。

        使用PipelineManager的create_pipeline_with_no_depth_output方法创建pipeline。
        创建后的pipeline对象将被保存在self._pipeline中。

        Raises:
            RuntimeError: 管线创建失败时抛出异常
        """
        self.pipeline_manager.create_pipeline_with_no_depth_output()
        self._pipeline = self.pipeline_manager.get_pipeline()



    def _publish_data(self, data: Union[VideoFrameDTO, DeviceDetectionDataDTO]) -> None:
        """发布视频帧或检测数据的私有方法"""
        if isinstance(data, VideoFrameDTO):
            self.event_bus.publish(EventType.RAW_FRAME_DATA, data)
        elif isinstance(data, DeviceDetectionDataDTO):
            self.event_bus.publish(EventType.RAW_DETECTION_DATA, data)
        else:
            self.logger.error(f"不支持的数据类型: {type(data)}")
            raise ValueError(f"不支持的数据类型: {type(data)}")

    def _assemble_frame_data_event(
        self,
        device_binding: DeviceRoleBindingDTO,
        frame_data: dai.ImgFrame
    ) -> Optional[VideoFrameDTO]:
        """
        组装原始视频帧数据 DTO。

        将 DepthAI 的 ImgFrame 转换为 VideoFrameDTO。

        Args:
            device_binding: 设备角色绑定信息
            frame_data: DepthAI 的 ImgFrame 对象（RGB 帧）
        
        Returns:
            VideoFrameDTO 对象，如果转换失败返回 None
        """
        if frame_data is None:
            return None
        
        try:
            # 获取设备ID
            device_id = device_binding.active_mxid
            if device_id is None:
                self.logger.error("设备ID为空，无法组装帧数据: %s", device_binding.role.value)
                return None
            
            # 获取当前帧ID并递增
            frame_id = self._frame_counters.get(device_binding, 0)
            
            # 从 DepthAI ImgFrame 转换为 OpenCV 格式
            cv_frame = frame_data.getCvFrame()
            if cv_frame is None:
                self.logger.warning("无法从 ImgFrame 获取 OpenCV 帧: device=%s", device_binding.role.value)
                return None
            
            # 获取帧尺寸
            frame_height, frame_width = cv_frame.shape[:2]
            
            # 创建 VideoFrameDTO
            video_frame = VideoFrameDTO(
                device_id=device_id,
                frame_id=frame_id,
                rgb_frame=cv_frame,
                frame_width=frame_width,
                frame_height=frame_height
            )
            
            # 更新帧计数器（在成功创建 DTO 后）
            self._frame_counters[device_binding] = frame_id + 1
            
            return video_frame
            
        except Exception as e:
            self.logger.exception(
                "组装视频帧事件数据失败: device=%s, error=%s",
                device_binding.role.value,
                e
            )
            return None

    def _assemble_detection_data_event(
        self,
        device_binding: DeviceRoleBindingDTO,
        detections_data: dai.SpatialImgDetections
    ) -> Optional[DeviceDetectionDataDTO]:
        """
        组装原始检测数据 DTO。

        将 DepthAI 的 SpatialImgDetections 转换为 DeviceDetectionDataDTO。

        Args:
            device_binding: 设备角色绑定信息
            detections_data: DepthAI 的 SpatialImgDetections 对象
        
        Returns:
            DeviceDetectionDataDTO 对象，如果转换失败返回 None
        """
        if detections_data is None:
            return None
        
        try:
            # 获取设备ID
            device_id = device_binding.active_mxid
            if device_id is None:
                self.logger.error("设备ID为空，无法组装检测数据: %s", device_binding.role.value)
                return None
            
            # 获取当前帧ID（与视频帧同步，使用上次的帧ID）
            frame_id = max(0, self._frame_counters.get(device_binding, 0) - 1)
            
            # 获取设备别名
            device_alias = None
            if device_id in self.config.device_metadata:
                metadata = self.config.device_metadata[device_id]
                device_alias = getattr(metadata, 'alias', None)
            
            # 获取标签映射
            label_map = self.config.hardware_config.label_map
            
            # 转换检测结果列表
            detections_list: List[DetectionDTO] = []
            
            for detection in detections_data.detections:
                try:
                    # 提取边界框坐标
                    xmin = float(detection.xmin)
                    ymin = float(detection.ymin)
                    xmax = float(detection.xmax)
                    ymax = float(detection.ymax)
                    
                    # 验证边界框有效性
                    if xmin >= xmax or ymin >= ymax:
                        self.logger.warning(
                            "无效的边界框坐标: xmin=%.2f, ymin=%.2f, xmax=%.2f, ymax=%.2f",
                            xmin, ymin, xmax, ymax
                        )
                        continue
                    
                    # 创建边界框 DTO
                    bbox = BoundingBoxDTO(
                        xmin=xmin,
                        ymin=ymin,
                        xmax=xmax,
                        ymax=ymax
                    )
                    
                    # 提取空间坐标（毫米单位）
                    spatial_x = float(detection.spatialCoordinates.x)
                    spatial_y = float(detection.spatialCoordinates.y)
                    spatial_z = float(detection.spatialCoordinates.z)
                    
                    # 创建空间坐标 DTO
                    spatial_coords = SpatialCoordinatesDTO(
                        x=spatial_x,
                        y=spatial_y,
                        z=spatial_z
                    )
                    
                    # 获取标签名称
                    label_index = int(detection.label) if hasattr(detection, 'label') else 0
                    if 0 <= label_index < len(label_map):
                        label = label_map[label_index]
                    else:
                        self.logger.warning(
                            "标签索引超出范围: index=%d, label_map_size=%d, 使用默认标签",
                            label_index,
                            len(label_map)
                        )
                        label = "unknown"
                    
                    # 获取置信度
                    confidence = float(detection.confidence)
                    
                    # 验证置信度范围
                    if not (0.0 <= confidence <= 1.0):
                        self.logger.warning(
                            "置信度超出范围 [0,1]: %.4f, 已限制",
                            confidence
                        )
                        confidence = max(0.0, min(1.0, confidence))
                    
                    # 创建 DetectionDTO
                    detection_dto = DetectionDTO(
                        label=label,
                        confidence=confidence,
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



    def _start_OAK_with_device(self,device_binding:DeviceRoleBindingDTO) -> None:

        if self.pipeline_manager.pipeline is None:
            self._init_pipeline()
            self.logger.warning("Pipeline 尚未创建，已使用默认创建pipeline")

        if device_binding.active_mxid is None:
            self.logger.error("设备%s未绑定MXid，无法启动采集",device_binding.role)
            raise ValueError(f"设备{device_binding.role}未绑定MXid，无法启动采集")

        # 使用dai.Device启动OAK设备
        pipeline = self.pipeline_manager.pipeline
        device_info = dai.DeviceInfo(device_binding.active_mxid)
        usb_mode = self.config.hardware_config.usb2_mode
        self.running[device_binding] = True
        try:
            with dai.Device(pipeline,device_info,usb2Mode=usb_mode) as device:
                previewQueue = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
                detectionNNQueue = device.getOutputQueue(name="detections", maxSize=4, blocking=False)


                while self.running[device_binding]:
                    previewFrame = previewQueue.get()
                    detectionFrame = detectionNNQueue.get()
                    # 组装并发布视频帧
                    frame_dto = self._assemble_frame_data_event(device_binding, previewFrame)
                    if frame_dto is not None:
                        self._publish_data(frame_dto)
                    # 组装并发布检测数据
                    detection_dto = self._assemble_detection_data_event(device_binding, detectionFrame)
                    if detection_dto is not None:
                        self._publish_data(detection_dto)
                

                
        
        except Exception as e:
            self.logger.exception(f"启动OAK设备{device_binding.role}失败: {e}")
            raise RuntimeError(f"启动OAK设备{device_binding.role}失败: {e}")

        # 使用私有方法组装RawFrameDataEvent和RawDetectionDataEvent

        # 内部使用事件发布逻辑发布数据帧和视频帧（使用私有方法）


    
    


    def start(self) -> bool:
        """启动采集流程（仅定义接口）"""
        pass

    def stop(self) -> None:
        """停止采集流程并释放资源（仅定义接口）"""
        pass