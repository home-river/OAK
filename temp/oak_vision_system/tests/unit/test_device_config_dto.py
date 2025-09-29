"""
设备配置DTO测试模块

测试设备配置相关的DTO类，包括：
- DeviceInfoDTO
- DeviceConfigDTO
- PipelineConfigDTO
- DeviceRegistryDTO
- 相关枚举类型的测试
"""

import unittest
import json
from typing import Dict, Any

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.dto.device_config_dto import (
    DeviceInfoDTO,
    DeviceConfigDTO,
    PipelineConfigDTO,
    DeviceRegistryDTO,
    DeviceType,
    ConnectionStatus,
    PipelineType
)
from core.dto.base_dto import DTOValidationError


class TestDeviceType(unittest.TestCase):
    """测试DeviceType枚举"""
    
    def test_device_type_values(self):
        """测试设备类型枚举值"""
        self.assertEqual(DeviceType.OAK_D.value, "OAK-D")
        self.assertEqual(DeviceType.OAK_D_LITE.value, "OAK-D-Lite")
        self.assertEqual(DeviceType.OAK_D_PRO.value, "OAK-D-Pro")
        self.assertEqual(DeviceType.OAK_D_S2.value, "OAK-D-S2")
        self.assertEqual(DeviceType.OAK_1.value, "OAK-1")
        self.assertEqual(DeviceType.UNKNOWN.value, "Unknown")
    
    def test_device_type_membership(self):
        """测试设备类型枚举成员"""
        device_types = list(DeviceType)
        self.assertEqual(len(device_types), 6)
        self.assertIn(DeviceType.OAK_D, device_types)
        self.assertIn(DeviceType.UNKNOWN, device_types)


class TestConnectionStatus(unittest.TestCase):
    """测试ConnectionStatus枚举"""
    
    def test_connection_status_values(self):
        """测试连接状态枚举值"""
        self.assertEqual(ConnectionStatus.CONNECTED.value, "connected")
        self.assertEqual(ConnectionStatus.DISCONNECTED.value, "disconnected")
        self.assertEqual(ConnectionStatus.BOOTLOADER.value, "bootloader")
        self.assertEqual(ConnectionStatus.UNBOOTED.value, "unbooted")
        self.assertEqual(ConnectionStatus.UNKNOWN.value, "unknown")


class TestPipelineType(unittest.TestCase):
    """测试PipelineType枚举"""
    
    def test_pipeline_type_values(self):
        """测试Pipeline类型枚举值"""
        self.assertEqual(PipelineType.DETECTION.value, "detection")
        self.assertEqual(PipelineType.DEPTH.value, "depth")
        self.assertEqual(PipelineType.COMBINED.value, "combined")
        self.assertEqual(PipelineType.CUSTOM.value, "custom")


