# 顶层设计

## 1. 架构模式概述

### 1.1 基于线程的模块架构

系统采用三个独立线程模块的架构设计，每个模块专注于特定的功能领域，通过高效的线程间通信实现协同工作。

#### 1.1.1 数据采集模块（OAK数据源模块）- 线程1

**核心职责：**
- **设备连接检查**：自动检查连接的OAK设备，获取并维护设备MXid信息
- **固定配置Pipeline**：根据检测到的设备MXid，加载对应的固定配置参数，创建专用的检测pipeline
- **检测线程启动**：为每个连接的设备根据其MXid启动对应的检测线程
- **数据获取**：持续获取设备返回的原始数据，包括坐标数据（coordination）和视频帧（video）
- **数据接口提供**：为其他线程提供统一的数据获取接口，支持按设备ID或者设备别名获取coordination数据和video数据

**运行模式：**
- 独立线程运行，不阻塞其他模块
- 维护设备状态和数据缓冲区
- 提供线程安全的数据访问接口

#### 1.1.2 数据调度器模块 - 线程2

**核心职责：**
- **坐标数据变换**：将从数据采集模块获取的相机坐标数据转换为世界坐标系
- **数据滤波**：对时序坐标数据进行平滑处理和稳态评分，提高数据质量
- **坐标修正**：应用各种误差修正策略，包括线性修正、多项式修正、距离修正等
- **坐标数据选择与处理**：根据业务策略进行目标选择、多设备数据融合、安全区域检查等

**架构特点：**
- **基础过滤器基类**：所有数据处理模块继承统一的基础过滤器基类
- **统一接口设计**：维护多个标准化的数据处理接口，确保模块间的一致性
- **策略注册模式**：采用策略注册机制，支持运行时快速更换不同的数据处理策略
- **模块化设计**：各个处理模块相互独立，便于维护和扩展

**运行模式：**
- 独立线程运行，专门负责数据处理调度
- 从数据采集模块获取原始数据
- 处理后的数据传递给CAN模块或显示模块

#### 1.1.3 CAN通信模块 - 线程3

**核心职责：**
- **总线监听**：持续监听CAN总线，实时获取外部系统发送的数据和指令
- **外部接口提供**：为系统提供统一的CAN通信外部接口
- **数据发送**：接收来自数据调度器的处理结果，发送特定格式的CAN数据到总线
- **数据接收**：接收CAN总线上的返回数据，解析后提供给其他模块使用

**运行模式：**
- 独立线程运行，专门负责CAN总线通信
- 提供异步的数据发送和接收服务
- 处理通信异常和重试机制


#### 1.1.4 显示模块 - 线程4

**核心职责：**
- **视频数据获取**：通过回调函数从数据采集模块获取实时video数据（包括深度图和彩色图）
- **坐标数据获取**：通过回调函数或主动调用接口从数据调度器获取处理后的坐标数据
- **图像渲染**：将检测框、坐标信息等处理结果绘制在视频图像上
- **显示模式支持**：支持显示深度图和彩色图的组合模式，或仅显示彩色图模式
- **实时可视化**：提供实时的数据可视化界面，展示检测结果和系统状态

**运行模式：**
- 独立线程运行，专门负责显示渲染
- 通过回调机制接收数据采集模块的video数据流
- 通过回调函数或接口查询获取数据调度器的处理结果
- 实时将坐标数据、检测框等信息叠加显示在视频图像上

#### 1.1.5 动作控制模块 - 线程5

**核心职责：**
- **抓取决策**：根据数据调度器传来的坐标数据，分析并决定最优的抓取位置和抓取策略
- **轨迹规划**：规划机械臂从当前位置到目标位置的运动轨迹，确保运动平滑和安全
- **传感器数据获取**：通过CAN模块接口获取机械臂各关节的角度传感器数据和状态信息
- **控制指令生成**：生成符合协议规范的控制指令，与PID控制器模块进行通信

**子模块设计：**
- **抓取决策模块**：分析目标物体的位置、姿态和环境约束，制定抓取策略
- **轨迹控制模块**：基于运动学模型规划机械臂的运动轨迹，避免碰撞和奇异点
- **传感器数据获取模块**：实时获取机械臂关节角度、力矩等传感器反馈数据

**运行模式：**
- 独立线程运行，专门负责机械臂动作控制
- 从数据调度器获取处理后的目标坐标数据
- 通过CAN模块接口与PID控制器进行协议通信
- 利用CAN模块获取机械臂传感器反馈数据
- 实现闭环控制，确保抓取动作的精确执行
#### 1.1.6 线程间协作模式

**高性能订阅发布架构：**
- **事件驱动架构**：采用订阅发布模式，实现高性能的异步数据传递
- **非阻塞通信**：数据发布者无需等待消费者处理，避免锁竞争和线程阻塞
- **松耦合设计**：各模块通过事件总线通信，降低直接依赖关系
- **并行处理**：多个消费者可以同时处理同一数据，提高系统吞吐量

**高性能事件总线设计：**
```python
class HighPerformanceEventBus:
    # 核心特性
    - 无锁队列：使用线程安全的无锁数据结构，避免锁竞争
    - 背压处理：队列满时采用丢帧策略，保证实时性
    - 零拷贝优化：大数据（视频帧）通过共享内存传递
    - 批量处理：支持批量事件发布，减少系统调用开销
    - 优先级队列：支持事件优先级，确保关键数据优先处理
```

**订阅发布通信机制：**
- **事件发布**：数据生产者通过事件总线发布数据，完全非阻塞执行
- **事件订阅**：数据消费者订阅感兴趣的事件类型，异步接收数据
- **回调处理**：支持异步回调函数，实现数据的主动推送
- **时间戳同步**：所有事件携带统一时间戳，确保跨线程时序一致性

**线程间数据流架构：**
```
数据采集模块     数据调度器      CAN通信模块     显示模块      动作控制模块
   (线程1)        (线程2)         (线程3)       (线程4)       (线程5)
      ↓             ↓               ↓            ↓             ↓
   事件发布     事件订阅+发布   事件订阅+发布   事件订阅    事件订阅+发布
      ↓             ↓               ↓            ↓             ↓
 [HighPerformanceEventBus - 高性能事件总线 - 支持并发订阅/发布/零拷贝]
```

**具体事件流定义：**

1. **数据采集模块发布事件**：
   - `raw_frame_data`: 原始视频帧数据（仅包含帧数据、帧ID、设备MXid，零拷贝传递）
   - `raw_detection_data`: 原始检测数据（包含完整检测信息，仅发送给数据调度器）
   - `device_status`: 设备连接状态和健康信息

2. **数据调度器订阅/发布事件**：
   - 订阅：`raw_detection_data`、`can_feedback`
   - 发布：`processed_display_data`、`control_commands`、`target_coordinates`

3. **CAN通信模块订阅/发布事件**：
   - 订阅：`control_commands`、`query_requests`
   - 发布：`can_feedback`、`sensor_data`、`system_alerts`

4. **显示模块订阅事件**：
   - 订阅：`raw_frame_data`（视频帧）、`processed_display_data`（处理后的显示数据）、`system_status`

5. **动作控制模块订阅/发布事件**：
   - 订阅：`target_coordinates`、`sensor_data`
   - 发布：`motion_commands`、`grasp_status`

**性能优化策略：**
- **异步处理**：所有事件处理均为异步，避免阻塞主流程
- **队列分离**：为不同事件类型设置独立队列，防止相互影响
- **背压控制**：当消费者处理能力不足时，自动丢弃过时数据
- **批量传输**：支持批量事件发布，提高传输效率
- **内存池**：使用内存池管理事件对象，减少内存分配开销

**数据同步与一致性：**
- **统一时间戳**：所有事件携带高精度时间戳，确保时序一致性
- **帧ID同步**：基于帧ID实现跨线程的数据关联和同步
- **版本控制**：事件数据支持版本号，避免过期数据处理
- **原子操作**：关键状态更新使用原子操作，保证数据一致性

**容错与监控机制：**
- **故障隔离**：单个订阅者异常不影响其他订阅者和发布者
- **自动重连**：订阅者异常时支持自动重新订阅机制
- **降级处理**：关键事件处理失败时启用降级策略
- **性能监控**：实时监控事件处理延迟、队列深度、丢包率
- **异常告警**：事件处理异常时及时告警和日志记录



## 2. 数据传输对象（DTO）设计

### 2.1 数据采集模块DTO

#### 2.1.1 空间坐标DTO
```python
from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class SpatialCoordinatesDTO:
    """空间坐标数据传输对象"""
    x: float  # X轴坐标 (mm)
    y: float  # Y轴坐标 (mm) 
    z: float  # Z轴坐标 (mm)
    
    def __post_init__(self):
        """坐标数据验证"""
        if not all(isinstance(coord, (int, float)) for coord in [self.x, self.y, self.z]):
            raise ValueError("坐标值必须为数值类型")
```

