"""
测试工具基类

提供事件订阅、生命周期管理、日志记录的通用功能框架。
子类负责定义队列结构、实现回调接口和数据处理逻辑。

架构：
    事件总线 → 回调函数（子类实现） → 队列（子类定义） → 工作线程（子类实现）

使用方式：
    1. 继承 BaseTestHarness
    2. 定义队列结构（单队列或多队列）
    3. 实现事件回调接口（处理接收到的事件）
    4. 实现工作线程逻辑（从队列取数据并分析）
    5. 调用 subscribe() 订阅事件
    6. 调用 start() 启动，stop() 停止
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from oak_vision_system.core.event_bus import EventBus, EventType
import logging
import json
import threading
from datetime import datetime
from pathlib import Path


class BaseTestHarness(ABC):
    """
    测试工具基类（框架模式）
    
    提供事件订阅、生命周期管理、日志记录的通用功能。
    子类负责定义队列结构和实现具体的数据处理逻辑。
    
    使用示例：
        class CollectorReceiver(BaseTestHarness):
            def __init__(self, event_bus, ...):
                super().__init__(event_bus, ...)
                # 定义双队列
                self.frame_queue = OverflowQueue[VideoFrameDTO](maxsize=100)
                self.detection_queue = OverflowQueue[DeviceDetectionDataDTO](maxsize=100)
            
            def _setup_subscriptions(self):
                # 订阅两个事件
                self.subscribe(EventType.RAW_FRAME_DATA, self._on_frame_received)
                self.subscribe(EventType.RAW_DETECTION_DATA, self._on_detection_received)
            
            def _on_frame_received(self, data: VideoFrameDTO):
                # 视频帧入队
                self.frame_queue.put_with_overflow(data)
            
            def _on_detection_received(self, data: DeviceDetectionDataDTO):
                # 检测数据入队
                self.detection_queue.put_with_overflow(data)
            
            def _worker_loop(self):
                # 从两个队列取数据并处理
                ...
    
    Attributes:
        event_bus: 事件总线实例
        logger: 日志记录器
        log_dir: 日志文件保存目录
        log_prefix: 日志文件名前缀
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        log_dir: str = "test_logs",
        log_prefix: str = "test"
    ):
        """
        初始化测试工具基类
        
        Args:
            event_bus: 事件总线实例
            log_dir: 日志文件保存目录，默认 "test_logs"
            log_prefix: 日志文件名前缀，默认 "test"
        """
        self.event_bus = event_bus
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 日志配置
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_prefix = log_prefix
        
        # 日志文件句柄（子类可以选择使用）
        self._log_file = None
        self._log_file_path = None
        
        # 工作线程（子类可以定义多个工作线程）
        self._worker_threads: List[threading.Thread] = []
        self._running: bool = False
        
        # 统计信息（子类可以扩展）
        self.start_time: Optional[datetime] = None
        
        # 订阅列表（用于清理）
        self._subscriptions: List[Tuple[EventType, str]] = []
        
        self.logger.info(
            f"{self.__class__.__name__} 初始化完成: log_dir={log_dir}"
        )
    
    # ========== 事件订阅相关 ==========
    
    def subscribe(self, event_type: EventType, callback) -> None:
        """
        订阅指定事件类型
        
        Args:
            event_type: 要订阅的事件类型
            callback: 事件回调函数，由子类提供
        """
        subscription_id = self.event_bus.subscribe(event_type, callback)
        self._subscriptions.append((event_type, subscription_id))
        self.logger.info(f"已订阅事件: {event_type}")
    
    @abstractmethod
    def _setup_subscriptions(self) -> None:
        """
        设置事件订阅（抽象方法，子类必须实现）
        
        子类在此方法中调用 subscribe() 订阅需要的事件。
        
        Example:
            def _setup_subscriptions(self):
                self.subscribe(EventType.RAW_FRAME_DATA, self._on_frame_received)
                self.subscribe(EventType.RAW_DETECTION_DATA, self._on_detection_received)
        """
        pass
    
    # ========== 数据处理相关 ==========
    
    @abstractmethod
    def _worker_loop(self) -> None:
        """
        工作线程主循环（抽象方法，子类必须实现）
        
        子类在此方法中实现从队列取数据、分析并保存的逻辑。
        此方法在独立线程中运行。
        
        Example:
            def _worker_loop(self):
                while self._running:
                    try:
                        data = self.data_queue.get(timeout=0.1)
                        result = self.analyze_data(data)
                        self.save_to_log(result)
                    except Empty:
                        continue
        """
        pass
    
    # ========== 日志记录相关 ==========
    
    def _open_log_file(self) -> None:
        """
        打开日志文件（供子类使用）
        
        创建一个带时间戳的日志文件，用于追加写入。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_file_path = self.log_dir / f"{self.log_prefix}_{timestamp}.jsonl"
        
        try:
            self._log_file = open(self._log_file_path, 'w', encoding='utf-8')
            self.logger.info(f"日志文件已创建: {self._log_file_path}")
        except Exception as e:
            self.logger.error(f"创建日志文件失败: {e}")
            self._log_file = None
    
    def _close_log_file(self) -> None:
        """
        关闭日志文件（供子类使用）
        """
        if self._log_file:
            try:
                self._log_file.close()
                self.logger.info(f"日志文件已关闭: {self._log_file_path}")
            except Exception as e:
                self.logger.error(f"关闭日志文件失败: {e}")
            finally:
                self._log_file = None
    
    def save_to_log(self, data: dict) -> None:
        """
        将数据保存到日志文件（追加模式，JSONL 格式）
        
        每条记录占一行，方便后续处理。
        
        Args:
            data: 要保存的数据字典
        """
        if not self._log_file:
            self.logger.warning("日志文件未打开，跳过保存")
            return
        
        try:
            # 写入 JSON 行（JSONL 格式）
            json_line = json.dumps(data, ensure_ascii=False, default=str)
            self._log_file.write(json_line + '\n')
            self._log_file.flush()  # 立即刷新到磁盘
            
            self.logger.debug(f"已保存日志记录")
        
        except Exception as e:
            self.logger.error(f"保存日志失败: {e}")
    
    # ========== 模拟数据发布相关 ==========
    
    def publish_mock_event(self, event_type: EventType, mock_data) -> None:
        """
        发布模拟事件
        
        Args:
            event_type: 事件类型
            mock_data: 模拟数据对象
        """
        try:
            self.event_bus.publish(event_type, mock_data)
            self.logger.info(f"已发布模拟事件: {event_type}")
        except Exception as e:
            self.logger.error(f"发布模拟事件失败: {e}", exc_info=True)
    
    # ========== 生命周期管理 ==========
    
    def start(self) -> None:
        """
        启动测试工具
        
        设置订阅并启动工作线程。
        """
        if self._running:
            self.logger.warning("测试工具已在运行")
            return
        
        self.start_time = datetime.now()
        self._running = True
        
        # 打开日志文件
        self._open_log_file()
        
        # 设置事件订阅
        self._setup_subscriptions()
        
        # 启动工作线程（子类可能启动多个线程）
        self._start_workers()
        
        self.logger.info(f"{self.__class__.__name__} 已启动")
    
    @abstractmethod
    def _start_workers(self) -> None:
        """
        启动工作线程（抽象方法，子类必须实现）
        
        子类在此方法中创建并启动工作线程。
        
        Example:
            def _start_workers(self):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"{self.__class__.__name__}-Worker",
                    daemon=True
                )
                worker.start()
                self._worker_threads.append(worker)
        """
        pass
    
    def stop(self) -> dict:
        """
        停止测试工具并返回统计信息
        
        停止工作线程，取消事件订阅，返回运行统计。
        子类可以重写此方法以返回自定义统计信息。
        
        Returns:
            统计信息字典
        """
        if not self._running:
            self.logger.warning("测试工具未在运行")
            return {}
        
        # 停止工作线程
        self._running = False
        for worker in self._worker_threads:
            if worker.is_alive():
                worker.join(timeout=5.0)
                if worker.is_alive():
                    self.logger.error(f"工作线程 {worker.name} 停止超时")
        
        self._worker_threads.clear()
        
        # 关闭日志文件
        self._close_log_file()
        
        # 取消所有订阅
        for event_type, subscription_id in self._subscriptions:
            # TODO: 事件总线需要支持取消订阅
            # self.event_bus.unsubscribe(event_type, subscription_id)
            pass
        
        self._subscriptions.clear()
        
        # 计算基本统计信息
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        stats = {
            "duration_seconds": duration,
            "log_file": str(self._log_file_path) if self._log_file_path else None
        }
        
        self.logger.info(f"{self.__class__.__name__} 已停止，统计: {stats}")
        return stats
