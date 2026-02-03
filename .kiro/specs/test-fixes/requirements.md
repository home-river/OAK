# Requirements Document: 测试修复需求记录

## Introduction

**本文档仅用于记录测试失败问题的需求，不包含设计方案或实施计划。**

本需求记录文档详细记录了在 SystemManager 模块开发过程中发现的测试失败问题。这些问题在代码迁移验证过程中被发现，与当前的代码迁移工作无关，是 config_manager 模块的历史遗留问题。

**文档目的:**
1. 详细记录每个测试失败的现象和原因
2. 分析问题的影响范围和严重程度
3. 评估修复的优先级和预计工作量
4. 为未来的修复工作提供需求基础

**文档范围:**
- ✅ 包含：问题描述、失败测试列表、影响分析、优先级评估
- ❌ 不包含：具体修复方案、实施步骤、代码示例

**使用说明:**
- 本文档作为问题记录和需求说明
- 实际修复时需要基于本文档创建设计文档（design.md）
- 实际修复时需要基于设计文档创建任务清单（tasks.md）

## Glossary

- **Test Suite**: 测试套件，包含单元测试和集成测试
- **DeviceMatchManager**: 设备匹配管理器模块
- **ConfigConverter**: 配置转换器模块
- **API Signature**: API 签名，指函数或方法的参数列表
- **Error Handling**: 错误处理机制
- **Test Coverage**: 测试覆盖率

## Requirements

### Requirement 1: 修复 DeviceMatchManager API 变更导致的测试失败

**User Story:** 作为开发者，我希望修复 DeviceMatchManager 模块的测试失败，以确保设备匹配功能的正确性。

#### Acceptance Criteria

1. WHEN 运行 `test_device_match.py` 中的测试 THEN THE System SHALL 确保所有测试通过
2. WHEN `default_match_devices()` 方法被调用 THEN THE System SHALL 使用正确的参数签名
3. WHEN 空绑定配置被传入 THEN THE System SHALL 正确处理并创建默认配置
4. THE System SHALL 更新所有受影响的测试用例（31个）
5. THE System SHALL 确保 API 变更不破坏现有功能

**影响范围:**
- `oak_vision_system/tests/unit/modules/config_manager/test_device_match.py`
- 31个失败的测试用例

**失败测试列表:**
1. `TestDeviceMatchManagerInit::test_init_with_empty_bindings_creates_default`
2. `TestDeviceMatching::test_full_match_with_history`
3. `TestDeviceMatching::test_partial_match_one_device_offline`
4. `TestDeviceMatching::test_no_match_all_devices_offline`
5. `TestDeviceMatching::test_auto_bind_new_devices_enabled`
6. `TestDeviceMatching::test_auto_bind_new_devices_disabled`
7. `TestDeviceMatching::test_match_priority_last_active_over_historical`
8. `TestManualBinding::test_unbind_role_success`
9. `TestManualBinding::test_unbind_all_devices`
10. `TestManualBinding::test_swap_devices_success`
11. `TestManualBinding::test_swap_devices_one_not_bound`
12. `TestConfigValidation::test_validate_match_result_can_start`
13. `TestConfigValidation::test_validate_match_result_partial_match_with_warning`
14. `TestConfigValidation::test_validate_match_result_no_match_cannot_start`
15. `TestQueryInterfaces::test_is_role_matched`
16. `TestQueryInterfaces::test_is_device_bound`
17. `TestQueryInterfaces::test_list_matched_devices`
18. `TestQueryInterfaces::test_list_available_devices`
19. `TestQueryInterfaces::test_get_unmatched_roles`
20. `TestStateExport::test_get_current_status`
21. `TestStateExport::test_export_bindings`
22. `TestStateExport::test_get_match_summary`
23. `TestEdgeCases::test_empty_online_devices`
24. `TestEdgeCases::test_more_devices_than_roles`
25. `TestEdgeCases::test_rematch_after_device_change`
26. `TestEdgeCases::test_toggle_auto_bind_switch`
27. `TestEdgeCases::test_reset_to_default_bindings_result`
28. `TestIntegrationScenarios::test_typical_startup_flow`
29. `TestIntegrationScenarios::test_device_swap_scenario`
30. `TestIntegrationScenarios::test_device_replacement_scenario`
31. 其他相关测试

