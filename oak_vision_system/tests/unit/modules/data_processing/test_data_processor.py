"""DataProcessor 单元测试

测试 DataProcessor 的初始化、数据处理和事件发布功能。
"""

import pytest
import numpy as np

from oak_vision_system.core.dto.config_dto import DataProcessingConfigDTO, FilterConfigDTO
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


class TestDataProcessorInit:
    """测试 DataProcessor 初始化"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @pytest.fixture
    def valid_config(self):
        """有效的配置对象"""
        return DataProcessingConfigDTO(
            coordinate_transforms={},
            filter_config=FilterConfigDTO(),
        )
    
    @pytest.fixture
    def valid_device_metadata(self):
        """有效的设备元数据"""
        return {
            "device_001": DeviceMetadataDTO(
                mxid="device_001_mxid_12345",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
            "device_002": DeviceMetadataDTO(
                mxid="device_002_mxid_67890",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
    
    @pytest.fixture
    def valid_bindings(self):
        """有效的设备角色绑定"""
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
    
    def test_init_with_valid_config(self, valid_config, valid_device_metadata, valid_bindings):
        """测试使用有效配置初始化"""
        # Act
        processor = DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
        
        # Assert
        assert processor is not None
        assert processor._config == valid_config
        assert processor._device_metadata == valid_device_metadata
        assert processor._transformer is not None
        assert processor._filter_manager is not None
        assert processor._event_bus is not None
    
    def test_init_with_none_config(self, valid_device_metadata, valid_bindings):
        """测试 config 为 None 时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="config 不能为 None"):
            DataProcessor(
                config=None,
                device_metadata=valid_device_metadata,
                bindings=valid_bindings,
            )
    
    def test_init_with_none_device_metadata(self, valid_config, valid_bindings):
        """测试 device_metadata 为 None 时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="device_metadata 不能为 None 或空字典"):
            DataProcessor(
                config=valid_config,
                device_metadata=None,
                bindings=valid_bindings,
            )
    
    def test_init_with_empty_device_metadata(self, valid_config, valid_bindings):
        """测试 device_metadata 为空字典时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="device_metadata 不能为 None 或空字典"):
            DataProcessor(
                config=valid_config,
                device_metadata={},
                bindings=valid_bindings,
            )
    
    def test_init_creates_transformer(self, valid_config, valid_device_metadata, valid_bindings):
        """测试初始化时创建 CoordinateTransformer 实例"""
        # Act
        processor = DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
        
        # Assert
        assert processor._transformer is not None
        assert hasattr(processor._transformer, 'transform_coordinates')
    
    def test_init_creates_filter_manager(self, valid_config, valid_device_metadata, valid_bindings):
        """测试初始化时创建 FilterManager 实例"""
        # Act
        processor = DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
        
        # Assert
        assert processor._filter_manager is not None
        assert hasattr(processor._filter_manager, 'process')
    
    def test_init_gets_event_bus(self, valid_config, valid_device_metadata, valid_bindings):
        """测试初始化时获取 EventBus 实例"""
        # Act
        processor = DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
        
        # Assert
        assert processor._event_bus is not None
        assert processor._event_bus == get_event_bus()
    
    def test_init_stores_config_parameters(self, valid_config, valid_device_metadata, valid_bindings):
        """测试初始化时正确存储配置参数"""
        # Act
        processor = DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
        
        # Assert
        assert processor._config is valid_config
        assert processor._device_metadata is valid_device_metadata


