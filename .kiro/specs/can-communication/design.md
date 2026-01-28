# Design Document

## Overview

CAN通信模块采用事件驱动的回调架构，实现OAK视觉系统与外部控制器之间的高效通信。模块专注于纯通信职责，通过python-can库的Notifier/Listener机制监听CAN总线，调用决策层的同步接口获取数据，并按照协议规范编码发送响应。

核心设计特点：
- **事件驱动回调**：使用python-can的Notifier自动管理监听线程，消息到达时触发回调
- **零CPU空转**：无消息时CPU占用接近0%，响应延迟< 1ms
- **纯通信职责**：不承担业务逻辑，仅负责协议编解码和数据收发
- **线程安全**：回调在python-can内部线程执行，与决策层的同步接口线程安全交互
- **模块解耦**：通过事件总线订阅人员警报，通过同步接口获取坐标

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      OAK Vision System                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ Decision     │         │  Event Bus   │                 │
│  │ Layer        │         │              │                 │
│  └──────┬───────┘         └──────┬───────┘                 │
│         │                        │                          │
│         │ get_target_coords()    │ PERSON_WARNING          │
│         │ (sync call)            │ (subscribe)             │
│         │                        │                          │
│  ┌──────▼────────────────────────▼───────┐                 │
│  │      CAN Communicator                 │                 │
│  │  ┌─────────────────────────────────┐  │                 │
│  │  │  CANMessageListener (Callback)  │  │                 │
│  │  │  - on_message_received()        │  │                 │
│  │  └─────────────────────────────────┘  │                 │
│  │  ┌─────────────────────────────────┐  │                 │
│  │  │  Alert Timer (threading.Timer)  │  │                 │
│  │  │  - Recursive scheduling         │  │                 │
│  │  └─────────────────────────────────┘  │                 │
│  └──────────────┬────────────────────────┘                 │
│                 │                                            │
└─────────────────┼────────────────────────────────────────────┘
                  │
                  │ python-can Bus
                  │
         ┌────────▼────────┐
         │  Notifier       │  (python-can internal thread)
         │  - Auto manage  │
         │  - Event driven │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │   CAN Bus       │
         │   (socketcan)   │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │  External       │
         │  Controller     │
         └─────────────────┘
```

### 线程模型

```
Main Thread
  └─ CANCommunicator.start()
      ├─ Configure CAN interface (if enabled)
      ├─ Create Bus object
      ├─ Create Notifier (spawns internal thread)
      └─ Subscribe to Event Bus

python-can Internal Thread (Notifier)
  └─ Listen CAN bus
      └─ on_message_received() callback
          ├─ Identify message type
          ├─ Call decision_layer.get_target_coords_snapshot()
          └─ Send response

Event Bus Thread
  └─ Publish PERSON_WARNING event
      └─ _on_person_warning() callback
          ├─ Start alert timer (if TRIGGERED)
          └─ Stop alert timer (if CLEARED)

Alert Timer Thread (按需创建)
  └─ _send_alert()
      ├─ Send 0x33 alert frame
      └─ Schedule next alert (recursive)
```

## Components and Interfaces

### 1. CANCommunicator (主通信管理器)

**职责**：
- 管理CAN总线连接生命周期
- 协调Notifier、Listener、定时器
- 订阅事件总线，处理人员警报
- 提供统一的对外接口

**接口**：
```python
class CANCommunicator:
    def __init__(
        self,
        config: CANConfigDTO,
        decision_layer: DecisionLayer,
        event_bus: EventBus
    ):
        """初始化CAN通信管理器"""
        
    def start(self) -> bool:
        """
        启动CAN通信
        
        Returns:
            bool: 启动成功返回True，失败返回False
        """
        
    def stop(self):
        """停止CAN通信，清理资源"""
        
    def handle_coordinate_request(self):
        """处理坐标请求（由Listener回调调用）"""
        
    def _on_person_warning(self, event_data: dict):
        """处理人员警报事件（事件总线回调）"""
        
    def _start_alert_timer(self):
        """启动警报定时器"""
        
    def _stop_alert_timer(self):
        """停止警报定时器"""
        
    def _send_alert(self):
        """发送警报帧（定时器回调）"""
```

### 2. CANMessageListener (消息监听器)

**职责**：
- 实现python-can的Listener接口
- 在消息到达时触发回调
- 识别消息类型并路由到处理器
- 异常保护，防止回调崩溃

**接口**：
```python
class CANMessageListener(can.Listener):
    def __init__(self, communicator: CANCommunicator):
        """初始化监听器"""
        
    def on_message_received(self, msg: can.Message):
        """
        消息到达时的回调（python-can内部线程调用）
        
        Args:
            msg: 接收到的CAN消息
        """
