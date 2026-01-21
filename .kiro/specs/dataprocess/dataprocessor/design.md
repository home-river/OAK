# DataProcessor 设计文档

## 概述

DataProcessor 是数据处理流水线的顶层协调组件，负责协调坐标变换和滤波处理流程，并完成数据格式的转换和组装。该模块基于现有的 CoordinateTransformer 和 FilterManager 构建，提供更高层次的数据流协调能力。

### 设计目标

1. **清晰的职责划分**：专注于协调和数据转换，不涉及具体算法实现
2. **高性能**：使用 NumPy 向量化操作，满足实时处理要求（20-30 FPS）
3. **简洁接口**：提供单一的 process 方法处理完整数据流
4. **可扩展性**：通过依赖注入支持不同的坐标变换和滤波实现

## 架构设计

### 系统层次

```
DataProcessor (顶层协调层)
    ├─ 数据接收与提取
    ├─ 数据格式转换（DTO ↔ NumPy）
    ├─ 协调子模块调用
    └─ 输出数据组装
    
CoordinateTransformer (坐标变换层 - 现有实现)
    └─ 设备坐标系 → 世界坐标系
    
FilterManager (滤波管理层 - 现有实现)
    └─ 管理多个 FilterPool 实例
        └─ 滤波和目标跟踪
```

### 核心职责

1. **数据接收阶段**：
   - 接收 DeviceDetectionDataDTO
   - 提取 device_id、frame_id、device_alias、detections

2. **数据转换阶段**：
   - 将 List[DetectionDTO] 转换为 NumPy 数组
   - 提取 coordinates、bboxes、confidences、labels

3. **处理阶段**：
   - 调用 CoordinateTransformer 进行坐标变换
   - 调用 FilterManager 进行滤波处理

4. **输出组装阶段**：
   - 将处理后的 NumPy 数组组装为 DeviceProcessedDataDTO
   - 保持数据的对应关系

## 组件和接口

### 类定义

```python
class DataProcessor:
    """数据处理器
    
    顶层协调组件，负责协调坐标变换和滤波流程。
    
    架构层次：
        DataProcessor (协调层)
            ├─ CoordinateTransformer (坐标变换)
            └─ FilterManager (滤波管理)
    
    使用示例：
        >>> config = DataProcessingConfigDTO(...)
        >>> device_metadata = {...}
        >>> 
        >>> processor = DataProcessor(
        ...     config=config,
        ...     device_metadata=device_metadata,
        ... )
        >>> 
        >>> # 处理数据
        >>> detection_data = DeviceDetectionDataDTO(...)
        >>> processed_data = processor.process(detection_data)
    """
    
    def __init__(
        self,
        *,
        config: DataProcessingConfigDTO,
        device_metadata: Dict[str, DeviceMetadataDTO],
    ) -> None:
        """初始化 DataProcessor
        
        Args:
            config: 数据处理配置对象
            device_metadata: 设备元数据字典，映射 MXid 到 DeviceMetadataDTO
        
        Raises:
            ValueError: 当配置参数无效时
        """
    
    def process(
        self,
        detection_data: DeviceDetectionDataDTO,
    ) -> DeviceProcessedDataDTO:
        """处理一帧检测数据
        
        工作流：
        1. 提取数据并转换为 NumPy 格式
        2. 坐标变换
        3. 滤波处理
        4. 重新组装为输出 DTO
        
        Args:
            detection_data: 设备检测数据
            
        Returns:
            DeviceProcessedDataDTO: 处理后的数据
        
        Raises:
            ValueError: 当输入数据无效时
        """
```

### 内部数据结构

```python
class DataProcessor:
    _config: DataProcessingConfigDTO              # 数据处理配置
    _device_metadata: Dict[str, DeviceMetadataDTO]  # 设备元数据
    _transformer: CoordinateTransformer           # 坐标变换器
    _filter_manager: FilterManager                # 滤波管理器
    _event_bus: EventBus                          # 事件总线实例
```

## 数据模型

### 输入数据格式

```python
# DeviceDetectionDataDTO
device_id: str                    # 设备 MXid
frame_id: int                     # 帧ID
device_alias: Optional[str]       # 设备别名
detections: List[DetectionDTO]    # 检测结果列表

# DetectionDTO
label: int                        # 标签
confidence: float                 # 置信度
bbox: BoundingBoxDTO              # 边界框
spatial_coordinates: SpatialCoordinatesDTO  # 空间坐标
```

