# Implementation Plan: Config Format Converter (终端交互型)

## Overview

本实现计划将配置格式转换器功能分为 4 个主要阶段：
1. 开发核心转换器（ConfigConverter）
2. 集成到配置管理器实现自动识别
3. 更新和修改相关测试
4. 开发终端交互型命令行工具并进行测试

**特色**：CLI 工具采用终端交互型设计，提供友好的用户体验，包括彩色输出、进度显示、交互式确认等功能。

## Tasks

- [x] 1. 开发核心转换器（ConfigConverter）
  - [x] 1.1 创建 ConfigConverter 类和基础结构
    - 创建 `oak_vision_system/modules/config_manager/config_converter.py`
    - 实现类框架和静态方法签名
    - 添加必要的导入和类型注解
    - _Requirements: 1.1, 1.2_
  
  - [x] 1.2 实现格式检测功能
    - 实现 `detect_format()` 方法
    - 支持 .json, .yaml, .yml 扩展名识别
    - 处理不支持格式的错误
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [x] 1.3 编写格式检测的属性测试
    - **Property 2: Format Detection is Accurate**
    - **Validates: Requirements 2.1, 2.2**
  
  - [x] 1.4 实现 JSON 到 YAML 转换
    - 实现 `json_to_yaml()` 方法
    - 处理文件读写和格式转换
    - 实现 PyYAML 依赖检查和友好错误提示
    - _Requirements: 1.1, 7.1_
  
  - [x] 1.5 实现 YAML 到 JSON 转换
    - 实现 `yaml_to_json()` 方法
    - 处理文件读写和格式转换
    - 实现 PyYAML 依赖检查和友好错误提示
    - _Requirements: 1.2, 7.2_
  
  - [x] 1.6 编写转换功能的属性测试
    - **Property 1: Round-trip Conversion Preserves Semantics**
    - **Validates: Requirements 1.1, 1.2, 1.4**
  
  - [x] 1.7 实现辅助方法
    - 实现 `load_yaml_as_dict()` 方法
    - 实现 `save_as_yaml()` 方法
    - 配置 YAML 输出格式（UTF-8、无流式风格、不排序键）
    - _Requirements: 3.2, 4.1_
  
  - [x] 1.8 编写错误处理的单元测试
    - 测试文件不存在错误
    - 测试 PyYAML 未安装错误
    - 测试无效格式错误
    - _Requirements: 1.3, 2.3, 7.1, 7.2_
  
  - [x] 1.9 更新 config_manager 模块导出
    - 在 `__init__.py` 中导出 ConfigConverter
    - 更新模块文档字符串
    - _Requirements: 1.1_

- [x] 2. 集成到配置管理器实现自动识别
  - [x] 2.1 增强 DeviceConfigManager.load_config()
    - 添加格式自动检测逻辑
    - 实现 YAML 配置加载分支
    - 保持 JSON 加载的现有逻辑不变
    - 添加格式类型日志记录
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 8.1_
  
  - [x] 2.2 编写 YAML 加载的属性测试
    - **Property 4: YAML Loading Integration**
    - **Validates: Requirements 3.2, 3.3**
  
  - [x] 2.3 实现 export_to_yaml() 方法
    - 添加 `export_to_yaml()` 方法到 DeviceConfigManager
    - 验证配置已加载
    - 调用 ConfigConverter 执行导出
    - 添加日志记录
    - _Requirements: 4.1, 4.4_
  
  - [x] 2.4 实现 export_to_json() 方法
    - 添加 `export_to_json()` 方法到 DeviceConfigManager
    - 验证配置已加载
    - 使用现有 JSON 序列化逻辑
    - 添加日志记录
    - _Requirements: 4.2, 4.4_
  
  - [x] 2.5 编写配置导出的属性测试
    - **Property 5: Configuration Export Preserves Content**
    - **Validates: Requirements 4.1, 4.2**
  
  - [x] 2.6 编写日志记录的属性测试
    - **Property 6: Logging Records Key Operations**
    - **Validates: Requirements 3.5, 4.4**

- [x] 3. Checkpoint - 核心功能验证
  - 确保所有核心转换和集成测试通过
  - 验证向后兼容性
  - 如有问题，询问用户

