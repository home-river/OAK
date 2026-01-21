# 设计文档：决策层模块

## 概述

决策层模块（DecisionLayer）是数据处理流水线的核心决策组件，嵌入在 DataProcessor 中，负责对滤波后的检测数据进行状态判断和全局决策。该模块采用全局单例模式，通过维护设备级别的状态信息，实现增量更新和线程安全的全局目标选择。

### 核心职责

1. **数据分流**：基于标签映射将检测对象分为人员和物体两类
2. **人员处理**：计算人员距离、管理警告状态机、发布警告事件
3. **物体处理**：判断物体所在区域、维护最近可抓取物体、选择全局待抓取目标
4. **状态管理**：维护设备级别的状态信息，支持状态过期检查
5. **同步接口**：提供线程安全的零延迟接口供 CAN 通信模块访问目标坐标

### 设计原则

- **性能优先**：使用 NumPy 向量化操作，避免 Python 循环
- **线程安全**：使用 RLock 保护全局状态，支持多线程访问
- **事件驱动**：通过事件总线发布警告事件，解耦模块依赖
- **Fail-Fast**：在方法入口验证输入，热路径中信任数据质量
- **单一职责**：每个方法专注于单一功能，便于测试和维护



## 架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        DataProcessor                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    DecisionLayer (单例)                    │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │              decide(device_id, coords, labels)      │  │  │
│  │  │                                                       │  │  │
│  │  │  1. 数据分流 (基于 labels_map)                      │  │  │
│  │  │     ├─→ person_mask                                  │  │  │
│  │  │     └─→ object_mask                                  │  │  │
│  │  │                                                       │  │  │
│  │  │  2. 并行处理                                         │  │  │
│  │  │     ├─→ _process_person() → 人员状态数组            │  │  │
│  │  │     └─→ _process_object() → 物体状态数组            │  │  │
│  │  │                                                       │  │  │
│  │  │  3. 状态合并与转换                                   │  │  │
│  │  │     └─→ states_to_labels() → 枚举列表               │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                             │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │           设备状态管理 (Device States)              │  │  │
│  │  │  {                                                    │  │  │
│  │  │    device_id: {                                      │  │  │
│  │  │      person_state: SAFE/PENDING/ALARM,              │  │  │
│  │  │      person_distance: float,                        │  │  │
│  │  │      t_in: float, t_out: float,                     │  │  │
│  │  │      nearest_object: {coords, distance},            │  │  │
│  │  │      last_update_time: float                        │  │  │
│  │  │    }                                                  │  │  │
│  │  │  }                                                    │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                             │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │      全局目标对象 (Global Target, 线程锁保护)       │  │  │
│  │  │  {                                                    │  │  │
│  │  │    coords: np.ndarray[3],                           │  │  │
│  │  │    distance: float,                                  │  │  │
│  │  │    device_id: str                                    │  │  │
│  │  │  }                                                    │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 事件发布
                              ↓
                    ┌──────────────────────┐
                    │     EventBus         │
                    └──────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ↓                           ↓
        PERSON_WARNING              (其他订阅者)
        (通信模块)
```

### 数据流图

```
设备A滤波数据 ──→ decide(A) ──→ 分流 ──→ _process_person(A) ──→ 人员状态数组A
                                  │                                    │
                                  └──→ _process_object(A) ──→ 物体状态数组A
                                                                       │
                                                                       ↓
                                                              合并 → 状态标签列表A

设备B滤波数据 ──→ decide(B) ──→ 分流 ──→ _process_person(B) ──→ 人员状态数组B
                                  │                                    │
                                  └──→ _process_object(B) ──→ 物体状态数组B
                                                                       │
                                                                       ↓
                                                              合并 → 状态标签列表B

全局目标选择：
  所有设备的最近可抓取物体 ──→ 比较距离 ──→ 选择最近 ──→ 更新全局目标
                                                          │
                                                          ↓
                                              CAN 通信模块读取
                                              (get_target_coords_snapshot)
```



## 组件和接口

### 类设计

#### DecisionLayer 类

```python
class DecisionLayer:
    """
    决策层模块（全局单例）
    
    职责：
    - 接收滤波后的检测数据，进行状态判断和全局决策
    - 维护设备级别的状态信息
    - 发布人员警告事件
    - 提供线程安全的目标坐标访问接口
    """
    
    # 类变量（单例模式）
    _instance: Optional['DecisionLayer'] = None
    _lock: threading.Lock = threading.Lock()
    
    def __init__(
        self,
        event_bus: EventBus,
        labels_map: List[int],
        d_in: float = 3000.0,
        d_out: float = 3200.0,
        T_warn: float = 3.0,
        T_clear: float = 3.0,
        grace_time: float = 0.5,
        danger_y_threshold: float = 1500.0,
        grasp_zone_config: Dict[str, float],
        state_expiration_time: float = 1.0
    ):
        """
        初始化决策层
        
        Args:
            event_bus: 事件总线实例
            labels_map: 人员标签列表（例如 [0] 表示 YOLO label 0 是人员）
            d_in: 进入危险区距离阈值（mm）
            d_out: 离开危险区距离阈值（mm）
            T_warn: 警告触发时间阈值（秒）
            T_clear: 警告清除时间阈值（秒）
            grace_time: 目标消失宽限期（秒）
            danger_y_threshold: 危险区 y 坐标绝对值阈值（mm），判断条件为 |y| < danger_y_threshold
            grasp_zone_config: 抓取区域配置（单位：mm）
                矩形模式: {"mode": "rect", "x_min": ..., "x_max": ..., "y_min": ..., "y_max": ...}
                半径模式: {"mode": "radius", "r_min": ..., "r_max": ...}
            state_expiration_time: 设备状态过期时间（秒）
        """
        pass
    
    # ========== 公共接口 ==========
    
    def decide(
        self,
        device_id: str,
        filtered_coords: np.ndarray,
        filtered_labels: np.ndarray
    ) -> List[DetectionStatusLabel]:
        """
        主方法：处理单个设备的滤波数据
        
        Args:
            device_id: 设备ID
            filtered_coords: 滤波后的坐标矩阵，形状 (N, 3)，dtype=float32
            filtered_labels: 滤波后的标签数组，形状 (N,)，dtype=int32
        
        Returns:
            状态标签列表，长度 N
        
        Raises:
            ValueError: 输入数据格式错误
        """
        pass
    
    @classmethod
    def get_instance(cls) -> 'DecisionLayer':
        """
        获取决策层单例实例
        
        Returns:
            DecisionLayer 实例
        
        Raises:
            RuntimeError: 实例尚未初始化
        """
        pass
    
    def get_target_coords_snapshot(self) -> Optional[np.ndarray]:
        """
        线程安全地获取待抓取目标坐标副本
        
        Returns:
            目标坐标的副本（形状 (3,)），如果不存在则返回 None
        """
        pass
    
    # ========== 私有方法 ==========
    
    def _process_person(
        self,
        device_id: str,
        person_coords: np.ndarray
    ) -> np.ndarray:
        """
        处理人员类数据
        
        Args:
            device_id: 设备ID
            person_coords: 人员坐标矩阵，形状 (M, 3)
        
        Returns:
            人员状态数组，形状 (M,)，dtype=int32
        """
        pass
    
    def _process_object(
        self,
        device_id: str,
        object_coords: np.ndarray
    ) -> np.ndarray:
        """
        处理物体类数据
        
        Args:
            device_id: 设备ID
            object_coords: 物体坐标矩阵，形状 (K, 3)
        
        Returns:
            物体状态数组，形状 (K,)，dtype=int32
        """
        pass
    
    def _update_global_target(self) -> None:
        """
        更新全局待抓取目标（线程安全）
        
        从所有未过期的设备状态中选择距离最近的可抓取物体作为全局目标
        """
        pass
    
    def _publish_warning_event(
        self,
        status: PersonWarningStatus,
        device_id: str
    ) -> None:
        """
        发布人员警告事件
        
        Args:
            status: 警告状态（TRIGGERED 或 CLEARED）
            device_id: 设备ID
        """
        pass
    
    def _validate_input(
        self,
        filtered_coords: np.ndarray,
        filtered_labels: np.ndarray
    ) -> None:
        """
        验证输入数据格式
        
        Args:
            filtered_coords: 坐标矩阵
            filtered_labels: 标签数组
        
        Raises:
            ValueError: 输入数据格式错误
        """
        pass
