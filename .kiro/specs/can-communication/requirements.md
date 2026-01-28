# Requirements Document

## Introduction

CAN通信模块是OAK视觉系统与外部控制器（如单片机）之间的通信桥梁。该模块专注于纯通信职责，负责CAN总线的数据收发和协议编解码，不承担任何业务逻辑（如坐标计算、决策判断等）。

模块通过监听CAN总线接收外部请求，调用决策层的同步接口获取数据，并按照协议规范编码发送响应。同时,模块订阅决策层发布的人员警报事件，按固定频率向外部系统发送警报信号。

**跨平台支持**：模块通过`enable_auto_configure`配置标志位控制CAN接口的自动配置行为。在Linux环境（如香橙派）下可启用自动配置以简化部署；在Windows等开发环境下可禁用自动配置，使用虚拟CAN或手动配置的接口进行开发测试。完整的功能测试和验证建议在目标硬件平台（香橙派）上进行。

## Glossary

- **CAN_Module**: CAN通信模块，负责CAN总线的数据收发
- **CAN_Interface_Config**: CAN接口配置工具模块，提供接口配置和重置函数
- **CANMessageListener**: CAN消息监听器类，实现回调接口
- **Notifier**: python-can库提供的消息通知器，管理监听线程
- **Decision_Layer**: 决策层模块，提供目标坐标和人员警报事件
- **External_Controller**: 外部控制器（如单片机），通过CAN总线与系统通信
- **Event_Bus**: 事件总线，用于模块间解耦通信
- **Coordinate_Request**: 外部控制器发送的坐标请求帧（0x22）
- **Coordinate_Response**: 系统响应的坐标数据帧（0x08）
- **Alert_Frame**: 人员警报帧（0x33）
- **Frame_ID**: CAN帧标识符，本协议使用0x30
- **Little_Endian**: 小端序字节序，低位字节在前

## Requirements

### Requirement 1: CAN总线连接管理

**User Story:** 作为系统管理员，我希望CAN模块能够自动配置和管理CAN接口，以便系统能够稳定地与外部控制器通信。

#### Acceptance Criteria

1. WHEN 系统启动时，THE CAN_Module SHALL 根据配置初始化CAN接口（socketcan, can0, 250000波特率）
2. WHERE 配置中enable_auto_configure=True且运行在Linux系统，THE CAN_Module SHALL 调用独立的接口配置工具函数自动配置CAN接口
3. THE CAN_Module SHALL 使用独立的can_interface_config脚本模块，该模块导出configure_can_interface()和reset_can_interface()函数
4. THE configure_can_interface()函数 SHALL 使用subprocess模块执行系统命令完成接口配置（关闭接口、加载内核模块、设置波特率、启用接口、验证状态）
5. THE configure_can_interface()函数 SHALL 智能处理sudo权限（root直接执行，普通用户使用sudo -S传递密码）
6. WHERE 配置中enable_auto_configure=False或运行在非Linux系统，THE CAN_Module SHALL 跳过自动配置并假设接口已手动配置
7. WHEN 系统关闭时，THE CAN_Module SHALL 优雅地关闭CAN总线连接
8. WHERE 启用auto_configure，THE CAN_Module SHALL 调用reset_can_interface()函数重置CAN接口状态
9. WHERE 禁用auto_configure，THE CAN_Module SHALL 在关闭时仅关闭总线连接而不修改接口状态

### Requirement 2: 坐标请求响应

**User Story:** 作为外部控制器，我希望通过CAN总线请求目标坐标，以便控制机械臂进行抓取操作。

#### Acceptance Criteria

1. WHEN External_Controller 发送坐标请求帧（帧ID=0x30，8字节全为0x22），THE CAN_Module SHALL 识别该请求
2. WHEN 收到坐标请求，THE CAN_Module SHALL 调用Decision_Layer的get_target_coords_snapshot()同步接口获取目标坐标
3. WHEN Decision_Layer返回有效坐标（numpy数组，形状(3,)，单位毫米），THE CAN_Module SHALL 将坐标转换为整数并编码为响应帧
4. WHEN Decision_Layer返回None或抛出异常，THE CAN_Module SHALL 发送默认坐标(0, 0, 0)作为兜底响应
5. THE CAN_Module SHALL 按照协议规范编码响应帧：Byte0=0x08，Byte1=0x00（预留），Byte2-7为xyz坐标的小端序表示（每个坐标2字节）
6. THE CAN_Module SHALL 在10ms内完成从接收请求到发送响应的全过程

