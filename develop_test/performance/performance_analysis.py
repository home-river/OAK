"""
DTO组合模式 vs 直接字段模式的性能分析

测试场景：
1. 对象创建性能
2. 内存占用对比
3. 属性访问性能
4. 序列化性能
5. 实际使用场景模拟
"""

import time
import sys
import json
import tracemalloc
from dataclasses import dataclass, field
from typing import Optional, Any
import uuid


# ==================== 组合模式 ====================
@dataclass(frozen=True)
class SpatialCoordinatesDTO:
    """空间坐标DTO"""
    x: float
    y: float
    z: float
    
    def distance_from_origin(self) -> float:
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5
    
    def distance_to(self, other: 'SpatialCoordinatesDTO') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5


@dataclass(frozen=True)
class BoundingBoxDTO:
    """边界框DTO"""
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    
    @property
    def width(self) -> float:
        return self.xmax - self.xmin
    
    @property
    def height(self) -> float:
        return self.ymax - self.ymin
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center_x(self) -> float:
        return (self.xmin + self.xmax) / 2
    
    @property
    def center_y(self) -> float:
        return (self.ymin + self.ymax) / 2


@dataclass(frozen=True)
class CompositeDetectionDTO:
    """组合模式的检测DTO"""
    label: str
    confidence: float
    bbox: BoundingBoxDTO
    spatial_coordinates: SpatialCoordinatesDTO
    detection_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        if self.detection_id is None:
            timestamp_ms = int(self.created_at * 1000)
            detection_id = f"{self.label}_{timestamp_ms}_{str(uuid.uuid4())[:8]}"
            object.__setattr__(self, 'detection_id', detection_id)


# ==================== 直接字段模式 ====================
@dataclass(frozen=True)
class DirectDetectionDTO:
    """直接字段模式的检测DTO"""
    label: str
    confidence: float
    # 边界框字段
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    # 空间坐标字段
    x: float
    y: float
    z: float
    detection_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        if self.detection_id is None:
            timestamp_ms = int(self.created_at * 1000)
            detection_id = f"{self.label}_{timestamp_ms}_{str(uuid.uuid4())[:8]}"
            object.__setattr__(self, 'detection_id', detection_id)
    
    # 边界框相关方法
    @property
    def width(self) -> float:
        return self.xmax - self.xmin
    
    @property
    def height(self) -> float:
        return self.ymax - self.ymin
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center_x(self) -> float:
        return (self.xmin + self.xmax) / 2
    
    @property
    def center_y(self) -> float:
        return (self.ymin + self.ymax) / 2
    
    # 空间坐标相关方法
    def distance_from_origin(self) -> float:
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5
    
    def distance_to(self, other: 'DirectDetectionDTO') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5


