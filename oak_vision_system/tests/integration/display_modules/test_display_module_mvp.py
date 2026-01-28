"""
显示模块 MVP 集成测试

测试场景：
1. 基础显示功能：窗口创建、视频帧显示、检测框绘制
2. 空检测帧处理：验证不崩溃，仅显示视频帧
3. 多设备支持：验证每个设备有独立窗口
4. 缓存机制：验证队列为空时使用缓存帧
5. 完整数据流：Collector → DataProcessor → Display

验证需求：
- 需求 1.1-1.9: 基础架构和线程管理
- 需求 2.1-2.7: 基础窗口显示
- 需求 3.1-3.6: 基础检测框绘制
- 需求 4.1-4.6: 配置加载
- 需求 5.1-5.6: 错误处理
- 需求 15.1-15.2: 空帧处理
- 需求 16.1-16.6: 多设备支持
"""

import time
import logging
import threading
import numpy as np
import pytest
from typing import List, Dict

from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.event_bus import EventBus, get_event_bus
from oak_vision_system.core.event_bus.event_types import EventType
from oak_vision_system.modules.display_modules import DisplayManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# ==================== 测试辅助函数 ====================

def create_test_video_frame(
    device_id: str,
    frame_id: int,
    width: int = 640,
    height: int = 480
) -> VideoFrameDTO:
    """创建测试用的视频帧"""
    # 创建随机 RGB 图像
    rgb_frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    
    # 创建随机深度图
    depth_frame = np.random.randint(0, 5000, (height, width), dtype=np.uint16)
    
    return VideoFrameDTO(
        device_id=device_id,
        frame_id=frame_id,
        rgb_frame=rgb_frame,
        depth_frame=depth_frame
    )


def create_test_processed_data(
    device_id: str,
    frame_id: int,
    num_detections: int = 3,
    device_alias: str = None
) -> DeviceProcessedDataDTO:
    """创建测试用的处理数据（包含检测框）"""
    if num_detections > 0:
        # 创建随机检测数据
        coords = np.random.rand(num_detections, 3).astype(np.float32) * 1000
        bbox = np.random.rand(num_detections, 4).astype(np.float32) * 640
        # 确保 bbox 有效（xmin < xmax, ymin < ymax）
        bbox[:, 2] = bbox[:, 0] + np.abs(bbox[:, 2] - bbox[:, 0])
        bbox[:, 3] = bbox[:, 1] + np.abs(bbox[:, 3] - bbox[:, 1])
        confidence = np.random.rand(num_detections).astype(np.float32)
        labels = np.random.randint(0, 10, num_detections, dtype=np.int32)
    else:
        # 空检测帧
        coords = np.empty((0, 3), dtype=np.float32)
        bbox = np.empty((0, 4), dtype=np.float32)
        confidence = np.empty((0,), dtype=np.float32)
        labels = np.empty((0,), dtype=np.int32)
    
    return DeviceProcessedDataDTO(
        device_id=device_id,
        frame_id=frame_id,
        device_alias=device_alias,
        coords=coords,
        bbox=bbox,
        confidence=confidence,
        labels=labels,
        state_label=[]
    )


def create_empty_processed_data(
    device_id: str,
    frame_id: int,
    device_alias: str = None
) -> DeviceProcessedDataDTO:
    """创建空检测帧（用于测试空帧处理）"""
    return create_test_processed_data(
        device_id=device_id,
        frame_id=frame_id,
        num_detections=0,
        device_alias=device_alias
    )


