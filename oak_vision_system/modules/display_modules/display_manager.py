"""
显示模块主控制器

负责协调 RenderPacketPackager 和 DisplayRenderer 两个子模块，
提供统一的启动、停止和统计接口。
"""

import logging
import threading
from typing import Dict, List, Optional

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO, DeviceRole
from oak_vision_system.modules.display_modules.render_packet_packager import (
    RenderPacketPackager,
)
from oak_vision_system.modules.display_modules.display_renderer import (
    DisplayRenderer,
)


class DisplayManager:
    """显示模块主控制器
    
    职责：
    - 创建和管理 RenderPacketPackager（适配器子模块）
    - 创建和管理 DisplayRenderer（渲染器子模块）
    - 提供统一的 start/stop 接口
    - 聚合统计信息
    - 处理配置验证
    """
    
    def __init__(
        self,
        *,
        config: DisplayConfigDTO,
        devices_list: List[str],
        role_bindings: Optional[Dict[DeviceRole, str]] = None,
        enable_depth_output: bool = False,
    ) -> None:
        """初始化显示管理器（子任务 5.1 + 6.1）
        
        Args:
            config: 显示配置对象
            devices_list: 设备ID列表
            role_bindings: 设备角色绑定（role -> mxid 映射），可选参数
                          由外部通过配置管理器获取并传入
                          用于设备在线状态检测和自动切换逻辑
            enable_depth_output: 是否启用深度数据处理（子任务 6.1）
                                从硬件配置传入，控制是否处理深度帧
            
        Raises:
            ValueError: 如果配置无效（需求 4.6, 5.5）
        """
        # 验证配置有效性（需求 4.6）
        if not config.validate():
            errors = config.get_validation_errors()
            error_msg = f"DisplayConfigDTO 配置无效: {errors}"
            # 配置无效时抛出 ValueError（需求 5.5）
            raise ValueError(error_msg)
        
        self._config = config
        self._devices_list = devices_list
        self._role_bindings = role_bindings or {}  # 存储角色绑定（子任务 5.1）
        self._enable_depth_output = enable_depth_output  # 存储深度输出配置（子任务 6.1）
        
        # 创建 RenderPacketPackager 实例（适配器子模块）
        self._packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=devices_list,
            cache_max_age_sec=1.0,
        )
        
        # 创建 DisplayRenderer 实例（渲染器子模块）
        self._renderer = DisplayRenderer(
            config=config,
            packager=self._packager,
            devices_list=devices_list,
            role_bindings=role_bindings,  # 传入角色绑定（子任务 5.1）
            enable_depth_output=enable_depth_output,  # 传入深度输出配置（子任务 6.1）
            event_bus=self._packager.event_bus,  # 传入事件总线，用于发布 SYSTEM_SHUTDOWN 事件
        )
        
        # 日志（需求 5.5）
        self.logger = logging.getLogger(__name__)
        
        # 状态管理（用于幂等性检查和线程安全）
        self._is_running = False
        self._running_lock = threading.RLock()
        
        self.logger.info(
            "DisplayManager 已初始化，设备数量: %d, enable_display: %s, 角色绑定数: %d, 深度输出: %s",
            len(devices_list),
            config.enable_display,
            len(self._role_bindings),
            "启用" if enable_depth_output else "禁用"
        )

    def start(self) -> bool:
        """启动显示模块
        
        启动流程：
        1. 检查幂等性（如果已启动则返回False）
        2. 启动 RenderPacketPackager（订阅事件，启动工作线程）
        3. 根据 enable_display 配置决定是否启动 DisplayRenderer
        4. 使用 AND 逻辑判断：两个子模块都成功启动才算成功
        5. 如果启动失败，清理已启动的子模块（需求 5.5）
        
        Returns:
            bool: 是否成功启动
            
        Raises:
            RuntimeError: 如果子模块启动失败（需求 5.5）
        """
        with self._running_lock:
            # 1. 幂等性检查
            if self._is_running:
                self.logger.info("DisplayManager 已在运行")
                return False
            
            packager_started = False
            renderer_started = False
            
            try:
                # 2. 启动 RenderPacketPackager
                self.logger.info("启动 RenderPacketPackager...")
                packager_started = self._packager.start()
                
                if not packager_started:
                    raise RuntimeError("RenderPacketPackager 启动失败")
                
                # 3. 根据配置决定是否启动 DisplayRenderer
                if self._config.enable_display:
                    self.logger.info("启动 DisplayRenderer...")
                    renderer_started = self._renderer.start()
                    
                    if not renderer_started:
                        raise RuntimeError("DisplayRenderer 启动失败")
                else:
                    self.logger.info("DisplayRenderer 已禁用（enable_display=False）")
                    renderer_started = True  # 未启用时视为成功
                
                # 4. 使用 AND 逻辑：两个子模块都成功才算成功
                if packager_started and renderer_started:
                    self._is_running = True
                    self.logger.info("DisplayManager 已成功启动")
                    return True
                else:
                    raise RuntimeError("子模块启动未完全成功")
                
            except Exception as e:
                # 5. 子模块启动失败时清理并抛出异常（需求 5.5）
                self.logger.error(
                    "DisplayManager 启动失败: %s",
                    e,
                    exc_info=True
                )
                # 清理已启动的子模块
                self.logger.info("清理已启动的子模块...")
                self.stop()
                # 重新抛出异常
                raise

    def stop(self, timeout: float = 5.0) -> bool:
        """停止显示模块
        
        停止流程：
        1. 幂等性检查：如果未运行则直接返回True
        2. 停止 DisplayRenderer（关闭窗口，停止线程）
        3. 停止 RenderPacketPackager（取消订阅，停止线程）
        4. 使用 AND 逻辑：两个子模块都成功停止才算成功
        5. 输出统计信息
        
        Args:
            timeout: 等待超时时间（秒）
            
        Returns:
            bool: 是否成功停止（两个子模块都成功才返回True）
            
        错误处理：
        - 停止超时时记录警告日志
        - 即使一个子模块失败，仍继续停止其他子模块
        """
        with self._running_lock:
            # 1. 幂等性检查
            if not self._is_running:
                self.logger.info("DisplayManager 未在运行")
                return True
            
            self.logger.info("正在停止 DisplayManager...")
            
            renderer_success = True
            packager_success = True
            
            # 2. 停止 DisplayRenderer
            if self._renderer is not None:
                self.logger.info("停止 DisplayRenderer...")
                try:
                    renderer_success = self._renderer.stop(timeout=timeout)
                    if not renderer_success:
                        self.logger.warning(
                            "DisplayRenderer 停止超时 (%.1f秒)",
                            timeout
                        )
                except Exception as e:
                    self.logger.error(
                        "停止 DisplayRenderer 时发生异常: %s",
                        e,
                        exc_info=True
                    )
                    renderer_success = False
            
            # 3. 停止 RenderPacketPackager
            if self._packager is not None:
                self.logger.info("停止 RenderPacketPackager...")
                try:
                    packager_success = self._packager.stop(timeout=timeout)
                    if not packager_success:
                        self.logger.warning(
                            "RenderPacketPackager 停止超时 (%.1f秒)",
                            timeout
                        )
                except Exception as e:
                    self.logger.error(
                        "停止 RenderPacketPackager 时发生异常: %s",
                        e,
                        exc_info=True
                    )
                    packager_success = False
            
            # 4. 使用 AND 逻辑：两个子模块都成功才算成功
            success = renderer_success and packager_success
            
            # 5. 清理状态（只在成功时执行）
            if success:
                self._is_running = False
            
            # 6. 输出统计信息
            try:
                stats = self.get_stats()
                self.logger.info(
                    "DisplayManager 已停止，统计数据: %s",
                    stats
                )
            except Exception as e:
                self.logger.error(
                    "获取统计信息时发生异常: %s",
                    e,
                    exc_info=True
                )
            
            if success:
                self.logger.info("DisplayManager 已成功停止")
            else:
                self.logger.warning("DisplayManager 停止未完全成功")
            
            return success

    def get_stats(self) -> dict:
        """获取统计信息（需求 13.1, 13.2）
        
        聚合 RenderPacketPackager 和 DisplayRenderer 的统计信息。
        包含队列使用率监控（需求 12.3, 13.2）。
        
        Returns:
            dict: 包含两个子模块的统计信息
                - packager: RenderPacketPackager 的统计信息
                    - render_packets: 成功配对的渲染包数量
                    - drops: 配对超时丢弃的数据包数量
                - renderer: DisplayRenderer 的统计信息
                    - frames_rendered: 总渲染帧数
                    - fps: 当前FPS
                    - fps_history: FPS历史记录
                    - avg_fps: 平均FPS
                    - min_fps: 最小FPS
                    - max_fps: 最大FPS
                    - runtime_sec: 运行时长
                    - is_running: 是否正在运行
                - queue_stats: 队列使用率统计（需求 12.3）
                    - {device_id}: 每个设备的队列统计
                        - size: 当前队列大小
                        - maxsize: 队列最大容量
                        - usage_ratio: 使用率（0.0-1.0）
                        - drop_count: 队列溢出丢弃的数据包数量
                - total_queue_drops: 所有队列的总丢弃数量
                - total_drops: 总丢弃数量（配对超时 + 队列溢出）
        """
        stats = {}
        
        # 聚合 RenderPacketPackager 的统计信息（需求 13.4）
        if self._packager is not None:
            # 线程安全地读取统计数据（需求 13.4）
            with self._packager._stats_lock:
                packager_drops = self._packager._stats["drops"]
                render_packets = self._packager._stats["render_packets"]
            
            stats["packager"] = {
                "render_packets": render_packets,
                "drops": packager_drops,
            }
            
            # 添加队列使用率统计（需求 12.3, 13.2）
            queue_stats = {}
            total_queue_drops = 0
            high_usage_devices = []
            
            for device_id, queue in self._packager.packet_queue.items():
                qsize = queue.qsize()
                maxsize = queue.maxsize
                usage_ratio = qsize / maxsize if maxsize > 0 else 0.0
                drop_count = queue.get_drop_count()
                
                queue_stats[device_id] = {
                    "size": qsize,
                    "maxsize": maxsize,
                    "usage_ratio": usage_ratio,
                    "drop_count": drop_count,
                }
                
                total_queue_drops += drop_count
                
                # 检测高使用率（需求 12.3）
                if usage_ratio > 0.8:  # 80% 阈值
                    high_usage_devices.append(device_id)
            
            stats["queue_stats"] = queue_stats
            stats["total_queue_drops"] = total_queue_drops
            stats["total_drops"] = packager_drops + total_queue_drops  # 总丢弃数量（需求 13.2）
            
            # 如果队列使用率过高，记录警告日志（需求 12.3）
            if high_usage_devices:
                self.logger.warning(
                    "检测到高队列使用率的设备: %s",
                    ", ".join(high_usage_devices)
                )
        
        # 聚合 DisplayRenderer 的统计信息
        if self._renderer is not None:
            stats["renderer"] = self._renderer.get_stats()
        
        return stats

    @property
    def is_running(self) -> bool:
        """检查是否正在运行
        
        使用内部状态标志判断，确保线程安全。
        
        Returns:
            bool: 是否正在运行
        """
        with self._running_lock:
            return self._is_running