#### 2.1.2 边界框DTO
```python
@dataclass
class BoundingBoxDTO:
    """边界框数据传输对象"""
    xmin: float  # 左上角X坐标
    ymin: float  # 左上角Y坐标
    xmax: float  # 右下角X坐标
    ymax: float  # 右下角Y坐标
    
    def __post_init__(self):
        """边界框数据验证"""
        if self.xmin >= self.xmax or self.ymin >= self.ymax:
            raise ValueError("边界框坐标无效：min值必须小于max值")
    
    @property
    def width(self) -> float:
        """边界框宽度"""
        return self.xmax - self.xmin
    
    @property
    def height(self) -> float:
        """边界框高度"""
        return self.ymax - self.ymin
    
    @property
    def center_x(self) -> float:
        """归一化边界框中心X坐标"""
        return (self.xmin + self.xmax) / 2
    
    @property
    def center_y(self) -> float:
        """归一化边界框中心Y坐标"""
        return (self.ymin + self.ymax) / 2
```

#### 2.1.3 检测结果DTO
```python
@dataclass(frozen=True)
class DetectionDTO(BaseDTO):
    """单个检测结果数据传输对象"""
    label: str  # 检测物体标签
    confidence: float  # 检测置信度 (0.0-1.0)
    bbox: BoundingBoxDTO  # 边界框信息
    spatial_coordinates: SpatialCoordinatesDTO  # 空间坐标信息
    detection_id: Optional[str] = None  # 检测唯一标识符
    # 注意：时间戳使用继承的 created_at 字段
    
    def _validate_data(self) -> List[str]:
        """检测数据验证"""
        errors = []
        
        # 验证标签
        errors.extend(validate_string_length(
            self.label, 'label', min_length=1, max_length=100
        ))
        
        # 验证置信度
        errors.extend(validate_numeric_range(
            self.confidence, 'confidence', min_value=0.0, max_value=1.0
        ))
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        if self.detection_id is None:
            # 生成基于标签和时间戳的唯一ID，使用继承的created_at字段
            timestamp_ms = int(self.created_at * 1000)
            detection_id = f"{self.label}_{timestamp_ms}_{str(uuid.uuid4())[:8]}"
            object.__setattr__(self, 'detection_id', detection_id)
```

#### 2.1.4 设备检测数据DTO
```python
@dataclass(frozen=True)
class DeviceDetectionDataDTO(BaseDTO):
    """单个设备的检测数据传输对象"""
    device_id: str  # 设备唯一标识符（MXid）
    device_alias: Optional[str] = None  # 设备别名
    detections: Optional[List[DetectionDTO]] = None  # 检测结果列表
    frame_id: int  # 帧ID（主要标识符，用于与视频帧同步）
    # 注意：时间戳使用继承的 created_at 字段，无需重复定义
    
    def _validate_data(self) -> List[str]:
        """设备检测数据验证"""
        errors = []
        
        # 验证设备ID
        errors.extend(validate_string_length(
            self.device_id, 'device_id', min_length=1, max_length=100
        ))
        
        # 验证帧ID（必需）
        errors.extend(validate_numeric_range(
            self.frame_id, 'frame_id', min_value=0
        ))
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        if self.detections is None:
            object.__setattr__(self, 'detections', [])
    
    @property
    def detection_count(self) -> int:
        """检测结果数量"""
        return len(self.detections)
    
    def get_detections_by_label(self, label: str) -> list[DetectionDTO]:
        """根据标签筛选检测结果"""
        return [det for det in self.detections if det.label == label]
    
    def get_high_confidence_detections(self, threshold: float = 0.5) -> list[DetectionDTO]:
        """获取高置信度检测结果"""
        return [det for det in self.detections if det.confidence >= threshold]
```

#### 2.1.5 视频帧数据DTO
```python
@dataclass(frozen=True)
class VideoFrameDTO(BaseDTO):
    """视频帧数据传输对象"""
    device_id: str  # 设备ID
    frame_id: int  # 帧ID
    rgb_frame: Optional[Any] = None  # RGB图像数据 (numpy.ndarray)
    depth_frame: Optional[Any] = None  # 深度图像数据 (numpy.ndarray)
    frame_width: Optional[int] = None  # 帧宽度
    frame_height: Optional[int] = None  # 帧高度
    # 注意：时间戳使用继承的 created_at 字段
    
    def _validate_data(self) -> List[str]:
        """视频帧数据验证"""
        errors = []
        
        # 验证至少有一种帧数据
        if self.rgb_frame is None and self.depth_frame is None:
            errors.append("rgb_frame和depth_frame不能同时为None")
        
        return errors
    
    @property
    def has_rgb(self) -> bool:
        """是否包含RGB数据"""
        return self.rgb_frame is not None
    
    @property
    def has_depth(self) -> bool:
        """是否包含深度数据"""
        return self.depth_frame is not None
```


#### 2.1.6 综合数据采集DTO
```python
@dataclass(frozen=True)
class OAKDataCollectionDTO(BaseDTO):
    """OAK数据采集模块综合数据传输对象"""
    collection_id: str  # 采集批次ID
    devices_data: Optional[Dict[str, DeviceDetectionDataDTO]] = None  # 设备检测数据字典
    video_frames: Optional[Dict[str, VideoFrameDTO]] = None  # 视频帧字典
    # 注意：时间戳使用继承的 created_at 字段
    
    def _validate_data(self) -> List[str]:
        """数据采集DTO验证"""
        errors = []
        
        # 验证采集批次ID
        errors.extend(validate_string_length(
            self.collection_id, 'collection_id', min_length=1, max_length=100
        ))
        
        return errors
    
    def _post_init_hook(self) -> None:
        """初始化后钩子，设置默认值"""
        if self.devices_data is None:
            object.__setattr__(self, 'devices_data', {})
        
        if self.video_frames is None:
            object.__setattr__(self, 'video_frames', {})
    
    @property
    def available_devices(self) -> list[str]:
        """获取可用设备列表（有数据的设备）"""
        return list(self.devices_data.keys())
    
    @property
    def total_detections(self) -> int:
        """获取总检测数量"""
        return sum(data.detection_count for data in self.devices_data.values())
    
    def get_device_data(self, device_id: str) -> Optional[DeviceDetectionDataDTO]:
        """根据设备ID获取检测数据"""
        return self.devices_data.get(device_id)
    
    def get_video_frame(self, device_id: str) -> Optional[VideoFrameDTO]:
        """根据设备ID获取视频帧"""
        return self.video_frames.get(device_id)
```

#### 2.1.7 事件数据DTO（优化后的设计）

**设计理念更新**：基于显示模块需求和性能优化考虑，事件DTO采用分离式设计。

```python
@dataclass
class RawFrameDataEvent(BaseDTO):
    """原始帧数据事件DTO（仅用于显示模块）"""
    event_type: str = field(default="raw_frame_data", init=False)
    device_id: str = ""           # 设备MXid
    frame_id: int = None            # 帧ID
    rgb_frame: Optional[Any] = None # RGB图像数据
    depth_frame: Optional[Any] = None # 深度图像数据（可选）
    # 注意：时间戳使用继承的 created_at 字段，无需重复定义
    
    # 注意：不再包含完整的VideoFrameDTO，减少数据传输开销

@dataclass
class RawDetectionDataEvent(BaseDTO):
    """原始检测数据事件DTO（仅发送给数据调度器）"""
    event_type: str = field(default="raw_detection_data", init=False)
    device_id: str = ""
    detection_data: Optional[DeviceDetectionDataDTO] = None
    # 注意：时间戳使用继承的 created_at 字段，无需重复定义
    
    # 注意：包含完整的检测信息，仅数据调度器订阅此事件
```

**关键设计变更**：
1. **数据分离传输**：视频帧和检测数据分别传输，避免重复数据传递
2. **目标模块专用**：`RawFrameDataEvent`专门服务显示模块，`RawDetectionDataEvent`专门服务数据调度器
3. **性能优化**：减少不必要的数据封装，提高传输效率
4. **职责明确**：每个事件DTO只承载其目标模块所需的数据
5. **字段优化**：消除timestamp字段重复，统一使用BaseDTO.created_at字段

**数据流向**：
```
数据采集模块 ┬─ RawFrameDataEvent ────→ 显示模块
            └─ RawDetectionDataEvent ──→ 数据调度器 ──→ ProcessedDisplayDataEvent ──→ 显示模块
```

#### 2.1.8 DTO字段优化说明

**重要优化**：消除timestamp字段重复性

在系统设计过程中，发现多个DTO中的`timestamp`字段与`BaseDTO.created_at`字段功能完全重复。经过优化，统一使用基类的`created_at`字段。

**优化前的问题**：
- `DeviceDetectionDataDTO.timestamp` ❌
- `DetectionDTO.timestamp` ❌  
- `VideoFrameDTO.timestamp` ❌
- `OAKDataCollectionDTO.timestamp` ❌
- `RawFrameDataEvent.timestamp` ❌
- `RawDetectionDataEvent.timestamp` ❌

**优化后的设计**：
- 统一使用 `BaseDTO.created_at` 字段 ✅
- 减少重复代码约30行 ✅
- 提高代码一致性 ✅
- 简化维护复杂度 ✅

**字段职责明确**：
- `frame_id`: 专门用于数据同步（整数序列）
- `created_at`: 专门用于时间记录（Unix时间戳）

---

## 3. 代码文件组织结构

### 3.1 项目结构总览

基于模块化架构设计，项目采用清晰的分层结构，每个模块职责明确，便于开发、测试和维护。

