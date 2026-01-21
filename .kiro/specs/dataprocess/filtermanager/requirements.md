# 需求文档

## 简介

FilterManager（滤波器管理器）是数据处理流水线中的核心协调组件，负责管理多个 FilterPool 实例，并根据设备ID和标签对检测数据进行智能分发和处理。

该模块基于现有的滤波器架构构建：
- **BaseSpatialFilter**：空间滤波器基类，定义了滤波器的基本接口（input、miss、reset 等）
- **MovingAverageFilter**：移动平均滤波器实现，使用滑动窗口平滑坐标数据
- **FilterPool**：滤波器池实现，管理多个滤波器实例，使用 Tracker 进行目标匹配和跟踪
- **BaseTracker**：跟踪器基类，提供目标匹配算法（如 HungarianTracker 基于 IoU 的匈牙利算法）

FilterManager 在此基础上提供更高层次的协调能力：在初始化时接受设备元数据字典（device_metadata）和标签映射列表（label_map），根据这些配置信息预先创建所有必要的 FilterPool 实例。运行时，它接收坐标变换后的检测数据，按设备和标签分组后分发到对应的滤波器池进行处理，最后将各滤波器池的结果按块状方式拼接输出。

## 术语表

- **FilterManager**: 滤波器管理器，管理多个 FilterPool 实例的协调组件
- **FilterPool**: 滤波器池，包含多个滤波器实例，负责单个设备-标签组合的目标跟踪和滤波（现有实现）
- **BaseSpatialFilter**: 空间滤波器基类，定义滤波器的基本接口（input、miss、reset 等方法）
- **MovingAverageFilter**: 移动平均滤波器，BaseSpatialFilter 的具体实现，使用滑动窗口平滑坐标数据
- **BaseTracker**: 跟踪器基类，定义目标匹配算法的基本接口
- **HungarianTracker**: 匈牙利算法跟踪器，BaseTracker 的具体实现，基于 IoU 进行目标匹配
- **device_id**: 设备唯一标识符（MXid），用于区分不同的 OAK 设备
- **label**: 检测标签，表示检测目标的类别（如：0=背景，1=物体A，2=物体B）
- **label_map**: 标签映射列表，定义检测模型支持的所有类别名称
- **coordinates**: 坐标矩阵，形状为 (n, 3) 的 NumPy 数组，表示 n 个检测结果的三维坐标
- **bboxes**: 边界框矩阵，形状为 (n, 4) 的 NumPy 数组，格式为 [xmin, ymin, xmax, ymax]
- **confidences**: 置信度列表，长度为 n 的浮点数列表，表示每个检测结果的置信度
- **IoU**: Intersection over Union，交并比，用于衡量两个边界框的重叠程度
- **DeviceMetadataDTO**: 设备元数据配置，记录每个物理设备的详细信息（包含 mxid）
- **device_metadata**: 设备元数据字典，映射 MXid 到 DeviceMetadataDTO

## 需求

### 需求 1: FilterPool 实例管理

**用户故事**: 作为数据处理系统，我希望能够为每个设备-标签组合维护独立的滤波器池，以便实现隔离的目标跟踪和滤波。

#### 验收标准

1. WHEN 系统初始化时，THE FilterManager SHALL 创建一个空的滤波器池字典
2. WHEN 系统初始化时，THE FilterManager SHALL 接受 device_metadata 字典（Dict[str, DeviceMetadataDTO]）以获取所有设备的 MXid
3. WHEN 系统初始化时，THE FilterManager SHALL 接受 label_map 列表（List[str]）以获取所有检测标签
4. FOR ALL device_metadata 中的 MXid 和 FOR ALL label_map 中的标签，THE FilterManager SHALL 预先创建对应的 (device_id, label) FilterPool 实例
5. WHEN 创建 FilterPool 实例时，THE FilterManager SHALL 使用统一的配置参数（pool_size、filter_factory、tracker、iou_threshold）
6. THE FilterManager SHALL 维护一个字典结构 {(device_id, label): FilterPool} 来存储所有滤波器池实例

### 需求 2: 数据分发与路由

**用户故事**: 作为数据处理系统，我希望能够根据设备ID和标签将检测数据智能分发到对应的滤波器池，以便实现精确的目标跟踪。

#### 验收标准

1. WHEN 接收到检测数据时，THE FilterManager SHALL 验证 coordinates、bboxes、confidences、labels 的长度一致性
2. WHEN 数据长度不一致时，THE FilterManager SHALL 抛出 ValueError 异常
3. WHEN 处理检测数据时，THE FilterManager SHALL 根据 labels 列表提取所有唯一标签
4. FOR ALL 唯一标签，THE FilterManager SHALL 提取该标签对应的索引数组
5. FOR ALL 唯一标签，THE FilterManager SHALL 使用索引从 coordinates、bboxes、confidences 中切片出对应的子集
6. FOR ALL 唯一标签，THE FilterManager SHALL 将子集数据传递给对应的 (device_id, label) FilterPool 进行处理
7. WHEN 输入数据为空（n=0）时，THE FilterManager SHALL 返回空的输出数组

