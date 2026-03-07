# 校准工具使用说明

## 概述

校准工具提供了一个图形界面，用于在系统运行时实时调整坐标变换参数和记录误差数据。

## 功能特性

- **实时参数调整**：在系统运行时动态修改坐标变换参数（平移、旋转）
- **误差数据记录**：设置基准位置并记录实际检测位置与基准位置的误差
- **独立线程运行**：GUI 在独立线程中运行，不阻塞主系统
- **内存中生效**：参数调整仅在内存中生效，不会修改配置文件
- **线程安全**：使用线程安全机制保护共享数据

## 系统要求

- **单设备运行模式**：校准工具仅支持单个 OAK 设备运行
- **Python 依赖**：需要 tkinter 库（GUI 支持）
- **主系统运行**：需要完整的主系统（Collector、DataProcessor、Display、CAN）

## 启动方式

### 方式 1：使用启动脚本（推荐）

```bash
# 从项目根目录运行
python tools/calibration_tools/calibration_main.py
```

这个脚本会：
1. 启动完整的主系统
2. 验证单设备运行模式
3. 创建校准工具组件
4. 启动校准 GUI

### 方式 2：在代码中集成

```python
from tools.calibration_tools.core.transform_param_manager import TransformParamManager
from tools.calibration_tools.core.error_recorder import ErrorRecorder
from tools.calibration_tools.gui.calibration_gui import CalibrationGUI

# 假设已经创建了 config_manager 和 data_processor
param_manager = TransformParamManager(config_manager, data_processor)
error_recorder = ErrorRecorder(decision_layer)

# 在独立线程中启动 GUI
gui_thread = CalibrationGUI.start_in_thread(param_manager, error_recorder)
```

## 配置要求

### 单设备模式配置

确保配置文件中只有一个设备处于激活状态：

```json
{
  "oak_module": {
    "role_bindings": {
      "left_camera": {
        "active_mxid": "14442C10D13F7FD000",
        "enabled": true
      }
    }
  }
}
```

### 坐标变换配置

确保配置文件中包含坐标变换参数：

```json
{
  "coordinate_transforms": {
    "left_camera": {
      "role": "left_camera",
      "translation_x": -50.0,
      "translation_y": 0.0,
      "translation_z": 0.0,
      "roll": 0.0,
      "pitch": 0.0,
      "yaw": 0.0
    }
  }
}
```

## GUI 使用说明

### 参数调整

1. **查看当前参数**：GUI 启动时会自动加载配置文件中的初始参数
2. **微调参数**：
   - 使用 `[-]` 和 `[+]` 按钮进行微调
   - 平移参数（Tx、Ty、Tz）步长：1.0 mm
   - 旋转参数（Pitch、Yaw）步长：0.1 度
3. **直接输入**：在输入框中直接输入参数值
4. **应用参数**：点击"设置参数"按钮应用新参数
5. **重置参数**：点击"重置为默认"按钮恢复到启动时的初始参数

### 误差记录

1. **设置基准位置**：
   - 在"基准位置 X"和"基准位置 Y"输入框中输入基准坐标（单位：mm）
   - 例如：X=1000.0, Y=500.0
2. **记录误差**：
   - 确保系统已检测到目标
   - 点击"记录误差"按钮
   - 系统会自动计算误差向量并保存到 JSON 文件
3. **查看记录数**：GUI 会显示已记录的数据条数

### 状态反馈

- **绿色文本**：操作成功
- **红色文本**：操作失败或错误
- **蓝色文本**：就绪状态

## 误差数据格式

误差数据保存在 `logs/calibration_errors.json` 文件中：

```json
[
  {
    "timestamp": "2024-01-15T10:30:45.123456",
    "target_type": "durian",
    "reference_position": {
      "x": 1000.0,
      "y": 500.0,
      "z": 0.0
    },
    "actual_position": {
      "x": 1005.2,
      "y": 498.3,
      "z": 2.1
    },
    "error_vector": {
      "dx": 5.2,
      "dy": -1.7,
      "dz": 2.1
    },
    "error_magnitude": 5.67
  }
]
```

## 常见问题

### 1. GUI 启动失败：多设备检测

**错误信息**：
```
校准工具仅支持单设备运行模式，当前检测到 2 个设备
```

**解决方案**：
- 修改配置文件，确保只有一个设备的 `enabled` 为 `true`
- 或者禁用其他设备的角色绑定

### 2. DecisionLayer 未初始化

**错误信息**：
```
DecisionLayer 尚未初始化
```

**解决方案**：
- 确保 DataProcessor 已经成功创建
- DecisionLayer 在 DataProcessor 初始化时自动创建

### 3. tkinter 未安装

**错误信息**：
```
No module named 'tkinter'
```

**解决方案**：
```bash
# Linux
sudo apt-get install python3-tk

# macOS
brew install python-tk

# Windows
# tkinter 通常随 Python 一起安装
```

### 4. 误差记录失败：未检测到目标

**错误信息**：
```
误差记录失败（未检测到目标）
```

**解决方案**：
- 确保相机视野中有目标物体
- 检查检测模型是否正常工作
- 等待系统检测到目标后再记录

## 日志文件

- **系统日志**：`log/main/calibration.log`
- **误差数据**：`logs/calibration_errors.json`

## 架构说明

### 组件关系

```
CalibrationGUI (独立线程)
    ├── TransformParamManager
    │   ├── ConfigManager (读取初始配置)
    │   └── DataProcessor (更新变换矩阵)
    └── ErrorRecorder
        └── DecisionLayer (获取目标坐标)
```

### 线程安全机制

- **CoordinateTransformer**：使用 RLock 保护变换矩阵访问
- **DecisionLayer**：使用 RLock 保护目标坐标访问
- **原子替换**：变换矩阵字典整体替换，确保一致性

## 开发说明

### 目录结构

```
tools/calibration_tools/
├── calibration_main.py          # 启动脚本
├── core/                         # 核心模块
│   ├── transform_param_manager.py  # 参数管理器
│   └── error_recorder.py           # 误差记录器
├── gui/                          # GUI 模块
│   └── calibration_gui.py          # GUI 界面
└── test/                         # 测试模块
    ├── test_transform_param_manager.py
    ├── test_error_recorder.py
    └── test_gui_integration.py
```

### 扩展点

1. **添加新的参数类型**：在 TransformParamManager 中添加新的参数处理逻辑
2. **自定义误差计算**：在 ErrorRecorder 中修改误差计算方法
3. **增强 GUI 功能**：在 CalibrationGUI 中添加新的 UI 组件

## 注意事项

1. **参数不持久化**：所有参数调整仅在内存中生效，系统重启后恢复到配置文件中的值
2. **单设备限制**：当前版本仅支持单设备运行模式
3. **GUI 异常隔离**：GUI 线程异常不会影响主系统运行
4. **性能影响**：校准工具对主系统性能影响 < 5%

## 许可证

与主项目相同