### 中间数据格式

```python
# NumPy 数组格式
coordinates: np.ndarray           # 形状 (n, 3)，dtype=float32
bboxes: np.ndarray                # 形状 (n, 4)，dtype=float32
confidences: np.ndarray           # 形状 (n,)，dtype=float32
labels: np.ndarray                # 形状 (n,)，dtype=int32
```

### 输出数据格式

```python
# DeviceProcessedDataDTO
device_id: str                    # 设备 MXid
frame_id: int                     # 帧ID
device_alias: Optional[str]       # 设备别名
coords: np.ndarray                # 形状 (m, 3)，dtype=float32
bbox: np.ndarray                  # 形状 (m, 4)，dtype=float32
confidence: np.ndarray            # 形状 (m,)，dtype=float32
labels: np.ndarray                # 形状 (m,)，dtype=int32
state_label: List[DetectionStatusLabel]  # 状态标签列表（初始为空）
```

### 数据流示例

```python
# 输入
detection_data = DeviceDetectionDataDTO(
    device_id="device_001",
    frame_id=100,
    device_alias="front_camera",
    detections=[
        DetectionDTO(label=0, confidence=0.9, bbox=..., spatial_coordinates=...),
        DetectionDTO(label=1, confidence=0.8, bbox=..., spatial_coordinates=...),
    ]
)

# 提取 NumPy 数组
coordinates = np.array([[x1,y1,z1], [x2,y2,z2]], dtype=np.float32)
bboxes = np.array([[...], [...]], dtype=np.float32)
confidences = np.array([0.9, 0.8], dtype=np.float32)
labels = np.array([0, 1], dtype=np.int32)

# 坐标变换
transformed_coords = transformer.get_trans_matrices(device_id, detections)
# 形状 (2, 3)

# 滤波处理
filtered_coords, filtered_bboxes, filtered_confs, filtered_labels = \
    filter_manager.process(device_id, transformed_coords, bboxes, confidences, labels)
# 形状可能变化（取决于滤波结果）

# 输出
processed_data = DeviceProcessedDataDTO(
    device_id="device_001",
    frame_id=100,
    device_alias="front_camera",
    coords=filtered_coords,
    bbox=filtered_bboxes,
    confidence=filtered_confs,
    labels=filtered_labels,
    state_label=[],
)
```

## 正确性属性

*属性是关于系统行为的形式化陈述，应该在所有有效执行中保持为真。这些属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*


### 属性反思

在编写正确性属性之前，我需要识别并消除冗余的属性：

**冗余分析**：
1. **字段传递属性**（1.1, 1.2, 1.3, 5.2, 5.3, 5.4）可以合并为一个综合属性：验证所有元数据字段正确传递
2. **数组格式属性**（2.1, 2.2, 2.3, 2.4）可以合并为一个综合属性：验证所有数组的形状和 dtype
3. **数据传递属性**（5.5, 5.6, 5.7, 5.8）可以合并为一个综合属性：验证所有处理后的数据正确传递
4. **初始化属性**（3.1, 4.1）可以合并：验证所有子模块正确初始化

**保留的核心属性**：
- 元数据字段传递（合并 1.1-1.3, 5.2-5.4）
- 数组格式正确性（合并 2.1-2.4）
- 数据对应关系（2.5）
- 坐标变换执行（3.2, 3.5）
- 滤波处理执行（4.2, 4.6）
- 处理后数据传递（合并 5.5-5.8）
- 空输入处理（1.5, 7.4）
- 配置验证（7.1, 7.2）

### 属性 1：元数据字段传递完整性
*对于任意* DeviceDetectionDataDTO 输入，输出的 DeviceProcessedDataDTO 应该保持相同的 device_id、frame_id 和 device_alias
**验证需求：1.1, 1.2, 1.3, 5.2, 5.3, 5.4**

### 属性 2：数组格式正确性
*对于任意* 包含 n 个检测结果的输入，输出应该包含：
- coords: 形状 (m, 3)，dtype=float32
- bbox: 形状 (m, 4)，dtype=float32
- confidence: 形状 (m,)，dtype=float32
- labels: 形状 (m,)，dtype=int32
其中 m 为滤波后的检测数量
**验证需求：2.1, 2.2, 2.3, 2.4**

