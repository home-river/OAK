"""
决策层线程安全测试

测试 DecisionLayer 类的线程安全性，包括：
- 并发访问 get_target_coords_snapshot()
- 并发更新全局目标
- 锁竞争情况
"""

import pytest
import numpy as np
import threading
import time

from oak_vision_system.core.event_bus import EventBus
from oak_vision_system.core.dto.config_dto import DecisionLayerConfigDTO
from oak_vision_system.modules.data_processing.decision_layer import DecisionLayer


class TestConcurrentTargetAccess:
    """测试并发访问目标坐标"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_concurrent_get_target_coords_snapshot(self):
        """测试并发调用 get_target_coords_snapshot()"""
        # 设置全局目标
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide("device_1", coords, labels)
        
        # 并发读取目标坐标
        results = []
        errors = []
        
        def reader_thread():
            try:
                for _ in range(100):
                    target = self.decision_layer.get_target_coords_snapshot()
                    results.append(target)
            except Exception as e:
                errors.append(e)
        
        # 启动多个读线程
        threads = [threading.Thread(target=reader_thread) for _ in range(10)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证无错误
        assert len(errors) == 0
        
        # 验证所有读取都成功
        assert len(results) == 1000  # 10 个线程 × 100 次
        
        # 验证所有结果都是有效的（None 或正确的坐标）
        for result in results:
            if result is not None:
                assert result.shape == (3,)
                assert np.allclose(result, coords[0])
    
    def test_concurrent_read_write_target(self):
        """测试并发读写目标坐标"""
        results = []
        errors = []
        
        def reader_thread():
            try:
                for _ in range(50):
                    target = self.decision_layer.get_target_coords_snapshot()
                    results.append(target)
                    time.sleep(0.001)  # 短暂休眠
            except Exception as e:
                errors.append(e)
        
        def writer_thread(device_id):
            try:
                for i in range(50):
                    # 生成随机坐标
                    coords = (np.random.rand(1, 3) * 3000 + 1000).astype(np.float32)
                    labels = np.array([1], dtype=np.int32)
                    self.decision_layer.decide(device_id, coords, labels)
                    time.sleep(0.001)  # 短暂休眠
            except Exception as e:
                errors.append(e)
        
        # 启动读写线程
        threads = []
        threads.extend([threading.Thread(target=reader_thread) for _ in range(5)])
        threads.extend([threading.Thread(target=writer_thread, args=(f"device_{i}",)) for i in range(3)])
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证无错误
        assert len(errors) == 0
        
        # 验证所有读取都成功
        assert len(results) == 250  # 5 个读线程 × 50 次
    
    def test_target_coords_snapshot_returns_copy(self):
        """测试 get_target_coords_snapshot() 返回副本"""
        # 设置全局目标
        coords = np.array([[1000.0, 1800.0, 0.0]], dtype=np.float32)
        labels = np.array([1], dtype=np.int32)
        
        self.decision_layer.decide("device_1", coords, labels)
        
        # 获取目标坐标
        target1 = self.decision_layer.get_target_coords_snapshot()
        target2 = self.decision_layer.get_target_coords_snapshot()
        
        # 应该是不同的对象（副本）
        assert target1 is not target2
        
        # 但值应该相同
        assert np.allclose(target1, target2)
        
        # 修改副本不应该影响内部状态
        target1[0] = 9999.0
        target3 = self.decision_layer.get_target_coords_snapshot()
        
        # 内部状态应该未改变
        assert not np.allclose(target3, target1)
        assert np.allclose(target3, target2)


class TestConcurrentGlobalTargetUpdate:
    """测试并发更新全局目标"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_concurrent_decide_calls(self):
        """测试并发调用 decide() 方法"""
        errors = []
        
        def process_device(device_id):
            try:
                for _ in range(50):
                    # 生成随机坐标
                    coords = (np.random.rand(5, 3) * 3000 + 1000).astype(np.float32)
                    labels = np.random.randint(0, 5, size=5, dtype=np.int32)
                    self.decision_layer.decide(device_id, coords, labels)
            except Exception as e:
                errors.append(e)
        
        # 启动多个设备处理线程
        threads = [threading.Thread(target=process_device, args=(f"device_{i}",)) for i in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证无错误
        assert len(errors) == 0
        
        # 验证设备状态被正确创建
        assert len(self.decision_layer._device_states) == 5
    
    def test_concurrent_global_target_selection(self):
        """测试并发全局目标选择的一致性"""
        errors = []
        
        def process_device(device_id, base_y):
            try:
                for i in range(20):
                    # 生成在抓取区内的坐标
                    # x ∈ (-200, 2000)，|y| ∈ (1550, 2500)
                    x = 1000.0 + i * 10
                    y = base_y + i * 5  # 确保 y 在抓取区范围内
                    coords = np.array([[x, y, 0.0]], dtype=np.float32)
                    labels = np.array([1], dtype=np.int32)
                    self.decision_layer.decide(device_id, coords, labels)
                    time.sleep(0.01)  # 短暂休眠
            except Exception as e:
                errors.append(e)
        
        # 启动多个设备处理线程，每个设备的物体位置不同
        # 确保 y 坐标在抓取区范围内：|y| ∈ (1550, 2500)
        threads = [
            threading.Thread(target=process_device, args=(f"device_{i}", 1600.0 + i * 100))
            for i in range(3)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证无错误
        assert len(errors) == 0
        
        # 等待一小段时间确保所有更新完成
        time.sleep(0.1)
        
        # 验证最终有全局目标
        target = self.decision_layer.get_target_coords_snapshot()
        assert target is not None, "Expected global target to be set after concurrent processing"


class TestLockContention:
    """测试锁竞争情况"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        self.decision_layer = DecisionLayer(event_bus, config)
    
    def test_high_frequency_read_write(self):
        """测试高频率读写操作"""
        errors = []
        read_count = [0]
        write_count = [0]
        
        def high_frequency_reader():
            try:
                for _ in range(200):
                    self.decision_layer.get_target_coords_snapshot()
                    read_count[0] += 1
            except Exception as e:
                errors.append(e)
        
        def high_frequency_writer(device_id):
            try:
                for _ in range(100):
                    coords = (np.random.rand(3, 3) * 3000 + 1000).astype(np.float32)
                    labels = np.random.randint(1, 5, size=3, dtype=np.int32)
                    self.decision_layer.decide(device_id, coords, labels)
                    write_count[0] += 1
            except Exception as e:
                errors.append(e)
        
        # 启动高频率读写线程
        threads = []
        threads.extend([threading.Thread(target=high_frequency_reader) for _ in range(10)])
        threads.extend([threading.Thread(target=high_frequency_writer, args=(f"device_{i}",)) for i in range(5)])
        
        start_time = time.time()
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        elapsed_time = time.time() - start_time
        
        # 验证无错误
        assert len(errors) == 0
        
        # 验证所有操作都完成
        assert read_count[0] == 2000  # 10 个读线程 × 200 次
        assert write_count[0] == 500  # 5 个写线程 × 100 次
        
        # 验证性能（总时间应该合理）
        # 2000 次读 + 500 次写，应该在几秒内完成
        assert elapsed_time < 10.0, f"操作耗时过长: {elapsed_time:.2f}s"
    
    def test_no_deadlock_with_nested_locks(self):
        """测试嵌套锁不会导致死锁"""
        errors = []
        
        def process_with_read():
            try:
                for _ in range(50):
                    # 调用 decide()，内部会调用 _update_global_target()
                    # _update_global_target() 会获取锁
                    coords = (np.random.rand(2, 3) * 3000 + 1000).astype(np.float32)
                    labels = np.random.randint(1, 5, size=2, dtype=np.int32)
                    self.decision_layer.decide("device_1", coords, labels)
                    
                    # 立即读取目标坐标（也会获取锁）
                    self.decision_layer.get_target_coords_snapshot()
            except Exception as e:
                errors.append(e)
        
        # 启动多个线程
        threads = [threading.Thread(target=process_with_read) for _ in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证无错误（无死锁）
        assert len(errors) == 0


class TestSingletonThreadSafety:
    """测试单例模式的线程安全性"""
    
    def setup_method(self):
        """每个测试前重置单例"""
        DecisionLayer._instance = None
    
    def test_concurrent_singleton_creation(self):
        """测试并发创建单例"""
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        
        instances = []
        errors = []
        
        def create_instance():
            try:
                instance = DecisionLayer(event_bus, config)
                instances.append(instance)
            except Exception as e:
                errors.append(e)
        
        # 创建多个线程同时实例化
        threads = [threading.Thread(target=create_instance) for _ in range(20)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证无错误
        assert len(errors) == 0
        
        # 验证所有实例都是同一个对象
        assert len(instances) == 20
        assert all(inst is instances[0] for inst in instances)
    
    def test_concurrent_get_instance(self):
        """测试并发调用 get_instance()"""
        # 先创建实例
        event_bus = EventBus()
        config = DecisionLayerConfigDTO()
        DecisionLayer(event_bus, config)
        
        instances = []
        errors = []
        
        def get_instance():
            try:
                instance = DecisionLayer.get_instance()
                instances.append(instance)
            except Exception as e:
                errors.append(e)
        
        # 创建多个线程同时获取实例
        threads = [threading.Thread(target=get_instance) for _ in range(20)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证无错误
        assert len(errors) == 0
        
        # 验证所有实例都是同一个对象
        assert len(instances) == 20
        assert all(inst is instances[0] for inst in instances)
