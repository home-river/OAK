# FilterManager 设计文档

## 概述

FilterManager 是数据处理流水线中的核心协调组件，负责管理多个 FilterPool 实例，并根据设备 ID 和标签对检测数据进行智能分发和处理。该模块基于现有的滤波器架构（BaseSpatialFilter、FilterPool、BaseTracker）构建，提供更高层次的多设备、多标签协调能力。

### 设计目标

1. **高性能**：零运行时验证开销，使用 NumPy 向量化操作
2. **可扩展**：支持多设备、多标签的灵活组合
3. **简洁接口**：最小化依赖，只接受必要的配置参数
4. **自动管理**：依赖 FilterPool 的自管理机制，无需手动重置

## 架构设计

### 系统层次

```
FilterManager (协调层)
    ├─ 管理多个 FilterPool 实例
    ├─ 按设备和标签分发数据
    └─ 块状拼接输出结果
    
FilterPool (池管理层 - 现有实现)
    ├─ 管理多个 Filter 实例
    ├─ 使用 Tracker 进行目标匹配
    └─ 处理单个设备-标签组合
    
BaseSpatialFilter (滤波层 - 现有实现)
    └─ MovingAverageFilter
        └─ 滑动窗口平滑坐标
```

### 核心职责

1. **初始化阶段**：
   - 接受 `device_metadata` 和 `label_map` 配置
   - 预先创建所有 (device_id, label) 组合的 FilterPool 实例
   - 验证配置参数的有效性

2. **运行时阶段**：
   - 接收检测数据（coordinates, bboxes, confidences, labels, device_id）
   - 按标签分组数据
   - 分发到对应的 FilterPool 进行处理
   - 块状拼接所有 FilterPool 的输出

3. **监控阶段**：
   - 提供统计信息查询接口
   - 返回各 FilterPool 的容量和活跃数量

## 组件和接口

### 类定义

```python
class FilterManager:
    """滤波器管理器
    
    管理多个 FilterPool 实例，按设备和标签分发检测数据。
    """
    
    def __init__(
        self,
        *,
        device_metadata: Dict[str, DeviceMetadataDTO],
        label_map: List[str],
        pool_size: int = 32,
        filter_factory: Optional[Callable[[], BaseSpatialFilter]] = None,
        tracker: Optional[BaseTracker] = None,
        iou_threshold: float = 0.5,
    ) -> None:
        """初始化 FilterManager
        
        Args:
            device_metadata: 设备元数据字典，映射 MXid 到 DeviceMetadataDTO
            label_map: 标签映射列表，定义所有检测类别
            pool_size: 每个 FilterPool 的大小（默认 32）
            filter_factory: 滤波器工厂函数（默认 MovingAverageFilter）
            tracker: 跟踪器实例（默认 HungarianTracker）
            iou_threshold: IoU 匹配阈值（默认 0.5）
        
        Raises:
            ValueError: 当配置参数无效时
        """
    
    def process(
        self,
        device_id: str,
        coordinates: np.ndarray,
        bboxes: np.ndarray,
        confidences: np.ndarray,
        labels: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """处理一帧检测数据
        
        Args:
            device_id: 设备 MXid
            coordinates: 坐标矩阵，形状 (n, 3)，dtype=float32
            bboxes: 边界框矩阵，形状 (n, 4)，dtype=float32
            confidences: 置信度数组，形状 (n,)，dtype=float32
            labels: 标签数组，形状 (n,)，dtype=int32
        
        Returns:
            Tuple[coordinates, bboxes, confidences, labels]:
                - coordinates: 滤波后的坐标矩阵，形状 (m, 3)，dtype=float32
                - bboxes: 对应的边界框矩阵，形状 (m, 4)，dtype=float32
                - confidences: 对应的置信度数组，形状 (m,)，dtype=float32
                - labels: 对应的标签数组，形状 (m,)，dtype=int32
        """
    
    def get_pool_stats(self) -> Dict[Tuple[str, int], Dict[str, int]]:
        """获取所有滤波器池的统计信息
        
        Returns:
            字典格式: {(device_id, label): {"capacity": int, "active_count": int}}
        """
```

### 内部数据结构

```python
class FilterManager:
    _pools: Dict[Tuple[str, int], FilterPool]  # {(device_id, label): FilterPool}
    _device_ids: List[str]                      # 所有设备 MXid
    _label_map: List[str]                       # 标签映射列表
    _pool_size: int                             # FilterPool 大小
    _filter_factory: Callable[[], BaseSpatialFilter]  # 滤波器工厂
    _tracker: BaseTracker                       # 跟踪器实例
    _iou_threshold: float                       # IoU 阈值
```

