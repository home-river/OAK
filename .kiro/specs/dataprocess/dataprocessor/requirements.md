# 需求文档

## 简介

DataProcessor（数据处理器）是数据处理流水线的顶层协调组件，负责协调坐标变换和滤波处理流程，并完成数据格式的转换和组装。

该模块基于现有的子模块构建：
- **TransformModule**：坐标变换模块，负责将设备坐标系转换到世界坐标系
- **FilterManager**：滤波管理器，负责管理多个 FilterPool 实例并进行滤波处理

DataProcessor 在此基础上提供更高层次的协调能力：接收上游的检测数据（DeviceDetectionDataDTO），依次调用坐标变换和滤波处理，最后将结果组装为输出格式（DeviceProcessedDataDTO）。整个过程确保数据流的正确性和高效性。

## 术语表

- **DataProcessor**: 数据处理器，顶层协调组件，负责协调坐标变换和滤波流程
- **TransformModule**: 坐标变换模块，负责坐标系转换（现有实现）
- **FilterManager**: 滤波管理器，负责管理多个 FilterPool 并进行滤波处理（现有实现）
- **DeviceDetectionDataDTO**: 设备检测数据传输对象，包含原始检测结果
- **DeviceProcessedDataDTO**: 设备处理后数据传输对象，包含处理后的结果
- **DetectionDTO**: 单个检测结果对象，包含坐标、边界框、置信度、标签等信息
- **device_id**: 设备唯一标识符（MXid），用于区分不同的 OAK 设备
- **frame_id**: 帧ID，用于与视频帧同步
- **coordinates**: 坐标矩阵，形状为 (n, 3) 的 NumPy 数组，表示 n 个检测结果的三维坐标
- **bboxes**: 边界框矩阵，形状为 (n, 4) 的 NumPy 数组，格式为 [xmin, ymin, xmax, ymax]
- **confidences**: 置信度数组，形状为 (n,) 的 NumPy 数组，表示每个检测结果的置信度
- **labels**: 标签数组，形状为 (n,) 的 NumPy 数组，表示每个检测结果的类别
- **DataProcessingConfigDTO**: 数据处理配置对象，包含坐标变换和滤波的配置参数
- **DeviceMetadataDTO**: 设备元数据配置，记录每个物理设备的详细信息

## 需求

### 需求 1: 数据接收与提取

**用户故事**: 作为数据处理系统，我希望能够接收上游的检测数据并提取必要的信息，以便进行后续处理。

#### 验收标准

1. WHEN 接收到 DeviceDetectionDataDTO 时，THE DataProcessor SHALL 提取 device_id 字段
2. WHEN 接收到 DeviceDetectionDataDTO 时，THE DataProcessor SHALL 提取 frame_id 字段
3. WHEN 接收到 DeviceDetectionDataDTO 时，THE DataProcessor SHALL 提取 device_alias 字段
4. WHEN 接收到 DeviceDetectionDataDTO 时，THE DataProcessor SHALL 提取 detections 列表
5. WHEN detections 列表为空或 None 时，THE DataProcessor SHALL 返回空的 DeviceProcessedDataDTO
6. FOR ALL detections 列表中的元素，THE DataProcessor SHALL 提取坐标、边界框、置信度和标签信息

### 需求 2: 数据格式转换

**用户故事**: 作为数据处理系统，我希望能够将 DTO 格式转换为 NumPy 数组格式，以便进行高效的数值计算。

#### 验收标准

1. WHEN 提取检测数据时，THE DataProcessor SHALL 将坐标转换为形状 (n, 3) 的 float32 NumPy 数组
2. WHEN 提取检测数据时，THE DataProcessor SHALL 将边界框转换为形状 (n, 4) 的 float32 NumPy 数组
3. WHEN 提取检测数据时，THE DataProcessor SHALL 将置信度转换为形状 (n,) 的 float32 NumPy 数组
4. WHEN 提取检测数据时，THE DataProcessor SHALL 将标签转换为形状 (n,) 的 int32 NumPy 数组
5. WHEN 转换数据时，THE DataProcessor SHALL 保持数组元素的对应关系（相同索引表示同一检测结果）
6. WHEN 转换数据时，THE DataProcessor SHALL 使用向量化操作以提高性能

### 需求 3: 坐标变换集成

**用户故事**: 作为数据处理系统，我希望能够调用坐标变换模块将设备坐标转换为世界坐标，以便统一坐标系。

#### 验收标准

1. WHEN 初始化时，THE DataProcessor SHALL 创建 TransformModule 实例
2. WHEN 处理检测数据时，THE DataProcessor SHALL 调用 TransformModule 的 transform 方法
3. WHEN 调用坐标变换时，THE DataProcessor SHALL 传递 device_id 参数
4. WHEN 调用坐标变换时，THE DataProcessor SHALL 传递坐标矩阵参数
5. WHEN 坐标变换完成时，THE DataProcessor SHALL 接收变换后的坐标矩阵
6. THE DataProcessor SHALL 确保坐标变换在滤波处理之前执行

### 需求 4: 滤波处理集成

**用户故事**: 作为数据处理系统，我希望能够调用滤波管理器对数据进行滤波处理，以便平滑检测结果并跟踪目标。

#### 验收标准

