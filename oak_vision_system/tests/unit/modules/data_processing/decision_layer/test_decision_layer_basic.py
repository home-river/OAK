"""
决策层基础功能测试

测试内容：
- 空输入返回空列表
- 输入验证错误处理
- 单例模式

需求：1.3, 16.1, 14.1-14.7
"""

import pytest
import numpy as np
import threading

from oak_vision_system.modules.data_processing.decision_layer import DecisionLayer
from oak_vision_system.modules.data_processing.decision_layer.types import (
    DetectionStatusLabel,
)
from oak_vision_system.core.event_bus import EventBus
from oak_vision_system.core.dto.config_dto import (
    DecisionLayerConfigDTO,
    PersonWarningConfigDTO,
    ObjectZonesConfigDTO,
    GraspZoneConfigDTO,
)


@pytest.fixture
def event_bus():
    """创建事件总线实例"""
    return EventBus()


@pytest.fixture
def default_config():
    """创建默认配置"""
    return DecisionLayerConfigDTO(
        person_label_ids=[0],
        person_warning=PersonWarningConfigDTO(
            d_in=3000.0,
            d_out=3200.0,
            T_warn=3.0,
            T_clear=3.0,
            grace_time=0.5
        ),
        object_zones=ObjectZonesConfigDTO(
            danger_y_threshold=1500.0,
            grasp_zone=GraspZoneConfigDTO(
                mode="rect",
                x_min=500.0,
                x_max=2000.0,
                y_min=300.0,
                y_max=1500.0
            )
        ),
        state_expiration_time=1.0
    )


@pytest.fixture
def decision_layer(event_bus, default_config):
    """
    创建决策层实例
    
    注意：由于 DecisionLayer 是单例，需要在每个测试后重置
    """
    # 重置单例（用于测试）
    DecisionLayer._instance = None
    
    # 创建新实例
    layer = DecisionLayer(event_bus, default_config)
    
    yield layer
    
    # 清理：重置单例
    DecisionLayer._instance = None


class TestEmptyInput:
    """测试空输入返回空列表（需求 1.3）"""
    
    def test_decide_empty_input_returns_empty_list(self, decision_layer):
        """
        测试空输入返回空列表
        
        验证需求：1.3 - WHEN 输入数据为空（零个检测对象）THEN THE decide() SHALL 返回空的状态标签列表
        """
        # 准备空输入
        coords = np.empty((0, 3), dtype=np.float32)
        labels = np.empty((0,), dtype=np.int32)
        
        # 调用 decide()
        result = decision_layer.decide("device_1", coords, labels)
        
        # 验证返回空列表
        assert result == []
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_decide_empty_input_multiple_calls(self, decision_layer):
        """
        测试多次调用空输入都返回空列表
        
        验证需求：1.3 - 确保空输入处理的一致性
        """
        coords = np.empty((0, 3), dtype=np.float32)
        labels = np.empty((0,), dtype=np.int32)
        
        # 多次调用
        for i in range(5):
            result = decision_layer.decide(f"device_{i}", coords, labels)
            assert result == []


