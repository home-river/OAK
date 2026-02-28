"""
Collector 接收器

用于接收和分析 Collector 模块发布的数据。
使用双队列分别处理视频帧数据和检测数据。
"""

from typing import Optional
from datetime import datetime
from queue import Empty
import numpy as np
import threading

from oak_vision_system.tests.harness.base_harness import BaseTestHarness
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO, DeviceDetectionDataDTO
from oak_vision_system.core.event_bus import EventBus, EventType
from oak_vision_system.utils.data_structures.Queue import OverflowQueue
import logging


class CollectorReceiver(BaseTestHarness):
    """
    Collector 数据接收器（双队列）
    
    订阅 Collector 发布的两种事件：
    - RAW_FRAME_DATA: 视频帧数据（VideoFrameDTO）
    - RAW_DETECTION_DATA: 检测数据（DeviceDetectionDataDTO）
    
    使用两个独立队列分别缓冲和处理这两种数据。
    
    使用示例：
        event_bus = EventBus()
        receiver = CollectorReceiver(
            event_bus,
            log_dir="test_logs/collector",
            frame_queue_size=100,
            detection_queue_size=100
        )
        
        # 启动接收器（自动订阅事件）
        receiver.start()
        
        # ... 运行测试 ...
        
        # 停止并获取统计
        stats = receiver.stop()
        print(f"接收视频帧: {stats['frame_count']}")
        print(f"接收检测数据: {stats['detection_count']}")
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        log_dir: str = "test_logs/collector",
        log_prefix: str = "collector",
        frame_queue_size: int = 100,
        detection_queue_size: int = 100
    ):
        """
        初始化 Collector 接收器
        
        Args:
            event_bus: 事件总线实例
            log_dir: 日志保存目录，默认 "test_logs/collector"
            log_prefix: 日志文件名前缀，默认 "collector"
            frame_queue_size: 视频帧队列大小，默认 100
            detection_queue_size: 检测数据队列大小，默认 100
        """
        super().__init__(
            event_bus=event_bus,
            log_dir=log_dir,
            log_prefix=log_prefix
        )
        
        # 定义双队列
        self.frame_queue: OverflowQueue[VideoFrameDTO] = OverflowQueue(maxsize=frame_queue_size)
        self.detection_queue: OverflowQueue[DeviceDetectionDataDTO] = OverflowQueue(maxsize=detection_queue_size)
        
        # 统计信息
        self.frame_count: int = 0
        self.detection_count: int = 0
        self.frame_processed: int = 0
        self.detection_processed: int = 0
        self.frame_dropped: int = 0
        self.detection_dropped: int = 0
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(
            f"CollectorReceiver 初始化: "
            f"frame_queue={frame_queue_size}, detection_queue={detection_queue_size}"
        )
    
    # ========== 事件订阅相关 ==========
    
    def _setup_subscriptions(self) -> None:
        """
        设置事件订阅
        
        订阅 Collector 发布的两种事件。
        """
        self.subscribe(EventType.RAW_FRAME_DATA, self._on_frame_received)
        self.subscribe(EventType.RAW_DETECTION_DATA, self._on_detection_received)
    
    def _on_frame_received(self, frame_data: VideoFrameDTO) -> None:
        """
        视频帧接收回调
        
        将视频帧数据快速入队，不阻塞事件总线。
        
        Args:
            frame_data: 视频帧数据
        """
        self.frame_count += 1
        
        try:
            dropped = self.frame_queue.put_with_overflow(frame_data)
            
            if dropped:
                self.frame_dropped += 1
                if self.frame_dropped % 10 == 0:
                    self.logger.warning(
                        f"视频帧队列溢出 (总丢弃: {self.frame_dropped})"
                    )
        except Exception as e:
            self.logger.error(f"视频帧入队失败: {e}")
    
    def _on_detection_received(self, detection_data: DeviceDetectionDataDTO) -> None:
        """
        检测数据接收回调
        
        将检测数据快速入队，不阻塞事件总线。
        
        Args:
            detection_data: 检测数据
        """
        self.detection_count += 1
        
        try:
            dropped = self.detection_queue.put_with_overflow(detection_data)
            
            if dropped:
                self.detection_dropped += 1
                if self.detection_dropped % 10 == 0:
                    self.logger.warning(
                        f"检测数据队列溢出 (总丢弃: {self.detection_dropped})"
                    )
        except Exception as e:
            self.logger.error(f"检测数据入队失败: {e}")
    
    # ========== 数据处理相关 ==========
    
    def _worker_loop(self) -> None:
        """
        工作线程主循环
        
        从两个队列取数据，分析并保存日志。
        使用轮询方式处理两个队列，避免某个队列阻塞另一个。
        """
        self.logger.info("工作线程已启动")
        
        while self._running:
            # 处理视频帧队列
            try:
                frame_data = self.frame_queue.get(timeout=0.05)
                result = self._analyze_frame(frame_data)
                if result:
                    self.save_to_log(result)
                    self.frame_processed += 1
            except Empty:
                pass
            except Exception as e:
                self.logger.error(f"处理视频帧失败: {e}", exc_info=True)
            
            # 处理检测数据队列
            try:
                detection_data = self.detection_queue.get(timeout=0.05)
                result = self._analyze_detection(detection_data)
                if result:
                    self.save_to_log(result)
                    self.detection_processed += 1
            except Empty:
                pass
            except Exception as e:
                self.logger.error(f"处理检测数据失败: {e}", exc_info=True)
        
        self.logger.info("工作线程已退出")
    
    def _analyze_frame(self, frame_data: VideoFrameDTO) -> Optional[dict]:
        """
        分析视频帧数据
        
        Args:
            frame_data: 视频帧数据
            
        Returns:
            分析结果字典
        """
        try:
            analysis = {
                "type": "video_frame",
                "device_id": frame_data.device_id,
                "frame_id": frame_data.frame_id,
                "analysis_time": datetime.now().isoformat()
            }
            
            # 分析 RGB 帧
            if frame_data.rgb_frame is not None:
                analysis["rgb_frame"] = {
                    "shape": frame_data.rgb_frame.shape,
                    "dtype": str(frame_data.rgb_frame.dtype),
                    "size_bytes": frame_data.rgb_frame.nbytes,
                    "mean_value": float(frame_data.rgb_frame.mean()),
                    "std_value": float(frame_data.rgb_frame.std())
                }
            else:
                analysis["rgb_frame"] = None
            
            # 分析深度帧
            if frame_data.depth_frame is not None:
                analysis["depth_frame"] = {
                    "shape": frame_data.depth_frame.shape,
                    "dtype": str(frame_data.depth_frame.dtype),
                    "size_bytes": frame_data.depth_frame.nbytes,
                    "min_depth": float(frame_data.depth_frame.min()),
                    "max_depth": float(frame_data.depth_frame.max()),
                    "mean_depth": float(frame_data.depth_frame.mean())
                }
            else:
                analysis["depth_frame"] = None
            
            return analysis
        
        except Exception as e:
            self.logger.error(f"分析视频帧失败: {e}", exc_info=True)
            return None
    
    def _analyze_detection(self, detection_data: DeviceDetectionDataDTO) -> Optional[dict]:
        """
        分析检测数据（仅类别统计）
        
        Args:
            detection_data: 检测数据
            
        Returns:
            分析结果字典（仅包含类别统计）
        """
        try:
            analysis = {
                "type": "detection_data",
                "device_id": detection_data.device_id,
                "device_alias": detection_data.device_alias,
                "frame_id": detection_data.frame_id,
                "analysis_time": datetime.now().isoformat(),
                "detection_count": detection_data.detection_count
            }
            
            # 类别统计
            if detection_data.detections:
                labels = [det.label for det in detection_data.detections]
                analysis["label_counts"] = {label: labels.count(label) for label in set(labels)}
            else:
                analysis["label_counts"] = {}
            
            return analysis
        
        except Exception as e:
            self.logger.error(f"分析检测数据失败: {e}", exc_info=True)
            return None
    
    # ========== 生命周期管理 ==========
    
    def _start_workers(self) -> None:
        """
        启动工作线程
        
        创建一个工作线程处理两个队列。
        """
        worker = threading.Thread(
            target=self._worker_loop,
            name=f"{self.__class__.__name__}-Worker",
            daemon=True
        )
        worker.start()
        self._worker_threads.append(worker)
    
    def stop(self) -> dict:
        """
        停止接收器并返回统计信息
        
        Returns:
            统计信息字典
        """
        stats = super().stop()
        
        # 添加自定义统计信息
        stats.update({
            "frame_count": self.frame_count,
            "detection_count": self.detection_count,
            "frame_processed": self.frame_processed,
            "detection_processed": self.detection_processed,
            "frame_dropped": self.frame_dropped,
            "detection_dropped": self.detection_dropped,
            "frame_queue_size": self.frame_queue.qsize(),
            "detection_queue_size": self.detection_queue.qsize()
        })
        
        # 计算速率
        duration = stats.get("duration_seconds", 0)
        if duration > 0:
            stats["frame_rate"] = self.frame_count / duration
            stats["detection_rate"] = self.detection_count / duration
        
        self.logger.info(f"日志文件: {stats.get('log_file')}")
        
        return stats
    
    def get_stats(self) -> dict:
        """
        获取当前统计信息（不停止接收器）
        
        Returns:
            当前统计信息字典
        """
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            "frame_count": self.frame_count,
            "detection_count": self.detection_count,
            "frame_processed": self.frame_processed,
            "detection_processed": self.detection_processed,
            "frame_dropped": self.frame_dropped,
            "detection_dropped": self.detection_dropped,
            "frame_queue_size": self.frame_queue.qsize(),
            "detection_queue_size": self.detection_queue.qsize(),
            "duration_seconds": duration,
            "frame_rate": self.frame_count / duration if duration > 0 else 0,
            "detection_rate": self.detection_count / duration if duration > 0 else 0,
            "is_running": self._running
        }