class TestDataProcessorExtraction:
    """测试 DataProcessor 数据提取功能"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @pytest.fixture
    def valid_config(self):
        """有效的配置对象"""
        return DataProcessingConfigDTO(
            coordinate_transforms={},
            filter_config=FilterConfigDTO(),
        )
    
    @pytest.fixture
    def valid_device_metadata(self):
        """有效的设备元数据"""
        return {
            "device_001": DeviceMetadataDTO(
                mxid="device_001_mxid_12345",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
    
    @pytest.fixture
    def valid_bindings(self):
        """有效的设备角色绑定"""
        return {
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="device_001_mxid_12345",
            ),
        }
    
    @pytest.fixture
    def processor(self, valid_config, valid_device_metadata, valid_bindings):
        """创建 DataProcessor 实例"""
        return DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
    
    @pytest.fixture
    def sample_detections(self):
        """创建示例检测数据"""
        return [
            DetectionDTO(
                label=0,
                confidence=0.9,
                bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
            ),
            DetectionDTO(
                label=1,
                confidence=0.8,
                bbox=BoundingBoxDTO(xmin=50.0, ymin=60.0, xmax=150.0, ymax=250.0),
                spatial_coordinates=SpatialCoordinatesDTO(x=400.0, y=500.0, z=600.0),
            ),
            DetectionDTO(
                label=0,
                confidence=0.75,
                bbox=BoundingBoxDTO(xmin=30.0, ymin=40.0, xmax=120.0, ymax=220.0),
                spatial_coordinates=SpatialCoordinatesDTO(x=700.0, y=800.0, z=900.0),
            ),
        ]
    
    def test_extract_arrays_from_detections(self, processor, sample_detections):
        """测试从 DetectionDTO 列表提取数组"""
        # Act
        coords, bboxes, confidences, labels = processor._extract_arrays(sample_detections)
        
        # Assert - 验证返回的是 NumPy 数组
        assert isinstance(coords, np.ndarray)
        assert isinstance(bboxes, np.ndarray)
        assert isinstance(confidences, np.ndarray)
        assert isinstance(labels, np.ndarray)
        
        # 验证数组长度
        assert len(coords) == 3
        assert len(bboxes) == 3
        assert len(confidences) == 3
        assert len(labels) == 3
    
    def test_extract_arrays_correct_shapes(self, processor, sample_detections):
        """测试数组形状正确"""
        # Act
        coords, bboxes, confidences, labels = processor._extract_arrays(sample_detections)
        
        # Assert
        assert coords.shape == (3, 4)  # (n, 4) for x, y, z, 1 (齐次坐标)
        assert bboxes.shape == (3, 4)  # (n, 4) for xmin, ymin, xmax, ymax
        assert confidences.shape == (3,)  # (n,)
        assert labels.shape == (3,)  # (n,)
    
    def test_extract_arrays_correct_dtypes(self, processor, sample_detections):
        """测试数组 dtype 正确"""
        # Act
        coords, bboxes, confidences, labels = processor._extract_arrays(sample_detections)
        
        # Assert
        assert coords.dtype == np.float32
        assert bboxes.dtype == np.float32
        assert confidences.dtype == np.float32
        assert labels.dtype == np.int32
    
    def test_extract_arrays_correct_values(self, processor, sample_detections):
        """测试数组元素对应关系和值正确"""
        # Act
        coords, bboxes, confidences, labels = processor._extract_arrays(sample_detections)
        
        # Assert - 验证第一个检测结果
        np.testing.assert_array_almost_equal(coords[0], [100.0, 200.0, 300.0, 1.0])
        np.testing.assert_array_almost_equal(bboxes[0], [10.0, 20.0, 100.0, 200.0])
        assert confidences[0] == pytest.approx(0.9)
        assert labels[0] == 0
        
        # 验证第二个检测结果
        np.testing.assert_array_almost_equal(coords[1], [400.0, 500.0, 600.0, 1.0])
        np.testing.assert_array_almost_equal(bboxes[1], [50.0, 60.0, 150.0, 250.0])
        assert confidences[1] == pytest.approx(0.8)
        assert labels[1] == 1
        
        # 验证第三个检测结果
        np.testing.assert_array_almost_equal(coords[2], [700.0, 800.0, 900.0, 1.0])
        np.testing.assert_array_almost_equal(bboxes[2], [30.0, 40.0, 120.0, 220.0])
        assert confidences[2] == pytest.approx(0.75)
        assert labels[2] == 0
    
    def test_extract_arrays_empty_input(self, processor):
        """测试空输入处理"""
        # Act
        coords, bboxes, confidences, labels = processor._extract_arrays([])
        
        # Assert - 验证返回空数组
        assert isinstance(coords, np.ndarray)
        assert isinstance(bboxes, np.ndarray)
        assert isinstance(confidences, np.ndarray)
        assert isinstance(labels, np.ndarray)
        
        # 验证形状
        assert coords.shape == (0, 4)  # 齐次坐标
        assert bboxes.shape == (0, 4)
        assert confidences.shape == (0,)
        assert labels.shape == (0,)
        
        # 验证 dtype
        assert coords.dtype == np.float32
        assert bboxes.dtype == np.float32
        assert confidences.dtype == np.float32
        assert labels.dtype == np.int32
    
    def test_extract_arrays_single_detection(self, processor):
        """测试单个检测结果"""
        # Arrange
        single_detection = [
            DetectionDTO(
                label=1,
                confidence=0.95,
                bbox=BoundingBoxDTO(xmin=5.0, ymin=10.0, xmax=50.0, ymax=100.0),
                spatial_coordinates=SpatialCoordinatesDTO(x=10.0, y=20.0, z=30.0),
            ),
        ]
        
        # Act
        coords, bboxes, confidences, labels = processor._extract_arrays(single_detection)
        
        # Assert
        assert coords.shape == (1, 4)  # 齐次坐标
        assert bboxes.shape == (1, 4)
        assert confidences.shape == (1,)
        assert labels.shape == (1,)
        
        np.testing.assert_array_almost_equal(coords[0], [10.0, 20.0, 30.0, 1.0])
        np.testing.assert_array_almost_equal(bboxes[0], [5.0, 10.0, 50.0, 100.0])
        assert confidences[0] == pytest.approx(0.95)
        assert labels[0] == 1
    
    def test_extract_arrays_preserves_order(self, processor, sample_detections):
        """测试数组元素对应关系保持一致"""
        # Act
        coords, bboxes, confidences, labels = processor._extract_arrays(sample_detections)
        
        # Assert - 验证每个索引对应同一个检测结果
        for i, detection in enumerate(sample_detections):
            # 验证坐标（齐次坐标）
            expected_coords = [
                detection.spatial_coordinates.x,
                detection.spatial_coordinates.y,
                detection.spatial_coordinates.z,
                1.0,  # 齐次坐标的第四维
            ]
            np.testing.assert_array_almost_equal(coords[i], expected_coords)
            
            # 验证边界框
            expected_bbox = [
                detection.bbox.xmin,
                detection.bbox.ymin,
                detection.bbox.xmax,
                detection.bbox.ymax,
            ]
            np.testing.assert_array_almost_equal(bboxes[i], expected_bbox)
            
            # 验证置信度和标签
            assert confidences[i] == pytest.approx(detection.confidence)
            assert labels[i] == detection.label


class TestDataProcessorTransform:
    """测试 DataProcessor 坐标变换集成"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @pytest.fixture
    def valid_config(self):
        """有效的配置对象"""
        return DataProcessingConfigDTO(
            coordinate_transforms={},
            filter_config=FilterConfigDTO(),
        )
    
    @pytest.fixture
    def valid_device_metadata(self):
        """有效的设备元数据"""
        return {
            "device_001": DeviceMetadataDTO(
                mxid="device_001_mxid_12345",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
    

    @pytest.fixture
    def valid_bindings(self):
        """有效的设备角色绑定"""
        return {
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="device_001_mxid_12345",
            ),
        }

    @pytest.fixture
    def processor(self, valid_config, valid_device_metadata, valid_bindings):
        """创建 DataProcessor 实例"""
        return DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
    
    @pytest.fixture
    def sample_detection_data(self):
        """创建示例检测数据"""
        return DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
                DetectionDTO(
                    label=1,
                    confidence=0.8,
                    bbox=BoundingBoxDTO(xmin=50.0, ymin=60.0, xmax=150.0, ymax=250.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=400.0, y=500.0, z=600.0),
                ),
            ],
        )
    
    def test_transform_is_called(self, processor, sample_detection_data, monkeypatch):
        """测试坐标变换正确调用"""
        # Arrange
        transform_called = {"called": False, "mxid": None, "coords": None}
        
        def mock_transform_coordinates(mxid, coords_homogeneous):
            transform_called["called"] = True
            transform_called["mxid"] = mxid
            transform_called["coords"] = coords_homogeneous
            # 返回变换后的坐标（简单地将坐标乘以2作为变换）
            # coords_homogeneous 形状为 (N, 4)，返回 (N, 3)
            return coords_homogeneous[:, :3] * 2
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Mock FilterManager.process to avoid actual filtering
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert
        assert transform_called["called"], "坐标变换方法应该被调用"
        assert transform_called["mxid"] == sample_detection_data.device_id
        # 验证传入的是齐次坐标数组
        assert isinstance(transform_called["coords"], np.ndarray)
        assert transform_called["coords"].shape == (2, 4)  # 2个检测，齐次坐标
    
    def test_transformed_coords_differ_from_original(self, processor, sample_detection_data, monkeypatch):
        """测试变换后坐标与原始坐标不同"""
        # Arrange
        original_coords = np.array([
            [d.spatial_coordinates.x, d.spatial_coordinates.y, d.spatial_coordinates.z]
            for d in sample_detection_data.detections
        ], dtype=np.float32)
        
        # Mock transformer to return transformed coordinates (multiply by 2)
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return coords_homogeneous[:, :3] * 2
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Mock FilterManager.process to return coords unchanged
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert - 验证输出坐标与原始坐标不同
        assert not np.allclose(result.coords, original_coords), \
            "变换后的坐标应该与原始坐标不同"
        
        # 验证变换后的坐标是原始坐标的2倍
        expected_coords = original_coords * 2
        np.testing.assert_array_almost_equal(result.coords, expected_coords)
    
    def test_transform_exception_propagation(self, processor, sample_detection_data, monkeypatch):
        """测试坐标变换异常传播"""
        # Arrange
        def mock_transform_coordinates(mxid, coords_homogeneous):
            raise RuntimeError("坐标变换失败")
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="坐标变换失败"):
            processor.process(sample_detection_data)
    
    def test_transform_with_empty_detections(self, processor, monkeypatch):
        """测试空检测列表不调用坐标变换"""
        # Arrange
        empty_detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[],
        )
        
        transform_called = {"called": False}
        
        def mock_transform_coordinates(mxid, coords_homogeneous):
            transform_called["called"] = True
            return np.empty((0, 3), dtype=np.float32)
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Act
        result = processor.process(empty_detection_data)
        
        # Assert
        assert not transform_called["called"], "空检测列表不应该调用坐标变换"
        # 更新：空检测列表应该返回空的 DeviceProcessedDataDTO，而不是 None
        assert isinstance(result, DeviceProcessedDataDTO), "空检测列表应该返回 DeviceProcessedDataDTO"
        assert len(result.labels) == 0, "空检测列表的 labels 应该为空"
    
    def test_transform_receives_correct_device_id(self, processor, sample_detection_data, monkeypatch):
        """测试坐标变换接收正确的 device_id"""
        # Arrange
        received_device_id = {"value": None}
        
        def mock_transform_coordinates(mxid, coords_homogeneous):
            received_device_id["value"] = mxid
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Mock FilterManager.process
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert
        assert received_device_id["value"] == sample_detection_data.device_id
    
    def test_transform_receives_correct_detections(self, processor, sample_detection_data, monkeypatch):
        """测试坐标变换接收正确的 detections 列表"""
        # Arrange
        received_coords = {"value": None}
        
        def mock_transform_coordinates(mxid, coords_homogeneous):
            received_coords["value"] = coords_homogeneous
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Mock FilterManager.process
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert
        # 验证传入的是齐次坐标数组
        assert isinstance(received_coords["value"], np.ndarray)
        assert received_coords["value"].shape == (2, 4)  # 2个检测，齐次坐标


