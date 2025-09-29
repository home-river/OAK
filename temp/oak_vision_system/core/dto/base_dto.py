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
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Type, TypeVar, Union
from datetime import datetime

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
    
    # 验证错误信息
    validation_errors: tuple = field(default_factory=tuple, init=False)

    def __post_init__(self):
        """
        数据初始化后的验证处理
        
        在dataclass创建实例后自动调用，用于：
        1. 执行数据有效性验证
        2. 设置计算字段
        3. 执行自定义初始化逻辑
        """
        # 执行数据验证
        validation_errors = self._validate_data()
        
        # 由于frozen=True，需要使用object.__setattr__来设置字段
        if validation_errors:
            object.__setattr__(self, 'is_valid', False)
            object.__setattr__(self, 'validation_errors', tuple(validation_errors))
        
        # 执行子类特定的初始化逻辑
        self._post_init_hook()

    @abstractmethod
    def _validate_data(self) -> list[str]:
        """
        抽象方法：数据验证
        
        子类必须实现此方法来定义特定的验证规则
        
        Returns:
            list[str]: 验证错误信息列表，空列表表示验证通过
        """
        pass

    def _post_init_hook(self) -> None:
        """
        初始化后钩子方法
        
        子类可以重写此方法来执行特定的初始化逻辑
        默认实现为空，子类按需重写
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """
        将DTO转换为字典
        
        Returns:
            Dict[str, Any]: DTO的字典表示
        """
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        """
        将DTO转换为JSON字符串
        
        Args:
            indent: JSON缩进级别，None表示紧凑格式
            
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
            self.to_dict(),
            indent=indent,
            ensure_ascii=False,
            default=json_serializer
        )

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        从字典创建DTO实例
        
        Args:
            data: 包含DTO数据的字典
            
        Returns:
            T: DTO实例
            
        Raises:
            ValueError: 当数据格式不正确时
            TypeError: 当数据类型不匹配时
        """
        try:
            # 过滤掉不属于该类的字段
            valid_fields = cls._get_init_fields()
            filtered_data = {k: v for k, v in data.items() if k in valid_fields}
            
            return cls(**filtered_data)
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

    def is_data_valid(self) -> bool:
        """
        检查数据是否有效
        
        Returns:
            bool: True表示数据有效，False表示数据无效
        """
        return self.is_valid

    def get_validation_errors(self) -> tuple[str, ...]:
        """
        获取验证错误信息
        
        Returns:
            tuple[str, ...]: 验证错误信息元组
        """
        return self.validation_errors

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
