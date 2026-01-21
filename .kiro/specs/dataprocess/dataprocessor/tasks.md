# DataProcessor 实现任务列表

## 概述

本任务列表将 DataProcessor 的设计转换为可执行的实现步骤。DataProcessor 是数据处理流水线的顶层协调组件，负责协调坐标变换和滤波处理流程，并通过事件总线发布处理后的数据。

## 任务

- [x] 1. 创建 DataProcessor 类骨架和初始化逻辑
  - 创建 `oak_vision_system/modules/data_processing/data_processor.py` 文件
  - 定义 `DataProcessor` 类和 `__init__()` 方法
  - 实现配置参数验证（config、device_metadata）
  - 初始化 CoordinateTransformer 实例
  - 初始化 FilterManager 实例
  - 获取全局 EventBus 实例
  - 存储配置参数供后续使用
  - _需求：6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.2, 8.1_

- [x] 1.1 编写初始化验证的单元测试
  - 在 `oak_vision_system/tests/unit/modules/data_processing/test_data_processor.py` 中创建 `TestDataProcessorInit` 测试类
  - 测试有效配置的初始化
  - 测试无效配置抛出 ValueError（None config、空 device_metadata）
  - 测试子模块实例正确创建（CoordinateTransformer、FilterManager、EventBus）
  - 测试配置参数正确存储
  - _需求：6.1, 6.2, 7.1, 7.2_

- [x] 2. 实现数据提取和格式转换逻辑
  - 实现 `_extract_arrays()` 私有方法
  - 从 List[DetectionDTO] 提取坐标、边界框、置信度、标签
  - 转换为 NumPy 数组格式（float32 和 int32）
  - 使用预分配数组和向量化操作
  - 保持数组元素的对应关系
  - _需求：1.4, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 9.2, 9.3_

- [x] 2.1 编写数据提取的单元测试
  - 在 `test_data_processor.py` 中创建 `TestDataProcessorExtraction` 测试类
  - 测试从 DetectionDTO 列表提取数组
  - 测试数组形状和 dtype 正确
  - 测试数组元素对应关系
  - 测试空输入处理
  - _需求：2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. 实现坐标变换集成
  - 在 `process()` 方法中调用 CoordinateTransformer
  - 传递 device_id 和坐标数组
  - 接收变换后的坐标矩阵
  - 处理坐标变换异常
  - _需求：3.2, 3.3, 3.4, 3.5, 7.5_

- [x] 3.1 编写坐标变换集成的单元测试
  - 在 `test_data_processor.py` 中创建 `TestDataProcessorTransform` 测试类
  - 测试坐标变换正确调用
  - 测试变换后坐标与原始坐标不同
  - 测试异常传播
  - _需求：3.2, 3.5, 7.5_

- [x] 4. 实现滤波处理集成
  - 在 `process()` 方法中调用 FilterManager
  - 传递 device_id、变换后坐标、边界框、置信度、标签
  - 接收滤波后的数据
  - 处理滤波异常
  - _需求：4.2, 4.3, 4.4, 4.5, 4.6, 7.6_

- [x] 4.1 编写滤波处理集成的单元测试
  - 在 `test_data_processor.py` 中创建 `TestDataProcessorFilter` 测试类
  - 测试滤波处理正确调用
  - 测试滤波后数据正确接收
  - 测试异常传播
  - _需求：4.2, 4.6, 7.6_

- [x] 5. 实现输出数据组装逻辑
  - 实现 `_assemble_output()` 私有方法
  - 创建 DeviceProcessedDataDTO 实例
  - 设置所有必需字段（device_id、frame_id、device_alias、coords、bbox、confidence、labels、state_label）
  - 实现 `_create_empty_output()` 私有方法处理空输入
  - _需求：1.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 7.4_

- [x] 5.1 编写输出组装的单元测试
  - 在 `test_data_processor.py` 中创建 `TestDataProcessorAssembly` 测试类
  - 测试输出 DTO 类型正确
  - 测试所有字段正确设置
  - 测试元数据字段传递
  - 测试空输出处理
  - _需求：5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 7.4_

- [x] 6. 实现事件发布逻辑
  - 在 `process()` 方法中发布 PROCESSED_DATA 事件
  - 使用异步模式（wait_all=False）
  - 传递 DeviceProcessedDataDTO 作为事件数据
  - 处理事件发布异常（记录日志但不抛出）
  - _需求：8.2, 8.3, 8.4, 8.5_

- [x] 6.1 编写事件发布的单元测试
  - 在 `test_data_processor.py` 中创建 `TestDataProcessorEvent` 测试类
  - 测试事件正确发布
  - 测试事件数据正确
  - 测试异步模式
  - 测试异常处理（不抛出异常）
  - _需求：8.2, 8.3, 8.4, 8.5_

