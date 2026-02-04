# 测试套件运行结果记录

## 测试执行时间
开始时间: 2026-02-03

## 测试范围
- 排除: CAN 模块测试 (oak_vision_system/tests/unit/can_communication)
- 排除: Manual 测试 (oak_vision_system/tests/manual)

---

## 1. DTO 测试套件

**测试路径**: `oak_vision_system/tests/unit/dto`

**总计**: 61 个测试
- ✅ 通过: 49
- ❌ 失败: 12
- ⏭️ 跳过: 0

### 失败的测试

1. `test_base_dto.py::TestBaseDTO::test_to_dict_conversion`
   - 错误: `AssertionError: assert 'version' in {...}`
   - 原因: `to_dict()` 默认不包含元数据字段

2. `test_config_dto_serialization.py::TestDeviceManagerConfigDTOSerialization::test_complete_config_serialization`
   - 错误: `NameError: name 'Path' is not defined`
   - 原因: 缺少 `Path` 导入

3. `test_detection_dto.py::TestDetectionDTO::test_valid_detection_creation`
   - 错误: `AttributeError: 'DetectionDTO' object has no attribute 'created_at'`
   - 原因: 测试引用了已删除的 `created_at` 字段

4. `test_detection_dto.py::TestDeviceDetectionDataDTO::test_valid_device_data_creation`
   - 错误: `AttributeError: 'DeviceDetectionDataDTO' object has no attribute 'created_at'`
   - 原因: 测试引用了已删除的 `created_at` 字段

5. `test_detection_dto.py::TestVideoFrameDTO::test_valid_video_frame_creation`
   - 错误: `AttributeError: 'VideoFrameDTO' object has no attribute 'created_at'`
   - 原因: 测试引用了已删除的 `created_at` 字段

6. `test_detection_dto.py::TestOAKDataCollectionDTO::test_valid_collection_creation`
   - 错误: `AttributeError: 'OAKDataCollectionDTO' object has no attribute 'created_at'`
   - 原因: 测试引用了已删除的 `created_at` 字段

7. `test_detection_dto.py::TestOAKDataCollectionDTO::test_collection_with_data`
   - 错误: `TypeError: DeviceDetectionDataDTO.__init__() missing 1 required positional argument: 'frame_id'`
   - 原因: 缺少必需的 `frame_id` 参数

8. `test_detection_dto.py::TestDTOIntegration::test_dto_serialization`
   - 错误: `AttributeError: 'SpatialCoordinatesDTO' object has no attribute 'to_json'`
   - 原因: DTO 方法变更

9. `test_detection_dto.py::TestDTOIntegration::test_dto_dict_conversion`
   - 错误: `AttributeError: 'BoundingBoxDTO' object has no attribute 'to_dict'`
   - 原因: DTO 方法变更

10. `test_detection_dto.py::TestDTOIntegration::test_complex_dto_composition`
    - 错误: `AssertionError: 验证失败: ['label必须为数值类型，当前类型: str']`
    - 原因: `label` 类型从字符串改为整数

11. `test_dto_validation.py::TestConfigDTOSmokeTest::test_oak_config_dto_smoke`
    - 错误: `AssertionError: OAK配置验证失败: ['model_path指向的模型文件不存在或不可读']`
    - 原因: 测试数据问题

12. `test_dto_validation.py::TestConfigDTOSmokeTest::test_system_config_dto_smoke`
    - 错误: `TypeError: SystemConfigDTO.__init__() got an unexpected keyword argument 'enable_can_communication'`
    - 原因: 构造函数参数变更

---

## 2. EventBus 测试套件

**测试路径**: `oak_vision_system/tests/unit/bus`

**总计**: 15 个测试
- ✅ 通过: 4
- ❌ 失败: 11
- ⏭️ 跳过: 0

### 失败的测试

1. `test_event_bus.py::TestEventBusBasics::test_event_bus_creation`
   - 错误: `AttributeError: 'EventBus' object has no attribute 'get_all_event_types'`
   - 原因: 方法已从 API 中移除

2. `test_event_bus.py::TestEventBusBasics::test_subscribe_and_publish`
   - 错误: `AttributeError: 'EventBus' object has no attribute 'get_subscriber_count'`
   - 原因: 方法已从 API 中移除

3. `test_event_bus.py::TestEventBusBasics::test_multiple_subscribers`
   - 错误: `AttributeError: 'EventBus' object has no attribute 'get_subscriber_count'`
   - 原因: 方法已从 API 中移除

4. `test_event_bus.py::TestEventBusBasics::test_unsubscribe`
   - 错误: `AttributeError: 'EventBus' object has no attribute 'get_subscriber_count'`
   - 原因: 方法已从 API 中移除