#### 3.1.1 一级目录结构
```
oak_vision_system/
├── config/                             # 配置文件目录
├── core/                               # 核心基础设施
├── modules/                            # 功能模块
├── utils/                              # 工具函数
├── tests/                              # 测试代码
├── scripts/                            # 脚本文件
├── docs/                               # 文档
├── deployment/                         # 部署相关
├── README.md                           # 项目说明文档
├── requirements.txt                    # Python依赖包列表
├── setup.py                           # 项目安装配置
├── pyproject.toml                      # 现代Python项目配置
└── .env.example                        # 环境变量示例文件
```

#### 3.1.2 核心模块二级结构
```
core/                                   # 核心基础设施
├── dto/                                # 数据传输对象
├── event_bus/                          # 事件总线系统
├── logging/                            # 日志管理系统（预留）
├── exceptions/                         # 自定义异常类
└── interfaces/                         # 接口定义

modules/                                # 功能模块
├── data_collector/                     # 数据采集模块（线程1）
├── data_scheduler/                     # 数据调度器模块（线程2）
├── can_communication/                  # CAN通信模块（线程3）
├── display/                            # 显示模块（线程4）
└── motion_control/                     # 动作控制模块（线程5）
```

### 3.2 核心基础设施详解

#### 3.2.1 数据传输对象（DTO）结构
```
core/dto/
├── __init__.py                         # 导出所有DTO类
├── base_dto.py                         # DTO基类，定义通用属性和方法
├── detection_dto.py                    # 检测相关的数据传输对象
├── video_dto.py                        # 视频相关的数据传输对象
├── coordinate_dto.py                   # 坐标处理相关DTO
├── can_dto.py                          # CAN通信相关DTO
├── control_dto.py                      # 动作控制相关DTO
└── event_dto.py                        # 事件相关DTO
```

#### 3.2.2 事件总线系统结构
```
core/event_bus/
├── __init__.py                         # 模块初始化，导出核心接口
├── event_bus.py                        # 事件总线核心实现
├── event_types.py                      # 所有事件类型的定义
├── priority.py                         # 事件优先级枚举和管理
├── subscription_manager.py             # 订阅关系管理
└── metrics.py                          # 性能指标收集和监控
```

#### 3.2.3 日志管理系统结构（预留）
```
core/logging/                           # 日志管理系统（待实现）
├── __init__.py                         # 模块初始化，导出标准接口
├── logger_factory.py                   # 日志器工厂
├── formatters.py                       # 结构化日志格式化器
├── handlers.py                         # 异步日志处理器
├── collectors.py                       # 日志收集和聚合器
├── config.py                           # 日志配置管理
└── dto.py                              # 日志相关DTO定义
```

#### 3.2.4 异常处理系统结构
```
core/exceptions/
├── __init__.py                         # 异常模块初始化
├── base_exceptions.py                  # 基础异常类
├── device_exceptions.py                # 设备相关异常
├── communication_exceptions.py         # 通信相关异常
└── processing_exceptions.py            # 数据处理异常
```

#### 3.2.5 接口定义结构
```
core/interfaces/
├── __init__.py                         # 接口模块初始化
├── module_interface.py                 # 模块基础接口
├── data_processor_interface.py         # 数据处理接口
└── communication_interface.py          # 通信接口
```

### 3.3 功能模块详解

#### 3.3.1 数据采集模块结构
```
modules/data_collector/
├── __init__.py                         # 模块初始化，导出主要类
├── oak_data_collector.py               # 主控制器，管理整个数据采集流程
├── device_manager.py                   # 设备发现、连接和状态管理
├── pipeline_manager.py                 # DepthAI Pipeline的创建和管理
├── detection_processor.py              # 检测数据的解析和处理
├── video_processor.py                  # 视频帧的获取和预处理
└── data_buffer.py                      # 线程安全的数据缓冲区管理
```

**关键类设计：**
- `OAKDataCollector`: 主控制器类，协调所有子组件
- `DeviceManager`: 管理OAK设备的连接和配置
- `PipelineManager`: 管理DepthAI管道的生命周期
- `DetectionProcessor`: 处理神经网络检测结果
- `VideoProcessor`: 处理RGB和深度图像数据
- `DataBuffer`: 提供线程安全的数据缓存

#### 3.3.2 数据调度器模块结构
```
modules/data_scheduler/
├── __init__.py                         # 模块初始化
├── data_scheduler.py                   # 主调度器，协调各处理组件
├── coordinate_transformer.py           # 坐标系变换（相机→世界坐标）
├── filters/                            # 数据滤波器子模块
│   ├── __init__.py
│   ├── base_filter.py                  # 滤波器抽象基类
│   ├── temporal_filter.py              # 时序数据平滑滤波
│   ├── spatial_filter.py               # 空间数据滤波
│   └── confidence_filter.py            # 置信度阈值滤波
├── correctors/                         # 坐标修正器子模块
│   ├── __init__.py
│   ├── base_corrector.py               # 修正器抽象基类
│   ├── linear_corrector.py             # 线性误差修正
│   ├── polynomial_corrector.py         # 多项式误差修正
│   └── distance_corrector.py           # 距离相关误差修正
├── strategies/                         # 数据使用策略子模块
│   ├── __init__.py
│   ├── base_strategy.py                # 策略抽象基类
│   ├── target_selection.py             # 目标选择策略
│   ├── multi_device_fusion.py          # 多设备数据融合策略
│   └── safety_zone_checker.py          # 安全区域检查策略
└── processor_registry.py               # 处理器动态注册和管理
```

**关键设计特点：**
- **策略模式**: 各种处理算法实现为可替换的策略类
- **责任链模式**: 数据通过滤波器链进行逐级处理
- **注册模式**: 支持运行时动态注册和切换处理策略
- **模板方法**: 基类定义处理流程，子类实现具体算法

#### 3.3.3 CAN通信模块结构
```
modules/can_communication/
├── __init__.py                         # 模块初始化
├── can_communicator.py                 # CAN通信器主类
├── bus_listener.py                     # 总线监听器
├── message_parser.py                   # 消息解析器
├── protocol_handler.py                 # 协议处理器
├── retry_manager.py                    # 重试管理器
└── connection_monitor.py               # 连接监控器
```

#### 3.3.4 显示模块结构
```
modules/display/
├── __init__.py                         # 模块初始化
├── display_manager.py                  # 显示管理器主类
├── frame_renderer.py                   # 帧渲染器
├── overlay_drawer.py                   # 叠加绘制器
├── ui_components/                      # UI组件
│   ├── __init__.py
│   ├── detection_overlay.py            # 检测框叠加
│   ├── coordinate_display.py           # 坐标信息显示
│   └── status_indicator.py             # 状态指示器
└── display_modes/                      # 显示模式
    ├── __init__.py
    ├── rgb_mode.py                     # RGB显示模式
    ├── depth_mode.py                   # 深度图显示模式
    └── combined_mode.py                # 组合显示模式
```

#### 3.3.5 动作控制模块结构
```
modules/motion_control/
├── __init__.py                         # 模块初始化
├── motion_controller.py                # 动作控制器主类
├── grasp_planner.py                    # 抓取规划器
├── trajectory_planner.py               # 轨迹规划器
├── sensor_monitor.py                   # 传感器监控器
├── safety_monitor.py                   # 安全监控器
└── control_strategies/                 # 控制策略
    ├── __init__.py
    ├── base_control_strategy.py        # 控制策略基类
    ├── pid_controller.py               # PID控制器
    └── adaptive_controller.py          # 自适应控制器
```

### 3.4 支撑系统结构

#### 3.4.1 配置管理结构
```
config/
├── __init__.py                         # 配置模块初始化
├── app_config.py                       # 应用级配置管理
├── device_config.py                    # 设备配置管理
├── logging_config.py                   # 日志系统配置
├── event_config.py                     # 事件总线配置
└── profiles/                           # 环境特定配置
    ├── development.json                # 开发环境配置
    ├── production.json                 # 生产环境配置
    └── testing.json                    # 测试环境配置
```

#### 3.4.2 工具函数结构
```
utils/
├── __init__.py                         # 工具模块初始化
├── logger.py                           # 日志工具
├── config_loader.py                    # 配置加载器
├── math_utils.py                       # 数学计算工具
├── image_utils.py                      # 图像处理工具
├── time_utils.py                       # 时间处理工具
├── validation_utils.py                 # 数据验证工具
└── performance_monitor.py              # 性能监控工具
```

#### 3.4.3 测试结构
```
tests/
├── __init__.py                         # 测试模块初始化
├── conftest.py                         # pytest全局配置和夹具
├── unit/                               # 单元测试
│   ├── test_data_collector.py          # 数据采集模块测试
│   ├── test_data_scheduler.py          # 数据调度器测试
│   ├── test_can_communication.py       # CAN通信测试
│   ├── test_display.py                 # 显示模块测试
│   ├── test_motion_control.py          # 动作控制测试
│   └── test_event_bus.py               # 事件总线测试
├── integration/                        # 集成测试
│   ├── test_module_integration.py      # 模块间集成测试
│   └── test_system_integration.py      # 系统级集成测试
├── performance/                        # 性能测试
│   ├── test_throughput.py              # 数据吞吐量测试
│   └── test_latency.py                 # 系统延迟测试
└── fixtures/                           # 测试数据和工具
    ├── mock_data.py                    # 模拟数据生成器
    └── test_configs.py                 # 测试专用配置
```