class TestDeviceInfoDTO(unittest.TestCase):
    """测试DeviceInfoDTO"""
    
    def setUp(self):
        """设置测试数据"""
        self.valid_mxid = "1844301041B3D13700"
        self.valid_device_name = "OAK-D Camera"
    
    def test_create_valid_device_info(self):
        """测试创建有效的设备信息DTO"""
        device_info = DeviceInfoDTO(
            mxid=self.valid_mxid,
            device_type=DeviceType.OAK_D,
            connection_status=ConnectionStatus.CONNECTED,
            device_name=self.valid_device_name
        )
        
        self.assertTrue(device_info.is_data_valid())
        self.assertEqual(device_info.mxid, self.valid_mxid)
        self.assertEqual(device_info.device_type, DeviceType.OAK_D)
        self.assertEqual(device_info.connection_status, ConnectionStatus.CONNECTED)
        self.assertEqual(device_info.device_name, self.valid_device_name)
    
    def test_device_info_minimal(self):
        """测试最小化设备信息DTO"""
        device_info = DeviceInfoDTO(mxid=self.valid_mxid)
        
        self.assertTrue(device_info.is_data_valid())
        self.assertEqual(device_info.device_type, DeviceType.UNKNOWN)
        self.assertEqual(device_info.connection_status, ConnectionStatus.UNKNOWN)
        self.assertIsNone(device_info.device_name)
    
    def test_device_info_invalid_mxid(self):
        """测试无效MXid"""
        # MXid太短
        device_info = DeviceInfoDTO(mxid="123")
        self.assertFalse(device_info.is_data_valid())
        self.assertIn("mxid", str(device_info.get_validation_errors()))
        
        # 空MXid
        device_info = DeviceInfoDTO(mxid="")
        self.assertFalse(device_info.is_data_valid())
    
    def test_device_info_invalid_types(self):
        """测试无效类型"""
        # 无效设备类型
        device_info = DeviceInfoDTO(
            mxid=self.valid_mxid,
            device_type="invalid_type"  # 应该是DeviceType枚举
        )
        self.assertFalse(device_info.is_data_valid())
    
    def test_device_info_properties(self):
        """测试设备信息属性方法"""
        # 已连接设备
        connected_device = DeviceInfoDTO(
            mxid=self.valid_mxid,
            connection_status=ConnectionStatus.CONNECTED
        )
        self.assertTrue(connected_device.is_connected)
        self.assertTrue(connected_device.is_available)
        
        # Bootloader模式设备
        bootloader_device = DeviceInfoDTO(
            mxid=self.valid_mxid,
            connection_status=ConnectionStatus.BOOTLOADER
        )
        self.assertFalse(bootloader_device.is_connected)
        self.assertTrue(bootloader_device.is_available)
        
        # 断开连接的设备
        disconnected_device = DeviceInfoDTO(
            mxid=self.valid_mxid,
            connection_status=ConnectionStatus.DISCONNECTED
        )
        self.assertFalse(disconnected_device.is_connected)
        self.assertFalse(disconnected_device.is_available)
    
    def test_device_info_serialization(self):
        """测试设备信息序列化"""
        device_info = DeviceInfoDTO(
            mxid=self.valid_mxid,
            device_type=DeviceType.OAK_D,
            connection_status=ConnectionStatus.CONNECTED,
            device_name=self.valid_device_name
        )
        
        # 转换为字典
        device_dict = device_info.to_dict()
        self.assertEqual(device_dict['mxid'], self.valid_mxid)
        self.assertEqual(device_dict['device_type'], DeviceType.OAK_D)
        
        # JSON序列化
        json_str = device_info.to_json()
        self.assertIsInstance(json_str, str)
        self.assertIn(self.valid_mxid, json_str)
        
        # 从JSON反序列化
        restored_device = DeviceInfoDTO.from_json(json_str)
        self.assertEqual(restored_device.mxid, device_info.mxid)
        self.assertEqual(restored_device.device_type, device_info.device_type)


