# 配置DTO说明文档

> **文件路径**: `temp/oak_vision_system/core/dto/config_dto/`  
> **更新日期**: 2025-10-08  
> **状态**: ✅ 扁平化架构已完成  
> **用途**: 系统配置数据管理

---

## 📋 概述

配置DTO用于管理系统的**持久化配置数据**，包括设备绑定、模块参数、系统设置等。采用**扁平化文件组织**，简洁高效。

### 核心设计理念

```
配置系统：
  配置文件(JSON) ⟷ 配置DTO ⟷ 各功能模块
       ↓              ↓            ↓
    持久化        类型安全      参数获取
```

---

## 🏗️ 文件组织结构（扁平化）

### 目录结构（8个文件，1层）

```
config_dto/
├─ __init__.py                          # 统一导出
├─ enums.py                             # 所有枚举类型
├─ device_binding_dto.py                # 设备绑定相关（3个DTO）
├─ oak_config_dto.py                    # OAK模块配置
├─ data_processing_config_dto.py        # 数据处理模块配置（3个DTO）
├─ can_config_dto.py                    # CAN模块配置
├─ display_config_dto.py                # 显示模块配置
└─ device_manager_config_dto.py         # 顶层管理配置
```

**设计优势**：
- ✅ 文件数：8个 vs 旧版20个（**-60%**）
- ✅ 目录层级：1层 vs 旧版4层（**-75%**）
- ✅ 找文件更快，维护更便捷

---

## 📦 DTO类型层次

### 架构关系

```
一级（顶层统领）
└─ DeviceManagerConfigDTO
    │
    ├─ 基础设备管理
    │   ├─ DeviceRoleBindingDTO     (角色绑定)
    │   ├─ DeviceMetadataDTO        (设备元数据)
    │   └─ DeviceHistoryDTO         (历史记录)
    │
    └─ 功能模块配置
        ├─ OAKConfigDTO                        (OAK模块)
        ├─ DataProcessingConfigDTO             (数据处理)
        │   ├─ CoordinateTransformConfigDTO    (坐标变换)
        │   └─ FilterConfigDTO                 (滤波)
        ├─ CANConfigDTO                        (CAN模块)
        └─ DisplayConfigDTO                    (显示模块)
```

---

## 🔧 枚举类型（enums.py）

### 1. DeviceType - 设备类型
```python
class DeviceType(Enum):
    OAK_D = "OAK-D"
    OAK_D_LITE = "OAK-D-Lite"
    OAK_D_PRO = "OAK-D-Pro"
    OAK_D_S2 = "OAK-D-S2"
    OAK_1 = "OAK-1"
    UNKNOWN = "Unknown"
```

### 2. DeviceRole - 设备功能角色
```python
class DeviceRole(Enum):
    """
    功能角色（固定的功能位置）
    类比：车的轮子位置是固定的，但轮子本身可以更换
    """
    LEFT_CAMERA = "left_camera"
    RIGHT_CAMERA = "right_camera"
    CENTER_CAMERA = "center_camera"  # 预留
    UNKNOWN = "unknown"
    
    @property
    def display_name(self) -> str:
        """获取中文显示名称"""
        ...
```

**核心概念**：
- `DeviceRole` = 固定的功能位置（如"左相机"）
- `MXid` = 可更换的物理设备
- 设备更换后配置不变

### 3. ConnectionStatus - 连接状态
```python
class ConnectionStatus(Enum):
    X_LINK_BOOTED = "X_LINK_BOOTED"
    X_LINK_BOOTLOADER = "X_LINK_BOOTLOADER"
    X_LINK_FLASH_BOOTED = "X_LINK_FLASH_BOOTED"
    X_LINK_UNBOOTED = "X_LINK_UNBOOTED"
    X_LINK_ANY_STATE = "X_LINK_ANY_STATE"
```

---

## 📦 设备绑定DTO（device_binding_dto.py）

### 1. DeviceRoleBindingDTO - 设备角色绑定

**用途**：管理功能角色与物理设备MXid的绑定关系

```python
@dataclass
class DeviceRoleBindingDTO(BaseDTO):
    role: DeviceRole                          # 功能角色（主键）
    historical_mxids: List[str]               # 历史MXid（最多5个）
    active_mxid: Optional[str] = None         # 当前激活MXid（运行时）
    last_active_mxid: Optional[str] = None    # 上次使用MXid（持久化）
```

**核心方法**：
| 方法 | 返回值 | 说明 |
|-----|--------|------|
| `has_active_device` | `bool` | 是否有激活的设备 |