#### 3.4.4 开发和部署工具
```
scripts/                                # 开发脚本
├── setup_environment.py                # 环境配置脚本
├── run_system.py                       # 系统启动脚本
├── calibration_tool.py                 # 标定工具脚本
├── performance_benchmark.py            # 性能基准测试脚本
├── data_migration.py                   # 数据迁移工具
└── code_generator.py                   # 代码生成工具

deployment/                             # 部署配置
├── docker/                             # 容器化部署
│   ├── Dockerfile                      # 应用容器定义
│   ├── docker-compose.yml              # 多容器编排
│   └── .dockerignore                   # Docker构建忽略文件
├── systemd/                            # 系统服务部署
│   ├── oak-vision.service              # Systemd服务定义
│   ├── install.sh                      # 服务安装脚本
│   └── uninstall.sh                    # 服务卸载脚本
└── monitoring/                         # 监控配置
    ├── prometheus.yml                  # Prometheus监控配置
    ├── grafana-dashboard.json          # Grafana仪表板
    └── alerting-rules.yml              # 告警规则配置
```

### 3.5 设计原则和规范

#### 3.5.1 文件命名规范
- **文件名**: 使用小写字母和下划线（snake_case）
- **类名**: 使用大驼峰命名（PascalCase）
- **函数和变量**: 使用小写字母和下划线（snake_case）
- **常量**: 使用全大写字母和下划线（UPPER_CASE）
- **模块导入**: 优先使用绝对导入，避免相对导入

#### 3.5.2 代码组织原则
- **单一职责**: 每个模块和类只负责一个明确的功能
- **依赖注入**: 通过构造函数注入依赖，便于测试和扩展
- **接口隔离**: 定义清晰的接口，减少模块间耦合
- **开闭原则**: 通过继承和组合实现功能扩展

#### 3.5.3 DTO设计原则
- **不可变性**: 所有DTO使用`@dataclass(frozen=True)`确保数据不可变
- **类型安全**: 使用类型提示确保数据类型正确性
- **验证机制**: 在`__post_init__`中进行数据有效性验证
- **序列化支持**: 支持JSON序列化，便于调试和持久化
- **版本兼容**: 预留版本字段，支持向后兼容

#### 3.5.4 配置管理策略
- **环境变量优先**: 支持通过环境变量覆盖配置
- **配置文件分层**: 基础配置+环境特定配置的组合模式
- **热重载支持**: 支持运行时配置更新（非关键配置）
- **配置验证**: 启动时验证配置完整性和有效性

#### 3.5.5 测试策略
- **Mock优先**: 使用Mock对象隔离外部依赖
- **数据驱动**: 使用参数化测试覆盖多种场景
- **性能基准**: 建立性能基准，防止性能回退
- **持续集成**: 支持自动化测试和代码覆盖率检查

#### 3.5.6 运维工具特性
- **健康检查**: 内置健康检查端点，支持容器编排
- **指标暴露**: 集成Prometheus指标暴露
- **日志聚合**: 结构化日志输出，支持日志聚合
- **故障恢复**: 自动重启和故障转移机制

#### 3.5.7 开发流程支持
- **代码生成**: 自动生成DTO、接口等模板代码
- **配置检查**: 验证配置文件的正确性和完整性
- **性能分析**: 内置性能分析和优化建议工具
- **依赖管理**: 自动检查和更新项目依赖

### 3.6 完整项目结构总览

基于以上分析，完整的项目文件组织结构如下：

```
oak_vision_system/
├── README.md                           # 项目说明文档
├── requirements.txt                    # Python依赖包列表
├── setup.py                           # 项目安装配置
├── pyproject.toml                      # 现代Python项目配置
├── .env.example                        # 环境变量示例文件
├── config/                             # 配置文件目录
│   ├── __init__.py
│   ├── app_config.py                   # 应用主配置
│   ├── device_config.py                # 设备配置管理
│   ├── logging_config.py               # 日志配置
│   ├── event_config.py                 # 事件总线配置
│   └── profiles/                       # 不同环境配置文件
│       ├── development.json            # 开发环境配置
│       ├── production.json             # 生产环境配置
│       └── testing.json                # 测试环境配置
├── core/                               # 核心基础设施
│   ├── __init__.py
│   ├── dto/                            # 数据传输对象
│   │   ├── __init__.py
│   │   ├── base_dto.py                 # DTO基类
│   │   ├── detection_dto.py            # 检测相关DTO
│   │   ├── video_dto.py                # 视频相关DTO
│   │   ├── coordinate_dto.py           # 坐标相关DTO
│   │   ├── can_dto.py                  # CAN通信DTO
│   │   ├── control_dto.py              # 控制相关DTO
│   │   └── event_dto.py                # 事件相关DTO
│   ├── event_bus/                      # 事件总线系统
│   │   ├── __init__.py
│   │   ├── event_bus.py                # 事件总线核心实现
│   │   ├── event_types.py              # 事件类型定义
│   │   ├── priority.py                 # 事件优先级定义
│   │   ├── subscription_manager.py     # 订阅管理器
│   │   └── metrics.py                  # 性能监控和指标
│   ├── logging/                        # 日志管理系统（预留）
│   │   ├── __init__.py
│   │   ├── logger_factory.py           # 日志器工厂
│   │   ├── formatters.py               # 结构化日志格式化器
│   │   ├── handlers.py                 # 异步日志处理器
│   │   ├── collectors.py               # 日志收集和聚合器
│   │   ├── config.py                   # 日志配置管理
│   │   └── dto.py                      # 日志相关DTO定义
│   ├── exceptions/                     # 自定义异常类
│   │   ├── __init__.py
│   │   ├── base_exceptions.py          # 基础异常类
│   │   ├── device_exceptions.py        # 设备相关异常
│   │   ├── communication_exceptions.py # 通信相关异常
│   │   └── processing_exceptions.py    # 数据处理异常
│   └── interfaces/                     # 接口定义
│       ├── __init__.py
│       ├── module_interface.py         # 模块基础接口
│       ├── data_processor_interface.py # 数据处理接口
│       └── communication_interface.py  # 通信接口
├── modules/                            # 功能模块
│   ├── __init__.py
│   ├── data_collector/                 # 数据采集模块（线程1）
│   │   ├── __init__.py
│   │   ├── oak_data_collector.py       # OAK数据采集器主类
│   │   ├── device_manager.py           # 设备管理器
│   │   ├── pipeline_manager.py         # Pipeline管理器
│   │   ├── detection_processor.py      # 检测数据处理器
│   │   ├── video_processor.py          # 视频数据处理器
│   │   └── data_buffer.py              # 数据缓冲管理
│   ├── data_scheduler/                 # 数据调度器模块（线程2）
│   │   ├── __init__.py
│   │   ├── data_scheduler.py           # 数据调度器主类
│   │   ├── coordinate_transformer.py   # 坐标变换器
│   │   ├── filters/                    # 数据滤波器
│   │   │   ├── __init__.py
│   │   │   ├── base_filter.py          # 滤波器基类
│   │   │   ├── temporal_filter.py      # 时序滤波器
│   │   │   ├── spatial_filter.py       # 空间滤波器
│   │   │   └── confidence_filter.py    # 置信度滤波器
│   │   ├── correctors/                 # 坐标修正器
│   │   │   ├── __init__.py
│   │   │   ├── base_corrector.py       # 修正器基类
│   │   │   ├── linear_corrector.py     # 线性修正器
│   │   │   ├── polynomial_corrector.py # 多项式修正器
│   │   │   └── distance_corrector.py   # 距离修正器
│   │   ├── strategies/                 # 数据使用策略
│   │   │   ├── __init__.py
│   │   │   ├── base_strategy.py        # 策略基类
│   │   │   ├── target_selection.py     # 目标选择策略
│   │   │   ├── multi_device_fusion.py  # 多设备数据融合
│   │   │   └── safety_zone_checker.py  # 安全区域检查
│   │   └── processor_registry.py       # 处理器注册管理
│   ├── can_communication/              # CAN通信模块（线程3）
│   │   ├── __init__.py
│   │   ├── can_communicator.py         # CAN通信器主类
│   │   ├── bus_listener.py             # 总线监听器
│   │   ├── message_parser.py           # 消息解析器
│   │   ├── protocol_handler.py         # 协议处理器
│   │   ├── retry_manager.py            # 重试管理器
│   │   └── connection_monitor.py       # 连接监控器
│   ├── display/                        # 显示模块（线程4）
│   │   ├── __init__.py
│   │   ├── display_manager.py          # 显示管理器主类
│   │   ├── frame_renderer.py           # 帧渲染器
│   │   ├── overlay_drawer.py           # 叠加绘制器
│   │   ├── ui_components/              # UI组件
│   │   │   ├── __init__.py
│   │   │   ├── detection_overlay.py    # 检测框叠加
│   │   │   ├── coordinate_display.py   # 坐标信息显示
│   │   │   └── status_indicator.py     # 状态指示器
│   │   └── display_modes/              # 显示模式
│   │       ├── __init__.py
│   │       ├── rgb_mode.py             # RGB显示模式
│   │       ├── depth_mode.py           # 深度图显示模式
│   │       └── combined_mode.py        # 组合显示模式
│   └── motion_control/                 # 动作控制模块（线程5）
│       ├── __init__.py
│       ├── motion_controller.py        # 动作控制器主类
│       ├── grasp_planner.py            # 抓取规划器
│       ├── trajectory_planner.py       # 轨迹规划器
│       ├── sensor_monitor.py           # 传感器监控器
│       ├── safety_monitor.py           # 安全监控器
│       └── control_strategies/         # 控制策略
│           ├── __init__.py
│           ├── base_control_strategy.py # 控制策略基类
│           ├── pid_controller.py       # PID控制器
│           └── adaptive_controller.py  # 自适应控制器
├── utils/                              # 工具函数
│   ├── __init__.py
│   ├── logger.py                       # 日志工具
│   ├── config_loader.py                # 配置加载器
│   ├── math_utils.py                   # 数学计算工具
│   ├── image_utils.py                  # 图像处理工具
│   ├── time_utils.py                   # 时间处理工具
│   ├── validation_utils.py             # 数据验证工具
│   └── performance_monitor.py          # 性能监控工具
├── tests/                              # 测试代码
│   ├── __init__.py
│   ├── conftest.py                     # pytest配置
│   ├── unit/                           # 单元测试
│   │   ├── __init__.py
│   │   ├── test_data_collector.py      # 数据采集模块测试
│   │   ├── test_data_scheduler.py      # 数据调度器测试
│   │   ├── test_can_communication.py   # CAN通信测试
│   │   ├── test_display.py             # 显示模块测试
│   │   ├── test_motion_control.py      # 动作控制测试
│   │   └── test_event_bus.py           # 事件总线测试
│   ├── integration/                    # 集成测试
│   │   ├── __init__.py
│   │   ├── test_module_integration.py  # 模块间集成测试
│   │   └── test_system_integration.py  # 系统级集成测试
│   ├── performance/                    # 性能测试
│   │   ├── __init__.py
│   │   ├── test_throughput.py          # 吞吐量测试
│   │   └── test_latency.py             # 延迟测试
│   └── fixtures/                       # 测试数据和夹具
│       ├── __init__.py
│       ├── mock_data.py                # 模拟数据
│       └── test_configs.py             # 测试配置
├── scripts/                            # 脚本文件
│   ├── setup_environment.py            # 环境配置脚本
│   ├── run_system.py                   # 系统启动脚本
│   ├── calibration_tool.py             # 标定工具脚本
│   ├── performance_benchmark.py        # 性能基准测试脚本
│   ├── data_migration.py               # 数据迁移工具
│   └── code_generator.py               # 代码生成工具
├── docs/                               # 文档
│   ├── api/                            # API文档
│   ├── architecture/                   # 架构文档
│   ├── user_guide/                     # 用户指南
│   └── development/                    # 开发文档
└── deployment/                         # 部署相关
    ├── docker/                         # Docker配置
    │   ├── Dockerfile
    │   └── docker-compose.yml
    ├── systemd/                        # Systemd服务配置
    │   ├── oak-vision.service
    │   └── install.sh
    └── monitoring/                     # 监控配置
        ├── prometheus.yml
        └── grafana-dashboard.json
```

