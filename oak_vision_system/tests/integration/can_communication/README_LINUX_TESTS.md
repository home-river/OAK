# CAN通信模块Linux环境测试指南

本目录包含CAN通信模块在Linux环境下的完整集成测试。这些测试专为Linux系统（特别是香橙派）设计，需要真实的CAN硬件环境。

## 测试文件概览

### 1. `test_can_interface_config_linux.py`
**接口配置工具测试**
- **功能**: 测试CAN接口配置命令构造、sudo权限处理、系统命令执行
- **环境**: Linux + mock subprocess
- **特点**: 使用mock避免实际执行系统命令，可在任何Linux系统运行

### 2. `test_can_integration_linux.py`
**CAN通信集成测试**
- **功能**: 测试CAN通信模块的集成功能（坐标请求响应、人员警报、接口配置）
- **环境**: Linux + socketCAN（真实或虚拟）
- **特点**: 使用mock决策层和事件总线，测试CAN通信逻辑

### 3. `test_can_end_to_end_linux.py`
**端到端测试**
- **功能**: 使用can_controller.py进程进行真实的进程间CAN通信测试
- **环境**: Linux + socketCAN + can_controller.py脚本
- **特点**: 利用socketCAN loopback机制，两个进程真实通信

### 4. `test_can_hardware_linux.py`
**硬件测试**
- **功能**: 在真实硬件环境下进行最高级别的集成测试
- **环境**: Linux（香橙派）+ 真实CAN硬件 + 外部控制器
- **特点**: 验证真实硬件环境下的性能和稳定性

## 环境准备

### 基础要求
```bash
# 1. 安装Python依赖
pip install python-can pytest numpy

# 2. 检查Linux平台
uname -a  # 确认是Linux系统

# 3. 检查CAN内核模块
lsmod | grep can
```

### CAN接口配置

#### 选项1: 虚拟CAN接口（用于开发测试）
```bash
# 加载虚拟CAN模块
sudo modprobe vcan

# 创建虚拟CAN接口
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0

# 验证接口
ip link show vcan0
```

#### 选项2: 真实CAN接口（用于硬件测试）
```bash
# 配置真实CAN接口
sudo ip link set can0 type can bitrate 250000
sudo ip link set can0 up

# 验证接口状态
ip link show can0
# 应该显示: can0: <NOARP,UP,LOWER_UP> ...
```

### 权限配置
```bash
# 添加用户到dialout组（可选）
sudo usermod -a -G dialout $USER

# 配置sudo免密（可选，用于自动化测试）
echo "$USER ALL=(ALL) NOPASSWD: /sbin/ip, /sbin/modprobe" | sudo tee /etc/sudoers.d/can-testing
```

## 测试运行

### 1. 接口配置测试（最基础）
```bash
# 运行接口配置测试
pytest oak_vision_system/tests/integration/can_communication/test_can_interface_config_linux.py -v

# 预期结果: 所有测试通过，验证命令构造和权限处理逻辑
```

### 2. 集成测试（需要CAN接口）
```bash
# 使用虚拟CAN接口
pytest oak_vision_system/tests/integration/can_communication/test_can_integration_linux.py -v

# 预期结果: 验证CAN通信逻辑，包括坐标响应和警报功能
```

### 3. 端到端测试（需要can_controller.py）
```bash
# 确保can_controller.py脚本存在
ls -la plan/modules/CAN_module/pre_inpimentation/can_controller.py

# 运行端到端测试
pytest oak_vision_system/tests/integration/can_communication/test_can_end_to_end_linux.py -v -s

# 预期结果: 两个进程通过socketCAN进行真实通信
```

### 4. 硬件测试（需要真实硬件）
```bash
# 确保真实CAN接口可用
ip link show can0

# 运行硬件测试
pytest oak_vision_system/tests/integration/can_communication/test_can_hardware_linux.py -v -s

# 预期结果: 验证真实硬件环境下的性能和稳定性
```

### 运行所有Linux测试
```bash
# 运行所有CAN Linux测试
pytest oak_vision_system/tests/integration/can_communication/ -v -k "linux"

# 运行特定测试类
pytest oak_vision_system/tests/integration/can_communication/ -v -k "TestCoordinateRequestResponse"

# 运行并显示详细输出
pytest oak_vision_system/tests/integration/can_communication/ -v -s --tb=short
```

