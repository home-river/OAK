"""
DTO基类使用示例

演示如何使用BaseDTO基类创建自定义的数据传输对象，包括：
- 定义具体的DTO类
- 数据验证
- JSON序列化和反序列化
- 错误处理
"""

import sys
import os
from dataclasses import dataclass
from typing import Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oak_vision_system.core.dto import (
    BaseDTO,
    validate_required_fields,
    validate_numeric_range,
    validate_string_length,
)


@dataclass(frozen=True)
class PersonDTO(BaseDTO):
    """人员信息DTO示例"""
    
    name: str
    age: int
    email: Optional[str] = None
    phone: Optional[str] = None
    
    def _validate_data(self) -> list[str]:
        """实现数据验证逻辑"""
        errors = []
        
        # 验证必需字段
        errors.extend(validate_required_fields(self, ['name']))
        
        # 验证年龄范围
        errors.extend(validate_numeric_range(
            self.age, 'age', min_value=0, max_value=150
        ))
        
        # 验证姓名长度
        errors.extend(validate_string_length(
            self.name, 'name', min_length=1, max_length=50
        ))
        
        # 验证邮箱格式（简单验证）
        if self.email is not None:
            if '@' not in self.email or '.' not in self.email:
                errors.append("邮箱格式无效")
        
        # 验证手机号格式（简单验证）
        if self.phone is not None:
            if not self.phone.replace('-', '').replace(' ', '').isdigit():
                errors.append("手机号格式无效")
        
        return errors


@dataclass(frozen=True)
class CoordinateDTO(BaseDTO):
    """坐标DTO示例"""
    
    x: float
    y: float
    z: float
    confidence: float = 1.0
    
    def _validate_data(self) -> list[str]:
        """实现坐标数据验证"""
        errors = []
        
        # 验证坐标值
        for coord_name, coord_value in [('x', self.x), ('y', self.y), ('z', self.z)]:
            errors.extend(validate_numeric_range(
                coord_value, coord_name, min_value=-1000.0, max_value=1000.0
            ))
        
        # 验证置信度范围
        errors.extend(validate_numeric_range(
            self.confidence, 'confidence', min_value=0.0, max_value=1.0
        ))
        
        return errors


def demonstrate_basic_usage():
    """演示基本用法"""
    print("=== DTO基类使用示例 ===\n")
    
    print("1. 创建有效的PersonDTO:")
    person = PersonDTO(
        name="张三",
        age=25,
        email="zhangsan@example.com",
        phone="138-0000-0000"
    )
    
    print(f"   DTO对象: {person}")
    print(f"   是否有效: {person.is_data_valid()}")
    print(f"   创建时间: {person.get_created_datetime()}")
    print()
    
    print("2. JSON序列化:")
    json_str = person.to_json(indent=2)
    print(f"   JSON表示:\n{json_str}")
    print()
    
    print("3. 从JSON反序列化:")
    person_from_json = PersonDTO.from_json(json_str)
    print(f"   反序列化结果: {person_from_json}")
    print(f"   数据一致性: {person.name == person_from_json.name}")
    print()


def demonstrate_validation():
    """演示数据验证"""
    print("=== 数据验证示例 ===\n")
    
    print("1. 创建无效的PersonDTO（年龄超出范围）:")
    invalid_person = PersonDTO(
        name="",  # 空名称
        age=200,  # 超出年龄范围
        email="invalid-email",  # 无效邮箱
        phone="abc123"  # 无效手机号
    )
    
    print(f"   DTO对象: {invalid_person}")
    print(f"   是否有效: {invalid_person.is_data_valid()}")
    print("   验证错误:")
    for error in invalid_person.get_validation_errors():
        print(f"     - {error}")
    print()
    
    print("2. 创建有效的CoordinateDTO:")
    coord = CoordinateDTO(x=10.5, y=-20.3, z=15.7, confidence=0.95)
    print(f"   坐标: {coord}")
    print(f"   是否有效: {coord.is_data_valid()}")
    print()
    
    print("3. 创建无效的CoordinateDTO（坐标超出范围）:")
    invalid_coord = CoordinateDTO(x=2000.0, y=0.0, z=0.0, confidence=1.5)
    print(f"   坐标: {invalid_coord}")
    print(f"   是否有效: {invalid_coord.is_data_valid()}")
    print("   验证错误:")
    for error in invalid_coord.get_validation_errors():
        print(f"     - {error}")
    print()


def demonstrate_immutability():
    """演示不可变性"""
    print("=== 不可变性示例 ===\n")
    
    person = PersonDTO(name="李四", age=30)
    print(f"原始DTO: {person}")
    
    try:
        # 尝试修改不可变对象
        person.name = "王五"
        print("错误：不应该能够修改不可变对象！")
    except Exception as e:
        print(f"正确：尝试修改不可变对象时抛出异常 - {type(e).__name__}")
    
    print()


def demonstrate_dict_operations():
    """演示字典操作"""
    print("=== 字典操作示例 ===\n")
    
    # 创建DTO
    person = PersonDTO(name="赵六", age=28, email="zhaoliu@example.com")
    
    print("1. 转换为字典:")
    person_dict = person.to_dict()
    for key, value in person_dict.items():
        print(f"   {key}: {value}")
    print()
    
    print("2. 从字典创建DTO:")
    new_data = {
        'name': '孙七',
        'age': 32,
        'email': 'sunqi@example.com',
        'phone': '139-1234-5678',
        'extra_field': 'will_be_ignored'  # 额外字段会被忽略
    }
    
    person_from_dict = PersonDTO.from_dict(new_data)
    print(f"   从字典创建: {person_from_dict}")
    print(f"   是否有效: {person_from_dict.is_data_valid()}")
    print()


def main():
    """主函数"""
    try:
        demonstrate_basic_usage()
        demonstrate_validation()
        demonstrate_immutability()
        demonstrate_dict_operations()
        
        print("=== 示例完成 ===")
        print("DTO基类提供了完整的数据验证、序列化和不可变性保证功能。")
        
    except Exception as e:
        print(f"示例执行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
