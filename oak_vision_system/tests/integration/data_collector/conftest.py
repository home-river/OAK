"""
数据采集模块集成测试的专用 fixtures

提供：
- Mock 设备和 Pipeline 数据
- 测试用的配置对象
- 事件订阅辅助工具
"""

import pytest
import time
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Optional
from pathlib import Path
import depthai as dai

from oak_vision_system.core.dto.config_dto import (
    OAKModuleConfigDTO,
    OAKConfigDTO,
    DeviceRoleBindingDTO,
    DeviceMetadataDTO,
    DeviceRole,
    ConnectionStatus,
)


# ==================== 配置资源路径 ====================

# 获取 assets 目录（项目根目录下的 assets/）
ASSETS_DIR = Path(__file__).parent.parent.parent.parent.parent / "assets"
TEST_CONFIG_DIR = ASSETS_DIR / "test_config"

# 查找可用的测试模型
def get_test_model_path() -> str:
    """
    获取测试模型路径
    
    优先级：
    1. assets/test_config/model.blob
    2. assets/test_config/ 下的任何 .blob 文件
    3. 假路径（用于 Mock 测试）
    """
    if TEST_CONFIG_DIR.exists():
        # 优先查找 model.blob
        model_path = TEST_CONFIG_DIR / "model.blob"
        if model_path.exists():
            return str(model_path)
        
        # 查找任何 .blob 文件
        blob_files = list(TEST_CONFIG_DIR.glob("*.blob"))
        if blob_files:
            return str(blob_files[0])
    
    # 返回假路径（用于 Mock 测试）
    return "/path/to/model.blob"


TEST_MODEL_PATH = get_test_model_path()


# ==================== Mock 数据生成器 ====================

class MockImgFrame:
    """Mock 的 DepthAI ImgFrame 对象"""
    
    def __init__(self, width: int = 640, height: int = 480, is_depth: bool = False):
        self.width = width
        self.height = height
        self.is_depth = is_depth
    
    def getCvFrame(self):
        """返回模拟的 OpenCV 帧"""
        if self.is_depth:
            # 深度帧返回 uint16 类型
            return np.random.randint(0, 5000, (self.height, self.width), dtype=np.uint16)
        else:
            # RGB 帧返回 uint8 类型
            return np.random.randint(0, 255, (self.height, self.width, 3), dtype=np.uint8)
    
    def getFrame(self):
        """返回原始帧数据（用于深度帧）"""
        if self.is_depth:
            return np.random.randint(0, 5000, (self.height, self.width), dtype=np.uint16)
        return None


class MockSpatialCoordinates:
    """Mock 的空间坐标"""
    
    def __init__(self, x: float = 100.0, y: float = 200.0, z: float = 300.0):
        self.x = x
        self.y = y
        self.z = z


class MockSpatialImgDetection:
    """Mock 的单个检测结果"""
    
    def __init__(
        self,
        label: int = 0,
        confidence: float = 0.9,
        xmin: float = 0.1,
        ymin: float = 0.2,
        xmax: float = 0.8,
        ymax: float = 0.9,
        x: float = 100.0,
        y: float = 200.0,
        z: float = 300.0,
    ):
        self.label = label
        self.confidence = confidence
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax
        self.spatialCoordinates = MockSpatialCoordinates(x, y, z)


class MockSpatialImgDetections:
    """Mock 的检测结果集合"""
    
    def __init__(self, num_detections: int = 2):
        self.detections = [
            MockSpatialImgDetection(
                label=i % 2,
                confidence=0.9 - i * 0.05,
                xmin=0.1 + i * 0.1,
                ymin=0.2 + i * 0.1,
                xmax=0.8 - i * 0.1,
                ymax=0.9 - i * 0.1,
                x=100.0 + i * 100,
                y=200.0 + i * 100,
                z=300.0 + i * 100,
            )
            for i in range(num_detections)
        ]


class MockOutputQueue:
    """Mock 的 DepthAI 输出队列"""
    
    def __init__(self, queue_type: str = "rgb", max_items: int = 10):
        self.queue_type = queue_type
        self.max_items = max_items
        self.items = []
        self.current_index = 0
    
    def add_item(self, item):
        """添加数据到队列"""
        self.items.append(item)
    
    def tryGet(self):
        """非阻塞获取数据"""
        if self.current_index < len(self.items):
            item = self.items[self.current_index]
            self.current_index += 1
            return item
        return None
    
    def get(self):
        """阻塞获取数据（简化实现）"""
        return self.tryGet()


# ==================== 测试配置 Fixtures ====================

@pytest.fixture
def test_oak_config():
    """创建测试用的 OAK 硬件配置"""
    return OAKConfigDTO(
        model_path=TEST_MODEL_PATH,  # 使用自动检测的模型路径
        confidence_threshold=0.5,
        hardware_fps=20,
        enable_depth_output=False,  # 默认禁用深度输出
        queue_max_size=4,
        queue_blocking=False,
        usb2_mode=False,
    )


@pytest.fixture
def test_oak_config_with_depth():
    """创建启用深度输出的测试配置"""
    return OAKConfigDTO(
        model_path=TEST_MODEL_PATH,  # 使用自动检测的模型路径
        confidence_threshold=0.5,
        hardware_fps=20,
        enable_depth_output=True,  # 启用深度输出
        queue_max_size=4,
        queue_blocking=False,
        usb2_mode=False,
    )