class TestDeviceConfigDTO(unittest.TestCase):
    """测试DeviceConfigDTO"""
    
    def setUp(self):
        """设置测试数据"""
        self.valid_mxid = "1844301041B3D13700"
        self.valid_alias = "left_oak"
        self.valid_properties = {"position": "left", "priority": 1}
    
    def test_create_valid_device_config(self):
        """测试创建有效的设备配置DTO"""
        device_config = DeviceConfigDTO(
            mxid=self.valid_mxid,
            alias=self.valid_alias,
            device_type=DeviceType.OAK_D,
            enabled=True,
            properties=self.valid_properties
        )
        
        self.assertTrue(device_config.is_data_valid())
        self.assertEqual(device_config.mxid, self.valid_mxid)
        self.assertEqual(device_config.alias, self.valid_alias)
        self.assertEqual(device_config.device_type, DeviceType.OAK_D)
        self.assertTrue(device_config.enabled)
        self.assertEqual(device_config.properties, self.valid_properties)
    
    def test_device_config_minimal(self):
        """测试最小化设备配置DTO"""
        device_config = DeviceConfigDTO(
            mxid=self.valid_mxid,
            alias=self.valid_alias
        )
        
        self.assertTrue(device_config.is_data_valid())
        self.assertEqual(device_config.device_type, DeviceType.UNKNOWN)
        self.assertTrue(device_config.enabled)
        self.assertEqual(device_config.properties, {})  # 默认为空字典
    
    def test_device_config_invalid_data(self):
        """测试无效设备配置数据"""
        # 无效MXid
        device_config = DeviceConfigDTO(mxid="123", alias=self.valid_alias)
        self.assertFalse(device_config.is_data_valid())
        
        # 无效别名
        device_config = DeviceConfigDTO(mxid=self.valid_mxid, alias="")
        self.assertFalse(device_config.is_data_valid())
        
        # 无效属性类型
        device_config = DeviceConfigDTO(
            mxid=self.valid_mxid,
            alias=self.valid_alias,
            properties="invalid"  # 应该是字典
        )
        self.assertFalse(device_config.is_data_valid())
    
    def test_device_config_property_methods(self):
        """测试设备配置属性方法"""
        device_config = DeviceConfigDTO(
            mxid=self.valid_mxid,
            alias=self.valid_alias,
            properties={"position": "left", "priority": 1, "enabled": True}
        )
        
        # 获取属性
        self.assertEqual(device_config.get_property("position"), "left")
        self.assertEqual(device_config.get_property("priority"), 1)
        self.assertEqual(device_config.get_property("nonexistent", "default"), "default")
        
        # 检查属性存在
        self.assertTrue(device_config.has_property("position"))
        self.assertFalse(device_config.has_property("nonexistent"))
    
    def test_device_config_serialization(self):
        """测试设备配置序列化"""
        device_config = DeviceConfigDTO(
            mxid=self.valid_mxid,
            alias=self.valid_alias,
            device_type=DeviceType.OAK_D,
            properties=self.valid_properties
        )
        
        # JSON序列化和反序列化
        json_str = device_config.to_json()
        restored_config = DeviceConfigDTO.from_json(json_str)
        
        self.assertEqual(restored_config.mxid, device_config.mxid)
        self.assertEqual(restored_config.alias, device_config.alias)
        self.assertEqual(restored_config.device_type, device_config.device_type)
        self.assertEqual(restored_config.properties, device_config.properties)


