"""exception_logger.py
将未捕获异常（主线程/子线程）记录到你传入的 logger。
不修改 root logger，不调用 basicConfig。

典型用法（在程序入口处调用）：
    import logging
    from oak_vision_system.utils.exception_logger import setup_exception_logger

    # 方式1：使用便捷函数，自动创建子logger
    handle = setup_exception_logger("myapp.exceptions")

    # 方式2：使用自定义logger
    from oak_vision_system.utils.exception_logger import attach_exception_logger
    mylog = logging.getLogger("myapp.errors")
    mylog.setLevel(logging.ERROR)
    # 添加你自己的 handler/formatter
    # mylog.addHandler(...)
    handle = attach_exception_logger(mylog, handle_threads=True)

    # ... 运行你的程序
    # handle.detach()  # 可选：卸载钩子
"""

from __future__ import annotations
import sys
import logging
import os
import threading
from dataclasses import dataclass
from types import TracebackType
from typing import Optional, Callable, Any
from oak_vision_system.core.dto.config_dto import SystemConfigDTO
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

_LOGGING_CONFIGURED = False
_LOGGING_CONFIG_LOCK = threading.Lock()


@dataclass
class _HookHandle:
    """返回的句柄，可卸载钩子；也可作为上下文管理器使用。"""
    logger: logging.Logger
    prev_sys_hook: Callable[[type, BaseException, TracebackType], Any]
    prev_thread_hook: Optional[Callable[[threading.ExceptHookArgs], Any]]

    def detach(self) -> None:
        """卸载已安装的异常钩子，恢复为挂载前的状态。"""
        sys.excepthook = self.prev_sys_hook
        if hasattr(threading, "excepthook") and self.prev_thread_hook is not None:
            threading.excepthook = self.prev_thread_hook  # type: ignore[attr-defined]

    # 作为上下文管理器使用
    def __enter__(self):
        """作为上下文管理器进入时，返回句柄自身以便链式调用。"""
        return self

    def __exit__(self, exc_type, exc, tb):
        """退出上下文时自动卸载钩子；返回 False 以确保异常继续向上传播。"""
        self.detach()
        # 不吞异常，交回原流程
        return False