@pytest.fixture
def test_device_bindings():
    """创建测试用的设备绑定"""
    current_time = time.time()
    return {
        DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
            role=DeviceRole.LEFT_CAMERA,
            active_mxid="test_device_001_mxid",
        ),
        DeviceRole.RIGHT_CAMERA: DeviceRoleBindingDTO(
            role=DeviceRole.RIGHT_CAMERA,
            active_mxid="test_device_002_mxid",
        ),
    }


@pytest.fixture
def test_device_metadata():
    """创建测试用的设备元数据"""
    current_time = time.time()
    return {
        "test_device_001_mxid": DeviceMetadataDTO(
            mxid="test_device_001_mxid",
            product_name="OAK-D",
            connection_status=ConnectionStatus.CONNECTED,
            first_seen=current_time,
            last_seen=current_time,
        ),
        "test_device_002_mxid": DeviceMetadataDTO(
            mxid="test_device_002_mxid",
            product_name="OAK-D-Lite",
            connection_status=ConnectionStatus.CONNECTED,
            first_seen=current_time,
            last_seen=current_time,
        ),
    }


@pytest.fixture
def test_oak_module_config(test_oak_config, test_device_bindings, test_device_metadata):
    """创建测试用的 OAK 模块配置"""
    return OAKModuleConfigDTO(
        hardware_config=test_oak_config,
        role_bindings=test_device_bindings,
        device_metadata=test_device_metadata,
    )


@pytest.fixture
def test_oak_module_config_with_depth(test_oak_config_with_depth, test_device_bindings, test_device_metadata):
    """创建启用深度输出的 OAK 模块配置"""
    return OAKModuleConfigDTO(
        hardware_config=test_oak_config_with_depth,
        role_bindings=test_device_bindings,
        device_metadata=test_device_metadata,
    )


@pytest.fixture
def single_device_config(test_oak_config, test_device_metadata):
    """创建单设备配置"""
    return OAKModuleConfigDTO(
        hardware_config=test_oak_config,
        role_bindings={
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="test_device_001_mxid",
            ),
        },
        device_metadata=test_device_metadata,
    )


# ==================== Mock Pipeline 和 Device Fixtures ====================

@pytest.fixture
def mock_pipeline():
    """创建 Mock 的 DepthAI Pipeline"""
    pipeline = MagicMock(spec=dai.Pipeline)
    return pipeline


@pytest.fixture
def mock_device_info():
    """创建 Mock 的 DeviceInfo"""
    device_info = Mock(spec=dai.DeviceInfo)
    device_info.mxid = "test_device_001_mxid"
    return device_info


@pytest.fixture
def mock_output_queues():
    """创建 Mock 的输出队列集合"""
    return {
        "rgb": MockOutputQueue("rgb"),
        "detections": MockOutputQueue("detections"),
        "depth": MockOutputQueue("depth"),
    }


@pytest.fixture
def mock_device(mock_output_queues):
    """创建 Mock 的 DepthAI Device"""
    device = MagicMock(spec=dai.Device)
    
    # 配置 getOutputQueue 方法
    def get_output_queue(name, maxSize=4, blocking=False):
        return mock_output_queues.get(name)
    
    device.getOutputQueue = Mock(side_effect=get_output_queue)
    
    # 配置上下文管理器
    device.__enter__ = Mock(return_value=device)
    device.__exit__ = Mock(return_value=False)
    
    return device


# ==================== 事件订阅辅助工具 ====================

class EventCollector:
    """事件收集器 - 用于测试事件发布"""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.frame_events = []
        self.detection_events = []
        self.subscription_ids = []
    
    def start_collecting(self):
        """开始收集事件"""
        from oak_vision_system.core.event_bus.event_types import EventType
        
        # 订阅视频帧事件
        frame_sub_id = self.event_bus.subscribe(
            EventType.RAW_FRAME_DATA,
            self._on_frame_event
        )
        self.subscription_ids.append(frame_sub_id)
        
        # 订阅检测数据事件
        detection_sub_id = self.event_bus.subscribe(
            EventType.RAW_DETECTION_DATA,
            self._on_detection_event
        )
        self.subscription_ids.append(detection_sub_id)
    
    def stop_collecting(self):
        """停止收集事件"""
        for sub_id in self.subscription_ids:
            self.event_bus.unsubscribe(sub_id)
        self.subscription_ids.clear()
    
    def _on_frame_event(self, data):
        """视频帧事件回调"""
        self.frame_events.append(data)
    
    def _on_detection_event(self, data):
        """检测数据事件回调"""
        self.detection_events.append(data)
    
    def clear(self):
        """清空收集的事件"""
        self.frame_events.clear()
        self.detection_events.clear()
    
    def wait_for_events(self, frame_count: int = 0, detection_count: int = 0, timeout: float = 5.0):
        """等待指定数量的事件"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if (len(self.frame_events) >= frame_count and 
                len(self.detection_events) >= detection_count):
                return True
            time.sleep(0.05)
        return False


@pytest.fixture
def event_collector(event_bus):
    """创建事件收集器"""
    collector = EventCollector(event_bus)
    yield collector
    collector.stop_collecting()


@pytest.fixture
def event_bus():
    """创建事件总线实例"""
    from oak_vision_system.core.event_bus import get_event_bus, reset_event_bus
    reset_event_bus()
    return get_event_bus()