- [x] 7. 实现完整的 process 方法
  - 整合所有子步骤
  - 实现完整的数据流：提取 → 变换 → 滤波 → 组装 → 发布
  - 处理空输入
  - 处理异常情况
  - 添加日志记录
  - _需求：1.1, 1.2, 1.3, 1.4, 1.5, 3.6, 4.7, 8.6_

- [x] 7.1 编写完整流程的集成测试
  - 在 `test_data_processor.py` 中创建 `TestDataProcessorIntegration` 测试类
  - 测试完整的数据处理流程
  - 测试多帧处理
  - 测试不同设备和标签
  - 测试执行顺序（变换 → 滤波）
  - _需求：所有需求的综合验证_

- [x] 8. 性能优化和代码审查
  - 确认使用 NumPy 向量化操作
  - 确认预分配输出数组
  - 确认避免不必要的数据复制
  - 确认子模块预先创建
  - 代码审查：检查类型注解、文档字符串、代码风格
  - _需求：9.1, 9.2, 9.3, 9.4_

- [ ]* 9. 文档和示例（可选 - MVP 后完成）
  - 编写完整的使用示例（参考设计文档中的示例）
  - 测试与现有 CoordinateTransformer 和 FilterManager 的集成
  - 测试事件总线集成
  - 更新模块文档字符串

- [ ]* 9.1 编写属性测试（Property-Based Testing）（可选 - MVP 后完成）
  - 在 `test_data_processor.py` 中创建 `TestDataProcessorProperties` 测试类
  - **属性 1**：元数据字段传递完整性 - 验证 device_id、frame_id、device_alias 正确传递
  - **属性 2**：数组格式正确性 - 验证输出数组的形状和 dtype
  - **属性 3**：输出数组长度一致性 - 验证所有输出数组长度相等
  - **属性 4**：坐标变换执行 - 验证坐标已被变换
  - **属性 5**：滤波处理执行 - 验证数据已被滤波
  - **属性 6**：空输入处理 - 验证空输入返回空输出
  - **属性 7**：配置验证完整性 - 验证无效配置抛出异常
  - **属性 8**：事件发布执行 - 验证事件正确发布
  - **属性 9**：state_label 初始化 - 验证 state_label 为空列表
  - 使用 `hypothesis` 库
  - 每个属性测试运行至少 100 次迭代
  - _需求：所有需求的综合验证_

## 注意事项

1. **测试文件位置和组织**：
   - **必须**将所有测试放在 `oak_vision_system/tests/unit/modules/data_processing/test_data_processor.py` 文件中
   - 单元测试和属性测试**统一放在同一个文件**中，便于维护
   - 遵循 pytest 命名约定（文件名以 `test_` 开头，测试函数以 `test_` 开头）
   - 使用 pytest 的 class 组织相关测试

2. **依赖现有实现**：
   - 直接使用 `CoordinateTransformer.get_trans_matrices()` 方法
   - 直接使用 `FilterManager.process()` 方法
   - 直接使用 `EventBus.publish()` 方法
   - 不重新实现坐标变换、滤波或事件发布逻辑

3. **数据格式转换**：
   - 使用 NumPy 预分配数组
   - 确保 dtype 正确（float32 和 int32）
   - 保持数组元素的对应关系

4. **错误处理**：
   - 初始化阶段验证配置参数
   - 运行时传播子模块异常
   - 事件发布异常不抛出，只记录日志

5. **事件发布**：
   - 使用异步模式（wait_all=False）
   - 发布 EventType.PROCESSED_DATA 事件
   - 传递 DeviceProcessedDataDTO 作为事件数据

6. **测试任务**：
   - 所有测试任务现在都是必需的
   - 确保全面的测试覆盖

## 实现路径

建议的实现顺序：
1. 任务 1：创建类骨架和初始化（必需）
2. 任务 2：实现数据提取和转换（必需）
3. 任务 3：实现坐标变换集成（必需）
4. 任务 4：实现滤波处理集成（必需）
5. 任务 5：实现输出组装（必需）
6. 任务 6：实现事件发布（必需）
7. 任务 7：实现完整流程（必需）
8. 任务 8：性能优化和审查（必需）
9. 任务 9：文档和示例（必需）
10. 任务 1.1-9.1：单元测试和属性测试（必需）

## 完成标准

- [ ] 所有非可选任务（不带 `*`）已完成
- [ ] 代码通过基本的手动测试
- [ ] 与现有 CoordinateTransformer 和 FilterManager 集成正常
- [ ] 事件总线集成正常
- [ ] 性能满足实时处理要求（20-30 FPS）