```

### 3. CANProtocol (协议编解码)

**职责**：
- 定义协议常量
- 提供消息识别函数
- 提供编码函数（硬编码实现）

**接口**：
```python
class CANProtocol:
    # 协议常量
    FRAME_ID = 0x30
    MSG_TYPE_REQUEST = 0x22
    MSG_TYPE_RESPONSE = 0x08
    MSG_TYPE_ALERT = 0x33
    
    @staticmethod
    def identify_message(msg: can.Message) -> Optional[str]:
        """
        识别CAN消息类型
        
        Args:
            msg: CAN消息对象
            
        Returns:
            消息类型字符串（如"coordinate_request"）或None
        """
        
    @staticmethod
    def encode_coordinate_response(x: int, y: int, z: int) -> bytes:
        """
        编码坐标响应帧
        
        Args:
            x, y, z: 坐标值（毫米，整数）
            
        Returns:
            8字节CAN数据（小端序）
        """
        
    @staticmethod
    def encode_alert() -> bytes:
        """
        编码警报帧
        
        Returns:
            8字节CAN数据（全为0x33）
        """
```

### 4. CAN Interface Config (接口配置工具)

**职责**：
- 独立的接口配置脚本模块
- 使用subprocess执行系统命令
- 智能处理sudo权限

**接口**：
```python
def configure_can_interface(
    channel: str,
    bitrate: int,
    sudo_password: Optional[str] = None
) -> bool:
    """
    配置CAN接口
    
    Args:
        channel: CAN通道名称（如'can0'）
        bitrate: 波特率（如250000）
        sudo_password: sudo密码（可选）
        
    Returns:
        配置成功返回True，失败返回False
    """
    
def reset_can_interface(
    channel: str,
    sudo_password: Optional[str] = None
) -> bool:
    """
    重置CAN接口
    
    Args:
        channel: CAN通道名称
        sudo_password: sudo密码（可选）
        
    Returns:
        重置成功返回True，失败返回False
    """
```

## Data Models

### CANConfigDTO

```python
@dataclass(frozen=True)
class CANConfigDTO(BaseConfigDTO):
    """CAN通信配置"""
    
    # 基础配置
    enable_can: bool = True
    can_interface: str = "socketcan"
    can_channel: str = "can0"
    can_bitrate: int = 250000
    
    # 超时配置
    send_timeout_ms: int = 100
    receive_timeout_ms: int = 10
    
    # 接口管理
    enable_auto_configure: bool = True
    sudo_password: Optional[str] = None
    
    # 警报配置
    alert_interval_ms: int = 100
    
    # 帧ID配置（可选，用于文档化）
    frame_ids: Optional[FrameIdConfigDTO] = None
    
    def validate(self) -> bool:
        """验证配置参数"""
        errors = []
        
        # 验证波特率
        valid_bitrates = [125000, 250000, 500000, 1000000]
        if self.can_bitrate not in valid_bitrates:
            errors.append(f"Invalid bitrate: {self.can_bitrate}")
        
        # 验证超时
        if self.send_timeout_ms <= 0:
            errors.append("send_timeout_ms must be positive")
        
        # 验证警报间隔
        if self.alert_interval_ms <= 0:
            errors.append("alert_interval_ms must be positive")
        
        if errors:
            self.validation_errors = errors
            return False
        return True
```

### CanFrameMeta

```python
@dataclass(frozen=True)
class CanFrameMeta(BaseDTO):
    """CAN帧元信息"""
    
    frame_id: int  # 帧ID（十进制）
    is_extended: bool = False  # 是否为扩展帧
    comment: str = ""  # 用途说明
    
    def validate(self) -> bool:
        """验证帧元信息"""
        errors = []
        
        # 验证帧ID范围
        if self.is_extended:
            if not (0 <= self.frame_id <= 0x1FFFFFFF):
                errors.append(f"Extended frame ID out of range: {self.frame_id}")
        else:
            if not (0 <= self.frame_id <= 0x7FF):
                errors.append(f"Standard frame ID out of range: {self.frame_id}")
        
        # 验证备注长度
        if len(self.comment) > 200:
            errors.append("Comment too long (max 200 chars)")
        
        if errors:
            self.validation_errors = errors
            return False
        return True
```

### FrameIdConfigDTO

```python
@dataclass(frozen=True)
class FrameIdConfigDTO(BaseDTO):
    """帧ID配置"""
    
    frames: Dict[str, CanFrameMeta] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """验证帧ID配置"""
        errors = []
        
        # 验证每个帧元信息
        for name, meta in self.frames.items():
            if not meta.validate():
                errors.extend([f"{name}: {e}" for e in meta.validation_errors])
        
        # 验证帧ID唯一性
        frame_ids = [meta.frame_id for meta in self.frames.values()]
        if len(frame_ids) != len(set(frame_ids)):
            errors.append("Duplicate frame IDs detected")
        
        if errors:
            self.validation_errors = errors
            return False
        return True
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: 消息识别正确性
*For any* CAN消息，如果帧ID为0x30且数据长度为8字节且全为0x22，则identify_message()应返回"coordinate_request"；否则应返回None或其他类型。