- [x] 4. 更新和修改相关测试
  - [x] 4.1 创建 ConfigConverter 单元测试文件
    - 创建 `test_config_converter.py`
    - 实现基本转换测试
    - 实现格式检测测试
    - 实现错误处理测试
    - _Requirements: 1.1, 1.2, 2.1, 2.2_
  
  - [x] 4.2 创建 ConfigConverter 属性测试文件
    - 创建 `test_config_converter_properties.py`
    - 配置 Hypothesis 策略
    - 实现配置字典生成器
    - 实现所有属性测试（Property 1-3, 5）
    - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 4.1, 4.2_
  
  - [x] 4.3 创建 DeviceConfigManager 格式支持测试
    - 创建 `test_config_manager_format_support.py`
    - 测试 YAML 配置加载
    - 测试配置导出功能
    - 测试错误处理
    - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3_
  
  - [x] 4.4 创建集成测试文件
    - 创建 `test_config_manager_yaml_support.py`
    - 测试端到端 YAML 支持
    - 测试向后兼容性
    - 测试配置验证集成
    - _Requirements: 8.1, 8.2, 9.1, 9.4_
  
  - [x] 4.5 编写向后兼容性测试
    - **Property 8: Backward Compatibility Maintained**
    - **Validates: Requirements 8.1, 8.2**
  
  - [x] 4.6 编写可选依赖处理测试
    - **Property 9: Optional Dependency Handling**
    - **Validates: Requirements 7.1, 7.2**
  
  - [x] 4.7 编写验证检测损坏测试
    - **Property 10: Validation Detects Corruption**
    - **Validates: Requirements 9.3, 9.4**
  
  - [x] 4.8 更新现有测试以确保兼容性
    - 运行所有现有 config_manager 测试
    - 修复任何因新功能导致的测试失败
    - 确保测试覆盖率不降低
    - _Requirements: 8.3_

- [x] 5. Checkpoint - 测试验证
  - 确保所有测试通过（单元测试 + 属性测试 + 集成测试）
  - 验证测试覆盖率 > 90%
  - 如有问题，询问用户

- [x] 6. 开发终端交互型命令行工具
  - [x] 6.1 创建 convert_config.py CLI 工具框架
    - 创建 `tools/config_tools/convert_config.py`
    - 实现命令行参数解析（click）
    - 设计终端输出格式（彩色、图标）
    - _Requirements: 5.1_
  
  - [x] 6.2 实现 CLI 工具的核心转换功能
    - 实现输入文件验证
    - 实现输出路径自动生成
    - 调用 ConfigConverter 执行转换
    - 添加转换进度显示（🔄 正在转换...）
    - _Requirements: 5.1, 5.2, 5.7_
  
  - [x] 6.3 实现终端友好的错误处理
    - 捕获并格式化各类错误（❌ 错误类型）
    - 实现非零退出码
    - 添加友好的错误提示（💡 提示）
    - 显示详细的错误信息
    - _Requirements: 5.4, 10.1, 10.2, 10.3_
  
  - [x] 6.4 实现交互式确认功能
    - 检测输出文件是否存在
    - 实现终端交互式确认提示（⚠️  文件已存在）
    - 处理用户输入（y/N）
    - 实现 --force 选项跳过确认
    - _Requirements: 5.6, 10.6_
  
  - [x] 6.5 实现 --validate 选项
    - 添加 --validate 命令行选项
    - 转换后调用 DeviceConfigManager 验证
    - 在终端显示验证进度（🔍 正在验证...）
    - 显示验证结果（✅ 验证通过 / ❌ 验证失败）
    - _Requirements: 5.5, 9.2, 9.3_
  
  - [x] 6.6 实现终端输出美化
    - 添加成功消息格式化（✅ 转换成功）
    - 添加操作摘要显示
    - 添加友好提示信息（💡 提示）
    - 实现彩色输出（成功/错误/警告）
    - _Requirements: 5.3, 10.5, 10.7_
  
  - [x] 6.7 编写 CLI 工具的集成测试
    - 使用 Click CliRunner 测试
    - 测试所有命令行选项
    - 测试终端交互式确认
    - 测试错误场景和输出格式
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  
  - [x] 6.8 增强 generate_config.py 工具
    - 添加 --format 选项（json/yaml）
    - 实现格式选择逻辑
    - 更新帮助文档
    - 保持默认为 JSON（向后兼容）
    - 添加终端友好的输出格式
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 6.9 更新 generate_config.py 的 README 生成
    - 在生成的 README 中添加 YAML 注释说明
    - 提供注释添加的示例
    - _Requirements: 6.5_
  
  - [x] 6.10 编写 generate_config.py 的测试
    - 测试 --format json 选项
    - 测试 --format yaml 选项
    - 测试默认行为
    - 测试终端输出格式
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 7. 更新项目依赖配置
  - [x] 7.1 更新 pyproject.toml
    - 添加 PyYAML 到 optional-dependencies
    - 创建 [yaml] extra
    - 更新项目元数据
    - _Requirements: 7.4, 7.5_
  
  - [x] 7.2 更新 requirements.txt（如果存在）
    - 添加 PyYAML 注释说明（可选依赖）
    - _Requirements: 7.4_
  
  - [x] 7.3 更新项目文档
    - 更新 README.md 说明 YAML 支持
    - 添加安装说明（包含 [yaml] extra）
    - 添加使用示例
    - _Requirements: 6.5, 7.1, 7.2_

