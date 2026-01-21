# FilterManager 模块职责文档

## 模块概述

FilterManager（滤波器管理器）是数据处理流水线中的核心协调组件，负责管理多个 FilterPool 实例，并根据设备ID和标签对检测数据进行智能分发和处理。

## 核心职责

### 1. FilterPool 实例管理

- **多池管理**：维护一个字典结构 `{(device_id, label): FilterPool}`，为每个设备-标签组合创建独立的滤波器池
- **懒加载创建**：首次遇到新的 (device_id, label) 组合时自动创建对应的 FilterPool 实例
- **生命周期管理**：提供重置、清理特定池或全部池的能力
- **配置统一**：所有 FilterPool 使用统一的配置参数（pool_size、filter_factory、tracker、iou_threshold）

### 2. 数据分发与路由

#### 输入数据结构
接收来自坐标变换模块的处理后数据：
- `device_id: str` - 设备唯一标识符（MXid）
- `coordinates: np.ndarray` - 坐标矩阵，形状 (n, 3)，已完成坐标变换
- `bboxes: np.ndarray` - 边界框矩阵，形状 (n, 4)，格式 [xmin, ymin, xmax, ymax]
- `confidences: list[float]` - 置信度列表，长度 n
- `labels: list[int]` - 标签列表，长度 n

#### 数据拆分逻辑
1. **按标签分组**：根据 `labels` 列表将数据拆分为不同的子集
2. **索引提取**：为每个唯一标签提取对应的索引数组
3. **数据切片**：使用索引从 coordinates、bboxes、confidences 中提取对应子集
4. **路由分发**：将每个子集传递给对应的 `(device_id, label)` FilterPool

### 3. 结果聚合与输出

#### 输出数据结构
返回处理后的完整数据，保持原始顺序：
- `filtered_coordinates: np.ndarray` - 滤波后的坐标矩阵，形状 (n, 3)
- 输出顺序与输入顺序严格一致，便于上游模块重新组装

#### 聚合策略
1. **预分配输出数组**：创建与输入相同形状的输出数组 `np.zeros((n, 3))`
2. **按标签处理**：遍历每个标签组，调用对应 FilterPool 的 `step_v2()` 方法
3. **结果回填**：将 FilterPool 返回的结果按原始索引回填到输出数组
4. **顺序保证**：确保输出数组中每个位置对应输入的同一检测结果

## 接口设计

### 主要方法

#### `__init__()`
```python
def __init__(
    self,
    *,
    pool_size: int = 32,
    filter_factory: Optional[Callable[[], BaseSpatialFilter]] = None,
    tracker: Optional[BaseTracker] = None,
    iou_threshold: float = 0.5,
) -> None:
    """
    初始化滤波器管理器
    
    Args:
        pool_size: 每个 FilterPool 的槽位数量
        filter_factory: 滤波器工厂函数，用于创建滤波器实例
        tracker: 匹配算法实例（如 HungarianTracker）
        iou_threshold: IoU 匹配阈值
    """
```

#### `process()`
```python
def process(
    self,
    device_id: str,
    coordinates: np.ndarray,
    bboxes: np.ndarray,
    confidences: list[float],
    labels: list[int],
) -> np.ndarray:
    """
    处理单个设备的检测数据
    
    Args:
        device_id: 设备ID
        coordinates: 坐标矩阵 (n, 3)
        bboxes: 边界框矩阵 (n, 4)
        confidences: 置信度列表，长度 n
        labels: 标签列表，长度 n
    
    Returns:
        np.ndarray: 滤波后的坐标矩阵 (n, 3)，顺序与输入一致
    
    Raises:
        ValueError: 当输入数据长度不一致时
    """
```

#### `reset_device()`
```python
def reset_device(self, device_id: str) -> None:
    """
    重置指定设备的所有滤波器池
    
    Args:
        device_id: 设备ID
    """
```

#### `reset_all()`
```python
def reset_all(self) -> None:
    """重置所有设备的所有滤波器池"""
```

#### `get_pool_stats()`
```python
def get_pool_stats(self) -> dict[tuple[str, int], dict[str, int]]:
    """
    获取所有滤波器池的统计信息
    
    Returns:
        dict: {(device_id, label): {"capacity": int, "active_count": int}}
    """
```

## 内部实现细节

### 数据结构

```python
class FilterManager:
    def __init__(self, ...):
        # 滤波器池字典：{(device_id, label): FilterPool}
        self._pools: dict[tuple[str, int], FilterPool] = {}
        
        # 配置参数（用于创建新池）
        self._pool_size: int = pool_size
        self._filter_factory: Callable = filter_factory or (lambda: MovingAverageFilter())
        self._tracker: BaseTracker = tracker or HungarianTracker(iou_threshold=iou_threshold)
        self._iou_threshold: float = iou_threshold
```

### 核心处理流程

