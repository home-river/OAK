# Requirements Document

## Introduction

本文档定义了OAK视觉检测系统的Smoke测试（不含CAN）功能需求。该测试系统使用SystemManager管理模块生命周期，通过MockCANReceiver替代真实CAN硬件，验证从数据采集到决策输出的完整数据流。Smoke测试支持在Windows开发环境中进行快速验证和调试，为后续的生产环境主脚本提供参考实现。

## Glossary

- **Smoke_Test**: 冒烟测试，快速验证主要功能的集成测试
- **SystemManager**: 系统管理器，负责模块生命周期管理和协调关闭（在system-manager spec中定义）
- **Collector**: 数据采集器模块，负责从OAK设备采集视频和检测数据
- **DataProcessor**: 数据处理器模块，负责处理原始检测数据
- **Display**: 显示模块，负责实时显示检测结果
- **MockCANReceiver**: 模拟CAN接收端，替代真实CAN硬件，打印警告信息到控制台
- **EventBus**: 事件总线，模块间通信的基础设施
- **WARNING_ALERT**: 警告事件类型，由DataProcessor发布

## Requirements

### Requirement 1: 系统初始化和配置

**User Story:** 作为开发者，我想要快速初始化测试系统，以便验证完整的检测流程。

#### Acceptance Criteria

1. WHEN 系统启动时 THEN THE System SHALL 自动发现可用的OAK设备
2. WHEN 配置文件存在时 THEN THE System SHALL 加载配置并应用设备绑定
3. WHEN 配置文件不存在时 THEN THE System SHALL 使用默认配置并提示用户
4. THE System SHALL 初始化事件总线作为模块间通信基础设施
5. THE System SHALL 创建并注册所有必需的模块实例

### Requirement 2: SystemManager集成

**User Story:** 作为Smoke测试，我想要使用SystemManager管理所有模块，以便复用统一的生命周期管理机制。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 创建SystemManager实例并传入事件总线
2. THE Smoke_Test SHALL 注册MockCANReceiver模块（优先级=100）
3. THE Smoke_Test SHALL 注册Display模块（优先级=50）
4. THE Smoke_Test SHALL 注册DataProcessor模块（优先级=30）
5. THE Smoke_Test SHALL 注册Collector模块（优先级=10）

### Requirement 3: 测试配置加载

**User Story:** 作为Smoke测试，我想要加载测试配置，以便使用合适的参数运行测试。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 支持从配置文件加载OAK设备配置
2. THE Smoke_Test SHALL 支持从配置文件加载DataProcessor配置
3. THE Smoke_Test SHALL 支持从配置文件加载Display配置
4. WHEN 配置文件不存在时 THEN THE Smoke_Test SHALL 使用默认配置
5. THE Smoke_Test SHALL 使用测试专用的模型路径（assets/test_config/yolov8.blob）

### Requirement 4: 设备发现和绑定

**User Story:** 作为Smoke测试，我想要自动发现并绑定OAK设备，以便快速启动测试。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 使用DeviceDiscoverer扫描可用的OAK设备
2. THE Smoke_Test SHALL 显示发现的设备列表（MXID和产品名）
3. WHEN 发现多个设备时 THEN THE Smoke_Test SHALL 支持多设备测试
4. THE Smoke_Test SHALL 使用ConfigManager处理设备绑定
5. THE Smoke_Test SHALL 在设备发现后等待3秒以确保设备完全释放连接

### Requirement 5: MockCANReceiver实现

**User Story:** 作为Smoke测试，我想要使用MockCANReceiver替代真实CAN模块，以便在没有CAN硬件的情况下验证决策输出。

#### Acceptance Criteria

1. THE MockCANReceiver SHALL 订阅WARNING_ALERT事件
2. WHEN 接收到警告事件时 THEN THE MockCANReceiver SHALL 打印警告信息到控制台
3. THE MockCANReceiver SHALL 显示目标类型、位置坐标（X, Y, Z）和置信度
4. THE MockCANReceiver SHALL 显示警告级别、来源设备和时间戳
5. THE MockCANReceiver SHALL 维护警告统计计数并定期显示

### Requirement 6: 测试启动流程

**User Story:** 作为Smoke测试，我想要按正确顺序启动所有模块，以便系统能够正常运行。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 首先初始化事件总线
2. THE Smoke_Test SHALL 创建并配置所有模块实例
3. THE Smoke_Test SHALL 将所有模块注册到SystemManager
4. THE Smoke_Test SHALL 调用SystemManager.start_all启动除Display外的所有模块
5. THE Smoke_Test SHALL 最后调用SystemManager.run让Display阻塞主线程

### Requirement 7: 测试退出机制

