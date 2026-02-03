"""
SystemManager 数据结构模块

定义系统管理器使用的核心数据结构：
- ModuleState: 模块状态枚举
- ManagedModule: 被管理的模块包装类
- ShutdownEvent: 系统停止事件
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ModuleState(Enum):
    """
    模块状态枚举
    
    定义模块在生命周期中的4个状态：
    - NOT_STARTED: 模块已注册但尚未启动
    - RUNNING: 模块正在运行中
    - STOPPED: 模块已正常停止
    - ERROR: 模块处于错误状态
    
    状态转换：
        NOT_STARTED → RUNNING → STOPPED
        任何阶段发生错误 → ERROR
    """
    NOT_STARTED = "not_started"  # 未启动
    RUNNING = "running"          # 运行中
    STOPPED = "stopped"          # 已停止
    ERROR = "error"              # 错误状态


@dataclass
class ManagedModule:
    """
    被管理的模块包装类
    
    封装模块实例及其管理信息，用于 SystemManager 统一管理。
    
    Attributes:
        name: 模块名称，作为唯一标识符
        instance: 模块实例，必须实现 start() 和 stop() 方法
        priority: 模块优先级，数字越大表示越靠近下游（消费者）
                 启动时从高到低（下游→上游），关闭时从低到高（上游→下游）
        state: 模块当前状态
    
    优先级示例：
        - 显示模块: 50 (下游，消费者)
        - 数据处理器: 30 (中游)
        - 数据采集器: 10 (上游，生产者)
    """
    name: str
    instance: Any
    priority: int
    state: ModuleState


@dataclass
class ShutdownEvent:
    """
    系统停止事件
    
    用于通知 SystemManager 系统需要关闭。
    通常由显示模块或其他模块发布到事件总线。
    
    Attributes:
        reason: 停止原因字符串，用于日志记录和调试
               常见值: "user_quit", "window_closed", "key_q" 等
    
    Example:
        >>> event = ShutdownEvent(reason="user_quit")
        >>> event_bus.publish("SYSTEM_SHUTDOWN", event)
    """
    reason: str