- [x] 8. Final Checkpoint - 完整功能验证
  - 运行完整测试套件
  - 手动测试 CLI 工具的终端交互功能
  - 验证终端输出格式和用户体验
  - 测试交互式确认流程
  - 验证文档完整性
  - 确认所有需求已实现
  - 如有问题，询问用户

## Notes

- 所有测试任务都已设为必需，确保全面的测试覆盖
- 每个任务都引用了相关的需求编号，便于追溯
- Checkpoint 任务用于阶段性验证，确保增量开发的质量
- 属性测试配置为最少 100 次迭代
- 所有测试任务都标注了对应的设计文档属性编号
- CLI 工具采用终端交互型设计，提供友好的用户体验：
  - 彩色输出（✅ 成功、❌ 错误、⚠️ 警告、🔄 进度）
  - 交互式确认提示
  - 友好的错误信息和提示
  - 操作摘要显示


- [x] 9. 实现 YAML 注释保持功能（ruamel.yaml）
  - [x] 9.1 更新依赖配置
    - 在 pyproject.toml 中添加 ruamel.yaml 到 optional-dependencies
    - 保留 PyYAML 作为回退方案
    - 更新安装文档说明
    - _Requirements: 11.5, 11.6, 11.7_
  
  - [x] 9.2 增强 ConfigConverter 支持 ruamel.yaml
    - 实现库检测逻辑（优先 ruamel.yaml，回退 PyYAML）
    - 添加 `_get_yaml_handler()` 方法
    - 更新 `load_yaml_as_dict()` 使用 ruamel.yaml
    - 更新 `save_as_yaml()` 使用 ruamel.yaml
    - 添加日志记录使用的库类型
    - _Requirements: 11.1, 11.2, 11.5, 11.6_
  
  - [x] 9.3 实现中文注释支持
    - 配置 ruamel.yaml 的 UTF-8 编码
    - 设置 allow_unicode=True
    - 测试中文注释的读写
    - _Requirements: 11.3_
  
  - [x] 9.4 实现格式保持功能
    - 配置 preserve_quotes=True
    - 配置 default_flow_style=False
    - 设置合适的 width 避免自动换行
    - _Requirements: 11.4_
  
  - [x] 9.5 编写注释保持的属性测试
    - **Property 11: Comment Preservation**
    - 测试用户注释在加载/保存循环中保持不变
    - 测试中文注释支持
    - 测试格式保持（缩进、引号）
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
  
  - [x] 9.6 编写库回退测试
    - 测试 ruamel.yaml 可用时的行为
    - 测试回退到 PyYAML 的行为
    - 测试两个库都不可用时的错误提示
    - _Requirements: 11.5, 11.6, 11.7_
  
  - [x] 9.7 更新 DeviceConfigManager 日志提示
    - 加载 YAML 时显示使用的库类型
    - 提示用户安装 ruamel.yaml 的好处
    - 保存时提示注释保持状态
    - _Requirements: 11.5, 11.6_

- [x] 10. ~~实现配置文件注释模板功能~~ (跳过 - 将通过 AI IDE 实现)
  - [x] ~~10.1 设计注释模板结构~~ (跳过)
  - [x] ~~10.2 实现注释添加工具函数~~ (跳过)
  - [x] ~~10.3 为关键字段添加中文注释~~ (跳过)
  - [x] ~~10.4 集成到配置生成工具~~ (跳过)
  - [x] ~~10.5 实现注释保护机制~~ (跳过)
  - [x] ~~10.6 编写注释模板测试~~ (跳过)
  - [x] ~~10.7 编写用户注释保护测试~~ (跳过)

- [x] 11. ~~更新文档和示例~~ (跳过 - 将通过 AI IDE 实现)
  - [x] ~~11.1 更新 README.md~~ (跳过)
  - [x] ~~11.2 创建 YAML 配置示例文件~~ (跳过)
  - [x] ~~11.3 更新 CLI 工具帮助文档~~ (跳过)
  - [x] ~~11.4 创建迁移指南~~ (跳过)

- [x] 12. ~~Final Checkpoint - YAML 注释功能验证~~ (跳过)

## Notes (Updated)

- 新增任务 9 实现 YAML 注释保持功能 ✅ **已完成**
- ruamel.yaml 作为推荐依赖，PyYAML 作为回退方案 ✅ **已实现**
- 完整支持中文注释和格式保持 ✅ **已实现**
- 任务 10-12 已跳过，配置文件注释模板功能将通过 AI IDE 实现
- 所有核心 YAML 注释保持功能都有对应的测试覆盖 ✅ **已完成**

**YAML 注释保持功能总结：**
- ✅ 支持用户手动添加的注释在加载/保存循环中保持不变
- ✅ 完整支持中文注释和 UTF-8 编码
- ✅ 保持原有的缩进风格和格式
- ✅ 优先使用 ruamel.yaml，自动回退到 PyYAML
- ✅ 提供清晰的日志提示和库选择建议
- ✅ 所有功能都通过了单元测试和属性测试验证
