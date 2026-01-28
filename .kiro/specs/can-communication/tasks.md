# Implementation Plan: CAN Communication Module

## Overview

本实现计划将CAN通信模块的设计转化为可执行的开发任务。采用增量开发方式，优先实现核心通信功能和可在Windows环境运行的测试，将需要Linux环境（socketCAN）的测试任务放在最后。

**测试策略**：
- **Windows环境测试**（优先）：使用mock的单元测试、属性测试，可立即运行验证
- **Linux环境测试**（延后）：需要真实socketCAN的集成测试，创建后不立即运行，留待Linux环境执行

实现顺序：
1. 基础设施（配置DTO、接口配置工具）
2. 协议编解码（硬编码实现）
3. 核心通信（回调监听、坐标响应）
4. 警报功能（事件订阅、定时发送）
5. Windows环境测试（单元测试、属性测试）
6. 日志和错误处理
7. 文档和示例
8. Linux环境测试（集成测试、硬件测试）- **创建后不运行**

## Tasks

### 阶段一：核心功能实现

- [x] 1. 扩展现有CAN配置DTO
  - 基于oak_vision_system/core/dto/config_dto/can_config_dto.py扩展
  - 添加新字段：enable_auto_configure（bool，默认True）
  - 添加新字段：sudo_password（Optional[str]，默认None）
  - 添加新字段：alert_interval_ms（int，默认100）
  - 调整默认值：enable_can改为True，receive_timeout_ms改为10
  - 更新_validate_data()方法，验证新字段（alert_interval_ms > 0）
  - 保留现有字段和验证逻辑（CanFrameMeta、FrameIdConfigDTO等）
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2. 实现CAN接口配置工具
  - [x] 2.1 创建can_interface_config.py模块
    - 实现configure_can_interface()函数
    - 实现reset_can_interface()函数
    - 使用subprocess执行系统命令
    - 智能处理sudo权限（root直接执行，普通用户使用sudo -S）
    - _Requirements: 1.2, 1.3, 1.4, 1.5_

- [-] 3. 实现协议编解码模块
  - [x] 3.1 创建CANProtocol类
    - 定义协议常量（FRAME_ID, MSG_TYPE_REQUEST, MSG_TYPE_RESPONSE, MSG_TYPE_ALERT）
    - 实现identify_message()静态方法
    - 实现encode_coordinate_response()静态方法
    - 实现encode_alert()静态方法
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 4. 实现CANMessageListener监听器
  - [x] 4.1 创建CANMessageListener类
    - 继承can.Listener
    - 实现__init__()方法，保存communicator引用
    - 实现on_message_received()回调方法
    - 添加try-except异常保护
    - 调用identify_message()识别消息类型
    - 根据类型调用对应处理器
    - _Requirements: 4.6, 6.2, 6.3, 6.5_

  - [x] 4.2 实现handle_coordinate_request()方法
    - 调用decision_layer.get_target_coords_snapshot()
    - 处理返回None的情况（发送0,0,0）
    - 处理异常情况（捕获并发送0,0,0）
    - 编码响应帧
    - 发送响应
    - 记录日志（坐标值和时间戳）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 8.2_

- [x] 5. 实现CANCommunicator主管理器
  - [x] 5.1 创建CANCommunicator类基础结构
    - 实现__init__()方法，保存config、decision_layer、event_bus引用
    - 初始化内部状态变量（bus, notifier, listener, alert_timer等）
    - _Requirements: 6.1_

  - [x] 5.2 实现start()方法
    - 检查enable_auto_configure，调用configure_can_interface()
    - 创建can.Bus对象
    - 创建CANMessageListener实例
    - 创建can.Notifier实例
    - 订阅Event_Bus的PERSON_WARNING事件
    - 记录启动日志
    - 处理连接失败异常
    - _Requirements: 1.1, 1.2, 1.6, 3.1, 6.1, 6.2, 6.3, 8.1, 9.1_

  - [x] 5.3 实现stop()方法
    - 停止警报定时器
    - 取消事件订阅
    - 停止Notifier
    - 关闭Bus
    - 检查enable_auto_configure，调用reset_can_interface()
    - 记录停止日志
    - _Requirements: 1.7, 1.8, 1.9, 6.8_