```



### 辅助类和枚举

#### PersonWarningState 枚举

```python
class PersonWarningState(Enum):
    """人员警告状态机状态"""
    SAFE = "safe"          # 安全状态
    PENDING = "pending"    # 潜在危险（正在累计时间）
    ALARM = "alarm"        # 危险告警
```

#### PersonWarningStatus 枚举

```python
class PersonWarningStatus(Enum):
    """人员警告事件状态"""
    TRIGGERED = "triggered"  # 警告触发
    CLEARED = "cleared"      # 警告清除
```

#### DeviceState 数据类

```python
@dataclass
class DeviceState:
    """设备状态信息"""
    
    # 人员相关状态
    person_warning_state: PersonWarningState = PersonWarningState.SAFE
    person_distance: Optional[float] = None
    person_last_seen_time: Optional[float] = None
    t_in: float = 0.0   # 危险持续时间
    t_out: float = 0.0  # 离开危险区持续时间
    
    # 物体相关状态
    nearest_object_coords: Optional[np.ndarray] = None
    nearest_object_distance: Optional[float] = None
    
    # 通用状态
    last_update_time: float = 0.0
```

#### GlobalTargetObject 数据类

```python
@dataclass
class GlobalTargetObject:
    """全局待抓取目标对象"""
    coords: np.ndarray      # 坐标，形状 (3,)
    distance: float         # 距离
    device_id: str          # 来源设备ID
```

### 接口规范

#### 输入接口

**decide() 方法**

- **输入**：
  - `device_id: str` - 设备ID
  - `filtered_coords: np.ndarray` - 滤波后的坐标矩阵，形状 (N, 3)，dtype=float32
  - `filtered_labels: np.ndarray` - 滤波后的标签数组，形状 (N,)，dtype=int32

- **输出**：
  - `List[DetectionStatusLabel]` - 状态标签列表，长度 N

- **异常**：
  - `ValueError` - 输入数据格式错误（形状不正确或长度不一致）

#### 输出接口

**get_target_coords_snapshot() 方法**

- **输入**：无

- **输出**：
  - `Optional[np.ndarray]` - 目标坐标的副本（形状 (3,)），如果不存在则返回 None

- **性能要求**：
  - 响应时间 < 0.1ms

#### 事件接口

**PERSON_WARNING 事件**

- **事件类型**：`EventType.PERSON_WARNING`

- **事件数据**：
  ```python
  {
      "status": PersonWarningStatus,  # TRIGGERED 或 CLEARED
      "timestamp": float              # Unix 时间戳
  }
  ```

- **发布时机**：
  - 状态从 PENDING 转为 ALARM 时发布 TRIGGERED
  - 状态从 ALARM 转为 SAFE 时发布 CLEARED



## 数据模型

### 状态标签枚举

```python
class DetectionStatusLabel(IntEnum):
    """
    检测对象状态标签（整数枚举）
    
    使用整数值便于向量化计算：
    - 物体状态：0-99
    - 人员状态：100-199
    """
    
    # 物体状态 (0-99)
    OBJECT_GRASPABLE = 0        # 可抓取
    OBJECT_DANGEROUS = 1        # 危险（过于靠近车体）
    OBJECT_OUT_OF_RANGE = 2     # 超出抓取范围
    OBJECT_PENDING_GRASP = 3    # 待抓取（全局目标）
    
    # 人员状态 (100-199)
    HUMAN_SAFE = 100            # 安全
    HUMAN_DANGEROUS = 101       # 危险（距离过近）
```

### 配置数据模型

决策层配置将作为 `DataProcessingConfigDTO` 的子配置，与坐标变换、滤波配置统一管理。

#### 配置层次结构

```python
@dataclass(frozen=True)
class DecisionLayerConfigDTO(BaseConfigDTO):
    """
    决策层配置 DTO
    
    作为 DataProcessingConfigDTO 的子配置，管理决策层的所有参数。
    """
    
    # 标签映射
    person_label_ids: List[int] = field(default_factory=lambda: [0])
    
    # 人员警告配置
    person_warning: PersonWarningConfigDTO = field(default_factory=PersonWarningConfigDTO)
    
    # 物体区域配置
    object_zones: ObjectZonesConfigDTO = field(default_factory=ObjectZonesConfigDTO)
    
    # 状态过期时间
    state_expiration_time: float = 1.0  # 秒
    
    def _validate_data(self) -> List[str]:
        """验证配置参数"""
        errors = []
        
        if not isinstance(self.person_label_ids, list):
            errors.append("person_label_ids 必须为列表类型")
        
        errors.extend(validate_numeric_range(
            self.state_expiration_time, 'state_expiration_time',
            min_value=0.1, max_value=10.0
        ))
        
        # 验证子配置
        errors.extend(self.person_warning._validate_data())
        errors.extend(self.object_zones._validate_data())
        
        return errors


@dataclass(frozen=True)
class PersonWarningConfigDTO(BaseConfigDTO):
    """人员警告配置"""
    
    d_in: float = 3.0           # 进入危险区距离（米）
    d_out: float = 3.2          # 离开危险区距离（米）
    T_warn: float = 3.0         # 警告触发时间（秒）
    T_clear: float = 3.0        # 警告清除时间（秒）
    grace_time: float = 0.5     # 目标消失宽限期（秒）
    
    def _validate_data(self) -> List[str]:
        """验证人员警告配置"""
        errors = []
        
        if self.d_out <= self.d_in:
            errors.append("d_out 必须大于 d_in")
        
        errors.extend(validate_numeric_range(
            self.d_in, 'd_in', min_value=0.0, max_value=10.0
        ))
        errors.extend(validate_numeric_range(
            self.d_out, 'd_out', min_value=0.0, max_value=10.0
        ))
        errors.extend(validate_numeric_range(
            self.T_warn, 'T_warn', min_value=0.0, max_value=10.0
        ))
        errors.extend(validate_numeric_range(
            self.T_clear, 'T_clear', min_value=0.0, max_value=10.0
        ))
        errors.extend(validate_numeric_range(
            self.grace_time, 'grace_time', min_value=0.0, max_value=5.0
        ))
        
        return errors


@dataclass(frozen=True)
class ObjectZonesConfigDTO(BaseConfigDTO):
    """
    物体区域配置
    
    定义危险区域和抓取区域的参数。
    注意：所有距离单位为毫米（mm）
    """
    
    danger_y_threshold: float = 1500.0  # 危险区 y 坐标绝对值阈值（mm），判断条件为 |y| < danger_y_threshold
    grasp_zone: GraspZoneConfigDTO = field(default_factory=GraspZoneConfigDTO)
    
    def _validate_data(self) -> List[str]:
        """验证物体区域配置"""
        errors = []
        
        errors.extend(validate_numeric_range(
            self.danger_y_threshold, 'danger_y_threshold',
            min_value=0.0, max_value=2000.0
        ))
        
        errors.extend(self.grasp_zone._validate_data())
        
        return errors


@dataclass(frozen=True)
class GraspZoneConfigDTO(BaseConfigDTO):
    """抓取区域配置"""
    
    mode: str = "rect"  # "rect" 或 "radius"
    
    # 矩形模式参数
    x_min: float = 0.5
    x_max: float = 2.0
    y_min: float = 0.3
    y_max: float = 1.5
    
    # 半径模式参数（可选）
    r_min: Optional[float] = None
    r_max: Optional[float] = None
    
    def _validate_data(self) -> List[str]:
        """验证抓取区域配置"""
        errors = []
        
        if self.mode not in ("rect", "radius"):
            errors.append(f"不支持的抓取区域模式: {self.mode}")
            return errors
        
        if self.mode == "rect":
            if self.x_min >= self.x_max:
                errors.append("x_min 必须小于 x_max")
            if self.y_min >= self.y_max:
                errors.append("y_min 必须小于 y_max")
            
            errors.extend(validate_numeric_range(
                self.x_min, 'x_min', min_value=0.0, max_value=5.0
            ))
            errors.extend(validate_numeric_range(
                self.x_max, 'x_max', min_value=0.0, max_value=5.0
            ))
            errors.extend(validate_numeric_range(
                self.y_min, 'y_min', min_value=0.0, max_value=3.0
            ))
            errors.extend(validate_numeric_range(
                self.y_max, 'y_max', min_value=0.0, max_value=3.0
            ))
        
        elif self.mode == "radius":
            if self.r_min is None or self.r_max is None:
                errors.append("半径模式需要 r_min 和 r_max")
            elif self.r_min >= self.r_max:
                errors.append("r_min 必须小于 r_max")
            else:
                errors.extend(validate_numeric_range(
                    self.r_min, 'r_min', min_value=0.0, max_value=5.0
                ))
                errors.extend(validate_numeric_range(
                    self.r_max, 'r_max', min_value=0.0, max_value=5.0
                ))
        
        return errors


