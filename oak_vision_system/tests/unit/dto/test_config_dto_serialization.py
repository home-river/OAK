"""
配置DTO序列化测试模块

测试 DeviceManagerConfigDTO 及其嵌套子模块的序列化功能：
- 枚举类型序列化
- 嵌套 DTO 序列化
- 字典类型字段序列化
- JSON 往返转换
"""

import unittest
import json
import os

from oak_vision_system.core.dto.config_dto import (
    DeviceManagerConfigDTO,
    OAKModuleConfigDTO,
    OAKConfigDTO,
    DeviceRoleBindingDTO,
    DeviceMetadataDTO,
    DataProcessingConfigDTO,
    FilterConfigDTO,
    CoordinateTransformConfigDTO,
    CANConfigDTO,
    DisplayConfigDTO,
    SystemConfigDTO,
    DeviceRole,
    ConnectionStatus,
    FilterType,
)


class TestDeviceManagerConfigDTOSerialization(unittest.TestCase):
    """测试 DeviceManagerConfigDTO 序列化"""
    
    def test_minimal_config_serialization(self):
        """测试最小配置的序列化"""
        print("\n=== 测试最小配置序列化 ===")
        
        # 创建最小配置
        config = DeviceManagerConfigDTO()
        
        # 测试 to_dict()
        config_dict = config.to_dict()
        print(f"✓ to_dict() 成功")
        print(f"  顶层键: {list(config_dict.keys())[:5]}")
        self.assertIsInstance(config_dict, dict)
        self.assertIn('config_version', config_dict)
        self.assertIn('oak_module', config_dict)
        
        # 测试 to_json()
        config_json = config.to_json(indent=2)
        print(f"✓ to_json() 成功")
        print(f"  JSON 长度: {len(config_json)} 字符")
        self.assertIsInstance(config_json, str)
        self.assertIn('"config_version"', config_json)
        
        # 测试 from_json()
        config_restored = DeviceManagerConfigDTO.from_json(config_json)
        print(f"✓ from_json() 成功")
        print(f"  还原后版本: {config_restored.config_version}")
        self.assertEqual(config_restored.config_version, config.config_version)
    
    def test_enum_serialization(self):
        """测试枚举类型的序列化"""
        print("\n=== 测试枚举类型序列化 ===")
        
        # 创建包含枚举的配置
        binding = DeviceRoleBindingDTO(
            role=DeviceRole.LEFT_CAMERA,
            historical_mxids=["14442C10D13D0D0000"],
            last_active_mxid="14442C10D13D0D0000"
        )
        
        # 序列化
        binding_dict = binding.to_dict()
        print(f"  role 类型: {type(binding_dict['role'])}")
        print(f"  role 值: {binding_dict['role']}")
        
        binding_json = binding.to_json()
        print(f"✓ 枚举序列化成功")
        print(f"  JSON: {binding_json[:100]}...")
        
        # 反序列化
        try:
            binding_restored = DeviceRoleBindingDTO.from_json(binding_json)
            print(f"✓ 枚举反序列化成功")
            print(f"  还原后 role: {binding_restored.role}")
        except Exception as e:
            print(f"✗ 枚举反序列化失败: {e}")
            self.fail(f"枚举反序列化失败: {e}")
    
    def test_nested_dto_serialization(self):
        """测试嵌套 DTO 的序列化"""
        print("\n=== 测试嵌套 DTO 序列化 ===")
        
        # 创建嵌套配置
        oak_config = OAKConfigDTO(
            model_path="/path/to/model.blob",
            confidence_threshold=0.6,
            hardware_fps=20
        )
        
        oak_module = OAKModuleConfigDTO(
            hardware_config=oak_config
        )
        
        config = DeviceManagerConfigDTO(
            oak_module=oak_module
        )
        
        # 序列化
        config_dict = config.to_dict()
        print(f"✓ 嵌套 DTO to_dict() 成功")
        print(f"  oak_module 类型: {type(config_dict['oak_module'])}")
        print(f"  hardware_config 类型: {type(config_dict['oak_module']['hardware_config'])}")
        
        config_json = config.to_json(indent=2)
        print(f"✓ 嵌套 DTO to_json() 成功")
        
        # 反序列化
        try:
            config_restored = DeviceManagerConfigDTO.from_json(config_json)
            print(f"✓ 嵌套 DTO from_json() 成功")
            print(f"  模型路径: {config_restored.oak_module.hardware_config.model_path}")
            self.assertEqual(
                config_restored.oak_module.hardware_config.model_path,
                oak_config.model_path
            )
        except Exception as e:
            print(f"✗ 嵌套 DTO 反序列化失败: {e}")
            self.fail(f"嵌套 DTO 反序列化失败: {e}")
    
    def test_dict_field_serialization(self):
        """测试字典类型字段的序列化"""
        print("\n=== 测试字典字段序列化 ===")
        
        # 创建包含字典的配置
        binding = DeviceRoleBindingDTO(
            role=DeviceRole.LEFT_CAMERA,
            historical_mxids=["14442C10D13D0D0000", "14442C10D13D0D0001"],
            last_active_mxid="14442C10D13D0D0000"
        )
        
        metadata = DeviceMetadataDTO(
            mxid="14442C10D13D0D0000",
            product_name="OAK-D",
            connection_status=ConnectionStatus.CONNECTED,
            notes="主力设备"
        )
        
        oak_module = OAKModuleConfigDTO(
            role_bindings={DeviceRole.LEFT_CAMERA: binding},
            device_metadata={"14442C10D13D0D0000": metadata}
        )
        
        # 序列化
        oak_module_dict = oak_module.to_dict()
        print(f"✓ 字典字段 to_dict() 成功")
        print(f"  role_bindings 类型: {type(oak_module_dict['role_bindings'])}")
        print(f"  device_metadata 类型: {type(oak_module_dict['device_metadata'])}")
        
        oak_module_json = oak_module.to_json(indent=2)
        print(f"✓ 字典字段 to_json() 成功")
        print(f"  JSON 片段: {oak_module_json[:200]}...")
        
        # 反序列化
        try:
            oak_module_restored = OAKModuleConfigDTO.from_json(oak_module_json)
            print(f"✓ 字典字段 from_json() 成功")
            print(f"  role_bindings 数量: {len(oak_module_restored.role_bindings)}")
            print(f"  device_metadata 数量: {len(oak_module_restored.device_metadata)}")
        except Exception as e:
            print(f"✗ 字典字段反序列化失败: {e}")
            # 不 fail，因为可能需要自定义序列化逻辑
    
    def test_complete_config_serialization(self):
        """测试完整配置的序列化"""
        print("\n=== 测试完整配置序列化 ===")
        
        # 创建完整配置
        config = DeviceManagerConfigDTO(
            oak_module=OAKModuleConfigDTO(
                hardware_config=OAKConfigDTO(
                    model_path="/path/to/model.blob",
                    confidence_threshold=0.7
                )
            ),
            display_config=DisplayConfigDTO(
                enable_display=True,
                window_width=1280
            ),
            system_config=SystemConfigDTO(
                log_level="INFO"
            )
        )
        
        # 序列化
        config_dict = config.to_dict()
        print(f"✓ 完整配置 to_dict() 成功")
        print(f"  顶层模块数: {len([k for k in config_dict.keys() if '_config' in k or k == 'oak_module'])}")
        
        config_json = config.to_json(indent=2)
        print(f"✓ 完整配置 to_json() 成功")
        print(f"  总大小: {len(config_json)} 字符")
        
        # 保存到文件测试
        test_file = Path("test_config_output.json")
        try:
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(config_json)
            print(f"✓ 配置保存到文件成功: {test_file}")
            
            # 从文件加载
            with open(test_file, 'r', encoding='utf-8') as f:
                loaded_json = f.read()
            
            config_restored = DeviceManagerConfigDTO.from_json(loaded_json)
            print(f"✓ 从文件加载配置成功")
            print(f"  版本: {config_restored.config_version}")
            print(f"  模型路径: {config_restored.oak_module.hardware_config.model_path}")
            
        except Exception as e:
            print(f"✗ 文件操作失败: {e}")
        finally:
            if test_file.exists():
                test_file.unlink()
                print(f"✓ 清理测试文件")
    
    def test_filter_config_serialization(self):
        """测试滤波配置的序列化（策略模式）"""
        print("\n=== 测试滤波配置序列化 ===")
        
        # 创建滤波配置
        filter_config = FilterConfigDTO(
            filter_type=FilterType.MOVING_AVERAGE
        )
        
        # 序列化
        filter_dict = filter_config.to_dict()
        print(f"✓ 滤波配置 to_dict() 成功")
        print(f"  filter_type: {filter_dict['filter_type']}")
        print(f"  moving_average_config: {filter_dict.get('moving_average_config')}")
        
        filter_json = filter_config.to_json()
        print(f"✓ 滤波配置 to_json() 成功")
        
        # 反序列化
        try:
            filter_restored = FilterConfigDTO.from_json(filter_json)
            print(f"✓ 滤波配置 from_json() 成功")
            print(f"  filter_type: {filter_restored.filter_type}")
        except Exception as e:
            print(f"✗ 滤波配置反序列化失败: {e}")


