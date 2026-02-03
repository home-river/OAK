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

from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.transport_dto import TransportDTO
from queue import Queue, Empty
from oak_vision_system.core.event_bus import get_event_bus, EventType
from oak_vision_system.utils import OverflowQueue


@dataclass(frozen=True)
class RenderPacket(TransportDTO):
    """单设备渲染数据包"""
    video_frame: VideoFrameDTO  # 视频帧数据
    processed_detections: DeviceProcessedDataDTO  # 处理后的检测数据（必需字段）
    
    def _validate_data(self) -> List[str]:
        """渲染数据包验证"""
        errors = []
        
        # 验证视频帧数据
        errors.extend(self.video_frame._validate_data())
        
        # 验证处理后的检测数据
        errors.extend(self.processed_detections._validate_data())
        
        # 验证帧id和mxid是否一致
        if self.video_frame.device_id != self.processed_detections.device_id:
            errors.append(f"视频帧数据和处理后的检测数据设备ID不一致")
        if self.video_frame.frame_id != self.processed_detections.frame_id:
            errors.append(f"视频帧数据和处理后的检测数据帧ID不一致")
            
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
    pro_data: Optional[DeviceProcessedDataDTO] = None
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
    processed_detection: Optional[DeviceProcessedDataDTO] = None


class RenderPacketPackager:
    """渲染数据包打包器"""
    def __init__(self, *, queue_maxsize: int = 8, timeout_sec: float = 0.2, devices_list: list[str] = [], cache_max_age_sec: float = 1.0):
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
        
        # 缓存时间戳：记录每个设备缓存帧的时间
        self._packet_timestamps: Dict[str, float] = {device_id: 0.0 for device_id in devices_list}

        # 线程控制事件，指示打包线程的运行状态
        self._running = threading.Event()
        
        # 状态管理（用于幂等性检查和线程安全）
        self._is_running = False
        self._running_lock = threading.RLock()

        # 打包工作线程对象
        self._worker_thread: Optional[threading.Thread] = None

        # 配对等待的超时时长（秒），超时未配对的条目将被丢弃
        self.timeout_sec = timeout_sec
        
        # 缓存最大年龄（秒），超过此时间的缓存帧将被清理
        self.cache_max_age_sec = cache_max_age_sec

        # 统计数据：成功配对包数和丢弃包数（需求 13.4）
        self._stats = {
            "render_packets": 0,
            "drops": 0,
        }
        self._stats_lock = threading.Lock()  # 线程安全保护（需求 13.4）
        # 事件订阅ID（用于取消订阅）
        self._video_frame_sub_id = None
        self._processed_data_sub_id = None
        
        # 订阅事件
        self._subscribe_event()

        # 日志模块
        self.logger = logging.getLogger(__name__)

        self.logger.info("渲染包打包器已初始化，队列最大长度: %d, 超时时间: %.2f 秒, 缓存最大年龄: %.2f 秒", 
                        queue_maxsize, timeout_sec, cache_max_age_sec)

    




    #------私有接口------
    def _subscribe_event(self):
        """订阅数据源模块的视频帧，订阅数据处理模块发布的数据帧"""

        self._video_frame_sub_id = self.event_bus.subscribe(EventType.RAW_FRAME_DATA, self._handle_video_frame)
        self._processed_data_sub_id = self.event_bus.subscribe(EventType.PROCESSED_DATA, self._handle_processed_data)


    def _handle_processed_data(self,processed_data:DeviceProcessedDataDTO):
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
        drops_count = 0
        for key, value in list(self._buffer.items()):
            if now - value.first_arrival_ts > self.timeout_sec:
                self._buffer.pop(key, None)
                drops_count += 1
        
        # 线程安全地更新统计数据（需求 13.4）
        if drops_count > 0:
            with self._stats_lock:
                self._stats["drops"] += drops_count


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
            # 线程安全地更新统计数据（需求 13.4）
            with self._stats_lock:
                self._stats["render_packets"] += 1
            return
        
        # 情况3：重复数据错误
        data_type_name = "视频帧" if new_video else "检测数据"
        raise ValueError(f"检测到重复的{data_type_name}：device_id={device_id}, frame_id={frame_id}")

    def _can_create_packet(
        self, 
        partial: _PartialMatch, 
        new_video: Optional[VideoFrameDTO],
        new_detection: Optional[DeviceProcessedDataDTO]
    ) -> bool:
        """判断是否可以创建渲染包"""

        has_video = bool(partial.video_frame or new_video)
        has_detection = bool(partial.processed_detection or new_detection)
        return has_video and has_detection

    def _create_render_packet(
        self,
        partial: _PartialMatch,
        new_video: Optional[VideoFrameDTO],
        new_detection: Optional[DeviceProcessedDataDTO]
    ) -> RenderPacket:
        """创建渲染包"""
        video_frame = new_video if new_video else partial.video_frame
        detection = new_detection if new_detection else partial.processed_detection
        
        return RenderPacket(
            video_frame=video_frame,
            processed_detections=detection
        )



    def start(self) -> bool:
        """启动打包线程
        
        Returns:
            bool: 启动成功返回True，已在运行返回False
        """
        with self._running_lock:
            # 幂等性检查
            if self._is_running:
                self.logger.info("RenderPacketPackager 已在运行")
                return False
            
            self._running.set()
            self._is_running = True
            
            self._worker_thread = threading.Thread(
                target=self._process_event, 
                name="RenderPacketPackagerWorker",
                daemon=False
            )
            self._worker_thread.start()
            
            self.logger.info("渲染包打包工作线程已启动")
            return True

    def stop(self, timeout: float = 5.0) -> bool:
        """停止打包线程
        
        Args:
            timeout: 等待线程结束的超时时间（秒）
            
        Returns:
            bool: 停止成功返回True，超时返回False
            
        实现要点：
        - 幂等性检查：如果已停止则直接返回True
        - 线程安全：使用锁保护状态
        - 使用 thread.join(timeout) 等待线程结束
        - 如果超时，记录警告日志并返回False
        - 取消事件订阅
        - 清理队列和缓存
        """
        with self._running_lock:
            # 1. 幂等性检查
            if not self._is_running:
                self.logger.info("RenderPacketPackager 未在运行")
                return True
            
            self.logger.info("正在停止 RenderPacketPackager...")
            
            # 2. 设置停止信号
            self._running.clear()
            
            # 3. 等待工作线程结束
            if self._worker_thread is not None:
                self._worker_thread.join(timeout=timeout)
                
                # 检查是否超时
                if self._worker_thread.is_alive():
                    self.logger.warning(
                        "RenderPacketPackager 停止超时 (%.1f秒)，线程仍在运行",
                        timeout
                    )
                    # 超时时不清理状态，保持一致性
                    return False
                
                self._worker_thread = None
            
            # 4. 取消事件订阅
            try:
                if self._video_frame_sub_id:
                    self.event_bus.unsubscribe(self._video_frame_sub_id)
                    self._video_frame_sub_id = None
                if self._processed_data_sub_id:
                    self.event_bus.unsubscribe(self._processed_data_sub_id)
                    self._processed_data_sub_id = None
                self.logger.debug("已取消事件订阅")
            except Exception as e:
                self.logger.error("取消事件订阅时发生错误: %s", e, exc_info=True)
            
            # 5. 清理队列和缓存
            try:
                # 清理输入队列
                while not self.event_queue.empty():
                    try:
                        self.event_queue.get_nowait()
                    except:
                        break
                
                # 清理输出队列
                for device_id, queue in self.packet_queue.items():
                    while not queue.empty():
                        try:
                            queue.get_nowait()
                        except:
                            break
                
                # 清理缓冲区
                self._buffer.clear()
                
                # 清理缓存
                for device_id in self._latest_packets.keys():
                    self._latest_packets[device_id] = None
                    self._packet_timestamps[device_id] = 0.0
                
                self.logger.debug("已清理所有队列和缓存")
            except Exception as e:
                self.logger.error("清理队列和缓存时发生错误: %s", e, exc_info=True)
            
            # 6. 清理状态（只在成功时执行）
            self._is_running = False
            
            # 7. 输出关闭统计信息
            with self._stats_lock:
                render_packets = self._stats["render_packets"]
                drops = self._stats["drops"]
            
            # 计算配对成功率
            total = render_packets + drops
            success_rate = (render_packets / total * 100) if total > 0 else 0
            
            self.logger.info(
                "RenderPacketPackager 已停止 - 渲染包: %d, 丢弃: %d, 成功率: %.1f%%", 
                render_packets, drops, success_rate
            )
            
            return True




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
        - 如果队列为空，使用缓冲帧（仅当未过期时）
        - 获取到新帧时，更新缓冲区和时间戳
        - 过期的缓存帧会被自动清理
        
        Returns:
            {device_id: RenderPacket} 字典，只包含有效的（新鲜或未过期的）帧
        """
        packets = {}
        now = time.time()
        
        for device_id, queue in self.packet_queue.items():
            try:
                # 尝试获取新帧
                packet = queue.get(timeout=timeout)
                
                # 更新缓冲区和时间戳
                self._latest_packets[device_id] = packet
                self._packet_timestamps[device_id] = now
                
                # 加入结果
                packets[device_id] = packet
                
            except Empty:
                # 尝试使用缓冲帧
                cached_packet = self._latest_packets.get(device_id)
                
                if cached_packet is not None:
                    # 检查是否过期
                    cached_at = self._packet_timestamps.get(device_id, 0.0)
                    age = now - cached_at
                    
                    if age <= self.cache_max_age_sec:
                        # 未过期，可以使用
                        packets[device_id] = cached_packet
                    else:
                        # 已过期，清理缓存
                        self.logger.debug(
                            f"设备 {device_id} 的缓存帧已过期 (年龄: {age:.2f}s)，已清理"
                        )
                        self._latest_packets[device_id] = None
                        self._packet_timestamps[device_id] = 0.0
        
        return packets
    
    def get_cache_stats(self) -> dict:
        """
        获取缓存统计信息（调试接口）
        
        Returns:
            dict: 缓存统计信息，包含：
                - total_cached: 总缓存数量
                - expired: 过期缓存数量
                - valid: 有效缓存数量
                - devices: 每个设备的详细信息
        """
        now = time.time()
        stats = {
            "total_cached": 0,
            "expired": 0,
            "valid": 0,
            "devices": {}
        }
        
        for device_id, packet in self._latest_packets.items():
            if packet is not None:
                stats["total_cached"] += 1
                cached_at = self._packet_timestamps.get(device_id, 0.0)
                age = now - cached_at
                is_expired = age > self.cache_max_age_sec
                
                if is_expired:
                    stats["expired"] += 1
                else:
                    stats["valid"] += 1
                
                stats["devices"][device_id] = {
                    "age": age,
                    "expired": is_expired,
                    "frame_id": packet.video_frame.frame_id
                }
        
        return stats