### Requirement 3: 人员警报发送

**User Story:** 作为安全监控系统，我希望在检测到人员危险时通过CAN总线通知外部控制器，以便及时停止机械臂动作。

#### Acceptance Criteria

1. THE CAN_Module SHALL 订阅Event_Bus的PERSON_WARNING事件
2. WHEN 收到status=TRIGGERED的PERSON_WARNING事件，THE CAN_Module SHALL 启动警报定时器（threading.Timer）
3. THE 警报定时器 SHALL 每隔100ms调用一次发送函数，发送警报帧（帧ID=0x30，8字节全为0x33）
4. THE 警报定时器 SHALL 使用递归调度方式实现周期发送（每次发送后调度下一次）
5. WHEN 收到status=CLEARED的PERSON_WARNING事件，THE CAN_Module SHALL 取消警报定时器并停止发送警报帧
6. THE CAN_Module SHALL 确保警报发送间隔的误差在±10ms以内
7. THE 事件回调函数 SHALL 在事件总线的线程中执行，仅负责启动/停止定时器，不阻塞事件总线

### Requirement 4: 消息识别与路由

**User Story:** 作为开发人员，我希望CAN模块能够准确识别不同类型的消息并路由到对应的处理器，以便系统能够正确响应各种CAN通信请求。

#### Acceptance Criteria

1. THE CAN_Module SHALL 提供消息识别器函数identify_message()，用于识别接收到的CAN消息类型
2. THE identify_message()函数 SHALL 首先验证帧ID是否为0x30，数据长度是否为8字节
3. THE identify_message()函数 SHALL 根据数据内容特征识别消息类型：8字节全为0x22识别为"coordinate_request"
4. THE identify_message()函数 SHALL 对于无法识别的消息返回None
5. THE CAN_Module SHALL 使用字典映射消息类型名称到对应的处理器函数
6. WHEN 收到CAN消息时，THE CAN_Module SHALL 调用identify_message()识别类型，然后查找字典调用对应处理器
7. THE CAN_Module SHALL 支持通过修改识别器和添加字典条目的方式扩展新的消息类型

### Requirement 5: 协议编解码

**User Story:** 作为开发人员，我希望协议编解码逻辑清晰且易于维护，以便后续修改和扩展通信协议。

#### Acceptance Criteria

1. THE CAN_Module SHALL 使用硬编码方式实现协议编解码逻辑
2. THE CAN_Module SHALL 提供encode_coordinate_response()函数，编码坐标响应帧（Byte0=0x08，Byte1=0x00，Byte2-7为xyz坐标的小端序表示）
3. THE CAN_Module SHALL 提供encode_alert()函数，编码警报帧（8字节全为0x33）
4. THE CAN_Module SHALL 将所有协议常量（帧ID、消息类型字节）定义为类常量，易于查阅和修改
5. THE CAN_Module SHALL 确保编码函数使用struct.pack()进行小端序打包，格式字符串为'<Bxhhh'（坐标响应）

### Requirement 6: 回调监听与并发

**User Story:** 作为系统架构师，我希望CAN模块使用事件驱动的回调机制监听CAN总线，以降低CPU占用并提高响应速度。

#### Acceptance Criteria

