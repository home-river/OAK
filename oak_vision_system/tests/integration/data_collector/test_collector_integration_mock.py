"""
OAK 数据采集器集成测试 - Mock 版本

测试策略：
- 使用 Mock 对象模拟 DepthAI 设备和 Pipeline
- 验证 Collector 的完整工作流程
- 不需要真实硬件，可以在任何环境中运行

测试覆盖：
1. Collector 初始化和配置验证
2. Pipeline 创建和设备启动
3. 数据采集循环（RGB 帧、检测数据、深度帧）
4. 事件发布机制
5. 多设备支持
6. 线程生命周期管理
7. 错误处理和边界情况

运行方式：
- 运行所有 Mock 测试：pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_mock.py -v
- 运行特定测试：pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_mock.py::TestCollectorInitialization -v
"""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
import numpy as np

from oak_vision_system.modules.data_collector.collector import OAKDataCollector
from oak_vision_system.core.dto import (
    VideoFrameDTO,
    DeviceDetectionDataDTO,
)
from oak_vision_system.core.dto.config_dto import DeviceRole
from oak_vision_system.core.event_bus import reset_event_bus


# ==================== 测试类：初始化和配置 ====================

class TestCollectorInitialization:
    """测试 Collector 的初始化和配置"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_collector_creation(self, test_oak_module_config, event_bus):
        """测试 1: Collector 创建"""
        # 创建 Collector
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        # 验证基本属性
        assert collector.config == test_oak_module_config
        assert collector.event_bus == event_bus
        assert collector.pipeline_manager is not None
        
        # 验证运行状态初始化
        assert len(collector.running) == 2  # 两个设备角色
        assert DeviceRole.LEFT_CAMERA.value in collector.running
        assert DeviceRole.RIGHT_CAMERA.value in collector.running
        assert all(not running for running in collector.running.values())  # 初始都为 False
        
        # 验证帧计数器初始化
        assert len(collector._frame_counters) == 2
        assert collector._frame_counters[DeviceRole.LEFT_CAMERA.value] == 0
        assert collector._frame_counters[DeviceRole.RIGHT_CAMERA.value] == 0
        
        print("✅ Collector 创建成功")
    
    def test_collector_with_single_device(self, single_device_config, event_bus):
        """测试 2: 单设备配置的 Collector"""
        collector = OAKDataCollector(
            config=single_device_config,
            event_bus=event_bus
        )
        
        # 验证只有一个设备角色
        assert len(collector.running) == 1
        assert DeviceRole.LEFT_CAMERA.value in collector.running
        
        print("✅ 单设备 Collector 创建成功")
    
    def test_collector_config_validation(self, test_oak_config, event_bus):
        """测试 3: 配置验证"""
        from oak_vision_system.core.dto.config_dto import OAKModuleConfigDTO
        
        # 创建空绑定的配置（应该可以创建，但无法启动）
        empty_config = OAKModuleConfigDTO(
            hardware_config=test_oak_config,
            role_bindings={},
            device_metadata={},
        )
        
        collector = OAKDataCollector(
            config=empty_config,
            event_bus=event_bus
        )
        
        # 验证空配置
        assert len(collector.running) == 0
        
        print("✅ 配置验证通过")


# ==================== 测试类：数据组装 ====================

class TestDataAssembly:
    """测试数据组装功能"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_assemble_frame_data_rgb_only(self, test_oak_module_config, event_bus):
        """测试 4: 组装 RGB 视频帧数据（无深度）"""
        from .conftest import MockImgFrame
        
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        # 创建 Mock RGB 帧
        mock_rgb_frame = MockImgFrame(width=640, height=480, is_depth=False)
        
        # 获取设备绑定
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        
        # 组装视频帧数据
        frame_dto = collector._assemble_frame_data(
            device_binding=binding,
            rgb_frame=mock_rgb_frame,
            depth_frame=None,
            frame_id=100
        )
        
        # 验证
        assert frame_dto is not None
        assert isinstance(frame_dto, VideoFrameDTO)
        assert frame_dto.device_id == "test_device_001_mxid"
        assert frame_dto.frame_id == 100
        assert frame_dto.has_rgb
        assert not frame_dto.has_depth  # 配置中禁用了深度
        assert frame_dto.rgb_frame.shape == (480, 640, 3)
        
        print("✅ RGB 视频帧组装成功")
    
    def test_assemble_frame_data_with_depth(self, test_oak_module_config_with_depth, event_bus):
        """测试 5: 组装视频帧数据（包含深度）"""
        from .conftest import MockImgFrame
        
        collector = OAKDataCollector(
            config=test_oak_module_config_with_depth,
            event_bus=event_bus
        )
        
        # 创建 Mock RGB 和深度帧
        mock_rgb_frame = MockImgFrame(width=640, height=480, is_depth=False)
        mock_depth_frame = MockImgFrame(width=640, height=480, is_depth=True)
        
        # 获取设备绑定
        binding = test_oak_module_config_with_depth.role_bindings[DeviceRole.LEFT_CAMERA]
        
        # 组装视频帧数据
        frame_dto = collector._assemble_frame_data(
            device_binding=binding,
            rgb_frame=mock_rgb_frame,
            depth_frame=mock_depth_frame,
            frame_id=100
        )
        
        # 验证
        assert frame_dto is not None
        assert frame_dto.has_rgb
        assert frame_dto.has_depth  # 配置中启用了深度
        assert frame_dto.depth_frame.shape == (480, 640)
        assert frame_dto.depth_frame.dtype == np.uint16
        
        print("✅ 带深度的视频帧组装成功")
    
    def test_assemble_detection_data(self, test_oak_module_config, event_bus):
        """测试 6: 组装检测数据"""
        from .conftest import MockSpatialImgDetections
        
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        # 创建 Mock 检测数据
        mock_detections = MockSpatialImgDetections(num_detections=3)
        
        # 获取设备绑定
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        
        # 组装检测数据
        detection_dto = collector._assemble_detection_data(
            device_binding=binding,
            detections_data=mock_detections,
            frame_id=100
        )
        
        # 验证
        assert detection_dto is not None
        assert isinstance(detection_dto, DeviceDetectionDataDTO)
        assert detection_dto.device_id == "test_device_001_mxid"
        assert detection_dto.frame_id == 100
        assert detection_dto.device_alias == DeviceRole.LEFT_CAMERA.value
        assert len(detection_dto.detections) == 3
        
        # 验证第一个检测结果
        first_detection = detection_dto.detections[0]
        assert first_detection.label == 0
        assert 0.0 <= first_detection.confidence <= 1.0
        assert first_detection.bbox.xmin < first_detection.bbox.xmax
        assert first_detection.bbox.ymin < first_detection.bbox.ymax
        assert first_detection.spatial_coordinates.x == 100.0
        
        print("✅ 检测数据组装成功")
    
    def test_assemble_empty_detection_data(self, test_oak_module_config, event_bus):
        """测试 7: 组装空检测数据"""
        from .conftest import MockSpatialImgDetections
        
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        # 创建空检测数据
        mock_detections = MockSpatialImgDetections(num_detections=0)
        
        # 获取设备绑定
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        
        # 组装检测数据
        detection_dto = collector._assemble_detection_data(
            device_binding=binding,
            detections_data=mock_detections,
            frame_id=100
        )
        
        # 验证
        assert detection_dto is not None
        assert len(detection_dto.detections) == 0
        
        print("✅ 空检测数据组装成功")