@dataclass(frozen=True)
class DataProcessingConfigDTO(BaseConfigDTO):
    """
    数据处理模块配置（容器）
    
    管理坐标变换、滤波、决策层等所有数据处理相关配置。
    """
    
    # 坐标变换配置
    coordinate_transforms: Dict[DeviceRole, CoordinateTransformConfigDTO] = field(default_factory=dict)
    
    # 滤波配置
    filter_config: FilterConfigDTO = field(default_factory=FilterConfigDTO)
    
    # 决策层配置
    decision_layer_config: DecisionLayerConfigDTO = field(default_factory=DecisionLayerConfigDTO)
    
    # 模块级配置
    enable_data_logging: bool = False
    processing_thread_priority: int = 5
    
    def _validate_data(self) -> List[str]:
        """验证所有子配置"""
        errors = []
        
        # 验证坐标变换
        for role, transform in self.coordinate_transforms.items():
            errors.extend(transform._validate_data())
        
        # 验证滤波配置
        errors.extend(self.filter_config._validate_data())
        
        # 验证决策层配置
        errors.extend(self.decision_layer_config._validate_data())
        
        return errors
```

#### 配置文件位置

决策层配置将存储在 `config/data_processing.json` 中，与其他数据处理配置统一管理：

```json
{
  "data_processing": {
    "coordinate_transforms": {
      "left": {
        "role": "left",
        "translation_x": 100.0,
        "translation_y": 0.0,
        "translation_z": 0.0,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0
      },
      "right": {
        "role": "right",
        "translation_x": -100.0,
        "translation_y": 0.0,
        "translation_z": 0.0,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0
      }
    },
    "filter_config": {
      "filter_type": "moving_average",
      "moving_average_config": {
        "window_size": 10
      }
    },
    "decision_layer_config": {
      "person_label_ids": [0],
      "person_warning": {
        "d_in": 3000.0,
        "d_out": 3200.0,
        "T_warn": 3.0,
        "T_clear": 3.0,
        "grace_time": 0.5
      },
      "object_zones": {
        "danger_y_threshold": 1500.0,
        "grasp_zone": {
          "mode": "rect",
          "x_min": 500.0,
          "x_max": 2000.0,
          "y_min": 300.0,
          "y_max": 1500.0
        }
      },
      "state_expiration_time": 1.0
    },
    "enable_data_logging": false,
    "processing_thread_priority": 5
  }
}
```

### 内部数据结构

#### 设备状态字典

```python
# 类型：Dict[str, DeviceState]
# 键：device_id（设备ID）
# 值：DeviceState 对象

_device_states: Dict[str, DeviceState] = {}
```

#### 全局目标对象

```python
# 类型：Optional[GlobalTargetObject]
# 使用 RLock 保护