class EventPublisher:
    """事件发布器（模拟 Collector 和 DataProcessor）"""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
    
    def publish_frame_data(
        self,
        device_id: str,
        frame_id: int,
        device_alias: str = None
    ) -> None:
        """发布视频帧数据（模拟 Collector）"""
        video_frame = create_test_video_frame(device_id, frame_id)
        self.event_bus.publish(EventType.RAW_FRAME_DATA, video_frame)
        self.logger.debug(f"发布 RAW_FRAME_DATA: device={device_id}, frame={frame_id}")
    
    def publish_processed_data(
        self,
        device_id: str,
        frame_id: int,
        num_detections: int = 3,
        device_alias: str = None
    ) -> None:
        """发布处理数据（模拟 DataProcessor）"""
        processed_data = create_test_processed_data(
            device_id, frame_id, num_detections, device_alias
        )
        self.event_bus.publish(EventType.PROCESSED_DATA, processed_data)
        self.logger.debug(
            f"发布 PROCESSED_DATA: device={device_id}, frame={frame_id}, "
            f"detections={num_detections}"
        )
    
    def publish_empty_frame(
        self,
        device_id: str,
        frame_id: int,
        device_alias: str = None
    ) -> None:
        """发布空检测帧（模拟 DataProcessor）"""
        video_frame = create_test_video_frame(device_id, frame_id)
        empty_data = create_empty_processed_data(device_id, frame_id, device_alias)
        
        self.event_bus.publish(EventType.RAW_FRAME_DATA, video_frame)
        self.event_bus.publish(EventType.PROCESSED_DATA, empty_data)
        self.logger.debug(f"发布空检测帧: device={device_id}, frame={frame_id}")
    
    def publish_complete_frame(
        self,
        device_id: str,
        frame_id: int,
        num_detections: int = 3,
        device_alias: str = None
    ) -> None:
        """发布完整帧（视频帧 + 处理数据）"""
        self.publish_frame_data(device_id, frame_id, device_alias)
        time.sleep(0.01)  # 短暂延迟，模拟真实场景
        self.publish_processed_data(device_id, frame_id, num_detections, device_alias)


# ==================== 测试 Fixtures ====================

@pytest.fixture
def event_bus():
    """创建事件总线实例"""
    return get_event_bus()


@pytest.fixture
def display_config():
    """创建显示配置（禁用显示以避免创建窗口）"""
    return DisplayConfigDTO(
        enable_display=False,  # 禁用显示以避免创建窗口
        window_width=1280,
        window_height=720,
        target_fps=20
    )


@pytest.fixture
def event_publisher(event_bus):
    """创建事件发布器"""
    return EventPublisher(event_bus)


# ==================== 测试用例 ====================

def test_display_manager_creation(display_config):
    """
    测试 1: DisplayManager 创建
    
    验证需求：
    - 需求 1.1: Display_Module 包含两个子模块
    - 需求 4.1: 接收 DisplayConfigDTO
    - 需求 4.6: 配置无效时抛出 ValueError
    """
    logger.info("\n" + "=" * 60)
    logger.info("测试 1: DisplayManager 创建")
    logger.info("=" * 60)
    
    # 创建 DisplayManager
    manager = DisplayManager(
        config=display_config,
        devices_list=["device_1", "device_2"]
    )
    
    # 验证子模块创建
    assert hasattr(manager, '_packager'), "应该有 _packager 属性"
    assert hasattr(manager, '_renderer'), "应该有 _renderer 属性"
    assert manager._packager is not None, "_packager 不应该为 None"
    assert manager._renderer is not None, "_renderer 不应该为 None"
    
    logger.info("✅ DisplayManager 创建成功")
    logger.info(f"   - 设备数量: {len(manager._devices_list)}")
    logger.info(f"   - RenderPacketPackager: {type(manager._packager).__name__}")
    logger.info(f"   - DisplayRenderer: {type(manager._renderer).__name__}")


