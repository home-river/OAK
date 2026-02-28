"""
事件总线使用示例

演示如何使用事件总线进行模块间通信
"""

import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from oak_vision_system.core.event_bus import EventBus, EventType, Priority
from oak_vision_system.core.dto.detection_dto import (
    DetectionDTO,
    BoundingBoxDTO,
    SpatialCoordinatesDTO,
    DeviceDetectionDataDTO,
)


def example1_basic_usage():
    """示例1：基本使用"""
    print("\n" + "="*60)
    print("示例1：基本的发布-订阅")
    print("="*60)
    
    # 创建事件总线
    event_bus = EventBus()
    
    # 定义订阅者
    def display_handler(data):
        print(f"[显示模块] 收到数据: {data}")
    
    def logging_handler(data):
        print(f"[日志模块] 记录数据: {data}")
    
    # 订阅事件
    sub_id1 = event_bus.subscribe(EventType.RAW_FRAME_DATA, display_handler)
    sub_id2 = event_bus.subscribe(EventType.RAW_FRAME_DATA, logging_handler)
    
    print(f"\n已订阅: sub_id1={sub_id1[:8]}..., sub_id2={sub_id2[:8]}...")
    print(f"订阅者数量: {event_bus.get_subscriber_count(EventType.RAW_FRAME_DATA)}")
    
    # 发布事件
    print("\n发布事件...")
    event_bus.publish(EventType.RAW_FRAME_DATA, {"frame_id": 1, "data": "test_frame"})
    
    # 取消订阅
    print(f"\n取消订阅: {sub_id2[:8]}...")
    event_bus.unsubscribe(sub_id2)
    
    # 再次发布
    print("\n再次发布事件...")
    event_bus.publish(EventType.RAW_FRAME_DATA, {"frame_id": 2, "data": "test_frame2"})
    


def example2_real_world_scenario():
    """示例2：实际场景 - 数据采集→显示"""
    print("\n" + "="*60)
    print("示例2：实际场景 - 数据采集模块 → 显示模块")
    print("="*60)
    
    event_bus = EventBus()
    
    # 模拟显示模块
    class DisplayModule:
        def __init__(self, event_bus):
            self.event_bus = event_bus
            self.received_count = 0
            
            # 订阅检测数据
            event_bus.subscribe(
                EventType.RAW_DETECTION_DATA,
                self.handle_detection_data
            )
        
        def handle_detection_data(self, data: DeviceDetectionDataDTO):
            """处理检测数据"""
            self.received_count += 1
            detection_data = data
            
            print(f"\n[显示模块] 收到检测数据:")
            print(f"  设备ID: {detection_data.device_id}")
            print(f"  帧ID: {detection_data.frame_id}")
            print(f"  检测数量: {detection_data.detection_count}")
            
            for i, detection in enumerate(detection_data.detections):
                print(f"  检测{i+1}: {detection.label}, "
                      f"置信度={detection.confidence:.2f}, "
                      f"位置=({detection.spatial_coordinates.x:.0f}, "
                      f"{detection.spatial_coordinates.y:.0f}, "
                      f"{detection.spatial_coordinates.z:.0f})")
    
    # 模拟数据采集模块
    class DataCollector:
        def __init__(self, event_bus):
            self.event_bus = event_bus
        
        def publish_detection_data(self, device_id, frame_id):
            """发布检测数据"""
            # 创建检测对象
            bbox = BoundingBoxDTO(xmin=0.1, ymin=0.2, xmax=0.8, ymax=0.9)
            coords = SpatialCoordinatesDTO(x=150.0, y=250.0, z=800.0)
            
            detection = DetectionDTO(
                label="durian",
                confidence=0.95,
                bbox=bbox,
                spatial_coordinates=coords
            )
            
            # 创建设备检测数据
            device_data = DeviceDetectionDataDTO(
                device_id=device_id,
                device_alias="left_camera",
                frame_id=frame_id,
                detections=[detection]
            )
            
            # 发布到事件总线
            print(f"\n[数据采集模块] 发布检测数据: frame_id={frame_id}")
            self.event_bus.publish(EventType.RAW_DETECTION_DATA, device_data)
    
    # 创建模块
    display_module = DisplayModule(event_bus)
    data_collector = DataCollector(event_bus)
    
    # 模拟数据采集
    for frame_id in range(1, 4):
        data_collector.publish_detection_data("device_001", frame_id)
        time.sleep(0.1)  # 模拟帧间隔
    
    print(f"\n[显示模块] 总共接收到 {display_module.received_count} 帧数据")