class TestInputValidation:
    """测试输入验证错误处理（需求 16.1）"""
    
    def test_validate_input_invalid_coords_type(self, decision_layer):
        """
        测试坐标数组类型错误
        
        验证需求：16.1 - WHEN 输入数据格式错误 THEN THE decide() SHALL 抛出异常
        """
        # 准备错误类型的输入（列表而非 ndarray）
        coords = [[1.0, 2.0, 3.0]]
        labels = np.array([0], dtype=np.int32)
        
        # 验证抛出 ValueError
        with pytest.raises(ValueError, match="filtered_coords 必须是 np.ndarray 类型"):
            decision_layer._validate_input(coords, labels)
    
    def test_validate_input_invalid_coords_shape_2d(self, decision_layer):
        """
        测试坐标数组形状错误（2列而非3列）
        
        验证需求：16.1 - 坐标数组形状必须为 (N, 3)
        """
        # 准备形状错误的输入 (1, 2)
        coords = np.array([[1.0, 2.0]], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)
        
        # 验证抛出 ValueError
        with pytest.raises(ValueError, match="形状必须为 \\(N, 3\\)"):
            decision_layer._validate_input(coords, labels)
    
    def test_validate_input_invalid_coords_shape_1d(self, decision_layer):
        """
        测试坐标数组形状错误（1维而非2维）
        
        验证需求：16.1 - 坐标数组形状必须为 (N, 3)
        """
        # 准备形状错误的输入 (3,)
        coords = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)
        
        # 验证抛出 ValueError
        with pytest.raises(ValueError, match="形状必须为 \\(N, 3\\)"):
            decision_layer._validate_input(coords, labels)
    
    def test_validate_input_invalid_labels_type(self, decision_layer):
        """
        测试标签数组类型错误
        
        验证需求：16.1 - WHEN 输入数据格式错误 THEN THE decide() SHALL 抛出异常
        """
        # 准备错误类型的输入（列表而非 ndarray）
        coords = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        labels = [0]
        
        # 验证抛出 ValueError
        with pytest.raises(ValueError, match="filtered_labels 必须是 np.ndarray 类型"):
            decision_layer._validate_input(coords, labels)
    
    def test_validate_input_invalid_labels_shape(self, decision_layer):
        """
        测试标签数组形状错误（2维而非1维）
        
        验证需求：16.1 - 标签数组形状必须为 (N,)
        """
        # 准备形状错误的输入 (1, 1)
        coords = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        labels = np.array([[0]], dtype=np.int32)
        
        # 验证抛出 ValueError
        with pytest.raises(ValueError, match="形状必须为 \\(N,\\)"):
            decision_layer._validate_input(coords, labels)
    
    def test_validate_input_length_mismatch(self, decision_layer):
        """
        测试坐标数组和标签数组长度不一致
        
        验证需求：16.1 - 验证长度一致性
        """
        # 准备长度不一致的输入
        coords = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)  # 长度为1，而coords长度为2
        
        # 验证抛出 ValueError
        with pytest.raises(ValueError, match="坐标数组长度.*与标签数组长度.*不一致"):
            decision_layer._validate_input(coords, labels)
    
    def test_validate_input_valid_data(self, decision_layer):
        """
        测试有效输入不抛出异常
        
        验证需求：16.1 - 有效输入应该通过验证
        """
        # 准备有效输入
        coords = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        labels = np.array([0, 1], dtype=np.int32)
        
        # 验证不抛出异常
        decision_layer._validate_input(coords, labels)  # 应该正常执行