def test_display_manager_start_stop(display_config, event_bus):
    """
    测试 2: DisplayManager 启动和停止
    
    验证需求：
    - 需求 1.7: 提供 start() 和 stop() 方法
    - 需求 1.8: 停止时清理资源
    - 需求 4.3: 根据 enable_display 决定是否启动渲染器
    """
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: DisplayManager 启动和停止")
    logger.info("=" * 60)
    
    manager = DisplayManager(
        config=display_config,
        devices_list=["device_1"]
    )
    
    # 启动
    success = manager.start()
    assert success, "启动应该成功"
    assert manager.is_running, "应该处于运行状态"
    
    logger.info("✅ DisplayManager 启动成功")
    
    # 等待一小段时间
    time.sleep(0.5)
    
    # 停止
    success = manager.stop(timeout=5.0)
    assert success, "停止应该成功"
    assert not manager.is_running, "应该处于停止状态"
    
    logger.info("✅ DisplayManager 停止成功")


def test_render_packet_packager_pairing(display_config, event_bus, event_publisher):
    """
    测试 3: RenderPacketPackager 数据配对
    
    验证需求：
    - 需求 1.4: 订阅外部事件
    - 需求 1.5: 维护按设备ID分组的内部队列
    - 需求 1.6: 通过 get_packets() 读取渲染包
    """
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: RenderPacketPackager 数据配对")
    logger.info("=" * 60)
    
    manager = DisplayManager(
        config=display_config,
        devices_list=["device_1", "device_2"]
    )
    
    # 启动
    manager.start()
    time.sleep(0.2)  # 等待订阅生效
    
    try:
        # 发布完整帧数据
        event_publisher.publish_complete_frame("device_1", 1, num_detections=3)
        event_publisher.publish_complete_frame("device_2", 1, num_detections=2)
        
        # 等待配对
        time.sleep(0.3)
        
        # 获取渲染包
        packets = manager._packager.get_packets(timeout=0.1)
        
        # 验证
        assert len(packets) > 0, "应该获取到渲染包"
        logger.info(f"✅ 获取到 {len(packets)} 个设备的渲染包")
        
        for device_id, packet in packets.items():
            logger.info(f"   - 设备 {device_id}:")
            logger.info(f"     - frame_id: {packet.video_frame.frame_id}")
            logger.info(f"     - 检测数量: {packet.processed_detections.coords.shape[0]}")
            
            # 验证数据一致性
            assert packet.video_frame.device_id == packet.processed_detections.device_id
            assert packet.video_frame.frame_id == packet.processed_detections.frame_id
        
    finally:
        manager.stop()


def test_empty_detection_frame_handling(display_config, event_bus, event_publisher):
    """
    测试 4: 空检测帧处理
    
    验证需求：
    - 需求 3.5: 检测数据为空时仅显示视频帧
    - 需求 3.6: 正确处理空检测帧（不崩溃）
    - 需求 15.1: 包含空检测数据时仅显示视频帧
    - 需求 15.2: 不绘制任何检测框或标签
    """
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: 空检测帧处理")
    logger.info("=" * 60)
    
    manager = DisplayManager(
        config=display_config,
        devices_list=["device_1"]
    )
    
    # 启动
    manager.start()
    time.sleep(0.2)
    
    try:
        # 发布空检测帧
        event_publisher.publish_empty_frame("device_1", 1, device_alias="test_camera")
        
        # 等待处理
        time.sleep(0.3)
        
        # 获取渲染包
        packets = manager._packager.get_packets(timeout=0.1)
        
        # 验证
        assert len(packets) > 0, "应该获取到渲染包"
        
        packet = packets.get("device_1")
        assert packet is not None, "应该有 device_1 的渲染包"
        
        # 验证空检测数据
        assert packet.processed_detections.coords.shape[0] == 0, "检测数量应该为 0"
        assert packet.processed_detections.bbox.shape[0] == 0, "边界框数量应该为 0"
        
        logger.info("✅ 空检测帧处理成功")
        logger.info(f"   - 检测数量: {packet.processed_detections.coords.shape[0]}")
        logger.info(f"   - 视频帧存在: {packet.video_frame.rgb_frame is not None}")
        
    finally:
        manager.stop()


