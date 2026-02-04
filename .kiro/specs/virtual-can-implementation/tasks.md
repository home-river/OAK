# 虚拟 CAN 通信器实现任务列表

## 概述

本文档定义了实现虚拟 CAN 通信器的具体任务。通过抽象基类和工厂模式，在不影响现有真实 CAN 实现的前提下，添加虚拟 CAN 实现以支持 Windows 开发环境和无硬件测试场景。

## 设计原则

- **最小改动**：现有 `CANCommunicator` 只修改 2 行代码
- **零风险**：不影响生产环境的稳定性
- **接口一致**：真实和虚拟实现具有相同的接口
- **事件消费**：虚拟实现订阅并消费 PERSON_WARNING 事件，但不执行硬件操作

## 任务

### 阶段 1: 抽象基类设计

- [x] 1. 创建 CAN 通信器抽象基类
  - [x] 1.1 创建 `can_communicator_base.py` 文件
    - 定义 `CANCommunicatorBase` 抽象类
    - 定义 `__init__` 方法（接收 config, decision_layer, event_bus）
    - 定义抽象方法 `start() -> bool`
    - 定义抽象方法 `stop(timeout: float) -> bool`
    - 定义 `is_running` 属性
    - 添加完整的文档字符串
    - _Requirements: 1.1, 1.2_
  
  - [x] 1.2 添加类型提示和导入
    - 使用 `TYPE_CHECKING` 避免循环导入
    - 导入必要的类型（CANConfigDTO, DecisionLayer, EventBus）
    - 添加 logger 配置
    - _Requirements: 1.1_

### 阶段 2: 修改现有真实 CAN 实现

- [x] 2. 最小化修改现有 CANCommunicator
  - [x] 2.1 修改类定义继承基类
    - 修改 `class CANCommunicator(can.Listener)` 为 `class CANCommunicator(CANCommunicatorBase, can.Listener)`
    - 导入 `CANCommunicatorBase`
    - _Requirements: 2.1, 2.2_
  
  - [x] 2.2 修改 `__init__` 方法
    - 在方法开头添加 `CANCommunicatorBase.__init__(self, config, decision_layer, event_bus)`
    - 保持其他所有代码不变
    - _Requirements: 2.1, 2.2_
  
  - [x] 2.3 验证现有功能不受影响
    - 运行现有的 CAN 模块单元测试
    - 确认所有测试通过
    - _Requirements: 2.2_

### 阶段 3: 实现虚拟 CAN 通信器

- [x] 3. 创建虚拟 CAN 通信器
  - [x] 3.1 创建 `virtual_can_communicator.py` 文件
    - 定义 `VirtualCANCommunicator` 类，继承 `CANCommunicatorBase`
    - 实现 `__init__` 方法
    - 初始化统计计数器（alert_triggered_count, alert_cleared_count, coordinate_request_count）
    - 初始化状态标志（_alert_active, _is_running）
    - 添加完整的文档字符串
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [x] 3.2 实现 `start()` 方法
    - 检查是否已运行（幂等性）
    - 订阅 `EventType.PERSON_WARNING` 事件
    - 设置 `_is_running = True`
    - 输出清晰的启动日志（包括功能说明和警告）
    - 处理异常并返回 bool
    - _Requirements: 3.1, 3.2, 3.4_
  
  - [x] 3.3 实现 `stop()` 方法
    - 检查是否正在运行（幂等性）
    - 取消事件订阅
    - 设置 `_is_running = False`
    - 输出统计信息日志
    - 处理异常并返回 bool
    - _Requirements: 3.1, 3.2, 3.4_
  
  - [x] 3.4 实现 `_on_person_warning()` 事件回调
    - 解析 event_data 获取 status 和 timestamp
    - 处理 TRIGGERED 状态：
      - 设置 `_alert_active = True`
      - 增加 `_alert_triggered_count`
      - 输出详细警告日志（包括真实环境行为说明）
    - 处理 CLEARED 状态：
      - 设置 `_alert_active = False`
      - 增加 `_alert_cleared_count`
      - 输出详细信息日志（包括真实环境行为说明）
    - 添加异常处理
    - _Requirements: 3.3, 3.4, 3.5_
  
  - [x] 3.5 实现 `simulate_coordinate_request()` 方法
    - 增加 `_coordinate_request_count`
    - 调用 `decision_layer.get_target_coords_snapshot()`
    - 处理返回 None 的情况（兜底坐标 0,0,0）
    - 转换坐标为整数
    - 输出详细日志（包括真实环境行为说明）
    - 返回坐标元组 (x, y, z)
    - 添加异常处理
    - _Requirements: 3.6_
  
  - [x] 3.6 实现 `get_stats()` 方法
    - 返回包含所有统计信息的字典
    - 包括：is_running, alert_active, alert_triggered_count, alert_cleared_count, coordinate_request_count
    - _Requirements: 3.7_
  
  - [x] 3.7 实现 `reset_stats()` 方法
    - 重置所有统计计数器为 0
    - 输出重置日志
    - _Requirements: 3.7_

