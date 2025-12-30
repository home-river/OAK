"""
渲染包打包器

负责将外部模块传入的数据打包成渲染数据包，并提供给渲染模块使用。
外部数据包括：
1. 视频帧数据
2. 处理后的检测数据ProcessedDetectionDTO
"""

from dataclasses import dataclass, field
from enum import Enum, auto
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading
import time

from oak_vision_system.core.dto.data_processing_dto import ProcessedDetectionDTO, DeviceProcessedDetectionDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.base_dto import BaseDTO
from queue import Queue, Empty
from oak_vision_system.core.event_bus import get_event_bus, EventType
from oak_vision_system.utils import OverflowQueue


@dataclass(frozen=True)
class RenderPacket(BaseDTO):
    """单设备渲染数据包"""
    video_frame: VideoFrameDTO  # 视频帧数据
    processed_detections: Optional[DeviceProcessedDetectionDTO] = None  # 处理后的检测数据  
    
    def _validate_data(self) -> List[str]:
        """渲染数据包验证"""
        errors = []
        
        # 验证视频帧数据
        errors.extend(self.video_frame._validate_data())
        # 验证处理后的检测数据
        if self.processed_detections is not None:
            errors.extend(self.processed_detections._validate_data())
            if self.video_frame is not None:
                # 验证帧id和mxid是否一致
                if self.video_frame.device_id != self.processed_detections.device_id:
                    errors.append(f"视频帧数据和处理后的检测数据设备ID不一致")
                if self.video_frame.frame_id != self.processed_detections.frame_id:
                    errors.append(f"视频帧数据和处理后的检测数据帧ID不一致")
        else:
            errors.extend("渲染包不完整。")

            
        return errors

# ------------------------------------
class DataType(Enum):
    """数据类型枚举"""
    RAW_FRAME_DATA = auto()
    PROCESSED_DATA = auto()

@dataclass
class RawDataEvent:
    """
    外部事件传入，组装的暂时的数据结构，用于后续的打包处理。

    存储外部传入的原始数据事件，包括数据帧和视频帧，并通过DataType做区分。
    
    """
    datatype: DataType
    pro_data: Optional[DeviceProcessedDetectionDTO] = None
    video_data: Optional[VideoFrameDTO] = None
    
    def __post_init__(self):
        """验证至少有一个数据字段不为None"""
        if self.pro_data is None and self.video_data is None:
            raise ValueError(
                "RawDataEvent 的 pro_data 和 video_data 不能同时为 None，"
                "至少需要提供一个数据字段"
            )

@dataclass
class _PartialMatch:
    """
    内部缓存的半配对结构。
    """

    device_id: str
    frame_id: int
    first_arrival_ts: float
    video_frame: Optional[VideoFrameDTO] = None
    processed_detection: Optional[DeviceProcessedDetectionDTO] = None