- [x] 6. 实现人员警报功能
  - [x] 6.1 实现_on_person_warning()事件回调
    - 解析event_data获取status
    - 如果status=TRIGGERED，调用_start_alert_timer()
    - 如果status=CLEARED，调用_stop_alert_timer()
    - 记录警报开关日志
    - _Requirements: 3.1, 3.2, 3.5, 8.3, 8.4_

  - [x] 6.2 实现_start_alert_timer()方法
    - 设置_alert_active标志为True
    - 调用_schedule_next_alert()
    - _Requirements: 3.2_

  - [x] 6.3 实现_stop_alert_timer()方法
    - 设置_alert_active标志为False
    - 取消当前定时器（如果存在）
    - _Requirements: 3.5_

  - [x] 6.4 实现_schedule_next_alert()方法
    - 检查_alert_active标志
    - 创建threading.Timer，间隔为alert_interval_ms
    - 设置回调为_send_alert()
    - 启动定时器
    - _Requirements: 3.3, 3.4_

  - [x] 6.5 实现_send_alert()方法
    - 编码警报帧（调用CANProtocol.encode_alert()）
    - 创建can.Message对象
    - 发送消息
    - 记录日志（时间戳）
    - 处理发送异常
    - 调用_schedule_next_alert()实现递归调度
    - _Requirements: 3.3, 9.2_

- [x] 7. 日志和错误处理完善
  - 确保所有关键事件记录日志
  - 确保所有异常情况有错误处理
  - 验证日志级别正确（INFO/ERROR）
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 8. Checkpoint - 核心功能验证
  - 确保所有核心功能代码已实现
  - 验证代码结构和接口定义
  - 如有问题，与用户讨论

### 阶段二：Windows环境测试（可立即运行）

- [ ] 9. 配置DTO单元测试
  - [ ] 9.1 为配置DTO编写单元测试
    - 测试有效配置的验证通过
    - 测试无效配置的验证失败
    - 测试默认值的正确性
    - _Requirements: 7.7_
    - **运行环境：Windows ✅**

- [ ] 10. 协议编解码测试
  - [ ] 10.1 为协议编解码编写单元测试
    - 测试identify_message()识别坐标请求
    - 测试identify_message()对无效消息返回None
    - 测试encode_coordinate_response()的格式正确性
    - 测试encode_alert()的格式正确性
    - _Requirements: 4.2, 4.3, 4.4, 5.2, 5.3_
    - **运行环境：Windows ✅**

  - [ ] 10.2 为协议编解码编写属性测试
    - **Property 1: 消息识别正确性**
    - **Validates: Requirements 4.2, 4.3, 4.4**
    - 使用Hypothesis生成随机CAN消息
    - 验证识别逻辑的正确性
    - **运行环境：Windows ✅**

  - [ ] 10.3 为坐标编码编写属性测试
    - **Property 2: 坐标编码round-trip**
    - **Validates: Requirements 5.5**
    - 使用Hypothesis生成随机坐标
    - 验证编码后解码得到相同值
    - **运行环境：Windows ✅**

  - [ ] 10.4 为坐标响应格式编写属性测试
    - **Property 6: 坐标响应编码格式**
    - **Validates: Requirements 2.5**
    - 使用Hypothesis生成随机坐标
    - 验证编码格式符合协议规范
    - **运行环境：Windows ✅**

- [ ] 11. 监听器和管理器单元测试（使用mock）
  - [ ] 11.1 为监听器编写单元测试
    - 测试on_message_received()正确识别消息
    - 测试handle_coordinate_request()调用决策层
    - 测试决策层返回None时的兜底逻辑
    - 测试决策层抛异常时的兜底逻辑
    - 测试异常不导致回调崩溃
    - 使用mock Decision_Layer和Bus
    - _Requirements: 2.2, 2.3, 2.4, 6.5, 9.3_
    - **运行环境：Windows ✅（使用mock）**

  - [ ] 11.2 为CANCommunicator生命周期编写单元测试
    - 测试start()成功初始化所有组件
    - 测试start()在连接失败时返回False
    - 测试stop()正确清理资源
    - 测试stop()的调用顺序（定时器→事件→Notifier→Bus→接口）
    - 使用mock can.Bus和can.Notifier
    - _Requirements: 1.1, 1.7, 6.8, 9.1_
    - **运行环境：Windows ✅（使用mock）**

  - [ ] 11.3 为警报功能编写单元测试
    - 测试_on_person_warning()正确处理TRIGGERED事件
    - 测试_on_person_warning()正确处理CLEARED事件
    - 测试_start_alert_timer()启动定时器
    - 测试_stop_alert_timer()取消定时器
    - 测试_send_alert()发送警报帧
    - 使用mock threading.Timer和Bus
    - _Requirements: 3.1, 3.2, 3.5_
    - **运行环境：Windows ✅（使用mock）**

