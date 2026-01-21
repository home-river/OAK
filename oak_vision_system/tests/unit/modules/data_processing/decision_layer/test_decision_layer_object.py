"""
决策层物体处理测试

测试 DecisionLayer 类的物体处理逻辑，包括：
- 区域判断（危险区/抓取区/超出范围）
- 矩形和半径抓取区域
- 最近物体选择
- 全局目标选择
- 待抓取目标标记
"""

import pytest
import numpy as np

from oak_vision_system.core.event_bus import EventBus
from oak_vision_system.core.dto.config_dto import (
    DecisionLayerConfigDTO,
    ObjectZonesConfigDTO,
    GraspZoneConfigDTO,
)
from oak_vision_system.modules.data_processing.decision_layer import (
    DecisionLayer,
    DetectionStatusLabel,
)


class TestObjectZoneJudgment:
    """测试物体区域判断"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        # 使用默认配置
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_object_in_danger_zone(self):
        """测试物体在危险区"""
        # 坐标单位：毫米（mm）
        # |y| = 1000mm < danger_y_threshold (1500mm)，应该是危险的
        coords = np.array([[1000.0, 1000.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)  # 1 是物体标签
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_DANGEROUS
    
    def test_object_in_grasp_zone(self):
        """测试物体在抓取区"""
        # 坐标单位：毫米（mm）
        # 使用符合默认配置的坐标：x ∈ (-200, 2000)，|y| ∈ (1550, 2500)
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        # 由于只有一个可抓取物体，它会被选为全局目标
        assert result[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
    
    def test_object_out_of_range(self):
        """测试物体超出范围"""
        # 坐标单位：毫米（mm）
        # x = 5000mm > x_max (2000mm)，超出范围
        coords = np.array([[5000.0, 2000.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE
    
    def test_object_negative_y_in_grasp_zone(self):
        """测试负 y 坐标的物体在抓取区"""
        # 坐标单位：毫米（mm）
        # y = -1800mm，|y| = 1800mm ∈ (1550, 2500)，应该在抓取区
        coords = np.array([[1000.0, -1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        # 由于只有一个可抓取物体，它会被选为全局目标
        assert result[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
    
    def test_multiple_objects_different_zones(self):
        """测试多个物体在不同区域"""
        # 坐标单位：毫米（mm）
        coords = np.array([
            [500.0, 500.0, 0.0],      # 危险区：|y|=500 < 1500
            [1000.0, 1800.0, 0.0],    # 抓取区：x ∈ (-200, 2000)，|y|=1800 ∈ (1550, 2500)
            [5000.0, 2000.0, 0.0],    # 超出范围：x=5000 > 2000
            [1500.0, -2000.0, 0.0],   # 抓取区：x ∈ (-200, 2000)，|y|=2000 ∈ (1550, 2500)
        ], dtype=np.float32)
        labels = np.array([1, 2, 3, 4], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_DANGEROUS
        # 物体 1 和 3 都在抓取区，距离更近的会被选为全局目标
        # 物体 1: [1000, 1800, 0]，距离 ≈ 2059mm
        # 物体 3: [1500, -2000, 0]，距离 ≈ 2500mm
        # 物体 1 距离更近
        assert result[1] == DetectionStatusLabel.OBJECT_PENDING_GRASP
        assert result[2] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE
        assert result[3] == DetectionStatusLabel.OBJECT_GRASPABLE


class TestRectangularGraspZone:
    """测试矩形抓取区域"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        # 使用自定义矩形抓取区域
        grasp_zone = GraspZoneConfigDTO(
            mode="rect",
            x_min=500.0,
            x_max=2000.0,
            y_min=1000.0,
            y_max=2000.0
        )
        object_zones = ObjectZonesConfigDTO(
            danger_y_threshold=800.0,
            grasp_zone=grasp_zone
        )
        config = DecisionLayerConfigDTO(object_zones=object_zones)
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_object_inside_rect_zone(self):
        """测试物体在矩形区域内"""
        # x=1000 ∈ (500, 2000)，|y|=1500 ∈ (1000, 2000)
        coords = np.array([[1000.0, 1500.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
    
    def test_object_outside_rect_zone_x(self):
        """测试物体在 x 方向超出矩形区域"""
        # x=2500 > x_max (2000)
        coords = np.array([[2500.0, 1500.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE
    
    def test_object_outside_rect_zone_y(self):
        """测试物体在 y 方向超出矩形区域"""
        # |y|=2500 > y_max (2000)
        coords = np.array([[1000.0, 2500.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE
    
    def test_object_at_rect_zone_boundary(self):
        """测试物体在矩形区域边界"""
        # x=500 = x_min（边界）
        coords = np.array([[500.0, 1500.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        # 边界是开区间，500 不应该在抓取区内
        assert result[0] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE


class TestRadiusGraspZone:
    """测试半径抓取区域"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        # 使用半径抓取区域
        grasp_zone = GraspZoneConfigDTO(
            mode="radius",
            r_min=1000.0,
            r_max=3000.0
        )
        object_zones = ObjectZonesConfigDTO(
            danger_y_threshold=500.0,
            grasp_zone=grasp_zone
        )
        config = DecisionLayerConfigDTO(object_zones=object_zones)
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_object_inside_radius_zone(self):
        """测试物体在半径区域内"""
        # r = sqrt(1500^2 + 1500^2) ≈ 2121mm ∈ (1000, 3000)
        coords = np.array([[1500.0, 1500.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
    
    def test_object_outside_radius_zone_too_far(self):
        """测试物体距离太远"""
        # r = sqrt(3000^2 + 3000^2) ≈ 4243mm > r_max (3000)
        coords = np.array([[3000.0, 3000.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE
    
    def test_object_outside_radius_zone_too_close(self):
        """测试物体距离太近"""
        # r = sqrt(500^2 + 500^2) ≈ 707mm < r_min (1000)
        coords = np.array([[500.0, 500.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        # 距离太近，但不在危险区（|y|=500 = danger_y_threshold）
        # 应该是超出范围
        assert result[0] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE


class TestNearestObjectSelection:
    """测试最近物体选择"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_nearest_object_selected_as_target(self):
        """测试最近的可抓取物体被选为目标"""
        # 坐标单位：毫米（mm）
        coords = np.array([
            [1000.0, 1800.0, 0.0],    # 距离 ≈ 2059mm
            [1500.0, 2000.0, 0.0],    # 距离 ≈ 2500mm
            [800.0, 1700.0, 0.0],     # 距离 ≈ 1878mm（最近）
        ], dtype=np.float32)
        labels = np.array([1, 2, 3], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        # 第三个物体距离最近，应该被选为全局目标
        assert result[0] == DetectionStatusLabel.OBJECT_GRASPABLE
        assert result[1] == DetectionStatusLabel.OBJECT_GRASPABLE
        assert result[2] == DetectionStatusLabel.OBJECT_PENDING_GRASP
    
    def test_single_graspable_object_becomes_target(self):
        """测试单个可抓取物体成为目标"""
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
    
    def test_no_graspable_objects_no_target(self):
        """测试没有可抓取物体时无目标"""
        # 所有物体都在危险区或超出范围
        coords = np.array([
            [500.0, 500.0, 0.0],      # 危险区
            [5000.0, 2000.0, 0.0],    # 超出范围
        ], dtype=np.float32)
        labels = np.array([1, 2], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        assert result[0] == DetectionStatusLabel.OBJECT_DANGEROUS
        assert result[1] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE
        
        # 验证没有全局目标
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is None


class TestGlobalTargetSelection:
    """测试全局目标选择"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_global_target_from_multiple_devices(self):
        """测试从多个设备中选择全局目标"""
        # 设备 1 的物体
        coords1 = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)  # 距离 ≈ 2059mm
        labels1 = np.array([1], dtype=np.int32)
        
        # 设备 2 的物体
        coords2 = np.array([[800.0, 1700.0, 0.0]], dtype=np.float32)  # 距离 ≈ 1878mm（更近）
        labels2 = np.array([1], dtype=np.int32)
        
        # 处理设备 1
        result1 = self.decision_layer.decide("device_1", coords1, labels1)
        assert result1[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
        
        # 处理设备 2
        result2 = self.decision_layer.decide("device_2", coords2, labels2)
        
        # 设备 2 的物体距离更近，应该成为全局目标
        assert result2[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
        
        # 重新处理设备 1，其物体应该不再是全局目标
        result1_updated = self.decision_layer.decide("device_1", coords1, labels1)
        assert result1_updated[0] == DetectionStatusLabel.OBJECT_GRASPABLE
    
    def test_global_target_updates_when_closer_object_found(self):
        """测试发现更近的物体时更新全局目标"""
        # 第一个物体
        coords1 = np.array([[1500.0, 2000.0, 0.0]], dtype=np.float32)  # 距离 ≈ 2500mm
        labels1 = np.array([1], dtype=np.int32)
        
        result1 = self.decision_layer.decide("device_1", coords1, labels1)
        assert result1[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
        
        # 发现更近的物体
        coords2 = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)  # 距离 ≈ 2059mm
        labels2 = np.array([1], dtype=np.int32)
        
        result2 = self.decision_layer.decide("device_1", coords2, labels2)
        
        # 第二个物体应该成为全局目标
        assert result2[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
    
    def test_global_target_cleared_when_no_graspable_objects(self):
        """测试没有可抓取物体时清除全局目标"""
        # 先有一个可抓取物体
        coords1 = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels1 = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide("device_1", coords1, labels1)
        
        # 验证有全局目标
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is not None
        
        # 所有物体都不可抓取
        coords2 = np.array([[500.0, 500.0, 0.0]], dtype=np.float32)  # 危险区
        labels2 = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide("device_1", coords2, labels2)
        
        # 全局目标应该被清除
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is None


class TestPendingGraspMarking:
    """测试待抓取目标标记"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_global_target_marked_as_pending_grasp(self):
        """测试全局目标被标记为待抓取"""
        coords = np.array([
            [1000.0, 1800.0, 0.0],    # 距离 ≈ 2059mm
            [1500.0, 2000.0, 0.0],    # 距离 ≈ 2500mm
        ], dtype=np.float32)
        labels = np.array([1, 2], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        # 第一个物体距离更近，应该被标记为待抓取
        assert result[0] == DetectionStatusLabel.OBJECT_PENDING_GRASP
        assert result[1] == DetectionStatusLabel.OBJECT_GRASPABLE
    
    def test_only_one_object_marked_as_pending_grasp(self):
        """测试只有一个物体被标记为待抓取"""
        coords = np.array([
            [1000.0, 1800.0, 0.0],
            [1100.0, 1900.0, 0.0],
            [1200.0, 2000.0, 0.0],
        ], dtype=np.float32)
        labels = np.array([1, 2, 3], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        # 只有一个物体应该被标记为待抓取
        pending_count = sum(1 for r in result if r == DetectionStatusLabel.OBJECT_PENDING_GRASP)
        assert pending_count == 1
    
    def test_non_graspable_objects_not_marked(self):
        """测试不可抓取的物体不会被标记"""
        coords = np.array([
            [500.0, 500.0, 0.0],      # 危险区
            [1000.0, 1800.0, 0.0],    # 可抓取
            [5000.0, 2000.0, 0.0],    # 超出范围
        ], dtype=np.float32)
        labels = np.array([1, 2, 3], dtype=np.int32)
        
        result = self.decision_layer.decide("device_1", coords, labels)
        
        # 只有可抓取的物体会被标记
        assert result[0] == DetectionStatusLabel.OBJECT_DANGEROUS
        assert result[1] == DetectionStatusLabel.OBJECT_PENDING_GRASP
        assert result[2] == DetectionStatusLabel.OBJECT_OUT_OF_RANGE