1. WHEN 初始化时，THE DataProcessor SHALL 创建 FilterManager 实例
2. WHEN 处理检测数据时，THE DataProcessor SHALL 调用 FilterManager 的 process 方法
3. WHEN 调用滤波处理时，THE DataProcessor SHALL 传递 device_id 参数
4. WHEN 调用滤波处理时，THE DataProcessor SHALL 传递变换后的坐标矩阵
5. WHEN 调用滤波处理时，THE DataProcessor SHALL 传递边界框矩阵、置信度数组和标签数组
6. WHEN 滤波处理完成时，THE DataProcessor SHALL 接收滤波后的坐标、边界框、置信度和标签
7. THE DataProcessor SHALL 确保滤波处理在坐标变换之后执行

### 需求 5: 输出数据组装

**用户故事**: 作为数据处理系统，我希望能够将处理后的数据组装为输出格式，以便传递给下游模块。

#### 验收标准

1. WHEN 滤波处理完成时，THE DataProcessor SHALL 创建 DeviceProcessedDataDTO 实例
2. WHEN 组装输出时，THE DataProcessor SHALL 设置 device_id 字段为输入的 device_id
3. WHEN 组装输出时，THE DataProcessor SHALL 设置 frame_id 字段为输入的 frame_id
4. WHEN 组装输出时，THE DataProcessor SHALL 设置 device_alias 字段为输入的 device_alias
5. WHEN 组装输出时，THE DataProcessor SHALL 设置 coords 字段为滤波后的坐标矩阵
6. WHEN 组装输出时，THE DataProcessor SHALL 设置 bbox 字段为滤波后的边界框矩阵
7. WHEN 组装输出时，THE DataProcessor SHALL 设置 confidence 字段为滤波后的置信度数组
8. WHEN 组装输出时，THE DataProcessor SHALL 设置 labels 字段为滤波后的标签数组
9. WHEN 组装输出时，THE DataProcessor SHALL 初始化 state_label 字段为空列表

### 需求 6: 配置管理

**用户故事**: 作为系统配置人员，我希望能够通过配置对象初始化数据处理器，以便灵活配置处理流程。

#### 验收标准

1. WHEN 初始化 DataProcessor 时，THE DataProcessor SHALL 接受 DataProcessingConfigDTO 作为必需参数
2. WHEN 初始化 DataProcessor 时，THE DataProcessor SHALL 接受 device_metadata 字典作为必需参数
3. WHEN 初始化 DataProcessor 时，THE DataProcessor SHALL 从配置中提取坐标变换配置
4. WHEN 初始化 DataProcessor 时，THE DataProcessor SHALL 从配置中提取滤波配置
5. WHEN 初始化 DataProcessor 时，THE DataProcessor SHALL 从配置中提取 label_map
6. WHEN 初始化 DataProcessor 时，THE DataProcessor SHALL 使用配置参数初始化 TransformModule
7. WHEN 初始化 DataProcessor 时，THE DataProcessor SHALL 使用配置参数初始化 FilterManager

### 需求 7: 错误处理

**用户故事**: 作为数据处理系统，我希望能够妥善处理各种异常情况，以便保证系统的稳定性和可靠性。

#### 验收标准

1. WHEN 初始化时 config 为 None 时，THE DataProcessor SHALL 抛出 ValueError 异常
2. WHEN 初始化时 device_metadata 为 None 或空字典时，THE DataProcessor SHALL 抛出 ValueError 异常
3. WHEN 接收到的 DeviceDetectionDataDTO 为 None 时，THE DataProcessor SHALL 抛出 ValueError 异常
4. WHEN detections 列表为空时，THE DataProcessor SHALL 返回空的 DeviceProcessedDataDTO 而不抛出异常
5. WHEN 坐标变换失败时，THE DataProcessor SHALL 记录错误日志并抛出异常
6. WHEN 滤波处理失败时，THE DataProcessor SHALL 记录错误日志并抛出异常

### 需求 8: 事件发布

**用户故事**: 作为数据处理系统，我希望能够将处理后的数据通过事件总线发布，以便下游模块（如显示模块）能够接收和处理数据。

#### 验收标准

1. WHEN 初始化时，THE DataProcessor SHALL 获取全局 EventBus 实例
2. WHEN 处理完成时，THE DataProcessor SHALL 发布 PROCESSED_DATA 事件
3. WHEN 发布事件时，THE DataProcessor SHALL 使用 DeviceProcessedDataDTO 作为事件数据
4. WHEN 发布事件时，THE DataProcessor SHALL 使用异步模式（wait_all=False）以避免阻塞
5. WHEN 发布失败时，THE DataProcessor SHALL 记录错误日志但不抛出异常
6. THE DataProcessor SHALL 在 process 方法中完成数据处理和事件发布

### 需求 9: 性能优化

**用户故事**: 作为数据处理系统，我希望能够高效处理检测数据，以便满足实时性要求。

#### 验收标准

1. WHEN 初始化时，THE DataProcessor SHALL 预先创建 TransformModule 和 FilterManager 实例
2. WHEN 转换数据格式时，THE DataProcessor SHALL 使用 NumPy 向量化操作
3. WHEN 提取数组时，THE DataProcessor SHALL 预分配输出数组以避免动态扩展
4. WHEN 处理数据时，THE DataProcessor SHALL 避免不必要的数据复制
5. THE DataProcessor SHALL 确保单帧处理时间满足实时性要求（20-30 FPS）