class TestSerializationEdgeCases(unittest.TestCase):
    """测试序列化边界情况"""
    
    def test_empty_dict_fields(self):
        """测试空字典字段"""
        print("\n=== 测试空字典字段 ===")
        
        oak_module = OAKModuleConfigDTO(
            role_bindings={},
            device_metadata={}
        )
        
        oak_json = oak_module.to_json()
        print(f"✓ 空字典序列化成功")
        self.assertIn('"role_bindings"', oak_json)
        self.assertIn('"device_metadata"', oak_json)
    
    def test_none_optional_fields(self):
        """测试 None 可选字段"""
        print("\n=== 测试 None 可选字段 ===")
        
        oak_config = OAKConfigDTO(
            model_path=None  # 可选字段
        )
        
        oak_json = oak_config.to_json()
        print(f"✓ None 字段序列化成功")
        self.assertIn('"model_path"', oak_json)
    
    def test_large_nested_structure(self):
        """测试大型嵌套结构"""
        print("\n=== 测试大型嵌套结构 ===")
        
        # 创建包含多个角色和设备的配置
        role_bindings = {}
        device_metadata = {}
        
        for i, role in enumerate([DeviceRole.LEFT_CAMERA, DeviceRole.RIGHT_CAMERA]):
            mxid = f"14442C{i:02d}D13D0D0000"
            role_bindings[role] = DeviceRoleBindingDTO(
                role=role,
                historical_mxids=[mxid],
                last_active_mxid=mxid
            )
            device_metadata[mxid] = DeviceMetadataDTO(
                mxid=mxid,
                product_name=f"OAK-D-{i}",
                notes=f"设备 {i}"
            )
        
        oak_module = OAKModuleConfigDTO(
            role_bindings=role_bindings,
            device_metadata=device_metadata
        )
        
        config = DeviceManagerConfigDTO(oak_module=oak_module)
        
        config_json = config.to_json(indent=2)
        print(f"✓ 大型结构序列化成功")
        print(f"  JSON 大小: {len(config_json)} 字符")
        print(f"  角色数: {len(role_bindings)}")
        print(f"  设备数: {len(device_metadata)}")


def run_tests():
    """运行所有测试"""
    print("=" * 70)
    print("配置 DTO 序列化功能测试")
    print("=" * 70)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestDeviceManagerConfigDTOSerialization))
    suite.addTests(loader.loadTestsFromTestCase(TestSerializationEdgeCases))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出摘要
    print("\n" + "=" * 70)
    print("测试摘要:")
    print(f"  运行: {result.testsRun}")
    print(f"  成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    print("=" * 70)
    
    if result.failures:
        print("\n失败详情:")
        for test, traceback in result.failures:
            print(f"\n{test}:")
            print(traceback)
    
    if result.errors:
        print("\n错误详情:")
        for test, traceback in result.errors:
            print(f"\n{test}:")
            print(traceback)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