_global_target_object: Optional[GlobalTargetObject] = None
_target_lock: threading.RLock = threading.RLock()
```



## 正确性属性

属性（Property）是一种特征或行为，应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的形式化陈述。属性是人类可读规范和机器可验证正确性保证之间的桥梁。

以下正确性属性基于需求文档的验收标准，每个属性都使用"对于所有"（for all）的形式表达，以便通过基于属性的测试进行验证。

### 属性 1：输出长度与输入一致性

*对于任意*设备ID、滤波后的坐标矩阵和标签数组，当调用 decide() 方法时，返回的状态标签列表长度应该与输入检测对象数量完全一致，且第 i 个状态标签对应第 i 个检测对象。

**验证需求**：1.2, 1.9, 3.8, 17.1, 17.2

**测试策略**：
- 生成随机长度的坐标矩阵和标签数组
- 调用 decide() 方法
- 验证返回列表长度 == 输入长度
- 验证索引对应关系（通过标记特定对象验证）

### 属性 2：数据分流正确性

*对于任意*标签数组和标签映射配置，当执行数据分流时，所有标签在人员标签列表中的对象应该被识别为人员，所有标签不在人员标签列表中的对象应该被识别为物体，且两个集合互不重叠。

**验证需求**：2.6, 2.7

**测试策略**：
- 生成随机标签数组和 labels_map
- 执行分流逻辑
- 验证 person_mask 中的所有标签都在 labels_map 中
- 验证 object_mask 中的所有标签都不在 labels_map 中
- 验证 person_mask 和 object_mask 互补（person_mask | object_mask == all）

### 属性 3：状态数组到枚举列表转换正确性

*对于任意*整数状态数组，当调用 states_to_labels() 函数时，返回的枚举列表长度应该与输入数组长度一致，且每个枚举值的整数值应该等于对应的输入整数。

**验证需求**：3.6

**测试策略**：
- 生成随机的有效状态整数数组（0, 1, 2, 3, 100, 101）
- 调用 states_to_labels()
- 验证返回列表长度 == 输入数组长度
- 验证每个枚举的 int 值 == 对应的输入整数

### 属性 4：人员距离计算正确性

*对于任意*人员坐标矩阵，当计算人员到原点的距离时，每个距离值应该等于对应坐标的欧几里得距离 sqrt(x² + y² + z²)。

**验证需求**：4.2

**测试策略**：
- 生成随机人员坐标矩阵
- 调用 _process_person() 或距离计算函数
- 手动计算欧几里得距离
- 验证计算结果与手动计算一致（允许浮点误差）

### 属性 5：人员距离阈值判断正确性

*对于任意*人员坐标，当人员距离 >= d_out 时，在 SAFE 状态下应该保持 SAFE 状态（状态值 100）；当人员距离 < d_in 时，在 SAFE 状态下应该转换为 PENDING 状态并开始累计时间。

**验证需求**：4.3, 4.4, 5.2

**测试策略**：
- 生成距离 >= d_out 的人员坐标
- 验证状态为 HUMAN_SAFE (100)
- 生成距离 < d_in 的人员坐标
- 验证状态转换逻辑正确

### 属性 6：人员警告状态机转换正确性

*对于任意*设备状态，当状态为 PENDING 且 t_in >= T_warn 时，状态应该转换为 ALARM；当状态为 ALARM 且 t_out >= T_clear 时，状态应该转换为 SAFE 并重置时间计数器。

**验证需求**：5.3, 5.6

**测试策略**：
- 设置初始状态为 PENDING，t_in = T_warn
- 调用 _process_person()
- 验证状态转换为 ALARM
- 设置状态为 ALARM，t_out = T_clear
- 验证状态转换为 SAFE，t_in 和 t_out 被重置

### 属性 7：人员警告事件发布正确性

*对于任意*设备，当人员警告状态从 PENDING 转为 ALARM 时，应该发布一次 PERSON_WARNING 事件（状态为 TRIGGERED）；当状态从 ALARM 转为 SAFE 时，应该发布一次 PERSON_WARNING 事件（状态为 CLEARED）。

**验证需求**：6.1, 6.2, 6.5

**测试策略**：
- 模拟状态从 PENDING 转为 ALARM
- 验证 PERSON_WARNING 事件被发布，status == TRIGGERED
- 验证事件只发布一次
- 模拟状态从 ALARM 转为 SAFE
- 验证 PERSON_WARNING 事件被发布，status == CLEARED
- 验证事件只发布一次

### 属性 8：物体区域判断正确性

*对于任意*物体坐标，当 |y| < danger_y_threshold 时，状态应该为 OBJECT_DANGEROUS (1)；当物体在抓取区域内时，状态应该为 OBJECT_GRASPABLE (0)；当物体在其他区域时，状态应该为 OBJECT_OUT_OF_RANGE (2)。

**验证需求**：7.3, 7.4, 7.5

**测试策略**：
- 生成 |y| < danger_y_threshold 的物体坐标
- 验证状态为 OBJECT_DANGEROUS (1)
- 生成抓取区域内的物体坐标
- 验证状态为 OBJECT_GRASPABLE (0)
- 生成抓取区域外的物体坐标
- 验证状态为 OBJECT_OUT_OF_RANGE (2)

### 属性 9：最近可抓取物体选择正确性

*对于任意*设备的可抓取物体集合，当存在多个可抓取物体时，选择的最近物体应该是距离最小的物体；当选择全局目标时，应该从所有未过期设备的最近物体中选择距离最小的。

**验证需求**：8.3, 9.3

**测试策略**：
- 生成多个可抓取物体坐标
- 调用 _process_object()
- 手动计算每个物体的距离
- 验证选择的物体距离 == min(所有距离)
- 模拟多个设备的最近物体
- 验证全局目标是距离最小的

### 属性 10：待抓取目标状态标记正确性

*对于任意*物体坐标集合，当物体是当前的全局待抓取目标时，该物体的状态值应该被修改为 OBJECT_PENDING_GRASP (3)，而其他可抓取物体保持 OBJECT_GRASPABLE (0)。

**验证需求**：9.6

**测试策略**：
- 生成多个可抓取物体
- 设置全局目标为其中一个
- 调用 _process_object()
- 验证目标物体状态 == OBJECT_PENDING_GRASP (3)
- 验证其他物体状态 == OBJECT_GRASPABLE (0)

### 属性 11：设备状态过期处理正确性

*对于任意*设备状态，当设备的最后更新时间超过过期阈值（默认 1 秒）时，该设备的最近可抓取物体状态应该被清空（设置为 None），且不应该参与全局目标选择。

**验证需求**：11.3, 11.4

**测试策略**：
- 设置设备状态，last_update_time = 当前时间 - 2 秒
- 调用全局目标选择逻辑
- 验证该设备的最近物体状态被清空
- 验证该设备不参与全局目标选择

### 属性 12：目标坐标副本返回正确性

*对于任意*全局目标对象，当调用 get_target_coords_snapshot() 时，如果存在目标，返回的数组应该是目标坐标的副本（修改返回值不影响内部状态）；如果不存在目标，应该返回 None。

**验证需求**：13.3, 13.4

**测试策略**：
- 设置全局目标对象
- 调用 get_target_coords_snapshot()
- 修改返回的数组
- 验证内部目标坐标未被修改（副本隔离）
- 清空全局目标
- 验证返回 None

### 属性 13：输入验证正确性

*对于任意*输入数据，当坐标数组形状不是 (N, 3) 或标签数组长度与坐标数组第一维度不一致时，decide() 方法应该在入口处抛出 ValueError 异常。

**验证需求**：16.1

**测试策略**：
- 生成形状错误的坐标数组（如 (N, 2) 或 (N, 4)）
- 验证抛出 ValueError
- 生成长度不一致的标签数组
- 验证抛出 ValueError



## 错误处理

### 错误处理策略

决策层采用**性能优先的 Fail-Fast 策略**：

1. **入口验证**：在 decide() 方法入口处进行一次性验证
   - 验证坐标数组形状为 (N, 3)
   - 验证标签数组长度与坐标数组一致
   - 验证失败立即抛出 ValueError

2. **热路径信任**：在向量化计算路径中不进行数据有效性检查
   - 不检查 NaN 或 Inf
   - 不使用 try-except 包裹计算逻辑
   - 信任滤波模块的输出质量

3. **异常传播**：如果数据异常导致计算错误，让异常自然抛出
   - 由上层模块（DataProcessor）捕获和处理
   - 记录详细的错误信息（设备ID、帧ID、错误类型）

### 错误类型和处理

#### 输入验证错误

```python
def _validate_input(
    self,
    filtered_coords: np.ndarray,
    filtered_labels: np.ndarray
) -> None:
    """
    验证输入数据格式
    
    Raises:
        ValueError: 输入数据格式错误
    """
    # 验证坐标数组
    if not isinstance(filtered_coords, np.ndarray):
        raise ValueError("filtered_coords 必须是 np.ndarray 类型")
    
    if filtered_coords.ndim != 2 or filtered_coords.shape[1] != 3:
        raise ValueError(
            f"filtered_coords 形状必须为 (N, 3)，当前形状: {filtered_coords.shape}"
        )
    
    # 验证标签数组
    if not isinstance(filtered_labels, np.ndarray):
        raise ValueError("filtered_labels 必须是 np.ndarray 类型")
    
    if filtered_labels.ndim != 1:
        raise ValueError(
            f"filtered_labels 形状必须为 (N,)，当前形状: {filtered_labels.shape}"
        )
    
    # 验证长度一致性
    if len(filtered_coords) != len(filtered_labels):
        raise ValueError(
            f"坐标数组长度 ({len(filtered_coords)}) 与标签数组长度 "
            f"({len(filtered_labels)}) 不一致"
        )
```

#### 配置验证错误

```python
# 在 DecisionLayerConfig.__post_init__() 中验证
# 如果配置参数无效，抛出 ValueError
```

#### 单例初始化错误

```python
@classmethod
def get_instance(cls) -> 'DecisionLayer':
    """
    获取决策层单例实例
    
    Raises:
        RuntimeError: 实例尚未初始化
    """
    if cls._instance is None:
        raise RuntimeError("DecisionLayer 尚未初始化，请先调用构造函数")
    return cls._instance
```

### 错误日志

虽然热路径中不进行错误检查，但在关键操作点记录日志：

```python
import logging

logger = logging.getLogger(__name__)

# 在入口验证失败时记录
logger.error(
    "输入验证失败: device_id=%s, coords_shape=%s, labels_shape=%s",
    device_id, filtered_coords.shape, filtered_labels.shape
)

# 在状态转换时记录（DEBUG 级别）
logger.debug(
    "人员警告状态转换: device_id=%s, %s -> %s",
    device_id, old_state, new_state
)

# 在事件发布时记录（DEBUG 级别）
logger.debug(
    "发布人员警告事件: device_id=%s, status=%s",
    device_id, status
)
```



## 测试策略

### 双重测试方法

决策层采用**单元测试**和**基于属性的测试**相结合的策略：

- **单元测试**：验证特定示例、边界情况和错误条件
- **基于属性的测试**：验证通用属性在所有输入下都成立

两种测试方法是互补的，共同提供全面的测试覆盖。

### 基于属性的测试

#### 测试框架

使用 **Hypothesis** 作为 Python 的基于属性的测试库。

```python
import hypothesis
from hypothesis import given, strategies as st
import hypothesis.extra.numpy as npst
```

#### 测试配置

每个属性测试至少运行 **100 次迭代**（由于随机化）：

```python
@given(...)
@hypothesis.settings(max_examples=100)
def test_property_X():
    pass
```

#### 测试标记

每个属性测试必须使用注释标记，引用设计文档中的属性：

```python
def test_property_output_length_consistency():
    """
    Feature: decision-layer, Property 1: 输出长度与输入一致性
    
    对于任意设备ID、滤波后的坐标矩阵和标签数组，当调用 decide() 方法时，
    返回的状态标签列表长度应该与输入检测对象数量完全一致。
    """
    pass
```

#### 数据生成策略

```python
# 生成随机坐标矩阵 (N, 3)
coords_strategy = npst.arrays(
    dtype=np.float32,
    shape=npst.array_shapes(min_dims=2, max_dims=2, min_side=0, max_side=50),
    elements=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
).filter(lambda arr: arr.shape[1] == 3)

# 生成随机标签数组 (N,)
def labels_strategy(n):
    return npst.arrays(
        dtype=np.int32,
        shape=(n,),
        elements=st.integers(min_value=0, max_value=10)
    )

