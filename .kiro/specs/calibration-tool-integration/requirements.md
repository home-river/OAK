# 需求文档

## 介绍

将现有的校准工具（tool4.0/5.0）迁移到新架构中，通过最小化侵入的方式实现坐标变换参数的实时调整和误差数据记录功能。该集成方案采用独立GUI线程和线程安全接口的设计，确保对现有系统架构的影响最小。

## 术语表

- **CoordinateTransformer**: 坐标变换模块，负责将相机坐标系转换为机器人基座坐标系
- **DecisionLayer**: 决策层模块，提供目标坐标数据的快照接口
- **CalibrationGUI**: 校准参数调整的图形用户界面
- **ErrorRecorder**: 误差数据记录模块
- **线程安全接口**: 支持多线程并发访问的安全接口
- **参数快照**: 某一时刻参数状态的完整副本
- **原子替换**: 通过创建新的完整副本并一次性替换整个数据结构引用的操作方式
- **变换矩阵字典**: 存储所有设备变换矩阵的字典结构（trans_matrices）
- **mxid**: 设备唯一标识符，用于区分不同的OAK相机设备
- **ConfigManager**: 配置管理器，提供系统配置访问接口，包括get_runnable_mxids()方法获取当前启动的设备列表

## 需求

### 需求 1: CoordinateTransformer线程安全接口

**用户故事**: 作为系统开发者，我希望CoordinateTransformer模块提供线程安全的参数更新接口，以便外部工具可以安全地修改坐标变换参数而不影响主系统运行。

#### 验收标准

1. WHEN 外部工具调用参数更新接口 THEN CoordinateTransformer SHALL 以线程安全的方式更新内部参数
2. WHEN 参数更新正在进行时 THEN 主系统的坐标变换计算 SHALL 不受影响或等待更新完成
3. WHEN 参数更新完成后 THEN 新的变换矩阵 SHALL 立即生效于后续的坐标变换计算
4. THE CoordinateTransformer SHALL 提供获取当前参数快照的接口
5. THE CoordinateTransformer SHALL 提供重置为默认参数的接口
6. THE 参数更新 SHALL 仅在内存中生效，不需要持久化保存到配置文件

### 需求 2: 独立校准GUI界面

**用户故事**: 作为系统操作员，我希望有一个独立的GUI界面来实时调整坐标变换参数，以便在系统运行时进行校准而不需要重启系统。

#### 验收标准

1. THE CalibrationGUI SHALL 在独立线程中运行，不阻塞主系统
2. THE CalibrationGUI SHALL 通过ConfigManager.get_runnable_mxids()接口获取当前启动的设备mxid
3. WHEN 系统为单设备运行时 THEN GUI SHALL 自动使用该设备的mxid进行参数调整
4. WHEN 用户在GUI中修改参数值 THEN 界面 SHALL 实时显示参数变化
5. WHEN 用户点击"设置参数"按钮 THEN GUI SHALL 将当前参数和目标mxid发送到CoordinateTransformer
6. WHEN 参数更新成功 THEN GUI SHALL 显示更新成功的状态反馈
7. WHEN 参数更新失败 THEN GUI SHALL 显示错误信息和失败原因
8. THE GUI SHALL 支持以下参数的调整：Tx、Ty、Tz（平移参数，单位mm）和Ry、Rz（旋转参数，单位度）
9. THE GUI SHALL 提供参数范围验证，防止输入超出有效范围的值
10. THE GUI SHALL 提供重置为默认值的功能，重置到启动时从配置文件加载的参数值
11. THE 参数调整 SHALL 仅影响当前运行时状态，不保存到配置文件
12. THE GUI SHALL 显示当前操作的设备mxid，确保用户知道正在校准哪个设备
13. THE GUI SHALL 提供+/-按钮进行参数微调，平移参数步长为1.0mm，旋转参数步长为0.1度

### 需求 3: 误差数据记录系统

**用户故事**: 作为系统校准工程师，我希望能够设置基准位置并记录实际检测位置与基准位置的误差数据，以便分析和优化校准参数。

#### 验收标准

1. THE ErrorRecorder SHALL 允许用户通过输入框设置基准位置坐标（X、Y坐标，单位mm）
2. WHEN 用户触发误差记录 THEN 系统 SHALL 读取输入框中的基准位置值
3. WHEN 用户触发误差记录 THEN 系统 SHALL 通过DecisionLayer.get_target_coords_snapshot()获取当前目标位置
4. WHEN 获取到目标位置后 THEN 系统 SHALL 计算误差向量（实际位置 - 基准位置）
5. THE 误差数据记录 SHALL 包含以下字段：时间戳、目标类型、实际位置、误差向量、基准位置
6. THE 误差数据 SHALL 以JSON格式保存到指定文件路径（如logs/calibration_errors.json）
7. THE 系统 SHALL 支持追加模式保存误差数据，不覆盖历史记录
8. THE GUI SHALL 显示已记录的数据条数
9. THE 误差数据文件 SHALL 包含完整的校准分析所需信息：基准位置、系统测量值、计算的误差向量