5. `test_event_bus.py::TestEventBusMultipleEventTypes::test_different_event_types`
   - 错误: `AssertionError: assert [] == ['detection']`
   - 原因: 事件类型查询方法变更

6. `test_event_bus.py::TestEventBusMultipleEventTypes::test_get_all_event_types`
   - 错误: `AttributeError: type object 'EventType' has no attribute 'TARGET_COORDINATES'`
   - 原因: 事件类型枚举变更

7. `test_event_bus.py::TestEventBusErrorHandling::test_subscriber_exception_isolation`
   - 错误: `assert 2 == 1`
   - 原因: 异常隔离行为变更

8. `test_event_bus.py::TestEventBusThreadSafety::test_concurrent_subscribe`
   - 错误: `AttributeError: 'EventBus' object has no attribute 'get_subscriber_count'`
   - 原因: 方法已从 API 中移除

9. `test_event_bus.py::TestEventBusThreadSafety::test_concurrent_publish`
   - 错误: `assert 49 == 50`
   - 原因: 并发发布行为变更

10. `test_event_bus.py::TestEventBusPerformance::test_publish_performance`
    - 错误: `assert 990 == 1000`
    - 原因: 发布行为变更

11. `test_event_bus.py::TestEventBusRepr::test_repr`
    - 错误: `AssertionError: assert 'event_types=1' in '<...EventBus object at ...>'`
    - 原因: `__repr__` 方法实现变更

---

## 3. DataProcessor 测试套件

**测试路径**: `oak_vision_system/tests/unit/modules/data_processing/test_data_processor.py`

**总计**: 55 个测试
- ✅ 通过: 46
- ❌ 失败: 9
- ⏭️ 跳过: 0

### 失败的测试

所有失败都与空检测列表处理相关：

1. `TestDataProcessorTransform::test_transform_with_empty_detections`
   - 错误: `AssertionError: 空检测列表应该返回 None`
   - 原因: 业务逻辑变更，现在返回空结果而非 None

2. `TestDataProcessorFilter::test_filter_with_empty_detections`
   - 错误: `AssertionError: 空检测列表应该返回 None`
   - 原因: 业务逻辑变更

3. `TestDataProcessorAssembly::test_state_label_initialized_empty`
   - 错误: `AssertionError: state_label 应该初始化为空列表`
   - 原因: 字段初始化逻辑变更

4. `TestDataProcessorAssembly::test_empty_output_handling`
   - 错误: `AssertionError: 空输入应该返回 None`
   - 原因: 业务逻辑变更

5. `TestDataProcessorAssembly::test_empty_output_correct_dtypes`
   - 错误: `AssertionError: 空输入（detections=None）应该返回 None`
   - 原因: 业务逻辑变更

6. `TestDataProcessorEvent::test_event_publish_with_empty_detections`
   - 错误: `AssertionError: 空检测列表不应该发布事件（返回 None）`
   - 原因: 事件发布逻辑变更

7. `TestDataProcessorEvent::test_event_data_contains_all_fields`
   - 错误: `assert [<DetectionStatus...DANGEROUS: 1>] == []`
   - 原因: 字段内容不匹配

8. `TestDataProcessorIntegration::test_empty_input_handling_in_flow`
   - 错误: `AssertionError: 空检测列表应该返回 None`
   - 原因: 业务逻辑变更

9. `TestDataProcessorIntegration::test_none_detections_handling_in_flow`
   - 错误: `AssertionError: None detections 应该返回 None`
   - 原因: 业务逻辑变更

---

## 4. DisplayManager 测试套件

**测试路径**: `oak_vision_system/tests/unit/modules/display_modules/test_display_graceful_shutdown.py`

**总计**: 6 个测试
- ✅ 通过: 5
- ❌ 失败: 1
- ⏭️ 跳过: 0

### 失败的测试

1. `test_display_graceful_shutdown.py::TestGracefulShutdown::test_packager_clears_resources`
   - 错误: `AssertionError: 2 != 0`
   - 原因: 资源清理验证逻辑不匹配

---

## 5. ConfigManager 测试套件

**测试路径**: `oak_vision_system/tests/unit/modules/config_manager`

**总计**: 119 个测试
- ✅ 通过: 118
- ❌ 失败: 1
- ⏭️ 跳过: 0

### 失败的测试

1. `test_config_converter_properties.py::test_property_round_trip_yaml_json_yaml`
   - 错误: 未显示详细信息
   - 原因: YAML 往返转换属性测试失败

---

## 6. DataCollector 测试套件

**测试路径**: `oak_vision_system/tests/unit/modules/data_collector`

**总计**: 9 个测试
- ✅ 通过: 9
- ❌ 失败: 0
- ⏭️ 跳过: 0

### 状态
✅ 所有测试通过

---

