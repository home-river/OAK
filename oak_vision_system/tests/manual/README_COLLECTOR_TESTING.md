# OAK数据采集器实机测试指南

## 概述

本目录包含OAK数据采集器（Collector）的实机测试脚本，用于在Windows端连接真实OAK设备进行功能验证。

## 测试脚本

### 1. 交互式实机测试 (`manual_collector_real_device.py`)

**用途：** 全功能的交互式测试工具，支持多种测试模式

**功能特性：**
- 自动设备发现和连接
- 多种测试模式选择
- 实时统计信息显示
- 交互式控制界面
- 性能测试和稳定性测试

**运行方式：**
```bash
# 交互式模式（推荐）
python oak_vision_system/tests/manual/manual_collector_real_device.py

# 自动模式（30秒测试）
python oak_vision_system/tests/manual/manual_collector_real_device.py --auto

# 自定义参数
python oak_vision_system/tests/manual/manual_collector_real_device.py --auto --duration 60 --depth --fps 30
```

**测试模式：**
1. 单设备测试（RGB + 检测）
2. 单设备测试（RGB + 深度 + 检测）
3. 多设备测试（需要2个以上设备）
4. 性能测试（长时间运行）

### 2. 快速验证测试 (`manual_collector_quick_verify.py`)

**用途：** 快速验证OAK设备连接和基本数据采集功能

**功能特性：**
- 10秒快速测试
- 基本功能验证
- 简洁的结果输出
- 适合开发过程中的快速验证

**运行方式：**
```bash
python oak_vision_system/tests/manual/manual_collector_quick_verify.py
```

**测试步骤：**
1. 设备发现测试
2. 配置创建测试
3. 10秒数据采集测试
4. 结果验证和总结

### 3. 多设备协同测试 (`manual_collector_multi_device.py`)

**用途：** 专门测试多个OAK设备的协同工作能力

**功能特性：**
- 双设备协同采集
- 设备间同步性验证
- 负载均衡测试
- 性能对比分析

**运行方式：**
```bash
# 交互式模式
python oak_vision_system/tests/manual/manual_collector_multi_device.py

# 指定参数
python oak_vision_system/tests/manual/manual_collector_multi_device.py --duration 60 --depth
```

**要求：** 至少需要2个OAK设备

## 测试环境要求

### 硬件要求
- **Windows系统**（测试专为Windows端设计）
- **OAK设备**：至少1个，多设备测试需要2个以上
- **USB 3.0接口**（推荐，USB 2.0也可以但性能较低）
- **足够的USB供电**（建议使用有源USB Hub）

### 软件要求
- Python 3.8+
- 必需依赖：`depthai`, `click`, `numpy`
- 项目依赖：完整的oak_vision_system包

### 模型文件
测试脚本会自动查找以下位置的模型文件：
1. `assets/test_config/model.blob`
2. `assets/example_config/mobilenet-ssd_openvino_2021.4_6shave.blob`
3. `models/mobilenet-ssd_openvino_2021.4_6shave.blob`

如果没有找到模型文件，请：
1. 下载适合的.blob模型文件
2. 放置到上述任一位置
3. 或修改测试脚本中的模型路径

## 运行测试

### 推荐测试流程

1. **首次测试 - 快速验证**
   ```bash
   python oak_vision_system/tests/manual/manual_collector_quick_verify.py
   ```
   验证基本连接和功能是否正常

2. **详细测试 - 交互式测试**
   ```bash
   python oak_vision_system/tests/manual/manual_collector_real_device.py
   ```
   进行全面的功能测试

3. **多设备测试**（如果有多个设备）
   ```bash
   python oak_vision_system/tests/manual/manual_collector_multi_device.py
   ```
   验证多设备协同工作

### 测试前准备

1. **连接设备**
   - 将OAK设备连接到Windows计算机
   - 确保USB连接稳定
   - 等待设备被系统识别

2. **验证设备**
   ```bash
   python tools/config_tools/discover_devices.py
   ```
   确认设备能被正确发现

3. **准备模型文件**
   - 确保有有效的.blob模型文件
   - 检查文件路径是否正确

## 测试结果解读

### 成功指标
- ✅ **设备发现**：能够发现并连接OAK设备
- ✅ **视频帧采集**：收到RGB视频帧数据
- ✅ **检测数据采集**：收到目标检测数据
- ✅ **帧率性能**：达到预期的帧率（通常>5fps）
- ✅ **数据完整性**：帧数据格式正确，无异常

### 常见问题

**问题1：未发现设备**
```
❌ 未发现任何OAK设备
```
**解决方案：**
- 检查USB连接
- 重新插拔设备
- 确认设备驱动已安装
- 尝试不同的USB端口

**问题2：模型文件未找到**
```
⚠️ 模型文件未找到，使用默认路径
```
**解决方案：**
- 下载合适的.blob模型文件
- 放置到指定路径
- 或修改测试脚本中的模型路径

**问题3：采集启动失败**
```
❌ 采集启动失败
```
**解决方案：**
- 检查设备是否被其他程序占用
- 重启设备
- 检查模型文件是否有效
- 降低帧率或队列大小

**问题4：帧率过低**
```
⚠️ 采集帧率: 2.3 fps (偏低)
```
**解决方案：**
- 使用USB 3.0接口
- 关闭其他占用资源的程序
- 降低分辨率或检测精度
- 检查系统性能

## 测试数据说明

### 统计信息
- **运行时间**：测试持续时间
- **总帧数**：收到的视频帧总数
- **总检测数**：收到的检测数据总数
- **平均帧率**：总帧数/运行时间
- **当前帧率**：基于最近帧间隔计算的实时帧率

### 设备统计（多设备测试）
- **设备帧数**：各设备的帧数统计
- **设备检测数**：各设备的检测数统计
- **同步性分析**：设备间数据同步情况
- **负载均衡**：设备间负载分布情况

## 性能基准

### 单设备性能
- **目标帧率**：15-30 fps
- **最低可接受帧率**：5 fps
- **检测延迟**：<100ms
- **内存使用**：<500MB

### 多设备性能
- **总体帧率**：单设备帧率 × 设备数量 × 0.8
- **设备同步性**：帧数差异<20%
- **负载均衡**：各设备帧率差异<30%

## 故障排除

### 设备连接问题
1. 检查USB线缆质量
2. 尝试不同的USB端口
3. 使用有源USB Hub
4. 检查设备驱动

### 性能问题
1. 使用USB 3.0接口
2. 关闭不必要的程序
3. 调整测试参数（帧率、分辨率）
4. 检查系统资源使用情况

### 软件问题
1. 更新depthai库到最新版本
2. 检查Python环境和依赖
3. 重启Python进程
4. 检查项目代码完整性

## 联系方式

如有问题或需要帮助，请联系开发团队。

---

**更新日期：** 2024-01-28
**版本：** 1.0.0