class RenderPacketPackager:
    """渲染数据包打包器"""
    def __init__(self, *, queue_maxsize: int = 8, timeout_sec: float = 0.2, devices_list: list[str] = []):
        # 获取事件总线实例（用于后续扩展和消息通信，可选，不依赖事件总线也可运行）
        self.event_bus = get_event_bus()

        # 事件输入队列，存储RawDataEvent。设置最大长度防止内存泄漏
        self.event_queue: OverflowQueue[RawDataEvent] = OverflowQueue(maxsize=queue_maxsize)

        # 用于存储输出的渲染包队列。
        self.packet_queue: Dict[str, OverflowQueue[RenderPacket]] = self._init_inner_queue(devices_list,maxsize=queue_maxsize)

        # 内部缓存：用于临时存储未配对的视频帧和检测结果，key为(device_id, frame_id)
        self._buffer: Dict[Tuple[str, int], _PartialMatch] = {}

        # 内部缓存：用于临时存储旧帧
        self._latest_packets: Dict[str, RenderPacket] = self._init_latest_packets(devices_list)

        # 线程控制事件，指示打包线程的运行状态
        self._running = threading.Event()

        # 打包工作线程对象
        self._worker_thread: Optional[threading.Thread] = None

        # 配对等待的超时时长（秒），超时未配对的条目将被丢弃
        self.timeout_sec = timeout_sec

        # 统计数据：成功配对包数和丢弃包数
        self._stats = {
            "render_packets": 0,
            "drops": 0,
        }
        # 订阅事件
        self._subscribe_event()

        # 日志模块
        self.logger = logging.getLogger(__name__)

        self.logger.info("渲染包打包器已初始化，队列最大长度: %d, 超时时间: %.2f 秒", queue_maxsize, timeout_sec)

    




    #------私有接口------
    def _subscribe_event(self):
        """订阅数据源模块的视频帧，订阅数据处理模块发布的数据帧"""

        self.event_bus.subscribe(EventType.RAW_FRAME_DATA,self._handle_video_frame)
        self.event_bus.subscribe(EventType.PROCESSED_DATA,self._handle_processed_data)


    def _handle_processed_data(self,processed_data:DeviceProcessedDetectionDTO):
        """
        打包模块接收处理检测数据的回调函数
        """
        new_data = RawDataEvent(datatype=DataType.PROCESSED_DATA,pro_data=processed_data)
        self.event_queue.put_with_overflow(new_data)


    def _handle_video_frame(self,frame_data:VideoFrameDTO):
        """
        打包模块接收处理视频帧的回调函数
        """
        new_data = RawDataEvent(datatype=DataType.RAW_FRAME_DATA,video_data=frame_data)
        self.event_queue.put_with_overflow(new_data)


    def _init_latest_packets(self, devices_list: list[str]) -> Dict[str, Optional[RenderPacket]]: 
        """
        初始化内部缓冲字典的方法

        根据传入的列表创建缓冲字典，key为device_id(str)，值为RenderPacket类型。

        用于输出渲染包时的帧匹配。
        
        Args:
            devices_list: 设备ID列表
        
        Returns:
            Dict[str, Optional[RenderPacket]]: 设备ID到渲染包的映射字典，初始值均为None
        """
        # 使用字典推导式创建，初始值为None（Optional[RenderPacket]）
        return {device_id: None for device_id in devices_list}


    def _init_inner_queue(self,devices_list: list[str],maxsize: int = 8):
        """
        初始化内部队列的方法
        
        初始化内部队列，用于存放设备渲染包。
        """
        return {device_id: OverflowQueue[RenderPacket](maxsize=maxsize) for device_id in devices_list}



    


    def _clean_buffer(self):
        """清理缓冲区的过期数据"""
        now = time.time()
        for key, value in list(self._buffer.items()):
            if now - value.first_arrival_ts > self.timeout_sec:
                self._buffer.pop(key, None)
                self._stats["drops"] += 1


    def _process_event(self):
        """处理事件队列中的事件"""
        while self._running.is_set():
            try:
                event = self.event_queue.get(timeout=self.timeout_sec)
            except Empty:
                self._clean_buffer()
                continue
            
            try:
                self._handle_single_event(event)
            except Exception as e:
                self.logger.error("处理事件时发生错误: %s", e, exc_info=True)
            
            self._clean_buffer()

    def _handle_single_event(self, event: RawDataEvent):
        """处理单个事件（提取配对逻辑）"""
        # 统一提取关键信息
        if event.datatype == DataType.RAW_FRAME_DATA:
            device_id = event.video_data.device_id
            frame_id = event.video_data.frame_id
            new_video = event.video_data
            new_detection = None
        else:  # PROCESSED_DATA
            device_id = event.pro_data.device_id
            frame_id = event.pro_data.frame_id
            new_video = None
            new_detection = event.pro_data
        
        key = (device_id, frame_id)
        partial_match = self._buffer.get(key)
        
        # 情况1：首次到达，创建半配对
        if partial_match is None:
            self._buffer[key] = _PartialMatch(
                device_id=device_id,
                frame_id=frame_id,
                first_arrival_ts=time.time(),
                video_frame=new_video,
                processed_detection=new_detection
            )
            return
        
        # 情况2：配对成功，生成渲染包
        if self._can_create_packet(partial_match, new_video, new_detection):
            packet = self._create_render_packet(partial_match, new_video, new_detection)
            self.packet_queue[device_id].put_with_overflow(packet)
            self._buffer.pop(key)
            self._stats["render_packets"] += 1
            return
        
        # 情况3：重复数据错误
        data_type_name = "视频帧" if new_video else "检测数据"
        raise ValueError(f"检测到重复的{data_type_name}：device_id={device_id}, frame_id={frame_id}")

    def _can_create_packet(
        self, 
        partial: _PartialMatch, 
        new_video: Optional[VideoFrameDTO],
        new_detection: Optional[DeviceProcessedDetectionDTO]
    ) -> bool:
        """判断是否可以创建渲染包"""

        has_video = bool(partial.video_frame or new_video)
        has_detection = bool(partial.processed_detection or new_detection)
        return has_video and has_detection

    def _create_render_packet(
        self,
        partial: _PartialMatch,
        new_video: Optional[VideoFrameDTO],
        new_detection: Optional[DeviceProcessedDetectionDTO]
    ) -> RenderPacket:
        """创建渲染包"""
        video_frame = new_video if new_video else partial.video_frame
        detection = new_detection if new_detection else partial.processed_detection
        
        return RenderPacket(
            video_frame=video_frame,
            processed_detections=detection
        )



    def start(self):
        """启动打包线程"""
        self._running.set()
        self._worker_thread = threading.Thread(target=self._process_event, name="RenderPacketPackagerWorker")
        self._worker_thread.start()
        self.logger.info("渲染包打包工作线程已启动")

    def stop(self):
        """停止打包线程"""
        self._running.clear()
        if self._worker_thread is not None:
            self._worker_thread.join()
        self._worker_thread = None
        
        # 计算配对成功率
        total = self._stats["render_packets"] + self._stats["drops"]
        success_rate = (self._stats["render_packets"] / total * 100) if total > 0 else 0
        
        self.logger.info("渲染包打包工作线程已停止，统计数据: 渲染包=%d, 丢弃=%d, 成功率=%.1f%%", 
                        self._stats["render_packets"], self._stats["drops"], success_rate)




    # 外部数据获取接口------------------------------------------------------------------------------------------------
    def get_packet_by_mxid(self,mx_id:str,timeout:float = 0.01) -> Optional[RenderPacket]:
        """获取渲染包的外部接口，如果队列为空，则返回None"""
        if mx_id not in self.packet_queue:
            self.logger.warning(f"设备ID {mx_id} 不存在于队列中")
            return None
        try:
            return self.packet_queue[mx_id].get(timeout=timeout)
        except Empty:
            return None


    def get_packets(self, timeout: float = 0.01) -> Dict[str, RenderPacket]:
        """
        获取所有设备的渲染包。
        
        策略：
        - 尝试获取新帧（timeout）
        - 如果队列为空，使用缓冲帧
        - 获取到新帧时，更新缓冲区
        
        Returns:
            {device_id: RenderPacket} 字典
        """
        packets = {}
        
        for device_id, queue in self.packet_queue.items():
            try:
                # 尝试获取新帧
                packet = queue.get(timeout=timeout)
                
                # 更新缓冲区
                self._latest_packets[device_id] = packet
                
                # 加入结果
                packets[device_id] = packet
                
            except Empty:
                # 使用缓冲帧（如果存在）
                if device_id in self._latest_packets:
                    packets[device_id] = self._latest_packets[device_id]
        
        return packets