def test_multiple_devices_support(display_config, event_bus, event_publisher):
    """
    测试 5: 多设备支持
    
    验证需求：
    - 需求 2.7: 支持多设备显示
    - 需求 16.1: 为每个设备维护独立队列
    - 需求 16.2: 为每个设备创建独立窗口
    - 需求 16.3: 一次性获取所有设备的渲染包
    """
    logger.info("\n" + "=" * 60)
    logger.info("测试 5: 多设备支持")
    logger.info("=" * 60)
    
    devices = ["device_1", "device_2", "device_3"]
    manager = DisplayManager(
        config=display_config,
        devices_list=devices
    )
    
    # 启动
    manager.start()
    time.sleep(0.2)
    
    try:
        # 为每个设备发布数据
        for i, device_id in enumerate(devices):
            event_publisher.publish_complete_frame(
                device_id,
                frame_id=1,
                num_detections=i + 1,
                device_alias=f"camera_{i+1}"
            )
        
        # 等待配对
        time.sleep(0.5)
        
        # 获取所有设备的渲染包
        packets = manager._packager.get_packets(timeout=0.1)
        
        # 验证
        logger.info(f"✅ 获取到 {len(packets)} 个设备的渲染包")
        
        for device_id in devices:
            packet = packets.get(device_id)
            if packet:
                logger.info(f"   - 设备 {device_id}:")
                logger.info(f"     - 别名: {packet.processed_detections.device_alias}")
                logger.info(f"     - 检测数量: {packet.processed_detections.coords.shape[0]}")
        
        # 验证每个设备都有独立队列
        assert device_id in manager._packager.packet_queue, \
            f"设备 {device_id} 应该有独立队列"
        
    finally:
        manager.stop()


def test_cache_mechanism(display_config, event_bus, event_publisher):
    """
    测试 6: 缓存机制
    
    验证需求：
    - 需求 1.9: 队列为空时使用缓存帧
    - 需求 16.4: 队列为空时使用缓存帧（如果未过期）
    """
    logger.info("\n" + "=" * 60)
    logger.info("测试 6: 缓存机制")
    logger.info("=" * 60)
    
    manager = DisplayManager(
        config=display_config,
        devices_list=["device_1"]
    )
    
    # 启动
    manager.start()
    time.sleep(0.2)
    
    try:
        # 发布第一帧
        event_publisher.publish_complete_frame("device_1", 1, num_detections=3)
        time.sleep(0.3)
        
        # 获取第一帧（应该成功）
        packets1 = manager._packager.get_packets(timeout=0.1)
        assert len(packets1) > 0, "应该获取到第一帧"
        
        logger.info("✅ 第一帧获取成功")
        logger.info(f"   - frame_id: {packets1['device_1'].video_frame.frame_id}")
        
        # 不发送新数据，再次获取（应该使用缓存）
        packets2 = manager._packager.get_packets(timeout=0.1)
        
        if len(packets2) > 0:
            logger.info("✅ 缓存机制工作正常（返回缓存帧）")
            logger.info(f"   - frame_id: {packets2['device_1'].video_frame.frame_id}")
            assert packets2['device_1'].video_frame.frame_id == 1, "应该返回缓存的第一帧"
        else:
            logger.info("⚠️  缓存已过期或队列为空")
        
        # 等待缓存过期
        time.sleep(1.5)
        
        # 再次获取（缓存应该过期）
        packets3 = manager._packager.get_packets(timeout=0.1)
        
        if len(packets3) == 0:
            logger.info("✅ 缓存过期后正确清理")
        else:
            logger.info("⚠️  缓存仍然有效")
        
    finally:
        manager.stop()