### 需求 3: 结果聚合与输出

**用户故事**: 作为数据处理系统，我希望能够将各个滤波器池的处理结果按块状方式聚合输出，以便简化数据组装流程并提高处理效率。

#### 验收标准

1. FOR ALL 滤波器池，THE FilterManager SHALL 调用对应 FilterPool 的 step_v2() 方法获取滤波结果
2. FOR ALL 滤波器池，THE FilterManager SHALL 收集其返回的坐标数组（形状为 (m, 3)，m 为该池的检测数量）
3. FOR ALL 滤波器池，THE FilterManager SHALL 生成与其输出数量一致的 label 数组
4. FOR ALL 滤波器池，THE FilterManager SHALL 收集对应的 bbox 矩阵和 confidence 列表
5. THE FilterManager SHALL 按滤波器池顺序将所有坐标数组块状拼接为最终输出（形状为 (n, 3)）
6. THE FilterManager SHALL 按相同顺序拼接 labels、bboxes、confidences，确保各字段对应关系一致
7. THE FilterManager SHALL 返回四个输出：coordinates (n, 3)、labels (n,)、bboxes (n, 4)、confidences (n,)

### 需求 4: 配置管理

**用户故事**: 作为系统配置人员，我希望能够通过简洁的配置参数统一管理 FilterManager 和所有 FilterPool，以便简化系统配置和维护。

#### 验收标准

1. WHEN 初始化 FilterManager 时，THE FilterManager SHALL 接受 device_metadata 字典（Dict[str, DeviceMetadataDTO]）作为必需参数
2. WHEN 初始化 FilterManager 时，THE FilterManager SHALL 接受 label_map 列表（List[str]）作为必需参数
3. WHEN 初始化 FilterManager 时，THE FilterManager SHALL 从 device_metadata 的键中提取所有设备 MXid
4. WHEN 初始化 FilterManager 时，THE FilterManager SHALL 接受 pool_size 参数（默认值为 32）
5. WHEN 初始化 FilterManager 时，THE FilterManager SHALL 接受 filter_factory 参数（默认为 MovingAverageFilter 工厂函数）
6. WHEN 初始化 FilterManager 时，THE FilterManager SHALL 接受 tracker 参数（默认为 HungarianTracker 实例）
7. WHEN 初始化 FilterManager 时，THE FilterManager SHALL 接受 iou_threshold 参数（默认值为 0.5）
8. WHEN 创建新的 FilterPool 时，THE FilterManager SHALL 使用存储的配置参数

### 需求 5: 统计信息查询

**用户故事**: 作为系统监控人员，我希望能够查询各个滤波器池的统计信息，以便了解系统运行状态。

#### 验收标准

1. THE FilterManager SHALL 提供 get_pool_stats() 方法返回所有滤波器池的统计信息
2. WHEN 调用 get_pool_stats() 时，THE FilterManager SHALL 返回字典格式 {(device_id, label): {"capacity": int, "active_count": int}}
3. FOR ALL 滤波器池，THE FilterManager SHALL 包含其容量（capacity）和活跃滤波器数量（active_count）信息

### 需求 6: 错误处理

**用户故事**: 作为数据处理系统，我希望能够在初始化阶段验证配置正确性，并在运行时保持零验证开销以实现极致性能。

#### 验收标准

1. WHEN 初始化时 device_metadata 为 None 或空字典时，THE FilterManager SHALL 抛出 ValueError 异常并包含详细错误信息
2. WHEN 初始化时 label_map 为 None 或空列表时，THE FilterManager SHALL 抛出 ValueError 异常并包含详细错误信息
3. WHEN 初始化时 device_metadata 中的任何 MXid 为空字符串时，THE FilterManager SHALL 抛出 ValueError 异常
4. WHEN 初始化时 pool_size 小于等于 0 时，THE FilterManager SHALL 抛出 ValueError 异常
5. WHEN 运行时处理数据时，THE FilterManager SHALL NOT 执行任何输入验证以保证性能
6. THE FilterManager SHALL 假设调用方保证输入数据的正确性（coordinates、bboxes、confidences、labels 长度一致且形状正确）

### 需求 7: 性能优化

**用户故事**: 作为数据处理系统，我希望能够高效处理大量检测数据，以便满足实时性要求。

#### 验收标准

1. WHEN 初始化时，THE FilterManager SHALL 预先创建所有必要的 FilterPool 实例，避免运行时动态创建开销
2. WHEN 处理数据时，THE FilterManager SHALL 使用 NumPy 向量化操作进行数据切片
3. WHEN 处理数据时，THE FilterManager SHALL 预分配输出数组，避免动态扩展
4. THE FilterManager SHALL 避免不必要的数据复制操作
