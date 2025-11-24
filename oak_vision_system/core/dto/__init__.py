"""
DTO（数据传输对象）模块

提供系统中所有数据传输对象的定义和基础功能，包括：
- BaseDTO: 所有DTO的抽象基类
- 各种具体的DTO实现
- 数据验证工具函数
- 序列化和反序列化支持

设计原则：
- 不可变性：所有DTO使用@dataclass(frozen=True)确保数据不可变
- 类型安全：使用类型提示确保数据类型正确性
- 验证机制：在__post_init__中进行数据有效性验证
- 序列化支持：支持JSON序列化，便于调试和持久化
- 版本兼容：预留版本字段，支持向后兼容
"""

from .base_dto import (
    BaseDTO,
    DTOValidationError,
    validate_required_fields,
    validate_numeric_range,
    validate_string_length,
)

from .detection_dto import (
    SpatialCoordinatesDTO,
    BoundingBoxDTO,
    DetectionDTO,
    DeviceDetectionDataDTO,
    VideoFrameDTO,
    OAKDataCollectionDTO,
)

# 配置相关的DTO已迁移到 config_dto 子包
# 如果需要使用配置DTO，请从 core.dto.config_dto 导入

# 版本信息
__version__ = "1.0.0"

# 导出的公共接口
__all__ = [
    # 基类
    "BaseDTO",
    
    # 异常类
    "DTOValidationError",
    
    # 验证工具函数
    "validate_required_fields",
    "validate_numeric_range", 
    "validate_string_length",
    
    # 数据采集模块DTO
    "SpatialCoordinatesDTO",
    "BoundingBoxDTO", 
    "DetectionDTO",
    "DeviceDetectionDataDTO",
    "VideoFrameDTO",
    "OAKDataCollectionDTO",
    
    # 版本信息
    "__version__",
]