# 生成随机设备ID
device_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
    min_size=1,
    max_size=20
)
```

### 单元测试

#### 测试覆盖范围

单元测试应该覆盖：

1. **特定示例**：
   - 典型场景（10-20 个检测对象）
   - 单个对象
   - 多个设备并发处理

2. **边界情况**：
   - 空输入（零个检测对象）
   - 距离阈值边界（d_in, d_out）
   - 时间阈值边界（T_warn, T_clear）
   - 状态过期边界（1 秒）

3. **错误条件**：
   - 输入格式错误
   - 配置参数无效
   - 单例未初始化

4. **集成点**：
   - 事件总线交互
   - 线程安全性
   - 状态持久化

#### 测试示例

```python
def test_decide_empty_input():
    """测试空输入返回空列表"""
    decision_layer = DecisionLayer(...)
    
    coords = np.empty((0, 3), dtype=np.float32)
    labels = np.empty((0,), dtype=np.int32)
    
    result = decision_layer.decide("device_1", coords, labels)
    
    assert result == []

def test_person_distance_threshold_boundary():
    """测试人员距离阈值边界"""
    decision_layer = DecisionLayer(d_in=3.0, d_out=3.2, ...)
    
    # 距离刚好等于 d_out
    coords = np.array([[3.2, 0.0, 0.0]], dtype=np.float32)
    labels = np.array([0], dtype=np.int32)  # 假设 0 是人员标签
    
    result = decision_layer.decide("device_1", coords, labels)
    
    assert result[0] == DetectionStatusLabel.HUMAN_SAFE

def test_invalid_input_shape():
    """测试输入形状错误"""
    decision_layer = DecisionLayer(...)
    
    # 坐标数组形状错误
    coords = np.array([[1.0, 2.0]], dtype=np.float32)  # (1, 2) 而非 (1, 3)
    labels = np.array([0], dtype=np.int32)
    
    with pytest.raises(ValueError, match="形状必须为 \\(N, 3\\)"):
        decision_layer.decide("device_1", coords, labels)
```

### 性能测试

虽然不是功能正确性测试，但应该包含性能基准测试：

```python
def test_decide_performance_typical():
    """测试典型场景性能（10-20 个对象）"""
    decision_layer = DecisionLayer(...)
    
    coords = np.random.rand(15, 3).astype(np.float32)
    labels = np.random.randint(0, 10, size=15, dtype=np.int32)
    
    import time
    start = time.perf_counter()
    
    for _ in range(100):
        decision_layer.decide("device_1", coords, labels)
    
    elapsed = time.perf_counter() - start
    avg_time = elapsed / 100
    
    # 应该在 5ms 内完成
    assert avg_time < 0.005, f"平均处理时间 {avg_time*1000:.2f}ms 超过 5ms"

def test_get_target_coords_snapshot_performance():
    """测试目标坐标获取性能"""
    decision_layer = DecisionLayer(...)
    
    # 设置全局目标
    # ...
    
    import time
    start = time.perf_counter()
    
    for _ in range(1000):
        decision_layer.get_target_coords_snapshot()
    
    elapsed = time.perf_counter() - start
    avg_time = elapsed / 1000
    
    # 应该在 0.1ms 内完成
    assert avg_time < 0.0001, f"平均响应时间 {avg_time*1000:.2f}ms 超过 0.1ms"
```

### 测试组织

```
tests/
├── unit/
│   └── modules/
│       └── data_processing/
│           └── decision_layer/
│               ├── test_decision_layer_basic.py          # 基本功能测试
│               ├── test_decision_layer_person.py         # 人员处理测试
│               ├── test_decision_layer_object.py         # 物体处理测试
│               ├── test_decision_layer_state.py          # 状态管理测试
│               ├── test_decision_layer_events.py         # 事件发布测试
│               ├── test_decision_layer_thread_safety.py  # 线程安全测试
│               └── test_decision_layer_properties.py     # 基于属性的测试
└── integration/
    └── data_processing/
        └── test_decision_layer_integration.py            # 集成测试