### 阶段 4: 工厂函数实现

- [x] 4. 创建 CAN 通信器工厂
  - [x] 4.1 创建 `can_factory.py` 文件
    - 定义 `create_can_communicator()` 工厂函数
    - 接收参数：config, decision_layer, event_bus
    - 返回类型：CANCommunicatorBase
    - 添加完整的文档字符串和使用示例
    - _Requirements: 4.1, 4.2_
  
  - [x] 4.2 实现工厂逻辑
    - 检查 `config.enable_can` 标志
    - 如果 True：导入并创建 `CANCommunicator` 实例
    - 如果 False：导入并创建 `VirtualCANCommunicator` 实例
    - 输出创建日志（说明创建的是哪种类型）
    - 返回实例
    - _Requirements: 4.1, 4.2_

### 阶段 5: 配置支持

- [x] 5. 更新配置 DTO
  - [x] 5.1 修改 `CANConfigDTO`
    - 添加 `enable_can: bool = False` 字段
    - 添加字段文档说明（False=虚拟模式，True=真实模式）
    - 保持其他字段不变
    - _Requirements: 5.1_
  
  - [x] 5.2 更新配置文件示例
    - 在示例配置中添加 `enable_can` 字段
    - 添加注释说明用途
    - _Requirements: 5.1_

### 阶段 6: 模块导出更新

- [x] 6. 更新模块 `__init__.py`
  - [x] 6.1 更新 `can_communication/__init__.py`
    - 导出 `CANCommunicatorBase`
    - 导出 `CANCommunicator`
    - 导出 `VirtualCANCommunicator`
    - 导出 `create_can_communicator`
    - 保持向后兼容（现有导入不受影响）
    - _Requirements: 6.1_

### 阶段 7: 单元测试

- [x] 7. 编写单元测试
  - [x]* 7.1 测试抽象基类
    - 测试不能直接实例化抽象类
    - 测试子类必须实现抽象方法
    - _Requirements: 1.1_
  
  - [x]* 7.2 测试虚拟 CAN 通信器基础功能
    - 测试初始化
    - 测试 start() 方法
    - 测试 stop() 方法
    - 测试 is_running 属性
    - _Requirements: 3.1, 3.2_
  
  - [x]* 7.3 测试虚拟 CAN 事件处理
    - 测试订阅 PERSON_WARNING 事件
    - 测试 TRIGGERED 事件处理
    - 测试 CLEARED 事件处理
    - 测试统计计数器更新
    - 测试状态标志更新
    - _Requirements: 3.3, 3.4, 3.5_
  
  - [x]* 7.4 测试坐标请求模拟
    - 测试有目标时的坐标返回
    - 测试无目标时的兜底坐标
    - 测试统计计数器更新
    - _Requirements: 3.6_
  
  - [x]* 7.5 测试统计功能
    - 测试 get_stats() 返回正确信息
    - 测试 reset_stats() 重置计数器
    - _Requirements: 3.7_
  
  - [x]* 7.6 测试工厂函数
    - 测试 enable_can=True 创建真实 CAN
    - 测试 enable_can=False 创建虚拟 CAN
    - 测试返回类型正确
    - _Requirements: 4.1, 4.2_
  
  - [x]* 7.7 测试真实 CAN 兼容性
    - 运行现有 CAN 模块测试套件
    - 确认所有测试通过
    - 确认行为未改变
    - _Requirements: 2.2_

