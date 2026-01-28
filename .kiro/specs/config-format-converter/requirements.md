# Requirements Document

## Introduction

本文档定义了配置格式转换器（Config Format Converter）功能的需求。该功能旨在为 OAK Vision System 提供 JSON 和 YAML 配置文件格式之间的无缝转换能力，并集成到现有的配置管理系统中，实现自动格式识别和加载。

## Glossary

- **ConfigConverter**: 配置格式转换器，负责 JSON 和 YAML 格式之间的转换
- **DeviceConfigManager**: 设备配置管理器，负责加载、验证和管理系统配置
- **ConfigDTO**: 配置数据传输对象，系统配置的结构化表示
- **Format Detection**: 格式检测，根据文件扩展名自动识别配置文件格式
- **CLI Tool**: 命令行工具，提供用户友好的配置转换界面

## Requirements

### Requirement 1: 配置格式转换核心功能

**User Story:** 作为开发者，我希望能够在 JSON 和 YAML 配置格式之间进行转换，以便根据不同场景选择最合适的配置格式。

#### Acceptance Criteria

1. WHEN 提供有效的 JSON 配置文件路径和输出路径 THEN THE ConfigConverter SHALL 将配置转换为 YAML 格式并保存
2. WHEN 提供有效的 YAML 配置文件路径和输出路径 THEN THE ConfigConverter SHALL 将配置转换为 JSON 格式并保存
3. WHEN 转换过程中遇到无效的配置数据 THEN THE ConfigConverter SHALL 抛出描述性错误信息
4. WHEN 转换完成后 THEN THE ConfigConverter SHALL 确保转换后的配置与原配置在语义上等价
5. WHEN 输出文件已存在 THEN THE ConfigConverter SHALL 覆盖现有文件

### Requirement 2: 配置格式自动检测

**User Story:** 作为开发者，我希望系统能够自动识别配置文件格式，而不需要手动指定格式类型。

#### Acceptance Criteria

1. WHEN 提供文件扩展名为 .json 的文件路径 THEN THE ConfigConverter SHALL 识别为 JSON 格式
2. WHEN 提供文件扩展名为 .yaml 或 .yml 的文件路径 THEN THE ConfigConverter SHALL 识别为 YAML 格式
3. WHEN 提供不支持的文件扩展名 THEN THE ConfigConverter SHALL 抛出明确的错误信息
4. WHEN 文件路径不存在 THEN THE ConfigConverter SHALL 抛出文件不存在的错误

### Requirement 3: DeviceConfigManager 集成

**User Story:** 作为系统用户，我希望 DeviceConfigManager 能够自动识别并加载 JSON 或 YAML 格式的配置文件，无需手动转换。

#### Acceptance Criteria

1. WHEN 使用 JSON 配置文件路径初始化 DeviceConfigManager THEN THE DeviceConfigManager SHALL 成功加载配置
2. WHEN 使用 YAML 配置文件路径初始化 DeviceConfigManager THEN THE DeviceConfigManager SHALL 自动识别格式并成功加载配置
3. WHEN 加载 YAML 配置时 THEN THE DeviceConfigManager SHALL 内部将其转换为 ConfigDTO 对象
4. WHEN 加载配置失败 THEN THE DeviceConfigManager SHALL 提供清晰的错误信息，包括文件路径和失败原因
5. WHEN 加载成功后 THEN THE DeviceConfigManager SHALL 记录日志，包含文件路径和识别的格式类型

### Requirement 4: 配置导出功能

**User Story:** 作为开发者，我希望能够将当前加载的配置导出为 JSON 或 YAML 格式，以便备份或在不同环境中使用。

#### Acceptance Criteria

1. WHEN 调用 export_to_yaml 方法并提供输出路径 THEN THE DeviceConfigManager SHALL 将当前配置导出为 YAML 格式
2. WHEN 调用 export_to_json 方法并提供输出路径 THEN THE DeviceConfigManager SHALL 将当前配置导出为 JSON 格式
3. WHEN 配置未加载时调用导出方法 THEN THE DeviceConfigManager SHALL 抛出明确的错误信息
4. WHEN 导出成功后 THEN THE DeviceConfigManager SHALL 记录日志，包含输出路径和格式类型
5. WHEN 导出的文件已存在 THEN THE DeviceConfigManager SHALL 覆盖现有文件