```

### 测试覆盖率目标

- **代码覆盖率**：> 90%
- **分支覆盖率**：> 85%
- **属性测试覆盖**：所有 13 个正确性属性



## 实现细节

### 单例模式实现

```python
class DecisionLayer:
    _instance: Optional['DecisionLayer'] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """确保全局唯一实例（线程安全）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, event_bus: EventBus, config: DecisionLayerConfig):
        """防止重复初始化"""
        if hasattr(self, '_initialized'):
            return
        
        # 初始化配置
        self._event_bus = event_bus
        self._config = config
        
        # 初始化状态
        self._device_states: Dict[str, DeviceState] = {}
        
        # 初始化全局目标（线程锁保护）
        self._target_lock = threading.RLock()
        self._global_target_object: Optional[GlobalTargetObject] = None
        
        # 标记已初始化
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'DecisionLayer':
        """获取单例实例"""
        if cls._instance is None:
            raise RuntimeError("DecisionLayer 尚未初始化")
        return cls._instance
```

### decide() 方法实现

```python
def decide(
    self,
    device_id: str,
    filtered_coords: np.ndarray,
    filtered_labels: np.ndarray
) -> List[DetectionStatusLabel]:
    """主方法：处理单个设备的滤波数据"""
    
    # 1. 输入验证（一次性）
    self._validate_input(filtered_coords, filtered_labels)
    
    # 2. 处理空输入
    if len(filtered_coords) == 0:
        return []
    
    # 3. 创建掩码分流
    person_mask = np.isin(filtered_labels, self._config.person_label_ids)
    object_mask = ~person_mask
    
    # 4. 分流并处理
    person_states = self._process_person(device_id, filtered_coords[person_mask])
    object_states = self._process_object(device_id, filtered_coords[object_mask])
    
    # 5. 合并状态数组
    all_states = np.empty(len(filtered_labels), dtype=np.int32)
    all_states[person_mask] = person_states
    all_states[object_mask] = object_states
    
    # 6. 转换为枚举列表
    return states_to_labels(all_states)
```

### _process_person() 方法实现

```python
def _process_person(
    self,
    device_id: str,
    person_coords: np.ndarray
) -> np.ndarray:
    """处理人员类数据"""
    
    # 处理空输入
    if len(person_coords) == 0:
        return np.array([], dtype=np.int32)
    
    # 1. 计算距离（向量化）
    distances = np.sqrt(np.sum(person_coords**2, axis=1))
    
    # 2. 获取或创建设备状态
    if device_id not in self._device_states:
        self._device_states[device_id] = DeviceState()
    
    device_state = self._device_states[device_id]
    current_time = time.time()
    
    # 3. 找到最近的人员
    min_distance = np.min(distances)
    
    # 4. 更新状态机
    old_state = device_state.person_warning_state
    new_state = self._update_person_state_machine(
        device_state, min_distance, current_time
    )
    
    # 5. 发布事件（如果状态转换）
    if old_state != new_state:
        if old_state == PersonWarningState.PENDING and new_state == PersonWarningState.ALARM:
            self._publish_warning_event(PersonWarningStatus.TRIGGERED, device_id)
        elif old_state == PersonWarningState.ALARM and new_state == PersonWarningState.SAFE:
            self._publish_warning_event(PersonWarningStatus.CLEARED, device_id)
    
    # 6. 分配状态值（向量化）
    states = np.where(
        distances >= self._config.d_out,
        DetectionStatusLabel.HUMAN_SAFE,
        np.where(
            distances < self._config.d_in,
            DetectionStatusLabel.HUMAN_DANGEROUS,
            # 中间区域根据状态机决定
            DetectionStatusLabel.HUMAN_DANGEROUS if new_state == PersonWarningState.ALARM
            else DetectionStatusLabel.HUMAN_SAFE
        )
    )
    
    return states.astype(np.int32)
```

### _process_object() 方法实现

```python
def _process_object(
    self,
    device_id: str,
    object_coords: np.ndarray
) -> np.ndarray:
    """处理物体类数据"""
    
    # 处理空输入
    if len(object_coords) == 0:
        return np.array([], dtype=np.int32)
    
    # 1. 判断区域（向量化）
    x = object_coords[:, 0]
    y = object_coords[:, 1]
    z = object_coords[:, 2]
    
    # 危险区判断（使用绝对值）
    is_dangerous = np.abs(y) < self._config.danger_y_threshold
    
    # 抓取区判断
    if self._config.grasp_zone_mode == "rect":
        is_graspable = (
            (x > self._config.grasp_x_min) & (x < self._config.grasp_x_max) &
            (np.abs(y) > self._config.grasp_y_min) & (np.abs(y) < self._config.grasp_y_max) &
            ~is_dangerous
        )
    else:  # radius mode
        distances = np.sqrt(x**2 + y**2 + z**2)
        is_graspable = (
            (distances > self._config.grasp_r_min) &
            (distances < self._config.grasp_r_max) &
            ~is_dangerous
        )
    
    # 分配初始状态
    states = np.where(
        is_dangerous,
        DetectionStatusLabel.OBJECT_DANGEROUS,
        np.where(
            is_graspable,
            DetectionStatusLabel.OBJECT_GRASPABLE,
            DetectionStatusLabel.OBJECT_OUT_OF_RANGE
        )
    )
    
    # 2. 更新设备最近可抓取物体
    graspable_indices = np.where(is_graspable)[0]
    if len(graspable_indices) > 0:
        graspable_coords = object_coords[graspable_indices]
        graspable_distances = np.sqrt(np.sum(graspable_coords**2, axis=1))
        nearest_idx = np.argmin(graspable_distances)
        
        device_state = self._device_states.get(device_id, DeviceState())
        device_state.nearest_object_coords = graspable_coords[nearest_idx].copy()
        device_state.nearest_object_distance = graspable_distances[nearest_idx]
        device_state.last_update_time = time.time()
        self._device_states[device_id] = device_state
    else:
        # 没有可抓取物体，清空状态
        if device_id in self._device_states:
            self._device_states[device_id].nearest_object_coords = None
            self._device_states[device_id].nearest_object_distance = None
    
    # 3. 更新全局目标
    self._update_global_target()
    
    # 4. 标记待抓取目标
    with self._target_lock:
        if self._global_target_object is not None:
            target_coords = self._global_target_object.coords
            # 找到与全局目标匹配的物体
            for i in graspable_indices:
                if np.allclose(object_coords[i], target_coords, atol=1e-5):
                    states[i] = DetectionStatusLabel.OBJECT_PENDING_GRASP
                    break
    
    return states.astype(np.int32)
```

### _update_global_target() 方法实现

```python
def _update_global_target(self) -> None:
    """更新全局待抓取目标（线程安全）"""
    
    current_time = time.time()
    candidates = []
    
    # 1. 收集所有未过期的候选物体
    for device_id, state in self._device_states.items():
        # 检查状态是否过期
        if current_time - state.last_update_time > self._config.state_expiration_time:
            # 清空过期状态
            state.nearest_object_coords = None
            state.nearest_object_distance = None
            continue
        
        # 收集有效候选
        if state.nearest_object_coords is not None:
            candidates.append(GlobalTargetObject(
                coords=state.nearest_object_coords,
                distance=state.nearest_object_distance,
                device_id=device_id
            ))
    
    # 2. 选择距离最近的候选（线程安全）
    with self._target_lock:
        if len(candidates) == 0:
            self._global_target_object = None
        else:
            self._global_target_object = min(candidates, key=lambda obj: obj.distance)
```

### get_target_coords_snapshot() 方法实现

```python
def get_target_coords_snapshot(self) -> Optional[np.ndarray]:
    """线程安全地获取待抓取目标坐标副本"""
    
    with self._target_lock:
        if self._global_target_object is None:
            return None
        return self._global_target_object.coords.copy()
```

### 性能优化要点

1. **向量化操作**：所有距离计算和区域判断使用 NumPy 向量化操作
2. **避免循环**：使用布尔索引和 np.where 替代 Python 循环
3. **预分配数组**：使用 np.empty 预分配状态数组
4. **最小化锁竞争**：只在必要时使用锁，锁内操作尽可能简短
5. **避免不必要的复制**：只在需要返回副本时才复制数组
6. **热路径无检查**：向量化计算路径中不进行数据有效性检查



## 线程安全设计

### 线程安全需求

决策层需要支持以下并发场景：

1. **多设备并发处理**：DataProcessor 可能在不同线程中处理不同设备的数据
2. **CAN 通信模块读取**：通信模块在独立线程中定期读取目标坐标
3. **事件发布**：事件总线可能在不同线程中触发回调

### 线程安全机制

#### 1. 全局目标对象保护

使用 **RLock（可重入锁）** 保护全局目标对象：

```python
self._target_lock = threading.RLock()
self._global_target_object: Optional[GlobalTargetObject] = None
```

**保护的操作**：
- 读取全局目标（get_target_coords_snapshot）
- 更新全局目标（_update_global_target）
- 标记待抓取目标（_process_object 中的匹配逻辑）

**为什么使用 RLock**：
- 允许同一线程多次获取锁（可重入）
- 避免死锁（例如 _process_object 调用 _update_global_target）

#### 2. 设备状态隔离

每个设备的状态独立存储，不同设备之间无共享状态：

```python
self._device_states: Dict[str, DeviceState] = {}
```

**线程安全保证**：
- 每个设备的状态只由处理该设备数据的线程访问
- 不同设备的处理可以完全并行，无锁竞争

#### 3. 单例模式线程安全

使用**双重检查锁定**确保单例创建的线程安全：

```python
def __new__(cls, *args, **kwargs):
    if cls._instance is None:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
    return cls._instance
```

### 锁竞争分析

#### 写入频率

- **设备数据处理**：每个设备 30 FPS，3 个设备 = 90 次/秒
- **全局目标更新**：每次物体处理时更新 = 90 次/秒

#### 读取频率

- **CAN 通信模块**：10-50 次/秒

#### 锁持有时间

- **读取操作**：< 0.01ms（仅复制数组）
- **更新操作**：< 0.1ms（比较距离 + 赋值）

#### 竞争概率

```
写入间隔：1000ms / 90 = 11.1ms
读取间隔：1000ms / 50 = 20ms（最坏情况）
锁持有时间：0.1ms

竞争概率 ≈ 0.1ms / 11.1ms ≈ 0.9%
```

**结论**：锁竞争可忽略，对性能影响 < 0.5%

### 线程安全测试

```python
def test_concurrent_target_access():
    """测试并发访问目标坐标"""
    decision_layer = DecisionLayer(...)
    
    # 设置全局目标
    # ...
    
    results = []
    errors = []
    
    def reader_thread():
        try:
            for _ in range(100):
                coords = decision_layer.get_target_coords_snapshot()
                results.append(coords)
        except Exception as e:
            errors.append(e)
    
    def writer_thread():
        try:
            for i in range(100):
                # 模拟更新全局目标
                coords = np.random.rand(10, 3).astype(np.float32)
                labels = np.random.randint(0, 10, size=10, dtype=np.int32)
                decision_layer.decide(f"device_{i % 3}", coords, labels)
        except Exception as e:
            errors.append(e)
    
    # 启动多个读写线程
    threads = []
    for _ in range(5):
        threads.append(threading.Thread(target=reader_thread))
        threads.append(threading.Thread(target=writer_thread))
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    # 验证无错误
    assert len(errors) == 0
    # 验证所有读取都成功
    assert len(results) == 500  # 5 个读线程 × 100 次
```



## 性能分析

### 性能目标

根据需求 15，决策层的性能目标：

- **典型场景**（10-20 个检测对象）：< 5ms
- **大量对象**（50+ 个检测对象）：< 20ms
- **目标坐标获取**：< 0.1ms

### 性能分解

#### decide() 方法时间分解

```
总时间：~3ms（15 个对象）

1. 输入验证：~0.1ms
   - 类型检查
   - 形状检查
   - 长度一致性检查

2. 数据分流：~0.2ms
   - np.isin()：~0.1ms
   - 布尔索引：~0.1ms

3. _process_person()：~0.8ms
   - 距离计算：~0.3ms
   - 状态机更新：~0.2ms
   - 状态分配：~0.3ms

4. _process_object()：~1.5ms
   - 区域判断：~0.5ms
   - 最近物体查找：~0.4ms
   - 全局目标更新：~0.3ms
   - 目标标记：~0.3ms

5. 状态合并：~0.2ms
   - 数组分配：~0.1ms
   - 掩码赋值：~0.1ms

6. 枚举转换：~0.2ms
   - 列表推导：~0.2ms
```

### 性能优化技术

#### 1. 向量化操作

**距离计算**：
```python
# 慢速（Python 循环）
distances = np.array([np.sqrt(x**2 + y**2 + z**2) for x, y, z in coords])

# 快速（向量化）
distances = np.sqrt(np.sum(coords**2, axis=1))
```

**性能提升**：10-50x

#### 2. 布尔索引

**区域判断**：
```python
# 慢速（循环 + 条件）
states = []
for x, y, z in coords:
    if abs(y) < threshold:
        states.append(DANGEROUS)
    elif is_in_grasp_zone(x, y, z):
        states.append(GRASPABLE)
    else:
        states.append(OUT_OF_RANGE)

# 快速（向量化布尔索引）
is_dangerous = np.abs(coords[:, 1]) < threshold
is_graspable = (
    (coords[:, 0] > x_min) & (coords[:, 0] < x_max) &
    (np.abs(coords[:, 1]) > y_min) & (np.abs(coords[:, 1]) < y_max)
)
states = np.where(is_dangerous, DANGEROUS,
                  np.where(is_graspable, GRASPABLE, OUT_OF_RANGE))
```

**性能提升**：20-100x

#### 3. 预分配数组

```python
# 慢速（动态扩展）
states = []
for ... :
    states.append(...)
states = np.array(states)

# 快速（预分配）
states = np.empty(n, dtype=np.int32)
states[person_mask] = person_states
states[object_mask] = object_states
```

**性能提升**：2-5x

#### 4. 避免不必要的复制

```python
# 慢速（多次复制）
person_coords = filtered_coords[person_mask].copy()
distances = np.sqrt(np.sum(person_coords**2, axis=1)).copy()

# 快速（视图操作）
person_coords = filtered_coords[person_mask]  # 视图，不复制
distances = np.sqrt(np.sum(person_coords**2, axis=1))  # 直接计算
```

**性能提升**：1.5-3x

#### 5. 最小化锁持有时间

```python
# 慢速（锁内计算）
with self._target_lock:
    candidates = self._collect_candidates()
    target = min(candidates, key=lambda obj: obj.distance)
    self._global_target_object = target

# 快速（锁外计算）
candidates = self._collect_candidates()
target = min(candidates, key=lambda obj: obj.distance) if candidates else None
with self._target_lock:
    self._global_target_object = target
```

**性能提升**：减少锁竞争

### 性能基准测试

```python
import time
import numpy as np

def benchmark_decide():
    """基准测试 decide() 方法"""
    decision_layer = DecisionLayer(...)
    
    # 典型场景：15 个对象
    coords = np.random.rand(15, 3).astype(np.float32) * 5
    labels = np.random.randint(0, 10, size=15, dtype=np.int32)
    
    # 预热
    for _ in range(10):
        decision_layer.decide("device_1", coords, labels)
    
    # 测试
    times = []
    for _ in range(1000):
        start = time.perf_counter()
        decision_layer.decide("device_1", coords, labels)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    times = np.array(times)
    print(f"平均时间: {np.mean(times)*1000:.2f}ms")
    print(f"中位数: {np.median(times)*1000:.2f}ms")
    print(f"P95: {np.percentile(times, 95)*1000:.2f}ms")
    print(f"P99: {np.percentile(times, 99)*1000:.2f}ms")
    print(f"最大值: {np.max(times)*1000:.2f}ms")

def benchmark_get_target_coords():
    """基准测试 get_target_coords_snapshot() 方法"""
    decision_layer = DecisionLayer(...)
    
    # 设置全局目标
    # ...
    
    times = []
    for _ in range(10000):
        start = time.perf_counter()
        decision_layer.get_target_coords_snapshot()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    times = np.array(times)
    print(f"平均时间: {np.mean(times)*1000:.3f}ms")
    print(f"P99: {np.percentile(times, 99)*1000:.3f}ms")
```

### 预期性能结果

基于向量化实现和性能优化：

| 场景 | 对象数量 | 预期时间 | 目标时间 |
|------|---------|---------|---------|
| 典型 | 15 | 2-3ms | < 5ms |
| 大量 | 50 | 8-12ms | < 20ms |
| 极限 | 100 | 15-18ms | N/A |
| 目标获取 | N/A | 0.02-0.05ms | < 0.1ms |

**结论**：设计满足性能要求，有充足的性能余量。



## 集成设计

### 与 DataProcessor 集成

#### 初始化

```python
class DataProcessor:
    def __init__(self, config: DataProcessingConfigDTO):
        # ... 其他初始化
        
        # 从 DataProcessingConfigDTO 中获取决策层配置
        decision_config = config.decision_layer_config
        
        # 初始化决策层（单例）
        self._decision_layer = DecisionLayer(
            event_bus=self._event_bus,
            config=decision_config
        )
```

#### 数据处理流程

```python
def _process_device_data(
    self,
    device_id: str,
    frame_id: int,
    detections: List[DetectionDTO]
) -> DeviceProcessedDataDTO:
    """处理单个设备的检测数据"""
    
    # 1. 提取坐标和标签
    coords = np.array([det.spatial_coordinates.to_array() for det in detections])
    labels = np.array([det.label for det in detections])
    
    # 2. 坐标变换
    transformed_coords = self._transformer.transform(device_id, coords)
    
    # 3. 滤波处理
    filtered_coords, filtered_labels = self._filter_manager.filter(
        device_id, transformed_coords, labels
    )
    
    # 4. 决策层处理
    state_labels = self._decision_layer.decide(
        device_id, filtered_coords, filtered_labels
    )
    
    # 5. 组装输出
    return DeviceProcessedDataDTO(
        device_id=device_id,
        frame_id=frame_id,
        coords=filtered_coords,
        labels=filtered_labels,
        state_label=state_labels,
        # ... 其他字段
    )
```

### 与事件总线集成

#### 事件发布

```python
def _publish_warning_event(
    self,
    status: PersonWarningStatus,
    device_id: str
) -> None:
    """发布人员警告事件"""
    
    event_data = {
        "status": status,
        "timestamp": time.time()
    }
    
    self._event_bus.publish(
        EventType.PERSON_WARNING,
        event_data,
        wait_all=False  # 异步发布
    )
```

#### 事件订阅（通信模块）

```python
class CommunicationModule:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        
        # 订阅人员警告事件
        self._event_bus.subscribe(
            EventType.PERSON_WARNING,
            self._handle_person_warning
        )
    
    def _handle_person_warning(self, event_data: Dict):
        """处理人员警告事件"""
        status = event_data["status"]
        timestamp = event_data["timestamp"]
        
        if status == PersonWarningStatus.TRIGGERED:
            # 触发警报
            self._trigger_alarm()
        elif status == PersonWarningStatus.CLEARED:
            # 清除警报
            self._clear_alarm()
```

### 与 CAN 通信模块集成

#### 目标坐标读取

```python
class CANModule:
    def __init__(self):
        # 获取决策层单例
        self._decision_layer = DecisionLayer.get_instance()
        
        # 启动定期读取线程
        self._reader_thread = threading.Thread(
            target=self._read_target_coords_loop,
            daemon=True
        )
        self._reader_thread.start()
    
    def _read_target_coords_loop(self):
        """定期读取目标坐标"""
        while self._running:
            # 获取目标坐标（线程安全）
            target_coords = self._decision_layer.get_target_coords_snapshot()
            
            if target_coords is not None:
                # 发送到 CAN 总线
                self._send_to_can(target_coords)
            
            # 等待下一次读取（例如 50ms）
            time.sleep(0.05)
    
    def _send_to_can(self, coords: np.ndarray):
        """发送坐标到 CAN 总线"""
        x, y, z = coords
        # CAN 总线发送逻辑
        # ...
```

### 配置管理

#### 配置文件示例

决策层配置存储在 `config/data_processing.json` 中，与坐标变换、滤波配置统一管理。

```json
{
  "data_processing": {
    "coordinate_transforms": {
      "left": {
        "role": "left",
        "translation_x": 100.0,
        "translation_y": 0.0,
        "translation_z": 0.0,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0
      },
      "right": {
        "role": "right",
        "translation_x": -100.0,
        "translation_y": 0.0,
        "translation_z": 0.0,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0
      }
    },
    "filter_config": {
      "filter_type": "moving_average",
      "moving_average_config": {
        "window_size": 10
      }
    },
    "decision_layer_config": {
      "person_label_ids": [0],
      "person_warning": {
        "d_in": 3000.0,
        "d_out": 3200.0,
        "T_warn": 3.0,
        "T_clear": 3.0,
        "grace_time": 0.5
      },
      "object_zones": {
        "danger_y_threshold": 1500.0,
        "grasp_zone": {
          "mode": "rect",
          "x_min": 500.0,
          "x_max": 2000.0,
          "y_min": 300.0,
          "y_max": 1500.0
        }
      },
      "state_expiration_time": 1.0
    },
    "enable_data_logging": false,
    "processing_thread_priority": 5
  }
}
```

#### 配置加载

```python
import json
from oak_vision_system.core.dto.config_dto import DataProcessingConfigDTO

def load_data_processing_config(config_path: str) -> DataProcessingConfigDTO:
    """从 JSON 配置文件加载数据处理配置（包含决策层配置）"""
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = json.load(f)
    
    dp_config = config_dict['data_processing']
    
    # 配置 DTO 会自动处理嵌套结构和验证
    return DataProcessingConfigDTO.from_dict(dp_config)
```



## 部署和维护

### 日志记录

#### 日志级别

- **DEBUG**：状态转换、事件发布、详细计算过程
- **INFO**：初始化完成、配置加载
- **WARNING**：状态过期、异常数据（如果启用检查）
- **ERROR**：输入验证失败、配置错误

#### 日志示例

```python
import logging

logger = logging.getLogger(__name__)

# INFO：初始化
logger.info(
    "决策层初始化完成: person_labels=%s, d_in=%.2f, d_out=%.2f",
    self._config.person_label_ids,
    self._config.d_in,
    self._config.d_out
)

# DEBUG：状态转换
logger.debug(
    "人员警告状态转换: device_id=%s, %s -> %s, distance=%.2f",
    device_id,
    old_state.value,
    new_state.value,
    min_distance
)

# DEBUG：事件发布
logger.debug(
    "发布人员警告事件: device_id=%s, status=%s, timestamp=%.3f",
    device_id,
    status.value,
    timestamp
)

# WARNING：状态过期
logger.warning(
    "设备状态过期: device_id=%s, last_update=%.3f, age=%.3f",
    device_id,
    state.last_update_time,
    current_time - state.last_update_time
)

# ERROR：输入验证失败
logger.error(
    "输入验证失败: device_id=%s, coords_shape=%s, labels_shape=%s",
    device_id,
    filtered_coords.shape,
    filtered_labels.shape
)
```

### 监控指标

#### 性能指标

```python
# 处理时间
metrics.histogram("decision_layer.decide.duration_ms", duration_ms)

# 对象数量
metrics.gauge("decision_layer.objects.count", len(filtered_coords))

# 人员数量
metrics.gauge("decision_layer.persons.count", np.sum(person_mask))

# 可抓取物体数量
metrics.gauge("decision_layer.graspable_objects.count", np.sum(is_graspable))
```

#### 状态指标

```python
# 设备状态数量
metrics.gauge("decision_layer.device_states.count", len(self._device_states))

# 警告状态分布
for state in PersonWarningState:
    count = sum(1 for s in self._device_states.values() 
                if s.person_warning_state == state)
    metrics.gauge(f"decision_layer.warning_state.{state.value}", count)

# 全局目标存在性
metrics.gauge(
    "decision_layer.global_target.exists",
    1 if self._global_target_object is not None else 0
)
```

#### 事件指标

```python
# 警告事件发布次数
metrics.counter("decision_layer.events.person_warning.triggered")
metrics.counter("decision_layer.events.person_warning.cleared")
```

### 调试工具

#### 状态导出

```python
def export_state(self) -> Dict:
    """导出当前状态（用于调试）"""
    
    with self._target_lock:
        global_target = None
        if self._global_target_object is not None:
            global_target = {
                "coords": self._global_target_object.coords.tolist(),
                "distance": float(self._global_target_object.distance),
                "device_id": self._global_target_object.device_id
            }
    
    device_states = {}
    for device_id, state in self._device_states.items():
        device_states[device_id] = {
            "person_warning_state": state.person_warning_state.value,
            "person_distance": float(state.person_distance) if state.person_distance else None,
            "t_in": float(state.t_in),
            "t_out": float(state.t_out),
            "nearest_object_distance": float(state.nearest_object_distance) 
                if state.nearest_object_distance else None,
            "last_update_time": float(state.last_update_time)
        }
    
    return {
        "global_target": global_target,
        "device_states": device_states,
        "config": {
            "d_in": self._config.d_in,
            "d_out": self._config.d_out,
            "T_warn": self._config.T_warn,
            "T_clear": self._config.T_clear
        }
    }
```

#### 可视化工具

```python
def visualize_zones(config: DecisionLayerConfig):
    """可视化抓取区域和危险区域"""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 绘制危险区
    danger_rect = Rectangle(
        (-10, -config.danger_y_threshold),
        20,
        2 * config.danger_y_threshold,
        color='red',
        alpha=0.3,
        label='危险区'
    )
    ax.add_patch(danger_rect)
    
    # 绘制抓取区（矩形模式）
    if config.grasp_zone_mode == "rect":
        grasp_rect1 = Rectangle(
            (config.grasp_x_min, config.grasp_y_min),
            config.grasp_x_max - config.grasp_x_min,
            config.grasp_y_max - config.grasp_y_min,
            color='green',
            alpha=0.3,
            label='抓取区'
        )
        grasp_rect2 = Rectangle(
            (config.grasp_x_min, -config.grasp_y_max),
            config.grasp_x_max - config.grasp_x_min,
            config.grasp_y_max - config.grasp_y_min,
            color='green',
            alpha=0.3
        )
        ax.add_patch(grasp_rect1)
        ax.add_patch(grasp_rect2)
    
    ax.set_xlim(-1, 5)
    ax.set_ylim(-3, 3)
    ax.set_xlabel('X (米)')
    ax.set_ylabel('Y (米)')
    ax.set_title('决策层区域配置')
    ax.legend()
    ax.grid(True)
    
    plt.show()
```

### 故障排查

#### 常见问题

1. **性能下降**
   - 检查对象数量是否异常增多
   - 检查是否有设备状态泄漏（未清理）
   - 检查锁竞争情况

2. **警告事件未触发**
   - 检查人员距离是否真的 < d_in
   - 检查时间累计是否达到 T_warn
   - 检查状态机是否正确转换

3. **全局目标选择错误**
   - 检查设备状态是否过期
   - 检查距离计算是否正确
   - 检查抓取区域配置是否合理

4. **线程安全问题**
   - 检查是否有未加锁的全局状态访问
   - 检查是否有死锁（使用 RLock）
   - 检查是否有竞态条件

#### 调试命令

```python
# 导出当前状态
state = decision_layer.export_state()
print(json.dumps(state, indent=2))

# 检查配置
print(decision_layer._config)

# 检查设备状态数量
print(f"设备数量: {len(decision_layer._device_states)}")

# 检查全局目标
target = decision_layer.get_target_coords_snapshot()
print(f"全局目标: {target}")
```

## 总结

本设计文档详细描述了决策层模块的完整设计，包括：

1. **架构设计**：全局单例、嵌入式设计、事件驱动
2. **组件设计**：主方法、人员处理、物体处理、状态管理
3. **数据模型**：状态标签、配置、内部状态
4. **正确性属性**：13 个可测试的正确性属性
5. **错误处理**：Fail-Fast 策略、性能优先
6. **测试策略**：单元测试 + 基于属性的测试
7. **实现细节**：向量化操作、线程安全、性能优化
8. **集成设计**：与 DataProcessor、事件总线、CAN 模块集成
9. **部署维护**：日志、监控、调试工具

该设计确保了决策层的：
- **高性能**：向量化计算，5ms 内完成典型场景
- **线程安全**：RLock 保护，支持并发访问
- **可测试性**：13 个正确性属性，全面的测试覆盖
- **可维护性**：清晰的架构，完善的日志和监控
- **可扩展性**：灵活的配置，易于添加新功能