**使用场景**：
- 设备角色管理
- 设备更换追踪
- 自动设备识别
- 历史MXid记录

---

### 2. DeviceMetadataDTO - 设备元数据

**用途**：记录每个物理设备（MXid）的详细信息

```python
@dataclass
class DeviceMetadataDTO(BaseDTO):
    mxid: str                                 # 设备MXid（主键）
    notes: Optional[str] = None               # 用户备注
    device_type: DeviceType                   # 设备类型
    first_seen: float                         # 首次发现时间
    last_seen: float                          # 最后发现时间
    health_status: Optional[str] = None       # "good"/"warning"/"error"
```

**核心方法**：
| 方法 | 返回值 | 说明 |
|-----|--------|------|
| `short_mxid` | `str` | 缩短的MXid（后8位） |

**使用场景**：
- 设备信息管理
- 健康状态监控
- 使用历史追踪
- 备注管理

---

### 3. DeviceHistoryDTO - 设备历史记录

**用途**：记录设备操作历史，用于审计和追溯

```python
@dataclass
class DeviceHistoryDTO(BaseDTO):
    operation: str                            # 操作类型
    operation_time: float                     # 操作时间
    target_type: str                          # "role"/"mxid"/"config"
    target_id: str                            # 目标ID
    details: dict                             # 操作详情
    operator: Optional[str] = None            # 操作者
    reason: Optional[str] = None              # 操作原因
```

**使用场景**：
- 操作审计
- 问题追溯
- 配置历史
- 责任追踪

---

## 📦 功能模块配置DTO

### 1. OAKConfigDTO - OAK模块配置（oak_config_dto.py）

**用途**：管理OAK设备的检测、相机、深度图等配置

```python
@dataclass
class OAKConfigDTO(BaseDTO):
    # 检测模型配置
    model_path: Optional[str] = None
    label_map: List[str] = ["durian", "person"]
    num_classes: int = 2
    confidence_threshold: float = 0.5
    
    # 检测参数配置
    input_resolution: Tuple[int, int] = (512, 288)
    nms_threshold: float = 0.4
    max_detections: int = -1
    depth_min_threshold: float = 400.0
    depth_max_threshold: float = 7000.0
    
    # 相机配置
    preview_resolution: Tuple[int, int] = (512, 288)
    hardware_fps: int = 30
    usb2_mode: bool = True
    
    # 深度图配置
    enable_depth_display: bool = True
    depth_display_resolution: Tuple[int, int] = (640, 480)
    
    # 显示配置
    enable_fullscreen: bool = False
    default_display_mode: str = "combined"
    
    # 队列配置
    queue_max_size: int = 4
    queue_blocking: bool = False
```

**使用场景**：
- 检测模型配置
- 相机参数设置
- 深度图配置
- 显示模式设置

---

### 2. DataProcessingConfigDTO - 数据处理模块配置（data_processing_config_dto.py）

**包含3个子配置DTO**：

#### 2.1 CoordinateTransformConfigDTO - 坐标变换配置

```python
@dataclass
class CoordinateTransformConfigDTO(BaseDTO):
    role: DeviceRole                          # 功能角色
    
    # 变换参数（欧拉角）
    translation_x: float = 0.0                # mm
    translation_y: float = 0.0
    translation_z: float = 0.0
    roll: float = 0.0                         # 度
    pitch: float = 0.0
    yaw: float = 0.0
    
    # 标定信息
    calibration_date: Optional[str] = None
    calibration_method: Optional[str] = None  # "manual"/"auto"
    calibration_accuracy: Optional[float] = None
```

**核心方法**：
| 方法 | 返回值 | 说明 |
|-----|--------|------|
| `get_transform_matrix()` | `np.ndarray` | 生成4x4齐次变换矩阵 |

**设计理念**：
- 参数绑定到**角色**，不绑定到MXid
- 设备更换后无需重新标定
- 支持热更新（实时调整）

#### 2.2 FilterConfigDTO - 滤波配置

```python
@dataclass
class FilterConfigDTO(BaseDTO):
    filter_type: str = "kalman"               # "kalman"/"lowpass"/"median"
    
    # 卡尔曼滤波参数
    kalman_gain: float = 0.5
    process_noise: float = 0.1
    measurement_noise: float = 0.5
    
    # 低通滤波参数
    cutoff_frequency: Optional[float] = None
    
    # 中值滤波参数
    window_size: Optional[int] = None
```

#### 2.3 DataProcessingConfigDTO - 容器