- [ ] 12. 配置相关属性测试
  - [ ] 12.1 配置加载正确性属性测试
    - **Property 3: 配置加载正确性**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    - 使用Hypothesis生成随机配置
    - 验证加载后内部状态一致
    - **运行环境：Windows ✅**

  - [ ] 12.2 自动配置条件触发属性测试
    - **Property 4: 自动配置条件触发**
    - **Validates: Requirements 1.2, 1.6**
    - 使用Hypothesis生成随机配置和系统环境
    - 验证自动配置按条件触发
    - 使用mock subprocess
    - **运行环境：Windows ✅（使用mock）**

  - [ ] 12.3 接口重置条件触发属性测试
    - **Property 5: 接口重置条件触发**
    - **Validates: Requirements 1.8, 1.9**
    - 使用Hypothesis生成随机配置
    - 验证接口重置按条件触发
    - 使用mock subprocess
    - **运行环境：Windows ✅（使用mock）**

- [ ] 13. Checkpoint - Windows环境测试验证
  - 运行所有Windows环境可运行的测试
  - 检查测试覆盖率（目标≥85%）
  - 确保所有单元测试和属性测试通过
  - 与用户确认测试结果

### 阶段三：文档和示例

- [ ] 14. 文档和示例
  - 编写模块使用文档
  - 创建简单示例（examples/can_communication_example.py）
  - 更新README说明CAN模块的使用方法

### 阶段四：Linux环境测试（创建后不运行，留待Linux环境执行）

- [ ] 15. 接口配置工具测试 **[Linux环境 - 创建后不运行]**
  - [ ] 15.1 为接口配置工具编写单元测试
    - 测试Linux系统下的配置命令构造
    - 测试sudo权限处理逻辑
    - 测试命令执行成功和失败的情况
    - 使用mock subprocess避免实际执行命令
    - _Requirements: 1.4, 1.5_
    - **运行环境：Linux（香橙派）⚠️**
    - **注意：此测试创建后不立即运行，留待Linux环境执行**

- [ ] 16. 集成测试 **[Linux环境 - 创建后不运行]**
  - [ ] 16.1 端到端坐标请求响应测试
    - 模拟外部控制器发送请求
    - 验证CAN模块调用决策层
    - 验证响应帧格式正确
    - _Requirements: 2.1, 2.2, 2.3, 2.5_
    - **运行环境：Linux（香橙派）+ socketCAN ⚠️**
    - **注意：此测试创建后不立即运行，需要真实CAN环境或虚拟CAN（vcan）**

  - [ ] 16.2 人员警报流程测试
    - 模拟决策层发布TRIGGERED事件
    - 验证警报定时器启动
    - 验证警报帧周期发送
    - 模拟CLEARED事件
    - 验证警报停止
    - _Requirements: 3.1, 3.2, 3.3, 3.5_
    - **运行环境：Linux（香橙派）+ socketCAN ⚠️**
    - **注意：此测试创建后不立即运行，需要真实CAN环境或虚拟CAN（vcan）**

  - [ ] 16.3 接口配置流程测试
    - 验证自动配置成功
    - 验证总线连接成功
    - 验证停止时重置接口
    - _Requirements: 1.2, 1.8_
    - **运行环境：Linux（香橙派）+ 真实CAN硬件 ⚠️**
    - **注意：此测试创建后不立即运行，必须在Linux环境下运行，涉及系统命令**

