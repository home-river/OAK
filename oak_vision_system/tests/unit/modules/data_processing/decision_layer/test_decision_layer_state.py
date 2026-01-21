"""
决策层状态管理测试

测试 DecisionLayer 类的状态管理逻辑，包括：
- 设备状态创建和更新
- 状态过期检查
"""

import pytest
import numpy as np
import time

from oak_vision_system.core.event_bus import EventBus
from oak_vision_system.core.dto.config_dto import DecisionLayerConfigDTO
from oak_vision_system.modules.data_processing.decision_layer import (
    DecisionLayer,
    DeviceState,
    PersonWarningState,
)


class TestDeviceStateManagement:
    """测试设备状态管理"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_device_state_created_on_first_access(self):
        """测试首次访问时创建设备状态"""
        device_id = "device_1"
        
        # 初始时不应该有设备状态
        assert device_id not in self.decision_layer._device_states
        
        # 处理数据后应该创建设备状态
        coords = np.array([[4000.0, 0.0, 0.0]], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)
        
        self.decision_layer.decide(device_id, coords, labels)
        
        # 设备状态应该被创建
        assert device_id in self.decision_layer._device_states
        assert isinstance(self.decision_layer._device_states[device_id], DeviceState)
    
    def test_device_state_updated_on_subsequent_access(self):
        """测试后续访问时更新设备状态"""
        device_id = "device_1"
        # 使用物体坐标，因为只有物体处理才更新 last_update_time
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)  # 1 是物体标签
        
        # 第一次处理
        self.decision_layer.decide(device_id, coords, labels)
        first_update_time = self.decision_layer._device_states[device_id].last_update_time
        
        # 验证第一次更新时间不为0
        assert first_update_time > 0
        
        # 等待一段时间
        time.sleep(0.1)
        
        # 第二次处理
        self.decision_layer.decide(device_id, coords, labels)
        second_update_time = self.decision_layer._device_states[device_id].last_update_time
        
        # 更新时间应该改变
        assert second_update_time > first_update_time
    
    def test_multiple_devices_independent_states(self):
        """测试多个设备的状态独立"""
        coords = np.array([[4000.0, 0.0, 0.0]], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)
        
        # 处理多个设备
        self.decision_layer.decide("device_1", coords, labels)
        self.decision_layer.decide("device_2", coords, labels)
        self.decision_layer.decide("device_3", coords, labels)
        
        # 应该有三个独立的设备状态
        assert len(self.decision_layer._device_states) == 3
        assert "device_1" in self.decision_layer._device_states
        assert "device_2" in self.decision_layer._device_states
        assert "device_3" in self.decision_layer._device_states
        
        # 每个设备的状态应该是独立的对象
        assert self.decision_layer._device_states["device_1"] is not self.decision_layer._device_states["device_2"]
        assert self.decision_layer._device_states["device_2"] is not self.decision_layer._device_states["device_3"]
    
    def test_person_state_persists_across_calls(self):
        """测试人员状态在多次调用间持久化"""
        device_id = "device_1"
        
        # 第一次检测到人员，距离 < d_in
        coords = np.array([[2500.0, 0.0, 0.0]], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)
        
        self.decision_layer.decide(device_id, coords, labels)
        
        # 状态应该是 PENDING
        assert self.decision_layer._device_states[device_id].person_warning_state == PersonWarningState.PENDING
        
        # 第二次检测，状态应该保持
        self.decision_layer.decide(device_id, coords, labels)
        
        # 状态应该仍然是 PENDING（或转换为 ALARM）
        assert self.decision_layer._device_states[device_id].person_warning_state in [
            PersonWarningState.PENDING,
            PersonWarningState.ALARM
        ]
    
    def test_object_state_persists_across_calls(self):
        """测试物体状态在多次调用间持久化"""
        device_id = "device_1"
        
        # 第一次检测到可抓取物体
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide(device_id, coords, labels)
        
        # 应该记录最近可抓取物体
        assert self.decision_layer._device_states[device_id].nearest_object_coords is not None
        assert self.decision_layer._device_states[device_id].nearest_object_distance is not None
        
        first_coords = self.decision_layer._device_states[device_id].nearest_object_coords.copy()
        
        # 第二次检测相同物体
        self.decision_layer.decide(device_id, coords, labels)
        
        # 最近物体应该更新
        second_coords = self.decision_layer._device_states[device_id].nearest_object_coords
        assert np.allclose(first_coords, second_coords)


class TestStateExpiration:
    """测试状态过期检查"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        # 使用较短的过期时间以便测试
        config = DecisionLayerConfigDTO(state_expiration_time=0.2)  # 200ms
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_state_not_expired_within_threshold(self):
        """测试状态在阈值内不过期"""
        device_id = "device_1"
        
        # 检测到可抓取物体
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide(device_id, coords, labels)
        
        # 验证有全局目标
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is not None
        
        # 等待一段时间（小于过期时间）
        time.sleep(0.1)
        
        # 处理另一个设备的数据，触发全局目标更新
        coords2 = np.array([[1500.0, 2000.0, 0.0]], dtype=np.float32)
        self.decision_layer.decide("device_2", coords2, labels)
        
        # 设备 1 的状态不应该过期
        assert self.decision_layer._device_states[device_id].nearest_object_coords is not None
    
    def test_state_expired_after_threshold(self):
        """测试状态在超过阈值后过期"""
        device_id = "device_1"
        
        # 检测到可抓取物体
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide(device_id, coords, labels)
        
        # 验证有全局目标
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is not None
        
        # 等待超过过期时间
        time.sleep(0.3)
        
        # 处理另一个设备的数据，触发全局目标更新
        coords2 = np.array([[1500.0, 2000.0, 0.0]], dtype=np.float32)
        self.decision_layer.decide("device_2", coords2, labels)
        
        # 设备 1 的状态应该过期并被清空
        assert self.decision_layer._device_states[device_id].nearest_object_coords is None
        assert self.decision_layer._device_states[device_id].nearest_object_distance is None
    
    def test_expired_state_not_used_for_global_target(self):
        """测试过期状态不参与全局目标选择"""
        # 设备 1 的物体（距离更近）
        coords1 = np.array([[800.0, 1700.0, 0.0]], dtype=np.float32)  # 距离 ≈ 1878mm
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide("device_1", coords1, labels)
        
        # 验证设备 1 的物体是全局目标
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is not None
        assert np.allclose(target, coords1[0])
        
        # 等待设备 1 的状态过期
        time.sleep(0.3)
        
        # 设备 2 的物体（距离更远）
        coords2 = np.array([[1500.0, 2000.0, 0.0]], dtype=np.float32)  # 距离 ≈ 2500mm
        self.decision_layer.decide("device_2", coords2, labels)
        
        # 全局目标应该切换到设备 2（因为设备 1 过期）
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is not None
        assert np.allclose(target, coords2[0])
    
    def test_global_target_cleared_when_all_states_expired(self):
        """测试所有状态过期时清除全局目标"""
        # 检测到可抓取物体
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide("device_1", coords, labels)
        
        # 验证有全局目标
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is not None
        
        # 等待状态过期
        time.sleep(0.3)
        
        # 处理不可抓取的物体数据，触发全局目标更新
        danger_coords = np.array([[500.0, 500.0, 0.0]], dtype=np.float32)  # 危险区
        self.decision_layer.decide("device_1", danger_coords, labels)
        
        # 全局目标应该被清除
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is None


class TestStateUpdateTiming:
    """测试状态更新时机"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_last_update_time_set_on_object_processing(self):
        """测试处理物体时设置最后更新时间"""
        device_id = "device_1"
        
        # 记录处理前的时间
        before_time = time.time()
        
        # 处理物体数据
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide(device_id, coords, labels)
        
        # 记录处理后的时间
        after_time = time.time()
        
        # 最后更新时间应该在处理前后之间
        last_update = self.decision_layer._device_states[device_id].last_update_time
        assert before_time <= last_update <= after_time
    
    def test_last_update_time_not_set_when_no_graspable_objects(self):
        """测试没有可抓取物体时不设置最后更新时间"""
        device_id = "device_1"
        
        # 处理不可抓取的物体
        coords = np.array([[500.0, 500.0, 0.0]], dtype=np.float32)  # 危险区
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide(device_id, coords, labels)
        
        # 最后更新时间应该是 0（未设置）
        # 或者设备状态可能不存在
        if device_id in self.decision_layer._device_states:
            last_update = self.decision_layer._device_states[device_id].last_update_time
            # 如果设备状态存在，最后更新时间应该是 0 或非常小
            assert last_update == 0.0 or last_update < 0.1
