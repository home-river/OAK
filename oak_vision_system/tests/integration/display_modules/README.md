# 显示模块集成测试

## 概述

本目录包含显示模块的 MVP 集成测试，用于验证显示模块的核心功能。

## 测试内容

### MVP 集成测试 (`test_display_module_mvp.py`)

测试场景：
1. **DisplayManager 创建** - 验证主控制器和子模块的创建
2. **DisplayManager 启动停止** - 验证生命周期管理
3. **RenderPacketPackager 数据配对** - 验证数据适配和配对功能
4. **空检测帧处理** - 验证空检测帧不会导致崩溃
5. **多设备支持** - 验证多设备独立队列和窗口管理
6. **缓存机制** - 验证队列为空时使用缓存帧
7. **统计信息收集** - 验证统计信息的收集和聚合
8. **错误处理** - 验证错误处理机制

验证需求：
- 需求 1.1-1.9: 基础架构和线程管理
- 需求 2.1-2.7: 基础窗口显示
- 需求 3.1-3.6: 基础检测框绘制
- 需求 4.1-4.6: 配置加载
- 需求 5.1-5.6: 错误处理
- 需求 15.1-15.2: 空帧处理
- 需求 16.1-16.6: 多设备支持

## 运行测试

### 方法 1: 使用 pytest（推荐）

```bash
# 运行所有测试
pytest oak_vision_system/tests/integration/display_modules/test_display_module_mvp.py -v

# 运行特定测试
pytest oak_vision_system/tests/integration/display_modules/test_display_module_mvp.py::test_display_manager_creation -v

# 显示详细输出
pytest oak_vision_system/tests/integration/display_modules/test_display_module_mvp.py -v -s
```

### 方法 2: 直接运行测试脚本

```bash
# 运行测试脚本
python oak_vision_system/tests/integration/display_modules/test_display_module_mvp.py

# 或使用运行脚本
python oak_vision_system/tests/integration/display_modules/run_mvp_tests.py
```

## 测试配置

测试使用以下配置：
- `enable_display=False` - 禁用窗口显示（避免在无头环境中失败）
- `window_width=1280` - 窗口宽度
- `window_height=720` - 窗口高度
- `target_fps=20` - 目标帧率

## 注意事项

1. **无头环境** - 测试默认禁用窗口显示（`enable_display=False`），可以在无头环境中运行
2. **事件总线** - 测试使用全局事件总线，确保测试之间的隔离
3. **时间延迟** - 测试中包含适当的延迟以确保异步操作完成
4. **资源清理** - 每个测试都会正确清理资源（停止 DisplayManager）

## 测试结果示例

```
====================================== test session starts =======================================
platform win32 -- Python 3.10.18, pytest-7.4.3, pluggy-1.5.0
collected 8 items

test_display_module_mvp.py::test_display_manager_creation PASSED                           [ 12%]
test_display_module_mvp.py::test_display_manager_start_stop PASSED                         [ 25%]
test_display_module_mvp.py::test_render_packet_packager_pairing PASSED                     [ 37%]
test_display_module_mvp.py::test_empty_detection_frame_handling PASSED                     [ 50%]
test_display_module_mvp.py::test_multiple_devices_support PASSED                           [ 62%]
test_display_module_mvp.py::test_cache_mechanism PASSED                                    [ 75%]
test_display_module_mvp.py::test_statistics_collection PASSED                              [ 87%]
test_display_module_mvp.py::test_error_handling PASSED                                     [100%]

======================================= 8 passed in 7.35s ========================================
```

## 故障排除

### 测试失败

如果测试失败，请检查：
1. 所有依赖是否已安装（`pip install -r requirements.txt`）
2. 事件总线是否正常工作
3. 日志输出中的错误信息

### 超时问题

如果测试超时，可能需要：
1. 增加等待时间（修改 `time.sleep()` 的值）
2. 检查系统性能
3. 检查是否有其他进程占用资源

## 下一步

完成 MVP 测试后，可以继续实现完整功能：
- 任务 9: 完整的检测信息叠加
- 任务 10: 按标签着色
- 任务 11: FPS 和设备信息显示
- 任务 12: 多种显示模式
- 等等...

参考 `.kiro/specs/display-module/tasks.md` 了解完整的任务列表。
