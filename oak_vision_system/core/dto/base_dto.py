"""
DTO基类模块

提供所有数据传输对象的基础功能，包括：
- 数据验证机制
- JSON序列化支持
- 版本兼容性
- 类型安全
- 不可变性保证
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict, fields, replace
from typing import Any, Dict, Optional, Type, TypeVar, Union, get_origin, get_args
from datetime import datetime
from enum import Enum

# 泛型类型变量，用于类型提示
T = TypeVar('T', bound='BaseDTO')


@dataclass(frozen=True)
class BaseDTO(ABC):
    """
    DTO基类，所有数据传输对象的抽象基类
    
    特性：
    - 不可变性：使用frozen=True确保数据不可变
    - 类型安全：使用类型提示确保数据类型正确性
    - 版本兼容：预留版本字段，支持向后兼容
    - 序列化支持：支持JSON序列化，便于调试和持久化
    - 验证机制：在__post_init__中进行数据有效性验证
    """
    
    # 版本信息，用于向后兼容
    version: str = field(default="1.0.0", init=False)
    
    # 创建时间戳
    created_at: float = field(default_factory=time.time, init=False)
    
    # 数据有效性标志
    is_valid: bool = field(default=True, init=False)
    
    # 验证错误信息（内部存储为 list，外部返回副本）
    validation_errors: list[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        """
        数据初始化后的处理
        
        在dataclass创建实例后自动调用，用于：
        1. 设置计算字段
        2. 执行自定义初始化逻辑
        
        性能优化说明：
        - 不在此处执行验证，以获得极致性能（零验证开销）
        - 验证应在单元测试中进行，或在需要时手动调用 validate()
        - 这种设计适用于实时性要求高的系统
        """
        # 仅执行子类的初始化钩子
        self._post_init_hook()

    @abstractmethod
    def _validate_data(self) -> list[str]:
        """
        抽象方法：数据验证逻辑
        
        子类必须实现此方法来定义特定的验证规则。
        
        注意：此方法不会自动调用，需要通过 validate() 方法手动触发验证。
        这样设计是为了在运行时获得极致性能，验证应在以下场景进行：
        - 单元测试中（必需）
        - 冒烟测试中（必需）
        - 接收外部不可信数据后
        - 调试阶段
        
        Returns:
            list[str]: 验证错误信息列表，空列表表示验证通过
        """
        pass

    def validate(self) -> bool:
        """
        手动验证接口
        
        调用 _validate_data() 执行验证逻辑，并更新验证状态。
        
        使用场景：
        1. 单元测试：确保每个DTO的验证逻辑正确
        2. 冒烟测试：批量验证系统完整性
        3. 外部数据：接收不可信数据后进行验证
        4. 调试：排查数据问题
        
        Returns:
            bool: True表示验证通过，False表示验证失败
            
        Example:
            >>> detection = DetectionDTO(...)
            >>> if not detection.validate():
            ...     print(f"验证失败: {detection.get_validation_errors()}")
            
            >>> # 单元测试中使用
            >>> assert dto.validate(), f"DTO验证失败: {dto.get_validation_errors()}"
        """
        validation_errors = self._validate_data()
        
        if validation_errors:
            object.__setattr__(self, 'is_valid', False)
            object.__setattr__(self, 'validation_errors', list(validation_errors))
            return False
        
        # 验证通过，更新状态
        object.__setattr__(self, 'is_valid', True)
        object.__setattr__(self, 'validation_errors', list())
        return True

    def _post_init_hook(self) -> None:
        """
        初始化后钩子方法
        
        子类可以重写此方法来执行特定的初始化逻辑，例如：
        - 生成默认ID
        - 计算衍生字段
        - 设置默认值
        
        默认实现为空，子类按需重写。
        """
        pass

    def to_dict(self, include_metadata: bool = False) -> Dict[str, Any]:
        """
        将DTO转换为可序列化的字典
        
        智能处理：
        - 枚举类型 → 字符串值
        - 嵌套 DTO → 递归转换为字典
        - 字典的枚举键 → 字符串键
        - 列表/元组 → 递归处理元素
        
        Args:
            include_metadata: 是否包含元数据字段（version, created_at, is_valid, validation_errors）
                            默认为 False，适用于配置文件等场景
        
        Returns:
            Dict[str, Any]: DTO的字典表示
        """
        # 元数据字段列表
        metadata_fields = {'version', 'created_at', 'is_valid', 'validation_errors'}
        
        result = {}
        # 手动遍历字段，保持嵌套 DTO 的对象形态
        for field_info in fields(self):
            field_name = field_info.name
            # 如果不包含元数据，跳过元数据字段
            if not include_metadata and field_name in metadata_fields:
                continue
            field_value = getattr(self, field_name)
            result[field_name] = self._serialize_value(field_value, include_metadata=include_metadata)
        return result
    
    def _serialize_value(self, value: Any, include_metadata: bool = False) -> Any:
        """
        递归序列化值，处理特殊类型
        
        Args:
            value: 待序列化的值
            include_metadata: 是否包含元数据字段（传递给嵌套 DTO）
            
        Returns:
            可序列化的值
        """
        # 1. None 值
        if value is None:
            return None
        
        # 2. 枚举类型 → 字符串值
        if isinstance(value, Enum):
            return value.value
        
        # 3. 嵌套 DTO → 递归调用 to_dict()
        if isinstance(value, BaseDTO):
            return value.to_dict(include_metadata=include_metadata)
        
        # 4. 字典类型 → 递归处理键和值
        if isinstance(value, dict):
            return {
                # 如果键是枚举，转换为字符串，否则保持原样；对值进行递归处理
                (k.value if isinstance(k, Enum) else k): self._serialize_value(v, include_metadata=include_metadata)
                for k, v in value.items()
            }
        
        # 5. 列表类型 → 递归处理每个元素
        if isinstance(value, list):
            return [self._serialize_value(item, include_metadata=include_metadata) for item in value]
        
        # 6. 元组类型 → 递归处理每个元素
        if isinstance(value, tuple):
            return tuple(self._serialize_value(item, include_metadata=include_metadata) for item in value)
        
        # 7. 其他类型直接返回（int, float, str, bool等）
        return value

    def to_json(self, indent: Optional[int] = None, include_metadata: bool = False) -> str:
        """
        将DTO转换为JSON字符串
        
        Args:
            indent: JSON缩进级别，None表示紧凑格式
            include_metadata: 是否包含元数据字段（version, created_at等）
                            默认为 False，适用于配置文件等场景
            
        Returns:
            str: DTO的JSON字符串表示
        """
        def json_serializer(obj):
            """自定义JSON序列化器，处理特殊类型"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif hasattr(obj, '__dict__'):
                return obj.__dict__
            else:
                return str(obj)
        
        return json.dumps(
            self.to_dict(include_metadata=include_metadata),
            indent=indent,
            ensure_ascii=False,
            default=json_serializer
        )

    # 便捷的不可变更新接口：返回一个带有变更字段的新实例
    def with_updates(self, **changes: Any) -> "BaseDTO":
        """
        基于 dataclasses.replace 的轻量封装，用于便捷地构造带更新字段的新实例。

        注意：不会修改当前对象本身（frozen 语义保持），而是返回一个新对象。
        若字段名或类型无效，将与原构造时一致地抛出异常。

        Example:
            >>> new_cfg = old_cfg.with_updates(yaw=30.0, translation_x=120.0)
        """
        return replace(self, **changes)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        从字典创建DTO实例
        
        智能处理：
        - 字符串值 → 枚举类型
        - 字典 → 嵌套 DTO
        - 字符串键 → 枚举键（用于字典字段）
        - 列表/元组 → 递归处理元素
        
        Args:
            data: 包含DTO数据的字典
            
        Returns:
            T: DTO实例
            
        Raises:
            ValueError: 当数据格式不正确时
            TypeError: 当数据类型不匹配时
        """
        try:
            # 获取类的字段类型注解和可初始化字段
            field_types = cls._get_field_types()
            init_fields = cls._get_init_fields()
            
            # 转换数据（只处理可初始化的字段）
            converted_data = {}
            for field_name, field_value in data.items():
                # 跳过不属于该类的字段或不可初始化的字段
                if field_name not in field_types or field_name not in init_fields:
                    continue
                
                field_type = field_types[field_name]
                converted_data[field_name] = cls._deserialize_value(field_value, field_type)
            
            return cls(**converted_data)
        except Exception as e:
            raise ValueError(f"无法从字典创建{cls.__name__}实例: {str(e)}")

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """
        从JSON字符串创建DTO实例
        
        Args:
            json_str: JSON字符串
            
        Returns:
            T: DTO实例
            
        Raises:
            ValueError: 当JSON格式不正确时
            TypeError: 当数据类型不匹配时
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"无效的JSON格式: {str(e)}")
        except Exception as e:
            raise ValueError(f"无法从JSON创建{cls.__name__}实例: {str(e)}")

    @classmethod
    def _get_init_fields(cls) -> set[str]:
        """
        获取类的初始化字段集合
        
        Returns:
            set[str]: 可用于初始化的字段名集合
        """
        if hasattr(cls, '__dataclass_fields__'):
            return {
                field_name 
                for field_name, field_info in cls.__dataclass_fields__.items()
                if field_info.init
            }
        return set()
    
    @classmethod
    def _get_field_types(cls) -> Dict[str, Type]:
        """
        获取类的所有字段及其类型注解
        
        Returns:
            Dict[str, Type]: 字段名到类型的映射
        """
        return {f.name: f.type for f in fields(cls)}
    
    @classmethod
    def _deserialize_value(cls, value: Any, field_type: Type) -> Any:
        """
        根据类型注解反序列化值
        
        Args:
            value: 待反序列化的值
            field_type: 字段的类型注解
            
        Returns:
            反序列化后的值
        """
        # 1. None 值
        if value is None:
            return None
        
        # 获取泛型类型信息
        origin = get_origin(field_type)
        # 获取泛型参数
        args = get_args(field_type)
        
        # 2. Optional[X] 或 Union[X, None] 类型
        if origin is Union:
            # 过滤掉 None 类型，获取实际类型
            non_none_types = [arg for arg in args if arg is not type(None)]
            if non_none_types:
                # 因为本项目常用optional类型，所以这里直接取第一个非None类型
                actual_type = non_none_types[0]
                # 递归调用反序列化
                return cls._deserialize_value(value, actual_type)
            return value
        
        # 3. Dict 类型
        if origin is dict:
            if not isinstance(value, dict):
                return value
            # 对于dict类型，args的第一个参数是键类型，第二个参数是值类型
            key_type = args[0] if args else Any
            value_type = args[1] if len(args) > 1 else Any
            # 递归调用反序列化
            return {
                cls._deserialize_key(k, key_type): cls._deserialize_value(v, value_type)
                for k, v in value.items()
            }
        
        # 4. List 类型
        if origin is list:
            if not isinstance(value, list):
                return value
            
            item_type = args[0] if args else Any
            return [cls._deserialize_value(item, item_type) for item in value]
        
        # 5. Tuple 类型
        if origin is tuple:
            if not isinstance(value, (list, tuple)):
                return value
            
            if args:
                # 如果有类型参数，按类型转换每个元素
                return tuple(
                    cls._deserialize_value(item, args[i] if i < len(args) else Any)
                    for i, item in enumerate(value)
                )
            else:
                return tuple(value)
        
        # 6. 枚举类型
        try:
            if isinstance(field_type, type) and issubclass(field_type, Enum):
                if isinstance(value, str):
                    # 返回枚举值实例
                    return field_type(value)
                elif isinstance(value, dict):
                    # 处理枚举被序列化为字典的情况（兼容性）
                    if '_value_' in value:
                        return field_type(value['_value_'])
                return value
        except TypeError:
            pass
        
        # 7. BaseDTO 子类
        try:
            if isinstance(field_type, type) and issubclass(field_type, BaseDTO):
                if isinstance(value, dict):
                    return field_type.from_dict(value)
                return value
        except TypeError:
            pass
        
        # 8. 其他类型直接返回
        return value
    
    @classmethod
    def _deserialize_key(cls, key: Any, key_type: Type) -> Any:
        """
        反序列化字典键
        
        Args:
            key: 字典键
            key_type: 键的类型注解
            
        Returns:
            反序列化后的键
        """
        # 如果键类型是枚举，从字符串转换回枚举
        try:
            if isinstance(key_type, type) and issubclass(key_type, Enum):
                if isinstance(key, str):
                    return key_type(key)
        except TypeError:
            pass
        
        return key

    def is_data_valid(self) -> bool:
        """
        检查数据是否有效
        
        Returns:
            bool: True表示数据有效，False表示数据无效
        """
        return self.is_valid

    def get_validation_errors(self) -> list[str]:
        """
        获取验证错误信息
        
        Returns:
            list[str]: 验证错误信息列表（返回副本，避免外部修改内部状态）
        """
        return list(self.validation_errors)

    def get_version(self) -> str:
        """
        获取DTO版本信息
        
        Returns:
            str: 版本字符串
        """
        return self.version

    def get_created_at(self) -> float:
        """
        获取创建时间戳
        
        Returns:
            float: Unix时间戳
        """
        return self.created_at

    def get_created_datetime(self) -> datetime:
        """
        获取创建时间的datetime对象
        
        Returns:
            datetime: 创建时间的datetime表示
        """
        return datetime.fromtimestamp(self.created_at)

    def __str__(self) -> str:
        """
        字符串表示
        
        Returns:
            str: DTO的字符串表示
        """
        class_name = self.__class__.__name__
        status = "有效" if self.is_valid else "无效"
        return f"{class_name}(状态: {status}, 版本: {self.version})"

    def __repr__(self) -> str:
        """
        详细字符串表示，用于调试
        
        Returns:
            str: DTO的详细字符串表示
        """
        class_name = self.__class__.__name__
        fields = []
        
        if hasattr(self, '__dataclass_fields__'):
            for field_name, field_info in self.__dataclass_fields__.items():
                if field_info.init:  # 只显示初始化字段
                    value = getattr(self, field_name)
                    fields.append(f"{field_name}={repr(value)}")
        
        fields_str = ", ".join(fields)
        return f"{class_name}({fields_str})"


