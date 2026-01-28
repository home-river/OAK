# OAK 数据采集器集成测试

## 概述

本目录包含 OAK 数据采集器（Collector）的集成测试，分为两个版本：

1. **Mock 版本** (`test_collector_integration_mock.py`) - 使用 Mock 对象模拟硬件，无需真实设备
2. **硬件版本** (`test_collector_integration_hardware.py`) - 使用真实 OAK 设备进行测试

## 测试内容

### Mock 版本测试

**测试场景：**
1. Collector 初始化和配置验证
2. 数据组装功能（RGB 帧、深度帧、检测数据）
3. 事件发布机制
4. 采集循环模拟
5. 线程生命周期管理
6. 错误处理和边界情况

**优点：**
- 不需要真实硬件
- 运行速度快
- 可以在任何环境中运行（包括 CI/CD）
- 可以测试各种边界情况和错误场景

### 硬件版本测试

**测试场景：**
1. 真实设备发现和连接
2. 真实 Pipeline 创建
3. 真实数据采集（RGB、深度、检测）
4. 多设备协同工作
5. 长时间运行稳定性
6. 性能测试（帧率、延迟）

**要求：**
- 至少一个 OAK 设备连接到计算机
- 有效的检测模型文件（.blob 格式）
- 多设备测试需要至少 2 个 OAK 设备

## 运行测试

### 方法 1: 运行 Mock 测试（推荐先运行）

```bash
# 运行所有 Mock 测试
pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_mock.py -v

# 运行特定测试类
pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_mock.py::TestCollectorInitialization -v

# 显示详细输出
pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_mock.py -v -s
```

### 方法 2: 运行硬件测试（需要真实设备）

```bash
# 运行所有硬件测试
pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_hardware.py -v -m hardware

# 运行特定测试
pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_hardware.py::TestCollectorHardwareDataCollection::test_collect_real_frames -v -m hardware

# 显示详细输出
pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_hardware.py -v -s -m hardware
```

### 方法 3: 运行所有集成测试（Mock + 硬件）

```bash
# 运行所有测试（如果有设备，硬件测试会自动运行）
pytest oak_vision_system/tests/integration/data_collector/ -v

# 只运行 Mock 测试，跳过硬件测试
pytest oak_vision_system/tests/integration/data_collector/ -v -m "not hardware"
```

## 测试配置

### Mock 测试配置

Mock 测试使用以下默认配置：
- 模型路径: `/path/to/model.blob`（Mock，不需要真实文件）
- 置信度阈值: `0.5`
- 硬件帧率: `20 fps`
- 深度输出: 可配置（默认禁用）
- 队列大小: `4`

### 硬件测试配置

硬件测试需要以下配置：
- **模型路径**: `models/mobilenet-ssd_openvino_2021.4_6shave.blob`
  - ⚠️ 需要实际的模型文件，请根据你的模型路径修改
- 置信度阈值: `0.5`
- 硬件帧率: `20 fps`
- 深度输出: 可配置
- 队列大小: `4`

**修改模型路径：**

如果你的模型文件在不同位置，请修改测试文件中的 `model_path` 参数：

```python
hardware_config=OAKConfigDTO(
    model_path="your/path/to/model.blob",  # 修改为你的模型路径
    # ...
)
```

## 测试结果示例

### Mock 测试结果

```
====================================== test session starts =======================================
collected 16 items

test_collector_integration_mock.py::TestCollectorInitialization::test_collector_creation PASSED                    [  6%]
test_collector_integration_mock.py::TestCollectorInitialization::test_collector_with_single_device PASSED          [ 12%]
test_collector_integration_mock.py::TestCollectorInitialization::test_collector_config_validation PASSED           [ 18%]
test_collector_integration_mock.py::TestDataAssembly::test_assemble_frame_data_rgb_only PASSED                     [ 25%]
test_collector_integration_mock.py::TestDataAssembly::test_assemble_frame_data_with_depth PASSED                   [ 31%]
test_collector_integration_mock.py::TestDataAssembly::test_assemble_detection_data PASSED                          [ 37%]
test_collector_integration_mock.py::TestDataAssembly::test_assemble_empty_detection_data PASSED                    [ 43%]
test_collector_integration_mock.py::TestEventPublishing::test_publish_frame_data PASSED                            [ 50%]
test_collector_integration_mock.py::TestEventPublishing::test_publish_detection_data PASSED                        [ 56%]
test_collector_integration_mock.py::TestCollectionLoopMock::test_start_single_device_mock PASSED                   [ 62%]
test_collector_integration_mock.py::TestThreadLifecycle::test_running_state_management PASSED                      [ 68%]
test_collector_integration_mock.py::TestThreadLifecycle::test_start_without_active_mxid PASSED                     [ 75%]
test_collector_integration_mock.py::TestThreadLifecycle::test_stop_collector PASSED                                [ 81%]
test_collector_integration_mock.py::TestErrorHandling::test_assemble_frame_with_none_rgb PASSED                    [ 87%]
test_collector_integration_mock.py::TestErrorHandling::test_assemble_frame_missing_depth_when_enabled PASSED       [ 93%]
test_collector_integration_mock.py::TestErrorHandling::test_assemble_detection_with_none PASSED                    [100%]

======================================= 16 passed in 2.35s ========================================
```

