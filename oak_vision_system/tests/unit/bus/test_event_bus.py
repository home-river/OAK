"""
事件总线单元测试

测试EventBus的核心功能：
- 订阅/取消订阅
- 事件发布和分发
- 线程安全性
- 错误隔离
- 统计信息
"""

import time
import threading
import pytest
from unittest.mock import Mock, call

from oak_vision_system.core.event_bus import EventBus, EventType, Priority, get_global_event_bus, reset_global_event_bus


class TestEventBusBasics:
    """事件总线基础功能测试"""
    
    def test_event_bus_creation(self):
        """测试：创建事件总线"""
        event_bus = EventBus()
        assert event_bus is not None
        # 使用 list_subscriptions() 替代已移除的 get_all_event_types()
        assert event_bus.list_subscriptions() == []
    
    def test_subscribe_and_publish(self):
        """测试：基本的订阅和发布"""
        event_bus = EventBus()
        received_data = []
        
        def handler(data):
            received_data.append(data)
        
        # 订阅
        sub_id = event_bus.subscribe(EventType.RAW_FRAME_DATA, handler)
        assert sub_id is not None
        # 使用 list_subscriptions() 替代已移除的 get_subscriber_count()
        subs = event_bus.list_subscriptions(EventType.RAW_FRAME_DATA)
        assert len(subs) == 1
        
        # 发布（使用同步模式确保回调执行完成）
        test_data = {"frame_id": 1, "data": "test"}
        count = event_bus.publish(EventType.RAW_FRAME_DATA, test_data, wait_all=True)
        
        # 验证
        assert count == 1
        assert len(received_data) == 1
        assert received_data[0] == test_data
    
    def test_multiple_subscribers(self):
        """测试：多个订阅者"""
        event_bus = EventBus()
        
        received1 = []
        received2 = []
        received3 = []
        
        event_bus.subscribe(EventType.RAW_FRAME_DATA, lambda d: received1.append(d))
        event_bus.subscribe(EventType.RAW_FRAME_DATA, lambda d: received2.append(d))
        event_bus.subscribe(EventType.RAW_FRAME_DATA, lambda d: received3.append(d))
        
        # 使用 list_subscriptions() 替代已移除的 get_subscriber_count()
        subs = event_bus.list_subscriptions(EventType.RAW_FRAME_DATA)
        assert len(subs) == 3
        
        # 发布事件（使用同步模式确保回调执行完成）
        test_data = "test_data"
        count = event_bus.publish(EventType.RAW_FRAME_DATA, test_data, wait_all=True)
        
        # 验证所有订阅者都收到
        assert count == 3
        assert received1 == [test_data]
        assert received2 == [test_data]
        assert received3 == [test_data]
    
    def test_unsubscribe(self):
        """测试：取消订阅"""
        event_bus = EventBus()
        received = []
        
        sub_id = event_bus.subscribe(
            EventType.RAW_FRAME_DATA,
            lambda d: received.append(d)
        )
        
        # 发布第一次（使用同步模式确保回调执行完成）
        event_bus.publish(EventType.RAW_FRAME_DATA, "data1", wait_all=True)
        assert len(received) == 1
        
        # 取消订阅
        result = event_bus.unsubscribe(sub_id)
        assert result is True
        # 使用 list_subscriptions() 替代已移除的 get_subscriber_count()
        subs = event_bus.list_subscriptions(EventType.RAW_FRAME_DATA)
        assert len(subs) == 0
        
        # 发布第二次（不应该收到）
        event_bus.publish(EventType.RAW_FRAME_DATA, "data2", wait_all=True)
        assert len(received) == 1  # 仍然是1
    
    def test_unsubscribe_invalid_id(self):
        """测试：取消不存在的订阅"""
        event_bus = EventBus()
        result = event_bus.unsubscribe("invalid_id")
        assert result is False
    
    def test_publish_without_subscribers(self):
        """测试：发布事件但没有订阅者"""
        event_bus = EventBus()
        count = event_bus.publish(EventType.RAW_FRAME_DATA, "data")
        assert count == 0


class TestEventBusMultipleEventTypes:
    """多事件类型测试"""
    
    def test_different_event_types(self):
        """测试：不同的事件类型"""
        event_bus = EventBus()
        
        frame_data = []
        detection_data = []
        
        event_bus.subscribe(EventType.RAW_FRAME_DATA, lambda d: frame_data.append(d))
        event_bus.subscribe(EventType.RAW_DETECTION_DATA, lambda d: detection_data.append(d))
        
        # 发布不同类型的事件（使用同步模式确保回调执行完成）
        event_bus.publish(EventType.RAW_FRAME_DATA, "frame", wait_all=True)
        event_bus.publish(EventType.RAW_DETECTION_DATA, "detection", wait_all=True)
        
        # 验证
        assert frame_data == ["frame"]
        assert detection_data == ["detection"]
    
    def test_get_all_event_types(self):
        """测试：获取所有事件类型"""
        event_bus = EventBus()
        
        event_bus.subscribe(EventType.RAW_FRAME_DATA, lambda d: None)
        event_bus.subscribe(EventType.RAW_DETECTION_DATA, lambda d: None)
        event_bus.subscribe(EventType.PROCESSED_DATA, lambda d: None)
        
        # 使用 list_subscriptions() 获取所有订阅
        all_subs = event_bus.list_subscriptions()
        # 提取唯一的事件类型
        event_types = list(set(sub["event_type"] for sub in all_subs))
        
        assert len(event_types) == 3
        assert EventType.RAW_FRAME_DATA in event_types
        assert EventType.RAW_DETECTION_DATA in event_types
        assert EventType.PROCESSED_DATA in event_types