def attach_exception_logger(
    logger: logging.Logger,
    *,
    handle_threads: bool = True,
    ignore_keyboard_interrupt: bool = True,
) -> _HookHandle:
    """
    将未捕获异常写入传入的 logger。
    - logger: 你自定义并配置好的 logger（自带 handler/formatter/level）
    - handle_threads: 是否捕获子线程未处理异常（3.8+）
    - ignore_keyboard_interrupt: 是否忽略 Ctrl+C（默认忽略）

    返回值：_HookHandle，可调用 .detach() 卸载；或用于 with 上下文。
    """

    if not isinstance(logger, logging.Logger):
        raise TypeError("logger must be an instance of logging.Logger")


    # ---- 主线程：sys.excepthook ----
    prev_sys_hook = sys.excepthook

    def _sys_hook(exc_type, exc_value, exc_tb):
        # 如果是 KeyboardInterrupt 且忽略，则直接返回，使用默认 hook 处理
        if ignore_keyboard_interrupt and issubclass(exc_type, KeyboardInterrupt):
            return prev_sys_hook(exc_type, exc_value, exc_tb)
        # 否则记录未捕获的异常
        logger.error("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))

        # 继续调用之前的 hook，保持与其他集成的兼容
        try:
            return prev_sys_hook(exc_type, exc_value, exc_tb)
        except Exception as e:
            # 上游 hook 抛错不影响本记录，但记录警告
            logger.debug(f"上游 sys.excepthook 执行出错：{e}")
    # 替换默认的 sys.excepthook
    sys.excepthook = _sys_hook

    # ---- 子线程：threading.excepthook ----
    prev_thread_hook = None
    if handle_threads and hasattr(threading, "excepthook"):
        prev_thread_hook = threading.excepthook  # type: ignore[attr-defined]

        def _thread_hook(args: "threading.ExceptHookArgs"):
            logger.error(
                "线程 %s 中发生未捕获异常", getattr(args.thread, "name", "<unknown>"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            # 同样保持与之前 hook 的兼容
            if prev_thread_hook is not None:
                try:
                    prev_thread_hook(args)  # type: ignore[misc]
                except Exception as e:
                    logger.debug(f"上游 threading.excepthook 执行出错：{e}")

        threading.excepthook = _thread_hook  # type: ignore[attr-defined]


    return _HookHandle(
        logger=logger,
        prev_sys_hook=prev_sys_hook,
        prev_thread_hook=prev_thread_hook,
    )


def setup_exception_logger(
    name: str,
    *,
    level: int = logging.ERROR,
    handle_threads: bool = True,
    ignore_keyboard_interrupt: bool = True,
    handler: Optional[logging.Handler] = None,
) -> _HookHandle:
    """
    便捷初始化：创建/获取子 logger，并挂载未捕获异常记录。

    - name: 子 logger 名称，例如 "myapp.exceptions"
    - level: 该 logger 的日志级别，默认 ERROR
    - handler: 可选，若提供则添加到该 logger（不会修改 root logger）
    其余参数转交给 attach_exception_logger。
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if handler is not None and handler not in logger.handlers:
        logger.addHandler(handler)
    return attach_exception_logger(
        logger,
        handle_threads=handle_threads,
        ignore_keyboard_interrupt=ignore_keyboard_interrupt,
    )


def configure_logging(system_config: SystemConfigDTO) -> None:
        """
        使用系统配置全局初始化日志模块
        
        功能说明：
        - 根据 system_config 中的日志配置，初始化 root logger 的级别和 handlers
        - 确保只初始化一次（通过全局标志 _LOGGING_CONFIGURED 控制）
        - 自动添加控制台输出 handler（如果不存在）
        - 可选添加文件日志 handler（根据配置决定）
        
        Args:
            system_config: 系统配置对象，包含日志级别、文件路径等配置信息
        
        Note:
            - 此函数会修改全局 root logger，影响整个应用的日志行为
            - 多次调用时，只有第一次会生效，后续调用会被忽略
        """
        try:
            global _LOGGING_CONFIGURED
            if _LOGGING_CONFIGURED:
                return
            with _LOGGING_CONFIG_LOCK:
                if _LOGGING_CONFIGURED:
                    return

                # 2. 解析日志级别并规范化
                raw_level = getattr(system_config, "log_level", "INFO")
                log_level_str = (str(raw_level).strip().upper() if raw_level is not None else "INFO")
                # 日志级别字符串到 logging 模块常量的映射
                level_map = {
                    "DEBUG": logging.DEBUG,
                    "INFO": logging.INFO,
                    "WARNING": logging.WARNING,
                    "ERROR": logging.ERROR,
                    "CRITICAL": logging.CRITICAL,
                }
                level = level_map.get(log_level_str)
                invalid_level = level is None
                if invalid_level:
                    level = logging.INFO

                # 3. 配置 root logger 的级别
                root = logging.getLogger()
                root.setLevel(level)

                # 4. 定义日志格式：时间戳、级别、logger名称、消息内容
                fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                datefmt = "%Y-%m-%d %H:%M:%S"

                # 5. 检查并添加控制台输出 handler（如果不存在）
                # 使用 type() 进行精确类型匹配，只识别 StreamHandler 本身，不包括子类
                has_stream = any(type(h) is logging.StreamHandler for h in root.handlers)
                if not has_stream:
                    ch = logging.StreamHandler()
                    ch.setFormatter(logging.Formatter(fmt, datefmt))
                    root.addHandler(ch)

                # 无效级别在 handler 就绪后警告一次
                if invalid_level:
                    root.warning(f"无效的日志级别: {raw_level!r}，已回退为 INFO")

                # 6. 可选：配置文件日志 handler（如果配置中启用了文件日志）
                if getattr(system_config, "log_to_file", False) and getattr(system_config, "log_file_path", None):
                    # 6.1 获取并归一化日志文件绝对路径，确保目录存在
                    path = os.path.abspath(system_config.log_file_path)
                    path_cmp = os.path.normcase(path)
                    dir_ = os.path.dirname(path)
                    if dir_:
                        os.makedirs(dir_, exist_ok=True)
                    
                    # 6.2 读取滚动模式并检查是否已存在对应 handler，避免重复添加
                    rotate_mode = str(getattr(system_config, "log_rotate_mode", "time") or "time").strip().lower()
                    exists_same = False
                    if rotate_mode == "size":
                        for h in root.handlers:
                            if type(h) is RotatingFileHandler:
                                base = getattr(h, "baseFilename", None)
                                if base and os.path.normcase(os.path.abspath(base)) == path_cmp:
                                    exists_same = True
                                    break
                    else:
                        for h in root.handlers:
                            if type(h) is TimedRotatingFileHandler:
                                base = getattr(h, "baseFilename", None)
                                if base and os.path.normcase(os.path.abspath(base)) == path_cmp:
                                    exists_same = True
                                    break
                    
                    # 6.3 如果不存在相同路径的 handler，则按模式创建
                    if not exists_same:
                        DEFAULT_BACKUP = 7
                        backup_count = getattr(system_config, "log_backup_count", DEFAULT_BACKUP)
                        try:
                            backup_count = int(backup_count)
                        except Exception:
                            backup_count = DEFAULT_BACKUP
                        if backup_count < 1:
                            backup_count = DEFAULT_BACKUP

                        if rotate_mode == "size":
                            # 按大小滚动（向后兼容）
                            DEFAULT_MAX_MB = 100
                            MAX_ALLOWED_MB = 1000
                            size_mb = getattr(system_config, "log_max_size_mb", DEFAULT_MAX_MB)
                            try:
                                size_mb = int(size_mb)
                            except Exception:
                                size_mb = DEFAULT_MAX_MB
                            if size_mb <= 0:
                                size_mb = DEFAULT_MAX_MB
                            if size_mb > MAX_ALLOWED_MB:
                                size_mb = MAX_ALLOWED_MB

                            fh = RotatingFileHandler(
                                path,
                                maxBytes=size_mb * 1024 * 1024,
                                backupCount=backup_count,
                                encoding="utf-8",
                            )
                        else:
                            # 按时间滚动（默认：每天午夜）
                            when = str(getattr(system_config, "log_rotate_when", "MIDNIGHT") or "MIDNIGHT").strip().upper()
                            interval = getattr(system_config, "log_rotate_interval", 1)
                            try:
                                interval = int(interval)
                            except Exception:
                                interval = 1
                            if interval < 1:
                                interval = 1
                            utc = bool(getattr(system_config, "log_rotate_utc", False))

                            fh = TimedRotatingFileHandler(
                                filename=path,
                                when=when,
                                interval=interval,
                                backupCount=backup_count,
                                encoding="utf-8",
                                utc=utc,
                            )
                        fh.setFormatter(logging.Formatter(fmt, datefmt))
                        root.addHandler(fh)

                # 7. 标记配置完成，并记录配置信息（仅在 DEBUG 级别下）
                _LOGGING_CONFIGURED = True
                if root.isEnabledFor(logging.DEBUG):
                    root.debug(f"日志级别设置为 {log_level_str}")
        except Exception as e:
            # 8. 异常处理：配置失败时记录错误，但不中断程序执行
            logging.getLogger(__name__).error(f"配置日志级别时出错: {e}", exc_info=True)