**结构特点总结：**
- **分层清晰**: 核心基础设施、功能模块、支撑系统明确分离
- **职责明确**: 每个目录和文件都有明确的功能定位
- **扩展性强**: 支持新模块的轻松添加和现有模块的扩展
- **可维护性**: 模块化设计便于独立开发和维护
- **标准化**: 统一的命名规范和代码组织原则

---

## 4. 数据处理调度器模块设计

### 4.1 模块概述

数据处理调度器模块是系统的**核心数据处理中枢**，负责接收原始检测数据，经过多层处理后输出用于显示和控制的结构化数据。

#### 4.1.1 核心职责扩展
- **检测数据处理**：接收并处理来自数据采集模块的原始检测数据
- **状态评估与分类**：为每个检测目标分配状态（危险、可抓取、不可抓取等）
- **抓取目标选择**：基于策略选择最优抓取目标，生成预抓取索引
- **显示数据生成**：生成专门用于显示模块的标注数据
- **控制数据输出**：为动作控制模块提供精确的目标坐标

#### 4.1.2 数据处理流水线
```python
数据处理流水线：
原始检测数据 → 坐标变换 → 数据滤波 → 状态评估 → 目标选择 → 输出分发
                                                      ↓
                                          ┌─ 显示数据（processed_display_data）
                                          └─ 控制数据（target_coordinates）
```

### 4.2 检测目标状态管理系统

#### 4.2.1 状态定义与评估标准
```python
class DetectionStatus(Enum):
    DANGEROUS = "dangerous"        # 危险状态：位于危险区域或移动过快
    READY_TO_GRASP = "ready"      # 待抓取状态：满足抓取条件但未被选中
    GRASPABLE = "graspable"       # 可抓取状态：基本满足抓取条件
    UNGRASPABLE = "ungraspable"   # 无法抓取状态：不满足抓取条件
    TARGET_SELECTED = "selected"  # 已选中目标：当前预抓取目标
```

#### 4.2.2 状态评估算法
- **危险状态判断**：
  - 位置：是否在安全区域外
  - 速度：移动速度是否超过安全阈值
  - 碰撞风险：是否与机械臂路径冲突

- **可抓取性评估**：
  - 位置可达性：机械臂工作空间内
  - 姿态适宜性：物体姿态是否适合抓取
  - 稳定性：目标是否稳定（时序分析）
  - 置信度：检测置信度是否足够高

#### 4.2.3 动态状态转换
- **状态监控**：实时监控目标状态变化
- **转换触发**：基于条件变化自动转换状态
- **状态历史**：维护状态变化历史，用于趋势分析

### 4.3 智能目标选择系统

#### 4.3.1 选择策略
- **优先级排序**：
  1. 置信度最高的可抓取目标
  2. 距离机械臂最近的目标
  3. 最稳定的目标（基于时序分析）
  4. 用户手动指定的目标

- **多目标处理**：
  - 同时维护多个候选目标
  - 动态切换预抓取目标
  - 备选目标管理

#### 4.3.2 预抓取索引管理
- **索引生成**：为选中的目标生成唯一索引
- **索引更新**：目标变化时更新索引
- **索引传递**：将索引信息传递给显示和控制模块

### 4.4 数据输出分发系统

#### 4.4.1 显示数据生成
```python
@dataclass(frozen=True)
class ProcessedDisplayDataEvent(BaseDTO):
    """处理后的显示数据事件"""
    event_type: str = "processed_display_data"
    device_id: str
    frame_id: int
    annotations: List[DisplayAnnotationDTO]  # 显示标注列表
    target_index: Optional[int] = None       # 预抓取目标索引
    processing_stats: Optional[Dict] = None  # 处理统计信息
```

#### 4.4.2 控制数据生成
```python
@dataclass(frozen=True)
class TargetCoordinatesEvent(BaseDTO):
    """目标坐标事件（用于控制模块）"""
    event_type: str = "target_coordinates"
    target_id: str                           # 目标唯一ID
    spatial_coordinates: SpatialCoordinatesDTO  # 3D坐标
    confidence: float                        # 置信度
    grasp_strategy: Optional[str] = None     # 抓取策略建议
    priority: int = 0                        # 优先级
```

### 4.5 坐标变换子模块
*（保持原有设计，待后续详细实现）*

### 4.6 数据滤波子模块

#### 4.6.1 时序数据处理
- **稳定性分析**：分析目标位置的时序稳定性
- **运动预测**：基于历史数据预测目标运动轨迹
- **噪声过滤**：过滤检测数据中的噪声

#### 4.6.2 置信度融合
- **多帧融合**：结合多帧检测结果提高置信度
- **时序一致性**：确保相同目标在时间上的一致性
- **异常检测**：识别和过滤异常检测结果

### 4.7 数据使用策略子模块

#### 4.7.1 安全策略
- **安全区域检查**：确保目标在安全操作范围内
- **碰撞检测**：预测并避免潜在碰撞
- **紧急停止条件**：定义紧急停止的触发条件

#### 4.7.2 效率优化策略
- **路径优化**：选择最优抓取路径的目标
- **批量处理**：支持批量抓取任务的规划
- **资源调度**：合理分配处理资源

### 4.8 坐标修正子模块
*（保持原有设计，待后续详细实现）*

### 4.9 数据处理调度器DTO设计

#### 4.9.1 内部处理DTO
```python
@dataclass(frozen=True)
class ProcessingContextDTO(BaseDTO):
    """处理上下文DTO"""
    session_id: str                    # 处理会话ID
    device_id: str                     # 设备ID
    frame_id: int                      # 帧ID
    raw_detections: List[DetectionDTO] # 原始检测数据
    processing_timestamp: float        # 处理时间戳

@dataclass(frozen=True)
class TargetEvaluationDTO(BaseDTO):
    """目标评估结果DTO"""
    detection_id: str                  # 检测ID
    original_detection: DetectionDTO   # 原始检测数据
    status: DetectionStatus           # 评估状态
    graspability_score: float         # 可抓取性评分
    safety_score: float               # 安全性评分
    priority_score: float             # 优先级评分
    evaluation_timestamp: float       # 评估时间戳
```

