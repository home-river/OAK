# 校准工具核心模块

## ErrorRecorder - 误差数据记录模块

### 功能概述

ErrorRecorder 负责记录校准过程中的误差数据，包括：
- 从 DecisionLayer 获取实际目标位置
- 计算与基准位置的误差向量
- 保存误差数据到 JSON 文件
- 提供统计信息接口

### 使用示例

```python
from oak_vision_system.modules.data_processing.decision_layer import DecisionLayer
from tools.calibration_tools.core import ErrorRecorder

# 获取 DecisionLayer 实例（假设主系统已启动）
decision_layer = DecisionLayer.get_instance()

# 创建 ErrorRecorder 实例
error_recorder = ErrorRecorder(
    decision_layer=decision_layer,
    log_file_path="logs/calibration_errors.json"
)

# 记录误差（基准位置：X=1000mm, Y=500mm）
success = error_recorder.record_error(
    reference_x=1000.0,
    reference_y=500.0,
    target_type="durian"
)

if success:
    print(f"误差记录成功，已记录 {error_recorder.record_count} 条数据")
else:
    print("误差记录失败（未检测到目标）")

# 获取统计信息
stats = error_recorder.get_statistics()
print(f"统计信息: {stats}")
```

### 误差数据格式

保存的 JSON 文件格式如下：

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

### 统计信息格式

`get_statistics()` 返回的字典格式：

```python
{
    "record_count": 10,      # 记录总数
    "mean_error": 5.23,      # 平均误差（mm）
    "std_error": 1.45,       # 标准差（mm）
    "max_error": 8.12,       # 最大误差（mm）
    "min_error": 2.34        # 最小误差（mm）
}
```

### 注意事项

1. **目标检测**：如果 DecisionLayer 未检测到目标，`record_error()` 将返回 `False`
2. **文件追加**：误差数据以追加模式保存，不会覆盖历史记录
3. **线程安全**：ErrorRecorder 本身不是线程安全的，应在单线程中使用（通常在 GUI 线程中）
4. **基准位置**：Z 坐标固定为 0.0，只需提供 X 和 Y 坐标

### 错误处理

- 如果 DecisionLayer 返回 `None`（无目标），记录失败并返回 `False`
- 如果文件写入失败，会记录错误日志并返回 `False`
- 如果 JSON 文件损坏，会自动创建新文件