## 数据模型

### 输入数据格式

```python
# 单帧检测数据
device_id: str                    # 设备 MXid，例如 "14442C10D13D0D0F00"
coordinates: np.ndarray           # 形状 (n, 3)，dtype=float32
bboxes: np.ndarray                # 形状 (n, 4)，dtype=float32，格式 [xmin, ymin, xmax, ymax]
confidences: np.ndarray           # 形状 (n,)，dtype=float32
labels: np.ndarray                # 形状 (n,)，dtype=int32
```

### 输出数据格式

```python
# 滤波后的数据（块状拼接）
coordinates: np.ndarray           # 形状 (m, 3)，dtype=float32
bboxes: np.ndarray                # 形状 (m, 4)，dtype=float32
confidences: np.ndarray           # 形状 (m,)，dtype=float32
labels: np.ndarray                # 形状 (m,)，dtype=int32
```

### 数据流示例

```python
# 输入
device_id = "device_001"
coordinates = np.array([[1,2,3], [4,5,6], [7,8,9], [10,11,12]], dtype=np.float32)
labels = np.array([0, 1, 0, 1], dtype=np.int32)
bboxes = np.array([[...], [...], [...], [...]],dtype=np.float32)
confidences = np.array([0.9, 0.8, 0.85, 0.95], dtype=np.float32)

# 分流
# Pool (device_001, label=0): indices=[0,2] -> coords=[[1,2,3], [7,8,9]]
# Pool (device_001, label=1): indices=[1,3] -> coords=[[4,5,6], [10,11,12]]

# 输出（块状拼接）
output_coords = np.array([[1',2',3'], [7',8',9'], [4',5',6'], [10',11',12']], dtype=np.float32)
#                         ↑---- label=0 ----↑  ↑---- label=1 ----↑
output_labels = np.array([0, 0, 1, 1], dtype=np.int32)
output_bboxes = np.array([bbox0, bbox2, bbox1, bbox3], dtype=np.float32)
output_confidences = np.array([0.9, 0.85, 0.8, 0.95], dtype=np.float32)
```

## 正确性属性

*属性是关于系统行为的形式化陈述，应该在所有有效执行中保持为真。这些属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*

### 属性 1：FilterPool 实例完整性
*对于任意* device_metadata 和 label_map，初始化后 FilterManager 应该包含所有 (device_id, label) 组合的 FilterPool 实例
**验证需求：1.4**

### 属性 2：数据分组正确性
*对于任意* 输入数据，按标签分组后，每个组内的所有元素应该具有相同的标签值
**验证需求：2.3, 2.4**

### 属性 3：输出长度一致性
*对于任意* 输入数据，输出的 coordinates、bboxes、confidences、labels 的长度应该相等
**验证需求：3.6**

### 属性 4：块状拼接顺序性
*对于任意* 输入数据，输出中同一标签的所有元素应该是连续的块
**验证需求：3.5**

### 属性 5：配置验证完整性
*对于任意* 无效配置（空 device_metadata 或空 label_map），初始化应该抛出 ValueError 异常
**验证需求：6.1, 6.2**

### 属性 6：零运行时验证
*对于任意* process() 调用，不应该执行任何输入验证逻辑
**验证需求：6.5**

### 属性 7：统计信息准确性
*对于任意* FilterManager 状态，get_pool_stats() 返回的 capacity 应该等于初始化时的 pool_size
**验证需求：5.2, 5.3**

## 错误处理

### 初始化阶段错误

```python
# 配置验证错误
if not device_metadata or len(device_metadata) == 0:
    raise ValueError("device_metadata 不能为 None 或空字典")

if not label_map or len(label_map) == 0:
    raise ValueError("label_map 不能为 None 或空列表")

if any(not mxid for mxid in device_metadata.keys()):
    raise ValueError("device_metadata 中的 MXid 不能为空字符串")

if pool_size <= 0:
    raise ValueError("pool_size 必须大于 0")
```

### 运行时阶段

**不进行任何验证**，假设调用方保证数据正确性：
- coordinates、bboxes、confidences、labels 长度一致
- coordinates 形状为 (n, 3)
- bboxes 形状为 (n, 4)
- device_id 非空且存在于 device_metadata 中

## 测试策略

### 测试文件组织

