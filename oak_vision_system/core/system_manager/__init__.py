"""
SystemManager 模块

提供系统级别的模块生命周期管理功能。

该模块是 OAK 视觉检测系统的核心基础设施，负责统一管理所有功能模块的生命周期，
提供清晰的启动/运行/关闭机制，确保系统能够优雅地启动和退出。

核心组件：
    - SystemManager: 系统管理器主类，负责模块生命周期管理
    - ModuleState: 模块状态枚举（NOT_STARTED, RUNNING, STOPPED, ERROR）
    - ManagedModule: 被管理的模块包装类，封装模块实例及其管理信息
    - ShutdownEvent: 系统停止事件，用于触发系统关闭

核心设计原则：
    - 简洁性：事件回调只做"置位"，不执行复杂操作
    - 统一退出点：所有退出路径汇聚到 finally 块
    - 防重复执行：使用 Event 防止多次关闭
    - 职责分离：回调负责"发信号"，run() 负责"执行关闭"

主要功能：
    1. 模块注册和管理
    2. 按优先级启动（下游→上游）和关闭（上游→下游）
    3. 启动失败自动回滚
    4. 两个明确的退出出口（KeyboardInterrupt 和 SYSTEM_SHUTDOWN 事件）
    5. 统一的关闭流程
    6. 防重复关闭机制
    7. 事件总线集成
    8. 日志系统初始化
    9. 异常日志记录

使用示例：
    >>> from oak_vision_system.core.system_manager import SystemManager
    >>> 
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
    
    使用上下文管理器：
    >>> with SystemManager(system_config=config) as manager:
    ...     manager.register_module("collector", collector, priority=10)
    ...     manager.register_module("processor", processor, priority=30)
    ...     manager.register_module("display", display, priority=50)
    ...     manager.run()
    # 自动调用 shutdown()

优先级说明：
    - 数字越大表示越靠近下游（消费者）
    - 数字越小表示越靠近上游（生产者）
    - 启动时从高到低（下游→上游）
    - 关闭时从低到高（上游→下游）
    - 建议值：显示=50，处理器=30，数据源=10

退出机制：
    SystemManager 提供两个明确的退出出口：
    1. KeyboardInterrupt（Ctrl+C）：用户手动中断
    2. SYSTEM_SHUTDOWN 事件：模块触发的系统关闭
    
    两个出口都会汇聚到 finally 块，统一调用 shutdown() 方法，
    确保所有模块按正确顺序关闭，资源得到正确释放。

版本信息：
    - 版本：简化版
    - 状态：稳定
    - 代码量：约 200 行（不含测试）
"""

from .data_structures import ModuleState, ManagedModule, ShutdownEvent
from .system_manager import SystemManager

__all__ = [
    "ModuleState",
    "ManagedModule",
    "ShutdownEvent",
    "SystemManager",
]