### 4.10 对外接口设计

#### 4.10.1 事件发布接口
- **processed_display_data**：向显示模块发布处理后的显示数据
- **target_coordinates**：向控制模块发布目标坐标数据
- **processing_status**：发布处理状态和统计信息

#### 4.10.2 配置接口
- **状态评估参数配置**：动态调整评估算法参数
- **选择策略配置**：切换不同的目标选择策略
- **安全参数配置**：调整安全区域和阈值参数

#### 4.10.3 监控接口
- **处理性能监控**：监控处理延迟和吞吐量
- **目标统计监控**：统计各状态目标数量
- **异常监控**：监控处理异常和错误

---

## 5. 显示模块设计

### 5.1 模块概述

显示模块采用**双数据源架构**，分别处理视频帧数据和显示标注数据，实现高效的实时渲染和丰富的视觉反馈。

#### 5.1.1 核心设计思路
- **数据源分离**：视频帧和显示标注分别从不同事件获取，降低数据传输开销
- **状态驱动渲染**：基于检测目标状态进行差异化视觉呈现
- **多样化显示**：支持不同的显示模式和视觉效果

#### 5.1.2 事件订阅架构
```python
显示模块事件订阅：
├── raw_frame_data: 原始视频帧（仅包含图像数据）
└── processed_display_data: 处理后的显示数据（包含标注信息）
```

### 5.2 双数据流处理机制

#### 5.2.1 视频帧数据流
- **数据来源**：直接从数据采集模块获取`raw_frame_data`事件
- **数据内容**：仅包含视频帧、帧ID、设备MXid
- **处理方式**：作为渲染底图，无需额外处理

#### 5.2.2 显示标注数据流
- **数据来源**：从数据调度器获取`processed_display_data`事件
- **数据内容**：经过处理的检测框、标签、状态信息
- **处理方式**：根据状态信息进行差异化渲染

### 5.3 智能检测框绘制系统

#### 5.3.1 检测目标状态定义
```python
class DetectionStatus(Enum):
    DANGEROUS = "dangerous"        # 危险状态 - 红色边框
    READY_TO_GRASP = "ready"      # 待抓取状态 - 黄色边框
    GRASPABLE = "graspable"       # 可抓取状态 - 绿色边框
    UNGRASPABLE = "ungraspable"   # 无法抓取状态 - 灰色边框
    TARGET_SELECTED = "selected"  # 预抓取目标 - 特殊高亮边框
```

#### 5.3.2 差异化渲染策略
- **危险状态**：红色粗边框，闪烁效果，警告图标
- **待抓取状态**：黄色边框，虚线样式，等待图标
- **可抓取状态**：绿色边框，实线样式，正常显示
- **无法抓取状态**：灰色边框，半透明显示，禁用图标
- **预抓取目标**：特殊颜色（如蓝色），加粗边框，目标标识

#### 5.3.3 动态视觉效果
- **状态转换动画**：边框颜色渐变过渡
- **预抓取目标高亮**：边框闪烁或呼吸灯效果
- **置信度可视化**：边框透明度反映置信度

### 5.4 显示数据DTO设计

#### 5.4.1 简化的视频帧事件DTO
```python
@dataclass(frozen=True)
class SimpleFrameDataEvent(BaseDTO):
    """简化的视频帧事件DTO（仅用于显示）"""
    event_type: str = field(default="raw_frame_data", init=False)
    device_id: str  # 设备MXid
    frame_id: int   # 帧ID
    rgb_frame: Optional[Any] = None    # RGB图像数据
    depth_frame: Optional[Any] = None  # 深度图像数据（可选）
    timestamp: Optional[float] = None  # 时间戳
```

#### 5.4.2 显示标注DTO
```python
@dataclass(frozen=True)
class DisplayAnnotationDTO(BaseDTO):
    """显示标注数据传输对象"""
    detection_id: str           # 检测ID
    label: str                  # 检测标签
    confidence: float           # 置信度
    bbox: BoundingBoxDTO        # 边界框
    status: DetectionStatus     # 检测状态
    is_target: bool = False     # 是否为预抓取目标
    
@dataclass(frozen=True)
class ProcessedDisplayDataEvent(BaseDTO):
    """处理后的显示数据事件DTO"""
    event_type: str = field(default="processed_display_data", init=False)
    device_id: str              # 设备ID
    frame_id: int               # 对应的帧ID
    annotations: List[DisplayAnnotationDTO]  # 显示标注列表
    target_index: Optional[int] = None       # 预抓取目标索引
    timestamp: Optional[float] = None        # 时间戳
```

### 5.5 渲染管道设计

#### 5.5.1 渲染流程
```python
渲染管道：
1. 接收视频帧 → 2. 接收显示标注 → 3. 帧ID匹配 → 4. 状态渲染 → 5. 输出显示
```

#### 5.5.2 帧同步机制
- **帧ID匹配**：确保视频帧和标注数据的时间同步
- **缓存策略**：短时间缓存未匹配的数据
- **超时处理**：超时数据自动清理，防止内存泄漏

### 5.6 多模式显示支持

#### 5.6.1 显示模式定义
- **仅RGB模式**：显示彩色图像和检测标注
- **RGB+深度模式**：分屏或叠加显示彩色和深度图像
- **调试模式**：额外显示坐标信息、置信度数值等

#### 5.6.2 状态信息面板
- **系统状态**：显示各模块运行状态
- **检测统计**：当前帧检测目标数量、各状态统计
- **抓取进度**：当前抓取任务进度和状态

### 5.7 性能优化策略

#### 5.7.1 渲染优化
- **帧率控制**：根据显示需求动态调整渲染帧率
- **ROI渲染**：仅重绘有变化的区域
- **GPU加速**：使用OpenGL/OpenCV的GPU功能

#### 5.7.2 内存管理
- **缓存池**：复用渲染资源，减少内存分配
- **数据清理**：及时清理过期的帧数据和标注信息
- **内存监控**：监控内存使用，防止内存泄漏

### 5.8 用户交互功能（预留）

#### 5.8.1 交互功能
- **手动目标选择**：点击选择预抓取目标
- **显示模式切换**：实时切换不同显示模式
- **参数调整**：动态调整显示参数（亮度、对比度等）

#### 5.8.2 调试功能
- **坐标显示开关**：可选显示3D坐标信息
- **置信度显示**：可选显示检测置信度数值
- **帧率显示**：实时显示处理帧率

---

## 6. CAN通信模块设计

### 6.1 模块概述
*（待补充：CAN通信模块的整体架构和通信协议）*

### 6.2 总线监听机制
*（待补充：CAN总线的持续监听和数据接收实现）*

### 6.3 数据发送接口
*（待补充：向CAN总线发送数据的标准接口）*

### 6.4 通信协议定义
*（待补充：与外部设备通信的协议格式和数据结构）*

### 6.5 控制器模块通信接口
*（待补充：为控制器模块预留的专用通信接口）*

### 6.6 异常处理和重试机制
*（待补充：通信异常的处理和自动重试策略）*

### 6.7 CAN通信模块DTO设计
*（待补充：CAN通信相关的数据传输对象设计）*

---

## 7. 控制器模块设计

### 7.1 模块概述
*（待补充：控制器模块的整体架构和控制策略）*

### 7.2 抓取决策子模块
*（待补充：基于检测数据的抓取位置和策略决策）*

### 7.3 轨迹规划子模块
*（待补充：机械臂运动轨迹的规划和优化）*

### 7.4 传感器数据获取子模块
*（待补充：通过CAN模块获取关节角度、力矩等传感器数据）*

### 7.5 实时闭环控制
*（待补充：基于传感器反馈的实时轨迹修正和控制）*

### 7.6 控制器模块DTO设计
*（待补充：控制器模块相关的数据传输对象设计）*

### 7.7 安全机制和异常处理
*（待补充：运动安全检查、碰撞检测、异常恢复等）*

---

## 8. 事件总线模块设计

### 8.1 模块概述和线程模型选择

#### 8.1.1 模块定位
事件总线作为独立的基础设施模块，专门负责系统内各线程间的数据传输和通信协调。

#### 8.1.2 线程模型选择
**选择：不使用独立线程**
- **执行模式**: 在发布者线程中同步执行事件分发
- **性能考虑**: 15fps场景下，避免线程切换开销更重要
- **延迟控制**: 同步执行保证延迟可控（< 5ms）
- **复杂度管理**: 避免多线程同步的复杂性

#### 8.1.3 核心设计目标
- **高效性**: 满足15fps数据流的性能要求
- **可靠性**: 保证关键数据不丢失，错误隔离
- **扩展性**: 支持动态调整数据流路由和分支扩展
- **易用性**: 提供简单统一的发布/订阅接口

### 8.2 核心接口设计

#### 8.2.1 对外接口规范
```python
class EventBus:
    """事件总线核心接口"""
    
    # 发布接口
    def publish(self, event_type: str, data: any, priority: Priority = Priority.NORMAL) -> bool
    
    # 订阅接口
    def subscribe(self, event_type: str, callback: Callable) -> str  # 返回订阅ID
    def unsubscribe(self, subscription_id: str) -> bool
    
    # 配置接口
    def configure(self, **config_options) -> None
    def get_metrics(self) -> EventBusMetrics
```