class TestDataProcessorFilter:
    """测试 DataProcessor 滤波处理集成"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @pytest.fixture
    def valid_config(self):
        """有效的配置对象"""
        return DataProcessingConfigDTO(
            coordinate_transforms={},
            filter_config=FilterConfigDTO(),
        )
    
    @pytest.fixture
    def valid_device_metadata(self):
        """有效的设备元数据"""
        return {
            "device_001": DeviceMetadataDTO(
                mxid="device_001_mxid_12345",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
    

    @pytest.fixture
    def valid_bindings(self):
        """有效的设备角色绑定"""
        return {
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="device_001_mxid_12345",
            ),
        }

    @pytest.fixture
    def processor(self, valid_config, valid_device_metadata, valid_bindings):
        """创建 DataProcessor 实例"""
        return DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
    
    @pytest.fixture
    def sample_detection_data(self):
        """创建示例检测数据"""
        return DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
                DetectionDTO(
                    label=1,
                    confidence=0.8,
                    bbox=BoundingBoxDTO(xmin=50.0, ymin=60.0, xmax=150.0, ymax=250.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=400.0, y=500.0, z=600.0),
                ),
            ],
        )
    
    def test_filter_is_called(self, processor, sample_detection_data, monkeypatch):
        """测试滤波处理正确调用"""
        # Arrange
        filter_called = {"called": False, "device_id": None, "coords": None, "bboxes": None, "confidences": None, "labels": None}
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            filter_called["called"] = True
            filter_called["device_id"] = device_id
            filter_called["coords"] = coordinates
            filter_called["bboxes"] = bboxes
            filter_called["confidences"] = confidences
            filter_called["labels"] = labels
            # 返回相同的数据（不做修改）
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Mock transformer to return transformed coordinates
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return coords_homogeneous[:, :3] * 2
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert
        assert filter_called["called"], "滤波处理方法应该被调用"
        assert filter_called["device_id"] == sample_detection_data.device_id
        assert filter_called["coords"] is not None
        assert filter_called["bboxes"] is not None
        assert filter_called["confidences"] is not None
        assert filter_called["labels"] is not None
    
    def test_filter_receives_transformed_coords(self, processor, sample_detection_data, monkeypatch):
        """测试滤波处理接收变换后的坐标"""
        # Arrange
        received_coords = {"value": None}
        
        # Mock transformer to return transformed coordinates (multiply by 2)
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return coords_homogeneous[:, :3] * 2
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Mock filter to capture received coordinates
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            received_coords["value"] = coordinates.copy()
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert - 验证滤波器接收到的是变换后的坐标
        expected_coords = np.array([
            [d.spatial_coordinates.x * 2, d.spatial_coordinates.y * 2, d.spatial_coordinates.z * 2]
            for d in sample_detection_data.detections
        ], dtype=np.float32)
        
        np.testing.assert_array_almost_equal(received_coords["value"], expected_coords)
    
    def test_filter_receives_correct_device_id(self, processor, sample_detection_data, monkeypatch):
        """测试滤波处理接收正确的 device_id"""
        # Arrange
        received_device_id = {"value": None}
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            received_device_id["value"] = device_id
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Mock transformer
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert
        assert received_device_id["value"] == sample_detection_data.device_id
    
    def test_filter_receives_correct_arrays(self, processor, sample_detection_data, monkeypatch):
        """测试滤波处理接收正确的数组参数"""
        # Arrange
        received_data = {"bboxes": None, "confidences": None, "labels": None}
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            received_data["bboxes"] = bboxes.copy()
            received_data["confidences"] = confidences.copy()
            received_data["labels"] = labels.copy()
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Mock transformer
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert - 验证边界框
        expected_bboxes = np.array([
            [10.0, 20.0, 100.0, 200.0],
            [50.0, 60.0, 150.0, 250.0],
        ], dtype=np.float32)
        np.testing.assert_array_almost_equal(received_data["bboxes"], expected_bboxes)
        
        # 验证置信度
        expected_confidences = np.array([0.9, 0.8], dtype=np.float32)
        np.testing.assert_array_almost_equal(received_data["confidences"], expected_confidences)
        
        # 验证标签
        expected_labels = np.array([0, 1], dtype=np.int32)
        np.testing.assert_array_equal(received_data["labels"], expected_labels)
    
    def test_filter_output_is_used(self, processor, sample_detection_data, monkeypatch):
        """测试滤波后数据正确接收"""
        # Arrange
        # Mock transformer
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return coords_homogeneous[:, :3] * 2
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Mock filter to return modified data
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            # 修改坐标（乘以 0.5）
            filtered_coords = coordinates * 0.5
            # 修改置信度（乘以 0.9）
            filtered_confidences = confidences * 0.9
            return filtered_coords, bboxes, filtered_confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert - 验证输出使用了滤波后的数据
        # 原始坐标 * 2 (变换) * 0.5 (滤波) = 原始坐标
        expected_coords = np.array([
            [d.spatial_coordinates.x, d.spatial_coordinates.y, d.spatial_coordinates.z]
            for d in sample_detection_data.detections
        ], dtype=np.float32)
        np.testing.assert_array_almost_equal(result.coords, expected_coords)
        
        # 验证置信度被修改
        expected_confidences = np.array([0.9 * 0.9, 0.8 * 0.9], dtype=np.float32)
        np.testing.assert_array_almost_equal(result.confidence, expected_confidences)
    
    def test_filter_exception_propagation(self, processor, sample_detection_data, monkeypatch):
        """测试滤波处理异常传播"""
        # Arrange
        # Mock transformer
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Mock filter to raise exception
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            raise RuntimeError("滤波处理失败")
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="滤波处理失败"):
            processor.process(sample_detection_data)
    
    def test_filter_with_empty_detections(self, processor, monkeypatch):
        """测试空检测列表不调用滤波处理"""
        # Arrange
        empty_detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[],
        )
        
        filter_called = {"called": False}
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            filter_called["called"] = True
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(empty_detection_data)
        
        # Assert
        assert not filter_called["called"], "空检测列表不应该调用滤波处理"
        # 更新：空检测列表应该返回空的 DeviceProcessedDataDTO，而不是 None
        assert isinstance(result, DeviceProcessedDataDTO), "空检测列表应该返回 DeviceProcessedDataDTO"
        assert len(result.labels) == 0, "空检测列表的 labels 应该为空"
    
    def test_filter_after_transform(self, processor, sample_detection_data, monkeypatch):
        """测试滤波处理在坐标变换之后执行"""
        # Arrange
        execution_order = []
        
        def mock_transform_coordinates(mxid, coords_homogeneous):
            execution_order.append("transform")
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            execution_order.append("filter")
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert
        assert execution_order == ["transform", "filter"], "滤波处理应该在坐标变换之后执行"



class TestDataProcessorAssembly:
    """测试 DataProcessor 输出数据组装功能"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @pytest.fixture
    def valid_config(self):
        """有效的配置对象"""
        return DataProcessingConfigDTO(
            coordinate_transforms={},
            filter_config=FilterConfigDTO(),
        )
    
    @pytest.fixture
    def valid_device_metadata(self):
        """有效的设备元数据"""
        return {
            "device_001": DeviceMetadataDTO(
                mxid="device_001_mxid_12345",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
    

    @pytest.fixture
    def valid_bindings(self):
        """有效的设备角色绑定"""
        return {
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="device_001_mxid_12345",
            ),
        }

    @pytest.fixture
    def processor(self, valid_config, valid_device_metadata, valid_bindings):
        """创建 DataProcessor 实例"""
        return DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
    
    @pytest.fixture
    def sample_detection_data(self):
        """创建示例检测数据"""
        return DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
                DetectionDTO(
                    label=1,
                    confidence=0.8,
                    bbox=BoundingBoxDTO(xmin=50.0, ymin=60.0, xmax=150.0, ymax=250.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=400.0, y=500.0, z=600.0),
                ),
            ],
        )
    
    def test_output_dto_type_correct(self, processor, sample_detection_data, monkeypatch):
        """测试输出 DTO 类型正确"""
        # Arrange
        # Mock transformer and filter to return simple data
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert
        assert isinstance(result, DeviceProcessedDataDTO), \
            "输出应该是 DeviceProcessedDataDTO 类型"
    
    def test_all_fields_correctly_set(self, processor, sample_detection_data, monkeypatch):
        """测试所有字段正确设置"""
        # Arrange
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert - 验证所有必需字段都已设置
        assert result.device_id is not None, "device_id 应该被设置"
        assert result.frame_id is not None, "frame_id 应该被设置"
        assert result.device_alias is not None, "device_alias 应该被设置"
        assert result.coords is not None, "coords 应该被设置"
        assert result.bbox is not None, "bbox 应该被设置"
        assert result.confidence is not None, "confidence 应该被设置"
        assert result.labels is not None, "labels 应该被设置"
        assert result.state_label is not None, "state_label 应该被设置"
    
    def test_metadata_fields_passed_correctly(self, processor, sample_detection_data, monkeypatch):
        """测试元数据字段传递正确"""
        # Arrange
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert - 验证元数据字段正确传递
        assert result.device_id == sample_detection_data.device_id, \
            "device_id 应该与输入相同"
        assert result.frame_id == sample_detection_data.frame_id, \
            "frame_id 应该与输入相同"
        assert result.device_alias == sample_detection_data.device_alias, \
            "device_alias 应该与输入相同"
    
    def test_processed_data_fields_set(self, processor, sample_detection_data, monkeypatch):
        """测试处理后的数据字段正确设置"""
        # Arrange
        # Mock transformer and filter to return specific data
        filtered_coords = np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]], dtype=np.float32)
        filtered_bboxes = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]], dtype=np.float32)
        filtered_confidences = np.array([0.95, 0.85], dtype=np.float32)
        filtered_labels = np.array([0, 1], dtype=np.int32)
        
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return filtered_coords
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return filtered_coords, filtered_bboxes, filtered_confidences, filtered_labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert - 验证处理后的数据字段
        np.testing.assert_array_almost_equal(result.coords, filtered_coords)
        np.testing.assert_array_almost_equal(result.bbox, filtered_bboxes)
        np.testing.assert_array_almost_equal(result.confidence, filtered_confidences)
        np.testing.assert_array_equal(result.labels, filtered_labels)
    
    def test_state_label_initialized_empty(self, processor, sample_detection_data, monkeypatch):
        """测试 state_label 由决策层填充"""
        # Arrange
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        # Mock decision layer to return empty list
        def mock_decide(device_id, filtered_coords, filtered_labels):
            return []
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        monkeypatch.setattr(processor._decision_layer, "decide", mock_decide)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert
        assert isinstance(result.state_label, list), "state_label 应该是列表类型"
        assert len(result.state_label) == 0, "当决策层返回空列表时，state_label 应该为空"
    
    def test_empty_output_handling(self, processor):
        """测试空输出处理"""
        # Arrange
        empty_detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[],
        )
        
        # Act
        result = processor.process(empty_detection_data)
        
        # Assert - 更新：空输入应该返回空的 DeviceProcessedDataDTO
        assert isinstance(result, DeviceProcessedDataDTO), "空输入应该返回 DeviceProcessedDataDTO"
        assert result.device_id == "device_001_mxid_12345"
        assert result.frame_id == 100
        assert len(result.labels) == 0
        assert len(result.bbox) == 0
        assert len(result.coords) == 0
        assert len(result.confidence) == 0
        assert result.state_label == []
    
    def test_empty_output_correct_dtypes(self, processor):
        """测试空输出的数组 dtype 正确"""
        # Arrange
        empty_detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=None,
        )
        
        # Act
        result = processor.process(empty_detection_data)
        
        # Assert - 更新：空输入应该返回空的 DeviceProcessedDataDTO，并验证 dtype
        assert isinstance(result, DeviceProcessedDataDTO), "空输入（detections=None）应该返回 DeviceProcessedDataDTO"
        assert result.labels.dtype == np.int32, "labels 的 dtype 应该是 int32"
        assert result.bbox.dtype == np.float32, "bbox 的 dtype 应该是 float32"
        assert result.coords.dtype == np.float32, "coords 的 dtype 应该是 float32"
        assert result.confidence.dtype == np.float32, "confidence 的 dtype 应该是 float32"
    
    def test_assemble_output_with_different_sizes(self, processor, monkeypatch):
        """测试组装不同大小的输出数据"""
        # Arrange
        # 创建包含不同数量检测结果的数据
        detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=200,
            device_alias="side_camera",
            detections=[
                DetectionDTO(
                    label=i,
                    confidence=0.9 - i * 0.1,
                    bbox=BoundingBoxDTO(xmin=float(i), ymin=float(i), xmax=float(i+10), ymax=float(i+10)),
                    spatial_coordinates=SpatialCoordinatesDTO(x=float(i*100), y=float(i*100), z=float(i*100)),
                )
                for i in range(5)  # 5个检测结果
            ],
        )
        
        # Mock transformer and filter to return data with different size (filter reduces to 3)
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            # 模拟滤波后减少到3个结果
            return coordinates[:3], bboxes[:3], confidences[:3], labels[:3]
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(detection_data)
        
        # Assert - 验证输出大小
        assert result.coords.shape[0] == 3, "coords 应该有3个结果"
        assert result.bbox.shape[0] == 3, "bbox 应该有3个结果"
        assert result.confidence.shape[0] == 3, "confidence 应该有3个结果"
        assert result.labels.shape[0] == 3, "labels 应该有3个结果"
    
    def test_assemble_output_preserves_array_correspondence(self, processor, sample_detection_data, monkeypatch):
        """测试组装输出保持数组元素对应关系"""
        # Arrange
        # Mock transformer and filter to return identifiable data
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            # 返回可识别的数据
            filtered_coords = np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]], dtype=np.float32)
            filtered_bboxes = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]], dtype=np.float32)
            filtered_confidences = np.array([0.95, 0.85], dtype=np.float32)
            filtered_labels = np.array([0, 1], dtype=np.int32)
            return filtered_coords, filtered_bboxes, filtered_confidences, filtered_labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert - 验证所有数组长度一致
        n = len(result.coords)
        assert len(result.bbox) == n, "bbox 长度应该与 coords 一致"
        assert len(result.confidence) == n, "confidence 长度应该与 coords 一致"
        assert len(result.labels) == n, "labels 长度应该与 coords 一致"
        
        # 验证每个索引对应同一个检测结果
        for i in range(n):
            # 验证第一个结果
            if i == 0:
                np.testing.assert_array_almost_equal(result.coords[i], [10.0, 20.0, 30.0])
                np.testing.assert_array_almost_equal(result.bbox[i], [1.0, 2.0, 3.0, 4.0])
                assert result.confidence[i] == pytest.approx(0.95)
                assert result.labels[i] == 0
            # 验证第二个结果
            elif i == 1:
                np.testing.assert_array_almost_equal(result.coords[i], [40.0, 50.0, 60.0])
                np.testing.assert_array_almost_equal(result.bbox[i], [5.0, 6.0, 7.0, 8.0])
                assert result.confidence[i] == pytest.approx(0.85)
                assert result.labels[i] == 1