### Requirement 5: 终端交互型转换工具

**User Story:** 作为配置管理员，我希望有一个终端交互型的命令行工具来转换配置文件格式，以便通过友好的交互界面快速处理配置文件而无需编写代码。

#### Acceptance Criteria

1. WHEN 运行 convert_config.py 并提供输入文件和目标格式 THEN THE CLI_Tool SHALL 执行格式转换
2. WHEN 未指定输出路径 THEN THE CLI_Tool SHALL 使用与输入文件相同的文件名，但扩展名改为目标格式
3. WHEN 转换成功 THEN THE CLI_Tool SHALL 在终端显示成功消息，包含输出文件路径
4. WHEN 转换失败 THEN THE CLI_Tool SHALL 在终端显示友好的错误信息并返回非零退出码
5. WHEN 使用 --validate 选项 THEN THE CLI_Tool SHALL 在转换后验证配置的有效性并在终端显示验证结果
6. WHEN 输出文件已存在且未使用 --force 选项 THEN THE CLI_Tool SHALL 在终端提示用户确认是否覆盖
7. WHEN 执行转换过程 THEN THE CLI_Tool SHALL 在终端显示友好的进度和状态信息

### Requirement 6: 配置生成工具集成

**User Story:** 作为配置管理员，我希望配置生成工具能够直接生成 YAML 格式的配置文件，以便利用 YAML 的注释功能。

#### Acceptance Criteria

1. WHEN 运行 generate_config.py 并指定 --format yaml THEN THE Generate_Tool SHALL 生成 YAML 格式的配置文件
2. WHEN 运行 generate_config.py 并指定 --format json THEN THE Generate_Tool SHALL 生成 JSON 格式的配置文件
3. WHEN 未指定 --format 选项 THEN THE Generate_Tool SHALL 默认生成 JSON 格式的配置文件
4. WHEN 生成 YAML 配置时 THEN THE Generate_Tool SHALL 生成干净的 YAML 结构，不包含自动生成的注释
5. WHEN 生成配置成功 THEN THE Generate_Tool SHALL 在 README.md 中说明如何为 YAML 配置添加注释

### Requirement 7: YAML 依赖管理

**User Story:** 作为系统维护者，我希望 YAML 支持是可选的，不强制所有用户安装 YAML 依赖。

#### Acceptance Criteria

1. WHEN 用户未安装 PyYAML 库且尝试加载 YAML 配置 THEN THE System SHALL 抛出清晰的错误信息，提示安装命令
2. WHEN 用户未安装 PyYAML 库且尝试导出 YAML 配置 THEN THE System SHALL 抛出清晰的错误信息，提示安装命令
3. WHEN 用户未安装 PyYAML 库但仅使用 JSON 配置 THEN THE System SHALL 正常工作，不受影响
4. WHEN 用户安装 oak_vision_system[yaml] THEN THE System SHALL 包含 PyYAML 依赖
5. WHEN 用户仅安装 oak_vision_system THEN THE System SHALL 不包含 PyYAML 依赖

### Requirement 8: 向后兼容性

**User Story:** 作为现有系统用户，我希望新功能不会破坏现有的 JSON 配置加载流程。

#### Acceptance Criteria

1. WHEN 使用现有的 JSON 配置文件 THEN THE DeviceConfigManager SHALL 保持原有的加载行为
2. WHEN 现有代码未指定配置格式 THEN THE System SHALL 默认支持 JSON 格式
3. WHEN 现有测试用例运行 THEN THE System SHALL 通过所有现有测试
4. WHEN 新功能添加后 THEN THE System SHALL 不改变现有 API 的行为和签名
5. WHEN 用户升级到新版本 THEN THE System SHALL 无需修改现有配置文件和代码

### Requirement 9: 配置验证