# ==================== 测试类：事件发布 ====================

class TestEventPublishing:
    """测试事件发布机制"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_publish_frame_data(self, test_oak_module_config, event_bus, event_collector):
        """测试 8: 发布视频帧事件"""
        from .conftest import MockImgFrame
        
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        # 开始收集事件
        event_collector.start_collecting()
        
        # 创建并发布视频帧
        mock_rgb_frame = MockImgFrame()
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        
        frame_dto = collector._assemble_frame_data(
            device_binding=binding,
            rgb_frame=mock_rgb_frame,
            frame_id=100
        )
        
        collector._publish_data(frame_dto)
        
        # 等待事件
        time.sleep(0.1)
        
        # 验证
        assert len(event_collector.frame_events) == 1
        received_frame = event_collector.frame_events[0]
        assert received_frame.device_id == "test_device_001_mxid"
        assert received_frame.frame_id == 100
        
        print("✅ 视频帧事件发布成功")
    
    def test_publish_detection_data(self, test_oak_module_config, event_bus, event_collector):
        """测试 9: 发布检测数据事件"""
        from .conftest import MockSpatialImgDetections
        
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        # 开始收集事件
        event_collector.start_collecting()
        
        # 创建并发布检测数据
        mock_detections = MockSpatialImgDetections(num_detections=2)
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        
        detection_dto = collector._assemble_detection_data(
            device_binding=binding,
            detections_data=mock_detections,
            frame_id=100
        )
        
        collector._publish_data(detection_dto)
        
        # 等待事件
        time.sleep(0.1)
        
        # 验证
        assert len(event_collector.detection_events) == 1
        received_detection = event_collector.detection_events[0]
        assert received_detection.device_id == "test_device_001_mxid"
        assert received_detection.frame_id == 100
        assert len(received_detection.detections) == 2
        
        print("✅ 检测数据事件发布成功")


# ==================== 测试类：采集循环（Mock）====================

class TestCollectionLoopMock:
    """测试采集循环（使用 Mock）"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @patch('depthai.Device')
    @patch('depthai.DeviceInfo')
    def test_start_single_device_mock(
        self,
        mock_device_info_class,
        mock_device_class,
        test_oak_module_config,
        event_bus,
        event_collector,
        mock_pipeline,
        mock_output_queues
    ):
        """测试 10: 启动单个设备的采集循环（Mock）"""
        from .conftest import MockImgFrame, MockSpatialImgDetections
        
        # 配置 Mock
        mock_device_info_class.return_value = Mock()
        
        # 配置 Mock Device
        mock_device = MagicMock()
        mock_device.__enter__ = Mock(return_value=mock_device)
        mock_device.__exit__ = Mock(return_value=False)
        
        # 准备队列数据
        rgb_queue = mock_output_queues["rgb"]
        det_queue = mock_output_queues["detections"]
        
        # 添加测试数据（3 帧）
        for i in range(3):
            rgb_queue.add_item(MockImgFrame())
            det_queue.add_item(MockSpatialImgDetections(num_detections=2))
        
        # 配置 getOutputQueue
        def get_output_queue(name, maxSize=4, blocking=False):
            return mock_output_queues.get(name)
        
        mock_device.getOutputQueue = Mock(side_effect=get_output_queue)
        mock_device_class.return_value = mock_device
        
        # 创建 Collector 并 Mock Pipeline
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        collector.pipeline_manager.pipeline = mock_pipeline
        
        # 开始收集事件
        event_collector.start_collecting()
        
        # 启动采集（只启动一个设备）
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        
        # 在独立线程中运行采集循环
        def run_collection():
            try:
                collector._start_OAK_with_device(binding)
            except Exception as e:
                print(f"采集循环异常: {e}")
        
        collection_thread = threading.Thread(target=run_collection, daemon=True)
        collection_thread.start()
        
        # 等待数据采集
        time.sleep(0.5)
        
        # 停止采集
        collector._set_running_state(binding, False)
        collection_thread.join(timeout=2.0)
        
        # 验证事件
        # 注意：由于 tryGet() 的行为，可能不是所有数据都被处理
        assert len(event_collector.frame_events) > 0, "应该收到至少一个视频帧事件"
        assert len(event_collector.detection_events) > 0, "应该收到至少一个检测数据事件"
        
        print(f"✅ 采集循环测试成功: 收到 {len(event_collector.frame_events)} 个视频帧, "
              f"{len(event_collector.detection_events)} 个检测数据")


