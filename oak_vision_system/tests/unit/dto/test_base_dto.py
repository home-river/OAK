"""
DTO基类单元测试

测试BaseDTO基类的所有功能，包括：
- 数据验证机制
- JSON序列化和反序列化
- 版本兼容性
- 类型安全
- 不可变性
"""

import json
import time
import pytest
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from oak_vision_system.core.dto import (
    BaseDTO,
    DTOValidationError,
    validate_required_fields,
    validate_numeric_range,
    validate_string_length,
)


# 测试用的具体DTO实现
@dataclass(frozen=True)
class _TestDTO(BaseDTO):
    """测试用的DTO实现"""
    
    name: str
    age: int
    email: Optional[str] = None
    
    def _validate_data(self) -> list[str]:
        """实现具体的验证逻辑"""
        errors = []
        
        # 验证必需字段
        errors.extend(validate_required_fields(self, ['name']))
        
        # 验证年龄范围
        errors.extend(validate_numeric_range(
            self.age, 'age', min_value=0, max_value=150
        ))
        
        # 验证姓名长度
        errors.extend(validate_string_length(
            self.name, 'name', min_length=1, max_length=100
        ))
        
        # 验证邮箱格式（简单验证）
        if self.email is not None and '@' not in self.email:
            errors.append("邮箱格式无效")
        
        return errors


@dataclass(frozen=True)
class Invalid_TestDTO(BaseDTO):
    """用于测试验证失败的DTO"""
    
    value: int
    
    def _validate_data(self) -> list[str]:
        """总是返回验证错误"""
        return ["测试验证错误"]


class TestBaseDTO:
    """BaseDTO基类测试套件"""
    
    def test_valid_dto_creation(self):
        """测试创建有效DTO"""
        dto = _TestDTO(name="张三", age=25, email="zhangsan@example.com")
        
        assert dto.validate() is True, \
            f"验证失败: {dto.get_validation_errors()}"
        assert len(dto.get_validation_errors()) == 0
        assert dto.name == "张三"
        assert dto.age == 25
        assert dto.email == "zhangsan@example.com"
        assert dto.version == "1.0.0"
        assert isinstance(dto.created_at, float)
    
    def test_invalid_dto_creation(self):
        """测试创建无效DTO"""
        dto = Invalid_TestDTO(value=100)
        
        assert dto.validate() is False
        assert len(dto.get_validation_errors()) == 1
        assert "测试验证错误" in dto.get_validation_errors()
    
    def test_dto_immutability(self):
        """测试DTO不可变性"""
        dto = _TestDTO(name="张三", age=25)
        
        # 尝试修改字段应该失败
        with pytest.raises(Exception):  # FrozenInstanceError
            dto.name = "李四"
    
    def test_to_dict_conversion(self):
        """测试转换为字典"""
        dto = _TestDTO(name="张三", age=25, email="zhangsan@example.com")
        dto_dict = dto.to_dict()
        
        assert isinstance(dto_dict, dict)
        assert dto_dict['name'] == "张三"
        assert dto_dict['age'] == 25
        assert dto_dict['email'] == "zhangsan@example.com"
        assert 'version' in dto_dict
        assert 'created_at' in dto_dict
        assert 'is_valid' in dto_dict
    
    def test_to_json_conversion(self):
        """测试转换为JSON"""
        dto = _TestDTO(name="张三", age=25, email="zhangsan@example.com")
        json_str = dto.to_json()
        
        assert isinstance(json_str, str)
        
        # 验证JSON可以解析
        parsed = json.loads(json_str)
        assert parsed['name'] == "张三"
        assert parsed['age'] == 25
        assert parsed['email'] == "zhangsan@example.com"
    
    def test_to_json_with_indent(self):
        """测试带缩进的JSON转换"""
        dto = _TestDTO(name="张三", age=25)
        json_str = dto.to_json(indent=2)
        
        assert isinstance(json_str, str)
        assert '\n' in json_str  # 有缩进应该包含换行符
    
    def test_from_dict_creation(self):
        """测试从字典创建DTO"""
        data = {
            'name': '李四',
            'age': 30,
            'email': 'lisi@example.com',
            'extra_field': 'should_be_ignored'  # 额外字段应该被忽略
        }
        
        dto = _TestDTO.from_dict(data)
        
        assert dto.name == '李四'
        assert dto.age == 30
        assert dto.email == 'lisi@example.com'
        assert dto.validate() is True, \
            f"验证失败: {dto.get_validation_errors()}"
    
    def test_from_dict_with_invalid_data(self):
        """测试从无效字典创建DTO"""
        data = {
            'name': '',  # 空名称应该验证失败
            'age': -5,   # 负年龄应该验证失败
        }
        
        dto = _TestDTO.from_dict(data)
        assert dto.validate() is False
        assert len(dto.get_validation_errors()) > 0
    
    def test_from_json_creation(self):
        """测试从JSON创建DTO"""
        json_data = '{"name": "王五", "age": 35, "email": "wangwu@example.com"}'
        
        dto = _TestDTO.from_json(json_data)
        
        assert dto.name == "王五"
        assert dto.age == 35
        assert dto.email == "wangwu@example.com"
        assert dto.validate() is True, \
            f"验证失败: {dto.get_validation_errors()}"
    
    def test_from_json_with_invalid_json(self):
        """测试从无效JSON创建DTO"""
        invalid_json = '{"name": "test", "age":}'  # 无效JSON
        
        with pytest.raises(ValueError, match="无效的JSON格式"):
            _TestDTO.from_json(invalid_json)
    
    def test_get_created_datetime(self):
        """测试获取创建时间的datetime对象"""
        dto = _TestDTO(name="测试", age=25)
        created_datetime = dto.get_created_datetime()
        
        assert isinstance(created_datetime, datetime)
        # 创建时间应该在当前时间附近
        time_diff = abs(time.time() - dto.created_at)
        assert time_diff < 1.0  # 1秒内
    
    def test_str_representation(self):
        """测试字符串表示"""
        dto = _TestDTO(name="测试", age=25)
        str_repr = str(dto)
        
        assert "_TestDTO" in str_repr
        assert "有效" in str_repr
        assert "1.0.0" in str_repr
    
    def test_repr_representation(self):
        """测试详细字符串表示"""
        dto = _TestDTO(name="测试", age=25, email="test@example.com")
        repr_str = repr(dto)
        
        assert "_TestDTO" in repr_str
        assert "name=" in repr_str
        assert "age=" in repr_str
        assert "email=" in repr_str