### 硬件测试结果

```
====================================== test session starts =======================================
collected 7 items

test_collector_integration_hardware.py::TestCollectorHardwareInitialization::test_discover_real_devices PASSED     [ 14%]
test_collector_integration_hardware.py::TestCollectorHardwareInitialization::test_create_collector_with_real_device PASSED [ 28%]
test_collector_integration_hardware.py::TestCollectorHardwareDataCollection::test_collect_real_frames PASSED       [ 42%]
test_collector_integration_hardware.py::TestCollectorHardwareDataCollection::test_collect_with_depth PASSED        [ 57%]
test_collector_integration_hardware.py::TestCollectorMultiDevice::test_collect_from_multiple_devices PASSED        [ 71%]
test_collector_integration_hardware.py::TestCollectorPerformance::test_long_running_collection PASSED              [ 85%]
test_collector_integration_hardware.py::TestCollectorPerformance::test_start_stop_multiple_times PASSED            [100%]

======================================= 7 passed in 95.42s ========================================
```

## 故障排除

### Mock 测试失败

如果 Mock 测试失败，请检查：
1. 所有依赖是否已安装（`pip install -r requirements.txt`）
2. 事件总线是否正常工作
3. DTO 验证逻辑是否正确
4. 查看日志输出中的错误信息

### 硬件测试失败

如果硬件测试失败，请检查：

1. **设备连接问题**
   - 确认 OAK 设备已连接到计算机
   - 运行 `python -c "import depthai as dai; print(dai.DeviceBootloader.getAllAvailableDevices())"` 检查设备
   - 检查 USB 线缆和端口

2. **模型文件问题**
   - 确认模型文件路径正确
   - 确认模型文件格式为 `.blob`
   - 确认模型文件与 DepthAI 版本兼容

3. **权限问题**
   - Linux 系统可能需要 udev 规则
   - 参考 DepthAI 文档配置设备权限

4. **性能问题**
   - 检查 USB 连接速度（USB 3.0 vs USB 2.0）
   - 检查系统资源（CPU、内存）
   - 降低帧率或队列大小

### 常见错误

**错误 1: "未检测到 OAK 设备"**
```
SKIPPED [1] test_collector_integration_hardware.py:45: 未检测到 OAK 设备，跳过硬件测试
```
**解决方案**: 连接 OAK 设备后重新运行测试

**错误 2: "模型文件未找到"**
```
RuntimeError: Failed to create pipeline: Model file not found
```
**解决方案**: 修改测试中的 `model_path` 为实际的模型文件路径

**错误 3: "设备启动失败"**
```
RuntimeError: 启动OAK设备LEFT_CAMERA失败
```
**解决方案**: 
- 检查设备是否被其他程序占用
- 重新插拔设备
- 重启计算机

## 测试覆盖率

### Mock 测试覆盖

- ✅ Collector 初始化（3 个测试）
- ✅ 数据组装（4 个测试）
- ✅ 事件发布（2 个测试）
- ✅ 采集循环（1 个测试）
- ✅ 线程管理（3 个测试）
- ✅ 错误处理（3 个测试）

**总计**: 16 个测试

### 硬件测试覆盖

- ✅ 设备发现（2 个测试）
- ✅ 数据采集（2 个测试）
- ✅ 多设备协同（1 个测试）
- ✅ 性能测试（2 个测试）

**总计**: 7 个测试

## 下一步

完成 Collector 集成测试后，可以：

1. **运行完整的数据流测试**
   - Collector → DataProcessor → Display 端到端测试

2. **添加更多测试场景**
   - 背压处理测试
   - 网络断开重连测试
   - 异常恢复测试

3. **性能优化**
   - 根据测试结果优化采集性能
   - 调整队列大小和帧率

4. **CI/CD 集成**
   - 在 CI 中运行 Mock 测试
   - 在有硬件的环境中运行硬件测试

## 参考资料

- [DepthAI 文档](https://docs.luxonis.com/projects/api/en/latest/)
- [Pytest 文档](https://docs.pytest.org/)
- [项目配置管理文档](../../../docs/config_architecture_refactoring.md)
