"""
FilterManager 单元测试

测试策略：
- 测试初始化验证逻辑
- 测试 FilterPool 实例的正确创建
- 测试配置参数的正确存储
- 覆盖正常情况和异常情况
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from oak_vision_system.modules.data_processing.filter_manager import FilterManager
from oak_vision_system.core.dto.config_dto.device_binding_dto import DeviceMetadataDTO
from oak_vision_system.core.dto.config_dto.enums import ConnectionStatus
from oak_vision_system.modules.data_processing.filter_base import (
    BaseSpatialFilter,
    MovingAverageFilter,
)
from oak_vision_system.modules.data_processing.tracker import HungarianTracker


# ==================== Fixtures ====================

@pytest.fixture
def valid_device_metadata():
    """有效的设备元数据字典"""
    return {
        "device_001": DeviceMetadataDTO(
            mxid="device_001",
            product_name="OAK-D",
            connection_status=ConnectionStatus.CONNECTED,
        ),
        "device_002": DeviceMetadataDTO(
            mxid="device_002",
            product_name="OAK-D-Lite",
            connection_status=ConnectionStatus.CONNECTED,
        ),
    }


@pytest.fixture
def valid_label_map():
    """有效的标签映射列表"""
    return ["durian", "person", "car"]


@pytest.fixture
def custom_filter_factory():
    """自定义滤波器工厂函数"""
    return lambda: MovingAverageFilter(queue_maxsize=5)


@pytest.fixture
def custom_tracker():
    """自定义跟踪器实例"""
    return HungarianTracker(iou_threshold=0.6)


# ==================== 1. 初始化测试 ====================

class TestFilterManagerInit:
    """测试 FilterManager 初始化"""
    
    def test_init_with_valid_config(self, valid_device_metadata, valid_label_map):
        """测试：使用有效配置初始化"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # Assert
        assert manager is not None
        assert len(manager._device_ids) == 2
        assert "device_001" in manager._device_ids
        assert "device_002" in manager._device_ids
        assert manager._label_map == valid_label_map
        assert manager._pool_size == 32
    
    def test_init_with_default_pool_size(self, valid_device_metadata, valid_label_map):
        """测试：使用默认 pool_size 初始化"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # Assert
        assert manager._pool_size == 32  # 默认值
    
    def test_init_with_custom_pool_size(self, valid_device_metadata, valid_label_map):
        """测试：使用自定义 pool_size 初始化"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=64,
        )
        
        # Assert
        assert manager._pool_size == 64
    
    def test_init_with_custom_filter_factory(
        self, valid_device_metadata, valid_label_map, custom_filter_factory
    ):
        """测试：使用自定义滤波器工厂初始化"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            filter_factory=custom_filter_factory,
        )
        
        # Assert
        assert manager._filter_factory is custom_filter_factory
    
    def test_init_with_custom_tracker(
        self, valid_device_metadata, valid_label_map, custom_tracker
    ):
        """测试：使用自定义跟踪器初始化"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            tracker=custom_tracker,
        )
        
        # Assert
        assert manager._tracker is custom_tracker
    
    def test_init_with_custom_iou_threshold(self, valid_device_metadata, valid_label_map):
        """测试：使用自定义 IoU 阈值初始化"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            iou_threshold=0.7,
        )
        
        # Assert
        assert manager._iou_threshold == 0.7
    
    def test_init_creates_all_filter_pools(self, valid_device_metadata, valid_label_map):
        """测试：初始化时创建所有 (device_id, label) 组合的 FilterPool"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # Assert
        # 应该创建 2 个设备 × 3 个标签 = 6 个 FilterPool
        assert len(manager._pools) == 6
        
        # 验证所有组合都存在
        for device_id in ["device_001", "device_002"]:
            for label_idx in range(3):
                key = (device_id, label_idx)
                assert key in manager._pools
                assert manager._pools[key] is not None
    
    def test_init_filter_pools_have_correct_capacity(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：创建的 FilterPool 具有正确的容量"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=64,
        )
        
        # Assert
        for pool in manager._pools.values():
            assert pool.capacity == 64
    
    def test_init_stores_config_parameters(self, valid_device_metadata, valid_label_map):
        """测试：初始化时正确存储配置参数"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=48,
            iou_threshold=0.6,
        )
        
        # Assert
        assert manager._device_ids == ["device_001", "device_002"]
        assert manager._label_map == valid_label_map
        assert manager._pool_size == 48
        assert manager._iou_threshold == 0.6
        assert manager._filter_factory is not None
        assert manager._tracker is not None


# ==================== 2. 配置验证测试 ====================

class TestFilterManagerConfigValidation:
    """测试 FilterManager 配置验证"""
    
    def test_init_with_none_device_metadata(self, valid_label_map):
        """测试：device_metadata 为 None 时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="device_metadata 不能为 None 或空字典"):
            FilterManager(
                device_metadata=None,
                label_map=valid_label_map,
            )
    
    def test_init_with_empty_device_metadata(self, valid_label_map):
        """测试：device_metadata 为空字典时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="device_metadata 不能为 None 或空字典"):
            FilterManager(
                device_metadata={},
                label_map=valid_label_map,
            )
    
    def test_init_with_none_label_map(self, valid_device_metadata):
        """测试：label_map 为 None 时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="label_map 不能为 None 或空列表"):
            FilterManager(
                device_metadata=valid_device_metadata,
                label_map=None,
            )
    
    def test_init_with_empty_label_map(self, valid_device_metadata):
        """测试：label_map 为空列表时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="label_map 不能为 None 或空列表"):
            FilterManager(
                device_metadata=valid_device_metadata,
                label_map=[],
            )
    
    def test_init_with_invalid_pool_size_zero(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：pool_size 为 0 时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="pool_size 必须大于 0"):
            FilterManager(
                device_metadata=valid_device_metadata,
                label_map=valid_label_map,
                pool_size=0,
            )
    
    def test_init_with_invalid_pool_size_negative(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：pool_size 为负数时抛出 ValueError"""
        # Act & Assert
        with pytest.raises(ValueError, match="pool_size 必须大于 0"):
            FilterManager(
                device_metadata=valid_device_metadata,
                label_map=valid_label_map,
                pool_size=-10,
            )
    
    def test_init_with_empty_mxid(self, valid_label_map):
        """测试：device_metadata 中包含空 MXid 时抛出 ValueError"""
        # Arrange
        invalid_device_metadata = {
            "": DeviceMetadataDTO(
                mxid="",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
        
        # Act & Assert
        with pytest.raises(ValueError, match="MXid 不能为空字符串"):
            FilterManager(
                device_metadata=invalid_device_metadata,
                label_map=valid_label_map,
            )
    
    def test_init_with_mixed_valid_and_empty_mxid(self, valid_label_map):
        """测试：device_metadata 中混合有效和空 MXid 时抛出 ValueError"""
        # Arrange
        mixed_device_metadata = {
            "device_001": DeviceMetadataDTO(
                mxid="device_001",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
            "": DeviceMetadataDTO(
                mxid="",
                product_name="OAK-D-Lite",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
        
        # Act & Assert
        with pytest.raises(ValueError, match="MXid 不能为空字符串"):
            FilterManager(
                device_metadata=mixed_device_metadata,
                label_map=valid_label_map,
            )


# ==================== 3. FilterPool 实例创建测试 ====================

class TestFilterManagerPoolCreation:
    """测试 FilterManager 的 FilterPool 实例创建"""
    
    def test_creates_pools_for_single_device_single_label(self):
        """测试：单设备单标签时创建 1 个 FilterPool"""
        # Arrange
        device_metadata = {
            "device_001": DeviceMetadataDTO(
                mxid="device_001",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
        label_map = ["durian"]
        
        # Act
        manager = FilterManager(
            device_metadata=device_metadata,
            label_map=label_map,
        )
        
        # Assert
        assert len(manager._pools) == 1
        assert ("device_001", 0) in manager._pools
    
    def test_creates_pools_for_single_device_multiple_labels(self):
        """测试：单设备多标签时创建正确数量的 FilterPool"""
        # Arrange
        device_metadata = {
            "device_001": DeviceMetadataDTO(
                mxid="device_001",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
        label_map = ["durian", "person", "car", "tree"]
        
        # Act
        manager = FilterManager(
            device_metadata=device_metadata,
            label_map=label_map,
        )
        
        # Assert
        assert len(manager._pools) == 4
        for label_idx in range(4):
            assert ("device_001", label_idx) in manager._pools
    
    def test_creates_pools_for_multiple_devices_single_label(self):
        """测试：多设备单标签时创建正确数量的 FilterPool"""
        # Arrange
        device_metadata = {
            "device_001": DeviceMetadataDTO(
                mxid="device_001",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
            "device_002": DeviceMetadataDTO(
                mxid="device_002",
                product_name="OAK-D-Lite",
                connection_status=ConnectionStatus.CONNECTED,
            ),
            "device_003": DeviceMetadataDTO(
                mxid="device_003",
                product_name="OAK-D-Pro",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
        label_map = ["durian"]
        
        # Act
        manager = FilterManager(
            device_metadata=device_metadata,
            label_map=label_map,
        )
        
        # Assert
        assert len(manager._pools) == 3
        for device_id in ["device_001", "device_002", "device_003"]:
            assert (device_id, 0) in manager._pools
    
    def test_creates_pools_for_multiple_devices_multiple_labels(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：多设备多标签时创建所有组合的 FilterPool"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # Assert
        # 2 设备 × 3 标签 = 6 个 FilterPool
        assert len(manager._pools) == 6
        
        # 验证所有组合
        for device_id in ["device_001", "device_002"]:
            for label_idx in range(3):
                key = (device_id, label_idx)
                assert key in manager._pools
    
    def test_pool_keys_are_tuples(self, valid_device_metadata, valid_label_map):
        """测试：FilterPool 的键是 (device_id, label) 元组"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # Assert
        for key in manager._pools.keys():
            assert isinstance(key, tuple)
            assert len(key) == 2
            assert isinstance(key[0], str)  # device_id
            assert isinstance(key[1], int)  # label index
    
    def test_all_pools_are_independent_instances(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：所有 FilterPool 都是独立的实例"""
        # Act
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # Assert
        pool_ids = set(id(pool) for pool in manager._pools.values())
        assert len(pool_ids) == len(manager._pools)  # 所有实例的 id 都不同


# ==================== 4. 数据分组测试 ====================

class TestFilterManagerGrouping:
    """测试 FilterManager 的数据分组逻辑"""
    
    def test_process_with_single_label_input(self, valid_device_metadata, valid_label_map):
        """测试：单标签输入的处理"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建单标签输入数据（所有检测都是标签 0）
        coordinates = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95], dtype=np.float32)
        labels = np.array([0, 0, 0], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert
        # 验证输出不为空
        assert len(result_coords) > 0
        # 验证所有输出标签都是 0
        assert np.all(result_labels == 0)
        # 验证输出长度一致
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)
    
    def test_process_with_multiple_labels_mixed_input(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：多标签混合输入的处理"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建多标签混合输入数据
        coordinates = np.array([
            [1.0, 2.0, 3.0],    # label 0
            [4.0, 5.0, 6.0],    # label 1
            [7.0, 8.0, 9.0],    # label 0
            [10.0, 11.0, 12.0], # label 2
            [13.0, 14.0, 15.0], # label 1
            [16.0, 17.0, 18.0], # label 0
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
            [60.0, 60.0, 70.0, 70.0],
            [80.0, 80.0, 90.0, 90.0],
            [100.0, 100.0, 110.0, 110.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95, 0.88, 0.92, 0.87], dtype=np.float32)
        labels = np.array([0, 1, 0, 2, 1, 0], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert
        # 验证输出不为空
        assert len(result_coords) > 0
        # 验证输出包含多个标签
        unique_output_labels = np.unique(result_labels)
        assert len(unique_output_labels) > 1
        # 验证输出标签都在有效范围内
        assert np.all(result_labels >= 0)
        assert np.all(result_labels < len(valid_label_map))
        # 验证输出长度一致
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)
    
    def test_process_with_empty_input(self, valid_device_metadata, valid_label_map):
        """测试：空输入（n=0）的处理"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建空输入数据
        coordinates = np.empty((0, 3), dtype=np.float32)
        bboxes = np.empty((0, 4), dtype=np.float32)
        confidences = np.empty((0,), dtype=np.float32)
        labels = np.empty((0,), dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert
        # 验证输出都是空数组
        assert len(result_coords) == 0
        assert len(result_bboxes) == 0
        assert len(result_confs) == 0
        assert len(result_labels) == 0
        # 验证输出形状正确
        assert result_coords.shape == (0, 3)
        assert result_bboxes.shape == (0, 4)
        assert result_confs.shape == (0,)
        assert result_labels.shape == (0,)
    
    def test_process_data_slicing_correctness(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：数据正确切片"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建测试数据，使用可识别的坐标值
        coordinates = np.array([
            [100.0, 100.0, 100.0],  # label 0 - 第1个
            [200.0, 200.0, 200.0],  # label 1 - 第1个
            [101.0, 101.0, 101.0],  # label 0 - 第2个
            [201.0, 201.0, 201.0],  # label 1 - 第2个
            [102.0, 102.0, 102.0],  # label 0 - 第3个
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [1.0, 1.0, 11.0, 11.0],
            [21.0, 21.0, 31.0, 31.0],
            [2.0, 2.0, 12.0, 12.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.91, 0.86, 0.92], dtype=np.float32)
        labels = np.array([0, 1, 0, 1, 0], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert
        # 验证输出不为空
        assert len(result_coords) > 0
        
        # 验证标签 0 的数据被正确分组（应该有 3 个）
        label_0_mask = (result_labels == 0)
        label_0_coords = result_coords[label_0_mask]
        # 验证标签 0 的坐标值在 100-102 范围内
        assert np.all(label_0_coords[:, 0] >= 100.0)
        assert np.all(label_0_coords[:, 0] <= 102.0)
        
        # 验证标签 1 的数据被正确分组（应该有 2 个）
        label_1_mask = (result_labels == 1)
        label_1_coords = result_coords[label_1_mask]
        # 验证标签 1 的坐标值在 200-201 范围内
        assert np.all(label_1_coords[:, 0] >= 200.0)
        assert np.all(label_1_coords[:, 0] <= 201.0)
        
        # 验证输出长度一致
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)


# ==================== 5. 结果拼接测试 ====================

class TestFilterManagerAggregation:
    """测试 FilterManager 的结果聚合和拼接逻辑"""
    
    def test_output_length_consistency(self, valid_device_metadata, valid_label_map):
        """测试：输出长度一致性 - 所有输出数组长度相等"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建多标签混合输入数据
        coordinates = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
            [10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0],
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
            [60.0, 60.0, 70.0, 70.0],
            [80.0, 80.0, 90.0, 90.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95, 0.88, 0.92], dtype=np.float32)
        labels = np.array([0, 1, 0, 2, 1], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert - 验证所有输出数组长度相等
        assert len(result_coords) == len(result_bboxes), \
            "coordinates 和 bboxes 长度不一致"
        assert len(result_coords) == len(result_confs), \
            "coordinates 和 confidences 长度不一致"
        assert len(result_coords) == len(result_labels), \
            "coordinates 和 labels 长度不一致"
        
        # 验证输出形状正确
        assert result_coords.shape[1] == 3, "coordinates 应该是 (n, 3) 形状"
        assert result_bboxes.shape[1] == 4, "bboxes 应该是 (n, 4) 形状"
        assert result_confs.ndim == 1, "confidences 应该是一维数组"
        assert result_labels.ndim == 1, "labels 应该是一维数组"
    
    def test_block_concatenation_order(self, valid_device_metadata, valid_label_map):
        """测试：块状拼接顺序正确 - 同一标签的元素应该是连续的块"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建交替标签的输入数据
        coordinates = np.array([
            [1.0, 2.0, 3.0],    # label 0
            [4.0, 5.0, 6.0],    # label 1
            [7.0, 8.0, 9.0],    # label 0
            [10.0, 11.0, 12.0], # label 1
            [13.0, 14.0, 15.0], # label 0
            [16.0, 17.0, 18.0], # label 1
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
            [60.0, 60.0, 70.0, 70.0],
            [80.0, 80.0, 90.0, 90.0],
            [100.0, 100.0, 110.0, 110.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95, 0.88, 0.92, 0.87], dtype=np.float32)
        labels = np.array([0, 1, 0, 1, 0, 1], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert - 验证块状拼接：同一标签的元素应该是连续的
        # 找到标签变化的位置
        label_changes = np.where(np.diff(result_labels) != 0)[0]
        
        # 验证每个连续块内的标签都相同
        start_idx = 0
        for change_idx in label_changes:
            # 检查从 start_idx 到 change_idx 的所有标签是否相同
            block_labels = result_labels[start_idx:change_idx + 1]
            assert np.all(block_labels == block_labels[0]), \
                f"块 [{start_idx}:{change_idx + 1}] 内的标签不一致"
            start_idx = change_idx + 1
        
        # 检查最后一个块
        if start_idx < len(result_labels):
            block_labels = result_labels[start_idx:]
            assert np.all(block_labels == block_labels[0]), \
                f"最后一个块 [{start_idx}:] 内的标签不一致"
    
    def test_multiple_labels_mixed_scenario(self, valid_device_metadata, valid_label_map):
        """测试：多标签混合场景 - 验证多个标签的数据正确聚合"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建包含所有三个标签的混合数据
        coordinates = np.array([
            [100.0, 100.0, 100.0],  # label 0
            [200.0, 200.0, 200.0],  # label 1
            [300.0, 300.0, 300.0],  # label 2
            [101.0, 101.0, 101.0],  # label 0
            [201.0, 201.0, 201.0],  # label 1
            [301.0, 301.0, 301.0],  # label 2
            [102.0, 102.0, 102.0],  # label 0
            [202.0, 202.0, 202.0],  # label 1
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
            [1.0, 1.0, 11.0, 11.0],
            [21.0, 21.0, 31.0, 31.0],
            [41.0, 41.0, 51.0, 51.0],
            [2.0, 2.0, 12.0, 12.0],
            [22.0, 22.0, 32.0, 32.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95, 0.91, 0.86, 0.96, 0.92, 0.87], dtype=np.float32)
        labels = np.array([0, 1, 2, 0, 1, 2, 0, 1], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert - 验证输出包含所有三个标签
        unique_output_labels = np.unique(result_labels)
        assert len(unique_output_labels) == 3, "输出应该包含所有三个标签"
        assert 0 in unique_output_labels, "输出应该包含标签 0"
        assert 1 in unique_output_labels, "输出应该包含标签 1"
        assert 2 in unique_output_labels, "输出应该包含标签 2"
        
        # 验证每个标签的数据数量
        label_0_count = np.sum(result_labels == 0)
        label_1_count = np.sum(result_labels == 1)
        label_2_count = np.sum(result_labels == 2)
        
        assert label_0_count > 0, "标签 0 应该有输出"
        assert label_1_count > 0, "标签 1 应该有输出"
        assert label_2_count > 0, "标签 2 应该有输出"
        
        # 验证标签 0 的坐标值在正确范围内（100-102）
        label_0_mask = (result_labels == 0)
        label_0_coords = result_coords[label_0_mask]
        assert np.all(label_0_coords[:, 0] >= 100.0), "标签 0 的坐标应该 >= 100"
        assert np.all(label_0_coords[:, 0] <= 102.0), "标签 0 的坐标应该 <= 102"
        
        # 验证标签 1 的坐标值在正确范围内（200-202）
        label_1_mask = (result_labels == 1)
        label_1_coords = result_coords[label_1_mask]
        assert np.all(label_1_coords[:, 0] >= 200.0), "标签 1 的坐标应该 >= 200"
        assert np.all(label_1_coords[:, 0] <= 202.0), "标签 1 的坐标应该 <= 202"
        
        # 验证标签 2 的坐标值在正确范围内（300-301）
        label_2_mask = (result_labels == 2)
        label_2_coords = result_coords[label_2_mask]
        assert np.all(label_2_coords[:, 0] >= 300.0), "标签 2 的坐标应该 >= 300"
        assert np.all(label_2_coords[:, 0] <= 301.0), "标签 2 的坐标应该 <= 301"
        
        # 验证输出长度一致性
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)
    
    def test_empty_output_handling(self, valid_device_metadata, valid_label_map):
        """测试：空输出处理 - 当输入为空时返回空数组"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建空输入数据
        coordinates = np.empty((0, 3), dtype=np.float32)
        bboxes = np.empty((0, 4), dtype=np.float32)
        confidences = np.empty((0,), dtype=np.float32)
        labels = np.empty((0,), dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert - 验证所有输出都是空数组
        assert len(result_coords) == 0, "coordinates 应该为空"
        assert len(result_bboxes) == 0, "bboxes 应该为空"
        assert len(result_confs) == 0, "confidences 应该为空"
        assert len(result_labels) == 0, "labels 应该为空"
        
        # 验证输出形状正确
        assert result_coords.shape == (0, 3), "空 coordinates 形状应该是 (0, 3)"
        assert result_bboxes.shape == (0, 4), "空 bboxes 形状应该是 (0, 4)"
        assert result_confs.shape == (0,), "空 confidences 形状应该是 (0,)"
        assert result_labels.shape == (0,), "空 labels 形状应该是 (0,)"
        
        # 验证数据类型正确
        assert result_coords.dtype == np.float32, "coordinates 类型应该是 float32"
        assert result_bboxes.dtype == np.float32, "bboxes 类型应该是 float32"
        assert result_confs.dtype == np.float32, "confidences 类型应该是 float32"
        assert result_labels.dtype == np.int32, "labels 类型应该是 int32"
    
    def test_single_label_block_concatenation(self, valid_device_metadata, valid_label_map):
        """测试：单标签块状拼接 - 所有元素都是同一标签时的拼接"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建单标签输入数据
        coordinates = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
            [10.0, 11.0, 12.0],
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
            [60.0, 60.0, 70.0, 70.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95, 0.88], dtype=np.float32)
        labels = np.array([1, 1, 1, 1], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert - 验证所有输出标签都是 1
        assert np.all(result_labels == 1), "所有输出标签应该都是 1"
        
        # 验证输出长度一致性
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)
        
        # 验证输出不为空
        assert len(result_coords) > 0, "输出不应该为空"
    
    def test_two_labels_block_structure(self, valid_device_metadata, valid_label_map):
        """测试：两个标签的块状结构 - 验证两个标签形成两个连续块"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建两个标签的输入数据（先所有 label 0，再所有 label 1）
        coordinates = np.array([
            [1.0, 2.0, 3.0],    # label 0
            [4.0, 5.0, 6.0],    # label 0
            [7.0, 8.0, 9.0],    # label 0
            [10.0, 11.0, 12.0], # label 1
            [13.0, 14.0, 15.0], # label 1
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
            [60.0, 60.0, 70.0, 70.0],
            [80.0, 80.0, 90.0, 90.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95, 0.88, 0.92], dtype=np.float32)
        labels = np.array([0, 0, 0, 1, 1], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert - 验证输出包含两个标签
        unique_labels = np.unique(result_labels)
        assert len(unique_labels) == 2, "输出应该包含两个标签"
        assert 0 in unique_labels, "输出应该包含标签 0"
        assert 1 in unique_labels, "输出应该包含标签 1"
        
        # 验证块状结构：找到标签变化的位置
        label_changes = np.where(np.diff(result_labels) != 0)[0]
        
        # 对于两个标签，应该最多有一个变化点
        assert len(label_changes) <= 1, "两个标签应该最多有一个变化点"
        
        # 验证输出长度一致性
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)
    
    def test_aggregation_preserves_data_correspondence(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：聚合保持数据对应关系 - coordinates、bboxes、confidences、labels 的对应关系一致"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建具有可识别特征的输入数据
        coordinates = np.array([
            [100.0, 100.0, 100.0],  # label 0, bbox [0,0,10,10], conf 0.9
            [200.0, 200.0, 200.0],  # label 1, bbox [20,20,30,30], conf 0.85
            [101.0, 101.0, 101.0],  # label 0, bbox [1,1,11,11], conf 0.91
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [1.0, 1.0, 11.0, 11.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.91], dtype=np.float32)
        labels = np.array([0, 1, 0], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert - 验证每个输出元素的对应关系
        for i in range(len(result_coords)):
            coord = result_coords[i]
            bbox = result_bboxes[i]
            conf = result_confs[i]
            label = result_labels[i]
            
            # 根据坐标值判断应该属于哪个标签
            if coord[0] >= 100.0 and coord[0] <= 101.0:
                # 应该是 label 0
                assert label == 0, f"索引 {i}: 坐标 {coord[0]} 应该对应标签 0"
                # bbox 应该在 [0,0,10,10] 或 [1,1,11,11] 范围内
                assert bbox[0] >= 0.0 and bbox[0] <= 1.0, \
                    f"索引 {i}: 标签 0 的 bbox 不正确"
            elif coord[0] >= 200.0 and coord[0] <= 200.0:
                # 应该是 label 1
                assert label == 1, f"索引 {i}: 坐标 {coord[0]} 应该对应标签 1"
                # bbox 应该在 [20,20,30,30] 范围内
                assert bbox[0] >= 20.0 and bbox[0] <= 20.0, \
                    f"索引 {i}: 标签 1 的 bbox 不正确"
        
        # 验证输出长度一致性
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)
    
    def test_process_with_all_different_labels(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：每个检测都是不同标签的情况"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建每个检测都是不同标签的数据
        coordinates = np.array([
            [1.0, 2.0, 3.0],    # label 0
            [4.0, 5.0, 6.0],    # label 1
            [7.0, 8.0, 9.0],    # label 2
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95], dtype=np.float32)
        labels = np.array([0, 1, 2], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert
        # 验证输出不为空
        assert len(result_coords) > 0
        # 验证输出包含所有三个标签
        unique_output_labels = np.unique(result_labels)
        assert len(unique_output_labels) == 3
        assert 0 in unique_output_labels
        assert 1 in unique_output_labels
        assert 2 in unique_output_labels
        # 验证输出长度一致
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)
    
    def test_process_with_two_labels_alternating(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：两个标签交替出现的情况"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
        )
        
        # 创建两个标签交替出现的数据
        coordinates = np.array([
            [1.0, 2.0, 3.0],    # label 0
            [4.0, 5.0, 6.0],    # label 1
            [7.0, 8.0, 9.0],    # label 0
            [10.0, 11.0, 12.0], # label 1
            [13.0, 14.0, 15.0], # label 0
            [16.0, 17.0, 18.0], # label 1
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
            [60.0, 60.0, 70.0, 70.0],
            [80.0, 80.0, 90.0, 90.0],
            [100.0, 100.0, 110.0, 110.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95, 0.88, 0.92, 0.87], dtype=np.float32)
        labels = np.array([0, 1, 0, 1, 0, 1], dtype=np.int32)
        
        # Act
        result_coords, result_bboxes, result_confs, result_labels = manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Assert
        # 验证输出不为空
        assert len(result_coords) > 0
        # 验证输出包含两个标签
        unique_output_labels = np.unique(result_labels)
        assert len(unique_output_labels) == 2
        assert 0 in unique_output_labels
        assert 1 in unique_output_labels
        # 验证输出长度一致
        assert len(result_coords) == len(result_bboxes)
        assert len(result_coords) == len(result_confs)
        assert len(result_coords) == len(result_labels)


# ==================== 6. 统计信息测试 ====================

class TestFilterManagerStats:
    """测试 FilterManager 的统计信息查询接口"""
    
    def test_get_pool_stats_returns_correct_format(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：get_pool_stats() 返回正确的格式"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert - 验证返回类型是字典
        assert isinstance(stats, dict), "返回值应该是字典类型"
        
        # 验证字典不为空
        assert len(stats) > 0, "统计信息不应该为空"
        
        # 验证每个键是 (device_id, label) 元组
        for key in stats.keys():
            assert isinstance(key, tuple), f"键 {key} 应该是元组类型"
            assert len(key) == 2, f"键 {key} 应该包含两个元素"
            assert isinstance(key[0], str), f"键 {key} 的第一个元素应该是字符串（device_id）"
            assert isinstance(key[1], int), f"键 {key} 的第二个元素应该是整数（label）"
        
        # 验证每个值包含 capacity 和 active_count
        for key, value in stats.items():
            assert isinstance(value, dict), f"键 {key} 的值应该是字典类型"
            assert "capacity" in value, f"键 {key} 的值应该包含 'capacity' 字段"
            assert "active_count" in value, f"键 {key} 的值应该包含 'active_count' 字段"
            assert isinstance(value["capacity"], int), \
                f"键 {key} 的 capacity 应该是整数类型"
            assert isinstance(value["active_count"], int), \
                f"键 {key} 的 active_count 应该是整数类型"
    
    def test_get_pool_stats_includes_all_pools(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：get_pool_stats() 包含所有 FilterPool"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert - 验证统计信息包含所有 (device_id, label) 组合
        # 2 个设备 × 3 个标签 = 6 个 FilterPool
        assert len(stats) == 6, "应该包含所有 6 个 FilterPool 的统计信息"
        
        # 验证所有组合都存在
        for device_id in ["device_001", "device_002"]:
            for label_idx in range(3):
                key = (device_id, label_idx)
                assert key in stats, f"统计信息应该包含键 {key}"
    
    def test_get_pool_stats_capacity_matches_pool_size(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：统计信息中的 capacity 与初始化时的 pool_size 一致"""
        # Arrange
        pool_size = 64
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=pool_size,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert - 验证所有 FilterPool 的 capacity 都等于 pool_size
        for key, value in stats.items():
            assert value["capacity"] == pool_size, \
                f"键 {key} 的 capacity 应该等于 {pool_size}，实际为 {value['capacity']}"
    
    def test_get_pool_stats_active_count_initially_zero(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：初始化后所有 FilterPool 的 active_count 为 0"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert - 验证所有 FilterPool 的 active_count 初始为 0
        for key, value in stats.items():
            assert value["active_count"] == 0, \
                f"键 {key} 的 active_count 初始应该为 0，实际为 {value['active_count']}"
    
    def test_get_pool_stats_active_count_after_processing(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：处理数据后 active_count 正确更新"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # 处理一些数据
        coordinates = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ], dtype=np.float32)
        bboxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [20.0, 20.0, 30.0, 30.0],
            [40.0, 40.0, 50.0, 50.0],
        ], dtype=np.float32)
        confidences = np.array([0.9, 0.85, 0.95], dtype=np.float32)
        labels = np.array([0, 1, 0], dtype=np.int32)
        
        manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert - 验证使用过的 FilterPool 的 active_count > 0
        # (device_001, 0) 和 (device_001, 1) 应该有活跃的滤波器
        assert stats[("device_001", 0)]["active_count"] > 0, \
            "处理标签 0 后，active_count 应该大于 0"
        assert stats[("device_001", 1)]["active_count"] > 0, \
            "处理标签 1 后，active_count 应该大于 0"
        
        # 未使用的 FilterPool 的 active_count 应该仍为 0
        assert stats[("device_001", 2)]["active_count"] == 0, \
            "未使用的 FilterPool active_count 应该为 0"
        assert stats[("device_002", 0)]["active_count"] == 0, \
            "未使用的 FilterPool active_count 应该为 0"
    
    def test_get_pool_stats_with_single_device_single_label(self):
        """测试：单设备单标签时的统计信息"""
        # Arrange
        device_metadata = {
            "device_001": DeviceMetadataDTO(
                mxid="device_001",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
        label_map = ["durian"]
        
        manager = FilterManager(
            device_metadata=device_metadata,
            label_map=label_map,
            pool_size=16,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert
        assert len(stats) == 1, "应该只有 1 个 FilterPool"
        assert ("device_001", 0) in stats, "应该包含 (device_001, 0)"
        assert stats[("device_001", 0)]["capacity"] == 16, "capacity 应该为 16"
        assert stats[("device_001", 0)]["active_count"] == 0, "active_count 初始应该为 0"
    
    def test_get_pool_stats_with_multiple_devices_multiple_labels(self):
        """测试：多设备多标签时的统计信息"""
        # Arrange
        device_metadata = {
            "device_001": DeviceMetadataDTO(
                mxid="device_001",
                product_name="OAK-D",
                connection_status=ConnectionStatus.CONNECTED,
            ),
            "device_002": DeviceMetadataDTO(
                mxid="device_002",
                product_name="OAK-D-Lite",
                connection_status=ConnectionStatus.CONNECTED,
            ),
            "device_003": DeviceMetadataDTO(
                mxid="device_003",
                product_name="OAK-D-Pro",
                connection_status=ConnectionStatus.CONNECTED,
            ),
        }
        label_map = ["durian", "person", "car", "tree"]
        
        manager = FilterManager(
            device_metadata=device_metadata,
            label_map=label_map,
            pool_size=48,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert
        # 3 个设备 × 4 个标签 = 12 个 FilterPool
        assert len(stats) == 12, "应该有 12 个 FilterPool"
        
        # 验证所有组合都存在
        for device_id in ["device_001", "device_002", "device_003"]:
            for label_idx in range(4):
                key = (device_id, label_idx)
                assert key in stats, f"应该包含键 {key}"
                assert stats[key]["capacity"] == 48, \
                    f"键 {key} 的 capacity 应该为 48"
                assert stats[key]["active_count"] == 0, \
                    f"键 {key} 的 active_count 初始应该为 0"
    
    def test_get_pool_stats_capacity_non_negative(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：capacity 始终为非负数"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert
        for key, value in stats.items():
            assert value["capacity"] >= 0, \
                f"键 {key} 的 capacity 应该为非负数，实际为 {value['capacity']}"
    
    def test_get_pool_stats_active_count_non_negative(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：active_count 始终为非负数"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # 处理一些数据
        coordinates = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        bboxes = np.array([[0.0, 0.0, 10.0, 10.0]], dtype=np.float32)
        confidences = np.array([0.9], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)
        
        manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert
        for key, value in stats.items():
            assert value["active_count"] >= 0, \
                f"键 {key} 的 active_count 应该为非负数，实际为 {value['active_count']}"
    
    def test_get_pool_stats_active_count_not_exceed_capacity(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：active_count 不应该超过 capacity"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # 处理大量数据
        n = 50  # 超过 pool_size
        coordinates = np.random.rand(n, 3).astype(np.float32) * 100
        bboxes = np.random.rand(n, 4).astype(np.float32) * 100
        confidences = np.random.rand(n).astype(np.float32)
        labels = np.random.randint(0, 3, size=n, dtype=np.int32)
        
        manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Act
        stats = manager.get_pool_stats()
        
        # Assert
        for key, value in stats.items():
            assert value["active_count"] <= value["capacity"], \
                f"键 {key} 的 active_count ({value['active_count']}) " \
                f"不应该超过 capacity ({value['capacity']})"
    
    def test_get_pool_stats_multiple_calls_consistency(
        self, valid_device_metadata, valid_label_map
    ):
        """测试：多次调用 get_pool_stats() 返回一致的结果"""
        # Arrange
        manager = FilterManager(
            device_metadata=valid_device_metadata,
            label_map=valid_label_map,
            pool_size=32,
        )
        
        # 处理一些数据
        coordinates = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        bboxes = np.array([[0.0, 0.0, 10.0, 10.0]], dtype=np.float32)
        confidences = np.array([0.9], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)
        
        manager.process(
            device_id="device_001",
            coordinates=coordinates,
            bboxes=bboxes,
            confidences=confidences,
            labels=labels,
        )
        
        # Act - 多次调用
        stats1 = manager.get_pool_stats()
        stats2 = manager.get_pool_stats()
        
        # Assert - 验证两次调用返回相同的结果
        assert len(stats1) == len(stats2), "两次调用返回的统计信息数量应该相同"
        
        for key in stats1.keys():
            assert key in stats2, f"键 {key} 应该在两次调用中都存在"
            assert stats1[key]["capacity"] == stats2[key]["capacity"], \
                f"键 {key} 的 capacity 应该一致"
            assert stats1[key]["active_count"] == stats2[key]["active_count"], \
                f"键 {key} 的 active_count 应该一致"
