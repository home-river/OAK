# 实施计划：校准工具集成

## 概述

将现有的校准工具（tool4.0/5.0）迁移到新架构中，通过最小化侵入的方式实现坐标变换参数的实时调整和误差数据记录功能。该集成方案采用独立GUI线程和线程安全接口的设计，确保对现有系统架构的影响最小。

## 任务

- [x] 1. 创建校准工具项目结构
  - 创建 `tools/calibration_tools/core/` 目录
  - 创建 `tools/calibration_tools/gui/` 目录
  - 创建必要的 `__init__.py` 文件
  - _需求: 4.3_

- [x] 2. 扩展主系统类以支持校准工具
  - [x] 2.1 在 CoordinateTransfomer 类中添加线程安全的矩阵更新接口
    - 在 `__init__` 方法中添加 RLock 实例变量 `_lock`
    - 修改 `transform_coordinates` 方法，使用读锁保护 `trans_matrices` 访问
    - 实现 `update_matrices(new_matrices: Dict[str, np.ndarray])` 方法
    - 在锁内原子替换 `trans_matrices` 字典引用
    - _需求: 1.1, 7.1, 7.3, 8.1, 8.2_
  
  - [x] 2.2 在 DataProcessor 类中添加矩阵更新代理接口
    - 实现 `update_transform_matrices(new_matrices: Dict[str, np.ndarray])` 方法
    - 直接调用 `self._transformer.update_matrices(new_matrices)`
    - _需求: 1.1_
  
  - [x] 2.3 编写 CoordinateTransfomer 扩展功能的属性测试

    - **属性 1: 变换矩阵原子替换一致性**
    - **验证: 需求 7.3, 7.6**
  
  - [x] 2.4 编写 CoordinateTransfomer 扩展功能的单元测试

    - 测试矩阵更新的线程安全性
    - 测试并发读写安全性
    - _需求: 8.2_

- [x] 3. 实现校准工具参数管理器
  - [x] 3.1 实现 TransformParamManager 核心类
    - 创建 `tools/calibration_tools/core/transform_param_manager.py`
    - 实现 `__init__` 方法，接收 ConfigManager 和 DataProcessor 实例
    - 实现 `_load_initial_configs` 方法，从配置加载初始参数
    - 通过 `get_active_role_binding_dtos()` 获取角色绑定
    - 通过 `get_data_processing_config()` 获取数据处理配置
    - 保存 `_initial_configs: Dict[str, CoordinateTransformConfigDTO]`
    - 保存 `_mxid_to_role: Dict[str, DeviceRole]` 映射关系
    - _需求: 1.4, 1.5_
  
  - [x] 3.2 实现矩阵构建方法
    - 实现 `_build_transform_matrix(config: CoordinateTransformConfigDTO)` 方法
    - 使用 `trans_utils.py` 中的工具函数构建变换矩阵
    - 流程：T_oak_to_xyz → R_pitch → R_yaw → T_trans（与 `_create_trans_matrix` 一致）
    - 返回 4x4 的 np.ndarray 变换矩阵
    - _需求: 1.1, 7.1_
  
  - [x] 3.3 实现参数更新接口
    - 实现 `update_params(mxid, tx, ty, tz, pitch, yaw)` 方法
    - 创建临时 CoordinateTransformConfigDTO 对象
    - 调用 `_build_transform_matrix` 构建新矩阵
    - 深拷贝 `_current_matrices` 并更新指定设备的矩阵
    - 调用 `data_processor.update_transform_matrices` 更新主系统
    - 更新成功后同步本地 `_current_matrices` 副本
    - _需求: 1.1, 1.2, 7.2, 7.3, 7.7_
  
  - [x] 3.4 实现参数查询和重置接口
    - 实现 `get_params_snapshot(mxid)` 方法，从 `_initial_configs` 读取并返回参数字典
    - 实现 `reset_to_default(mxid)` 方法，从 `_initial_configs` 获取初始配置
    - 调用 `update_params` 使用初始参数更新矩阵
    - 实现 `get_current_mxid()` 方法，验证并返回单设备的 mxid
    - _需求: 1.4, 1.5, 6.9, 7.9_
  
  - [x] 3.5 编写 TransformParamManager 的单元测试

    - 测试参数加载和初始化
    - 测试矩阵构建正确性
    - 测试参数更新流程
    - 测试重置功能
    - _需求: 1.1, 1.5_

- [x] 4. 实现误差数据记录模块
  - [x] 4.1 实现 ErrorRecorder 核心类
    - 实现 `__init__` 方法，初始化日志文件路径
    - 实现 `record_error` 方法，接收基准位置参数并记录误差
    - 从 DecisionLayer 获取目标坐标快照
    - 计算误差向量（实际位置 - 基准位置）
    - _需求: 3.1, 3.2, 3.3, 3.4, 5.1, 5.2_
  
  - [x] 4.2 实现误差数据持久化
    - 实现 `_append_to_json` 方法，追加模式保存误差数据
    - 构造包含时间戳、目标类型、实际位置、误差向量的记录
    - 确保不覆盖历史记录
    - _需求: 3.5, 3.6, 3.7, 3.9_
  
  - [x] 4.3 实现统计信息接口
    - 实现 `get_statistics` 方法，计算误差统计信息
    - 返回记录数、平均误差、标准差等
    - _需求: 3.8_
  
  - [x] 4.4 编写 ErrorRecorder 的属性测试

    - **属性 4: 误差计算正确性**
    - **验证: 需求 3.4**
  
  - [x] 4.5 编写 ErrorRecorder 的单元测试

    - 测试误差计算正确性
    - 测试追加模式不覆盖历史
    - 测试无目标时的处理
    - _需求: 3.3, 3.6, 5.5_