**User Story:** 作为开发者，我希望转换后的配置能够通过系统的配置验证，确保配置的正确性。

#### Acceptance Criteria

1. WHEN 转换配置文件后 THEN THE System SHALL 能够使用 DeviceConfigManager 加载转换后的配置
2. WHEN 使用 --validate 选项转换配置 THEN THE CLI_Tool SHALL 调用 DeviceConfigManager 验证配置
3. WHEN 验证失败 THEN THE System SHALL 提供详细的验证错误信息
4. WHEN 验证成功 THEN THE System SHALL 确认配置符合 ConfigDTO 的所有约束
5. WHEN 转换过程中数据丢失或损坏 THEN THE System SHALL 在验证阶段检测到错误

### Requirement 10: 终端交互和用户体验

**User Story:** 作为系统维护者，我希望 CLI 工具能够提供清晰的终端交互和友好的用户体验，以便快速定位和解决问题。

#### Acceptance Criteria

1. WHEN 转换过程中发生错误 THEN THE System SHALL 在终端显示详细的错误信息，包括文件路径和错误原因
2. WHEN 文件读取失败 THEN THE System SHALL 在终端提供文件路径和权限相关的错误信息
3. WHEN 格式解析失败 THEN THE System SHALL 在终端提供具体的解析错误位置和原因
4. WHEN 配置加载成功 THEN THE System SHALL 记录信息级别的日志，包含文件路径和格式类型
5. WHEN 使用 CLI 工具时 THEN THE System SHALL 在终端显示友好的进度和状态信息（如 "🔄 正在转换..."、"✅ 转换成功"）
6. WHEN 用户需要确认操作时 THEN THE CLI_Tool SHALL 在终端提供清晰的提示和选项
7. WHEN 转换完成时 THEN THE CLI_Tool SHALL 在终端显示操作摘要，包括输入文件、输出文件和格式类型

### Requirement 11: YAML 注释保持功能

**User Story:** 作为配置管理员，我希望在加载和保存 YAML 配置文件时能够保留用户手动添加的注释，以便维护配置文档和说明信息。

#### Acceptance Criteria

1. WHEN 加载包含注释的 YAML 配置文件 THEN THE System SHALL 保留所有用户注释
2. WHEN 修改配置并保存为 YAML 格式 THEN THE System SHALL 保持原有注释不变
3. WHEN 用户在 YAML 配置中添加中文注释 THEN THE System SHALL 正确处理和保存中文字符
4. WHEN 保存 YAML 配置时 THEN THE System SHALL 保持原有的缩进风格和格式
5. WHEN 使用 ruamel.yaml 库时 THEN THE System SHALL 优先使用 ruamel.yaml 而不是 PyYAML
6. WHEN ruamel.yaml 未安装但 PyYAML 已安装 THEN THE System SHALL 回退到 PyYAML（不保留注释）
7. WHEN 两个库都未安装 THEN THE System SHALL 提供清晰的错误信息，推荐安装 ruamel.yaml

### Requirement 12: 配置文件注释模板

**User Story:** 作为配置管理员，我希望生成的 YAML 配置文件包含有用的注释说明，以便理解各个配置项的含义和可选值。

#### Acceptance Criteria

1. WHEN 生成新的 YAML 配置文件 THEN THE System SHALL 为关键字段添加中文注释说明
2. WHEN 注释说明字段的可选值时 THEN THE System SHALL 列出所有有效选项（如 calibration_method: manual 或 auto）
3. WHEN 注释说明数值字段时 THEN THE System SHALL 包含单位信息（如 "单位：毫米"）
4. WHEN 注释说明时间字段时 THEN THE System SHALL 提供格式示例（如 "格式：YYYY-MM-DD HH:MM"）
5. WHEN 生成配置文件顶部 THEN THE System SHALL 添加配置文件说明和最后修改时间
6. WHEN 用户手动修改配置后保存 THEN THE System SHALL 保留用户添加的自定义注释
7. WHEN 程序自动更新配置时 THEN THE System SHALL 不覆盖用户的自定义注释
