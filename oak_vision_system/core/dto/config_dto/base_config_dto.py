"""
配置DTO基类模块

聚焦“配置加载/保存”的序列化与反序列化能力：
- JSON/Dict 类型感知转换
- 枚举键与值的兼容处理
- 容器与 Optional/Union 的递归恢复
"""

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Type, TypeVar, Union, get_origin, get_args
from datetime import datetime
from enum import Enum

from ..base_dto import BaseDTO

# 泛型类型变量，用于类型提示
T = TypeVar('T', bound='BaseConfigDTO')


@dataclass(frozen=True)
class BaseConfigDTO(BaseDTO):
    """配置DTO基类：仅保留配置持久化相关能力。"""

    def to_dict(self) -> Dict[str, Any]:
        """
        将DTO转换为可序列化的字典
        
        智能处理：
        - 枚举类型 → 字符串值
        - 嵌套 DTO → 递归转换为字典
        - 字典的枚举键 → 字符串键
        - 列表/元组 → 递归处理元素
        
        Returns:
            Dict[str, Any]: DTO的字典表示
        """
        result = {}
        for field_name, field_value in asdict(self).items():
            result[field_name] = self._serialize_value(field_value)
        return result
    
    def _serialize_value(self, value: Any) -> Any:
        """
        递归序列化值，处理特殊类型
        
        Args:
            value: 待序列化的值
            
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
            return value.to_dict()
        
        # 4. 字典类型 → 递归处理键和值
        if isinstance(value, dict):
            return {
                # 如果键是枚举，转换为字符串，否则保持原样；对值进行递归处理
                (k.value if isinstance(k, Enum) else k): self._serialize_value(v)
                for k, v in value.items()
            }
        
        # 5. 列表类型 → 递归处理每个元素
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        
        # 6. 元组类型 → 递归处理每个元素
        if isinstance(value, tuple):
            return tuple(self._serialize_value(item) for item in value)
        
        # 7. 其他类型直接返回（int, float, str, bool等）
        return value

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

    # _get_init_fields/_get_field_types 由 BaseDTO 提供
    
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