### 属性 3：输出数组长度一致性
*对于任意* 输入，输出的 coords、bbox、confidence、labels 数组的第一维长度应该相等
**验证需求：2.5**

### 属性 4：坐标变换执行
*对于任意* 非空输入，输出的坐标应该与输入的原始坐标不同（已被变换）
**验证需求：3.2, 3.5**

### 属性 5：滤波处理执行
*对于任意* 输入，输出的数据应该经过滤波处理（可以通过多帧输入验证滤波效果）
**验证需求：4.2, 4.6**

### 属性 6：空输入处理
*对于任意* detections 为空或 None 的输入，输出应该包含长度为 0 的数组，且不抛出异常
**验证需求：1.5, 7.4**

### 属性 7：配置验证完整性
*对于任意* 无效配置（None 或空），初始化应该抛出 ValueError 异常
**验证需求：7.1, 7.2**

### 属性 8：事件发布执行
*对于任意* 成功处理的输入，应该发布 PROCESSED_DATA 事件到事件总线
**验证需求：8.2**

### 属性 9：state_label 初始化
*对于任意* 输入，输出的 state_label 字段应该是空列表
**验证需求：5.9**

## 错误处理

### 初始化阶段错误

```python
# 配置验证错误
if config is None:
    raise ValueError("config 不能为 None")

if not device_metadata or len(device_metadata) == 0:
    raise ValueError("device_metadata 不能为 None 或空字典")
```

### 运行时阶段错误

```python
# 输入验证错误
if detection_data is None:
    raise ValueError("detection_data 不能为 None")

# 空输入处理（不抛出异常）
if not detections or len(detections) == 0:
    return self._create_empty_output(detection_data)

# 子模块异常传播
try:
    transformed_coords = self._transformer.get_trans_matrices(device_id, detections)
except Exception as e:
    logger.error(f"坐标变换失败: {e}")
    raise

try:
    filtered_data = self._filter_manager.process(...)
except Exception as e:
    logger.error(f"滤波处理失败: {e}")
    raise

# 事件发布异常处理（不抛出异常，只记录日志）
try:
    self._event_bus.publish(
        EventType.PROCESSED_DATA,
        processed_data,
        wait_all=False,
    )
except Exception as e:
    logger.error(f"事件发布失败: {e}")
    # 不抛出异常，继续返回处理结果
```

## 事件发布设计

### 事件类型

使用 `EventType.PROCESSED_DATA` 事件类型发布处理后的数据。

### 发布时机

在 `process()` 方法完成数据处理和组装后，立即发布事件。

### 发布模式

使用异步模式（`wait_all=False`）发布事件，避免阻塞数据处理流程：
- 不等待订阅者处理完成
- 提高数据处理吞吐量
- 订阅者在后台线程池中并行执行

### 事件数据

事件数据为 `DeviceProcessedDataDTO` 实例，包含：
- device_id: 设备标识
- frame_id: 帧ID
- device_alias: 设备别名
- coords: 处理后的坐标数组
- bbox: 处理后的边界框数组
- confidence: 处理后的置信度数组
- labels: 处理后的标签数组
- state_label: 状态标签列表（初始为空）

### 错误处理

事件发布失败时：
- 记录错误日志
- 不抛出异常（避免影响数据处理流程）
- 继续返回处理结果

### 使用示例

```python
# 在 process 方法中
processed_data = self._assemble_output(...)

# 发布事件
try:
    self._event_bus.publish(
        EventType.PROCESSED_DATA,
        processed_data,
        wait_all=False,  # 异步模式
    )
    logger.debug(f"发布处理数据事件: device_id={processed_data.device_id}, frame_id={processed_data.frame_id}")
except Exception as e:
    logger.error(f"事件发布失败: {e}")

return processed_data
```

## 测试策略

### 单元测试

1. **初始化测试**：
   - 测试有效配置的初始化
   - 测试无效配置抛出异常
   - 测试子模块正确创建

2. **数据提取测试**：
   - 测试从 DetectionDTO 提取数组
   - 测试数组形状和 dtype
   - 测试空输入处理

3. **数据流测试**：
   - 测试完整的处理流程
   - 测试元数据字段传递
   - 测试数据对应关系

4. **错误处理测试**：
   - 测试各种无效输入
   - 测试异常传播

### 集成测试

1. **与 CoordinateTransformer 集成**：
   - 测试坐标变换正确执行
   - 测试变换参数正确传递