class TestValidationFunctions:
    """验证函数测试套件"""
    
    def test_validate_required_fields(self):
        """测试必需字段验证"""
        # 创建测试对象
        class TestObj:
            def __init__(self):
                self.field1 = "value1"
                self.field2 = None
                # field3 不存在
        
        obj = TestObj()
        errors = validate_required_fields(obj, ['field1', 'field2', 'field3'])
        
        assert len(errors) == 2
        assert any("field2" in error and "None" in error for error in errors)
        assert any("field3" in error and "缺少" in error for error in errors)
    
    def test_validate_numeric_range(self):
        """测试数值范围验证"""
        # 测试有效值
        errors = validate_numeric_range(25, 'age', min_value=0, max_value=100)
        assert len(errors) == 0
        
        # 测试超出范围
        errors = validate_numeric_range(-5, 'age', min_value=0, max_value=100)
        assert len(errors) == 1
        assert "小于最小值" in errors[0]
        
        errors = validate_numeric_range(150, 'age', min_value=0, max_value=100)
        assert len(errors) == 1
        assert "大于最大值" in errors[0]
        
        # 测试非数值类型
        errors = validate_numeric_range("not_a_number", 'age', min_value=0)
        assert len(errors) == 1
        assert "必须为数值类型" in errors[0]
    
    def test_validate_string_length(self):
        """测试字符串长度验证"""
        # 测试有效长度
        errors = validate_string_length("测试", 'name', min_length=1, max_length=10)
        assert len(errors) == 0
        
        # 测试长度不足
        errors = validate_string_length("", 'name', min_length=1, max_length=10)
        assert len(errors) == 1
        assert "小于最小长度" in errors[0]
        
        # 测试长度超出
        long_string = "a" * 20
        errors = validate_string_length(long_string, 'name', min_length=1, max_length=10)
        assert len(errors) == 1
        assert "大于最大长度" in errors[0]
        
        # 测试非字符串类型
        errors = validate_string_length(123, 'name', min_length=1)
        assert len(errors) == 1
        assert "必须为字符串类型" in errors[0]


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
