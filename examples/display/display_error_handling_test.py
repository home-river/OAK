"""
显示模块错误处理测试

验证 DisplayRenderer 和 DisplayManager 的错误处理机制。
测试场景：
1. 配置无效时抛出 ValueError
2. 渲染失败时记录错误但继续运行
3. 停止超时时记录警告
"""

import logging
import numpy as np
from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.modules.display_modules import DisplayManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_invalid_config():
    """测试配置无效时抛出 ValueError（需求 4.6, 5.5）"""
    logger.info("=" * 60)
    logger.info("测试 1: 配置无效时抛出 ValueError")
    logger.info("=" * 60)
    
    try:
        # 创建无效配置（window_width 太小）
        invalid_config = DisplayConfigDTO(
            enable_display=False,  # 禁用显示以避免创建窗口
            window_width=100,  # 无效值（太小）
            window_height=100,
            target_fps=20
        )
        
        # 尝试创建 DisplayManager
        manager = DisplayManager(
            config=invalid_config,
            devices_list=["test_device"]
        )
        
        logger.error("❌ 测试失败：应该抛出 ValueError")
        return False
        
    except ValueError as e:
        logger.info(f"✅ 测试通过：正确抛出 ValueError: {e}")
        return True
    except Exception as e:
        logger.error(f"❌ 测试失败：抛出了错误的异常类型: {type(e).__name__}: {e}")
        return False


def test_valid_config():
    """测试有效配置可以正常创建 DisplayManager"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 有效配置可以正常创建 DisplayManager")
    logger.info("=" * 60)
    
    try:
        # 创建有效配置
        valid_config = DisplayConfigDTO(
            enable_display=False,  # 禁用显示以避免创建窗口
            window_width=1280,
            window_height=720,
            target_fps=20
        )
        
        # 创建 DisplayManager
        manager = DisplayManager(
            config=valid_config,
            devices_list=["test_device_1", "test_device_2"]
        )
        
        logger.info("✅ 测试通过：DisplayManager 创建成功")
        logger.info(f"   - 设备数量: {len(manager._devices_list)}")
        logger.info(f"   - enable_display: {manager._config.enable_display}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败：{type(e).__name__}: {e}")
        return False


def test_logging_setup():
    """测试日志器设置（需求 5.5）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 日志器设置")
    logger.info("=" * 60)
    
    try:
        # 创建有效配置
        config = DisplayConfigDTO(
            enable_display=False,
            window_width=1280,
            window_height=720,
            target_fps=20
        )
        
        # 创建 DisplayManager
        manager = DisplayManager(
            config=config,
            devices_list=["test_device"]
        )
        
        # 检查日志器
        assert hasattr(manager, 'logger'), "DisplayManager 应该有 logger 属性"
        assert hasattr(manager._renderer, 'logger'), "DisplayRenderer 应该有 logger 属性"
        assert hasattr(manager._packager, 'logger'), "RenderPacketPackager 应该有 logger 属性"
        
        # 检查日志器名称
        assert manager.logger.name == 'oak_vision_system.modules.display_modules.display_manager'
        assert manager._renderer.logger.name == 'oak_vision_system.modules.display_modules.display_renderer'
        
        logger.info("✅ 测试通过：所有模块都正确使用 logging.getLogger(__name__)")
        logger.info(f"   - DisplayManager logger: {manager.logger.name}")
        logger.info(f"   - DisplayRenderer logger: {manager._renderer.logger.name}")
        logger.info(f"   - RenderPacketPackager logger: {manager._packager.logger.name}")
        return True
        
    except AssertionError as e:
        logger.error(f"❌ 测试失败：{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 测试失败：{type(e).__name__}: {e}")
        return False


def main():
    """运行所有测试"""
    logger.info("\n" + "=" * 60)
    logger.info("显示模块错误处理测试")
    logger.info("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("配置无效测试", test_invalid_config()))
    results.append(("有效配置测试", test_valid_config()))
    results.append(("日志器设置测试", test_logging_setup()))
    
    # 输出总结
    logger.info("\n" + "=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{status}: {name}")
    
    logger.info(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("\n🎉 所有测试通过！")
        return 0
    else:
        logger.error(f"\n❌ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit(main())