**Validates: Requirements 4.2, 4.3, 4.4**

### Property 2: 坐标编码round-trip
*For any* 有效坐标三元组(x, y, z)，编码后再解码应得到相同的坐标值（在整数范围内）。

**Validates: Requirements 5.5**

### Property 3: 配置加载正确性
*For any* 有效的CANConfigDTO，加载配置后CAN模块的内部状态应与配置参数一致。

**Validates: Requirements 7.1, 7.2, 7.3, 7.4**

### Property 4: 自动配置条件触发
*For any* 配置，当enable_auto_configure=True且运行在Linux系统时，应调用configure_can_interface()；否则不应调用。

**Validates: Requirements 1.2, 1.6**

### Property 5: 接口重置条件触发
*For any* 配置，当enable_auto_configure=True时，stop()应调用reset_can_interface()；否则不应调用。

**Validates: Requirements 1.8, 1.9**

### Property 6: 坐标响应编码格式
*For any* 坐标三元组(x, y, z)，encode_coordinate_response()应返回8字节数据，其中Byte0=0x08，Byte1=0x00，Byte2-7为xyz的小端序表示。

**Validates: Requirements 2.5**

## Error Handling

### 1. CAN总线连接失败
```python
try:
    self.bus = can.Bus(...)
except can.CanError as e:
    logger.error(f"CAN总线连接失败: {e}")
    return False
```

### 2. 决策层接口异常
```python
try:
    coords = self.decision_layer.get_target_coords_snapshot()
except Exception as e:
    logger.error(f"获取坐标失败: {e}")
    coords = None  # 触发兜底逻辑

# 兜底：发送(0, 0, 0)
if coords is None:
    data = CANProtocol.encode_coordinate_response(0, 0, 0)
```

### 3. 回调异常保护
```python
def on_message_received(self, msg: can.Message):
    try:
        # 处理逻辑
        msg_type = CANProtocol.identify_message(msg)
        if msg_type == "coordinate_request":
            self.communicator.handle_coordinate_request()
    except Exception as e:
        logger.error(f"CAN消息处理异常: {e}")
        # 不抛出异常，避免Notifier线程崩溃
```

### 4. 发送超时
```python
try:
    self.bus.send(msg, timeout=self.config.send_timeout_ms / 1000.0)
except can.CanError as e:
    logger.warning(f"CAN消息发送超时: {e}")
    # 继续运行，不中断
```

### 5. 接口配置失败
```python
if self.config.enable_auto_configure:
    success = configure_can_interface(...)
    if not success:
        logger.error("CAN接口配置失败，请手动配置")
        # 继续尝试连接总线
```

## Testing Strategy

### 单元测试与属性测试的互补关系

本项目采用**双重测试策略**：
- **单元测试**：验证具体示例、边界情况和错误处理
- **属性测试**：验证通用规则在大量随机输入下的正确性

两者互补，共同保证代码质量：
- 单元测试捕获具体的已知bug
- 属性测试发现未预料到的边界情况

### 单元测试策略

**测试范围**：
1. **初始化和生命周期**
   - 测试start()成功初始化所有组件
   - 测试stop()正确清理资源
   - 测试配置加载和验证

2. **消息处理**
   - 测试坐标请求的识别和响应
   - 测试决策层返回None时的兜底逻辑
   - 测试决策层抛异常时的兜底逻辑

3. **事件订阅**
   - 测试PERSON_WARNING事件的订阅
   - 测试TRIGGERED事件启动定时器
   - 测试CLEARED事件停止定时器

4. **错误处理**
   - 测试CAN总线连接失败
   - 测试回调异常不导致崩溃
   - 测试发送超时的处理

5. **日志记录**
   - 测试关键事件是否记录日志
   - 测试日志级别是否正确

**测试工具**：
- pytest作为测试框架
- unittest.mock用于mock外部依赖
- pytest-cov用于代码覆盖率

### 属性测试策略

**测试库**：使用Hypothesis进行属性测试

**测试配置**：
- 每个属性测试运行**最少100次**迭代
- 使用`@given`装饰器生成随机输入
- 使用`@settings(max_examples=100)`配置迭代次数

**属性测试用例**：