```python
@dataclass
class DataProcessingConfigDTO(BaseDTO):
    # 子配置
    coordinate_transforms: Dict[DeviceRole, CoordinateTransformConfigDTO]
    filter_config: FilterConfigDTO
    
    # 模块级配置
    enable_data_logging: bool = False
    processing_thread_priority: int = 5
```

**核心方法**：
| 方法 | 返回值 | 说明 |
|-----|--------|------|
| `get_coordinate_transform(role)` | `CoordinateTransformConfigDTO` | 获取指定角色的坐标变换 |
| `add_coordinate_transform(config)` | `None` | 添加坐标变换配置 |

---

### 3. CANConfigDTO - CAN模块配置（can_config_dto.py）

```python
@dataclass
class CANConfigDTO(BaseDTO):
    # 基本配置
    enable_can: bool = False
    can_interface: str = 'socketcan'
    can_channel: str = 'can0'
    can_bitrate: int = 250000
    
    # 超时配置
    send_timeout_ms: int = 100
    receive_timeout_ms: int = 200
    person_timeout_seconds: float = 5.0
```

---

### 4. DisplayConfigDTO - 显示模块配置（display_config_dto.py）

```python
@dataclass
class DisplayConfigDTO(BaseDTO):
    # 显示模式
    enable_display: bool = True
    default_display_mode: str = "combined"    # "rgb"/"depth"/"combined"
    enable_fullscreen: bool = False
    
    # 显示参数
    window_width: int = 1280
    window_height: int = 720
    target_fps: int = 30
    
    # 叠加信息
    show_detection_boxes: bool = True
    show_coordinates: bool = True
    show_fps: bool = True
```

---

## 🔝 顶层配置DTO（device_manager_config_dto.py）

### DeviceManagerConfigDTO - 设备管理器配置

**用途**：统领所有配置，是配置文件的顶层结构

```python
@dataclass
class DeviceManagerConfigDTO(BaseDTO):
    config_version: str = "2.0.0"
    
    # 基础设备管理
    role_bindings: Dict[DeviceRole, DeviceRoleBindingDTO]
    device_metadata: Dict[str, DeviceMetadataDTO]
    predefined_roles: List[DeviceRole] = [LEFT_CAMERA, RIGHT_CAMERA]
    strict_mode: bool = True
    history: List[DeviceHistoryDTO]
    
    # 功能模块配置
    oak_config: OAKConfigDTO
    data_processing_config: DataProcessingConfigDTO
    can_config: CANConfigDTO
    display_config: DisplayConfigDTO
```

**核心方法**：
| 方法 | 返回值 | 说明 |
|-----|--------|------|
| `get_role_binding(role)` | `Optional[DeviceRoleBindingDTO]` | 获取角色绑定 |
| `get_active_mxid(role)` | `Optional[str]` | 获取角色的激活MXid |
| `get_device_metadata(mxid)` | `Optional[DeviceMetadataDTO]` | 获取设备元数据 |
| `active_role_count` | `int` | 获取激活的角色数量 |

---

## 📄 配置文件示例（JSON）

```json
{
  "config_version": "2.0.0",
  
  "role_bindings": {
    "left_camera": {
      "role": "left_camera",
      "historical_mxids": ["14442C10D13D0D0000", "14442C10D13D0D0001"],
      "last_active_mxid": "14442C10D13D0D0000"
    },
    "right_camera": {
      "role": "right_camera",
      "historical_mxids": ["14442C10D13D0D0002"],
      "last_active_mxid": "14442C10D13D0D0002"
    }
  },
  
  "device_metadata": {
    "14442C10D13D0D0000": {
      "mxid": "14442C10D13D0D0000",
      "notes": "2025年10月购入，主力设备",
      "device_type": "OAK-D",
      "health_status": "good"
    }
  },
  
  "oak_config": {
    "confidence_threshold": 0.5,
    "hardware_fps": 30,
    "label_map": ["durian", "person"]
  },
  
  "data_processing_config": {
    "coordinate_transforms": {
      "left_camera": {
        "role": "left_camera",
        "translation_x": 100.0,
        "translation_y": 50.0,
        "translation_z": 200.0,
        "pitch": 10.0,
        "yaw": 45.0,
        "calibration_method": "manual"
      }
    },
    "filter_config": {
      "filter_type": "kalman",
      "kalman_gain": 0.5
    }
  },
  
  "can_config": {
    "enable_can": false,
    "can_bitrate": 250000
  },
  
  "display_config": {
    "default_display_mode": "combined",
    "show_fps": true
  }
}
```

---