### 需求 4: 系统集成和兼容性

**用户故事**: 作为系统架构师，我希望校准工具的集成不会破坏现有系统的稳定性和性能，并且可以随时启用或禁用校准功能。

#### 验收标准

1. WHEN 校准工具启动时 THEN 主系统的性能 SHALL 不受显著影响（性能损失<5%）
2. WHEN 校准工具未启动时 THEN 系统 SHALL 正常运行，无任何功能缺失
3. THE 校准工具 SHALL 作为可选组件，可以独立启动和关闭
4. THE 现有的配置管理系统 SHALL 不需要修改来支持校准功能
5. THE 校准工具 SHALL 与现有的日志系统兼容
6. WHEN 校准工具发生异常时 THEN 主系统 SHALL 继续正常运行
7. THE 校准参数调整 SHALL 不影响系统的配置文件和持久化设置

### 需求 5: 数据获取和处理

**用户故事**: 作为校准工具用户，我希望能够实时获取系统的目标检测数据，以便进行误差分析和参数调整。

#### 验收标准

1. THE 校准工具 SHALL 通过DecisionLayer接口获取目标坐标数据
2. WHEN 请求目标坐标快照时 THEN DecisionLayer SHALL 返回当前时刻的所有目标位置信息
3. THE 获取的坐标数据 SHALL 包含目标类型（如durian、person）和三维坐标信息
4. THE 坐标数据获取 SHALL 是非阻塞的，不影响主系统的实时性
5. WHEN 没有检测到目标时 THEN 系统 SHALL 返回空数据或明确的无目标状态

### 需求 6: 用户界面和交互

**用户故事**: 作为系统操作员，我希望校准工具的界面直观易用，能够快速完成参数调整和误差记录操作。

#### 验收标准

1. THE GUI界面 SHALL 提供清晰的参数标签和单位显示
2. THE GUI SHALL 支持通过输入框直接输入参数值
3. THE GUI SHALL 提供+/-按钮进行参数的微调，平移参数（Tx、Ty、Tz）步长为1.0mm，旋转参数（Ry、Rz）步长为0.1度
4. THE GUI SHALL 实时显示当前参数值的状态
5. THE 基准位置设置 SHALL 支持X、Y坐标的独立输入
6. THE 基准位置 SHALL 直接从输入框读取，无需额外确认按钮
7. WHEN 用户进行任何操作时 THEN GUI SHALL 提供即时的视觉反馈
8. THE GUI窗口 SHALL 支持置顶显示，便于与主系统窗口同时使用
9. THE "重置为默认"功能 SHALL 将参数恢复到启动时从配置文件加载的初始值

### 需求 7: 坐标变换矩阵原子替换机制

**用户故事**: 作为系统架构师，我希望坐标变换矩阵的更新采用原子替换机制，确保在多线程环境下变换矩阵的一致性和完整性，避免部分更新导致的计算错误。

#### 验收标准

1. THE 坐标变换矩阵更新 SHALL 采用字典整体替换策略，而非逐个矩阵元素更新
2. WHEN 新的校准参数传入时 THEN 系统 SHALL 在独立的内存空间中构建完整的新变换矩阵字典副本
3. WHEN 新变换矩阵字典构建完成后 THEN 系统 SHALL 通过单次原子操作替换整个trans_matrices字典引用
4. WHEN 矩阵字典替换正在进行时 THEN 正在执行坐标变换的线程 SHALL 继续使用完整的旧字典
5. THE 字典替换操作 SHALL 在微秒级时间内完成，最小化锁持有时间
6. THE 系统 SHALL 确保任何时刻都不会出现部分更新的不一致矩阵状态
7. THE 原子替换机制 SHALL 支持按mxid独立更新单个设备的变换矩阵，不影响其他设备
8. THE 参数更新接口 SHALL 接收mxid参数，明确指定要更新的目标设备
9. WHEN 校准工具启动时 THEN 系统 SHALL 通过ConfigManager.get_runnable_mxids()获取当前运行设备的mxid
10. WHEN 矩阵替换失败时 THEN 系统 SHALL 保持使用原有矩阵，并记录错误日志

### 需求 8: 线程安全的参数管理

**用户故事**: 作为校准工具开发者，我希望能够在系统运行时安全地更新坐标变换参数，而不会影响主系统的实时检测和坐标变换功能。

#### 验收标准

1. THE CoordinateTransformer SHALL 使用读写锁（RWLock）或类似机制保护变换矩阵访问
2. WHEN 多个线程同时读取变换矩阵时 THEN 系统 SHALL 允许并发读取操作
3. WHEN 校准工具更新参数时 THEN 系统 SHALL 获取写锁，阻止新的读取操作
4. THE 写锁持有时间 SHALL 限制在矩阵构建和替换的最短时间内
5. THE 参数更新接口 SHALL 提供非阻塞选项，允许调用者选择等待或立即返回
6. WHEN 参数更新冲突时 THEN 系统 SHALL 返回明确的错误状态和重试建议
7. THE 线程安全机制 SHALL 确保参数读取的一致性，避免读取到部分更新的参数值