#### 8.2.2 使用示例
```python
# 发布事件
event_bus.publish("raw_detection_data", detection_dto, Priority.HIGH)

# 订阅事件
def handle_detection_data(data):
    # 处理检测数据
    pass

subscription_id = event_bus.subscribe("raw_detection_data", handle_detection_data)
```

### 8.3 高性能实现策略

#### 8.3.1 数据传输优化
- **大数据零拷贝**: 视频帧通过共享内存引用传递
- **小数据直接拷贝**: 检测坐标等小数据直接复制，简单可靠
- **内存池管理**: 预分配常用DTO对象，避免频繁分配
- **引用计数**: 自动管理共享数据的生命周期

#### 8.3.2 性能目标
- **事件分发延迟**: < 5ms（同步执行）
- **内存开销**: < 50MB（包含对象池和缓冲区）
- **CPU占用**: < 5%（15fps场景下）
- **吞吐量**: 支持每秒100+事件处理

### 8.4 事件类型定义
*（待补充：系统中所有事件类型的完整定义）*

### 8.5 背压处理和流量控制
*（待补充：队列满时的丢帧策略和流量控制机制）*

### 8.6 监控和诊断
*（待补充：事件处理性能监控、异常诊断和告警）*

### 8.7 事件总线DTO设计
*（待补充：事件总线相关的数据传输对象设计）*

---

## 9. 系统集成和部署

### 9.1 模块间集成测试
*（待补充：各模块集成测试的策略和实现）*

### 9.2 性能基准测试
*（待补充：系统性能基准和优化目标）*

### 9.3 部署配置管理
*（待补充：系统配置文件、环境变量、部署脚本等）*

### 9.4 监控和日志
*（待补充：系统运行监控、日志收集和分析）*

### 9.5 故障恢复和容错
*（待补充：系统级别的故障恢复和容错机制）*

---

## 9. 日志管理系统设计

### 9.1 系统概述
*（预留章节：在核心数据流实现完成后开发）*

日志管理系统作为重要的支撑基础设施，将提供统一的日志记录、收集、存储和分析功能。主要特性包括：
- 标准化日志接口，支持各模块统一调用
- 多线程安全的异步日志处理
- 结构化日志格式，便于分析和监控
- 性能指标收集和实时监控
- 集中式日志存储和管理
- 与事件总线和配置系统的深度集成

### 9.2 架构设计
*（待实现：标准化日志接口和分层架构）*

#### 9.2.1 核心组件
- **LoggerFactory**: 日志器工厂，负责创建和管理各模块日志器
- **StructuredFormatter**: 结构化日志格式化器
- **AsyncHandler**: 异步日志处理器，确保高性能
- **MetricsCollector**: 性能指标收集器
- **LogAggregator**: 日志聚合和分析组件

#### 9.2.2 标准化接口
- **基础接口**: 兼容标准logging的基本功能
- **增强接口**: 结构化数据、性能监控、事务日志
- **业务接口**: 领域特定的日志记录方法
- **上下文管理**: 自动性能监控和事务追踪

### 9.3 数据模型设计
*（待实现：基于DTO的日志数据结构）*

#### 9.3.1 核心DTO
- **LogEntryDTO**: 标准日志条目数据传输对象
- **PerformanceMetricDTO**: 性能指标数据传输对象
- **LogConfigDTO**: 日志配置数据传输对象

### 9.4 集成策略
*（待实现：与现有系统的无缝集成）*

#### 9.4.1 事件总线集成
- 关键日志自动发布为事件
- 基于事件的日志聚合和分析
- 异常日志触发系统告警

#### 9.4.2 配置系统集成
- 动态日志级别调整
- 环境特定的日志配置
- 运行时配置热更新

### 9.5 性能优化
*（待实现：高性能日志处理）*

#### 9.5.1 异步处理
- 队列缓冲避免阻塞主线程
- 批量写入提高IO效率
- 智能过滤减少不必要的日志

#### 9.5.2 存储优化
- 日志文件轮转和压缩
- 分级存储策略
- 自动清理过期日志

### 9.6 运维支持
*（待实现：生产环境运维功能）*

#### 9.6.1 监控告警
- 关键指标实时监控
- 基于日志的自动告警
- 系统健康状态报告

#### 9.6.2 日志分析
- 结构化查询和搜索
- 性能趋势分析
- 异常模式识别

### 9.7 实现计划
*（待规划：开发优先级和时间安排）*

**实现优先级**：
1. **P1**: 基础日志接口和异步处理（核心数据流完成后立即实现）
2. **P2**: 结构化日志和性能监控（系统稳定后添加）
3. **P3**: 高级分析和运维功能（生产部署前完成）

**依赖关系**：
- 依赖DTO基类和事件总线系统
- 需要配置管理系统支持
- 与各功能模块的集成点预留

---

## 10. 开发计划和里程碑

### 10.1 当前开发进度（2025-10-08更新）

#### 10.1.1 已完成模块 ✅

**阶段1：核心基础设施（100%完成）**

1. **DTO系统（core/dto/）** ✅
   - `base_dto.py`: DTO基类，包含验证机制、序列化支持、版本兼容
     - ✨ **性能优化**：验证从自动改为手动调用（`validate()`方法）
     - 运行时零验证开销，极致性能，适合实时系统
     - 验证前置到单元测试和冒烟测试中
   - `detection_dto.py`: 检测相关DTO完整实现（运行时数据）
     - SpatialCoordinatesDTO（空间坐标）
     - BoundingBoxDTO（边界框）
     - DetectionDTO（检测结果）
     - DeviceDetectionDataDTO（设备检测数据）
     - VideoFrameDTO（视频帧数据）
     - OAKDataCollectionDTO（数据采集综合DTO）
     - RawFrameDataEvent（原始帧数据事件）
     - RawDetectionDataEvent（原始检测数据事件）
   - ✨ **配置DTO系统（config_dto/）** - 扁平化架构 ✅
     - **架构特点**：扁平化文件组织，简洁高效
     - **文件结构**（仅8个文件，1层目录）：
       - `enums.py`: 所有枚举类型（DeviceRole、DeviceType、ConnectionStatus）
       - `device_binding_dto.py`: 设备绑定相关（合并3个DTO）
         - DeviceRoleBindingDTO（角色绑定）
         - DeviceMetadataDTO（设备元数据）
         - DeviceHistoryDTO（操作历史）
       - `oak_config_dto.py`: OAK模块配置
       - `data_processing_config_dto.py`: 数据处理模块配置
         - CoordinateTransformConfigDTO（坐标变换）
         - FilterConfigDTO（滤波）
         - DataProcessingConfigDTO（容器）
       - `can_config_dto.py`: CAN模块配置
       - `display_config_dto.py`: 显示模块配置
       - `device_manager_config_dto.py`: 顶层管理配置
       - `__init__.py`: 统一导出
     - **设计优势**：
       - 文件组织：8个文件 vs 旧版20个文件（减少60%）
       - 目录层级：1层 vs 旧版4层（减少75%）
       - 易于维护：扁平结构，找文件更快
       - 易于扩展：新增模块只需添加一个文件
       - 代码量合理：约643行，功能完整
   - `device_config_dto.py`: 旧版设备配置DTO（待清理）

2. **事件总线系统（core/event_bus/）** ✅
   - `event_types.py`: 事件类型和优先级定义
     - EventType类：定义所有系统事件类型（已优化，移除内部处理步骤事件）
     - Priority枚举：事件优先级定义
   - ✨ `event_bus.py`: 事件总线核心实现（新增）
     - 高性能发布-订阅机制
     - 线程安全（使用RLock保护）
     - 错误隔离（单个订阅者异常不影响其他）
     - 同步执行（在发布者线程中直接调用回调）
     - 性能目标：<5ms分发延迟

3. **数据采集模块基础（modules/data_collector/）** ✅
   - `config_manager.py`: 系统配置管理器（670+行）
     - 配置的序列化和反序列化
     - 设备发现和状态同步
     - 配置备份、恢复和验证
     - 为各模块提供配置分发接口
   - `device_discovery.py`: 设备发现工具

4. **测试系统** ✅
   - 单元测试（tests/unit/）：
     - `test_base_dto.py`: BaseDTO单元测试（已更新，使用validate()）
     - `test_detection_dto.py`: 检测DTO单元测试（已更新，使用validate()）
     - `test_device_config_dto.py`: 设备配置DTO单元测试
     - ✨ `test_event_bus.py`: 事件总线单元测试（新增）
       - 基础功能测试（订阅/发布/取消订阅）
       - 多事件类型测试
       - 错误隔离测试
       - 线程安全性测试
       - 性能基准测试
   - 集成测试（tests/integration/）：
     - ✨ `test_smoke.py`: DTO冒烟测试框架（新增）
       - 所有DTO的创建和验证测试
       - 批量验证性能测试
       - 无效数据检测测试

