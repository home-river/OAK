"""
CAN 通信器工厂模块

提供统一的 CAN 通信器创建接口，根据配置自动选择真实或虚拟实现。

设计要点：
- 工厂模式：根据 config.enable_can 标志选择实现
- 统一接口：返回 CANCommunicatorBase 类型，确保接口一致性
- 延迟导入：避免循环导入和不必要的依赖
- 详细日志：记录创建过程和选择的实现类型
- 异常处理：提供清晰的错误信息和故障排除建议
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
    from oak_vision_system.modules.data_processing.decision_layer.decision_layer import DecisionLayer
    from oak_vision_system.core.event_bus.event_bus import EventBus
    from .can_communicator_base import CANCommunicatorBase

logger = logging.getLogger(__name__)


def create_can_communicator(
    config: 'CANConfigDTO',
    decision_layer: 'DecisionLayer',
    event_bus: 'EventBus'
) -> 'CANCommunicatorBase':
    """
    创建 CAN 通信器实例
    
    根据配置中的 enable_can 标志自动选择合适的实现：
    - enable_can=True: 创建真实 CAN 通信器 (CANCommunicator)
    - enable_can=False: 创建虚拟 CAN 通信器 (VirtualCANCommunicator)
    
    Args:
        config: CAN 配置 DTO，包含所有配置参数
            - enable_can: bool - 是否启用真实 CAN 通信
            - 其他 CAN 相关配置参数
        decision_layer: 决策层实例，用于获取目标坐标
        event_bus: 事件总线实例，用于订阅和发布事件
        
    Returns:
        CANCommunicatorBase: CAN 通信器实例
            - 如果 enable_can=True，返回 CANCommunicator 实例
            - 如果 enable_can=False，返回 VirtualCANCommunicator 实例
            
    Raises:
        ImportError: 如果无法导入所需的 CAN 通信器类
        RuntimeError: 如果创建 CAN 通信器实例失败
        
    使用示例:
        # 创建真实 CAN 通信器（生产环境）
        config = CANConfigDTO(
            enable_can=True,
            can_interface='socketcan',
            can_channel='can0',
            can_bitrate=250000
        )
        communicator = create_can_communicator(config, decision_layer, event_bus)
        
        # 创建虚拟 CAN 通信器（开发/测试环境）
        config = CANConfigDTO(
            enable_can=False,
            can_interface='socketcan',  # 虚拟实现中不使用，但保持配置完整性
            can_channel='can0',
            can_bitrate=250000
        )
        communicator = create_can_communicator(config, decision_layer, event_bus)
        
        # 统一的使用方式
        success = communicator.start()
        if success:
            print("CAN 通信器已启动")
            # ... 使用通信器
            communicator.stop()
        
    配置说明:
        enable_can 字段的含义：
        - True: 启用真实 CAN 通信
            * 适用于生产环境和有 CAN 硬件的测试环境
            * 需要实际的 CAN 接口和硬件支持
            * 会执行真实的 CAN 消息收发
            * Linux 系统下支持自动配置 CAN 接口
            
        - False: 启用虚拟 CAN 通信
            * 适用于开发环境和无硬件的测试场景
            * 不需要实际的 CAN 硬件
            * 模拟 CAN 通信行为，提供详细日志
            * 支持 Windows 等非 Linux 系统
            * 维护统计信息，便于调试和验证
            
    故障排除:
        如果遇到导入错误：
        1. 检查 python-can 库是否已安装（真实 CAN 通信需要）
        2. 检查系统是否支持所选的 CAN 接口类型
        3. 在 Linux 系统上检查 CAN 内核模块是否已加载
        
        如果遇到创建失败：
        1. 检查配置参数是否有效
        2. 检查 decision_layer 和 event_bus 是否已正确初始化
        3. 查看详细的错误日志获取更多信息
    """
    try:
        logger.info("=" * 60)
        logger.info("🏭 CAN 通信器工厂开始创建实例")
        logger.info("=" * 60)
        logger.info(f"📋 配置信息:")
        logger.info(f"  • enable_can: {config.enable_can}")
        logger.info(f"  • can_interface: {config.can_interface}")
        logger.info(f"  • can_channel: {config.can_channel}")
        logger.info(f"  • can_bitrate: {config.can_bitrate}")
        logger.info("")
        
        if config.enable_can:
            # 创建真实 CAN 通信器
            logger.info("🔧 enable_can=True，创建真实 CAN 通信器 (CANCommunicator)")
            logger.info("📦 正在导入 CANCommunicator...")
            
            try:
                from .can_communicator import CANCommunicator
                logger.info("✅ CANCommunicator 导入成功")
            except ImportError as e:
                logger.error(f"❌ 导入 CANCommunicator 失败: {e}")
                logger.error("💡 故障排除建议:")
                logger.error("  • 检查 python-can 库是否已安装: pip install python-can")
                logger.error("  • 检查系统是否支持所选的 CAN 接口类型")
                logger.error("  • 在 Linux 系统上检查 CAN 内核模块是否已加载")
                raise ImportError(f"无法导入 CANCommunicator: {e}") from e
            
            logger.info("🚀 正在创建 CANCommunicator 实例...")
            communicator = CANCommunicator(config, decision_layer, event_bus)
            
            logger.info("✅ CANCommunicator 实例创建成功")
            logger.info("🎯 适用场景:")
            logger.info("  • 生产环境")
            logger.info("  • 有 CAN 硬件的测试环境")
            logger.info("  • Linux 系统（支持自动配置）")
            logger.info("  • 需要真实 CAN 消息收发的场景")
            
        else:
            # 创建虚拟 CAN 通信器
            logger.info("🔧 enable_can=False，创建虚拟 CAN 通信器 (VirtualCANCommunicator)")
            logger.info("📦 正在导入 VirtualCANCommunicator...")
            
            try:
                from .virtual_can_communicator import VirtualCANCommunicator
                logger.info("✅ VirtualCANCommunicator 导入成功")
            except ImportError as e:
                logger.error(f"❌ 导入 VirtualCANCommunicator 失败: {e}")
                logger.error("💡 这通常不应该发生，因为虚拟实现没有外部依赖")
                raise ImportError(f"无法导入 VirtualCANCommunicator: {e}") from e
            
            logger.info("🚀 正在创建 VirtualCANCommunicator 实例...")
            communicator = VirtualCANCommunicator(config, decision_layer, event_bus)
            
            logger.info("✅ VirtualCANCommunicator 实例创建成功")
            logger.info("🎯 适用场景:")
            logger.info("  • 开发环境")
            logger.info("  • 无硬件的测试场景")
            logger.info("  • Windows 等非 Linux 系统")
            logger.info("  • 功能验证和调试")
            logger.info("  • 事件流测试")
        
        logger.info("")
        logger.info(f"🎉 CAN 通信器创建完成: {communicator.__class__.__name__}")
        logger.info("📝 接下来可以调用 communicator.start() 启动通信器")
        logger.info("=" * 60)
        
        return communicator
        
    except (ImportError, RuntimeError) as e:
        # 重新抛出已知异常，保持原始错误信息
        raise
    except Exception as e:
        # 捕获其他未预期的异常
        logger.error(f"❌ 创建 CAN 通信器时发生未预期的异常: {e}", exc_info=True)
        logger.error("💡 故障排除建议:")
        logger.error("  • 检查配置参数是否有效")
        logger.error("  • 检查 decision_layer 和 event_bus 是否已正确初始化")
        logger.error("  • 查看上述详细错误信息")
        raise RuntimeError(f"创建 CAN 通信器失败: {e}") from e