class TestPipelineConfigDTO(unittest.TestCase):
    """测试PipelineConfigDTO"""
    
    def setUp(self):
        """设置测试数据"""
        self.valid_model_path = "/path/to/model.blob"
        self.valid_config_params = {"custom_param": "value"}
    
    def test_create_valid_detection_pipeline(self):
        """测试创建有效的检测Pipeline配置"""
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.DETECTION,
            model_path=self.valid_model_path,
            input_resolution=(416, 416),
            confidence_threshold=0.6,
            nms_threshold=0.4,
            max_detections=15,
            enable_depth=True,
            depth_resolution=(640, 480),
            fps=30,
            config_params=self.valid_config_params
        )
        
        self.assertTrue(pipeline_config.is_data_valid())
        self.assertEqual(pipeline_config.pipeline_type, PipelineType.DETECTION)
        self.assertEqual(pipeline_config.model_path, self.valid_model_path)
        self.assertEqual(pipeline_config.input_resolution, (416, 416))
        self.assertEqual(pipeline_config.confidence_threshold, 0.6)
    
    def test_create_valid_depth_pipeline(self):
        """测试创建有效的深度Pipeline配置"""
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.DEPTH,
            # 深度Pipeline不需要模型路径
            input_resolution=(640, 480),
            enable_depth=True,
            depth_resolution=(640, 480)
        )
        
        self.assertTrue(pipeline_config.is_data_valid())
        self.assertEqual(pipeline_config.pipeline_type, PipelineType.DEPTH)
        self.assertIsNone(pipeline_config.model_path)
    
    def test_pipeline_config_minimal(self):
        """测试最小化Pipeline配置"""
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.DEPTH  # 深度Pipeline不需要模型
        )
        
        self.assertTrue(pipeline_config.is_data_valid())
        self.assertEqual(pipeline_config.input_resolution, (416, 416))  # 默认值
        self.assertEqual(pipeline_config.confidence_threshold, 0.5)  # 默认值
        self.assertEqual(pipeline_config.config_params, {})  # 默认为空字典
    
    def test_pipeline_config_invalid_data(self):
        """测试无效Pipeline配置数据"""
        # 检测Pipeline缺少模型路径
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.DETECTION
            # 缺少model_path
        )
        self.assertFalse(pipeline_config.is_data_valid())
        self.assertIn("检测Pipeline必须指定model_path", str(pipeline_config.get_validation_errors()))
        
        # 无效置信度阈值
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.DEPTH,
            confidence_threshold=1.5  # 超出范围
        )
        self.assertFalse(pipeline_config.is_data_valid())
        
        # 无效分辨率
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.DEPTH,
            input_resolution=(0, 480)  # 宽度为0
        )
        self.assertFalse(pipeline_config.is_data_valid())
        
        # 无效帧率
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.DEPTH,
            fps=0  # 帧率为0
        )
        self.assertFalse(pipeline_config.is_data_valid())
    
    def test_pipeline_config_properties(self):
        """测试Pipeline配置属性方法"""
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.COMBINED,
            input_resolution=(320, 240),
            depth_resolution=(640, 480),
            config_params={"param1": "value1", "param2": 123}
        )
        
        # 分辨率字符串
        self.assertEqual(pipeline_config.resolution_string, "320x240")
        self.assertEqual(pipeline_config.depth_resolution_string, "640x480")
        
        # 配置参数
        self.assertEqual(pipeline_config.get_config_param("param1"), "value1")
        self.assertEqual(pipeline_config.get_config_param("param2"), 123)
        self.assertEqual(pipeline_config.get_config_param("nonexistent", "default"), "default")
    
    def test_pipeline_config_serialization(self):
        """测试Pipeline配置序列化"""
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.COMBINED,
            model_path=self.valid_model_path,
            input_resolution=(416, 416),
            confidence_threshold=0.7,
            config_params=self.valid_config_params
        )
        
        # JSON序列化和反序列化
        json_str = pipeline_config.to_json()
        restored_config = PipelineConfigDTO.from_json(json_str)
        
        self.assertEqual(restored_config.pipeline_type, pipeline_config.pipeline_type)
        self.assertEqual(restored_config.model_path, pipeline_config.model_path)
        self.assertEqual(restored_config.input_resolution, pipeline_config.input_resolution)
        self.assertEqual(restored_config.confidence_threshold, pipeline_config.confidence_threshold)


