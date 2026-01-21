"""DataProcessor 集成测试

测试 DataProcessor 模块的完整数据流：
- 外部发布检测数据事件
- DataProcessor 订阅并处理数据
- 处理后发布事件
- 外部订阅者接收处理后的数据
"""

import pytest
import time
import threading
import numpy as np

from oak_vision_system.core.dto.config_dto import (
    DataProcessingConfigDTO,
    FilterConfigDTO,
    CoordinateTransformConfigDTO,
)
from oak_vision_system.core.dto.config_dto.device_binding_dto import (
    DeviceMetadataDTO,
    DeviceRoleBindingDTO,
)
from oak_vision_system.core.dto.config_dto.enums import DeviceRole, ConnectionStatus
from oak_vision_system.core.dto.detection_dto import (
    DeviceDetectionDataDTO,
    DetectionDTO,
    SpatialCoordinatesDTO,
    BoundingBoxDTO,
)
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.event_bus import get_event_bus, reset_event_bus
from oak_vision_system.core.event_bus.event_types import EventType
from oak_vision_system.modules.data_processing.data_processor import DataProcessor


class DataProcessorIntegrationTestHelper:
    """集成测试辅助类 - 模拟外部环境"""
    
    def __init__(self):
        """初始化测试辅助类"""
        self.received_data = []
        self.event_bus = get_event_bus()
        self.subscription_id = None
        self.lock = threading.Lock()
    
    def subscribe_processed_data(self):
        """订阅处理后的数据（模拟下游模块）"""
        self.subscription_id = self.event_bus.subscribe(
            EventType.PROCESSED_DATA,
            self._on_data_received
        )
    
    def unsubscribe_processed_data(self):
        """取消订阅"""
        if self.subscription_id:
            self.event_bus.unsubscribe(self.subscription_id)
            self.subscription_id = None
    
    def _on_data_received(self, data: DeviceProcessedDataDTO):
        """接收数据回调"""
        with self.lock:
            self.received_data.append(data)
    
    def publish_detection_data(self, data: DeviceDetectionDataDTO):
        """发布检测数据（模拟上游模块）"""
        self.event_bus.publish(
            EventType.RAW_DETECTION_DATA,
            data,
            wait_all=False
        )
    
    def wait_for_data(self, count: int, timeout: float = 5.0) -> list:
        """等待接收指定数量的数据
        
        Args:
            count: 期望接收的数据数量
            timeout: 超时时间（秒）
            
        Returns:
            list: 接收到的数据列表
            
        Raises:
            TimeoutError: 等待超时
        """
        start = time.time()
        while True:
            with self.lock:
                if len(self.received_data) >= count:
                    return self.received_data[:count]
            
            if time.time() - start > timeout:
                with self.lock:
                    actual_count = len(self.received_data)
                raise TimeoutError(
                    f"等待数据超时: 期望 {count} 条，实际接收 {actual_count} 条"
                )
            
            time.sleep(0.05)  # 50ms 轮询间隔
    
    def clear_received_data(self):
        """清空接收到的数据"""
        with self.lock:
            self.received_data.clear()
    
    @staticmethod
    def create_test_config() -> DataProcessingConfigDTO:
        """创建测试配置"""
        # 为测试设备创建恒等变换配置（所有参数为0，相当于恒等变换）
        coordinate_transforms = {
            DeviceRole.LEFT_CAMERA: CoordinateTransformConfigDTO(
                role=DeviceRole.LEFT_CAMERA,
                translation_x=0.0,
                translation_y=0.0,
                translation_z=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
            ),
            DeviceRole.RIGHT_CAMERA: CoordinateTransformConfigDTO(
                role=DeviceRole.RIGHT_CAMERA,
                translation_x=0.0,
                translation_y=0.0,
                translation_z=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
            ),
        }
        
        return DataProcessingConfigDTO(
            coordinate_transforms=coordinate_transforms,
            filter_config=FilterConfigDTO(),  # 使用默认滤波配置
        )
    
    @staticmethod
    def create_device_metadata() -> dict:
        """创建设备元数据"""
        return {
            "device_001_mxid_12345": DeviceMetadataDTO(
                mxid="device_001_mxid_12345",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
            "device_002_mxid_67890": DeviceMetadataDTO(
                mxid="device_002_mxid_67890",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
    
    @staticmethod
    def create_bindings() -> dict:
        """创建设备角色绑定"""
        return {
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="device_001_mxid_12345",
            ),
            DeviceRole.RIGHT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.RIGHT_CAMERA,
                active_mxid="device_002_mxid_67890",
            ),
        }
    
    @staticmethod
    def create_detection_data(
        device_id: str = "device_001_mxid_12345",
        frame_id: int = 100,
        device_alias: str = "front_camera",
        num_detections: int = 2,
    ) -> DeviceDetectionDataDTO:
        """创建模拟检测数据
        
        Args:
            device_id: 设备ID
            frame_id: 帧ID
            device_alias: 设备别名
            num_detections: 检测结果数量
            
        Returns:
            DeviceDetectionDataDTO: 检测数据
        """
        detections = [
            DetectionDTO(
                label=i % 2,  # 交替使用两个标签
                confidence=0.9 - i * 0.05,
                bbox=BoundingBoxDTO(
                    xmin=float(10 + i * 40),
                    ymin=float(20 + i * 40),
                    xmax=float(100 + i * 40),
                    ymax=float(200 + i * 40),
                ),
                spatial_coordinates=SpatialCoordinatesDTO(
                    x=float(100 + i * 300),
                    y=float(200 + i * 300),
                    z=float(300 + i * 300),
                ),
            )
            for i in range(num_detections)
        ]
        
        return DeviceDetectionDataDTO(
            device_id=device_id,
            frame_id=frame_id,
            device_alias=device_alias,
            detections=detections,
        )


class TestDataProcessorIntegration:
    """DataProcessor 集成测试"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @pytest.fixture
    def helper(self):
        """创建测试辅助类"""
        return DataProcessorIntegrationTestHelper()
    
    @pytest.fixture
    def processor(self, helper):
        """创建 DataProcessor 实例"""
        processor = DataProcessor(
            config=helper.create_test_config(),
            device_metadata=helper.create_device_metadata(),
            bindings=helper.create_bindings(),
            label_map=["durian", "person"],
            queue_size=10,
        )
        yield processor
        # 清理：停止处理器
        if processor.is_running:
            processor.shutdown()
    
    def test_basic_data_flow(self, processor, helper):
        """测试基本数据流：发布 → 处理 → 接收"""
        # 1. 订阅处理后的数据
        helper.subscribe_processed_data()
        
        # 2. 启动 DataProcessor
        assert processor.start(), "DataProcessor 应该成功启动"
        assert processor.is_running, "DataProcessor 应该处于运行状态"
        
        # 3. 发布检测数据
        detection_data = helper.create_detection_data(
            device_id="device_001_mxid_12345",
            frame_id=100,
            num_detections=2,
        )
        helper.publish_detection_data(detection_data)
        
        # 4. 等待接收处理后的数据
        received = helper.wait_for_data(count=1, timeout=3.0)
        
        # 5. 验证接收到的数据
        assert len(received) == 1, "应该接收到 1 条处理后的数据"
        
        result = received[0]
        assert isinstance(result, DeviceProcessedDataDTO)
        assert result.device_id == detection_data.device_id
        assert result.frame_id == detection_data.frame_id
        assert result.device_alias == detection_data.device_alias
        assert result.coords.shape[0] == 2, "应该有 2 个检测结果"
        assert result.bbox.shape[0] == 2
        assert result.confidence.shape[0] == 2
        assert result.labels.shape[0] == 2
        
        # 6. 停止 DataProcessor
        assert processor.stop(), "DataProcessor 应该成功停止"
        assert not processor.is_running, "DataProcessor 应该停止运行"
    
    def test_multiple_frames(self, processor, helper):
        """测试多帧处理"""
        # 1. 订阅处理后的数据
        helper.subscribe_processed_data()
        
        # 2. 启动 DataProcessor
        processor.start()
        
        # 3. 发布多帧检测数据
        num_frames = 5
        for i in range(num_frames):
            detection_data = helper.create_detection_data(
                device_id="device_001_mxid_12345",
                frame_id=100 + i,
                num_detections=2,
            )
            helper.publish_detection_data(detection_data)
            time.sleep(0.01)  # 短暂延迟，模拟真实场景
        
        # 4. 等待接收所有处理后的数据
        received = helper.wait_for_data(count=num_frames, timeout=5.0)
        
        # 5. 验证接收到的数据
        assert len(received) == num_frames, f"应该接收到 {num_frames} 条处理后的数据"
        
        # 验证帧ID递增
        for i, result in enumerate(received):
            assert result.frame_id == 100 + i, f"第 {i} 帧的 frame_id 应该是 {100 + i}"
            assert result.coords.shape[0] == 2, "每帧应该有 2 个检测结果"
        
        # 6. 停止 DataProcessor
        processor.stop()
    
    def test_empty_detection_handling(self, processor, helper):
        """测试空检测数据处理（应该跳过，不发布事件）"""
        # 1. 订阅处理后的数据
        helper.subscribe_processed_data()
        
        # 2. 启动 DataProcessor
        processor.start()
        
        # 3. 发布空检测数据
        empty_detection_data = helper.create_detection_data(
            device_id="device_001_mxid_12345",
            frame_id=100,
            num_detections=0,  # 空检测
        )
        helper.publish_detection_data(empty_detection_data)
        
        # 4. 发布正常检测数据（用于验证处理器仍在工作）
        normal_detection_data = helper.create_detection_data(
            device_id="device_001_mxid_12345",
            frame_id=101,
            num_detections=2,
        )
        helper.publish_detection_data(normal_detection_data)
        
        # 5. 等待接收数据
        received = helper.wait_for_data(count=1, timeout=3.0)
        
        # 6. 验证只接收到正常数据，空数据被跳过
        assert len(received) == 1, "应该只接收到 1 条数据（空数据被跳过）"
        assert received[0].frame_id == 101, "接收到的应该是正常数据"
        assert received[0].coords.shape[0] == 2, "正常数据应该有 2 个检测结果"
        
        # 7. 停止 DataProcessor
        processor.stop()
    
    def test_thread_lifecycle(self, processor, helper):
        """测试线程生命周期：启动 → 运行 → 停止"""
        # 1. 初始状态
        assert not processor.is_running, "初始状态应该未运行"
        
        # 2. 启动
        assert processor.start(), "应该成功启动"
        assert processor.is_running, "启动后应该处于运行状态"
        
        # 3. 重复启动应该失败
        assert not processor.start(), "重复启动应该返回 False"
        
        # 4. 验证处理器正常工作
        helper.subscribe_processed_data()
        detection_data = helper.create_detection_data(num_detections=1)
        helper.publish_detection_data(detection_data)
        received = helper.wait_for_data(count=1, timeout=3.0)
        assert len(received) == 1, "处理器应该正常工作"
        
        # 5. 停止
        assert processor.stop(), "应该成功停止"
        assert not processor.is_running, "停止后应该不再运行"
        
        # 6. 重复停止应该成功（幂等操作）
        assert processor.stop(), "重复停止应该返回 True"
        
        # 7. 可以重新启动
        assert processor.start(), "应该可以重新启动"
        assert processor.is_running, "重新启动后应该处于运行状态"
        processor.stop()
    
    def test_shutdown_vs_stop(self, processor, helper):
        """测试 shutdown 与 stop 的区别"""
        # 1. 启动处理器
        processor.start()
        
        # 2. 使用 stop（保持事件订阅）
        processor.stop()
        assert not processor.is_running
        
        # 3. 重新启动后仍然可以接收事件
        processor.start()
        helper.subscribe_processed_data()
        detection_data = helper.create_detection_data(num_detections=1)
        helper.publish_detection_data(detection_data)
        received = helper.wait_for_data(count=1, timeout=3.0)
        assert len(received) == 1, "stop 后重启应该仍能接收事件"
        
        # 4. 使用 shutdown（取消事件订阅）
        processor.shutdown()
        assert not processor.is_running
        
        # 注意：shutdown 后不应该重新启动，因为事件订阅已取消
        # 这是设计上的限制，shutdown 表示完全关闭
    
    def test_queue_stats(self, processor, helper):
        """测试队列统计信息"""
        # 1. 启动处理器
        processor.start()
        
        # 2. 获取初始统计信息
        stats = processor.get_stats()
        assert stats["is_running"] is True
        assert "queue_stats" in stats
        assert stats["queue_stats"]["size"] == 0, "初始队列应该为空"
        assert stats["queue_stats"]["drop_count"] == 0, "初始溢出计数应该为 0"
        
        # 3. 发布数据
        helper.subscribe_processed_data()
        for i in range(3):
            detection_data = helper.create_detection_data(frame_id=100 + i)
            helper.publish_detection_data(detection_data)
        
        # 4. 等待处理完成
        helper.wait_for_data(count=3, timeout=3.0)
        
        # 5. 验证统计信息
        stats = processor.get_stats()
        assert stats["queue_stats"]["drop_count"] == 0, "正常情况下不应该有溢出"
        
        # 6. 重置统计信息
        processor.reset_stats()
        stats = processor.get_stats()
        assert stats["queue_stats"]["drop_count"] == 0, "重置后溢出计数应该为 0"
        
        # 7. 停止处理器
        processor.stop()
    
    def test_different_devices(self, processor, helper):
        """测试不同设备的数据处理"""
        # 1. 订阅处理后的数据
        helper.subscribe_processed_data()
        
        # 2. 启动 DataProcessor
        processor.start()
        
        # 3. 发布来自不同设备的数据
        device_ids = ["device_001_mxid_12345", "device_002_mxid_67890"]
        for i, device_id in enumerate(device_ids):
            detection_data = helper.create_detection_data(
                device_id=device_id,
                frame_id=100 + i,
                device_alias=f"camera_{i}",
                num_detections=2,
            )
            helper.publish_detection_data(detection_data)
        
        # 4. 等待接收所有处理后的数据
        received = helper.wait_for_data(count=2, timeout=3.0)
        
        # 5. 验证不同设备的数据都被正确处理
        assert len(received) == 2
        received_device_ids = {r.device_id for r in received}
        assert received_device_ids == set(device_ids), "应该接收到来自两个设备的数据"
        
        # 6. 停止 DataProcessor
        processor.stop()
    
    def test_data_correctness(self, processor, helper):
        """测试数据处理的正确性（坐标、边界框、置信度等）"""
        # 1. 订阅处理后的数据
        helper.subscribe_processed_data()
        
        # 2. 启动 DataProcessor
        processor.start()
        
        # 3. 创建已知的检测数据
        detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="test_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.95,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
            ],
        )
        helper.publish_detection_data(detection_data)
        
        # 4. 等待接收处理后的数据
        received = helper.wait_for_data(count=1, timeout=3.0)
        result = received[0]
        
        # 5. 验证数据正确性
        assert result.coords.shape == (1, 3), "应该有 1 个检测结果的坐标"
        assert result.bbox.shape == (1, 4), "应该有 1 个检测结果的边界框"
        assert result.confidence.shape == (1,), "应该有 1 个检测结果的置信度"
        assert result.labels.shape == (1,), "应该有 1 个检测结果的标签"
        
        # 验证标签和置信度保持不变（滤波不改变这些值）
        assert result.labels[0] == 0, "标签应该保持不变"
        # 注意：置信度可能被滤波器修改，这里只验证范围
        assert 0.0 <= result.confidence[0] <= 1.0, "置信度应该在有效范围内"
        
        # 验证边界框保持不变（滤波不改变边界框）
        np.testing.assert_array_almost_equal(
            result.bbox[0],
            [10.0, 20.0, 100.0, 200.0],
            decimal=2,
            err_msg="边界框应该保持不变"
        )
        
        # 验证坐标有效（不验证具体值，因为有 OAK 手性变换）
        assert not np.isnan(result.coords[0]).any(), "坐标不应该包含 NaN"
        assert not np.isinf(result.coords[0]).any(), "坐标不应该包含 Inf"
        
        # 6. 停止 DataProcessor
        processor.stop()