```python
def process(self, device_id, coordinates, bboxes, confidences, labels):
    # 1. 参数验证
    n = len(coordinates)
    assert len(bboxes) == n and len(confidences) == n and len(labels) == n
    
    # 2. 预分配输出数组
    outputs = np.zeros((n, 3), dtype=np.float32)
    
    # 3. 按标签分组
    unique_labels = np.unique(labels)
    
    for label in unique_labels:
        # 4. 提取该标签的索引
        indices = np.where(labels == label)[0]
        
        # 5. 切片数据
        label_coords = coordinates[indices]
        label_bboxes = bboxes[indices]
        label_confs = [confidences[i] for i in indices]
        
        # 6. 获取或创建对应的 FilterPool
        pool_key = (device_id, int(label))
        if pool_key not in self._pools:
            self._pools[pool_key] = self._create_pool()
        
        # 7. 调用 FilterPool 处理
        filtered = self._pools[pool_key].step_v2(
            label_coords, label_bboxes, label_confs
        )
        
        # 8. 回填结果到输出数组
        outputs[indices] = filtered
    
    return outputs
```

### 辅助方法

```python
def _create_pool(self) -> FilterPool:
    """创建新的 FilterPool 实例"""
    return FilterPool(
        pool_size=self._pool_size,
        filter_factory=self._filter_factory,
        tracker=self._tracker,
        iou_threshold=self._iou_threshold,
    )

def _get_or_create_pool(self, device_id: str, label: int) -> FilterPool:
    """获取或创建指定的 FilterPool"""
    key = (device_id, label)
    if key not in self._pools:
        self._pools[key] = self._create_pool()
    return self._pools[key]
```

## 关键设计特点

### 1. 隔离性
- 不同设备的数据完全隔离（不同 device_id）
- 同一设备的不同标签数据隔离（不同 label）
- 每个 (device_id, label) 组合拥有独立的 FilterPool 和跟踪状态

### 2. 可扩展性
- 支持任意数量的设备
- 支持任意数量的标签类别
- 动态创建 FilterPool，无需预先配置

### 3. 性能优化
- 使用 NumPy 向量化操作进行数据切片
- 预分配输出数组，避免动态扩展
- 懒加载创建 FilterPool，节省内存

### 4. 顺序保证
- 输出数组的索引与输入严格对应
- 便于上游模块按原始顺序重新组装 DetectionDTO

## 使用示例

```python
# 初始化管理器
manager = FilterManager(
    pool_size=32,
    filter_factory=lambda: MovingAverageFilter(queue_maxsize=8),
    iou_threshold=0.5
)

# 处理检测数据
device_id = "18443010D116441200"
coordinates = np.array([[100, 200, 300], [150, 250, 350]], dtype=np.float32)
bboxes = np.array([[10, 20, 50, 60], [15, 25, 55, 65]], dtype=np.float32)
confidences = [0.9, 0.85]
labels = [1, 1]  # 两个检测结果都是标签1

# 获取滤波后的坐标
filtered_coords = manager.process(device_id, coordinates, bboxes, confidences, labels)

# 查看统计信息
stats = manager.get_pool_stats()
print(stats)  # {('18443010D116441200', 1): {'capacity': 32, 'active_count': 2}}

# 重置特定设备
manager.reset_device(device_id)
```

## 与其他模块的交互

### 上游模块：坐标变换模块
- **输入**：接收坐标变换后的数据（世界坐标系）
- **数据格式**：coordinates (n,3), bboxes (n,4), confidences, labels

### 下游模块：顶层数据处理模块
- **输出**：返回滤波后的坐标矩阵
- **顺序保证**：输出顺序与输入一致，便于重新组装 DeviceDetectionDataDTO

### 依赖模块
- **FilterPool**：实际执行滤波和跟踪的工作单元
- **BaseSpatialFilter**：滤波器基类（如 MovingAverageFilter）
- **BaseTracker**：匹配算法（如 HungarianTracker）

## 错误处理

### 输入验证
- 检查 coordinates、bboxes、confidences、labels 长度一致性
- 验证 device_id 非空
- 验证数组形状正确（coordinates: (n,3), bboxes: (n,4)）

### 异常情况
- 空输入（n=0）：直接返回空数组
- 无效标签：跳过该标签的处理
- FilterPool 异常：捕获并记录，返回原始坐标

## 测试要点

### 单元测试
1. 单设备单标签处理
2. 单设备多标签处理
3. 多设备多标签处理
4. 空输入处理
5. 数据顺序保证
6. FilterPool 懒加载创建
7. 重置功能

### 集成测试
1. 与 FilterPool 的集成
2. 与坐标变换模块的集成
3. 完整数据流测试

### 性能测试
1. 大量检测结果处理（n > 100）
2. 多标签场景性能
3. 内存占用测试

## 未来扩展

### 可能的优化方向
1. **并行处理**：不同标签的 FilterPool 可以并行处理
2. **池复用策略**：长时间未使用的池可以被清理
3. **统计监控**：添加处理时间、丢帧率等监控指标
4. **配置热更新**：支持运行时修改 FilterPool 配置

### 可能的功能扩展
1. **多设备协同**：支持跨设备的目标关联
2. **自适应参数**：根据场景自动调整 IoU 阈值
3. **历史轨迹导出**：支持导出目标运动轨迹用于分析