## 测试分级

### Level 1: 基础测试（任何Linux系统）
- `test_can_interface_config_linux.py`
- 使用mock，不需要真实CAN硬件
- 验证命令构造和权限处理逻辑

### Level 2: 集成测试（需要socketCAN）
- `test_can_integration_linux.py`
- 需要虚拟或真实CAN接口
- 验证CAN通信逻辑

### Level 3: 端到端测试（需要socketCAN + 脚本）
- `test_can_end_to_end_linux.py`
- 需要can_controller.py脚本
- 验证进程间真实通信

### Level 4: 硬件测试（需要真实硬件）
- `test_can_hardware_linux.py`
- 需要真实CAN硬件接口
- 验证硬件环境性能

## 故障排除

### 常见问题

#### 1. CAN接口不存在
```bash
# 错误: Cannot find device can0
# 解决: 创建虚拟CAN接口
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```

#### 2. 权限不足
```bash
# 错误: Operation not permitted
# 解决: 使用sudo或配置权限
sudo pytest ...
# 或配置sudo免密
```

#### 3. python-can模块问题
```bash
# 错误: No module named 'can'
# 解决: 安装python-can
pip install python-can
```

#### 4. can_controller.py脚本不存在
```bash
# 错误: FileNotFoundError: can_controller.py
# 解决: 确保脚本路径正确
ls -la plan/modules/CAN_module/pre_inpimentation/can_controller.py
```

### 调试技巧

#### 1. 查看CAN接口状态
```bash
# 查看所有网络接口
ip link show

# 查看CAN接口详情
ip -details link show can0

# 查看CAN统计信息
cat /proc/net/can/stats
```

#### 2. 监控CAN消息
```bash
# 安装can-utils
sudo apt-get install can-utils

# 监控CAN消息
candump can0

# 发送测试消息
cansend can0 123#DEADBEEF
```

#### 3. 查看测试日志
```bash
# 运行测试并保存日志
pytest oak_vision_system/tests/integration/can_communication/ -v -s --tb=long > test_results.log 2>&1

# 查看详细日志
tail -f test_results.log
```

## 性能基准

### 预期性能指标

#### 坐标请求响应
- **响应时间**: < 10ms（集成测试），< 50ms（硬件测试）
- **成功率**: ≥ 95%
- **并发处理**: 支持50Hz请求频率

#### 人员警报
- **警报间隔**: 100ms ± 20ms（集成测试），± 50ms（硬件测试）
- **启动延迟**: < 100ms
- **停止延迟**: < 200ms

#### 系统稳定性
- **连续运行**: 支持长时间运行（> 1小时）
- **内存泄漏**: 无明显内存增长
- **错误恢复**: 自动恢复CAN总线错误

## 测试报告

### 生成测试报告
```bash
# 生成HTML报告
pip install pytest-html
pytest oak_vision_system/tests/integration/can_communication/ --html=can_test_report.html --self-contained-html

# 生成覆盖率报告
pip install pytest-cov
pytest oak_vision_system/tests/integration/can_communication/ --cov=oak_vision_system.modules.can_communication --cov-report=html
```

### 测试结果解读
- **PASSED**: 测试通过，功能正常
- **FAILED**: 测试失败，需要检查代码或环境
- **SKIPPED**: 测试跳过，通常是环境不满足要求
- **ERROR**: 测试错误，通常是配置或依赖问题

## 注意事项

1. **环境隔离**: 建议在专用的测试环境运行，避免影响生产系统
2. **权限管理**: 某些测试需要sudo权限，注意安全性
3. **硬件保护**: 硬件测试可能对CAN总线产生负载，注意保护设备
4. **并发限制**: 避免同时运行多个CAN测试，可能导致资源冲突
5. **日志监控**: 关注测试日志，及时发现潜在问题

## 联系支持

如果遇到测试问题，请提供以下信息：
- Linux发行版和版本
- CAN硬件型号
- 测试失败的详细日志
- 系统环境信息（`uname -a`, `lsmod | grep can`）