5. **示例和文档** ✅
   - `examples/dto_example.py`: DTO使用示例
   - `examples/config_example.py`: 配置系统示例
   - `examples/config_manager_usage.py`: 配置管理器使用示例
   - `examples/device_manager_example.py`: 设备管理器示例
   - `examples/future_module_integration.py`: 未来模块集成示例
   - ✨ `examples/event_bus_example.py`: 事件总线使用示例（新增）
     - 基本发布-订阅示例
     - 实际场景：数据采集→显示
     - 多模块协作示例
     - 错误隔离演示
   - ✨ `examples/config_dto_simple_example.py`: 配置DTO简单示例（扁平化版本）
     - 基本配置创建
     - 设备角色绑定
     - 设备元数据管理
     - 坐标变换配置
     - 模块配置访问
     - 配置序列化
   - `MIGRATION_GUIDE.md`: 系统迁移指南
   - ✨ `plan/BaseDTO基类说明.md`: BaseDTO基类详细说明（新增）
   - ✨ `plan/检测数据DTO说明.md`: 运行时检测数据DTO说明（新增）
   - ✨ `plan/配置DTO说明.md`: 配置数据DTO说明（新增）
   - ✨ `plan/DTO验证策略优化总结.md`: DTO性能优化文档（新增）
   - ✨ `plan/事件总线实现总结.md`: 事件总线实现文档（新增）
   - ✨ `plan/设备角色绑定架构设计方案.md`: 设备角色绑定架构文档（新增）
   - ✨ `plan/软件功能设想与架构设计.md`: 软件功能设想文档（新增）

#### 10.1.2 进行中模块 🚧

**阶段2：数据采集模块完整实现（30%完成）**

已完成：
- ✅ 配置管理系统（SystemConfigManager）
- ✅ 设备发现功能

待完成：
- ⏳ `device_manager.py`: 设备连接和状态管理（已删除，待重构）
- ⏳ `oak_data_collector.py`: OAK数据采集器主类
- ⏳ `pipeline_manager.py`: DepthAI Pipeline管理器
- ⏳ `detection_processor.py`: 检测数据处理器
- ⏳ `video_processor.py`: 视频数据处理器
- ⏳ `data_buffer.py`: 数据缓冲管理

#### 10.1.3 未开始模块 📋

**阶段3：事件总线完整实现（已完成 → 移至已完成模块）**
- ~~事件总线已完成MVP版本~~

**注：事件总线后续优化（可选）**
- ⏳ `subscription_manager.py`: 独立的订阅管理器（可选）
- ⏳ `metrics.py`: 详细的性能监控和指标（可选）
- ⏳ 优先级队列支持（当前已预留Priority参数）
- ⏳ 背压处理机制

**阶段4：数据调度器模块（0%完成）**
- ⏳ `data_scheduler.py`: 数据调度器主类
- ⏳ `coordinate_transformer.py`: 坐标变换器
- ⏳ 滤波器子系统（filters/）
- ⏳ 修正器子系统（correctors/）
- ⏳ 策略子系统（strategies/）

**阶段5：显示模块（0%完成）**
- ⏳ `display_manager.py`: 显示管理器主类
- ⏳ `frame_renderer.py`: 帧渲染器
- ⏳ UI组件和显示模式

**阶段6：CAN通信模块（0%完成）**
- ⏳ `can_communicator.py`: CAN通信器主类
- ⏳ 总线监听和消息解析

**阶段7：动作控制模块（0%完成）**
- ⏳ `motion_controller.py`: 动作控制器主类
- ⏳ 抓取规划和轨迹规划

### 10.2 开发阶段划分

#### 阶段1：核心基础设施（已完成 ✅）
**目标**：建立系统开发的基础框架
- DTO系统设计和实现
- 事件类型定义
- 配置管理基础
- 单元测试框架

**交付物**：
- 完整的DTO类库
- 配置管理系统
- 基础测试用例
- 开发示例和文档

#### 阶段2：数据采集模块（进行中 🚧 - 30%）
**目标**：实现OAK设备的数据采集功能
- 设备连接和管理
- Pipeline创建和管理
- 检测数据处理
- 视频帧处理

**依赖关系**：
- 依赖DTO系统（已完成）
- 依赖配置管理（已完成）

**当前进度**：
- ✅ 配置管理器实现
- ✅ 设备发现功能
- ⏳ 设备管理器重构中
- ⏳ Pipeline管理器待开发

#### 阶段3：事件总线实现（未开始 📋 - 0%）
**目标**：实现高性能的线程间通信机制
- 事件总线核心实现
- 订阅管理系统
- 性能监控

**依赖关系**：
- 依赖事件类型定义（已完成）
- 需要在数据采集模块基本可用后开始

#### 阶段4：数据调度器模块（未开始 📋 - 0%）
**目标**：实现数据处理和调度功能
- 坐标变换
- 数据滤波
- 坐标修正
- 目标选择策略

**依赖关系**：
- 依赖数据采集模块（30%）
- 依赖事件总线（0%）

#### 阶段5：显示模块（未开始 📋 - 0%）
**目标**：实现实时数据可视化
- 视频帧渲染
- 检测结果叠加
- 多模式显示

**依赖关系**：
- 依赖数据采集模块
- 依赖事件总线

#### 阶段6：CAN通信模块（未开始 📋 - 0%）
**目标**：实现CAN总线通信功能
- 总线监听
- 消息解析和发送
- 协议处理

**依赖关系**：
- 可与其他模块并行开发

#### 阶段7：动作控制模块（未开始 📋 - 0%）
**目标**：实现机械臂控制功能
- 抓取决策
- 轨迹规划
- 传感器数据处理

**依赖关系**：
- 依赖数据调度器模块
- 依赖CAN通信模块

### 10.3 里程碑定义

#### 里程碑1：基础框架完成（已达成 ✅）
**时间**：2025-10-08
**交付**：
- DTO系统完整实现
- 配置管理系统完成
- 基础测试和示例

**验收标准**：
- ✅ 所有DTO类通过单元测试
- ✅ 配置系统可正常读写配置文件
- ✅ 提供完整的使用示例

#### 里程碑2：数据采集模块MVP（目标：第1周）
**目标时间**：2025-10-15
**交付**：
- 单设备数据采集功能
- Pipeline基础实现
- 检测数据获取

**验收标准**：
- 能够连接单个OAK设备
- 能够获取检测数据和视频帧
- 通过集成测试

#### 里程碑3：事件总线完成（目标：第2周）
**目标时间**：2025-10-22
**交付**：
- 事件总线核心实现
- 订阅发布机制
- 性能监控

**验收标准**：
- 满足性能指标（<5ms延迟）
- 支持并发订阅/发布
- 通过压力测试

#### 里程碑4：多模块集成（目标：第4周）
**目标时间**：2025-11-05
**交付**：
- 数据采集+数据调度器+显示模块集成
- 完整的数据流通路
- 系统性能优化

**验收标准**：
- 端到端数据流畅通
- 满足实时性要求（15fps）
- 系统稳定运行

#### 里程碑5：系统完整功能（目标：第6周）
**目标时间**：2025-11-19
**交付**：
- 所有模块完成
- 完整的测试覆盖
- 部署文档

**验收标准**：
- 所有功能模块可用
- 测试覆盖率>80%
- 可部署到生产环境

### 10.4 测试策略

#### 10.4.1 单元测试
**范围**：所有独立组件和类
**工具**：pytest
**覆盖率目标**：>80%

**已完成测试**：
- ✅ BaseDTO测试
- ✅ 检测DTO测试
- ✅ 设备配置DTO测试

**待完成测试**：
- ⏳ 事件总线测试
- ⏳ 数据采集模块测试
- ⏳ 数据调度器测试

#### 10.4.2 集成测试
**范围**：模块间交互
**重点**：
- 数据采集+事件总线
- 数据调度器+显示模块
- 完整数据流

#### 10.4.3 性能测试
**指标**：
- 事件分发延迟：<5ms
- 系统帧率：15fps稳定
- CPU占用：<10%
- 内存占用：<100MB

### 10.5 风险评估和应对

#### 10.5.1 技术风险

**风险1：事件总线性能不达标**
- 影响：系统实时性无法保证
- 概率：中
- 应对：提前进行性能测试和优化，准备降级方案

**风险2：多设备管理复杂度**
- 影响：数据采集模块开发周期延长
- 概率：高
- 应对：先实现单设备功能，再扩展多设备

**风险3：DepthAI API不稳定**
- 影响：Pipeline管理可能需要调整
- 概率：低
- 应对：封装抽象层，隔离API变化

#### 10.5.2 进度风险

**风险4：功能范围蔓延**
- 影响：开发周期延长
- 概率：中
- 应对：严格控制MVP范围，非核心功能延后

**风险5：测试不充分**
- 影响：系统稳定性问题
- 概率：中
- 应对：测试驱动开发，持续集成

### 10.6 当前开发重点

#### 短期目标（1-2周）
1. 完成数据采集模块设备管理器重构
2. 实现Pipeline管理器基础功能
3. 实现事件总线核心功能
4. 完成数据采集模块集成测试

#### 中期目标（3-4周）
1. 完成数据调度器模块基础实现
2. 完成显示模块基础实现
3. 实现端到端数据流
4. 性能优化和压力测试

#### 长期目标（5-6周）
1. 完成CAN通信模块
2. 完成动作控制模块
3. 完整系统集成测试
4. 部署和文档完善