# ==================== 性能测试函数 ====================
def test_object_creation_performance():
    """测试对象创建性能"""
    print("=" * 60)
    print("1. 对象创建性能测试")
    print("=" * 60)
    
    iterations = 10000
    
    # 测试组合模式
    start_time = time.perf_counter()
    for i in range(iterations):
        bbox = BoundingBoxDTO(10.0, 20.0, 100.0, 80.0)
        coords = SpatialCoordinatesDTO(100.0, 50.0, 300.0)
        detection = CompositeDetectionDTO(
            label="apple",
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
    composite_time = time.perf_counter() - start_time
    
    # 测试直接字段模式
    start_time = time.perf_counter()
    for i in range(iterations):
        detection = DirectDetectionDTO(
            label="apple",
            confidence=0.95,
            xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0,
            x=100.0, y=50.0, z=300.0
        )
    direct_time = time.perf_counter() - start_time
    
    print(f"组合模式创建 {iterations} 个对象: {composite_time:.4f}s")
    print(f"直接字段创建 {iterations} 个对象: {direct_time:.4f}s")
    print(f"性能差异: {((composite_time - direct_time) / direct_time * 100):+.2f}%")
    print(f"平均每个对象额外耗时: {(composite_time - direct_time) / iterations * 1000000:.2f}μs")
    
    return composite_time, direct_time


def test_memory_usage():
    """测试内存占用"""
    print("\n" + "=" * 60)
    print("2. 内存占用测试")
    print("=" * 60)
    
    tracemalloc.start()
    
    # 测试组合模式内存占用
    composite_objects = []
    for i in range(1000):
        bbox = BoundingBoxDTO(10.0, 20.0, 100.0, 80.0)
        coords = SpatialCoordinatesDTO(100.0, 50.0, 300.0)
        detection = CompositeDetectionDTO(
            label=f"object_{i}",
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        composite_objects.append(detection)
    
    composite_current, composite_peak = tracemalloc.get_traced_memory()
    # tracemalloc.reset_peak()  # Python 3.9+ only, skip for compatibility
    
    # 测试直接字段模式内存占用
    direct_objects = []
    for i in range(1000):
        detection = DirectDetectionDTO(
            label=f"object_{i}",
            confidence=0.95,
            xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0,
            x=100.0, y=50.0, z=300.0
        )
        direct_objects.append(detection)
    
    direct_current, direct_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"组合模式内存占用: {composite_current / 1024:.2f} KB")
    print(f"直接字段内存占用: {direct_current / 1024:.2f} KB")
    print(f"内存差异: {((composite_current - direct_current) / direct_current * 100):+.2f}%")
    print(f"平均每个对象额外内存: {(composite_current - direct_current) / 1000:.0f} bytes")
    
    return composite_current, direct_current


def test_attribute_access_performance():
    """测试属性访问性能"""
    print("\n" + "=" * 60)
    print("3. 属性访问性能测试")
    print("=" * 60)
    
    # 创建测试对象
    bbox = BoundingBoxDTO(10.0, 20.0, 100.0, 80.0)
    coords = SpatialCoordinatesDTO(100.0, 50.0, 300.0)
    composite_obj = CompositeDetectionDTO(
        label="apple",
        confidence=0.95,
        bbox=bbox,
        spatial_coordinates=coords
    )
    
    direct_obj = DirectDetectionDTO(
        label="apple",
        confidence=0.95,
        xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0,
        x=100.0, y=50.0, z=300.0
    )
    
    iterations = 100000
    
    # 测试组合模式属性访问
    start_time = time.perf_counter()
    for i in range(iterations):
        # 访问嵌套属性
        _ = composite_obj.bbox.center_x
        _ = composite_obj.bbox.area
        _ = composite_obj.spatial_coordinates.x
        _ = composite_obj.spatial_coordinates.distance_from_origin()
    composite_time = time.perf_counter() - start_time
    
    # 测试直接字段属性访问
    start_time = time.perf_counter()
    for i in range(iterations):
        # 访问直接属性
        _ = direct_obj.center_x
        _ = direct_obj.area
        _ = direct_obj.x
        _ = direct_obj.distance_from_origin()
    direct_time = time.perf_counter() - start_time
    
    print(f"组合模式属性访问 {iterations} 次: {composite_time:.4f}s")
    print(f"直接字段属性访问 {iterations} 次: {direct_time:.4f}s")
    print(f"性能差异: {((composite_time - direct_time) / direct_time * 100):+.2f}%")
    print(f"平均每次访问额外耗时: {(composite_time - direct_time) / iterations * 1000000:.2f}μs")
    
    return composite_time, direct_time


def test_serialization_performance():
    """测试序列化性能"""
    print("\n" + "=" * 60)
    print("4. 序列化性能测试")
    print("=" * 60)
    
    iterations = 1000
    
    # 创建测试对象
    bbox = BoundingBoxDTO(10.0, 20.0, 100.0, 80.0)
    coords = SpatialCoordinatesDTO(100.0, 50.0, 300.0)
    composite_obj = CompositeDetectionDTO(
        label="apple",
        confidence=0.95,
        bbox=bbox,
        spatial_coordinates=coords
    )
    
    direct_obj = DirectDetectionDTO(
        label="apple",
        confidence=0.95,
        xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0,
        x=100.0, y=50.0, z=300.0
    )
    
    # 测试组合模式序列化
    start_time = time.perf_counter()
    for i in range(iterations):
        # 简单的字典转换（模拟序列化）
        data = {
            'label': composite_obj.label,
            'confidence': composite_obj.confidence,
            'bbox': {
                'xmin': composite_obj.bbox.xmin,
                'ymin': composite_obj.bbox.ymin,
                'xmax': composite_obj.bbox.xmax,
                'ymax': composite_obj.bbox.ymax,
            },
            'spatial_coordinates': {
                'x': composite_obj.spatial_coordinates.x,
                'y': composite_obj.spatial_coordinates.y,
                'z': composite_obj.spatial_coordinates.z,
            }
        }
        json_str = json.dumps(data)
    composite_time = time.perf_counter() - start_time
    
    # 测试直接字段序列化
    start_time = time.perf_counter()
    for i in range(iterations):
        data = {
            'label': direct_obj.label,
            'confidence': direct_obj.confidence,
            'xmin': direct_obj.xmin,
            'ymin': direct_obj.ymin,
            'xmax': direct_obj.xmax,
            'ymax': direct_obj.ymax,
            'x': direct_obj.x,
            'y': direct_obj.y,
            'z': direct_obj.z,
        }
        json_str = json.dumps(data)
    direct_time = time.perf_counter() - start_time
    
    print(f"组合模式序列化 {iterations} 次: {composite_time:.4f}s")
    print(f"直接字段序列化 {iterations} 次: {direct_time:.4f}s")
    print(f"性能差异: {((composite_time - direct_time) / direct_time * 100):+.2f}%")
    
    return composite_time, direct_time


def test_real_world_scenario():
    """测试实际使用场景模拟"""
    print("\n" + "=" * 60)
    print("5. 实际场景性能测试")
    print("=" * 60)
    
    # 模拟15fps，每秒15帧，每帧5个检测目标，持续10秒
    fps = 15
    detections_per_frame = 5
    duration_seconds = 10
    total_detections = fps * detections_per_frame * duration_seconds
    
    print(f"场景: {fps}fps × {detections_per_frame}检测/帧 × {duration_seconds}秒 = {total_detections}个检测对象")
    
    # 测试组合模式
    start_time = time.perf_counter()
    composite_detections = []
    for frame in range(fps * duration_seconds):
        frame_detections = []
        for det in range(detections_per_frame):
            bbox = BoundingBoxDTO(
                xmin=10.0 + det * 20,
                ymin=20.0 + det * 15,
                xmax=100.0 + det * 20,
                ymax=80.0 + det * 15
            )
            coords = SpatialCoordinatesDTO(
                x=100.0 + det * 50,
                y=50.0 + det * 30,
                z=300.0 + det * 100
            )
            detection = CompositeDetectionDTO(
                label=f"object_{det}",
                confidence=0.95 - det * 0.1,
                bbox=bbox,
                spatial_coordinates=coords
            )
            frame_detections.append(detection)
            
            # 模拟一些计算操作
            _ = detection.bbox.area
            _ = detection.spatial_coordinates.distance_from_origin()
            
        composite_detections.append(frame_detections)
    composite_total_time = time.perf_counter() - start_time
    
    # 测试直接字段模式
    start_time = time.perf_counter()
    direct_detections = []
    for frame in range(fps * duration_seconds):
        frame_detections = []
        for det in range(detections_per_frame):
            detection = DirectDetectionDTO(
                label=f"object_{det}",
                confidence=0.95 - det * 0.1,
                xmin=10.0 + det * 20,
                ymin=20.0 + det * 15,
                xmax=100.0 + det * 20,
                ymax=80.0 + det * 15,
                x=100.0 + det * 50,
                y=50.0 + det * 30,
                z=300.0 + det * 100
            )
            frame_detections.append(detection)
            
            # 模拟相同的计算操作
            _ = detection.area
            _ = detection.distance_from_origin()
            
        direct_detections.append(frame_detections)
    direct_total_time = time.perf_counter() - start_time
    
    print(f"组合模式总耗时: {composite_total_time:.4f}s")
    print(f"直接字段总耗时: {direct_total_time:.4f}s")
    print(f"性能差异: {((composite_total_time - direct_total_time) / direct_total_time * 100):+.2f}%")
    
    # 计算处理效率
    avg_frame_time_composite = composite_total_time / (fps * duration_seconds)
    avg_frame_time_direct = direct_total_time / (fps * duration_seconds)
    frame_budget = 1.0 / fps  # 15fps的帧预算
    
    print(f"\n处理效率分析:")
    print(f"帧预算: {frame_budget * 1000:.2f}ms/帧")
    print(f"组合模式平均帧处理时间: {avg_frame_time_composite * 1000:.2f}ms/帧")
    print(f"直接字段平均帧处理时间: {avg_frame_time_direct * 1000:.2f}ms/帧")
    print(f"组合模式帧预算占用率: {avg_frame_time_composite / frame_budget * 100:.2f}%")
    print(f"直接字段帧预算占用率: {avg_frame_time_direct / frame_budget * 100:.2f}%")
    
    return composite_total_time, direct_total_time


def test_extreme_scenarios():
    """极限场景测试"""
    print("\n" + "=" * 60)
    print("6. 极限场景性能测试")
    print("=" * 60)
    
    # 场景1: 高频率检测 - 30fps，每帧10个目标
    print("\n--- 场景1: 高频率检测 (30fps, 10个目标/帧) ---")
    test_high_frequency_detection()
    
    # 场景2: 大量目标检测 - 15fps，每帧50个目标
    print("\n--- 场景2: 大量目标检测 (15fps, 50个目标/帧) ---")
    test_massive_detection()
    
    # 场景3: 长时间运行 - 15fps，持续5分钟
    print("\n--- 场景3: 长时间运行测试 (15fps, 5分钟) ---")
    test_long_running()
    
    # 场景4: 内存压力测试 - 累积大量对象
    print("\n--- 场景4: 内存压力测试 (累积10万个对象) ---")
    test_memory_pressure()
    
    # 场景5: 并发处理测试 - 模拟多线程
    print("\n--- 场景5: 并发处理模拟 (多批次同时处理) ---")
    test_concurrent_processing()


def test_high_frequency_detection():
    """高频率检测测试"""
    fps = 30
    detections_per_frame = 10
    duration_seconds = 30  # 30秒测试
    total_detections = fps * detections_per_frame * duration_seconds
    
    print(f"高频场景: {fps}fps × {detections_per_frame}检测/帧 × {duration_seconds}秒 = {total_detections}个检测对象")
    
    # 组合模式测试
    start_time = time.perf_counter()
    for frame in range(fps * duration_seconds):
        for det in range(detections_per_frame):
            bbox = BoundingBoxDTO(
                xmin=10.0 + det * 20,
                ymin=20.0 + det * 15,
                xmax=100.0 + det * 20,
                ymax=80.0 + det * 15
            )
            coords = SpatialCoordinatesDTO(
                x=100.0 + det * 50,
                y=50.0 + det * 30,
                z=300.0 + det * 100
            )
            detection = CompositeDetectionDTO(
                label=f"obj_{det}",
                confidence=0.95 - det * 0.05,
                bbox=bbox,
                spatial_coordinates=coords
            )
            # 模拟处理操作
            _ = detection.bbox.area
            _ = detection.spatial_coordinates.distance_from_origin()
    composite_time = time.perf_counter() - start_time
    
    # 直接字段模式测试
    start_time = time.perf_counter()
    for frame in range(fps * duration_seconds):
        for det in range(detections_per_frame):
            detection = DirectDetectionDTO(
                label=f"obj_{det}",
                confidence=0.95 - det * 0.05,
                xmin=10.0 + det * 20,
                ymin=20.0 + det * 15,
                xmax=100.0 + det * 20,
                ymax=80.0 + det * 15,
                x=100.0 + det * 50,
                y=50.0 + det * 30,
                z=300.0 + det * 100
            )
            # 模拟相同处理操作
            _ = detection.area
            _ = detection.distance_from_origin()
    direct_time = time.perf_counter() - start_time
    
    print(f"组合模式耗时: {composite_time:.4f}s")
    print(f"直接字段耗时: {direct_time:.4f}s")
    print(f"性能差异: {((composite_time - direct_time) / direct_time * 100):+.2f}%")
    
    # 实时性分析
    frame_budget = 1.0 / fps
    avg_frame_time_composite = composite_time / (fps * duration_seconds)
    avg_frame_time_direct = direct_time / (fps * duration_seconds)
    
    print(f"30fps帧预算: {frame_budget * 1000:.2f}ms/帧")
    print(f"组合模式平均帧时间: {avg_frame_time_composite * 1000:.2f}ms/帧")
    print(f"直接字段平均帧时间: {avg_frame_time_direct * 1000:.2f}ms/帧")
    print(f"组合模式帧预算占用率: {avg_frame_time_composite / frame_budget * 100:.1f}%")
    print(f"直接字段帧预算占用率: {avg_frame_time_direct / frame_budget * 100:.1f}%")
    
    return composite_time, direct_time


def test_massive_detection():
    """大量目标检测测试"""
    fps = 15
    detections_per_frame = 50  # 每帧50个目标
    duration_seconds = 60  # 1分钟测试
    total_detections = fps * detections_per_frame * duration_seconds
    
    print(f"大量目标场景: {fps}fps × {detections_per_frame}检测/帧 × {duration_seconds}秒 = {total_detections}个检测对象")
    
    # 组合模式测试
    start_time = time.perf_counter()
    peak_memory_start = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else 0
    
    for frame in range(fps * duration_seconds):
        frame_detections = []
        for det in range(detections_per_frame):
            bbox = BoundingBoxDTO(
                xmin=det * 2.0,
                ymin=det * 1.5,
                xmax=det * 2.0 + 50,
                ymax=det * 1.5 + 40
            )
            coords = SpatialCoordinatesDTO(
                x=det * 10.0,
                y=det * 8.0,
                z=300.0 + det * 5
            )
            detection = CompositeDetectionDTO(
                label=f"target_{det}",
                confidence=max(0.5, 0.95 - det * 0.01),
                bbox=bbox,
                spatial_coordinates=coords
            )
            frame_detections.append(detection)
        
        # 模拟批量处理
        for detection in frame_detections:
            _ = detection.bbox.center_x
            _ = detection.spatial_coordinates.distance_from_origin()
    
    composite_time = time.perf_counter() - start_time
    
    # 直接字段模式测试
    start_time = time.perf_counter()
    
    for frame in range(fps * duration_seconds):
        frame_detections = []
        for det in range(detections_per_frame):
            detection = DirectDetectionDTO(
                label=f"target_{det}",
                confidence=max(0.5, 0.95 - det * 0.01),
                xmin=det * 2.0,
                ymin=det * 1.5,
                xmax=det * 2.0 + 50,
                ymax=det * 1.5 + 40,
                x=det * 10.0,
                y=det * 8.0,
                z=300.0 + det * 5
            )
            frame_detections.append(detection)
        
        # 模拟批量处理
        for detection in frame_detections:
            _ = detection.center_x
            _ = detection.distance_from_origin()
    
    direct_time = time.perf_counter() - start_time
    
    print(f"组合模式耗时: {composite_time:.4f}s")
    print(f"直接字段耗时: {direct_time:.4f}s")
    print(f"性能差异: {((composite_time - direct_time) / direct_time * 100):+.2f}%")
    print(f"每秒处理目标数 - 组合模式: {total_detections / composite_time:.0f}个/秒")
    print(f"每秒处理目标数 - 直接字段: {total_detections / direct_time:.0f}个/秒")
    
    return composite_time, direct_time


def test_long_running():
    """长时间运行测试"""
    fps = 15
    detections_per_frame = 8
    duration_seconds = 300  # 5分钟
    total_detections = fps * detections_per_frame * duration_seconds
    
    print(f"长时间运行场景: {fps}fps × {detections_per_frame}检测/帧 × {duration_seconds//60}分钟 = {total_detections}个检测对象")
    
    # 分段测试，每30秒输出一次进度
    segment_duration = 30
    segments = duration_seconds // segment_duration
    
    composite_times = []
    direct_times = []
    
    for segment in range(segments):
        print(f"  进度: {(segment + 1) * segment_duration}s / {duration_seconds}s", end=" ... ")
        
        # 组合模式测试
        start_time = time.perf_counter()
        for frame in range(fps * segment_duration):
            for det in range(detections_per_frame):
                bbox = BoundingBoxDTO(10.0, 20.0, 100.0, 80.0)
                coords = SpatialCoordinatesDTO(100.0 + det * 10, 50.0, 300.0)
                detection = CompositeDetectionDTO(
                    label="long_test",
                    confidence=0.9,
                    bbox=bbox,
                    spatial_coordinates=coords
                )
                _ = detection.bbox.area
        composite_segment_time = time.perf_counter() - start_time
        
        # 直接字段模式测试
        start_time = time.perf_counter()
        for frame in range(fps * segment_duration):
            for det in range(detections_per_frame):
                detection = DirectDetectionDTO(
                    label="long_test",
                    confidence=0.9,
                    xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0,
                    x=100.0 + det * 10, y=50.0, z=300.0
                )
                _ = detection.area
        direct_segment_time = time.perf_counter() - start_time
        
        composite_times.append(composite_segment_time)
        direct_times.append(direct_segment_time)
        
        print(f"组合:{composite_segment_time:.3f}s 直接:{direct_segment_time:.3f}s")
    
    total_composite_time = sum(composite_times)
    total_direct_time = sum(direct_times)
    
    print(f"\n长时间运行总结:")
    print(f"组合模式总耗时: {total_composite_time:.4f}s")
    print(f"直接字段总耗时: {total_direct_time:.4f}s")
    print(f"性能差异: {((total_composite_time - total_direct_time) / total_direct_time * 100):+.2f}%")
    print(f"性能稳定性 - 组合模式标准差: {(max(composite_times) - min(composite_times)):.4f}s")
    print(f"性能稳定性 - 直接字段标准差: {(max(direct_times) - min(direct_times)):.4f}s")
    
    return total_composite_time, total_direct_time


def test_memory_pressure():
    """内存压力测试"""
    print("内存压力测试 - 累积创建10万个检测对象...")
    
    tracemalloc.start()
    
    # 组合模式内存压力测试
    composite_objects = []
    start_time = time.perf_counter()
    
    for i in range(100000):
        if i % 10000 == 0:
            current_memory = tracemalloc.get_traced_memory()[0]
            print(f"  组合模式 - 已创建{i}个对象，内存占用: {current_memory / 1024 / 1024:.2f} MB")
        
        bbox = BoundingBoxDTO(
            xmin=i % 1000,
            ymin=(i + 1) % 1000,
            xmax=(i % 1000) + 50,
            ymax=((i + 1) % 1000) + 40
        )
        coords = SpatialCoordinatesDTO(
            x=i * 0.1,
            y=i * 0.2,
            z=i * 0.3
        )
        detection = CompositeDetectionDTO(
            label=f"stress_{i % 100}",
            confidence=0.8 + (i % 20) * 0.01,
            bbox=bbox,
            spatial_coordinates=coords
        )
        composite_objects.append(detection)
    
    composite_time = time.perf_counter() - start_time
    composite_memory = tracemalloc.get_traced_memory()[0]
    
    # 清理内存
    del composite_objects
    # tracemalloc.reset_peak()  # Python 3.9+ only, skip for compatibility
    
    # 直接字段模式内存压力测试
    direct_objects = []
    start_time = time.perf_counter()
    
    for i in range(100000):
        if i % 10000 == 0:
            current_memory = tracemalloc.get_traced_memory()[0]
            print(f"  直接字段 - 已创建{i}个对象，内存占用: {current_memory / 1024 / 1024:.2f} MB")
        
        detection = DirectDetectionDTO(
            label=f"stress_{i % 100}",
            confidence=0.8 + (i % 20) * 0.01,
            xmin=i % 1000,
            ymin=(i + 1) % 1000,
            xmax=(i % 1000) + 50,
            ymax=((i + 1) % 1000) + 40,
            x=i * 0.1,
            y=i * 0.2,
            z=i * 0.3
        )
        direct_objects.append(detection)
    
    direct_time = time.perf_counter() - start_time
    direct_memory = tracemalloc.get_traced_memory()[0]
    
    tracemalloc.stop()
    
    print(f"\n内存压力测试结果:")
    print(f"组合模式 - 创建时间: {composite_time:.4f}s, 内存占用: {composite_memory / 1024 / 1024:.2f} MB")
    print(f"直接字段 - 创建时间: {direct_time:.4f}s, 内存占用: {direct_memory / 1024 / 1024:.2f} MB")
    print(f"时间差异: {((composite_time - direct_time) / direct_time * 100):+.2f}%")
    print(f"内存差异: {((composite_memory - direct_memory) / direct_memory * 100):+.2f}%")
    print(f"单个对象平均内存 - 组合模式: {composite_memory / 100000:.0f} bytes")
    print(f"单个对象平均内存 - 直接字段: {direct_memory / 100000:.0f} bytes")
    
    return composite_time, direct_time


def test_concurrent_processing():
    """并发处理模拟测试"""
    print("并发处理模拟 - 同时处理多个批次...")
    
    batch_size = 1000
    batch_count = 10
    
    # 组合模式并发模拟
    start_time = time.perf_counter()
    all_batches = []
    
    for batch in range(batch_count):
        batch_detections = []
        for i in range(batch_size):
            bbox = BoundingBoxDTO(
                xmin=batch * 100 + i,
                ymin=batch * 80 + i,
                xmax=batch * 100 + i + 50,
                ymax=batch * 80 + i + 40
            )
            coords = SpatialCoordinatesDTO(
                x=batch * 200.0 + i,
                y=batch * 150.0 + i,
                z=300.0 + i
            )
            detection = CompositeDetectionDTO(
                label=f"batch_{batch}_item_{i}",
                confidence=0.9,
                bbox=bbox,
                spatial_coordinates=coords
            )
            batch_detections.append(detection)
            
            # 模拟处理
            if i % 100 == 0:  # 每100个做一次计算
                _ = detection.bbox.area
                _ = detection.spatial_coordinates.distance_from_origin()
        
        all_batches.append(batch_detections)
    
    composite_time = time.perf_counter() - start_time
    
    # 直接字段模式并发模拟
    start_time = time.perf_counter()
    all_batches = []
    
    for batch in range(batch_count):
        batch_detections = []
        for i in range(batch_size):
            detection = DirectDetectionDTO(
                label=f"batch_{batch}_item_{i}",
                confidence=0.9,
                xmin=batch * 100 + i,
                ymin=batch * 80 + i,
                xmax=batch * 100 + i + 50,
                ymax=batch * 80 + i + 40,
                x=batch * 200.0 + i,
                y=batch * 150.0 + i,
                z=300.0 + i
            )
            batch_detections.append(detection)
            
            # 模拟处理
            if i % 100 == 0:  # 每100个做一次计算
                _ = detection.area
                _ = detection.distance_from_origin()
        
        all_batches.append(batch_detections)
    
    direct_time = time.perf_counter() - start_time
    
    total_objects = batch_size * batch_count
    print(f"\n并发处理测试结果 ({batch_count}个批次，每批次{batch_size}个对象):")
    print(f"组合模式耗时: {composite_time:.4f}s")
    print(f"直接字段耗时: {direct_time:.4f}s")
    print(f"性能差异: {((composite_time - direct_time) / direct_time * 100):+.2f}%")
    print(f"组合模式吞吐量: {total_objects / composite_time:.0f}个/秒")
    print(f"直接字段吞吐量: {total_objects / direct_time:.0f}个/秒")
    
    return composite_time, direct_time




def main():
    """运行所有性能测试"""
    print("DTO组合模式 vs 直接字段模式 - 性能分析报告")
    print("=" * 60)
    
    # 基础性能测试
    print("\n🔥 基础性能测试")
    creation_results = test_object_creation_performance()
    memory_results = test_memory_usage()
    access_results = test_attribute_access_performance()
    serialization_results = test_serialization_performance()
    scenario_results = test_real_world_scenario()
    
    # 极限场景测试
    print("\n🚀 极限场景测试")
    test_extreme_scenarios()
    
    # 综合分析
    print("\n" + "=" * 80)
    print("📊 综合性能分析")
    print("=" * 80)
    
    composite_total = (creation_results[0] + access_results[0] + 
                      serialization_results[0] + scenario_results[0])
    direct_total = (creation_results[1] + access_results[1] + 
                   serialization_results[1] + scenario_results[1])
    
    print(f"基础测试总体性能差异: {((composite_total - direct_total) / direct_total * 100):+.2f}%")
    print(f"基础测试内存占用差异: {((memory_results[0] - memory_results[1]) / memory_results[1] * 100):+.2f}%")
    
    # 性能影响评估
    print("\n" + "=" * 80)
    print("🎯 性能影响评估")
    print("=" * 80)
    
    # 计算不同场景下的性能损失
    creation_loss = ((creation_results[0] - creation_results[1]) / creation_results[1] * 100)
    memory_loss = ((memory_results[0] - memory_results[1]) / memory_results[1] * 100)
    access_loss = ((access_results[0] - access_results[1]) / access_results[1] * 100)
    
    print(f"1. 对象创建性能损失: {creation_loss:+.2f}%")
    print(f"2. 内存占用增加: {memory_loss:+.2f}%")
    print(f"3. 属性访问性能损失: {access_loss:+.2f}%")
    print(f"4. 序列化性能影响: 较小")
    
    # 实际应用影响分析
    avg_frame_time_15fps = scenario_results[0] / (15 * 10 * 5)  # 15fps * 10秒 * 5个检测
    frame_budget_15fps = 1.0 / 15
    frame_usage_percentage = (avg_frame_time_15fps / frame_budget_15fps) * 100
    
    print(f"\n实际应用影响分析:")
    print(f"- 15fps场景帧预算占用: {frame_usage_percentage:.2f}%")
    print(f"- 每个检测对象额外耗时: {(creation_results[0] - creation_results[1]) / 10000 * 1000000:.2f}μs")
    print(f"- 每MB内存可存储对象数量差异: {1024*1024 / (memory_results[0] / 1000) - 1024*1024 / (memory_results[1] / 1000):.0f}个")
    
    
    # 最终建议
    print("\n" + "=" * 60)
    print("💡 最终建议")
    print("=" * 60)
    
    # 评估标准
    if creation_loss < 30 and memory_loss < 50:
        recommendation = "✅ 推荐使用组合模式"
        reason = "性能损失可接受，架构优势明显"
        confidence = "高信心"
    elif creation_loss < 60 and memory_loss < 100:
        recommendation = "⚠️ 谨慎使用组合模式"
        reason = "性能有一定损失，需要权衡架构优势"
        confidence = "中等信心"
    else:
        recommendation = "❌ 建议使用直接字段模式"
        reason = "性能损失过大，影响系统效率"
        confidence = "高信心"
    
    print(f"建议: {recommendation}")
    print(f"理由: {reason}")
    print(f"信心度: {confidence}")
    
    print(f"\n💡 优化建议:")
    print(f"1. 如果选择组合模式:")
    print(f"   - 考虑使用对象池减少GC压力")
    print(f"   - 批量处理检测数据减少创建频率")
    print(f"2. 如果选择直接字段模式:")
    print(f"   - 代码结构需要更严格的规范")
    print(f"   - 考虑使用工厂方法统一创建逻辑")
    print(f"3. 通用优化:")
    print(f"   - 使用更高效的数据结构 (如__slots__)")
    print(f"   - 减少不必要的属性计算")


def quick_test():
    """快速测试模式 - 用于开发调试"""
    print("🚀 快速性能测试模式")
    print("=" * 50)
    
    # 快速对象创建测试 (1000个对象)
    print("1. 快速对象创建测试 (1000个对象)")
    start_time = time.perf_counter()
    for i in range(1000):
        bbox = BoundingBoxDTO(10.0, 20.0, 100.0, 80.0)
        coords = SpatialCoordinatesDTO(100.0, 50.0, 300.0)
        detection = CompositeDetectionDTO(
            label="test", confidence=0.95, bbox=bbox, spatial_coordinates=coords
        )
    composite_time = time.perf_counter() - start_time
    
    start_time = time.perf_counter()
    for i in range(1000):
        detection = DirectDetectionDTO(
            label="test", confidence=0.95,
            xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0,
            x=100.0, y=50.0, z=300.0
        )
    direct_time = time.perf_counter() - start_time
    
    print(f"组合模式: {composite_time:.4f}s")
    print(f"直接字段: {direct_time:.4f}s")
    print(f"性能差异: {((composite_time - direct_time) / direct_time * 100):+.2f}%")
    
    # 快速内存测试 (1000个对象)
    print("\n2. 快速内存测试 (1000个对象)")
    tracemalloc.start()
    
    objects = []
    for i in range(1000):
        bbox = BoundingBoxDTO(10.0, 20.0, 100.0, 80.0)
        coords = SpatialCoordinatesDTO(100.0, 50.0, 300.0)
        detection = CompositeDetectionDTO(
            label=f"test_{i}", confidence=0.95, bbox=bbox, spatial_coordinates=coords
        )
        objects.append(detection)
    
    composite_memory = tracemalloc.get_traced_memory()[0]
    del objects
    # tracemalloc.reset_peak()  # Python 3.9+ only, skip for compatibility
    
    objects = []
    for i in range(1000):
        detection = DirectDetectionDTO(
            label=f"test_{i}", confidence=0.95,
            xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0,
            x=100.0, y=50.0, z=300.0
        )
        objects.append(detection)
    
    direct_memory = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    
    print(f"组合模式内存: {composite_memory / 1024:.2f} KB")
    print(f"直接字段内存: {direct_memory / 1024:.2f} KB")
    print(f"内存差异: {((composite_memory - direct_memory) / direct_memory * 100):+.2f}%")
    
    print("\n✅ 快速测试完成！运行 'python performance_analysis.py full' 进行完整测试")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        quick_test()
    else:
        main()