### 阶段 8: 集成测试

- [ ] 8. 集成测试
  - [ ]* 8.1 测试完整数据流（虚拟模式）
    - 启动 DataProcessor
    - 启动虚拟 CAN 通信器
    - 模拟检测到人员
    - 验证 PERSON_WARNING 事件被虚拟 CAN 接收
    - 验证日志输出正确
    - 验证统计信息正确
    - _Requirements: 3.3, 3.4, 3.5_
  
  - [ ]* 8.2 测试坐标请求流程（虚拟模式）
    - 启动 DecisionLayer
    - 启动虚拟 CAN 通信器
    - 调用 simulate_coordinate_request()
    - 验证坐标获取正确
    - 验证日志输出正确
    - _Requirements: 3.6_
  
  - [ ]* 8.3 测试模式切换
    - 使用工厂函数创建虚拟 CAN
    - 验证功能正常
    - 修改配置为 enable_can=True
    - 使用工厂函数创建真实 CAN（如果环境支持）
    - 验证接口一致性
    - _Requirements: 4.1, 4.2_

### 阶段 9: 文档更新

- [ ] 9. 更新文档
  - [ ] 9.1 更新 CAN 模块 README
    - 添加虚拟 CAN 功能说明
    - 添加使用示例（真实模式 vs 虚拟模式）
    - 添加配置说明
    - 添加日志输出示例
    - _Requirements: 6.2_
  
  - [ ] 9.2 更新配置文档
    - 说明 enable_can 字段的作用
    - 说明何时使用虚拟模式
    - 说明何时使用真实模式
    - _Requirements: 5.1, 6.2_
  
  - [ ] 9.3 添加开发指南
    - 说明如何在 Windows 上开发
    - 说明如何使用虚拟 CAN 进行测试
    - 说明如何查看统计信息
    - 说明如何模拟坐标请求
    - _Requirements: 6.2_

### 阶段 10: 验收测试

- [ ] 10. 最终验收
  - [ ] 10.1 Windows 环境验证
    - 在 Windows 环境下启动系统
    - 配置 enable_can=False
    - 验证虚拟 CAN 正常启动
    - 验证事件正常接收和处理
    - 验证日志输出清晰
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ] 10.2 Linux 环境验证（如果可用）
    - 在 Linux 环境下启动系统
    - 配置 enable_can=True
    - 验证真实 CAN 正常启动
    - 验证功能未受影响
    - _Requirements: 2.2_
  
  - [ ] 10.3 代码审查
    - 检查代码风格一致性
    - 检查文档完整性
    - 检查异常处理完备性
    - 检查日志输出规范性
    - _Requirements: 6.1_

## 注意事项

1. **最小改动原则**：现有 `CANCommunicator` 只修改 2 行代码，确保稳定性
2. **向后兼容**：现有代码可以继续直接使用 `CANCommunicator`，不强制使用工厂函数
3. **测试优先**：每个阶段完成后立即测试，确保功能正确
4. **日志清晰**：虚拟模式的日志要清晰说明真实环境下的行为
5. **统计信息**：提供统计功能帮助验证事件流
6. **异常处理**：所有方法都要有完善的异常处理
7. **文档完整**：每个类和方法都要有清晰的文档字符串

## 任务标记说明

- `[ ]`: 未开始
- `[-]`: 进行中
- `[x]`: 已完成
- `[ ]*`: 可选任务（测试相关）
