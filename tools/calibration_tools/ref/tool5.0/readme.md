# Single OAK Detector V2.0 - 修改说明

## 版本更新内容

### 主要修改 (2025-08-23)

#### 1. 神经网络输入优化
- **分辨率调整**: 将神经网络输入从1:1长宽比修改为16:9长宽比
- **新分辨率**: 512×288像素，保证不裁剪RGB原始视野
- **模型适配**: 使用适配512×288输入的新模型 `best_openvino_2022.1_6shave.blob`

#### 2. RGB显示流优化
- **显示质量**: 修改RGB显示流为原生video流，保证清晰度
- **视野完整**: 保持完整的RGB视野，无裁剪损失

#### 3. CV显示功能增强
- **显示模式**: 新增CV显示RGB功能，支持两种显示模式
  - **全屏模式**: 使用原始分辨率全屏显示
  - **中屏模式**: 800×600窗口显示
- **按键控制**:
  - `f` - 切换到全屏模式
  - `m` - 切换到中屏模式
  - `ESC` - 从全屏模式退出到中屏模式
  - `q` - 退出程序

## 技术细节

### 相机配置
```python
camRgb.setPreviewSize(512, 288)  # 神经网络输入尺寸
camRgb.setVideoSize(1920, 1080)  # RGB显示流尺寸
```

### 显示模式实现
- **全屏模式**: `cv2.WINDOW_FULLSCREEN` 属性，显示原始分辨率
- **中屏模式**: `cv2.WINDOW_AUTOSIZE` 属性，调整为800×600

### 文件结构
```
test4.0/
├── single_oak_detector_v2.py          # 主检测器文件
├── single_oak_with_tuning_v2.py       # GUI参数调整模块
├── best_openvino_2022.1_6shave.blob   # 新的神经网络模型
└── readme.md                          # 本说明文件
```

## 使用说明

1. **启动程序**: 运行 `single_oak_detector_v2.py`
2. **参数调整**: 使用GUI窗口实时调整坐标变换参数
3. **显示控制**: 使用按键切换不同的显示模式
4. **CAN通信**: 可选择启用/禁用CAN通信功能

## 依赖要求

- OpenCV (cv2)
- DepthAI (depthai)
- NumPy
- Tkinter (GUI)
- 相关自定义模块 (calculate_module, can_module)

## 注意事项

- 确保模型文件 `best_openvino_2022.1_6shave.blob` 存在于同目录下
- 16:9长宽比设计更符合实际应用场景
- 全屏模式适合详细观察，中屏模式适合多窗口工作

## 存在的问题

- 标定参数下，未能完整重建目标坐标系，仍需进一步寻找解决方法

## 误差数据记录功能

### 数据保存格式

误差数据以JSON格式保存在 `error/error_data.json` 文件中，采用追加模式。每条记录包含以下字段：

```json
{
  "timestamp": "2025-09-01T11:15:37.123456",
  "target_type": "durian",
  "real_position": [123.4, 456.7],
  "error_vector": [12.3, -45.6],
  "reference_position": [111.1, 502.3]
}
```

### 字段说明

- **timestamp**: 记录时间戳，ISO格式
- **target_type**: 目标类型，可选值：`"durian"` 或 `"person"`
- **real_position**: 实际检测到的目标位置 `[x, y]` (单位：mm)
- **error_vector**: 误差向量 `[error_x, error_y]` (单位：mm)
  - `error_x = real_x - reference_x`
  - `error_y = real_y - reference_y`
- **reference_position**: 基准位置 `[ref_x, ref_y]` (单位：mm)

### 使用流程

1. 启动程序时选择要记录的目标类型（durian/person）
2. 在GUI中设置基准位置坐标
3. 点击GUI中的"记录误差数据"按钮记录当前目标位置
4. 数据自动追加保存到 `error/error_data.json` 文件

### 数据文件管理

- **文件位置**: `error/error_data.json`（脚本同级目录）
- **保存模式**: 追加模式，所有记录保存在同一文件中
- **编码格式**: UTF-8，支持中文字符
- **格式化**: 带缩进的JSON格式，便于阅读