def example3_multiple_modules():
    """示例3：多模块协作"""
    print("\n" + "="*60)
    print("示例3：多模块协作 - 数据采集→调度器→显示+控制")
    print("="*60)
    
    event_bus = EventBus()
    
    # 数据采集模块
    class DataCollector:
        def __init__(self, event_bus):
            self.event_bus = event_bus
        
        def collect_frame(self, frame_id):
            print(f"\n[数据采集] 采集帧 {frame_id}")
            event_bus.publish(
                EventType.RAW_FRAME_DATA,
                {"frame_id": frame_id, "timestamp": time.time()}
            )
    
    # 数据调度器模块
    class DataScheduler:
        def __init__(self, event_bus):
            self.event_bus = event_bus
            event_bus.subscribe(EventType.RAW_FRAME_DATA, self.handle_raw_frame)
        
        def handle_raw_frame(self, data):
            print(f"[数据调度器] 处理原始帧: frame_id={data['frame_id']}")
            
            # 模拟处理后发布给下游模块
            processed_data = {
                "frame_id": data['frame_id'],
                "processed": True,
                "target_selected": True
            }
            
            # 发布给显示模块
            event_bus.publish(EventType.PROCESSED_DISPLAY_DATA, processed_data)
            
            # 发布给控制模块
            event_bus.publish(EventType.TARGET_COORDINATES, {
                "x": 100, "y": 200, "z": 300
            })
    
    # 显示模块
    class DisplayModule:
        def __init__(self, event_bus):
            event_bus.subscribe(EventType.PROCESSED_DISPLAY_DATA, self.handle_display_data)
        
        def handle_display_data(self, data):
            print(f"[显示模块] 显示帧: frame_id={data['frame_id']}")
    
    # 控制模块
    class ControlModule:
        def __init__(self, event_bus):
            event_bus.subscribe(EventType.TARGET_COORDINATES, self.handle_target)
        
        def handle_target(self, coords):
            print(f"[控制模块] 移动到目标: ({coords['x']}, {coords['y']}, {coords['z']})")
    
    # 创建所有模块
    collector = DataCollector(event_bus)
    scheduler = DataScheduler(event_bus)
    display = DisplayModule(event_bus)
    control = ControlModule(event_bus)
    
    # 模拟数据流
    for i in range(1, 4):
        collector.collect_frame(i)
        time.sleep(0.1)
    
    print(f"\n[事件总线] {event_bus}")


def example4_error_isolation():
    """示例4：错误隔离"""
    print("\n" + "="*60)
    print("示例4：错误隔离 - 一个订阅者出错不影响其他订阅者")
    print("="*60)
    
    event_bus = EventBus()
    
    def good_handler1(data):
        print(f"[处理器1] 成功处理: {data}")
    
    def bad_handler(data):
        print(f"[处理器2] 准备处理...")
        raise ValueError("故意抛出的异常！")
    
    def good_handler2(data):
        print(f"[处理器3] 成功处理: {data}")
    
    # 订阅
    event_bus.subscribe(EventType.RAW_FRAME_DATA, good_handler1)
    event_bus.subscribe(EventType.RAW_FRAME_DATA, bad_handler)
    event_bus.subscribe(EventType.RAW_FRAME_DATA, good_handler2)
    
    # 发布事件
    print("\n发布事件...")
    count = event_bus.publish(EventType.RAW_FRAME_DATA, "test_data")
    
    print(f"\n成功调用的订阅者数量: {count}")
    print("\n注意：处理器2抛出异常，但处理器1和3仍然正常工作！")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("事件总线使用示例")
    print("="*60)
    
    # 运行所有示例
    example1_basic_usage()
    example2_real_world_scenario()
    example3_multiple_modules()
    example4_error_isolation()
    
    print("\n" + "="*60)
    print("所有示例运行完成！")
    print("="*60)


if __name__ == "__main__":
    main()