class TestSingletonPattern:
    """测试单例模式（需求 14.1-14.7）"""
    
    def test_singleton_same_instance(self, event_bus, default_config):
        """
        测试多次创建返回同一个实例
        
        验证需求：14.1, 14.4 - THE Decision_Layer SHALL 实现单例模式，
        WHEN 多次调用构造函数 THEN THE 方法 SHALL 返回同一个实例
        """
        # 重置单例
        DecisionLayer._instance = None
        
        # 创建第一个实例
        layer1 = DecisionLayer(event_bus, default_config)
        
        # 创建第二个实例
        layer2 = DecisionLayer(event_bus, default_config)
        
        # 验证是同一个实例
        assert layer1 is layer2
        
        # 清理
        DecisionLayer._instance = None
    
    def test_singleton_get_instance_after_init(self, event_bus, default_config):
        """
        测试 get_instance() 返回已初始化的实例
        
        验证需求：14.3 - THE Decision_Layer SHALL 提供 get_instance() 类方法获取单例实例
        """
        # 重置单例
        DecisionLayer._instance = None
        
        # 先创建实例
        layer1 = DecisionLayer(event_bus, default_config)
        
        # 通过 get_instance() 获取
        layer2 = DecisionLayer.get_instance()
        
        # 验证是同一个实例
        assert layer1 is layer2
        
        # 清理
        DecisionLayer._instance = None
    
    def test_singleton_get_instance_before_init_raises_error(self):
        """
        测试在初始化前调用 get_instance() 抛出异常
        
        验证需求：14.7 - WHEN get_instance() 被调用但实例尚未创建 
        THEN THE 方法 SHALL 抛出 RuntimeError
        """
        # 重置单例
        DecisionLayer._instance = None
        
        # 验证抛出 RuntimeError
        with pytest.raises(RuntimeError, match="DecisionLayer 尚未初始化"):
            DecisionLayer.get_instance()
    
    def test_singleton_no_reinitialization(self, event_bus, default_config):
        """
        测试防止重复初始化
        
        验证需求：14.5, 14.6 - THE Decision_Layer SHALL 在首次实例化时初始化所有内部状态，
        THE Decision_Layer SHALL 防止通过 __init__ 重复初始化已存在的实例
        """
        # 重置单例
        DecisionLayer._instance = None
        
        # 创建第一个实例
        layer1 = DecisionLayer(event_bus, default_config)
        
        # 记录初始状态
        initial_device_states = layer1._device_states
        
        # 尝试再次初始化（应该被忽略）
        layer2 = DecisionLayer(event_bus, default_config)
        
        # 验证是同一个实例
        assert layer1 is layer2
        
        # 验证内部状态没有被重置
        assert layer1._device_states is initial_device_states
        
        # 清理
        DecisionLayer._instance = None
    
    def test_singleton_thread_safety(self, event_bus, default_config):
        """
        测试单例模式的线程安全性
        
        验证需求：14.2 - THE Decision_Layer SHALL 使用线程安全的单例实现（双重检查锁定）
        """
        # 重置单例
        DecisionLayer._instance = None
        
        instances = []
        errors = []
        
        def create_instance():
            try:
                layer = DecisionLayer(event_bus, default_config)
                instances.append(layer)
            except Exception as e:
                errors.append(e)
        
        # 创建多个线程同时创建实例
        threads = []
        for _ in range(10):
            t = threading.Thread(target=create_instance)
            threads.append(t)
        
        # 启动所有线程
        for t in threads:
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证没有错误
        assert len(errors) == 0
        
        # 验证所有实例都是同一个
        assert len(instances) == 10
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance
        
        # 清理
        DecisionLayer._instance = None


class TestBasicFunctionality:
    """测试基础功能集成"""
    
    def test_decide_with_valid_input_returns_correct_length(self, decision_layer):
        """
        测试有效输入返回正确长度的结果
        
        验证需求：1.2, 1.9 - WHEN decide() 完成处理 THEN THE 方法 SHALL 返回与输入长度一致的状态标签列表
        """
        # 准备有效输入（3个对象）
        coords = np.array([
            [1000.0, 500.0, 0.0],
            [2000.0, 300.0, 0.0],
            [3000.0, 200.0, 0.0]
        ], dtype=np.float32)
        labels = np.array([0, 1, 1], dtype=np.int32)  # 1个人员，2个物体
        
        # 调用 decide()
        result = decision_layer.decide("device_1", coords, labels)
        
        # 验证返回列表长度与输入一致
        assert len(result) == 3
        assert isinstance(result, list)
        
        # 验证所有元素都是 DetectionStatusLabel 枚举
        for label in result:
            assert isinstance(label, DetectionStatusLabel)
    
    def test_decide_returns_detection_status_labels(self, decision_layer):
        """
        测试返回的是 DetectionStatusLabel 枚举类型
        
        验证需求：17.4 - THE decide() SHALL 使用 DetectionStatusLabel 枚举类型作为状态标签
        """
        # 准备输入
        coords = np.array([[1000.0, 500.0, 0.0]], dtype=np.float32)
        labels = np.array([0], dtype=np.int32)
        
        # 调用 decide()
        result = decision_layer.decide("device_1", coords, labels)
        
        # 验证返回的是枚举类型
        assert len(result) == 1
        assert isinstance(result[0], DetectionStatusLabel)
        
        # 验证枚举值在有效范围内
        assert result[0] in [
            DetectionStatusLabel.OBJECT_GRASPABLE,
            DetectionStatusLabel.OBJECT_DANGEROUS,
            DetectionStatusLabel.OBJECT_OUT_OF_RANGE,
            DetectionStatusLabel.OBJECT_PENDING_GRASP,
            DetectionStatusLabel.HUMAN_SAFE,
            DetectionStatusLabel.HUMAN_DANGEROUS
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