#### 1. 消息识别正确性
```python
@given(
    frame_id=st.integers(min_value=0, max_value=0x7FF),
    data=st.binary(min_size=8, max_size=8)
)
@settings(max_examples=100)
def test_message_identification_property(frame_id, data):
    """
    Feature: can-communication, Property 1: 消息识别正确性
    
    For any CAN消息，识别逻辑应正确判断消息类型
    """
    msg = can.Message(arbitration_id=frame_id, data=data)
    result = CANProtocol.identify_message(msg)
    
    # 验证识别逻辑
    if frame_id == 0x30 and len(data) == 8 and all(b == 0x22 for b in data):
        assert result == "coordinate_request"
    else:
        assert result is None or result != "coordinate_request"
```

#### 2. 坐标编码round-trip
```python
@given(
    x=st.integers(min_value=-32768, max_value=32767),
    y=st.integers(min_value=-32768, max_value=32767),
    z=st.integers(min_value=-32768, max_value=32767)
)
@settings(max_examples=100)
def test_coordinate_encoding_roundtrip(x, y, z):
    """
    Feature: can-communication, Property 2: 坐标编码round-trip
    
    For any 有效坐标，编码后解码应得到相同值
    """
    # 编码
    data = CANProtocol.encode_coordinate_response(x, y, z)
    
    # 解码
    decoded = struct.unpack('<Bxhhh', data)
    assert decoded[0] == 0x08
    assert decoded[1] == x
    assert decoded[2] == y
    assert decoded[3] == z
```

#### 3. 配置加载正确性
```python
@given(
    bitrate=st.sampled_from([125000, 250000, 500000, 1000000]),
    alert_interval=st.integers(min_value=50, max_value=500),
    enable_auto_configure=st.booleans()
)
@settings(max_examples=100)
def test_config_loading_property(bitrate, alert_interval, enable_auto_configure):
    """
    Feature: can-communication, Property 3: 配置加载正确性
    
    For any 有效配置，加载后内部状态应一致
    """
    config = CANConfigDTO(
        can_bitrate=bitrate,
        alert_interval_ms=alert_interval,
        enable_auto_configure=enable_auto_configure
    )
    
    # 验证配置有效
    assert config.validate()
    
    # 验证配置值
    assert config.can_bitrate == bitrate
    assert config.alert_interval_ms == alert_interval
    assert config.enable_auto_configure == enable_auto_configure
```

#### 4. 自动配置条件触发
```python
@given(
    enable_auto_configure=st.booleans(),
    is_linux=st.booleans()
)
@settings(max_examples=100)
def test_auto_configure_condition(enable_auto_configure, is_linux):
    """
    Feature: can-communication, Property 4: 自动配置条件触发
    
    For any 配置和系统环境，自动配置应按条件触发
    """
    config = CANConfigDTO(enable_auto_configure=enable_auto_configure)
    
    with patch('os.name', 'posix' if is_linux else 'nt'):
        with patch('can_interface_config.configure_can_interface') as mock_config:
            communicator = CANCommunicator(config, mock_decision, mock_event_bus)
            communicator.start()
            
            # 验证调用条件
            if enable_auto_configure and is_linux:
                mock_config.assert_called_once()
            else:
                mock_config.assert_not_called()
```

#### 5. 坐标响应编码格式
```python
@given(
    x=st.integers(min_value=-32768, max_value=32767),
    y=st.integers(min_value=-32768, max_value=32767),
    z=st.integers(min_value=-32768, max_value=32767)
)
@settings(max_examples=100)
def test_coordinate_response_format(x, y, z):
    """
    Feature: can-communication, Property 6: 坐标响应编码格式
    
    For any 坐标，编码格式应符合协议规范
    """
    data = CANProtocol.encode_coordinate_response(x, y, z)
    
    # 验证长度
    assert len(data) == 8
    
    # 验证Byte0和Byte1
    assert data[0] == 0x08
    assert data[1] == 0x00
    
    # 验证小端序
    x_bytes = struct.pack('<h', x)
    y_bytes = struct.pack('<h', y)
    z_bytes = struct.pack('<h', z)
    
    assert data[2:4] == x_bytes
    assert data[4:6] == y_bytes
    assert data[6:8] == z_bytes
```

### 集成测试

**测试场景**：
1. **端到端坐标请求响应**
   - 模拟外部控制器发送请求
   - 验证CAN模块调用决策层
   - 验证响应帧格式正确

2. **人员警报流程**
   - 模拟决策层发布TRIGGERED事件
   - 验证警报定时器启动
   - 验证警报帧周期发送
   - 模拟CLEARED事件
   - 验证警报停止

3. **接口配置流程**（仅Linux）
   - 验证自动配置成功
   - 验证总线连接成功
   - 验证停止时重置接口

### 测试覆盖率目标

- **单元测试覆盖率**：≥ 85%
- **属性测试覆盖率**：核心逻辑100%
- **集成测试覆盖率**：关键流程100%

### 测试执行

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行属性测试
pytest tests/property/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=modules/can --cov-report=html
```