class TestDataProcessorEvent:
    """测试 DataProcessor 事件发布功能"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @pytest.fixture
    def valid_config(self):
        """有效的配置对象"""
        return DataProcessingConfigDTO(
            coordinate_transforms={},
            filter_config=FilterConfigDTO(),
        )
    
    @pytest.fixture
    def valid_device_metadata(self):
        """有效的设备元数据"""
        return {
            "device_001": DeviceMetadataDTO(
                mxid="device_001_mxid_12345",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
    

    @pytest.fixture
    def valid_bindings(self):
        """有效的设备角色绑定"""
        return {
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="device_001_mxid_12345",
            ),
        }

    @pytest.fixture
    def processor(self, valid_config, valid_device_metadata, valid_bindings):
        """创建 DataProcessor 实例"""
        return DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
    
    @pytest.fixture
    def sample_detection_data(self):
        """创建示例检测数据"""
        return DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
                DetectionDTO(
                    label=1,
                    confidence=0.8,
                    bbox=BoundingBoxDTO(xmin=50.0, ymin=60.0, xmax=150.0, ymax=250.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=400.0, y=500.0, z=600.0),
                ),
            ],
        )
    
    def test_event_is_published(self, processor, sample_detection_data, monkeypatch):
        """测试事件正确发布"""
        # Arrange
        event_published = {"called": False, "event_type": None, "data": None, "wait_all": None}
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Mock event bus publish
        def mock_publish(event_type, data, wait_all=False):
            event_published["called"] = True
            event_published["event_type"] = event_type
            event_published["data"] = data
            event_published["wait_all"] = wait_all
            return 1  # 返回成功投递的订阅者数量
        
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert
        assert event_published["called"], "事件应该被发布"
        assert event_published["event_type"] == EventType.PROCESSED_DATA, \
            "事件类型应该是 PROCESSED_DATA"
    
    def test_event_data_is_correct(self, processor, sample_detection_data, monkeypatch):
        """测试事件数据正确"""
        # Arrange
        event_data = {"data": None}
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Mock event bus publish
        def mock_publish(event_type, data, wait_all=False):
            event_data["data"] = data
            return 1
        
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act
        result = processor.process(sample_detection_data)
        
        # Assert - 验证事件数据是 DeviceProcessedDataDTO 类型
        assert isinstance(event_data["data"], DeviceProcessedDataDTO), \
            "事件数据应该是 DeviceProcessedDataDTO 类型"
        
        # 验证事件数据与返回结果相同
        assert event_data["data"].device_id == result.device_id
        assert event_data["data"].frame_id == result.frame_id
        assert event_data["data"].device_alias == result.device_alias
        np.testing.assert_array_equal(event_data["data"].coords, result.coords)
        np.testing.assert_array_equal(event_data["data"].bbox, result.bbox)
        np.testing.assert_array_equal(event_data["data"].confidence, result.confidence)
        np.testing.assert_array_equal(event_data["data"].labels, result.labels)
    
    def test_event_uses_async_mode(self, processor, sample_detection_data, monkeypatch):
        """测试异步模式（wait_all=False）"""
        # Arrange
        publish_params = {"wait_all": None}
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Mock event bus publish
        def mock_publish(event_type, data, wait_all=False):
            publish_params["wait_all"] = wait_all
            return 1
        
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert
        assert publish_params["wait_all"] is False, \
            "事件发布应该使用异步模式（wait_all=False）"
    
    def test_event_publish_exception_does_not_raise(self, processor, sample_detection_data, monkeypatch):
        """测试事件发布异常不抛出"""
        # Arrange
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Mock event bus publish to raise exception
        def mock_publish(event_type, data, wait_all=False):
            raise RuntimeError("事件发布失败")
        
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act & Assert - 不应该抛出异常
        try:
            result = processor.process(sample_detection_data)
            # 验证仍然返回正确的结果
            assert isinstance(result, DeviceProcessedDataDTO)
            assert result.device_id == sample_detection_data.device_id
        except RuntimeError:
            pytest.fail("事件发布异常不应该被抛出")
    
    def test_event_publish_with_empty_detections(self, processor, monkeypatch):
        """测试空检测列表也会发布事件"""
        # Arrange
        empty_detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[],
        )
        
        event_published = {"called": False, "data": None}
        
        # Mock event bus publish
        def mock_publish(event_type, data, wait_all=False):
            event_published["called"] = True
            event_published["data"] = data
            return 1
        
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act
        processor.process(empty_detection_data)
        
        # Assert - 更新：空检测列表也应该发布事件（返回空的 DeviceProcessedDataDTO）
        assert event_published["called"], "空检测列表也应该发布事件"
        assert isinstance(event_published["data"], DeviceProcessedDataDTO), "发布的数据应该是 DeviceProcessedDataDTO"
        assert len(event_published["data"].labels) == 0, "发布的数据应该是空的"
    
    def test_event_published_after_processing(self, processor, sample_detection_data, monkeypatch):
        """测试事件在处理完成后发布"""
        # Arrange
        execution_order = []
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            execution_order.append("transform")
            n = len(coords_homogeneous)
            return np.zeros((n, 3), dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            execution_order.append("filter")
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Mock event bus publish
        def mock_publish(event_type, data, wait_all=False):
            execution_order.append("publish")
            return 1
        
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert
        assert execution_order == ["transform", "filter", "publish"], \
            "事件应该在处理完成后发布"
    
    def test_event_data_contains_all_fields(self, processor, sample_detection_data, monkeypatch):
        """测试事件数据包含所有必需字段"""
        # Arrange
        event_data = {"data": None}
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            filtered_coords = np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]], dtype=np.float32)
            filtered_bboxes = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]], dtype=np.float32)
            filtered_confidences = np.array([0.95, 0.85], dtype=np.float32)
            filtered_labels = np.array([0, 1], dtype=np.int32)
            return filtered_coords, filtered_bboxes, filtered_confidences, filtered_labels
        
        # Mock decision layer to return empty list
        def mock_decide(device_id, filtered_coords, filtered_labels):
            return []
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        monkeypatch.setattr(processor._decision_layer, "decide", mock_decide)
        
        # Mock event bus publish
        def mock_publish(event_type, data, wait_all=False):
            event_data["data"] = data
            return 1
        
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act
        processor.process(sample_detection_data)
        
        # Assert - 验证所有字段都存在
        data = event_data["data"]
        assert data.device_id == sample_detection_data.device_id
        assert data.frame_id == sample_detection_data.frame_id
        assert data.device_alias == sample_detection_data.device_alias
        assert data.coords.shape == (2, 3)
        assert data.bbox.shape == (2, 4)
        assert data.confidence.shape == (2,)
        assert data.labels.shape == (2,)
        # 更新：state_label 由决策层填充，这里 mock 返回空列表
        assert isinstance(data.state_label, list), "state_label 应该是列表类型"



class TestDataProcessorIntegration:
    """测试 DataProcessor 完整流程的集成测试"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    @pytest.fixture
    def valid_config(self):
        """有效的配置对象"""
        return DataProcessingConfigDTO(
            coordinate_transforms={},
            filter_config=FilterConfigDTO(),
        )
    
    @pytest.fixture
    def valid_device_metadata(self):
        """有效的设备元数据"""
        return {
            "device_001": DeviceMetadataDTO(
                mxid="device_001_mxid_12345",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
            "device_002": DeviceMetadataDTO(
                mxid="device_002_mxid_67890",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
    

    @pytest.fixture
    def valid_bindings(self):
        """有效的设备角色绑定"""
        return {
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid="device_001_mxid_12345",
            ),
        }

    @pytest.fixture
    def processor(self, valid_config, valid_device_metadata, valid_bindings):
        """创建 DataProcessor 实例"""
        return DataProcessor(
            config=valid_config,
            device_metadata=valid_device_metadata,
            bindings=valid_bindings,
            label_map=["durian", "person"],
        )
    
    def test_complete_data_processing_flow(self, processor, monkeypatch):
        """测试完整的数据处理流程：提取 → 变换 → 滤波 → 组装 → 发布"""
        # Arrange
        detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
                DetectionDTO(
                    label=1,
                    confidence=0.8,
                    bbox=BoundingBoxDTO(xmin=50.0, ymin=60.0, xmax=150.0, ymax=250.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=400.0, y=500.0, z=600.0),
                ),
            ],
        )
        
        # 跟踪执行顺序
        execution_order = []
        
        # Mock transformer - 坐标乘以2
        def mock_transform_coordinates(mxid, coords_homogeneous):
            execution_order.append("transform")
            # coords_homogeneous 是 (N, 4)，返回 (N, 3)
            return coords_homogeneous[:, :3] * 2
        
        # Mock filter - 坐标乘以0.5，置信度乘以0.9
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            execution_order.append("filter")
            filtered_coords = coordinates * 0.5
            filtered_confidences = confidences * 0.9
            return filtered_coords, bboxes, filtered_confidences, labels
        
        # Mock event bus
        event_data = {"data": None}
        def mock_publish(event_type, data, wait_all=False):
            execution_order.append("publish")
            event_data["data"] = data
            return 1
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act
        result = processor.process(detection_data)
        
        # Assert - 验证执行顺序
        assert execution_order == ["transform", "filter", "publish"], \
            "执行顺序应该是：变换 → 滤波 → 发布"
        
        # 验证输出类型
        assert isinstance(result, DeviceProcessedDataDTO)
        
        # 验证元数据传递
        assert result.device_id == detection_data.device_id
        assert result.frame_id == detection_data.frame_id
        assert result.device_alias == detection_data.device_alias
        
        # 验证数据变换：原始 * 2 (变换) * 0.5 (滤波) = 原始
        expected_coords = np.array([
            [100.0, 200.0, 300.0],
            [400.0, 500.0, 600.0],
        ], dtype=np.float32)
        np.testing.assert_array_almost_equal(result.coords, expected_coords)
        
        # 验证置信度变换：原始 * 0.9
        expected_confidences = np.array([0.9 * 0.9, 0.8 * 0.9], dtype=np.float32)
        np.testing.assert_array_almost_equal(result.confidence, expected_confidences)
        
        # 验证事件发布
        assert event_data["data"] is not None
        assert event_data["data"].device_id == result.device_id
    
    def test_multi_frame_processing(self, processor, monkeypatch):
        """测试多帧处理"""
        # Arrange
        frames = [
            DeviceDetectionDataDTO(
                device_id="device_001_mxid_12345",
                frame_id=i,
                device_alias="front_camera",
                detections=[
                    DetectionDTO(
                        label=0,
                        confidence=0.9,
                        bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                        spatial_coordinates=SpatialCoordinatesDTO(x=100.0 + i, y=200.0 + i, z=300.0 + i),
                    ),
                ],
            )
            for i in range(5)  # 5帧
        ]
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return coords_homogeneous[:, :3]
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act - 处理所有帧
        results = [processor.process(frame) for frame in frames]
        
        # Assert - 验证每帧都正确处理
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.frame_id == i
            assert result.device_id == "device_001_mxid_12345"
            assert result.coords.shape == (1, 3)
            # 验证坐标随帧变化
            expected_coords = np.array([[100.0 + i, 200.0 + i, 300.0 + i]], dtype=np.float32)
            np.testing.assert_array_almost_equal(result.coords, expected_coords)
    
    def test_different_devices_processing(self, processor, monkeypatch):
        """测试不同设备的处理"""
        # Arrange
        device_data = [
            DeviceDetectionDataDTO(
                device_id="device_001_mxid_12345",
                frame_id=100,
                device_alias="front_camera",
                detections=[
                    DetectionDTO(
                        label=0,
                        confidence=0.9,
                        bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                        spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                    ),
                ],
            ),
            DeviceDetectionDataDTO(
                device_id="device_002_mxid_67890",
                frame_id=100,
                device_alias="side_camera",
                detections=[
                    DetectionDTO(
                        label=1,
                        confidence=0.8,
                        bbox=BoundingBoxDTO(xmin=50.0, ymin=60.0, xmax=150.0, ymax=250.0),
                        spatial_coordinates=SpatialCoordinatesDTO(x=400.0, y=500.0, z=600.0),
                    ),
                ],
            ),
        ]
        
        # 跟踪每个设备的处理
        device_calls = {"device_001_mxid_12345": 0, "device_002_mxid_67890": 0}
        
        # Mock transformer
        def mock_transform_coordinates(mxid, coords_homogeneous):
            device_calls[mxid] += 1
            return coords_homogeneous[:, :3]
        
        # Mock filter
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act - 处理不同设备的数据
        results = [processor.process(data) for data in device_data]
        
        # Assert - 验证每个设备都被正确处理
        assert len(results) == 2
        
        # 验证第一个设备
        assert results[0].device_id == "device_001_mxid_12345"
        assert results[0].device_alias == "front_camera"
        assert results[0].labels[0] == 0
        
        # 验证第二个设备
        assert results[1].device_id == "device_002_mxid_67890"
        assert results[1].device_alias == "side_camera"
        assert results[1].labels[0] == 1
        
        # 验证每个设备都被调用了一次
        assert device_calls["device_001_mxid_12345"] == 1
        assert device_calls["device_002_mxid_67890"] == 1
    
    def test_different_labels_processing(self, processor, monkeypatch):
        """测试不同标签的处理"""
        # Arrange
        detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,  # durian
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
                DetectionDTO(
                    label=1,  # person
                    confidence=0.8,
                    bbox=BoundingBoxDTO(xmin=50.0, ymin=60.0, xmax=150.0, ymax=250.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=400.0, y=500.0, z=600.0),
                ),
                DetectionDTO(
                    label=0,  # durian
                    confidence=0.85,
                    bbox=BoundingBoxDTO(xmin=30.0, ymin=40.0, xmax=120.0, ymax=220.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=700.0, y=800.0, z=900.0),
                ),
            ],
        )
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return coords_homogeneous[:, :3]
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(detection_data)
        
        # Assert - 验证不同标签都被正确处理
        assert len(result.labels) == 3
        assert result.labels[0] == 0  # durian
        assert result.labels[1] == 1  # person
        assert result.labels[2] == 0  # durian
        
        # 验证对应的置信度
        assert result.confidence[0] == pytest.approx(0.9)
        assert result.confidence[1] == pytest.approx(0.8)
        assert result.confidence[2] == pytest.approx(0.85)
    
    def test_execution_order_transform_before_filter(self, processor, monkeypatch):
        """测试执行顺序：变换在滤波之前"""
        # Arrange
        detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
            ],
        )
        
        execution_order = []
        
        # Mock transformer
        def mock_transform_coordinates(mxid, coords_homogeneous):
            execution_order.append("transform")
            return coords_homogeneous[:, :3]
        
        # Mock filter
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            execution_order.append("filter")
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        processor.process(detection_data)
        
        # Assert - 验证执行顺序
        assert execution_order == ["transform", "filter"], \
            "坐标变换应该在滤波处理之前执行"
    
    def test_empty_input_handling_in_flow(self, processor):
        """测试完整流程中的空输入处理"""
        # Arrange
        empty_detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[],
        )
        
        # Act
        result = processor.process(empty_detection_data)
        
        # Assert - 更新：空输入应该返回空的 DeviceProcessedDataDTO
        assert isinstance(result, DeviceProcessedDataDTO), "空检测列表应该返回 DeviceProcessedDataDTO"
        assert len(result.labels) == 0, "空检测列表的 labels 应该为空"
        assert len(result.coords) == 0, "空检测列表的 coords 应该为空"
    
    def test_none_detections_handling_in_flow(self, processor):
        """测试完整流程中的 None detections 处理"""
        # Arrange
        none_detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=None,
        )
        
        # Act
        result = processor.process(none_detection_data)
        
        # Assert - 更新：None detections 应该返回空的 DeviceProcessedDataDTO
        assert isinstance(result, DeviceProcessedDataDTO), "None detections 应该返回 DeviceProcessedDataDTO"
        assert len(result.labels) == 0, "None detections 的 labels 应该为空"
        assert len(result.coords) == 0, "None detections 的 coords 应该为空"
    
    def test_exception_handling_in_flow(self, processor, monkeypatch):
        """测试完整流程中的异常处理"""
        # Arrange
        detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
            ],
        )
        
        # Mock transformer to raise exception
        def mock_transform_coordinates(mxid, coords_homogeneous):
            raise RuntimeError("坐标变换失败")
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        
        # Act & Assert - 验证异常被传播
        with pytest.raises(RuntimeError, match="坐标变换失败"):
            processor.process(detection_data)
    
    def test_event_publish_failure_does_not_affect_result(self, processor, monkeypatch):
        """测试事件发布失败不影响结果返回"""
        # Arrange
        detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=0,
                    confidence=0.9,
                    bbox=BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=200.0),
                    spatial_coordinates=SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0),
                ),
            ],
        )
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return coords_homogeneous[:, :3]
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        # Mock event bus to raise exception
        def mock_publish(event_type, data, wait_all=False):
            raise RuntimeError("事件发布失败")
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        monkeypatch.setattr(processor._event_bus, "publish", mock_publish)
        
        # Act - 不应该抛出异常
        result = processor.process(detection_data)
        
        # Assert - 验证仍然返回正确的结果
        assert isinstance(result, DeviceProcessedDataDTO)
        assert result.device_id == detection_data.device_id
        assert result.frame_id == detection_data.frame_id
        assert result.coords.shape == (1, 3)
    
    def test_large_batch_processing(self, processor, monkeypatch):
        """测试大批量检测结果处理"""
        # Arrange - 创建包含大量检测结果的数据
        num_detections = 100
        detection_data = DeviceDetectionDataDTO(
            device_id="device_001_mxid_12345",
            frame_id=100,
            device_alias="front_camera",
            detections=[
                DetectionDTO(
                    label=i % 2,  # 交替使用两个标签
                    confidence=0.9 - (i * 0.001),  # 递减的置信度
                    bbox=BoundingBoxDTO(
                        xmin=float(i),
                        ymin=float(i),
                        xmax=float(i + 10),
                        ymax=float(i + 10)
                    ),
                    spatial_coordinates=SpatialCoordinatesDTO(
                        x=float(i * 10),
                        y=float(i * 10),
                        z=float(i * 10)
                    ),
                )
                for i in range(num_detections)
            ],
        )
        
        # Mock transformer and filter
        def mock_transform_coordinates(mxid, coords_homogeneous):
            return coords_homogeneous[:, :3]
        
        def mock_filter_process(device_id, coordinates, bboxes, confidences, labels):
            return coordinates, bboxes, confidences, labels
        
        monkeypatch.setattr(processor._transformer, "transform_coordinates", mock_transform_coordinates)
        monkeypatch.setattr(processor._filter_manager, "process", mock_filter_process)
        
        # Act
        result = processor.process(detection_data)
        
        # Assert - 验证大批量数据正确处理
        assert result.coords.shape == (num_detections, 3)
        assert result.bbox.shape == (num_detections, 4)
        assert result.confidence.shape == (num_detections,)
        assert result.labels.shape == (num_detections,)
        
        # 验证数据对应关系
        for i in range(num_detections):
            expected_coords = np.array([i * 10.0, i * 10.0, i * 10.0], dtype=np.float32)
            np.testing.assert_array_almost_equal(result.coords[i], expected_coords)
            assert result.labels[i] == i % 2
