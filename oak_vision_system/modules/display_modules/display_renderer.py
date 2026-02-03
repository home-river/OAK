"""显示渲染器模块

负责将处理后的检测数据和视频帧渲染到屏幕窗口。
支持多种显示模式（RGB、深度、组合、并排）和实时交互控制。
"""

import logging
import threading
import time
from typing import Dict, List, Optional

import cv2
import numpy as np

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO, DeviceRole
from oak_vision_system.core.dto.data_processing_dto import DetectionStatusLabel
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacket,
    RenderPacketPackager,
)


class DisplayRenderer:
    """显示渲染器
    
    主要功能：
    - 多设备窗口管理
    - RGB 图像显示
    - 实时FPS显示和统计
    - 检测框、标签、坐标的可视化
    - 全屏模式和窗口位置控制
    """
    
    # 状态标签到颜色的映射字典（BGR格式）
    # 当启用 bbox_color_by_label 时，根据状态标签选择对应颜色
    STATE_LABEL_COLOR_MAP = {
        # 抓取物状态 (0-99)
        DetectionStatusLabel.OBJECT_GRASPABLE: (0, 255, 0),      # 绿色 - 可抓取
        DetectionStatusLabel.OBJECT_DANGEROUS: (0, 0, 255),      # 红色 - 危险
        DetectionStatusLabel.OBJECT_OUT_OF_RANGE: (128, 128, 128),  # 灰色 - 超出范围
        DetectionStatusLabel.OBJECT_PENDING_GRASP: (0, 255, 255),   # 黄色 - 待抓取
        
        # 人类状态 (100-199)
        DetectionStatusLabel.HUMAN_SAFE: (0, 255, 0),            # 绿色 - 安全
        DetectionStatusLabel.HUMAN_DANGEROUS: (0, 0, 255),       # 红色 - 危险
    }
    
    # 默认颜色（当状态标签未定义或未启用按标签着色时使用）
    DEFAULT_BBOX_COLOR = (0, 255, 0)  # 绿色
    
    def __init__(
        self,
        *,
        config: DisplayConfigDTO,
        packager: RenderPacketPackager,
        devices_list: List[str],
        role_bindings: Optional[Dict[DeviceRole, str]] = None,
        enable_depth_output: bool = False,
        event_bus = None,
    ) -> None:
        """初始化显示渲染器（子任务 5.1 + 6.1）
        
        Args:
            config: 显示配置
            packager: 渲染数据包打包器
            devices_list: 设备ID列表
            role_bindings: 设备角色绑定（role -> mxid 映射），可选参数
                          由外部通过配置管理器获取并传入
                          用于设备在线状态检测和自动切换逻辑
            enable_depth_output: 是否启用深度数据处理（子任务 6.1）
                                从硬件配置传入，控制是否处理深度帧
            event_bus: 事件总线实例，用于发布 SYSTEM_SHUTDOWN 事件
        """
        self._config = config
        self._packager = packager
        self._devices_list = devices_list
        self._role_bindings = role_bindings or {}  # 存储角色绑定（子任务 5.1）
        self._enable_depth_output = enable_depth_output  # 存储深度输出配置（子任务 6.1）
        self._event_bus = event_bus  # 存储事件总线实例
        
        # 单窗口管理
        self._main_window_name = "OAK Display"
        self._window_created = False
        self._is_fullscreen = False
        
        # 显示模式状态管理（子任务 3.2）
        # 显示模式：单设备索引（0, 1, 2...）或 "combined"
        self._display_mode = "combined"  # 默认为 Combined 模式
        self._selected_device_index = 0  # 当前选中的设备索引
        
        # 线程控制
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running_lock = threading.RLock()
        self._is_running = False
        
        # 统计信息（需求 13.2）
        self._stats = {
            "frames_rendered": 0,
            "start_time": 0.0,
            "fps": 0.0,
            "fps_history": [],  # FPS 历史记录（需求 13.2）
        }
        self._stats_lock = threading.Lock()
        
        # FPS计算
        self._frame_timestamps: List[float] = []
        self._fps_update_interval = 1.0
        self._last_fps_update_time = 0.0
        self._fps_history_max_length = 60  # 保留最近60秒的FPS历史
        
        # 帧率限制（需求 12.1, 12.2）
        self._target_frame_interval = 1.0 / config.target_fps if config.target_fps > 0 else 0.0
        self._last_frame_time = 0.0
        
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(
            "DisplayRenderer 初始化完成 - 设备数: %d, FPS: %d, 角色绑定数: %d, 深度输出: %s",
            len(devices_list), config.target_fps, len(self._role_bindings), 
            "启用" if self._enable_depth_output else "禁用"
        )
    
    def start(self) -> bool:
        """启动渲染器线程
        
        Returns:
            bool: 启动成功返回True，已在运行返回False
        """
        with self._running_lock:
            if self._is_running:
                return False
            
            self._stop_event.clear()
            self._is_running = True
            
            with self._stats_lock:
                self._stats["start_time"] = time.time()
            
            self._thread = threading.Thread(
                target=self._run_main_loop,
                name="DisplayRenderer",
                daemon=False
            )
            self._thread.start()
            
            self.logger.info("DisplayRenderer 已启动")
            return True
    
    def stop(self, timeout: float = 5.0) -> bool:
        """停止渲染器线程
        
        Args:
            timeout: 等待线程结束的超时时间（秒）
            
        Returns:
            bool: 停止成功返回True，超时返回False
        """
        with self._running_lock:
            if not self._is_running:
                return True
            
            self._stop_event.set()
            
            if self._thread is not None:
                self._thread.join(timeout=timeout)
                
                if self._thread.is_alive():
                    self.logger.warning("DisplayRenderer 停止超时")
                    self._is_running = False
                    return False
            
            self._is_running = False
            self._thread = None
            
            # 输出运行统计
            with self._stats_lock:
                runtime = time.time() - self._stats["start_time"]
                frames = self._stats["frames_rendered"]
                avg_fps = frames / runtime if runtime > 0 else 0
                
                self.logger.info(
                    "DisplayRenderer 已停止 - 帧数: %d, 时长: %.1fs, 平均FPS: %.1f",
                    frames, runtime, avg_fps
                )
            
            return True
    
    def get_stats(self) -> dict:
        """获取渲染统计信息（需求 13.1, 13.2）
        
        Returns:
            dict: 包含以下统计信息：
                - frames_rendered: 总渲染帧数
                - fps: 当前FPS
                - fps_history: FPS历史记录（最近60秒）
                - avg_fps: 平均FPS（基于历史记录）
                - min_fps: 最小FPS（基于历史记录）
                - max_fps: 最大FPS（基于历史记录）
                - runtime_sec: 运行时长（秒）
                - is_running: 是否正在运行
        """
        with self._stats_lock:
            runtime = time.time() - self._stats["start_time"] if self._stats["start_time"] > 0 else 0.0
            fps_history = self._stats["fps_history"].copy()
            
            # 计算FPS统计信息
            avg_fps = sum(fps_history) / len(fps_history) if fps_history else 0.0
            min_fps = min(fps_history) if fps_history else 0.0
            max_fps = max(fps_history) if fps_history else 0.0
            
            return {
                "frames_rendered": self._stats["frames_rendered"],
                "fps": self._stats["fps"],
                "fps_history": fps_history,
                "avg_fps": avg_fps,
                "min_fps": min_fps,
                "max_fps": max_fps,
                "runtime_sec": runtime,
                "is_running": self._is_running,
            }
    
    @property
    def is_running(self) -> bool:
        """检查渲染器是否正在运行"""
        with self._running_lock:
            return self._is_running
    
    def _run_main_loop(self) -> None:
        """主渲染循环
        
        持续获取渲染数据包并显示，处理键盘输入：
        - 'q': 退出
        - 'f': 切换全屏
        - '1', '2', '3'...: 切换到对应设备
        - '3' (或最后一个数字键): 切换到 Combined 模式
        
        实现帧率限制（需求 12.1, 12.2）：
        - 根据 target_fps 计算帧间隔
        - 测量实际渲染时间
        - 动态调整休眠时间以达到目标帧率
        """
        try:
            while not self._stop_event.is_set():
                # 记录帧开始时间
                frame_start_time = time.time()
                
                packets = self._packager.get_packets(timeout=0.1)
                
                if not packets:
                    continue
                
                # 单窗口渲染
                frame = self._render_current_mode(packets)
                
                if frame is not None:
                    # 创建窗口（如果尚未创建）
                    if not self._window_created:
                        self._create_main_window()
                    
                    cv2.imshow(self._main_window_name, frame)
                    
                    with self._stats_lock:
                        self._stats["frames_rendered"] += 1
                    
                    self._update_fps()
                
                # 处理键盘输入
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    # 发布 SYSTEM_SHUTDOWN 事件，通知 SystemManager 关闭系统
                    if self._event_bus is not None:
                        from oak_vision_system.core.system_manager import ShutdownEvent
                        self._event_bus.publish(
                            "SYSTEM_SHUTDOWN",
                            ShutdownEvent(reason="user_quit")
                        )
                        self.logger.info("用户按下 'q' 键，已发布 SYSTEM_SHUTDOWN 事件")
                    else:
                        # 如果没有 event_bus（向后兼容），使用旧的行为
                        self.logger.info("用户按下 'q' 键，停止渲染器")
                        self._stop_event.set()
                        break
                    # 继续运行，等待 SystemManager 调用 stop()
                elif key == ord('f'):
                    self._toggle_fullscreen()
                elif key == ord('1'):
                    self._switch_to_device(0)
                elif key == ord('2'):
                    self._switch_to_device(1)
                elif key == ord('3'):
                    self._switch_to_combined()
                
                # 帧率限制：计算需要休眠的时间（需求 12.1, 12.2）
                if self._target_frame_interval > 0:
                    frame_elapsed = time.time() - frame_start_time
                    sleep_time = self._target_frame_interval - frame_elapsed
                    
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                
                self._last_frame_time = time.time()
        finally:
            cv2.destroyAllWindows()
            # 同步状态：线程退出时将 _is_running 置为 False
            # 这样 display_manager.is_running 能立即反映渲染线程的退出状态
            with self._running_lock:
                self._is_running = False
    
    def _create_main_window(self) -> None:
        """创建单个主窗口（子任务 3.1 + 5.4 + 7.3）
        
        根据配置设置窗口大小、位置和全屏状态。
        
        子任务 5.4：固定窗口大小（双设备场景）
        - 单设备模式：使用配置的窗口大小（默认640x480）
        - Combined模式：固定为双倍宽度（1280x480）
        
        子任务 7.3：设置初始窗口标题
        """
        cv2.namedWindow(self._main_window_name, cv2.WINDOW_NORMAL)
        
        # 子任务 5.4：根据显示模式设置窗口大小
        if self._display_mode == "combined":
            # Combined 模式：双倍宽度（1280x480）
            window_width = self._config.window_width * 2 if self._config.window_width else 1280
            window_height = self._config.window_height if self._config.window_height else 480
        else:
            # 单设备模式：使用配置的窗口大小（默认640x480）
            window_width = self._config.window_width if self._config.window_width else 640
            window_height = self._config.window_height if self._config.window_height else 480
        
        cv2.resizeWindow(self._main_window_name, window_width, window_height)
        
        # 子任务 7.2：设置窗口位置
        if self._config.window_position_x or self._config.window_position_y:
            cv2.moveWindow(
                self._main_window_name, 
                self._config.window_position_x, 
                self._config.window_position_y
            )
        
        # 设置全屏模式
        if self._config.enable_fullscreen:
            cv2.setWindowProperty(
                self._main_window_name, 
                cv2.WND_PROP_FULLSCREEN, 
                cv2.WINDOW_FULLSCREEN
            )
            self._is_fullscreen = True
        else:
            self._is_fullscreen = False
        
        self._window_created = True
        
        # 子任务 7.3：设置初始窗口标题
        self._update_window_title()
        
        self.logger.info(f"主窗口已创建: {self._main_window_name} ({window_width}x{window_height})")
    
    def _get_active_devices(self) -> List[str]:
        """获取当前有数据的设备列表（子任务 5.2）
        
        基于 role_bindings 和 packager 缓存检测设备在线状态。
        检查两个设备是否有最近的数据（未过期）。
        
        Returns:
            在线设备ID列表（最多2个）
        """
        active = []
        now = time.time()
        
        # 只检查前两个设备（固定双设备场景）
        for device_id in self._devices_list[:2]:
            # 检查该设备是否有最近的数据
            if device_id in self._packager._latest_packets:
                packet = self._packager._latest_packets[device_id]
                if packet is not None:
                    # 检查数据是否过期
                    cached_at = self._packager._packet_timestamps.get(device_id, 0.0)
                    age = now - cached_at
                    if age <= self._packager.cache_max_age_sec:
                        active.append(device_id)
        
        return active
    
    def _render_current_mode(self, packets: Dict[str, RenderPacket]) -> Optional[np.ndarray]:
        """根据当前显示模式渲染帧（子任务 5.3 + 7.3 - 添加自动切换逻辑）
        
        Args:
            packets: 所有设备的渲染包字典
            
        Returns:
            渲染后的帧，如果无法渲染则返回 None
        """
        if not packets:
            return None
        
        # 子任务 5.3：实现单设备自动切换逻辑
        # 获取在线设备列表
        active_devices = self._get_active_devices()
        
        # 记录之前的显示模式，用于检测是否发生了自动切换
        previous_mode = self._display_mode
        
        # 如果只有一个设备在线，自动切换到单设备模式
        if len(active_devices) == 1:
            if self._display_mode != "single":
                self.logger.info(f"检测到只有一个设备在线，自动切换到单设备模式")
                self._display_mode = "single"
            # 找到在线设备的索引
            device_id = active_devices[0]
            if device_id in self._devices_list:
                self._selected_device_index = self._devices_list.index(device_id)
        # 如果两个设备都在线，且当前是单设备模式，可以考虑切换回 Combined
        # 但这里我们保持用户的选择，不自动切换回去
        
        # 子任务 7.3：如果显示模式发生了自动切换，更新窗口标题
        if previous_mode != self._display_mode and self._window_created:
            self._update_window_title()
        
        if self._display_mode == "combined":
            return self._render_combined_devices(packets)
        else:
            # 单设备模式
            if self._selected_device_index < len(self._devices_list):
                device_id = self._devices_list[self._selected_device_index]
                if device_id in packets:
                    return self._render_single_device(packets[device_id])
            return None
    
    # ==================== 绘制方法 ====================
    
    def _draw_detection_boxes(self, frame: np.ndarray, processed_data) -> None:
        """在帧上绘制检测框"""

        # 检查是否有检测框
        if processed_data.coords.shape[0] == 0:
            return

        # 检查是否有状态标签
        bboxes = processed_data.bbox
        state_labels = processed_data.state_label

        # 检查是否有检测框
        if bboxes is None or len(bboxes) == 0:
            return
        
        # 设置检测框的厚度
        thickness = 2
        
        for i, bbox in enumerate(bboxes):
            xmin, ymin, xmax, ymax = bbox
            
            # 根据配置和状态标签选择颜色
            if self._config.bbox_color_by_label and state_labels and i < len(state_labels):
                # 从映射字典中获取状态标签对应的颜色
                state_label = state_labels[i]
                color = self.STATE_LABEL_COLOR_MAP.get(state_label, self.DEFAULT_BBOX_COLOR)
            else:
                color = self.DEFAULT_BBOX_COLOR
            # 绘制检测框
            cv2.rectangle(
                frame, 
                (int(xmin), int(ymin)), 
                (int(xmax), int(ymax)), 
                color, 
                thickness
            )
    
    def _draw_text_with_background(
        self,
        frame: np.ndarray,
        text: str,
        position: tuple,
        font_scale: float,
        text_color: tuple = (255, 255, 255),
        bg_color: tuple = (0, 0, 0),
        thickness: int = 1,
        padding: int = 5
    ) -> None:
        """绘制带半透明背景的文本
        
        提高文本在复杂背景下的可读性。
        """
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        
        x, y = position
        
        # 计算背景矩形坐标
        bg_x1 = x - padding
        bg_y1 = y - text_height - padding
        bg_x2 = x + text_width + padding
        bg_y2 = y + baseline + padding
        
        # 绘制半透明背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), bg_color, -1)
        alpha = 0.6
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        # 绘制文本
        cv2.putText(
            frame, text, (x, y), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            font_scale, text_color, thickness, 
            cv2.LINE_AA
        )
    
    def _draw_labels(self, frame: np.ndarray, processed_data) -> None:
        """绘制检测标签和置信度"""
        if not self._config.show_labels:
            return
        
        if processed_data.coords.shape[0] == 0:
            return
        
        bboxes = processed_data.bbox
        labels = processed_data.labels
        confidences = processed_data.confidence
        
        if bboxes is None or len(bboxes) == 0:
            return
        
        font_scale = self._config.text_scale
        thickness = 1
        
        for i, bbox in enumerate(bboxes):
            xmin, ymin, xmax, ymax = bbox
            
            label_id = int(labels[i])
            label_text = f"Label_{label_id}"
            
            # 添加置信度
            if self._config.show_confidence:
                confidence = confidences[i]
                confidence_percent = round(confidence * 100)
                label_text = f"{label_text} {confidence_percent}%"
            
            # 计算文本位置（避免超出边界）
            text_x = int(xmin)
            text_y = int(ymin) - 10
            if text_y < 20:
                text_y = int(ymin) + 20
            
            self._draw_text_with_background(
                frame, label_text, (text_x, text_y), font_scale,
                text_color=(255, 255, 255), bg_color=(0, 0, 0), thickness=thickness
            )
    
    def _draw_coordinates(self, frame: np.ndarray, processed_data) -> None:
        """绘制3D空间坐标"""
        if not self._config.show_coordinates:
            return
        
        if processed_data.coords.shape[0] == 0:
            return
        
        bboxes = processed_data.bbox
        coords = processed_data.coords
        
        if bboxes is None or len(bboxes) == 0:
            return
        
        font_scale = self._config.text_scale
        thickness = 1
        
        for i, bbox in enumerate(bboxes):
            xmin, ymin, xmax, ymax = bbox
            x, y, z = coords[i]
            
            coord_text = f"({int(x)}, {int(y)}, {int(z)}) mm"
            
            # 计算文本位置（避免超出边界）
            text_x = int(xmin)
            text_y = int(ymax) + 20
            if text_y > frame.shape[0] - 10:
                text_y = int(ymax) - 10
            
            self._draw_text_with_background(
                frame, coord_text, (text_x, text_y), font_scale,
                text_color=(255, 255, 255), bg_color=(0, 0, 0), thickness=thickness
            )
    
    def _update_fps(self) -> None:
        """更新FPS统计
        
        使用滑动窗口计算实时FPS，并维护FPS历史记录（需求 13.2）。
        """
        current_time = time.time()
        
        self._frame_timestamps.append(current_time)
        
        # 保留最近1秒内的时间戳
        cutoff_time = current_time - 1.0
        self._frame_timestamps = [
            ts for ts in self._frame_timestamps if ts > cutoff_time
        ]
        
        # 每秒更新一次FPS
        if current_time - self._last_fps_update_time >= self._fps_update_interval:
            if len(self._frame_timestamps) > 1:
                time_span = self._frame_timestamps[-1] - self._frame_timestamps[0]
                fps = (len(self._frame_timestamps) - 1) / time_span if time_span > 0 else 0.0
            else:
                fps = 0.0
            
            with self._stats_lock:
                self._stats["fps"] = fps
                # 维护FPS历史记录（需求 13.2）
                self._stats["fps_history"].append(fps)
                # 限制历史记录长度
                if len(self._stats["fps_history"]) > self._fps_history_max_length:
                    self._stats["fps_history"].pop(0)
            
            self._last_fps_update_time = current_time
    
    def _draw_fps(self, frame: np.ndarray) -> None:
        """在帧上绘制FPS信息"""
        if not self._config.show_fps:
            return
        
        with self._stats_lock:
            fps = self._stats["fps"]
        
        fps_text = f"FPS: {fps:.1f}"
        
        self._draw_text_with_background(
            frame, fps_text, (10, 30), font_scale=0.7,
            text_color=(0, 255, 0), bg_color=(0, 0, 0), thickness=2
        )
    
    def _draw_device_info(
        self, 
        frame: np.ndarray, 
        device_id: str, 
        processed_data
    ) -> None:
        """在帧上绘制设备信息"""
        if not self._config.show_device_info:
            return
        
        device_alias = processed_data.device_alias
        
        if device_alias:
            device_info_text = f"Device: {device_alias} ({device_id})"
        else:
            device_info_text = f"Device: {device_id}"
        
        font_scale = 0.6
        thickness = 1
        (text_width, text_height), baseline = cv2.getTextSize(
            device_info_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        
        # 右上角显示
        text_x = frame.shape[1] - text_width - 10
        text_y = 30
        
        self._draw_text_with_background(
            frame, device_info_text, (text_x, text_y), font_scale=font_scale,
            text_color=(255, 255, 0), bg_color=(0, 0, 0), thickness=thickness
        )
    
    def _draw_key_hints(self, frame: np.ndarray) -> None:
        """在窗口底部显示按键提示信息（子任务 4.4）
        
        显示格式："1:Device1 2:Device2 3:Combined F:Fullscreen Q:Quit"
        """
        # 构建按键提示文本
        hints = []
        
        # 添加设备切换键提示
        for i, device_id in enumerate(self._devices_list):
            key_num = i + 1
            # 尝试从 packager 获取设备别名
            # 如果有缓存的渲染包，使用其中的设备别名
            device_name = f"Device{key_num}"
            
            # 尝试从最近的渲染包中获取设备别名
            try:
                latest_packets = self._packager._latest_packets
                if device_id in latest_packets:
                    packet = latest_packets[device_id]
                    if packet and packet.processed_detections.device_alias:
                        device_name = packet.processed_detections.device_alias
            except Exception:
                pass  # 如果获取失败，使用默认名称
            
            hints.append(f"{key_num}:{device_name}")
        
        # 添加 Combined 模式键提示
        hints.append("3:Combined")
        
        # 添加全屏和退出键提示
        hints.append("F:Fullscreen")
        hints.append("Q:Quit")
        
        hint_text = "  ".join(hints)
        
        # 计算文本位置（窗口底部居中）
        font_scale = 0.5
        thickness = 1
        (text_width, text_height), baseline = cv2.getTextSize(
            hint_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        
        # 底部居中显示
        text_x = (frame.shape[1] - text_width) // 2
        text_y = frame.shape[0] - 10
        
        self._draw_text_with_background(
            frame, hint_text, (text_x, text_y), font_scale=font_scale,
            text_color=(200, 200, 200), bg_color=(0, 0, 0), thickness=thickness
        )
    
    # ==================== 深度图处理 ====================
    
    def _visualize_depth(self, depth_frame: np.ndarray) -> Optional[np.ndarray]:
        """将深度图转换为彩色可视化（使用HOT颜色映射）（子任务 6.1 + 6.2）
        
        处理步骤：
        1. 检查是否启用深度输出（子任务 6.1）
        2. 清理无效值（NaN、Inf）
        3. 使用百分位数归一化深度值（避免极值影响）
        4. 应用HOT伪彩色映射
        
        参考旧实现的百分位数归一化方法，比简单的 cv2.normalize 更鲁棒。
        
        Args:
            depth_frame: 深度帧数据
            
        Returns:
            彩色深度图，如果未启用深度输出或数据无效则返回 None
        """
        # 子任务 6.1：检查是否启用深度输出
        if not self._enable_depth_output:
            return None
        
        if depth_frame is None or depth_frame.size == 0:
            return None
        
        depth_frame = depth_frame.copy()
        depth_frame[np.isnan(depth_frame)] = 0
        depth_frame[np.isinf(depth_frame)] = 0
        
        # 降采样以提高性能
        depth_downscaled = depth_frame[::4, ::4]
        
        # 归一化深度值（子任务 6.2：确认百分位数归一化逻辑）
        if self._config.normalize_depth:
            # 使用百分位数归一化（避免极值影响）
            if np.all(depth_downscaled == 0):
                min_depth = 0
            else:
                min_depth = np.percentile(depth_downscaled[depth_downscaled != 0], 1)
            
            max_depth = np.percentile(depth_downscaled, 99)
            
            if max_depth > min_depth:
                depth_normalized = np.interp(
                    depth_frame, (min_depth, max_depth), (0, 255)
                ).astype(np.uint8)
            else:
                depth_normalized = np.zeros_like(depth_frame, dtype=np.uint8)
        else:
            depth_normalized = (depth_frame / 256).astype(np.uint8)
        
        # 子任务 6.2：确认使用 HOT 颜色映射（与旧实现一致）
        depth_colored = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_HOT)
        
        return depth_colored
    
    # ==================== 显示模式 ====================
    
    def _render_single_device(self, packet: RenderPacket) -> Optional[np.ndarray]:
        """渲染单个设备的RGB帧（子任务 3.3）
        
        Args:
            packet: 单个设备的渲染包
            
        Returns:
            渲染后的帧
        """
        # 使用视图而非复制（需求 12.5）
        frame = packet.video_frame.rgb_frame
        
        # 检查帧是否可写，如果不可写则复制
        if not frame.flags.writeable:
            frame = frame.copy()
        
        # 绘制检测信息
        self._draw_detection_boxes(frame, packet.processed_detections)
        self._draw_labels(frame, packet.processed_detections)
        self._draw_coordinates(frame, packet.processed_detections)
        
        # 绘制设备信息叠加
        device_id = packet.processed_detections.device_id
        device_alias = packet.processed_detections.device_alias
        
        # 在左上角显示设备名称（大字体）
        device_name = device_alias or device_id
        self._draw_text_with_background(
            frame, device_name, (10, 50), font_scale=1.0,
            text_color=(0, 255, 255), bg_color=(0, 0, 0), thickness=2
        )
        
        # 绘制FPS
        self._draw_fps(frame)
        
        # 在右上角显示设备详细信息
        if self._config.show_device_info:
            self._draw_device_info(frame, device_id, packet.processed_detections)
        
        # 绘制按键提示信息（子任务 4.4）
        self._draw_key_hints(frame)
        
        return frame
    
    def _render_combined_devices(self, packets: Dict[str, RenderPacket]) -> Optional[np.ndarray]:
        """渲染多设备RGB水平拼接（子任务 3.4 - 新的Combined模式）
        
        Args:
            packets: 所有设备的渲染包字典
            
        Returns:
            水平拼接后的帧
        """
        if not packets:
            return None
        
        rgb_frames = []
        device_names = []
        
        # 按设备列表顺序收集RGB帧
        for device_id in self._devices_list:
            if device_id in packets:
                packet = packets[device_id]
                
                # 渲染单个设备的帧（包含检测框等）
                frame = packet.video_frame.rgb_frame
                
                # 检查帧是否可写，如果不可写则复制
                if not frame.flags.writeable:
                    frame = frame.copy()
                
                # 绘制检测信息
                self._draw_detection_boxes(frame, packet.processed_detections)
                self._draw_labels(frame, packet.processed_detections)
                self._draw_coordinates(frame, packet.processed_detections)
                
                rgb_frames.append(frame)
                device_names.append(packet.processed_detections.device_alias or device_id)
        
        if not rgb_frames:
            return None
        
        # 水平拼接
        if len(rgb_frames) == 1:
            combined = rgb_frames[0]
        else:
            combined = np.hstack(rgb_frames)
        
        # 在每个设备图像上添加设备名称标签
        frame_width = rgb_frames[0].shape[1]
        for i, name in enumerate(device_names):
            x_offset = i * frame_width
            self._draw_text_with_background(
                combined, name, (x_offset + 10, 30), font_scale=0.7,
                text_color=(0, 255, 255), bg_color=(0, 0, 0), thickness=2
            )
        
        # 在整个拼接图像上绘制FPS（左上角）
        self._draw_fps(combined)
        
        # 绘制按键提示信息（子任务 4.4）
        self._draw_key_hints(combined)
        
        return combined
    
    def _render_rgb_mode(self, packet: RenderPacket) -> Optional[np.ndarray]:
        """渲染RGB模式
        
        优化：直接在原始帧上绘制，避免不必要的复制（需求 12.4, 12.5）
        """
        # 使用视图而非复制（需求 12.5）
        frame = packet.video_frame.rgb_frame
        
        # 检查帧是否可写，如果不可写则复制
        if not frame.flags.writeable:
            frame = frame.copy()
        
        self._draw_detection_boxes(frame, packet.processed_detections)
        self._draw_labels(frame, packet.processed_detections)
        self._draw_coordinates(frame, packet.processed_detections)
        self._draw_fps(frame)
        
        device_id = packet.processed_detections.device_id
        self._draw_device_info(frame, device_id, packet.processed_detections)
        
        return frame
    
    # ==================== 窗口控制 ====================
    
    def _switch_to_device(self, device_index: int) -> None:
        """切换到指定设备的单设备显示（子任务 4.2 + 5.4 + 7.3）
        
        Args:
            device_index: 设备索引（0, 1, 2...）
        """
        if device_index < len(self._devices_list):
            self._display_mode = "single"
            self._selected_device_index = device_index
            device_id = self._devices_list[device_index]
            
            # 子任务 5.4：调整窗口大小为单设备模式
            if self._window_created and not self._is_fullscreen:
                window_width = self._config.window_width if self._config.window_width else 640
                window_height = self._config.window_height if self._config.window_height else 480
                cv2.resizeWindow(self._main_window_name, window_width, window_height)
            
            # 子任务 7.3：更新窗口标题（单设备模式：显示设备名称）
            if self._window_created:
                self._update_window_title()
            
            self.logger.info(f"切换到设备 {device_index + 1}: {device_id}")
    
    def _switch_to_combined(self) -> None:
        """切换到Combined模式（多设备拼接）（子任务 4.3 + 5.4 + 7.3）"""
        self._display_mode = "combined"
        
        # 子任务 5.4：调整窗口大小为 Combined 模式（双倍宽度）
        if self._window_created and not self._is_fullscreen:
            window_width = self._config.window_width * 2 if self._config.window_width else 1280
            window_height = self._config.window_height if self._config.window_height else 480
            cv2.resizeWindow(self._main_window_name, window_width, window_height)
        
        # 子任务 7.3：更新窗口标题（Combined模式：显示 "Combined View"）
        if self._window_created:
            self._update_window_title()
        
        self.logger.info("切换到 Combined 模式")
    
    def _toggle_fullscreen(self) -> None:
        """切换主窗口的全屏状态"""
        if not self._window_created:
            return
        
        self._is_fullscreen = not self._is_fullscreen
        mode = cv2.WINDOW_FULLSCREEN if self._is_fullscreen else cv2.WINDOW_NORMAL
        cv2.setWindowProperty(self._main_window_name, cv2.WND_PROP_FULLSCREEN, mode)
        
        status = "全屏" if self._is_fullscreen else "窗口"
        self.logger.info(f"切换到{status}模式")
    
    def _update_window_title(self) -> None:
        """更新窗口标题（子任务 7.3）
        
        根据当前显示模式更新窗口标题：
        - 单设备模式：显示设备名称（例如："left_camera - OAK Display"）
        - Combined模式：显示 "Combined View - OAK Display"
        """
        if not self._window_created:
            return
        
        if self._display_mode == "combined":
            # Combined 模式：显示 "Combined View"
            new_title = "Combined View - OAK Display"
        else:
            # 单设备模式：显示设备名称
            if self._selected_device_index < len(self._devices_list):
                device_id = self._devices_list[self._selected_device_index]
                
                # 尝试从最近的渲染包中获取设备别名
                device_name = device_id
                try:
                    latest_packets = self._packager._latest_packets
                    if device_id in latest_packets:
                        packet = latest_packets[device_id]
                        if packet and packet.processed_detections.device_alias:
                            device_name = packet.processed_detections.device_alias
                except Exception:
                    pass  # 如果获取失败，使用设备ID
                
                new_title = f"{device_name} - OAK Display"
            else:
                new_title = "OAK Display"
        
        # 更新窗口标题
        cv2.setWindowTitle(self._main_window_name, new_title)
        self.logger.debug(f"窗口标题已更新: {new_title}")