class TestEventBusErrorHandling:
    """错误处理测试"""
    
    def test_subscriber_exception_isolation(self):
        """测试：订阅者异常不影响其他订阅者"""
        event_bus = EventBus()
        
        received = []
        
        def bad_handler(data):
            raise ValueError("故意的错误")
        
        def good_handler(data):
            received.append(data)
        
        # 订阅两个处理器（一个会出错）
        event_bus.subscribe(EventType.RAW_FRAME_DATA, bad_handler)
        event_bus.subscribe(EventType.RAW_FRAME_DATA, good_handler)
        
        # 发布事件（使用同步模式确保回调执行完成）
        count = event_bus.publish(EventType.RAW_FRAME_DATA, "test", wait_all=True)
        
        # 验证：即使bad_handler抛异常，good_handler仍然收到数据
        # 在同步模式下，count 返回成功执行的订阅者数量
        assert count == 1  # 只有good_handler成功
        assert received == ["test"]
        

class TestEventBusThreadSafety:
    """线程安全性测试"""
    
    def test_concurrent_subscribe(self):
        """测试：并发订阅"""
        event_bus = EventBus()
        
        def subscribe_worker():
            for _ in range(10):
                event_bus.subscribe(EventType.RAW_FRAME_DATA, lambda d: None)
        
        # 创建多个线程同时订阅
        threads = [threading.Thread(target=subscribe_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证：应该有50个订阅者（5个线程 × 10次订阅）
        # 使用 list_subscriptions() 替代已移除的 get_subscriber_count()
        subs = event_bus.list_subscriptions(EventType.RAW_FRAME_DATA)
        assert len(subs) == 50
    
    def test_concurrent_publish(self):
        """测试：并发发布"""
        event_bus = EventBus()
        received = []
        lock = threading.Lock()
        
        def handler(data):
            with lock:
                received.append(data)
        
        event_bus.subscribe(EventType.RAW_FRAME_DATA, handler)
        
        def publish_worker(worker_id):
            for i in range(10):
                # 使用同步模式确保回调执行完成
                event_bus.publish(EventType.RAW_FRAME_DATA, f"worker{worker_id}_msg{i}", wait_all=True)
        
        # 创建多个线程同时发布
        threads = [
            threading.Thread(target=publish_worker, args=(i,))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证：应该收到50条消息（5个线程 × 10条消息）
        assert len(received) == 50


class TestGlobalEventBus:
    """全局事件总线测试"""
    
    def test_get_global_event_bus(self):
        """测试：获取全局事件总线"""
        reset_global_event_bus()
        
        bus1 = get_global_event_bus()
        bus2 = get_global_event_bus()
        
        # 应该是同一个实例
        assert bus1 is bus2
    
    def test_reset_global_event_bus(self):
        """测试：重置全局事件总线"""
        bus1 = get_global_event_bus()
        reset_global_event_bus()
        bus2 = get_global_event_bus()
        
        # 应该是不同的实例
        assert bus1 is not bus2


class TestEventBusPerformance:
    """性能测试"""
    
    def test_publish_performance(self):
        """测试：发布性能（简单基准）"""
        event_bus = EventBus()
        
        call_count = [0]
        
        def handler(data):
            call_count[0] += 1
        
        # 订阅10个处理器
        for _ in range(10):
            event_bus.subscribe(EventType.RAW_FRAME_DATA, handler)
        
        # 测试发布性能（使用同步模式确保回调执行完成）
        start_time = time.perf_counter()
        
        for i in range(100):
            event_bus.publish(EventType.RAW_FRAME_DATA, f"data{i}", wait_all=True)
        
        elapsed_time = time.perf_counter() - start_time
        
        # 验证
        assert call_count[0] == 1000  # 10个订阅者 × 100条消息
        
        # 性能要求：100次发布（每次10个订阅者）应该 < 1秒（放宽要求以适应同步模式）
        assert elapsed_time < 1.0, f"性能不达标: {elapsed_time*1000:.2f}ms"
        
        print(f"\n性能测试结果：")
        print(f"  100次发布（10个订阅者/次）: {elapsed_time*1000:.2f}ms")
        print(f"  平均每次发布: {elapsed_time*10:.2f}ms")


class TestEventBusRepr:
    """字符串表示测试"""
    
    def test_repr(self):
        """测试：字符串表示"""
        event_bus = EventBus()
        event_bus.subscribe(EventType.RAW_FRAME_DATA, lambda d: None)
        event_bus.publish(EventType.RAW_FRAME_DATA, "test", wait_all=True)
        
        # 验证基本的 repr 包含类名
        repr_str = repr(event_bus)
        assert "EventBus" in repr_str
        
        # 验证可以通过 list_subscriptions() 获取订阅信息
        subs = event_bus.list_subscriptions()
        assert len(subs) == 1
        assert subs[0]["event_type"] == EventType.RAW_FRAME_DATA
        assert subs[0]["total_calls"] == 1


if __name__ == "__main__":
    """直接运行测试"""
    pytest.main([__file__, "-v", "-s"])