**错误类型:**
- `TypeError: DeviceMatchManager.default_match_devices() missing 1 required positional argument: 'online_devices'`
- `ValueError: Invalid bindings: 绑定结果为空,请先填入默认DeviceRoleBindingDTO`

---

### Requirement 2: 修复 YAML 错误处理相关测试

**User Story:** 作为开发者，我希望修复 YAML 错误处理的测试失败，以确保配置文件解析的健壮性。

#### Acceptance Criteria

1. WHEN YAML 文件格式错误 THEN THE System SHALL 抛出正确的异常类型
2. WHEN 测试期望捕获特定异常 THEN THE System SHALL 确保异常类型匹配
3. THE System SHALL 统一 YAML 错误处理机制
4. THE System SHALL 更新所有受影响的测试用例（5个）
5. THE System SHALL 确保错误消息清晰易懂

**影响范围:**
- `oak_vision_system/tests/unit/modules/config_manager/test_config_manager_format_support.py`
- `oak_vision_system/tests/integration/config_manager/test_config_manager_yaml_support.py`
- `oak_vision_system/modules/config_manager/config_converter.py`

**失败测试列表:**
1. `TestErrorHandling::test_invalid_yaml_format`
2. `TestErrorHandling::test_pyyaml_not_installed_load`
3. `TestErrorHandling::test_pyyaml_not_installed_export`
4. `TestConfigValidationIntegration::test_invalid_yaml_config_validation_fails`
5. `TestErrorHandlingIntegration::test_yaml_parse_error_handling`

**错误类型:**
- `Exception: YAML 文件读取失败: mapping values are not allowed here`
- 测试期望 `ConfigValidationError` 或 `yaml.YAMLError`，但实际抛出 `Exception`
- 测试期望 `ImportError`，但实际没有抛出异常（因为 ruamel.yaml 已安装）

**问题分析:**
1. `ConfigConverter.load_yaml_as_dict()` 捕获所有异常并重新抛出为通用 `Exception`
2. 测试期望更具体的异常类型（`ConfigValidationError` 或 `yaml.YAMLError`）
3. PyYAML 未安装的测试在 ruamel.yaml 已安装时无法正确模拟

---

### Requirement 3: 修复文件编码相关测试

**User Story:** 作为开发者，我希望修复文件编码相关的测试失败，以确保跨平台兼容性。

#### Acceptance Criteria

1. WHEN 在 Windows 系统上运行测试 THEN THE System SHALL 正确处理文件编码
2. WHEN 读取 JSON 文件 THEN THE System SHALL 使用 UTF-8 编码
3. THE System SHALL 确保所有文件操作明确指定编码
4. THE System SHALL 更新受影响的测试用例（1个）
5. THE System SHALL 在所有平台上保持一致的行为

**影响范围:**
- `oak_vision_system/tests/integration/config_manager/test_cli_generate_config.py`

**失败测试列表:**
1. `test_cli_generate_json_content`

**错误类型:**
- `UnicodeDecodeError: 'gbk' codec can't decode byte 0xaa in position 1521: illegal multibyte sequence`

**问题分析:**
1. 测试在读取 JSON 文件时未指定编码
2. Windows 系统默认使用 GBK 编码
3. 文件内容包含非 ASCII 字符，导致解码失败

**修复建议:**
```python
# 修改前
with open(json_file) as f:
    config = json.load(f)

# 修改后
with open(json_file, encoding='utf-8') as f:
    config = json.load(f)
```

---

### Requirement 4: 优化测试套件结构

**User Story:** 作为开发者，我希望优化测试套件的结构和组织，以提高可维护性和可读性。

#### Acceptance Criteria

1. THE System SHALL 识别并移除重复的测试用例
2. THE System SHALL 合并功能相似的测试
3. THE System SHALL 确保测试命名清晰且一致
4. THE System SHALL 为每个测试添加清晰的文档字符串
5. THE System SHALL 确保测试覆盖率不降低

**优化目标:**
- 减少测试冗余
- 提高测试执行速度
- 改善测试可读性
- 统一测试风格

