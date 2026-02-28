# 配置方案

此配置方案由工具自动生成。

## 文件说明

- `config.json` - 系统完整配置文件
- `README.md` - 本说明文件


## 配置文件结构

配置文件包含以下部分：

### 1. 配置版本 (config_version)
- 当前版本: 2.0.0

### 2. OAK 模块配置 (oak_module)

#### 2.1 角色绑定 (role_bindings)
定义设备角色（如 LEFT_CAMERA, RIGHT_CAMERA）与实际设备的绑定关系。

运行设备发现工具获取 MXid：
```bash
python tools/discover_devices.py
```

#### 2.2 硬件配置 (hardware_config)
- `model_path`: 模型文件路径
- `confidence_threshold`: 检测置信度阈值 (0.0-1.0)
- `hardware_fps`: 硬件帧率
- `enable_depth_output`: 是否启用深度输出
- `rgb_resolution`: RGB 分辨率
- `preview_resolution`: 预览分辨率
- 更多参数请参考配置文件

#### 2.3 设备元数据 (device_metadata)
存储每个设备的详细信息（MXid、产品名、校准信息等）

### 3. 数据处理配置 (data_processing_config)

#### 3.1 坐标变换 (coordinate_transforms)
为每个设备角色配置坐标变换参数：
- `translation_x/y/z`: 平移参数（毫米）
- `roll/pitch/yaw`: 旋转参数（度）
- `calibration_date`: 校准日期
- `calibration_method`: 校准方法

#### 3.2 滤波配置 (filter_config)
- `filter_type`: 滤波器类型（MOVING_AVERAGE 等）
- `moving_average_config`: 滑动平均滤波器配置
  - `window_size`: 窗口大小

#### 3.3 其他参数
- `enable_data_logging`: 是否启用数据日志
- `processing_thread_priority`: 处理线程优先级
- `person_timeout_seconds`: 人员跟踪超时时间

### 4. CAN 通信配置 (can_config)
- `enable_can`: 是否启用 CAN 通信
- `can_interface`: CAN 接口类型
- `can_channel`: CAN 通道
- `can_bitrate`: CAN 波特率
- `frame_ids`: 帧 ID 配置

### 5. 显示配置 (display_config)
- `enable_display`: 是否启用显示
- `window_width/height`: 窗口尺寸
- `target_fps`: 目标帧率
- `show_detection_boxes`: 显示检测框
- `show_labels`: 显示标签
- `show_confidence`: 显示置信度
- 更多显示参数请参考配置文件

### 6. 系统配置 (system_config)

#### 6.1 日志配置
- `log_level`: 日志等级（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- `log_to_file`: 是否写入日志文件
- `log_file_path`: 日志文件路径
- `log_max_size_mb`: 单个日志文件最大大小
- `log_backup_count`: 日志文件备份数量

#### 6.2 性能配置
- `enable_profiling`: 启用性能分析
- `max_worker_threads`: 最大工作线程数

#### 6.3 系统行为
- `auto_reconnect`: 设备断开后自动重连
- `reconnect_interval`: 重连间隔（秒）
- `max_reconnect_attempts`: 最大重连次数
- `graceful_shutdown_timeout`: 优雅关闭超时（秒）

## 获取模型文件

### 方法 1: 使用 DepthAI Model Zoo

从 DepthAI Model Zoo 下载预训练模型：
- 仓库地址: https://github.com/luxonis/depthai-model-zoo
- 推荐模型: MobileNet-SSD（轻量级）

### 方法 2: 使用自己的模型

如果你有自己训练的模型，直接放在此目录或指定路径。

## 使用配置

### 方法 1: 通过 ConfigManager 加载

```python
from oak_vision_system.modules.config_manager import DeviceConfigManager

manager = DeviceConfigManager(config_path="test_config/config.json")
manager.load_config()
config = manager.get_runnable_config()
```

### 方法 2: 直接读取文件

```python
import json
from pathlib import Path

config_path = Path("test_config") / "config.json"
with open(config_path) as f:
    config = json.load(f)
```

## 修改配置

直接编辑 `config.json` 文件，根据你的需求调整参数。

**注意事项：**
1. 修改后建议通过 ConfigManager 验证配置有效性
2. 某些参数修改后需要重启系统
3. 坐标变换参数需要通过校准工具获取


## 下一步

1. **绑定设备**
   ```bash
   python tools/config_tools/discover_devices.py
   ```
   将获取的 MXid 填入 `oak_module.role_bindings` 中

2. **添加模型文件**
   将模型文件路径配置到 `oak_module.hardware_config.model_path`

3. **调整参数**
   根据实际场景调整各模块参数

4. **验证配置**
   ```python
   from oak_vision_system.modules.config_manager import DeviceConfigManager
   manager = DeviceConfigManager(config_path="config.json")
   manager.load_config()
   is_valid, errors = manager.validate_config()
   ```

## 格式转换

如需在 JSON 和 YAML 格式之间转换：

```bash
# JSON 转 YAML
python tools/config_tools/convert_config.py config.json --format yaml

# 转换后验证
python tools/config_tools/convert_config.py config.json --format yaml --validate
```

## 参考资料

- [项目文档](../../docs/)
- [配置架构说明](../../docs/config_architecture_refactoring.md)
- [DepthAI 文档](https://docs.luxonis.com/)