## 🔄 使用流程

### 1. 创建配置

```python
from core.dto.config_dto import (
    DeviceManagerConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    CoordinateTransformConfigDTO,
)

# 创建顶层配置
config = DeviceManagerConfigDTO()

# 添加设备角色绑定
binding = DeviceRoleBindingDTO(
    role=DeviceRole.LEFT_CAMERA,
    historical_mxids=["14442C10D13D0D0000"]
)
config.role_bindings[DeviceRole.LEFT_CAMERA] = binding

# 添加坐标变换配置
transform = CoordinateTransformConfigDTO(
    role=DeviceRole.LEFT_CAMERA,
    translation_x=100.0,
    yaw=45.0
)
config.data_processing_config.add_coordinate_transform(transform)
```

### 2. 保存配置

```python
# 序列化为字典
config_dict = config.to_dict()

# 保存为JSON文件
import json
with open("config.json", "w") as f:
    json.dump(config_dict, f, indent=2)
```

### 3. 加载配置

```python
# 从JSON文件加载
import json
with open("config.json", "r") as f:
    config_dict = json.load(f)

# 反序列化为DTO
config = DeviceManagerConfigDTO.from_dict(config_dict)

# 验证配置
if not config.validate():
    print(f"配置无效: {config.get_validation_errors()}")
```

### 4. 使用配置

```python
# 获取OAK配置
oak_config = config.oak_config
print(f"置信度阈值: {oak_config.confidence_threshold}")

# 获取坐标变换配置
transform = config.data_processing_config.get_coordinate_transform(
    DeviceRole.LEFT_CAMERA
)
matrix = transform.get_transform_matrix()

# 获取设备绑定
left_camera_mxid = config.get_active_mxid(DeviceRole.LEFT_CAMERA)
```

---

## 🎯 设计原则

### 1. 扁平化组织
- 8个文件，1层目录
- 找文件更快，维护更便捷
- 相关DTO合并在一起

### 2. 角色驱动
- 配置绑定到角色，不绑定到MXid
- 设备更换后配置不变
- 支持设备热插拔

### 3. 模块化扩展
```python
# 添加新模块：只需新增一个文件
# modules/log/log_config_dto.py

@dataclass
class LogConfigDTO(BaseDTO):
    log_level: str = "INFO"
    log_file: str = "system.log"

# 在顶层配置中添加
log_config: LogConfigDTO = field(default_factory=LogConfigDTO)
```

### 4. 完整验证
- 类型验证
- 范围验证
- 逻辑验证
- 依赖验证

---

## ⚠️ 注意事项

### 1. 配置版本管理
```python
# 配置文件迁移
if config.config_version == "1.0.0":
    # 执行迁移逻辑
    config = migrate_to_v2(config)
```

### 2. 默认值管理
```python
# ✅ 在DTO中定义默认值
@dataclass
class OAKConfigDTO(BaseDTO):
    confidence_threshold: float = 0.5  # 默认值

# ✅ 配置文件中可以省略
{
  "oak_config": {
    // confidence_threshold使用默认值0.5
  }
}
```

### 3. 配置热更新
```python
# 坐标变换参数支持热更新
# 无需重启系统
new_transform = CoordinateTransformConfigDTO(
    role=DeviceRole.LEFT_CAMERA,
    yaw=50.0  # 更新偏航角
)
config.data_processing_config.add_coordinate_transform(new_transform)
```

---

## 📊 代码量统计

| 文件 | 行数 | 说明 |
|-----|------|------|
| `enums.py` | 49行 | 枚举类型 |
| `device_binding_dto.py` | 124行 | 设备绑定（3个DTO） |
| `oak_config_dto.py` | 70行 | OAK配置 |
| `data_processing_config_dto.py` | 150行 | 数据处理（3个DTO） |
| `can_config_dto.py` | 45行 | CAN配置 |
| `display_config_dto.py` | 47行 | 显示配置 |
| `device_manager_config_dto.py` | 89行 | 顶层管理 |
| `__init__.py` | 69行 | 统一导出 |
| **总计** | **643行** | **8个文件** |

---

## 🔗 相关文档

- 📄 [BaseDTO基类说明.md](./BaseDTO基类说明.md) - DTO基类详解
- 📄 [检测数据DTO说明.md](./检测数据DTO说明.md) - 运行时检测数据
- 📄 [设备角色绑定架构设计方案.md](./设备角色绑定架构设计方案.md) - 角色绑定详细设计

---

**文档维护者**: AI Assistant  
**最后更新**: 2025-10-08
