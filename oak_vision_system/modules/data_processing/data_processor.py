"""DataProcessor 模块

DataProcessor 是数据处理流水线的顶层协调组件，负责协调坐标变换和滤波处理流程，
并完成数据格式的转换和组装。

设计特点：
1. 清晰的职责划分：专注于协调和数据转换，不涉及具体算法实现
2. 高性能：使用 NumPy 向量化操作，满足实时处理要求（20-30 FPS）
3. 线程管理：内置队列缓冲和线程管理功能
4. 事件驱动：自动订阅上游数据事件，异步处理
5. 可扩展性：通过依赖注入支持不同的坐标变换和滤波实现
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple
from queue import Empty

import numpy as np

from oak_vision_system.core.dto.config_dto import DataProcessingConfigDTO
from oak_vision_system.core.dto.config_dto.device_binding_dto import (
    DeviceMetadataDTO,
    DeviceRoleBindingDTO,
)
from oak_vision_system.core.dto.config_dto.enums import DeviceRole
from oak_vision_system.core.dto.detection_dto import DeviceDetectionDataDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO, DetectionStatusLabel
from oak_vision_system.core.event_bus import get_event_bus, EventBus
from oak_vision_system.core.event_bus.event_types import EventType
from oak_vision_system.modules.data_processing.transform_module import CoordinateTransfomer
from oak_vision_system.modules.data_processing.filter_manager import FilterManager
from oak_vision_system.modules.data_processing.decision_layer import DecisionLayer
from oak_vision_system.utils.data_structures.Queue import OverflowQueue


logger = logging.getLogger(__name__)


class DataProcessor:
    """数据处理器
    
    集成了数据处理逻辑和线程管理功能。
    
    架构特点：
    - 内置队列缓冲：使用 OverflowQueue 缓冲上游数据
    - 事件订阅：自动订阅 RAW_DETECTION_DATA 事件
    - 线程管理：内置 start/stop 方法管理工作线程
    - 数据处理：协调坐标变换和滤波流程
    
    使用示例：
        >>> config = DataProcessingConfigDTO(...)
        >>> device_metadata = {...}
        >>> bindings = {...}
        >>> 
        >>> processor = DataProcessor(
        ...     config=config,
        ...     device_metadata=device_metadata,
        ...     bindings=bindings,
        ... )
        >>> 
        >>> # 启动异步处理
        >>> processor.start()
        >>> 
        >>> # 停止处理
        >>> processor.stop()
    """
    
    def __init__(
        self,
        *,
        config: DataProcessingConfigDTO,
        device_metadata: Dict[str, DeviceMetadataDTO],
        bindings: Dict[DeviceRole, DeviceRoleBindingDTO],
        label_map: Optional[List[str]] = None,
        queue_size: int = 10,
        queue_pressure_threshold: float = 0.8,
    ) -> None:
        """初始化 DataProcessor
        
        Args:
            config: 数据处理配置对象
            device_metadata: 设备元数据字典，映射 MXid 到 DeviceMetadataDTO
            bindings: 设备角色绑定字典，映射 DeviceRole 到 DeviceRoleBindingDTO
            label_map: 标签映射列表，定义所有检测类别（可选，默认为空列表）
            queue_size: 内部队列大小，建议 5-20
            queue_pressure_threshold: 队列压力阈值，超过此值会记录警告
        
        Raises:
            ValueError: 当配置参数无效时
        """
        # 验证配置参数
        if config is None:
            raise ValueError("config 不能为 None")
        
        if not device_metadata or len(device_metadata) == 0:
            raise ValueError("device_metadata 不能为 None 或空字典")
        
        if bindings is None:
            raise ValueError("bindings 不能为 None")
        
        # 存储配置参数
        self._config = config
        self._device_metadata = device_metadata
        self._bindings = bindings
        self._label_map = label_map if label_map is not None else []
        self._queue_size = queue_size
        self._pressure_threshold = queue_pressure_threshold
        
        # 从配置中提取坐标变换配置
        coordinate_transforms = config.coordinate_transforms
        
        # 初始化 CoordinateTransformer
        self._transformer = CoordinateTransfomer(
            calibrations=coordinate_transforms,
            bindings=bindings,
        )
        
        # 初始化 FilterManager 实例
        self._filter_manager = FilterManager(
            device_metadata=device_metadata,
            label_map=self._label_map,
        )
        
        # 初始化队列缓冲
        self._queue = OverflowQueue[DeviceDetectionDataDTO](maxsize=queue_size)
        
        # 线程控制
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running_lock = threading.RLock()
        self._is_running = False
        
        # 事件总线（必须在 DecisionLayer 初始化之前）
        self._event_bus: EventBus = get_event_bus()
        self._subscription_id: Optional[str] = None
        
        # 初始化 DecisionLayer 单例
        decision_config = config.decision_layer_config
        self.decision_layer = DecisionLayer(
            event_bus=self._event_bus,
            config=decision_config
        )
        
        # 统计信息（保留用于 get_stats 方法）
        self._last_drop_count = 0  # 用于跟踪队列溢出情况
        
        # 自动订阅事件（在初始化时完成）
        self._subscribe_events()
        
        # 注册到背压监控器
        self._register_to_backpressure_monitor()
        
        logger.info(
            "DataProcessor 初始化完成: devices=%d, labels=%d, queue_size=%d, decision_layer_initialized=%s",
            len(device_metadata),
            len(self._label_map),
            queue_size,
            self.decision_layer is not None,
        )
    
    # ========== 事件订阅管理 ==========
    
    def _subscribe_events(self) -> bool:
        """订阅事件（内部方法，在初始化时调用）
        
        Returns:
            bool: 是否成功订阅
        """
        if self._subscription_id:
            logger.debug("事件已订阅，跳过重复订阅")
            return False  # 已订阅
        
        try:
            self._subscription_id = self._event_bus.subscribe(
                EventType.RAW_DETECTION_DATA,
                self._on_detection_data_received
            )
            logger.info("已订阅 RAW_DETECTION_DATA 事件")
            return True
        except Exception as e:
            logger.error(f"订阅事件失败: {e}")
            return False
    
    def _unsubscribe_events(self) -> bool:
        """取消订阅事件（内部方法）
        
        Returns:
            bool: 是否成功取消订阅
        """
        if not self._subscription_id:
            return True  # 未订阅，无需取消
        
        try:
            self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None
            logger.info("已取消订阅 RAW_DETECTION_DATA 事件")
            return True
        except Exception as e:
            logger.error(f"取消订阅事件失败: {e}")
            return False
    
    def _register_to_backpressure_monitor(self) -> None:
        """将队列注册到背压监控器"""
        try:
            from oak_vision_system.core.backpressure import get_backpressure_monitor, OverflowQueueMetricsProvider
            
            # 获取全局背压监控器
            self._backpressure_monitor = get_backpressure_monitor()
            
            # 生成唯一的 queue_id（使用对象ID确保唯一性）
            unique_queue_id = f"data_processor_queue_{id(self)}"
            
            # 创建队列指标提供者
            self._bp_provider = OverflowQueueMetricsProvider(
                self._queue, 
                queue_id=unique_queue_id
            )
            
            # 注册队列
            self._backpressure_monitor.register_queue(
                queue_id=unique_queue_id,
                metrics_provider=self._bp_provider.get_metrics,
                capacity=self._queue.maxsize,
            )
            
            # 启动监控器（如果还没启动的话）
            self._backpressure_monitor.start()
            
            logger.debug(f"已注册队列到背压监控器: {unique_queue_id}")
        except Exception as e:
            logger.warning(f"注册背压监控失败: {e}")
    
    # ========== 线程管理接口 ==========
    
    def start(self) -> bool:
        """启动数据处理线程
        
        Returns:
            bool: 是否成功启动
        """
        with self._running_lock:
            if self._is_running:
                logger.warning("DataProcessor 已在运行中")
                return False
            
            self._stop_event.clear()
            self._is_running = True
            
            # 启动工作线程（事件订阅已在初始化时完成）
            self._thread = threading.Thread(
                target=self._run_main_loop,
                name="DataProcessor",
                daemon=False
            )
            self._thread.start()
            
            logger.info("DataProcessor 线程已启动")
            return True
    
    def stop(self, timeout: float = 5.0) -> bool:
        """停止数据处理线程
        
        Args:
            timeout: 等待线程停止的超时时间（秒）
            
        Returns:
            bool: 是否成功停止
        """
        with self._running_lock:
            if not self._is_running:
                logger.info("DataProcessor 未在运行")
                return True
            
            logger.info("正在停止 DataProcessor...")
            
            # 1. 设置停止信号
            self._stop_event.set()
            
            # 2. 等待线程结束
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=timeout)
                
                if self._thread.is_alive():
                    logger.error(f"线程停止超时 ({timeout}s)")
                    return False
            
            # 3. 清理状态
            self._is_running = False
            self._thread = None
            
            # 4. 输出统计信息
            drop_count = self._queue.get_drop_count()
            logger.info(
                "DataProcessor 已停止: dropped=%d",
                drop_count
            )
            return True
    
    def shutdown(self) -> bool:
        """完全关闭 DataProcessor（停止线程并取消事件订阅）
        
        与 stop() 的区别：
        - stop(): 只停止处理线程，保持事件订阅
        - shutdown(): 停止线程并取消事件订阅，完全关闭
        
        Returns:
            bool: 是否成功关闭
        """
        # 先停止线程
        success = self.stop()
        
        # 再取消事件订阅
        if success:
            self._unsubscribe_events()
            logger.info("DataProcessor 已完全关闭")
        
        return success
    
    # ========== 事件订阅回调 ==========
    
    def _on_detection_data_received(self, data: DeviceDetectionDataDTO) -> None:
        """处理接收到的检测数据事件（回调函数）
        
        轻量级回调，只负责数据入队。
        所有控制逻辑在消费端处理。
        
        Args:
            data: 接收到的检测数据
        """
        # 只做入队操作，其他逻辑移到消费端
        self._queue.put_with_overflow(data)
    
    # ========== 主循环方法 ==========
    
    def _run_main_loop(self) -> None:
        """主循环方法（在独立线程中运行）
        
        职责：
        1. 循环从队列中获取数据
        2. 调用 process() 方法处理数据
        3. 处理异常和停止信号
        4. 定期监控队列压力
        """
        logger.info("DataProcessor 主循环开始")
        
        try:
            while not self._stop_event.is_set():
                try:
                    # 阻塞获取队列数据（超时1秒）
                    data = self._queue.get(block=True, timeout=1.0)
                    
                    # 处理数据
                    try:
                        self.process(data)
                    except Exception as e:
                        logger.error(
                            f"数据处理失败: device_id={data.device_id}, frame_id={data.frame_id}, error={e}",
                            exc_info=True
                        )
                    
                    # 标记任务完成
                    self._queue.task_done()
                    
                except Empty:
                    # 超时，继续循环
                    continue
                except Exception as e:
                    logger.error(f"处理数据异常: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"主循环异常: {e}", exc_info=True)
        finally:
            logger.info("DataProcessor 主循环结束")
    
    # ========== 数据处理方法（原有逻辑保持不变） ==========
    
    def process(
        self,
        detection_data: DeviceDetectionDataDTO,
    ) -> Optional[DeviceProcessedDataDTO]:
        """处理一帧检测数据（原有方法，保持不变）
        
        现在这个方法主要在内部线程中被调用，
        也可以作为同步处理接口供外部直接调用。
        
        工作流：
        1. 提取数据并转换为 NumPy 格式
        2. 坐标变换
        3. 滤波处理
        4. 重新组装为输出 DTO
        5. 发布事件
        
        Args:
            detection_data: 设备检测数据
            
        Returns:
            Optional[DeviceProcessedDataDTO]: 处理后的数据，如果输入为空则返回 None
        """
        
        # 提取元数据
        device_id = detection_data.device_id
        frame_id = detection_data.frame_id
        device_alias = detection_data.device_alias
        detections = detection_data.detections
        
        # 处理空输入（创建空 DTO 并发布事件）
        if not detections or len(detections) == 0:
            processed_data = self._create_empty_output(
                device_id=device_id,
                frame_id=frame_id,
                device_alias=device_alias,
            )
            self._event_bus.publish(
                EventType.PROCESSED_DATA,
                processed_data,
                wait_all=False,
            )
            return processed_data
        
        # 1. 提取数据并转换为 NumPy 格式（包括齐次坐标）
        coords_homogeneous, bboxes, confidences, labels = self._extract_arrays(detections)
        
        # 2. 坐标变换
        try:
            transformed_coords = self._transformer.transform_coordinates(device_id, coords_homogeneous)
        except Exception as e:
            logger.error(f"坐标变换失败: device_id={device_id}, frame_id={frame_id}, error={e}")
            raise
        
        # 3. 滤波处理
        try:
            filtered_coords, filtered_bboxes, filtered_confidences, filtered_labels = \
                self._filter_manager.process(
                    device_id=device_id,
                    coordinates=transformed_coords,
                    bboxes=bboxes,
                    confidences=confidences,
                    labels=labels,
                )
        except Exception as e:
            logger.error(f"滤波处理失败: device_id={device_id}, frame_id={frame_id}, error={e}")
            raise
        
        # 4. 决策层处理
        state_labels = []
        try:
            state_labels = self.decision_layer.decide(
                device_id=device_id,
                filtered_coords=filtered_coords,
                filtered_labels=filtered_labels
            )
        except Exception as e:
            logger.error(
                f"决策层处理失败: device_id={device_id}, frame_id={frame_id}, error={e}",
                exc_info=True
            )
            # 决策层失败时，使用空状态标签列表，不中断整个流程
            state_labels = []
        
        # 5. 重新组装为输出 DTO
        processed_data = self._assemble_output(
            device_id=device_id,
            frame_id=frame_id,
            device_alias=device_alias,
            coords=filtered_coords,
            bboxes=filtered_bboxes,
            confidences=filtered_confidences,
            labels=filtered_labels,
            state_labels=state_labels,
        )
        
        # 6. 发布事件
        try:
            self._event_bus.publish(
                EventType.PROCESSED_DATA,
                processed_data,
                wait_all=False,
            )
        except Exception as e:
            logger.error(f"事件发布失败: {e}")
            # 不抛出异常，继续返回处理结果
        
        return processed_data
    
    def _extract_arrays(
        self,
        detections: List,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """从 DetectionDTO 列表提取 NumPy 数组（包括齐次坐标）
        
        使用预分配数组和向量化操作以提高性能。
        提取的坐标为齐次坐标格式 [x, y, z, 1]，用于后续的坐标变换。
        
        Args:
            detections: DetectionDTO 列表
        
        Returns:
            Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]: 
                (coords_homogeneous, bboxes, confidences, labels)
                - coords_homogeneous: 形状 (n, 4)，dtype=float32，齐次坐标数组 [x, y, z, 1]
                - bboxes: 形状 (n, 4)，dtype=float32，边界框数组
                - confidences: 形状 (n,)，dtype=float32，置信度数组
                - labels: 形状 (n,)，dtype=int32，标签数组
        """
        n = len(detections)
        
        # 处理空输入
        if n == 0:
            return (
                np.empty((0, 4), dtype=np.float32),  # 齐次坐标为 4 列
                np.empty((0, 4), dtype=np.float32),
                np.empty((0,), dtype=np.float32),
                np.empty((0,), dtype=np.int32),
            )
        
        # 预分配数组（性能优化：避免动态扩展）
        coords_homogeneous = np.zeros((n, 4), dtype=np.float32)
        bboxes = np.zeros((n, 4), dtype=np.float32)
        confidences = np.zeros((n,), dtype=np.float32)
        labels = np.zeros((n,), dtype=np.int32)
        
        # 向量化填充数组（性能优化：使用 NumPy 数组操作）
        for i, det in enumerate(detections):
            # 提取齐次坐标 [x, y, z, 1]
            coords_homogeneous[i] = [
                det.spatial_coordinates.x,
                det.spatial_coordinates.y,
                det.spatial_coordinates.z,
                1.0,  # 齐次坐标的第四维
            ]
            
            # 提取边界框
            bboxes[i] = [
                det.bbox.xmin,
                det.bbox.ymin,
                det.bbox.xmax,
                det.bbox.ymax,
            ]
            
            # 提取置信度和标签
            confidences[i] = det.confidence
            labels[i] = det.label
        
        return coords_homogeneous, bboxes, confidences, labels
    
    def _create_empty_output(
        self,
        device_id: str,
        frame_id: int,
        device_alias: Optional[str],
    ) -> DeviceProcessedDataDTO:
        """创建空输出
        
        Args:
            device_id: 设备ID
            frame_id: 帧ID
            device_alias: 设备别名
        
        Returns:
            DeviceProcessedDataDTO: 空的处理后数据
        """
        return DeviceProcessedDataDTO(
            device_id=device_id,
            frame_id=frame_id,
            labels=np.empty((0,), dtype=np.int32),
            bbox=np.empty((0, 4), dtype=np.float32),
            coords=np.empty((0, 3), dtype=np.float32),
            confidence=np.empty((0,), dtype=np.float32),
            state_label=[],
            device_alias=device_alias,
        )
    
    def _assemble_output(
        self,
        device_id: str,
        frame_id: int,
        device_alias: Optional[str],
        coords: np.ndarray,
        bboxes: np.ndarray,
        confidences: np.ndarray,
        labels: np.ndarray,
        state_labels: List[DetectionStatusLabel],
    ) -> DeviceProcessedDataDTO:
        """组装输出数据
        
        Args:
            device_id: 设备ID
            frame_id: 帧ID
            device_alias: 设备别名
            coords: 滤波后的坐标矩阵
            bboxes: 滤波后的边界框矩阵
            confidences: 滤波后的置信度数组
            labels: 滤波后的标签数组
            state_labels: 决策层输出的状态标签列表
        
        Returns:
            DeviceProcessedDataDTO: 处理后的数据
        """
        return DeviceProcessedDataDTO(
            device_id=device_id,
            frame_id=frame_id,
            device_alias=device_alias,
            coords=coords,
            bbox=bboxes,
            confidence=confidences,
            labels=labels,
            state_label=state_labels,
        )

    # ========== 状态查询接口 ==========
    
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        with self._running_lock:
            return self._is_running
    
    def get_stats(self) -> dict:
        """获取处理统计信息"""
        return {
            "is_running": self.is_running,
            "queue_stats": {
                "size": self._queue.qsize(),
                "maxsize": self._queue.maxsize,
                "usage_ratio": self._queue.get_usage_ratio(),
                "available_space": self._queue.get_available_space(),
                "drop_count": self._queue.get_drop_count(),
                "pressure_level": self._queue.get_pressure_level(),
            }
        }
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self._queue.reset_drop_count()
        logger.info("DataProcessor 统计信息已重置")