class DTOValidationError(Exception):
    """
    DTO验证异常类
    
    当DTO数据验证失败时抛出此异常
    """
    
    def __init__(self, dto_class: str, errors: list[str]):
        """
        初始化验证异常
        
        Args:
            dto_class: DTO类名
            errors: 验证错误列表
        """
        self.dto_class = dto_class
        self.errors = errors
        error_msg = f"{dto_class}验证失败: {'; '.join(errors)}"
        super().__init__(error_msg)


def validate_required_fields(obj: Any, required_fields: list[str]) -> list[str]:
    """
    验证必需字段的通用函数
    
    Args:
        obj: 要验证的对象
        required_fields: 必需字段列表
        
    Returns:
        list[str]: 验证错误信息列表
    """
    errors = []
    
    for field_name in required_fields:
        if not hasattr(obj, field_name):
            errors.append(f"缺少必需字段: {field_name}")
            continue
            
        value = getattr(obj, field_name)
        if value is None:
            errors.append(f"必需字段不能为None: {field_name}")
        elif isinstance(value, str) and not value.strip():
            errors.append(f"字符串字段不能为空: {field_name}")
    
    return errors


def validate_numeric_range(
    value: Union[int, float], 
    field_name: str,
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
    allow_none: bool = False
) -> list[str]:
    """
    验证数值范围的通用函数
    
    Args:
        value: 要验证的数值
        field_name: 字段名
        min_value: 最小值（可选）
        max_value: 最大值（可选）
        allow_none: 是否允许None值
        
    Returns:
        list[str]: 验证错误信息列表
    """
    errors = []
    
    if value is None:
        if not allow_none:
            errors.append(f"{field_name}不能为None")
        return errors
    
    if not isinstance(value, (int, float)):
        errors.append(f"{field_name}必须为数值类型，当前类型: {type(value).__name__}")
        return errors
    
    if min_value is not None and value < min_value:
        errors.append(f"{field_name}值{value}小于最小值{min_value}")
    
    if max_value is not None and value > max_value:
        errors.append(f"{field_name}值{value}大于最大值{max_value}")
    
    return errors


def validate_string_length(
    value: str,
    field_name: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    allow_none: bool = False
) -> list[str]:
    """
    验证字符串长度的通用函数
    
    Args:
        value: 要验证的字符串
        field_name: 字段名
        min_length: 最小长度（可选）
        max_length: 最大长度（可选）
        allow_none: 是否允许None值
        
    Returns:
        list[str]: 验证错误信息列表
    """
    errors = []
    
    if value is None:
        if not allow_none:
            errors.append(f"{field_name}不能为None")
        return errors
    
    if not isinstance(value, str):
        errors.append(f"{field_name}必须为字符串类型，当前类型: {type(value).__name__}")
        return errors
    
    length = len(value)
    
    if min_length is not None and length < min_length:
        errors.append(f"{field_name}长度{length}小于最小长度{min_length}")
    
    if max_length is not None and length > max_length:
        errors.append(f"{field_name}长度{length}大于最大长度{max_length}")
    
    return errors