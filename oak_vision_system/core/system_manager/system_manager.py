"""
SystemManager 模块

提供系统级别的模块生命周期管理功能。
负责统一管理所有功能模块的启动、运行和关闭流程。
"""

import logging
import threading
from typing import Any, Dict, Optional
from typing_extensions import Literal

from oak_vision_system.core.dto.config_dto import SystemConfigDTO
from oak_vision_system.core.event_bus import EventBus, get_event_bus
from oak_vision_system.utils.logging_utils import (
    configure_logging,
    attach_exception_logger,
    _HookHandle,
)
from .data_structures import ModuleState, ManagedModule, ShutdownEvent


class SystemManager:
    """
    系统管理器（简化版）
    
    负责统一管理所有功能模块的生命周期，提供清晰的启动/运行/关闭机制。
    
    核心设计原则：
    - 简洁性：事件回调只做"置位"，不执行复杂操作
    - 统一退出点：所有退出路径汇聚到 finally 块
    - 防重复执行：使用 Event 防止多次关闭
    - 职责分离：回调负责"发信号"，run() 负责"执行关闭"
    
    核心职责：
    1. 模块管理：注册、存储模块信息
    2. 优先级调度：按优先级启动（下游→上游）和关闭（上游→下游）
    3. 启动失败回滚：启动失败时自动回滚已启动的模块
    4. 两个退出出口：KeyboardInterrupt 和 SYSTEM_SHUTDOWN 事件
    5. 统一关闭流程：确保所有模块按正确顺序关闭
    
    使用示例：
        >>> # 创建管理器
        >>> manager = SystemManager(system_config=config)
        >>> 
        >>> # 注册模块（按优先级）
        >>> manager.register_module("collector", collector, priority=10)
        >>> manager.register_module("processor", processor, priority=30)
        >>> manager.register_module("display", display, priority=50)
        >>> 
        >>> # 启动所有模块
        >>> manager.start_all()  # 按优先级 50→30→10 启动
        >>> 
        >>> # 运行主循环（阻塞）
        >>> manager.run()  # 等待 Ctrl+C 或 SYSTEM_SHUTDOWN 事件
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        system_config: Optional[SystemConfigDTO] = None,
        default_stop_timeout: float = 5.0,
        force_exit_grace_period: float = 3.0
    ):
        """
        初始化 SystemManager
        
        Args:
            event_bus: 事件总线实例（可选，默认使用全局单例）
            system_config: 系统配置对象（可选，用于日志初始化）
            default_stop_timeout: 默认模块关闭超时时间（秒），默认5.0秒
            force_exit_grace_period: 强制退出宽限期（秒），默认3.0秒
                当模块停止失败时，等待此时间后强制退出进程。
                此参数用于兜底机制，确保系统能够可靠退出。
        
        Raises:
            ValueError: 如果 default_stop_timeout 小于等于 0
            ValueError: 如果 force_exit_grace_period 小于等于 0
        """
        # 验证参数
        if default_stop_timeout <= 0:
            raise ValueError(f"default_stop_timeout 必须大于 0，当前值: {default_stop_timeout}")
        
        if force_exit_grace_period <= 0:
            raise ValueError(f"force_exit_grace_period 必须大于 0，当前值: {force_exit_grace_period}")
        
        # 初始化日志系统（如果提供 system_config）
        if system_config is not None:
            try:
                configure_logging(system_config)
            except Exception as e:
                # 如果日志配置失败，使用默认配置并记录警告
                logging.basicConfig(level=logging.INFO)
                logging.warning(f"日志配置失败，使用默认配置: {e}")
        
        # 创建 logger 实例
        self._logger = logging.getLogger(__name__)
        
        # 初始化事件总线（使用提供的实例或全局单例）
        self._event_bus = event_bus if event_bus is not None else get_event_bus()
        
        # 保存配置参数
        self._default_stop_timeout = default_stop_timeout
        self._force_exit_grace_period = force_exit_grace_period
        
        # 初始化内部数据结构
        self._modules: Dict[str, ManagedModule] = {}  # 模块名称 -> ManagedModule
        self._shutdown_event = threading.Event()      # 退出信号
        self._stop_started = threading.Event()        # 防重复关闭标志
        self._display_module: Optional[Any] = None   # 显示模块引用（需要主线程渲染）
        
        # 异常钩子句柄（稍后初始化）
        self._exception_handle: Optional[_HookHandle] = None
        
        # 订阅 SYSTEM_SHUTDOWN 事件
        self._event_bus.subscribe(
            "SYSTEM_SHUTDOWN",
            self._on_shutdown_event,
            subscriber_name="SystemManager"
        )
        
        # 安装异常钩子：只用于记录日志，不触发退出
        exception_logger = logging.getLogger(f"{__name__}.exceptions")
        self._exception_handle = attach_exception_logger(
            exception_logger,
            handle_threads=True,
            ignore_keyboard_interrupt=True  # 忽略 KeyboardInterrupt
        )
        
        # 记录初始化信息
        self._logger.info(
            "SystemManager 初始化完成: default_stop_timeout=%.1fs, force_exit_grace_period=%.1fs",
            default_stop_timeout,
            force_exit_grace_period
        )
        self._logger.debug(
            "SystemManager 配置: event_bus=%s, system_config=%s",
            "custom" if event_bus is not None else "global",
            "provided" if system_config is not None else "none"
        )
    
    # ==================== 模块管理 ====================
    
    def register_module(self, name: str, instance: Any, priority: int) -> None:
        """
        注册模块
        
        将模块注册到 SystemManager 进行统一管理。
        模块必须实现 start() 和 stop() 方法。
        
        Args:
            name: 模块名称（唯一标识）
            instance: 模块实例（必须有 start() 和 stop() 方法）
            priority: 优先级（数字越大越靠近下游）
                     启动时从高到低（下游→上游），关闭时从低到高（上游→下游）
                     建议值：显示=50，处理器=30，数据源=10
        
        Raises:
            ValueError: 如果模块名称已存在
        
        Example:
            >>> manager.register_module("collector", collector, priority=10)
            >>> manager.register_module("processor", processor, priority=30)
            >>> manager.register_module("display", display, priority=50)
        """
        # 检查模块名称是否已存在
        if name in self._modules:
            raise ValueError(f"模块名称已存在: {name}")
        
        # 创建 ManagedModule 对象（初始状态为 NOT_STARTED）
        managed_module = ManagedModule(
            name=name,
            instance=instance,
            priority=priority,
            state=ModuleState.NOT_STARTED
        )
        
        # 存储到 _modules 字典
        self._modules[name] = managed_module
        
        # 记录注册日志
        self._logger.info(
            f"注册模块: {name} (priority={priority}, state={ModuleState.NOT_STARTED.value})"
        )
    
    def register_display_module(self, name: str, instance: Any, priority: int) -> None:
        """
        注册显示模块（需要主线程渲染）
        
        显示模块需要特殊处理，因为 OpenCV 窗口操作必须在主线程中执行。
        此方法会：
        1. 将模块注册到常规模块列表（用于 start/stop 管理）
        2. 存储到 _display_module 属性（用于主循环渲染）
        
        Args:
            name: 模块名称（唯一标识）
            instance: DisplayManager 实例（必须有 start(), stop(), render_once() 方法）
            priority: 优先级（数字越大越靠近下游）
                     建议值：显示=50
        
        Raises:
            ValueError: 如果模块名称已存在
            ValueError: 如果已经注册了其他显示模块
        
        Example:
            >>> manager.register_display_module("display", display_manager, priority=50)
        
        需求: 3.1, 3.2
        """
        # 检查是否已经注册了显示模块
        if self._display_module is not None:
            raise ValueError(
                f"已经注册了显示模块，不能重复注册。"
                f"当前显示模块: {self._display_module}"
            )
        
        # 调用常规注册方法（用于 start/stop 管理）
        self.register_module(name, instance, priority)
        
        # 存储到 _display_module 属性（用于主循环渲染）
        self._display_module = instance
        
        # 记录注册日志，标记该模块需要主线程渲染
        self._logger.info(
            f"注册显示模块: {name} (priority={priority}, 需要主线程渲染)"
        )
    
    def start_all(self) -> None:
        """
        启动所有注册的模块
        
        按优先级从高到低启动模块（下游→上游）。
        如果任何模块启动失败，触发回滚机制，停止所有已启动的模块。
        
        启动顺序示例：
            Display(50) → Processor(30) → Collector(10)
        
        Raises:
            RuntimeError: 如果任何模块启动失败
        
        Example:
            >>> manager.register_module("collector", collector, priority=10)
            >>> manager.register_module("processor", processor, priority=30)
            >>> manager.register_module("display", display, priority=50)
            >>> manager.start_all()  # 按 50→30→10 顺序启动
        """
        self._logger.info("开始启动所有模块...")
        
        # 按优先级降序排序模块（优先级高的先启动）
        sorted_modules = sorted(
            self._modules.values(),
            key=lambda m: m.priority,
            reverse=True  # 降序：优先级高的先启动
        )
        
        # 记录启动顺序
        startup_order = " → ".join([f"{m.name}({m.priority})" for m in sorted_modules])
        self._logger.debug(f"启动顺序: {startup_order}")
        
        # 跟踪已启动的模块（用于回滚）
        started_modules = []
        
        try:
            # 遍历模块并启动
            for module in sorted_modules:
                self._logger.info(f"启动模块: {module.name} (priority={module.priority})")
                
                # 调用模块的 start() 方法
                ret = module.instance.start()
                
                # 检查返回值：如果返回 False，表示启动失败（兜底语义）
                if ret is False:
                    self._logger.error(
                        f"模块启动失败（返回 False）: {module.name}"
                    )
                    # 设置失败模块状态为 ERROR
                    module.state = ModuleState.ERROR
                    # 触发回滚
                    self._rollback_startup(started_modules)
                    # 抛出异常
                    raise RuntimeError(
                        f"模块启动失败: {module.name} (返回 False)"
                    )
                
                # 设置状态为 RUNNING
                module.state = ModuleState.RUNNING
                
                # 记录到已启动列表
                started_modules.append(module)
                
                self._logger.info(f"模块启动成功: {module.name}")
            
            self._logger.info(f"所有模块启动完成，共 {len(started_modules)} 个模块")
        
        except Exception as e:
            # 启动失败：记录错误
            failed_module = sorted_modules[len(started_modules)]
            self._logger.error(
                f"模块启动失败: {failed_module.name}, 错误: {e}",
                exc_info=True
            )
            
            # 设置失败模块状态为 ERROR
            failed_module.state = ModuleState.ERROR
            
            # 调用回滚：停止所有已启动的模块
            self._rollback_startup(started_modules)
            
            # 重新抛出原始异常
            raise RuntimeError(
                f"模块启动失败: {failed_module.name}"
            ) from e
    
    def _rollback_startup(self, started_modules: list) -> None:
        """
        回滚启动：停止所有已启动的模块
        
        在模块启动失败时调用，按相反顺序停止已启动的模块。
        即使某个模块停止失败，也会继续停止其他模块。
        
        Args:
            started_modules: 已启动的模块列表（ManagedModule 对象）
        """
        if not started_modules:
            self._logger.debug("没有需要回滚的模块")
            return
        
        self._logger.warning(f"开始回滚启动，停止 {len(started_modules)} 个已启动的模块...")
        
        # 按相反顺序遍历已启动的模块
        for module in reversed(started_modules):
            try:
                self._logger.info(f"回滚停止模块: {module.name}")
                
                # 调用模块的 stop() 方法
                stop_result = module.instance.stop()
                
                # 检查返回值（如果返回 False，表示停止失败）
                if stop_result is False:
                    self._logger.error(
                        f"回滚停止模块失败（返回 False）: {module.name}"
                    )
                    # 设置状态为 ERROR
                    module.state = ModuleState.ERROR
                else:
                    # 设置状态为 STOPPED
                    module.state = ModuleState.STOPPED
                    self._logger.info(f"模块回滚停止成功: {module.name}")
            
            except Exception as stop_err:
                # 捕获异常并记录错误（不抛出，继续停止其他模块）
                self._logger.error(
                    f"回滚停止模块失败（抛出异常）: {module.name}, 错误: {stop_err}",
                    exc_info=True
                )
                
                # 设置状态为 ERROR
                module.state = ModuleState.ERROR
        
        self._logger.warning("启动回滚完成")
    
    # ==================== 事件处理 ====================
    
    def _on_shutdown_event(self, event: ShutdownEvent) -> None:
        """
        处理 SYSTEM_SHUTDOWN 事件
        
        只做一件事：设置 _shutdown_event 标志
        不执行复杂操作，避免在回调线程中产生死锁或竞态条件
        
        Args:
            event: 系统停止事件，包含停止原因
        """
        reason = getattr(event, 'reason', 'unknown')
        self._logger.info(f"接收到退出事件: {reason}")
        self._shutdown_event.set()  # 只做置位操作
    
    # ==================== 主循环和退出 ====================
    
    def run(self, force_exit_on_shutdown_failure: bool = True) -> None:
        """
        运行系统并阻塞主线程
        
        三个退出出口：
        1. KeyboardInterrupt（Ctrl+C）- except 块捕获
        2. SYSTEM_SHUTDOWN 事件 - 设置 _shutdown_event
        3. 用户按 'q' 键 - render_once() 返回 True
        
        主线程渲染支持：
        - 如果注册了显示模块，主循环会调用 display_module.render_once()
        - render_once() 返回 True 时触发系统关闭
        
        退出流程设计：
        - 所有退出路径都设置 _shutdown_event（保持状态一致性）
        - 统一在 finally 块中调用 shutdown() 清理资源
        - 使用 _stop_started 防止重复关闭
        
        退出流程：
            - 出口1：用户按 Ctrl+C → 设置 _shutdown_event → except KeyboardInterrupt → finally → shutdown()
            - 出口2：SYSTEM_SHUTDOWN 事件 → _shutdown_event.set() → while 循环退出 → finally → shutdown()
            - 出口3：用户按 'q' 键 → render_once() 返回 True → _shutdown_event.set() → finally → shutdown()

        强退策略：
            - shutdown() 会返回 bool 表示是否所有模块都停止成功
            - 当 shutdown() 返回 False 且 force_exit_on_shutdown_failure=True 时，
              run() 会在宽限期后调用 os._exit(1) 强制退出进程

        Args:
            force_exit_on_shutdown_failure: 当模块停止失败时是否触发强制退出兜底机制。
                默认 True（生产环境保持强退兜底）。测试/开发环境可传 False 以便异常传播与断言。
        
        Example:
            >>> manager = SystemManager(system_config=config)
            >>> manager.register_module("collector", collector, priority=10)
            >>> manager.register_display_module("display", display_manager, priority=50)
            >>> manager.start_all()
            >>> manager.run()  # 阻塞主线程，等待退出信号
        
        需求: 2.1, 2.2, 2.3, 2.4
        """
        try:
            self._logger.info("SystemManager 开始运行，等待退出信号...")
            self._logger.info("退出方式: Ctrl+C 或 SYSTEM_SHUTDOWN 事件")
            
            # 获取注册的显示模块（如果有）
            display_module = self._display_module
            
            if display_module is not None:
                self._logger.info("检测到显示模块，使用主线程渲染模式")
            
            # 主循环：等待退出信号
            while not self._shutdown_event.is_set():
                # 如果有显示模块，调用 render_once()（主线程渲染）
                if display_module is not None:
                    try:
                        should_quit = display_module.render_once()
                        if should_quit:
                            # 出口3：用户按 'q' 键请求退出
                            self._logger.info("显示模块请求退出（用户按下 'q' 键）")
                            self._shutdown_event.set()
                            break
                    except Exception as e:
                        # 捕获渲染异常，记录日志但不中断主循环
                        self._logger.error(
                            "渲染过程中发生异常: %s",
                            e,
                            exc_info=True
                        )
                        # 继续运行，不退出
                else:
                    # 无显示模块，使用原有的等待逻辑
                    # 使用 Event.wait(timeout) 阻塞主线程，CPU 使用率接近 0%
                    self._shutdown_event.wait(timeout=0.5)
                # 出口2：SYSTEM_SHUTDOWN 事件设置 _shutdown_event
            
            # 正常退出：_shutdown_event 已被设置
            self._logger.info("接收到退出信号，准备关闭系统...")
        
        except KeyboardInterrupt:
            # 出口1：Ctrl+C
            # 关键设计：统一设置 _shutdown_event，保持状态一致性
            self._shutdown_event.set()
            self._logger.info("捕获到 KeyboardInterrupt (Ctrl+C)，准备关闭系统...")
        
        finally:
            # 统一退出点：三个出口都汇聚到这里
            # 检查 _stop_started 防止重复调用 shutdown()
            if not self._stop_started.is_set():
                self._logger.info("执行统一关闭流程...")
                shutdown_success = self.shutdown()

                if (not shutdown_success) and force_exit_on_shutdown_failure:
                    import os
                    import time

                    self._logger.critical(
                        f"触发兜底机制：等待 {self._force_exit_grace_period} 秒后强制退出进程"
                    )

                    # 等待宽限期（给日志系统时间刷新缓冲区）
                    time.sleep(self._force_exit_grace_period)

                    # 刷新日志缓冲区
                    try:
                        logging.shutdown()
                    except Exception as e:
                        # 忽略日志刷新失败
                        print(f"日志刷新失败: {e}", flush=True)

                    # 强制退出进程（退出码 1 表示模块停止失败）
                    self._logger.critical("强制退出进程 (exit code 1)")
                    os._exit(1)
            else:
                self._logger.debug("shutdown() 已经执行过，跳过")
    
    def shutdown(self) -> bool:
        """
        关闭系统
        
        流程：
        1. 检查 _stop_started 防止重复关闭
        2. 按优先级从低到高关闭模块（上游→下游）
        3. 停止失败时重试一次 stop()，并记录失败模块
        4. 关闭事件总线
        5. 恢复异常钩子
        
        兜底机制：
            shutdown() 只记录 stop() 失败模块并返回成功/失败布尔值，
            强制退出进程（os._exit(1)）由 run() 根据参数决定是否触发。

        Returns:
            bool: True 表示所有模块都成功停止（或已执行过 shutdown 被跳过）；
            False 表示至少有一个模块停止失败（失败模块会以 CRITICAL 日志记录）。
        """

        self._logger.info("开始关闭系统...")

        # 防重复关闭检查：检查 _stop_started，如果已设置则直接返回
        if self._stop_started.is_set():
            self._logger.debug("shutdown() 已经执行过，跳过")
            return True

        # 设置 _stop_started 标志
        self._stop_started.set()
        
        # 按优先级升序排序模块（优先级低的先关闭）
        sorted_modules = sorted(
            self._modules.values(),
            key=lambda m: m.priority  # 升序：优先级低的先关闭
        )
        
        # 记录关闭顺序
        if sorted_modules:
            shutdown_order = " → ".join([f"{m.name}({m.priority})" for m in sorted_modules])
            self._logger.debug(f"关闭顺序: {shutdown_order}")
        
        # 创建失败模块列表（用于跟踪停止失败的模块）
        failed_modules = []
        
        # 遍历模块并关闭
        for module in sorted_modules:
            # 跳过非 RUNNING 状态的模块
            if module.state != ModuleState.RUNNING:
                self._logger.debug(
                    f"跳过模块 {module.name}，状态为 {module.state.value}"
                )
                continue
            
            try:
                # 记录日志
                self._logger.info(f"停止模块: {module.name} (priority={module.priority})")
                
                # 调用 stop() 方法并检查返回值
                try:
                    stop_result = module.instance.stop(timeout=self._default_stop_timeout)
                except TypeError:
                    stop_result = module.instance.stop()
                
                # 检查返回值（如果返回 False，表示停止失败）
                if stop_result is False:
                    self._logger.error(f"模块停止失败（返回 False）: {module.name}，尝试重试 stop()")

                    try:
                        try:
                            retry_result = module.instance.stop(timeout=self._default_stop_timeout)
                        except TypeError:
                            retry_result = module.instance.stop()
                        if retry_result is False:
                            self._logger.error(
                                f"模块停止重试失败（返回 False）: {module.name}"
                            )
                            module.state = ModuleState.ERROR
                            failed_modules.append(module.name)
                        else:
                            module.state = ModuleState.STOPPED
                            self._logger.info(f"模块停止重试成功: {module.name}")
                    except Exception as retry_err:
                        self._logger.error(
                            f"模块停止重试失败（抛出异常）: {module.name}, 错误: {retry_err}",
                            exc_info=True
                        )
                        module.state = ModuleState.ERROR
                        failed_modules.append(module.name)
                else:
                    # 设置状态为 STOPPED
                    module.state = ModuleState.STOPPED
                    self._logger.info(f"模块停止成功: {module.name}")
            
            except Exception as e:
                # 捕获异常并记录错误（不抛出）
                self._logger.error(
                    f"停止模块失败（抛出异常）: {module.name}, 错误: {e}",
                    exc_info=True
                )

                self._logger.error(f"尝试重试 stop(): {module.name}")

                try:
                    try:
                        retry_result = module.instance.stop(timeout=self._default_stop_timeout)
                    except TypeError:
                        retry_result = module.instance.stop()
                    if retry_result is False:
                        self._logger.error(
                            f"模块停止重试失败（返回 False）: {module.name}"
                        )
                        module.state = ModuleState.ERROR
                        failed_modules.append(module.name)
                    else:
                        module.state = ModuleState.STOPPED
                        self._logger.info(f"模块停止重试成功: {module.name}")
                except Exception as retry_err:
                    self._logger.error(
                        f"模块停止重试失败（抛出异常）: {module.name}, 错误: {retry_err}",
                        exc_info=True
                    )
                    module.state = ModuleState.ERROR
                    failed_modules.append(module.name)
        
        # 关闭事件总线
        try:
            self._logger.info("关闭事件总线...")
            self._event_bus.close(wait=True, cancel_pending=False)
            self._logger.info("事件总线关闭成功")
        except Exception as e:
            # 捕获异常并记录错误（不抛出）
            self._logger.error(f"关闭事件总线失败: {e}", exc_info=True)
        
        # 恢复异常钩子
        try:
            if self._exception_handle is not None:
                self._logger.debug("恢复异常钩子...")
                self._exception_handle.detach()
                self._logger.debug("异常钩子恢复成功")
        except Exception as e:
            # 捕获异常并记录错误（不抛出）
            self._logger.error(f"恢复异常钩子失败: {e}", exc_info=True)
        
        # 检查是否有失败的模块（记录日志，但不在 shutdown() 内强退进程）
        if failed_modules:
            self._logger.critical(
                f"检测到 {len(failed_modules)} 个模块停止失败: {', '.join(failed_modules)}"
            )
        
        self._logger.info("SystemManager 关闭完成")
        return len(failed_modules) == 0
    
    # ==================== 状态查询 ====================
    
    def get_status(self) -> Dict[str, str]:
        """
        获取所有模块的状态
        
        返回一个字典，键为模块名称，值为状态字符串。
        状态字符串包括："not_started", "running", "stopped", "error"
        
        Returns:
            Dict[str, str]: 模块名称 -> 状态字符串的映射
        
        Example:
            >>> status = manager.get_status()
            >>> print(status)
            {'collector': 'running', 'processor': 'running', 'display': 'running'}
        """
        return {
            name: module.state.value
            for name, module in self._modules.items()
        }
    
    def is_shutting_down(self) -> bool:
        """
        检查系统是否正在关闭
        
        Returns:
            bool: 如果系统正在关闭返回 True，否则返回 False
        
        Example:
            >>> if manager.is_shutting_down():
            ...     print("系统正在关闭...")
        """
        return self._stop_started.is_set()
    
    # ==================== 上下文管理器 ====================
    
    def __enter__(self) -> "SystemManager":
        """
        进入 with 块时返回 self
        
        使 SystemManager 支持上下文管理器协议，可以使用 with 语句。
        注意：不再自动调用 start_all()，需要在 with 块中手动调用。
        
        这样设计的原因：
        - 如果在 __enter__() 中调用 start_all() 失败，__exit__() 不会被调用（Python 标准行为）
        - 手动调用可以确保即使 start_all() 失败，__exit__() 也会执行，从而调用 shutdown() 清理资源
        
        Returns:
            SystemManager: 返回 self，允许在 with 语句中使用 as 子句
        
        Example:
            >>> with SystemManager(system_config=config) as manager:
            ...     manager.register_module("collector", collector, priority=10)
            ...     manager.register_module("processor", processor, priority=30)
            ...     manager.register_module("display", display, priority=50)
            ...     manager.start_all()  # 手动调用
            ...     manager.run()
            # 自动调用 shutdown()
        """
        self._logger.debug("进入 with 块")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        """
        退出 with 块时自动调用 shutdown()
        
        无论 with 块是否发生异常，都会调用 shutdown() 确保资源清理。
        返回 False 表示不抑制异常，异常会继续向上传播。
        
        Args:
            exc_type: 异常类型（如果有异常）
            exc_val: 异常值（如果有异常）
            exc_tb: 异常回溯（如果有异常）
        
        Returns:
            Literal[False]: 返回 False，不抑制异常
        
        Example:
            >>> with SystemManager(system_config=config) as manager:
            ...     manager.register_module("collector", collector, priority=10)
            ...     manager.run()
            # 自动调用 shutdown()，即使发生异常也会执行
        """
        if exc_type is not None:
            self._logger.debug(
                f"退出 with 块（发生异常: {exc_type.__name__}），调用 shutdown()"
            )
        else:
            self._logger.debug("退出 with 块，调用 shutdown()")
        
        self.shutdown()
        return False  # 不抑制异常