---

### Requirement 5: 建立测试修复优先级

**User Story:** 作为项目管理者，我希望建立测试修复的优先级，以合理分配资源。

#### Acceptance Criteria

1. THE System SHALL 将测试失败按严重程度分类
2. THE System SHALL 优先修复影响核心功能的测试
3. THE System SHALL 记录每个测试失败的影响范围
4. THE System SHALL 提供修复时间估算
5. THE System SHALL 跟踪修复进度

**优先级分类:**

**P0 - 紧急（阻塞发布）:**
- 无（当前所有失败都不阻塞核心功能）

**P1 - 高优先级（影响主要功能）:**
- Requirement 1: DeviceMatchManager API 变更（31个测试）
- Requirement 2: YAML 错误处理（5个测试）

**P2 - 中优先级（影响次要功能）:**
- Requirement 3: 文件编码问题（1个测试）

**P3 - 低优先级（优化改进）:**
- Requirement 4: 测试套件优化

---

### Requirement 6: 建立测试修复验证流程

**User Story:** 作为质量保证人员，我希望建立测试修复的验证流程，以确保修复的有效性。

#### Acceptance Criteria

1. WHEN 测试被修复 THEN THE System SHALL 运行完整的测试套件
2. WHEN 修复引入新代码 THEN THE System SHALL 确保不破坏现有功能
3. THE System SHALL 记录修复前后的测试结果对比
4. THE System SHALL 确保所有相关测试都通过
5. THE System SHALL 更新测试文档

**验证步骤:**
1. 运行单个修复的测试
2. 运行相关模块的所有测试
3. 运行完整的测试套件
4. 检查测试覆盖率
5. 更新文档

---

### Requirement 7: 环境迁移后的测试验证

**User Story:** 作为开发者，我希望在环境迁移后能够快速验证所有测试，以确保系统正常运行。

#### Acceptance Criteria

1. WHEN 项目迁移到新环境 THEN THE System SHALL 提供一键测试脚本
2. WHEN 运行测试 THEN THE System SHALL 生成详细的测试报告
3. THE System SHALL 识别环境相关的测试失败
4. THE System SHALL 提供环境配置检查清单
5. THE System SHALL 记录已知的环境特定问题

**测试脚本要求:**
- 自动检测依赖安装
- 按模块分组运行测试
- 生成 HTML 测试报告
- 标记已知失败的测试
- 提供修复建议

---

## Summary

本需求记录文档记录了 37 个失败的测试用例，分为以下几类：

1. **DeviceMatchManager API 变更**: 31个测试失败
2. **YAML 错误处理**: 5个测试失败
3. **文件编码问题**: 1个测试失败

**当前状态:**
- ✅ 121个测试通过（88单元 + 33集成）
- ❌ 37个测试失败
- ⏭️ 1个测试跳过
- **总计**: 159个测试
- **当前通过率**: 76.1%

**修复后目标:**
- ✅ 158个测试通过
- ⏭️ 1个测试跳过（环境依赖）
- **目标通过率**: 99.4%

**预计工作量（参考）:**
- Requirement 1 (DeviceMatchManager): 4-6小时
- Requirement 2 (YAML 错误处理): 2-3小时
- Requirement 3 (文件编码): 0.5小时
- Requirement 4-7 (优化和工具): 可选，5-10小时
- **核心修复总计**: 7-10小时
- **完整修复总计**: 12-20小时

**重要说明:**
- 以上工作量仅为初步估算，实际修复时需要重新评估
- 本文档不包含具体的修复方案和实施计划
- 实际修复时需要创建详细的设计文档和任务清单

---

## Notes

- 所有测试失败都不影响核心功能的正常运行
- 代码迁移（config_template → core/config）已成功完成
- SystemManager 模块测试全部通过（21/21）
- 建议在完成 SystemManager 开发后统一修复这些测试
- 本文档仅记录需求，不包含具体的修复方案
- 实际修复时需要创建设计文档（design.md）和任务清单（tasks.md）
- 修复过程中应保持测试覆盖率不降低
- 所有修复都应该经过充分的测试和代码审查

**文档状态**: 需求记录完成，待后续创建设计和任务文档