**所有测试统一放在单个文件中**：
- 文件路径：`oak_vision_system/tests/unit/modules/data_processing/test_filter_manager.py`
- 使用 pytest 的 class 组织不同类型的测试：
  - `TestFilterManagerInit`：初始化测试
  - `TestFilterManagerGrouping`：数据分组测试
  - `TestFilterManagerAggregation`：结果拼接测试
  - `TestFilterManagerStats`：统计信息测试
  - `TestFilterManagerProperties`：属性测试

### 单元测试

1. **初始化测试**：
   - 测试有效配置的初始化
   - 测试无效配置抛出异常
   - 测试 FilterPool 实例创建

2. **数据分组测试**：
   - 测试按标签正确分组
   - 测试空输入处理
   - 测试单标签输入

3. **输出拼接测试**：
   - 测试块状拼接顺序
   - 测试输出长度一致性
   - 测试多标签混合场景

4. **统计信息测试**：
   - 测试 get_pool_stats() 返回格式
   - 测试统计信息准确性

### 属性测试

使用 Property-Based Testing 验证通用属性：

1. **属性 1-7 的测试**：
   - 生成随机的 device_metadata 和 label_map
   - 生成随机的检测数据
   - 验证所有属性在所有输入下都成立

2. **边界情况测试**：
   - 空数组输入
   - 单元素输入
   - 大量元素输入（性能测试）
   - 所有元素同一标签
   - 每个元素不同标签

## 性能优化

### 初始化优化

1. **预分配所有 FilterPool**：
   ```python
   # 一次性创建所有实例，避免运行时开销
   for device_id in device_metadata.keys():
       for label_idx in range(len(label_map)):
           key = (device_id, label_idx)
           self._pools[key] = FilterPool(...)
   ```

### 运行时优化

1. **NumPy 向量化操作**：
   ```python
   # 使用 NumPy 布尔索引进行高效切片
   mask = (labels == target_label)
   sub_coords = coordinates[mask]
   sub_bboxes = bboxes[mask]
   ```

2. **预分配输出数组**：
   ```python
   # 预先计算总输出大小
   total_size = sum(len(pool_output) for pool_output in outputs)
   result_coords = np.empty((total_size, 3), dtype=np.float32)
   ```

3. **避免数据复制**：
   ```python
   # 使用视图而不是复制
   sub_coords = coordinates[mask]  # 返回视图
   # 而不是
   sub_coords = coordinates[mask].copy()  # 创建副本
   ```

4. **零验证开销**：
   ```python
   def process(self, ...):
       # 直接处理，不进行任何验证
       # 假设调用方保证数据正确性
       ...
   ```

### 内存优化

1. **复用 FilterPool 实例**：
   - 预先创建，运行时不再分配
   - 依赖 FilterPool 的自管理机制

2. **使用 dtype=float32**：
   - 减少内存占用（相比 float64）
   - 提高缓存命中率

## 实现注意事项

1. **依赖现有实现**：
   - 直接使用 FilterPool.step_v2() 方法
   - 不重新实现滤波逻辑

2. **配置参数传递**：
   - 将 pool_size、filter_factory、tracker、iou_threshold 传递给每个 FilterPool
   - 所有 FilterPool 使用相同的配置

3. **标签索引映射**：
   - label_map 的索引即为标签值
   - 例如：label_map = ["durian", "person"] → 0=durian, 1=person

4. **块状拼接顺序**：
   - 按 FilterPool 的迭代顺序拼接
   - 建议按 (device_id, label) 的字典序

5. **空输入处理**：
   - 当 n=0 时，返回空数组
   - 不调用任何 FilterPool

## 接口使用示例

```python
# 初始化
device_metadata = {
    "device_001": DeviceMetadataDTO(mxid="device_001", ...),
    "device_002": DeviceMetadataDTO(mxid="device_002", ...),
}
label_map = ["durian", "person"]

manager = FilterManager(
    device_metadata=device_metadata,
    label_map=label_map,
    pool_size=32,
)

# 处理数据
coords, bboxes, confs, labels = manager.process(
    device_id="device_001",
    coordinates=np.array([[1,2,3], [4,5,6]], dtype=np.float32),
    bboxes=np.array([[0,0,10,10], [20,20,30,30]], dtype=np.float32),
    confidences=np.array([0.9, 0.8], dtype=np.float32),
    labels=np.array([0, 1], dtype=np.int32),
)

# 查询统计
stats = manager.get_pool_stats()
# {("device_001", 0): {"capacity": 32, "active_count": 5}, ...}
```