class TestDeviceRegistryDTO(unittest.TestCase):
    """测试DeviceRegistryDTO"""
    
    def setUp(self):
        """设置测试数据"""
        self.device1 = DeviceConfigDTO(
            mxid="1844301041B3D13700",
            alias="left_oak",
            device_type=DeviceType.OAK_D
        )
        self.device2 = DeviceConfigDTO(
            mxid="1844301041B3D13701",
            alias="right_oak",
            device_type=DeviceType.OAK_D,
            enabled=False
        )
        self.pipeline1 = PipelineConfigDTO(
            pipeline_type=PipelineType.DETECTION,
            model_path="/path/to/model.blob"
        )
        self.pipeline2 = PipelineConfigDTO(
            pipeline_type=PipelineType.DEPTH
        )
    
    def test_create_valid_device_registry(self):
        """测试创建有效的设备注册表DTO"""
        devices = {
            self.device1.mxid: self.device1,
            self.device2.mxid: self.device2
        }
        pipeline_configs = {
            self.device1.alias: self.pipeline1,
            self.device2.alias: self.pipeline2
        }
        global_settings = {"setting1": "value1", "setting2": 123}
        
        registry = DeviceRegistryDTO(
            config_version="2.0.0",
            devices=devices,
            pipeline_configs=pipeline_configs,
            global_settings=global_settings
        )
        
        self.assertTrue(registry.is_data_valid())
        self.assertEqual(registry.config_version, "2.0.0")
        self.assertEqual(len(registry.devices), 2)
        self.assertEqual(len(registry.pipeline_configs), 2)
        self.assertEqual(registry.global_settings, global_settings)
    
    def test_device_registry_minimal(self):
        """测试最小化设备注册表DTO"""
        registry = DeviceRegistryDTO()
        
        self.assertTrue(registry.is_data_valid())
        self.assertEqual(registry.config_version, "2.0.0")
        self.assertEqual(registry.devices, {})  # 默认为空字典
        self.assertEqual(registry.pipeline_configs, {})  # 默认为空字典
        self.assertEqual(registry.global_settings, {})  # 默认为空字典
    
    def test_device_registry_invalid_data(self):
        """测试无效设备注册表数据"""
        # 无效配置版本
        registry = DeviceRegistryDTO(config_version="")
        self.assertFalse(registry.is_data_valid())
        
        # 无效设备字典
        registry = DeviceRegistryDTO(
            devices={"invalid_key": "not_a_device_config"}
        )
        self.assertFalse(registry.is_data_valid())
        
        # 无效Pipeline配置字典
        registry = DeviceRegistryDTO(
            pipeline_configs={"invalid_key": "not_a_pipeline_config"}
        )
        self.assertFalse(registry.is_data_valid())
    
    def test_device_registry_properties(self):
        """测试设备注册表属性方法"""
        devices = {
            self.device1.mxid: self.device1,
            self.device2.mxid: self.device2  # enabled=False
        }
        pipeline_configs = {
            self.device1.alias: self.pipeline1
        }
        
        registry = DeviceRegistryDTO(
            devices=devices,
            pipeline_configs=pipeline_configs
        )
        
        # 设备数量
        self.assertEqual(registry.device_count, 2)
        self.assertEqual(registry.enabled_device_count, 1)  # 只有device1启用
        
        # 获取设备配置
        retrieved_device = registry.get_device_config(self.device1.mxid)
        self.assertEqual(retrieved_device, self.device1)
        
        # 根据别名获取设备
        device_by_alias = registry.get_device_by_alias(self.device1.alias)
        self.assertEqual(device_by_alias, self.device1)
        
        # 获取Pipeline配置
        pipeline_config = registry.get_pipeline_config(self.device1.alias)
        self.assertEqual(pipeline_config, self.pipeline1)
        
        # 获取别名和MXid列表
        aliases = registry.get_aliases()
        self.assertIn(self.device1.alias, aliases)
        self.assertIn(self.device2.alias, aliases)
        
        mxids = registry.get_mxids()
        self.assertIn(self.device1.mxid, mxids)
        self.assertIn(self.device2.mxid, mxids)
    
    def test_device_registry_serialization(self):
        """测试设备注册表序列化"""
        devices = {self.device1.mxid: self.device1}
        pipeline_configs = {self.device1.alias: self.pipeline1}
        
        registry = DeviceRegistryDTO(
            config_version="2.0.0",
            devices=devices,
            pipeline_configs=pipeline_configs,
            global_settings={"test": "value"}
        )
        
        # JSON序列化和反序列化
        json_str = registry.to_json()
        restored_registry = DeviceRegistryDTO.from_json(json_str)
        
        self.assertEqual(restored_registry.config_version, registry.config_version)
        self.assertEqual(restored_registry.device_count, registry.device_count)
        self.assertEqual(len(restored_registry.pipeline_configs), len(registry.pipeline_configs))
        self.assertEqual(restored_registry.global_settings, registry.global_settings)