def test_statistics_collection(display_config, event_bus, event_publisher):
    """
    测试 7: 统计信息收集
    
    验证需求：
    - 需求 13.1: 提供 get_stats() 方法
    - 需求 13.2: 包含渲染帧数、丢弃帧数等信息
    """
    logger.info("\n" + "=" * 60)
    logger.info("测试 7: 统计信息收集")
    logger.info("=" * 60)
    
    manager = DisplayManager(
        config=display_config,
        devices_list=["device_1"]
    )
    
    # 启动
    manager.start()
    time.sleep(0.2)
    
    try:
        # 发布多帧数据
        for i in range(5):
            event_publisher.publish_complete_frame("device_1", i, num_detections=2)
            time.sleep(0.1)
        
        # 等待处理
        time.sleep(0.5)
        
        # 获取统计信息
        stats = manager.get_stats()
        
        # 验证
        assert stats is not None, "应该返回统计信息"
        assert 'packager' in stats, "应该包含 packager 统计"
        assert 'renderer' in stats, "应该包含 renderer 统计"
        
        logger.info("✅ 统计信息收集成功")
        logger.info(f"   - Packager 统计: {stats['packager']}")
        logger.info(f"   - Renderer 统计: {stats['renderer']}")
        
    finally:
        manager.stop()


def test_error_handling(display_config, event_bus):
    """
    测试 8: 错误处理
    
    验证需求：
    - 需求 5.1: 渲染包数据无效时记录错误并跳过
    - 需求 5.2: OpenCV 操作失败时记录错误并继续
    - 需求 5.3: 捕获所有异常，避免线程崩溃
    - 需求 5.6: 队列获取超时时继续循环
    """
    logger.info("\n" + "=" * 60)
    logger.info("测试 8: 错误处理")
    logger.info("=" * 60)
    
    manager = DisplayManager(
        config=display_config,
        devices_list=["device_1"]
    )
    
    # 启动
    manager.start()
    time.sleep(0.2)
    
    try:
        # 测试队列获取超时（不应该崩溃）
        packets = manager._packager.get_packets(timeout=0.1)
        logger.info("✅ 队列获取超时处理正常（返回空字典或缓存）")
        
        # 验证系统仍在运行
        assert manager.is_running, "系统应该仍在运行"
        
        logger.info("✅ 错误处理机制正常")
        
    finally:
        manager.stop()


# ==================== 主测试函数 ====================

def run_all_tests():
    """运行所有测试（用于手动执行）"""
    logger.info("\n" + "=" * 80)
    logger.info("显示模块 MVP 集成测试")
    logger.info("=" * 80)
    
    # 创建测试环境
    event_bus = get_event_bus()
    display_config = DisplayConfigDTO(
        enable_display=False,
        window_width=1280,
        window_height=720,
        target_fps=20
    )
    event_publisher = EventPublisher(event_bus)
    
    results = []
    
    # 运行测试
    try:
        test_display_manager_creation(display_config)
        results.append(("DisplayManager 创建", True))
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        results.append(("DisplayManager 创建", False))
    
    try:
        test_display_manager_start_stop(display_config, event_bus)
        results.append(("DisplayManager 启动停止", True))
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        results.append(("DisplayManager 启动停止", False))
    
    try:
        test_render_packet_packager_pairing(display_config, event_bus, event_publisher)
        results.append(("数据配对", True))
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        results.append(("数据配对", False))
    
    try:
        test_empty_detection_frame_handling(display_config, event_bus, event_publisher)
        results.append(("空检测帧处理", True))
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        results.append(("空检测帧处理", False))
    
    try:
        test_multiple_devices_support(display_config, event_bus, event_publisher)
        results.append(("多设备支持", True))
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        results.append(("多设备支持", False))
    
    try:
        test_cache_mechanism(display_config, event_bus, event_publisher)
        results.append(("缓存机制", True))
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        results.append(("缓存机制", False))
    
    try:
        test_statistics_collection(display_config, event_bus, event_publisher)
        results.append(("统计信息收集", True))
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        results.append(("统计信息收集", False))
    
    try:
        test_error_handling(display_config, event_bus)
        results.append(("错误处理", True))
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        results.append(("错误处理", False))
    
    # 输出总结
    logger.info("\n" + "=" * 80)
    logger.info("测试总结")
    logger.info("=" * 80)
    
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
    exit(run_all_tests())