2. **与 FilterManager 集成**：
   - 测试滤波处理正确执行
   - 测试滤波参数正确传递

3. **端到端测试**：
   - 测试完整的数据流
   - 测试多帧处理
   - 测试性能指标

### 属性测试

使用 Property-Based Testing 验证通用属性：

1. **属性 1-8 的测试**：
   - 生成随机的 DeviceDetectionDataDTO
   - 验证所有属性在所有输入下都成立

2. **边界情况测试**：
   - 空数组输入
   - 单元素输入
   - 大量元素输入

## 性能优化

### 初始化优化

1. **预创建子模块实例**：
   ```python
   # 在 __init__ 中创建，避免运行时开销
   self._transformer = CoordinateTransformer(...)
   self._filter_manager = FilterManager(...)
   ```

### 运行时优化

1. **NumPy 向量化操作**：
   ```python
   # 预分配数组
   n = len(detections)
   coords = np.zeros((n, 3), dtype=np.float32)
   bboxes = np.zeros((n, 4), dtype=np.float32)
   
   # 向量化填充
   for i, det in enumerate(detections):
       coords[i] = [det.spatial_coordinates.x, 
                   det.spatial_coordinates.y, 
                   det.spatial_coordinates.z]
       bboxes[i] = [det.bbox.xmin, det.bbox.ymin, 
                   det.bbox.xmax, det.bbox.ymax]
   ```

2. **避免数据复制**：
   ```python
   # 直接使用返回的数组，不复制
   filtered_coords = filter_manager.process(...)
   # 而不是
   filtered_coords = filter_manager.process(...).copy()
   ```

3. **最小化对象创建**：
   ```python
   # 复用 DTO 对象的字段
   return DeviceProcessedDataDTO(
       device_id=detection_data.device_id,  # 直接引用
       frame_id=detection_data.frame_id,
       ...
   )
   ```

## 实现注意事项

1. **依赖现有实现**：
   - 直接使用 CoordinateTransformer.get_trans_matrices() 方法
   - 直接使用 FilterManager.process() 方法
   - 不重新实现坐标变换或滤波逻辑

2. **数据格式转换**：
   - 确保 NumPy 数组使用正确的 dtype
   - 保持数组元素的对应关系
   - 处理空输入的边界情况

3. **错误处理**：
   - 在初始化阶段验证配置
   - 在运行时传播子模块异常
   - 记录详细的错误日志

4. **性能考虑**：
   - 预分配数组
   - 使用向量化操作
   - 避免不必要的复制

## 接口使用示例

```python
from oak_vision_system.core.event_bus import get_event_bus, EventType

# 初始化
config = DataProcessingConfigDTO(
    coordinate_transform_configs={...},
    filter_config=FilterConfigDTO(...),
    label_map=["durian", "person"],
)

device_metadata = {
    "device_001": DeviceMetadataDTO(mxid="device_001", ...),
    "device_002": DeviceMetadataDTO(mxid="device_002", ...),
}

processor = DataProcessor(
    config=config,
    device_metadata=device_metadata,
)

# 订阅处理后的数据（下游模块）
event_bus = get_event_bus()

def on_processed_data(data: DeviceProcessedDataDTO):
    print(f"接收到处理数据: device_id={data.device_id}, frame_id={data.frame_id}")
    print(f"检测数量: {len(data.coords)}")

event_bus.subscribe(
    EventType.PROCESSED_DATA,
    on_processed_data,
)

# 处理数据
detection_data = DeviceDetectionDataDTO(
    device_id="device_001",
    frame_id=100,
    device_alias="front_camera",
    detections=[
        DetectionDTO(label=0, confidence=0.9, bbox=..., spatial_coordinates=...),
        DetectionDTO(label=1, confidence=0.8, bbox=..., spatial_coordinates=...),
    ]
)

# process 方法会：
# 1. 处理数据
# 2. 发布 PROCESSED_DATA 事件
# 3. 返回处理结果
processed_data = processor.process(detection_data)

# 输出
# processed_data.device_id == "device_001"
# processed_data.frame_id == 100
# processed_data.coords.shape == (m, 3)  # m 为滤波后的数量
# processed_data.bbox.shape == (m, 4)
# processed_data.confidence.shape == (m,)
# processed_data.labels.shape == (m,)
# processed_data.state_label == []

# 订阅者会在后台线程中接收到事件
```