class TestDeviceConfigDTOIntegration(unittest.TestCase):
    """设备配置DTO集成测试"""
    
    def test_complete_device_configuration_workflow(self):
        """测试完整的设备配置工作流程"""
        # 1. 创建设备信息
        device_info = DeviceInfoDTO(
            mxid="1844301041B3D13700",
            device_type=DeviceType.OAK_D,
            connection_status=ConnectionStatus.CONNECTED,
            device_name="Left OAK-D Camera"
        )
        
        # 2. 创建设备配置
        device_config = DeviceConfigDTO(
            mxid=device_info.mxid,
            alias="left_oak",
            device_type=device_info.device_type,
            enabled=True,
            properties={"position": "left", "calibrated": True}
        )
        
        # 3. 创建Pipeline配置
        pipeline_config = PipelineConfigDTO(
            pipeline_type=PipelineType.COMBINED,
            model_path="/models/yolo_oak.blob",
            input_resolution=(416, 416),
            confidence_threshold=0.6,
            enable_depth=True,
            config_params={"spatial_detection": True}
        )
        
        # 4. 创建设备注册表
        registry = DeviceRegistryDTO(
            config_version="2.0.0",
            devices={device_config.mxid: device_config},
            pipeline_configs={device_config.alias: pipeline_config},
            global_settings={
                "auto_discovery": True,
                "health_check_interval": 30.0
            }
        )
        
        # 验证所有DTO都有效
        self.assertTrue(device_info.is_data_valid())
        self.assertTrue(device_config.is_data_valid())
        self.assertTrue(pipeline_config.is_data_valid())
        self.assertTrue(registry.is_data_valid())
        
        # 验证数据一致性
        self.assertEqual(device_info.mxid, device_config.mxid)
        self.assertEqual(device_info.device_type, device_config.device_type)
        self.assertEqual(registry.get_device_config(device_config.mxid), device_config)
        self.assertEqual(registry.get_pipeline_config(device_config.alias), pipeline_config)
        
        # 验证序列化和反序列化
        registry_json = registry.to_json()
        restored_registry = DeviceRegistryDTO.from_json(registry_json)
        
        self.assertTrue(restored_registry.is_data_valid())
        self.assertEqual(restored_registry.device_count, 1)
        self.assertEqual(len(restored_registry.pipeline_configs), 1)
    
    def test_error_handling_and_validation(self):
        """测试错误处理和验证"""
        # 测试无效数据的处理
        invalid_cases = [
            # 无效MXid
            {"mxid": "", "alias": "test", "expected_error": "mxid"},
            # 无效别名
            {"mxid": "1844301041B3D13700", "alias": "", "expected_error": "alias"},
            # 无效属性类型
            {"mxid": "1844301041B3D13700", "alias": "test", "properties": "invalid", "expected_error": "properties"}
        ]
        
        for case in invalid_cases:
            with self.subTest(case=case):
                device_config = DeviceConfigDTO(
                    mxid=case["mxid"],
                    alias=case["alias"],
                    properties=case.get("properties")
                )
                
                self.assertFalse(device_config.is_data_valid())
                errors = device_config.get_validation_errors()
                self.assertTrue(any(case["expected_error"] in str(error) for error in errors))
    
    def test_dto_immutability(self):
        """测试DTO不可变性"""
        device_config = DeviceConfigDTO(
            mxid="1844301041B3D13700",
            alias="test_device"
        )
        
        # 尝试修改不可变对象应该抛出异常
        with self.assertRaises(Exception):
            device_config.mxid = "new_mxid"
        
        with self.assertRaises(Exception):
            device_config.alias = "new_alias"


if __name__ == '__main__':
    # 创建测试套件
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestDeviceType,
        TestConnectionStatus,
        TestPipelineType,
        TestDeviceInfoDTO,
        TestDeviceConfigDTO,
        TestPipelineConfigDTO,
        TestDeviceRegistryDTO,
        TestDeviceConfigDTOIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出测试结果摘要
    print(f"\n{'='*50}")
    print(f"测试摘要:")
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"{'='*50}")
    
    if result.failures:
        print(f"\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