1. THE CAN_Module SHALL 使用python-can的Notifier和Listener机制实现回调监听
2. THE CAN_Module SHALL 创建CANMessageListener类，实现on_message_received()回调方法
3. WHEN CAN消息到达时，THE Notifier SHALL 自动调用on_message_received()回调（在python-can内部线程执行）
4. THE CAN_Module SHALL NOT 创建独立的监听线程，监听线程由python-can的Notifier自动管理
5. THE on_message_received()回调 SHALL 包含try-except异常保护，防止回调异常导致Notifier线程崩溃
6. THE CAN_Module SHALL 确保回调函数执行时间短（< 1ms），避免阻塞后续消息接收
7. THE CAN_Module SHALL 确保与Decision_Layer的同步接口调用是线程安全的（Decision_Layer已提供线程锁保护）
8. THE CAN_Module SHALL 提供优雅的启动和停止机制：启动时创建Notifier，停止时先stop Notifier再shutdown Bus

### Requirement 7: 配置管理

**User Story:** 作为系统配置员，我希望能够通过配置文件灵活调整CAN通信参数，以适应不同的硬件环境和通信需求。

#### Acceptance Criteria

1. THE CAN_Module SHALL 从CANConfigDTO加载所有配置参数
2. THE CAN_Module SHALL 支持配置CAN接口类型、通道名称、波特率
3. THE CAN_Module SHALL 支持配置发送超时、接收超时
4. THE CAN_Module SHALL 支持配置警报发送间隔（默认100ms）
5. THE CAN_Module SHALL 支持配置enable_auto_configure标志位（默认True），控制是否自动配置CAN接口
6. THE CAN_Module SHALL 支持配置sudo密码（用于Linux系统的自动配置）
7. THE CAN_Module SHALL 在配置参数无效时使用合理的默认值并记录警告日志
8. THE CAN_Module SHALL 在Windows等非Linux系统上自动禁用接口自动配置功能

### Requirement 8: 日志记录

**User Story:** 作为系统维护人员，我希望能够通过日志了解CAN通信的关键事件，以便排查问题和监控系统状态。

#### Acceptance Criteria

1. WHEN 启动CAN模块时，THE CAN_Module SHALL 记录接口配置信息（通道、波特率、配置状态）
2. WHEN 收到坐标请求并发送响应时，THE CAN_Module SHALL 记录发送的坐标值和时间戳
3. WHEN 启动警报定时器时，THE CAN_Module SHALL 记录"警报已启动"和时间戳
4. WHEN 停止警报定时器时，THE CAN_Module SHALL 记录"警报已停止"和时间戳
5. WHEN 发生CAN通信错误时，THE CAN_Module SHALL 记录错误类型和详细信息
6. THE CAN_Module SHALL 使用INFO级别记录正常通信事件，使用ERROR级别记录异常事件

### Requirement 9: 错误处理与容错

**User Story:** 作为系统运维人员，我希望CAN模块能够优雅地处理各种异常情况，以提高系统的稳定性和可靠性。

#### Acceptance Criteria

1. WHEN CAN总线连接失败时，THE CAN_Module SHALL 记录错误并返回初始化失败状态
2. WHEN 发送CAN消息超时时，THE CAN_Module SHALL 记录警告并继续运行
3. WHEN Decision_Layer的同步接口抛出异常时，THE CAN_Module SHALL 捕获异常并发送默认坐标(0, 0, 0)
4. WHEN CAN总线在运行中断开时，THE CAN_Module SHALL 记录错误并尝试优雅退出监听循环
5. IF 接口配置失败，THEN THE CAN_Module SHALL 记录详细错误信息并允许用户手动配置接口

### Requirement 10: 性能要求

**User Story:** 作为系统性能工程师，我希望CAN模块能够满足实时通信的性能要求，以确保系统响应及时。

#### Acceptance Criteria

1. THE CAN_Module SHALL 在收到坐标请求后10ms内完成响应发送
2. THE CAN_Module SHALL 确保警报帧发送间隔的精度在±10ms以内
3. THE CAN_Module SHALL 确保调用Decision_Layer同步接口的耗时不超过1ms（包含锁等待）
4. THE CAN_Module SHALL 确保回调函数on_message_received()的执行时间不超过1ms，避免阻塞后续消息
5. THE CAN_Module SHALL 在无消息时CPU占用率接近0%（得益于回调机制）
6. THE CAN_Module SHALL 支持每秒至少处理100次坐标请求而不丢失消息
