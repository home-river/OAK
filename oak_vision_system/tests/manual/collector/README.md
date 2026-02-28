# Collector 数据采集测试

## 概述

本目录包含用于测试 Collector 模块数据采集功能的手动测试脚本。

## 测试脚本

### test_collector_data_capture.py

用于在真实配置下测试双设备 Collector 的数据采集功能。

**功能特性：**
- 自动加载配置文件
- 启动 Collector 模块
- 使用 CollectorReceiver 接收数据
- 保存数据日志到 `test_logs/collector`
- 实时显示统计信息
- 支持 Ctrl+C 或指定时长后停止

**运行方式：**
```bash
python oak_vision_system/tests/manual/collector/test_collector_data_capture.py
```

**测试流程：**
1. 加载配置文件 `assets/test_config/config.json`
2. 创建并启动 OAKDataCollector
3. 创建并启动 CollectorReceiver
4. 运行 30 秒（默认）采集数据
5. 每 5 秒打印一次统计信息
6. 停止并输出最终统计

**输出文件：**
- 数据日志：`test_logs/collector/collector_data_*.json`
- 运行日志：`collector_test.log`

## 数据日志格式

### 视频帧日志

```json
{
  "type": "video_frame",
  "device_id": "19443010C122201300",
  "frame_id": 123,
  "timestamp": "2026-02-27T10:30:45.123456",
  "analysis_time": "2026-02-27T10:30:45.234567",
  "rgb_frame": {
    "shape": [480, 640, 3],
    "dtype": "uint8",
    "size_bytes": 921600,
    "mean_value": 128.5,
    "std_value": 45.2
  },
  "depth_frame": {
    "shape": [480, 640],
    "dtype": "uint16",
    "size_bytes": 614400,
    "min_depth": 500.0,
    "max_depth": 2000.0,
    "mean_depth": 1250.5
  }
}
```

### 检测数据日志

```json
{
  "type": "detection_data",
  "device_id": "19443010C122201300",
  "device_alias": "left_camera",
  "frame_id": 123,
  "timestamp": "2026-02-27T10:30:45.123456",
  "analysis_time": "2026-02-27T10:30:45.234567",
  "detection_count": 3,
  "label_counts": {
    "0": 2,
    "1": 1
  }
}
```

## 数据分析

采集完成后，可以使用以下方法分析数据：

### 1. 查看日志文件列表

```bash
ls test_logs/collector
```

### 2. 统计日志数量

```bash
# Windows PowerShell
(Get-ChildItem test_logs/collector -Filter "collector_data_*.json").Count

# Linux/Mac
ls test_logs/collector/collector_data_*.json | wc -l
```

### 3. 查看单个日志文件

```bash
# Windows PowerShell
Get-Content test_logs/collector/collector_data_20260227_103045_123456.json | ConvertFrom-Json

# Linux/Mac
cat test_logs/collector/collector_data_20260227_103045_123456.json | jq
```

### 4. 分析数据（Python 脚本）

```python
import json
from pathlib import Path
from collections import Counter

log_dir = Path("test_logs/collector")

# 统计数据类型
type_counter = Counter()
device_counter = Counter()

for log_file in log_dir.glob("collector_data_*.json"):
    with open(log_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        type_counter[data['type']] += 1
        device_counter[data['device_id']] += 1

print("数据类型统计:")
for data_type, count in type_counter.items():
    print(f"  {data_type}: {count}")

print("\n设备统计:")
for device_id, count in device_counter.items():
    print(f"  {device_id}: {count}")
```

## 常见问题

### 1. 设备未发现

检查：
- USB 连接是否稳定
- 设备是否被系统识别
- 配置文件中的设备 ID 是否正确

### 2. 数据丢弃过多

可能原因：
- 队列大小不足（增加 `frame_queue_size` 和 `detection_queue_size`）
- 处理速度过慢（检查磁盘 I/O）
- 系统资源不足

### 3. 日志文件过多

解决方法：
- 减少测试时长
- 增加日志保存间隔
- 定期清理旧日志

## 修改测试参数

编辑 `test_collector_data_capture.py` 中的参数：

```python
# 配置参数
config_path = "assets/test_config/config.json"  # 配置文件路径
test_duration = 30  # 测试时长（秒）
log_dir = "test_logs/collector"  # 日志目录

# CollectorReceiver 参数
frame_queue_size=100,  # 视频帧队列大小
detection_queue_size=100  # 检测数据队列大小
```

## 下一步

1. 运行测试采集数据
2. 分析日志文件
3. 验证数据完整性
4. 检查数据质量
5. 根据需要调整参数