# ==================== 测试类：线程生命周期 ====================

class TestThreadLifecycle:
    """测试线程生命周期管理"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_running_state_management(self, test_oak_module_config, event_bus):
        """测试 11: 运行状态管理"""
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        # 初始状态
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        assert not collector._is_running(binding)
        
        # 设置运行状态
        collector._set_running_state(binding, True)
        assert collector._is_running(binding)
        
        # 停止运行
        collector._set_running_state(binding, False)
        assert not collector._is_running(binding)
        
        print("✅ 运行状态管理正常")
    
    def test_start_without_active_mxid(self, test_oak_config, event_bus):
        """测试 12: 启动没有激活 MXid 的设备"""
        from oak_vision_system.core.dto.config_dto import OAKModuleConfigDTO, DeviceRoleBindingDTO
        
        # 创建没有激活 MXid 的配置
        config = OAKModuleConfigDTO(
            hardware_config=test_oak_config,
            role_bindings={
                DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                    role=DeviceRole.LEFT_CAMERA,
                    active_mxid=None,  # 没有激活的 MXid
                ),
            },
            device_metadata={},
        )
        
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        
        # 启动采集
        result = collector.start()
        
        # 验证：应该跳过没有 MXid 的设备
        assert len(result["started"]) == 0
        assert DeviceRole.LEFT_CAMERA.value in result["skipped"]
        assert result["skipped"][DeviceRole.LEFT_CAMERA.value] == "no_active_mxid"
        
        print("✅ 正确跳过没有激活 MXid 的设备")
    
    def test_stop_collector(self, test_oak_module_config, event_bus):
        """测试 13: 停止 Collector"""
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        # 手动设置运行状态（模拟启动）
        for role_key in collector.running.keys():
            collector._set_running_state(role_key, True)
        
        # 停止
        collector.stop()
        
        # 验证所有设备都已停止
        for role_key in collector.running.keys():
            assert not collector._is_running(role_key)
        
        # 验证线程已清理
        assert len(collector._worker_threads) == 0
        
        print("✅ Collector 停止成功")


# ==================== 测试类：错误处理 ====================

class TestErrorHandling:
    """测试错误处理"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_assemble_frame_with_none_rgb(self, test_oak_module_config, event_bus):
        """测试 14: 组装视频帧时 RGB 为 None"""
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        
        # RGB 帧为 None
        frame_dto = collector._assemble_frame_data(
            device_binding=binding,
            rgb_frame=None,
            frame_id=100
        )
        
        # 应该返回 None
        assert frame_dto is None
        
        print("✅ 正确处理 RGB 帧为 None 的情况")
    
    def test_assemble_frame_missing_depth_when_enabled(self, test_oak_module_config_with_depth, event_bus):
        """测试 15: 启用深度但未提供深度数据"""
        from .conftest import MockImgFrame
        
        collector = OAKDataCollector(
            config=test_oak_module_config_with_depth,
            event_bus=event_bus
        )
        
        binding = test_oak_module_config_with_depth.role_bindings[DeviceRole.LEFT_CAMERA]
        mock_rgb_frame = MockImgFrame()
        
        # 启用深度但不提供深度帧
        frame_dto = collector._assemble_frame_data(
            device_binding=binding,
            rgb_frame=mock_rgb_frame,
            depth_frame=None,  # 缺少深度数据
            frame_id=100
        )
        
        # 应该返回 None（因为配置要求深度）
        assert frame_dto is None
        
        print("✅ 正确处理缺少深度数据的情况")
    
    def test_assemble_detection_with_none(self, test_oak_module_config, event_bus):
        """测试 16: 组装检测数据时数据为 None"""
        collector = OAKDataCollector(
            config=test_oak_module_config,
            event_bus=event_bus
        )
        
        binding = test_oak_module_config.role_bindings[DeviceRole.LEFT_CAMERA]
        
        # 检测数据为 None
        detection_dto = collector._assemble_detection_data(
            device_binding=binding,
            detections_data=None,
            frame_id=100
        )
        
        # 应该返回 None
        assert detection_dto is None
        
        print("✅ 正确处理检测数据为 None 的情况")


# ==================== 主测试函数 ====================

if __name__ == "__main__":
    """直接运行测试"""
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