- [ ] 17. 端到端测试（使用can_controller.py + socketCAN loopback）**[Linux环境 - 创建后不运行]**
  - [ ] 17.1 创建端到端测试脚本
    - 编写tests/integration/test_can_end_to_end.py测试脚本
    - 使用subprocess启动plan/modules/CAN_module/pre_inpimentation/can_controller.py作为独立进程
    - 利用socketCAN的loopback机制实现进程间通信（两个进程共享can0接口）
    - 在当前pytest进程中启动CAN通信模块（使用mock决策层和事件总线）
    - 通过subprocess.stdin向can_controller发送命令（'r'=单次请求, 'c'=连续请求, 'q'=退出）
    - 通过subprocess.stdout/stderr读取can_controller的输出进行验证
    - 实现输出解析函数，提取坐标值、警报计数、统计信息
    - _Requirements: 所有需求的端到端验证_
    - **运行环境：Linux（香橙派）+ socketCAN ⚠️**
    - **关键机制：socketCAN loopback - 进程1发送的消息，进程1和进程2都能收到**
    - **注意：此测试创建后不立即运行，需要真实socketCAN环境（can0）**

  - [ ] 17.2 坐标请求响应测试
    - 启动can_controller.py进程（模拟外部控制器）
    - 在当前进程启动CAN通信模块（被测试对象）
    - Mock决策层返回测试坐标（如100, 200, 300）
    - 通过stdin发送'r\n'命令触发单次坐标请求
    - can_controller通过can0发送请求帧（0x22）
    - CAN通信模块从can0收到请求，调用mock决策层获取坐标
    - CAN通信模块通过can0发送响应帧（0x08 + 坐标）
    - can_controller从can0收到响应，解析坐标
    - 解析can_controller的stdout输出，验证坐标值正确（小端序、补码）
    - 记录时间戳，验证响应时间< 10ms
    - 测试连续请求：发送10次'r\n'命令，验证10次响应都正确
    - 测试边界值：Mock决策层返回(-32768, 0, 32767)，验证补码编解码
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
    - **运行环境：Linux（香橙派）+ socketCAN ⚠️**

  - [ ] 17.3 人员警报测试
    - 启动can_controller.py进程
    - 在当前进程启动CAN通信模块
    - Mock事件总线发布PERSON_WARNING(TRIGGERED)事件
    - CAN通信模块启动警报定时器，周期通过can0发送警报帧（0x33）
    - can_controller从can0收到警报，增加alert_count计数
    - 解析can_controller的stdout输出，验证收到警报消息
    - 持续监控1秒，记录警报计数和时间戳
    - 验证警报间隔为100ms±10ms（通过时间戳计算）
    - Mock事件总线发布PERSON_WARNING(CLEARED)事件
    - CAN通信模块停止警报定时器
    - 等待300ms，验证can_controller的alert_count不再增加
    - 通过stdin发送's\n'命令，读取统计信息，验证警报已停止
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
    - **运行环境：Linux（香橙派）+ socketCAN ⚠️**

  - [ ] 17.4 协议兼容性和性能测试
    - 测试负数坐标补码编解码：Mock决策层返回(-100, -200, -300)，验证解析正确
    - 测试边界值坐标：分别测试(32767, 32767, 32767)和(-32768, -32768, -32768)
    - 测试混合边界值：(32767, -32768, 0)
    - 测试连续快速请求：通过stdin发送'c\n'启动连续请求模式
    - 等待1秒（can_controller每2秒发送一次，应收到约0.5次响应）
    - 通过stdin发送'c\n'停止连续请求模式
    - 通过stdin发送's\n'读取统计信息
    - 解析统计输出，验证请求数=响应数（无消息丢失）
    - 验证协议格式：所有响应帧的Byte0=0x08, Byte1=0x00
    - 验证小端序：手动解析响应帧字节，确认与坐标值匹配
    - _Requirements: 5.5, 10.6_
    - **运行环境：Linux（香橙派）+ socketCAN ⚠️**

- [ ] 18. 硬件测试 **[Linux环境 - 创建后不运行]**
  - 在香橙派上进行实际硬件测试
  - 验证与外部控制器的真实通信
  - 验证坐标请求响应的完整流程
  - 验证人员警报的实时发送
  - **运行环境：Linux（香橙派）+ 真实CAN硬件 + 外部控制器 ⚠️**
  - **注意：此测试创建后不立即运行，需要完整的硬件环境**

- [ ] 18. Final Checkpoint - 完整性验证
  - 确认所有代码已实现
  - 确认Windows环境测试全部通过
  - 确认Linux环境测试已创建（但未运行）
  - 与用户确认功能完整性
  - 提供Linux环境测试的运行指南

## Notes

**测试分类说明**：

**✅ Windows环境可运行（任务9-13）**：
- 配置DTO测试
- 协议编解码测试（单元测试 + 属性测试）
- 监听器和管理器单元测试（使用mock）
- 配置相关属性测试（使用mock）
- **这些测试创建后会立即运行验证**

**⚠️ Linux环境测试（任务15-17）**：
- 接口配置工具测试（涉及subprocess和系统命令）
- 集成测试（需要socketCAN）
- 硬件测试（需要真实CAN硬件）
- **这些测试创建后不会立即运行，留待Linux环境（香橙派）执行**

**开发策略**：
1. 在Windows环境下完成所有核心功能实现
2. 运行Windows环境可运行的测试，确保代码质量
3. 创建Linux环境测试代码，但不运行
4. 在Linux环境（香橙派）下运行Linux环境测试

**Mock策略**：
- 使用`unittest.mock`模拟`can.Bus`、`can.Notifier`、`subprocess`等
- Windows环境测试不依赖真实CAN硬件
- Linux环境测试使用真实socketCAN或虚拟CAN（vcan）

**每个任务都引用了对应的需求编号，确保可追溯性**
