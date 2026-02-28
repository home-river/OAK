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
from oak_vision_system.modules.display_modules.render_config import (
    STATUS_COLOR_MAP,
    DEFAULT_DETECTION_COLOR,
    BBOX_THICKNESS,
    LABEL_FONT,
    LABEL_FONT_SCALE,
    LABEL_THICKNESS,
)

class DisplayRenderer:
    """显示渲染器
    
    主要功能：
    - 多设备窗口管理
    - RGB 图像显示
    - 实时FPS显示和统计
    - 检测框、标签、坐标的可视化
    - 全屏模式和窗口位置控制
    
    注意：颜色映射配置已移至 render_config.py 模块，实现集中配置管理
    """
    
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
        """初始化显示渲染器
        
        Args:
            config: 显示配置
            packager: 渲染数据包打包器
            devices_list: 设备ID列表
            role_bindings: 设备角色绑定（role -> mxid 映射），可选参数
                          由外部通过配置管理器获取并传入
            enable_depth_output: 是否启用深度数据处理
            event_bus: 事件总线实例（未使用，保留用于向后兼容）
        """
        self._config = config
        self._packager = packager
        self._devices_list = devices_list
        self._role_bindings = role_bindings or {}  # 存储角色绑定
        self._enable_depth_output = enable_depth_output  # 存储深度输出配置
        self._event_bus = event_bus  # 保留用于向后兼容
        
        # 单窗口管理
        self._main_window_name = "OAK Display"
        self._window_created = False
        self._is_fullscreen = False
        
        # 双状态驱动架构（任务 3.4）
        # 状态 1：显示模式 - "combined" | "single"
        self._display_mode = "combined"  # 默认为 Combined 模式
        # 状态 2：选中的设备角色（单设备模式下使用）
        self._selected_device_role = DeviceRole.LEFT_CAMERA  # 默认选择左相机
        
        # 窗口层尺寸配置（任务 3.4）
        self._window_width = 1280
        self._window_height = 720  # 16:9
        self._fullscreen_width = 1920
        self._fullscreen_height = 1080  # 16:9
        
        # 统计信息（需求 13.2）
        self._stats = {
            "frames_rendered": 0,
            "start_time": 0.0,
            "fps": 0.0,
            "fps_history": [],  # FPS 历史记录
        }
        self._stats_lock = threading.Lock()
        
        # FPS计算
        self._frame_timestamps: List[float] = []
        self._fps_update_interval = 1.0
        self._last_fps_update_time = 0.0
        self._fps_history_max_length = 60  # 保留最近60秒的FPS历史
        
        # 帧率限制
        self._target_frame_interval = 1.0 / config.target_fps if config.target_fps > 0 else 0.0
        self._last_frame_time = 0.0
        
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(
            "DisplayRenderer 初始化完成 - 设备数: %d, FPS: %d, 角色绑定数: %d, 深度输出: %s",
            len(devices_list), config.target_fps, len(self._role_bindings), 
            "启用" if self._enable_depth_output else "禁用"
        )
    
    def initialize(self) -> None:
        """初始化渲染器（任务 3.2）
        
        功能：
        - 初始化统计信息
        - 准备窗口创建（但不立即创建）
        - 设置初始状态
        """
        with self._stats_lock:
            self._stats["start_time"] = time.time()
        
        self._window_created = False
        self.logger.info("DisplayRenderer 已初始化")
    
    def cleanup(self) -> None:
        """清理渲染器资源（任务 3.3）
        
        功能：
        - 关闭所有 OpenCV 窗口
        - 输出统计信息
        - 清理状态
        """
        cv2.destroyAllWindows()
        
        with self._stats_lock:
            runtime = time.time() - self._stats["start_time"]
            frames = self._stats["frames_rendered"]
            avg_fps = frames / runtime if runtime > 0 else 0
            
            self.logger.info(
                "DisplayRenderer 已清理 - 帧数: %d, 时长: %.1fs, 平均FPS: %.1f",
                frames, runtime, avg_fps
            )
    
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
            }
    
    def render_once(self) -> bool:
        """执行一次渲染循环（任务 3.5 - 主线程调用）
        
        Returns:
            bool: True 表示用户按下 'q' 键请求退出，False 表示继续运行
        
        实现流程（状态驱动 + 惰性渲染 + Stretch Resize）：
        1. 根据状态 1（显示模式）选择取包策略：
           - 单设备模式：调用 get_packet_by_mxid(device_mxid, timeout)
           - 拼接模式：调用 get_packets(timeout)
        2. 根据状态 2（视图属性）确定目标分辨率
        3. 渲染当前模式的帧（按需分支，内部使用 Stretch Resize）
        4. 创建窗口（如果尚未创建）
        5. 显示帧（已经是目标尺寸，无需再次 resize）
        6. 处理键盘输入
        7. 更新统计信息
        8. 返回退出信号
        """
        # 1. 根据显示模式选择取包策略（惰性渲染）
        if self._display_mode == "combined":
            # 拼接模式：获取所有设备的渲染包
            packets = self._packager.get_packets(timeout=0.01)
            
            if not packets:
                # 无数据时仍需处理按键
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    return True
                return False
            
            # 渲染拼接帧（内部已完成 Stretch Resize 到目标尺寸）
            frame = self._render_combined_devices(packets)
        else:
            # 单设备模式：仅获取当前设备的渲染包（惰性渲染）
            # 根据当前选中的角色（LEFT_CAMERA 或 RIGHT_CAMERA）获取 mxid
            if self._selected_device_role in self._role_bindings:
                device_mxid = self._role_bindings[self._selected_device_role]
                packet = self._packager.get_packet_by_mxid(device_mxid, timeout=0.01)
                
                if packet is None:
                    # 无数据时仍需处理按键
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        return True
                    return False
                
                # 渲染单设备帧（内部已完成 Stretch Resize 到目标尺寸）
                frame = self._render_single_device(packet)
            else:
                return False
        
        if frame is not None:
            # 2. 创建窗口（如果尚未创建）
            if not self._window_created:
                self._create_main_window()
            
            # 3. 显示帧（已经是目标尺寸，无需再次 resize）
            cv2.imshow(self._main_window_name, frame)
            
            # 更新统计
            with self._stats_lock:
                self._stats["frames_rendered"] += 1
            
            self._update_fps()
        
        # 4. 处理键盘输入（任务 3.10）
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            self.logger.info("用户按下 'q' 键")
            return True
        elif key == ord('f'):
            self._toggle_fullscreen()
        elif key == ord('1'):
            self._switch_to_device(DeviceRole.LEFT_CAMERA)  # 切换到左相机
        elif key == ord('2'):
            self._switch_to_device(DeviceRole.RIGHT_CAMERA)  # 切换到右相机
        elif key == ord('3'):
            self._switch_to_combined()  # 切换到拼接模式
        
        # 5. 帧率限制
        if self._target_frame_interval > 0:
            current_time = time.time()
            elapsed = current_time - self._last_frame_time
            sleep_time = self._target_frame_interval - elapsed
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            self._last_frame_time = time.time()
        
        return False
    
    def _create_main_window(self) -> None:
        """创建主窗口
        
        策略：
        1. 创建 WINDOW_NORMAL 类型窗口（可调整大小）
        2. 不使用 cv2.resizeWindow()（渲染方法内部已完成 resize）
        3. 根据全屏配置设置窗口属性
        4. 渲染方法返回的帧已经是目标尺寸，可直接 imshow
        """
        cv2.namedWindow(self._main_window_name, cv2.WINDOW_NORMAL)
        
        # 设置窗口位置（如果配置了）
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
        self.logger.info(f"主窗口已创建: {self._main_window_name}")
    
    # ==================== 绘制方法 ====================
    
    def _draw_detection_boxes_normalized(
        self,
        canvas: np.ndarray,
        detections,
        roiW: int,
        roiH: int,
        offsetX: int
    ) -> None:
        """在画布上绘制归一化坐标的检测框（任务 3.8）
        
        Args:
            canvas: 已 resize 到目标尺寸的画布
            detections: 包含归一化坐标的检测结果
            roiW: 当前 ROI 宽度
            roiH: 当前 ROI 高度（通常等于 target_height）
            offsetX: 水平偏移量（合并模式用，单图模式为0）
        
        实现：
        1. 遍历检测结果
        2. 根据 status_label 从 render_config 获取颜色
        3. 将归一化坐标映射到画布像素坐标
        4. 使用状态对应的颜色绘制矩形框和标签
        """
        
        
        # 检查是否有检测框
        if detections.coords.shape[0] == 0:
            return
        
        bboxes = detections.bbox
        state_labels = detections.state_label
        labels = detections.labels
        confidences = detections.confidence
        
        if bboxes is None or len(bboxes) == 0:
            return
        
        for i, bbox in enumerate(bboxes):
            # 1. 获取状态标签对应的颜色
            if self._config.bbox_color_by_label and state_labels and i < len(state_labels):
                status_label = state_labels[i]
                color = STATUS_COLOR_MAP.get(status_label, DEFAULT_DETECTION_COLOR)
            else:
                color = DEFAULT_DETECTION_COLOR
            
            # 2. 归一化坐标映射到画布像素坐标
            xmin, ymin, xmax, ymax = bbox
            x1 = int(xmin * roiW) + offsetX
            y1 = int(ymin * roiH)
            x2 = int(xmax * roiW) + offsetX
            y2 = int(ymax * roiH)
            
            # 3. 使用状态对应的颜色绘制矩形框
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, BBOX_THICKNESS)
            
            # 4. 绘制标签（如果启用）
            if self._config.show_labels:
                label_id = int(labels[i])
                label_text = f"Label_{label_id}"
                
                # 添加置信度
                if self._config.show_confidence:
                    confidence = confidences[i]
                    confidence_percent = round(confidence * 100)
                    label_text = f"{label_text} {confidence_percent}%"
                
                # 计算标签背景位置
                (label_w, label_h), baseline = cv2.getTextSize(
                    label_text, LABEL_FONT, LABEL_FONT_SCALE, LABEL_THICKNESS
                )
                
                # 绘制标签背景（填充矩形）
                cv2.rectangle(
                    canvas,
                    (x1, y1 - label_h - baseline - 5),
                    (x1 + label_w, y1),
                    color,
                    -1  # 填充
                )
                
                # 绘制标签文字（白色，确保可读性）
                cv2.putText(
                    canvas,
                    label_text,
                    (x1, y1 - baseline - 5),
                    LABEL_FONT,
                    LABEL_FONT_SCALE,
                    (255, 255, 255),  # 白色文字
                    LABEL_THICKNESS
                )
            
            # 5. 绘制3D坐标（如果启用）
            if self._config.show_coordinates:
                coords = detections.coords
                x, y, z = coords[i]
                coord_text = f"({int(x)}, {int(y)}, {int(z)}) mm"
                
                # 计算文本位置
                text_x = x1
                text_y = y2 + 20
                if text_y > canvas.shape[0] - 10:
                    text_y = y2 - 10
                
                self._draw_text_with_background(
                    canvas, coord_text, (text_x, text_y), 
                    font_scale=self._config.text_scale,
                    text_color=(255, 255, 255), bg_color=(0, 0, 0), thickness=1
                )
    
    def _draw_detection_boxes(self, frame: np.ndarray, processed_data) -> None:
        """在帧上绘制检测框（旧方法，保留用于向后兼容）
        
        注意：此方法使用 render_config 中的颜色映射配置
        """
        # 检查是否有检测框
        if processed_data.coords.shape[0] == 0:
            return

        # 检查是否有状态标签
        bboxes = processed_data.bbox
        state_labels = processed_data.state_label

        # 检查是否有检测框
        if bboxes is None or len(bboxes) == 0:
            return
        
        for i, bbox in enumerate(bboxes):
            xmin, ymin, xmax, ymax = bbox
            
            # 根据配置和状态标签选择颜色
            if self._config.bbox_color_by_label and state_labels and i < len(state_labels):
                # 从 render_config 映射字典中获取状态标签对应的颜色
                state_label = state_labels[i]
                color = STATUS_COLOR_MAP.get(state_label, DEFAULT_DETECTION_COLOR)
            else:
                color = DEFAULT_DETECTION_COLOR
            
            # 绘制检测框
            cv2.rectangle(
                frame, 
                (int(xmin), int(ymin)), 
                (int(xmax), int(ymax)), 
                color, 
                BBOX_THICKNESS
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
        """渲染单设备模式（任务 3.6 - 返回已 resize 到目标尺寸的帧）
        
        Stretch Resize 策略：
        - 直接 stretch resize 到目标尺寸（窗口模式 1280x720 / 全屏 1920x1080）
        - 在最终画布上绘制 UI（使用归一化坐标映射）
        
        Returns:
            已经 resize 到目标尺寸（窗口或全屏）的画布，可直接用于 cv2.imshow()
        """
        frame = packet.video_frame.rgb_frame
        
        # 确定目标尺寸（根据状态 2：视图属性）
        if self._is_fullscreen:
            target_width = self._fullscreen_width
            target_height = self._fullscreen_height
        else:
            target_width = self._window_width
            target_height = self._window_height
        
        # Stretch resize 到目标尺寸（直接拉伸，不保持宽高比）
        frame_resized = cv2.resize(frame, (target_width, target_height))
        
        # 检查可写性
        if not frame_resized.flags.writeable:
            frame_resized = frame_resized.copy()
        
        # 绘制检测信息（使用归一化坐标映射）
        self._draw_detection_boxes_normalized(
            frame_resized, packet.processed_detections,
            target_width, target_height, offsetX=0
        )
        
        # 绘制叠加信息
        device_name = packet.processed_detections.device_alias or packet.processed_detections.device_id
        self._draw_text_with_background(
            frame_resized, device_name, (10, 50), 
            font_scale=1.0, text_color=(0, 255, 255)
        )
        
        self._draw_fps(frame_resized)
        
        if self._config.show_device_info:
            self._draw_device_info(frame_resized, packet.processed_detections.device_id, packet.processed_detections)
        
        self._draw_key_hints(frame_resized)
        
        return frame_resized
    
    def _render_combined_devices(self, packets: Dict[str, RenderPacket]) -> Optional[np.ndarray]:
        """渲染合并模式（任务 3.7 - 返回已 resize 到目标尺寸的帧）
        
        Stretch Resize 策略：
        1. 确定目标画布尺寸（Target_W, Target_H）
        2. 计算每路 ROI 尺寸（roiW_left, roiW_right）
        3. 分别 stretch resize 到 ROI 尺寸
        4. 水平拼接到画布
        5. 在最终画布上绘制 UI（使用归一化坐标映射）
        
        Returns:
            已经 resize 到目标尺寸（窗口或全屏）的画布，可直接用于 cv2.imshow()
        """
        # 确定目标画布尺寸（根据状态 2：视图属性）
        if self._is_fullscreen:
            target_width = self._fullscreen_width
            target_height = self._fullscreen_height
        else:
            target_width = self._window_width
            target_height = self._window_height
        
        # 计算 ROI 尺寸
        roiW_left = target_width // 2
        roiW_right = target_width - roiW_left
        
        rgb_frames = []
        
        # 处理每个设备
        for i, device_id in enumerate(self._devices_list):
            if device_id in packets:
                packet = packets[device_id]
                frame = packet.video_frame.rgb_frame
                
                # 确定当前设备的 ROI 尺寸
                roiW = roiW_left if i == 0 else roiW_right
                
                # Stretch resize 到 ROI 尺寸（直接拉伸，不保持宽高比）
                frame_resized = cv2.resize(frame, (roiW, target_height))
                
                # 检查可写性
                if not frame_resized.flags.writeable:
                    frame_resized = frame_resized.copy()
                
                # 添加设备名称标签
                device_name = packet.processed_detections.device_alias or device_id
                self._draw_text_with_background(
                    frame_resized, device_name, (10, 30), 
                    font_scale=0.7, text_color=(0, 255, 255)
                )
                
                rgb_frames.append(frame_resized)
        
        if not rgb_frames:
            return None
        
        # 水平拼接（拼接后的画布尺寸正好是 target_width × target_height）
        combined = np.hstack(rgb_frames)

        # 在最终画布上绘制检测信息（使用归一化坐标映射）
        # 说明：检测框坐标使用归一化坐标（0~1），映射到目标画布 ROI 后，再加 offsetX
        for i, device_id in enumerate(self._devices_list):
            if device_id in packets:
                packet = packets[device_id]
                roiW = roiW_left if i == 0 else roiW_right
                offsetX = 0 if i == 0 else roiW_left
                self._draw_detection_boxes_normalized(
                    combined, packet.processed_detections,
                    roiW, target_height, offsetX
                )
        
        # 绘制全局叠加信息
        self._draw_fps(combined)
        self._draw_key_hints(combined)
        
        return combined
    

    
    # ==================== 窗口控制 ====================
    
    def _switch_to_device(self, device_role: DeviceRole) -> None:
        """切换到指定角色的设备显示（任务 3.9 - 基于 DeviceRole）
        
        Args:
            device_role: 设备角色（DeviceRole.LEFT_CAMERA 或 DeviceRole.RIGHT_CAMERA）
        
        实现：
        1. 检查 role_bindings 中是否存在该角色
        2. 切换显示模式为 "single"
        3. 更新 _selected_device_role
        4. 记录日志
        """
        if device_role not in self._role_bindings:
            self.logger.warning(f"角色 {device_role} 不存在于 role_bindings 中")
            return
        
        self._display_mode = "single"
        self._selected_device_role = device_role
        device_mxid = self._role_bindings[device_role]
        
        self.logger.info(f"切换到设备角色 {device_role.name}: {device_mxid}")
    
    def _switch_to_combined(self) -> None:
        """切换到Combined模式（多设备拼接）"""
        self._display_mode = "combined"
        self.logger.info("切换到 Combined 模式")
    
    def _toggle_fullscreen(self) -> None:
        """切换全屏/窗口模式
        
        策略：
        1. 切换 _is_fullscreen 标志
        2. 使用 cv2.setWindowProperty 切换窗口属性
        3. 下一帧渲染时，_render_single_device() 或 _render_combined_devices() 
           会根据 _is_fullscreen 选择对应的目标尺寸进行 resize
        """
        if not self._window_created:
            return
        
        # 切换标志
        self._is_fullscreen = not self._is_fullscreen
        
        # 设置窗口属性
        if self._is_fullscreen:
            cv2.setWindowProperty(
                self._main_window_name,
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN
            )
            self.logger.info("切换到全屏模式")
        else:
            cv2.setWindowProperty(
                self._main_window_name,
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_NORMAL
            )
            self.logger.info("切换到窗口模式")
        
        # 注意：不需要手动 resize 窗口
        # 下一帧渲染时会根据 _is_fullscreen 自动选择目标尺寸
    