**User Story:** 作为Smoke测试用户，我想要通过多种方式退出测试，以便灵活控制测试流程。

#### Acceptance Criteria

1. WHEN 用户按Q键时 THEN THE Display SHALL 发布SYSTEM_SHUTDOWN事件
2. WHEN 用户按Ctrl+C时 THEN THE SystemManager SHALL 发布SYSTEM_SHUTDOWN事件
3. THE SystemManager SHALL 订阅SYSTEM_SHUTDOWN事件并触发关闭流程
4. THE Smoke_Test SHALL 在退出时显示最终统计摘要
5. THE Smoke_Test SHALL 确保所有模块被正确关闭

### Requirement 8: 统计信息收集和显示

**User Story:** 作为Smoke测试用户，我想要查看详细的统计信息，以便评估系统性能和运行状态。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 定期显示采集统计信息（每10秒）
2. THE 统计信息 SHALL 包含运行时间、总帧数、总检测数和平均帧率
3. WHEN 多设备运行时 THEN THE Smoke_Test SHALL 显示每个设备的详细统计
4. THE Smoke_Test SHALL 显示设备间同步性指标（帧数差异和差异比例）
5. THE Smoke_Test SHALL 显示MockCANReceiver接收到的警告数量

### Requirement 9: 测试数据流验证

**User Story:** 作为Smoke测试，我想要验证完整的数据流，以便确认从采集到输出的所有环节正常工作。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 验证Collector能够成功采集视频帧和检测数据
2. THE Smoke_Test SHALL 验证DataProcessor能够接收并处理检测数据
3. THE Smoke_Test SHALL 验证Display能够接收并显示处理后的数据
4. THE Smoke_Test SHALL 验证MockCANReceiver能够接收警告事件
5. THE Smoke_Test SHALL 验证事件总线能够正确传递所有事件类型

### Requirement 10: 测试运行时间控制

**User Story:** 作为Smoke测试用户，我想要控制测试运行时间，以便进行快速验证或长时间稳定性测试。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 支持通过命令行参数指定运行时长（秒）
2. WHEN 指定运行时长时 THEN THE Smoke_Test SHALL 在时间到达后自动停止
3. WHEN 未指定运行时长时 THEN THE Smoke_Test SHALL 持续运行直到用户手动停止
4. THE Smoke_Test SHALL 在自动停止前显示倒计时提示
5. THE Smoke_Test SHALL 在达到时长后发布SYSTEM_SHUTDOWN事件

### Requirement 11: 测试结果评估

**User Story:** 作为Smoke测试用户，我想要自动评估测试结果，以便快速判断系统是否正常工作。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 在测试结束时评估是否采集到足够的帧数（>0）
2. THE Smoke_Test SHALL 评估平均帧率是否达到预期阈值（>15 fps）
3. THE Smoke_Test SHALL 评估是否有检测数据产生
4. THE Smoke_Test SHALL 评估MockCANReceiver是否接收到警告事件
5. THE Smoke_Test SHALL 显示测试通过/失败状态和详细原因

### Requirement 12: 测试报告生成

**User Story:** 作为Smoke测试用户，我想要生成测试报告，以便记录和分享测试结果。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 在测试结束时生成文本格式的测试报告
2. THE 测试报告 SHALL 包含测试开始和结束时间
3. THE 测试报告 SHALL 包含所有模块的运行统计信息
4. THE 测试报告 SHALL 包含测试通过/失败状态
5. THE Smoke_Test SHALL 将报告保存到指定目录（可选）

### Requirement 13: 错误场景测试

**User Story:** 作为Smoke测试，我想要测试常见的错误场景，以便验证系统的健壮性。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 测试无设备连接时的错误处理
2. THE Smoke_Test SHALL 测试配置文件缺失时的默认行为
3. THE Smoke_Test SHALL 测试模型文件缺失时的错误提示
4. THE Smoke_Test SHALL 测试模块启动失败时的回滚机制
5. THE Smoke_Test SHALL 验证所有错误场景都有清晰的错误消息

### Requirement 14: 测试配置灵活性

**User Story:** 作为开发者，我想要灵活的测试配置选项，以便适应不同的测试场景。

#### Acceptance Criteria

1. THE Smoke_Test SHALL 支持通过命令行参数指定配置文件路径
2. THE Smoke_Test SHALL 支持通过命令行参数启用/禁用Display模块
3. THE Smoke_Test SHALL 支持通过命令行参数启用/禁用MockCANReceiver
4. THE Smoke_Test SHALL 支持通过命令行参数设置日志级别
5. THE Smoke_Test SHALL 显示所有可用的命令行参数帮助信息