- [x] 5. 实现校准GUI界面
  - [x] 5.1 实现 CalibrationGUI 核心框架
    - 实现 `__init__` 方法，初始化 Tkinter 窗口
    - 接收 TransformParamManager 和 ErrorRecorder 实例作为参数
    - 通过 `param_manager.get_current_mxid()` 获取设备 mxid
    - 通过 `param_manager.get_params_snapshot(mxid)` 获取初始参数值
    - 验证单设备运行模式
    - _需求: 2.1, 2.2, 2.3, 2.12, 7.9_
  - [x] 5.2 实现参数调整UI组件
    - 实现 `_create_widgets` 方法，创建参数调整界面
    - 实现 `_create_param_row` 方法，创建参数行（输入框 + 微调按钮）
    - 平移参数步长 1.0mm，旋转参数步长 0.1度
    - 显示当前设备 mxid
    - _需求: 2.4, 2.8, 2.13, 6.1, 6.2, 6.3_
  
  - [x] 5.3 实现参数更新回调
    - 实现 `_on_set_params` 方法，调用 `param_manager.update_params` 更新参数
    - 实现 `_on_reset` 方法，调用 `param_manager.reset_to_default` 重置参数
    - 提供状态反馈（成功/失败）
    - _需求: 2.5, 2.6, 2.7, 2.10, 6.4, 6.9_
  
  - [x] 5.4 实现误差记录UI组件
    - 添加基准位置输入框（X、Y坐标）
    - 实现 `_on_record_error` 方法，从输入框读取基准位置并记录误差
    - 显示已记录数据条数
    - _需求: 3.1, 3.2, 6.5, 6.6_
  
  - [x] 5.5 实现GUI线程管理
    - 实现 `run` 方法，启动 Tkinter 主循环
    - 实现 `start_in_thread` 静态方法，在独立线程中启动 GUI
    - 接收 TransformParamManager 和 ErrorRecorder 实例作为参数
    - 设置为 daemon 线程，不阻塞主系统
    - _需求: 2.1, 4.6_
  
  - [x] 5.6 编写 GUI 集成测试

    - 测试参数更新流程
    - 测试误差记录流程
    - 测试重置功能
    - _需求: 2.5, 2.6, 2.7, 3.2_

- [x] 6. 实现校准工具启动入口
  - [x] 6.1 创建 calibration_main.py 启动脚本
    - 实现 `main` 函数，初始化所有组件
    - 从 ConfigManager 获取配置
    - 验证单设备运行模式（通过 `get_runnable_mxids()` 检查）
    - 获取主系统的 DataProcessor 实例
    - 获取 DecisionLayer 实例（通过 `DecisionLayer.get_instance()`）
    - 创建 TransformParamManager 实例（传入 ConfigManager 和 DataProcessor）
    - 创建 ErrorRecorder 实例
    - 创建 CalibrationGUI 实例并传入 TransformParamManager 和 ErrorRecorder
    - 在独立线程中启动 GUI
    - _需求: 4.2, 4.3, 7.9_
  
  - [x] 6.2 实现错误处理和日志记录
    - 捕获启动异常，提供清晰的错误信息
    - 配置日志系统
    - 处理 DecisionLayer 未初始化的情况
    - _需求: 4.5, 4.6_
  
  - [x] 6.3 编写端到端集成测试

    - 测试完整的校准工作流程
    - 测试主系统和校准工具的协同工作
    - _需求: 4.1, 4.2, 4.6_

- [ ] 7. 检查点 - 确保所有测试通过
  - 运行所有单元测试和属性测试
  - 验证线程安全性
  - 验证参数更新不影响配置文件
  - 如有问题请向用户反馈

- [ ] 8. 性能验证和优化
  - [ ] 8.1 验证性能影响
    - 测量校准工具对主系统性能的影响
    - 确保性能损失 < 5%
    - _需求: 4.1_
  
  - [ ] 8.2 优化锁持有时间
    - 验证锁持有时间 < 0.1ms
    - 优化矩阵构建和替换流程
    - _需求: 7.5, 8.4_

- [ ] 9. 文档和使用说明
  - [ ] 9.1 创建使用文档
    - 编写启动步骤说明
    - 编写参数调整指南
    - 编写误差记录指南
  
  - [ ] 9.2 创建开发文档
    - 记录架构设计决策
    - 记录线程安全机制
    - 记录扩展点和未来改进方向

## 注意事项

- 任务标记 `*` 的为可选测试任务，可以跳过以加快 MVP 开发
- 每个任务都引用了具体的需求编号，确保可追溯性
- 任务按照依赖关系排序，每个任务都基于前面的任务构建
- 校准工具作为独立组件，不修改主系统代码
- 所有参数更新仅在内存中生效，不持久化到配置文件
