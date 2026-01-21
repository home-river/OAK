# FilterManager 实现任务列表

## 概述

本任务列表将 FilterManager 的设计转换为可执行的实现步骤。FilterManager 是一个协调组件，负责管理多个 FilterPool 实例，按设备和标签分发检测数据，并块状拼接输出结果。

## 任务

- [x] 1. 创建 FilterManager 类骨架和初始化逻辑
  - 创建 `oak_vision_system/modules/data_processing/filter_manager.py` 文件
  - 定义 `FilterManager` 类和 `__init__()` 方法
  - 实现配置参数验证（device_metadata、label_map、pool_size 等）
  - 预先创建所有 (device_id, label) 组合的 FilterPool 实例
  - 存储配置参数供后续使用
  - _需求：1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 6.1, 6.2, 6.3, 6.4_

- [x] 1.1 编写初始化验证的单元测试

  - 在 `oak_vision_system/tests/unit/modules/data_processing/test_filter_manager.py` 中创建 `TestFilterManagerInit` 测试类
  - 测试有效配置的初始化
  - 测试无效配置抛出 ValueError（空 device_metadata、空 label_map、无效 pool_size、空 MXid）
  - 测试 FilterPool 实例正确创建（验证所有 (device_id, label) 组合）
  - 测试配置参数正确存储
  - _需求：6.1, 6.2, 6.3, 6.4_

- [x] 2. 实现数据分组和分发逻辑
  - 实现 `process()` 方法的数据分组部分
  - 根据 labels 提取唯一标签
  - 为每个唯一标签提取对应的索引数组
  - 使用 NumPy 布尔索引切片 coordinates、bboxes、confidences
  - 将切片后的数据传递给对应的 FilterPool
  - _需求：2.1, 2.3, 2.4, 2.5, 2.6, 7.2_

- [x] 2.1 编写数据分组的单元测试

  - 在 `test_filter_manager.py` 中创建 `TestFilterManagerGrouping` 测试类
  - 测试单标签输入
  - 测试多标签混合输入
  - 测试空输入（n=0）
  - 测试数据正确切片
  - _需求：2.3, 2.4, 2.5, 2.7_

- [x] 3. 实现结果聚合和块状拼接逻辑
  - 收集所有 FilterPool 的输出结果
  - 为每个 FilterPool 的输出生成对应的 label 数组
  - 使用 `np.concatenate()` 或 `np.vstack()` 块状拼接所有结果
  - 确保 coordinates、bboxes、confidences、labels 的对应关系一致
  - 返回四个 NumPy 数组
  - _需求：3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 7.3_

- [x] 3.1 编写结果拼接的单元测试

  - 在 `test_filter_manager.py` 中创建 `TestFilterManagerAggregation` 测试类
  - 测试块状拼接顺序正确
  - 测试输出长度一致性
  - 测试多标签混合场景
  - 测试空输出处理
  - _需求：3.5, 3.6, 3.7_

- [x] 4. 实现统计信息查询接口
  - 实现 `get_pool_stats()` 方法
  - 遍历所有 FilterPool 实例
  - 收集每个 FilterPool 的 capacity 和 active_count
  - 返回字典格式 `{(device_id, label): {"capacity": int, "active_count": int}}`
  - _需求：5.1, 5.2, 5.3_

- [x] 4.1 编写统计信息的单元测试

  - 在 `test_filter_manager.py` 中创建 `TestFilterManagerStats` 测试类
  - 测试返回格式正确
  - 测试统计信息准确性
  - 测试所有 FilterPool 都被包含
  - _需求：5.1, 5.2, 5.3_

- [x] 5. 性能优化和代码审查
  - 确认使用 NumPy 向量化操作（布尔索引、concatenate）
  - 确认预分配输出数组
  - 确认避免不必要的数据复制（使用视图而非 copy）
  - 确认零运行时验证（process 方法中无验证逻辑）
  - 代码审查：检查类型注解、文档字符串、代码风格
  - _需求：7.1, 7.2, 7.3, 7.4, 6.5, 6.6_

- [ ] 6. 集成测试和文档
  - 编写完整的使用示例（参考设计文档中的示例）
  - 测试与现有 FilterPool 的集成
  - 测试多设备、多标签的实际场景
  - 更新模块文档字符串

- [ ]* 6.1 编写属性测试（Property-Based Testing）
  - 在 `test_filter_manager.py` 中创建 `TestFilterManagerProperties` 测试类
  - **属性 1**：FilterPool 实例完整性 - 验证所有 (device_id, label) 组合都有对应的 FilterPool
  - **属性 2**：数据分组正确性 - 验证分组后每组内标签一致
  - **属性 3**：输出长度一致性 - 验证输出的四个数组长度相等
  - **属性 4**：块状拼接顺序性 - 验证同一标签的元素是连续的块
  - **属性 5**：配置验证完整性 - 验证无效配置抛出异常
  - **属性 6**：零运行时验证 - 验证 process() 不执行验证逻辑
  - **属性 7**：统计信息准确性 - 验证 get_pool_stats() 返回正确的 capacity
  - 使用 `hypothesis` 或 `pytest-quickcheck` 库
  - 每个属性测试运行至少 100 次迭代
  - _需求：所有需求的综合验证_

## 注意事项

1. **测试文件位置和组织**：
   - **必须**将所有测试放在 `oak_vision_system/tests/unit/modules/data_processing/test_filter_manager.py` 文件中
   - 单元测试和属性测试**统一放在同一个文件**中，便于维护
   - 文件路径：`oak_vision_system/tests/unit/modules/data_processing/test_filter_manager.py`
   - 遵循 pytest 命名约定（文件名以 `test_` 开头，测试函数以 `test_` 开头）
   - 使用 pytest 的 class 组织相关测试（如 `TestFilterManagerInit`、`TestFilterManagerProcess` 等）

2. **依赖现有实现**：
   - 直接使用 `FilterPool.step_v2()` 方法
   - 导入 `BaseSpatialFilter`、`MovingAverageFilter`、`HungarianTracker`
   - 不重新实现滤波或跟踪逻辑

3. **零运行时验证**：
   - `process()` 方法中不进行任何输入验证
   - 假设调用方保证数据正确性
   - 只在 `__init__()` 中验证配置参数

4. **NumPy 性能优化**：
   - 使用布尔索引：`coordinates[labels == target_label]`
   - 使用 `np.concatenate()` 或 `np.vstack()` 拼接
   - 使用 `dtype=np.float32` 和 `dtype=np.int32`
   - 避免 `.copy()`，使用视图

5. **块状拼接顺序**：
   - 按 `(device_id, label)` 的字典序拼接
   - 确保 coordinates、bboxes、confidences、labels 的对应关系

6. **测试任务标记**：
   - 标记 `*` 的任务为可选任务
   - 可以先实现核心功能，后续补充测试

## 实现路径

建议的实现顺序：
1. 任务 1：创建类骨架和初始化（必需）
2. 任务 2：实现数据分组和分发（必需）
3. 任务 3：实现结果拼接（必需）
4. 任务 4：实现统计信息（必需）
5. 任务 5：性能优化和审查（必需）
6. 任务 6：集成测试和文档（必需）
7. 任务 1.1, 2.1, 3.1, 4.1, 6.1：单元测试和属性测试（可选）

## 完成标准

- [ ] 所有非可选任务（不带 `*`）已完成
- [ ] 代码通过基本的手动测试
- [ ] 与现有 FilterPool 集成正常
- [ ] 性能满足实时处理要求（20-30 FPS）
