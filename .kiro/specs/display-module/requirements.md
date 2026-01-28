# 需求文档：显示模块（Display Module）

## 简介

显示模块是系统的可视化输出终端，负责接收渲染包（RenderPacket）并将检测结果、视频帧、处理数据等信息以图形化方式呈现给用户。本模块采用异步渲染模式，确保实时性和流畅性。

**开发策略**：
- **阶段 1（MVP）**：实现最小可行功能，验证数据流完整性
- **阶段 2（完整版）**：实现所有功能特性，提供完整的用户体验

**模块架构**：
```
┌─────────────────────────────────────────────────────────┐
│                    Display Module                        │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  RenderPacketPackager (适配器子模块)           │    │
│  │  - 订阅外部事件（VideoFrame + ProcessedData）  │    │
│  │  - 配对数据（按 device_id + frame_id）         │    │
│  │  - 转换为 RenderPacket                         │    │
│  │  - 放入内部队列（不发布事件）                  │    │
│  └────────────────────────────────────────────────┘    │
│                          ↓ 内部队列                     │
│  ┌────────────────────────────────────────────────┐    │
│  │  DisplayRenderer (渲染子模块)                  │    │
│  │  - 从队列读取 RenderPacket                     │    │
│  │  - 绘制检测框、标签、坐标等                    │    │
│  │  - 显示窗口                                    │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**数据流**：
```
外部事件（通过事件总线）
    ↓
RenderPacketPackager（适配器）
    ↓
内部队列（线程安全）
    ↓
DisplayRenderer（渲染器）
    ↓
OpenCV 窗口显示
```

**核心特性**：
- 适配器模式：RenderPacketPackager 作为数据适配器，将外部异构数据转换为内部统一格式
- 模块内通信：适配器和渲染器通过内部队列通信，不使用事件总线
- 异步渲染：接收到渲染包即刻渲染，不阻塞上游
- 线程安全：使用阻塞队列缓冲数据
- 配置驱动：所有显示参数可通过 DisplayConfigDTO 配置

---

## 术语表

- **Display_Module**：显示模块，负责图形化输出
- **RenderPacketPackager**：渲染包打包器，作为显示模块的适配器子模块，将外部异构数据转换为内部统一格式
- **DisplayRenderer**：显示渲染器，显示模块的核心子模块，负责实际的图形渲染
- **RenderPacket**：渲染包，显示模块的内部数据格式，包含视频帧和处理后的检测数据
- **Adapter_Pattern**：适配器模式，RenderPacketPackager 采用此模式将外部数据适配为内部格式
- **Internal_Queue**：内部队列，适配器和渲染器之间的通信通道，不使用事件总线
- **Overlay**：叠加层，在视频帧上绘制的检测信息
- **Async_Rendering**：异步渲染，接收到数据即渲染，不等待配对
- **OpenCV_Window**：OpenCV 窗口，用于显示图像
- **FPS**：每秒帧数，衡量渲染性能
- **Colormap**：颜色映射，用于深度图可视化
- **BBox**：边界框（Bounding Box），检测目标的矩形框
- **MVP**：最小可行产品（Minimum Viable Product），核心功能的最简实现

---

## 需求优先级说明

本文档将需求分为两个优先级：


### 🎯 P0 - MVP 需求（最小可行产品）

**目标**：验证数据流完整性，快速看到可视化效果

**范围**：
- 基础窗口显示
- 简单的检测框绘制
- 接收和处理渲染包
- 基本的线程管理

**时间估计**：1-2 小时

### 🚀 P1 - 完整需求

**目标**：提供完整的用户体验和所有功能特性

**范围**：
- 所有叠加信息（标签、置信度、坐标、FPS、设备信息）
- 多种显示模式（RGB/Depth/Combined/Side-by-Side）
- 深度图可视化
- 完整的配置支持
- 错误处理和统计

**时间估计**：2-3 小时

---

## 需求 1：基础架构和线程管理 🎯 P0

**用户故事**：作为系统开发者，我希望显示模块能够独立运行在单独的线程中，并通过内部队列安全地接收和处理渲染包。

### 验收标准

1. THE Display_Module SHALL 包含两个子模块：RenderPacketPackager（适配器）和 DisplayRenderer（渲染器）
2. THE RenderPacketPackager SHALL 在独立线程中运行，负责数据配对和适配
3. THE DisplayRenderer SHALL 在独立线程中运行，负责图形渲染
4. THE RenderPacketPackager SHALL 订阅外部事件（RAW_FRAME_DATA 和 PROCESSED_DATA）
5. THE RenderPacketPackager SHALL 维护按设备ID分组的内部队列（`packet_queue: Dict[str, OverflowQueue[RenderPacket]]`）
6. THE DisplayRenderer SHALL 通过 `get_packets()` 或 `get_packet_by_mxid()` 方法读取渲染包
7. THE Display_Module SHALL 提供 start() 和 stop() 方法管理两个子模块的生命周期
8. WHEN 停止显示模块 THEN THE 模块 SHALL 停止两个子模块并清理资源
9. THE DisplayRenderer SHALL 在队列为空时使用缓存帧（如果未过期）或阻塞等待
10. THE RenderPacketPackager SHALL 不发布事件（仅消费外部事件，通过内部队列传递数据）

**实现要点**：
- 使用 `threading.Thread` 为两个子模块创建独立线程
- RenderPacketPackager 使用 `Dict[str, OverflowQueue]` 为每个设备维护独立队列
- RenderPacketPackager 订阅 `EventType.RAW_FRAME_DATA` 和 `EventType.PROCESSED_DATA`
- DisplayRenderer 通过 `get_packets(timeout)` 方法获取所有设备的渲染包
- 支持多设备显示（每个设备独立队列）
- 缓存机制：当队列为空时，使用最近的缓存帧（如果未过期）
- 线程安全的启动/停止机制
- **关键**：适配器和渲染器之间不使用事件总线，使用内部队列通信

**当前实现状态**：
- ✅ RenderPacketPackager 已实现（`render_packet_packager.py`）
- ⏳ DisplayRenderer 待实现
- ⏳ DisplayManager 待实现

---

## 需求 2：基础窗口显示 🎯 P0

**用户故事**：作为用户，我希望能够在窗口中看到实时的视频流。

### 验收标准

1. THE DisplayRenderer SHALL 创建单个 OpenCV 窗口显示视频帧
2. WHEN DisplayRenderer 通过 `get_packets()` 获取到渲染包 THEN THE 模块 SHALL 提取 RGB 帧并显示
3. THE DisplayRenderer SHALL 使用 cv2.imshow() 显示图像
4. THE DisplayRenderer SHALL 使用 cv2.waitKey() 处理窗口事件
5. WHEN 用户按下 'q' 键 THEN THE 窗口 SHALL 关闭
6. THE DisplayRenderer SHALL 在窗口关闭时优雅退出
7. THE DisplayRenderer SHALL 使用单窗口策略（不是每个设备一个窗口）
8. THE DisplayRenderer SHALL 根据当前显示模式动态更新窗口内容

**实现要点**：
- 窗口名称：固定使用 "OAK Display" 或配置的名称
- 单窗口策略：只创建一个主窗口，根据显示模式切换内容
- 刷新机制：调用 `get_packets(timeout)` 获取所有设备的渲染包
- 退出机制：检测 'q' 键或窗口关闭事件
- 从 RenderPacketPackager 的内部队列读取数据
- 缓存机制：当队列为空时，使用缓存帧（如果未过期）

**当前实现状态**：
- ✅ RenderPacketPackager 提供 `get_packets()` 接口
- ✅ 支持多设备队列
- ✅ 缓存机制已实现（`cache_max_age_sec`）
- ⏳ DisplayRenderer 待实现（需要修改为单窗口策略）

---


## 需求 3：基础检测框绘制 🎯 P0

**用户故事**：作为用户，我希望能够看到检测到的目标的边界框。

### 验收标准

1. WHEN 渲染包包含检测数据 THEN THE DisplayRenderer SHALL 在视频帧上绘制边界框
2. THE DisplayRenderer SHALL 使用 cv2.rectangle() 绘制矩形框
3. THE 边界框 SHALL 使用固定颜色（例如绿色）
4. THE 边界框 SHALL 使用固定粗细（例如 2 像素）
5. WHEN 检测数据为空 THEN THE DisplayRenderer SHALL 仅显示视频帧，不绘制任何内容
6. THE DisplayRenderer SHALL 正确处理空检测帧（不崩溃）

**实现要点**：
- 从 `processed_detections.bbox` 提取边界框坐标
- 使用 `cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, thickness)`
- 固定颜色：`(0, 255, 0)` 绿色
- 固定粗细：`2` 像素

---

## 需求 4：配置加载 🎯 P0

**用户故事**：作为系统开发者，我希望显示模块能够从配置对象中读取基本参数。

### 验收标准

1. THE Display_Module SHALL 接收 DisplayConfigDTO 作为初始化参数
2. THE Display_Module SHALL 将配置传递给 DisplayRenderer 子模块
3. THE DisplayRenderer SHALL 读取 enable_display 配置决定是否启用显示
4. WHEN enable_display 为 False THEN THE DisplayRenderer SHALL 不创建窗口
5. THE DisplayRenderer SHALL 读取 window_width 和 window_height 配置窗口大小
6. THE Display_Module SHALL 在配置无效时抛出 ValueError

**实现要点**：
- DisplayManager 在 `__init__` 中接收 `DisplayConfigDTO`
- 验证配置有效性（调用 `config.validate()`）
- 将配置传递给 DisplayRenderer
- 根据 `enable_display` 决定是否启动渲染器

---

## 需求 5：错误处理 🎯 P0

**用户故事**：作为系统开发者，我希望显示模块在遇到错误时不会崩溃，而是记录日志并继续运行。

### 验收标准

1. WHEN 渲染包数据无效 THEN THE DisplayRenderer SHALL 记录错误日志并跳过该帧
2. WHEN OpenCV 操作失败 THEN THE DisplayRenderer SHALL 记录错误日志并继续运行
3. THE DisplayRenderer SHALL 捕获所有异常，避免线程崩溃
4. THE RenderPacketPackager SHALL 捕获配对过程中的异常，避免线程崩溃
5. THE Display_Module SHALL 使用 logging 模块记录错误信息
6. WHEN 队列获取超时 THEN THE DisplayRenderer SHALL 继续循环，不退出

**实现要点**：
- 使用 `try-except` 包裹关键操作
- 使用 `logger.error()` 记录错误
- 队列获取使用超时机制（例如 1 秒）
- 两个子模块都需要错误处理

---


## 需求 6：完整的检测信息叠加 🚀 P1

**用户故事**：作为用户，我希望能够看到检测目标的详细信息，包括标签、置信度和 3D 坐标。

### 验收标准

1. WHEN show_labels 为 True THEN THE DisplayRenderer SHALL 在边界框上方显示标签文本
2. WHEN show_confidence 为 True THEN THE DisplayRenderer SHALL 在标签旁显示置信度百分比
3. WHEN show_coordinates 为 True THEN THE DisplayRenderer SHALL 在边界框下方显示 3D 坐标
4. THE 标签文本 SHALL 使用 cv2.putText() 绘制
5. THE 文本 SHALL 使用配置的 text_scale 大小
6. THE 文本 SHALL 使用白色背景矩形提高可读性
7. THE 坐标 SHALL 格式化为 "(x, y, z) mm"

**实现要点**：
- 标签格式：`"person"` 或 `"person 95%"`（根据配置）
- 坐标格式：`"(1234, 567, 890) mm"`
- 使用 `cv2.rectangle()` 绘制文本背景
- 使用 `cv2.putText()` 绘制文本

---

## 需求 7：按标签着色 🚀 P1

**用户故事**：作为用户，我希望不同类别的检测目标使用不同的颜色，便于区分。

### 验收标准

1. WHEN bbox_color_by_label 为 True THEN THE 模块 SHALL 根据标签 ID 选择颜色
2. THE Display_Module SHALL 维护一个颜色映射表（label_id → color）
3. THE 颜色映射表 SHALL 包含至少 10 种不同的颜色
4. WHEN bbox_color_by_label 为 False THEN THE 模块 SHALL 使用固定颜色（绿色）
5. THE 颜色 SHALL 在 BGR 格式中定义（OpenCV 格式）

**实现要点**：
- 预定义颜色列表：`[(0, 255, 0), (255, 0, 0), (0, 0, 255), ...]`
- 颜色选择：`color = colors[label_id % len(colors)]`

---

## 需求 8：FPS 和设备信息显示 🚀 P1

**用户故事**：作为用户，我希望能够看到实时的帧率和设备信息，以便监控系统性能。

### 验收标准

1. WHEN show_fps 为 True THEN THE DisplayRenderer SHALL 在窗口左上角显示当前 FPS
2. WHEN show_device_info 为 True THEN THE DisplayRenderer SHALL 在窗口右上角显示设备信息
3. THE FPS SHALL 每秒更新一次
4. THE FPS SHALL 计算最近 1 秒内的平均帧率
5. THE 设备信息 SHALL 包含设备别名和设备 ID
6. THE 信息文本 SHALL 使用半透明背景提高可读性

**实现要点**：
- FPS 计算：维护帧时间戳队列，计算平均值
- 设备信息格式：`"Device: left_camera (18443010D116441200)"`
- 使用 `cv2.rectangle()` 绘制半透明背景

---


## 需求 9：多设备显示模式切换 🚀 P1

**用户故事**：作为用户，我希望能够通过按键切换不同的显示模式，查看单个设备或多设备合并视图。

### 验收标准

1. THE DisplayRenderer SHALL 支持以下显示模式：
   - 单设备显示：显示特定设备的 RGB 图像
   - Combined 模式：多设备 RGB 图像水平拼接显示
2. THE DisplayRenderer SHALL 使用单窗口显示（不是每个设备一个窗口）
3. WHEN 用户按下数字键 '1', '2', '3'... THEN THE DisplayRenderer SHALL 切换到对应设备的单设备显示
4. WHEN 用户按下 '3' 键（或配置的 combined 键）THEN THE DisplayRenderer SHALL 切换到 Combined 模式
5. WHEN 显示模式为单设备 THEN THE DisplayRenderer SHALL 只显示该设备的 RGB 帧
6. WHEN 显示模式为 Combined THEN THE DisplayRenderer SHALL 水平拼接所有设备的 RGB 帧
7. THE DisplayRenderer SHALL 在每个设备的图像上显示设备名称标签
8. WHEN 只有一个设备在线 THEN THE DisplayRenderer SHALL 自动使用单设备显示（避免半边黑屏）
9. THE DisplayRenderer SHALL 根据 enable_depth_output 配置决定是否处理深度数据

**实现要点**：
- 单窗口策略：使用一个主窗口，根据模式动态更新显示内容
- 设备切换：维护当前选中的设备索引
- Combined 模式：使用 `np.hstack()` 水平拼接多个设备的 RGB 帧
- 设备标签：在每个设备图像的左上角显示设备别名
- 键盘事件：
  - '1': 切换到第一个设备
  - '2': 切换到第二个设备
  - '3': 切换到 Combined 模式
  - 'f': 切换全屏
  - 'q': 退出
- 自适应显示：检测在线设备数量，单设备时自动全屏显示
- 深度数据：仅当 enable_depth_output=True 时处理深度帧（可选功能）

---

## 需求 10：深度图可视化（可选功能） 🚀 P1

**用户故事**：作为用户，我希望能够以伪彩色方式查看深度信息，便于理解场景的 3D 结构（当 enable_depth_output=True 时）。

### 验收标准

1. WHEN enable_depth_output 为 True THEN THE DisplayRenderer SHALL 处理深度帧数据
2. WHEN enable_depth_output 为 False THEN THE DisplayRenderer SHALL 忽略深度帧数据
3. THE DisplayRenderer SHALL 将深度图转换为伪彩色图像（使用 HOT 颜色映射）
4. WHEN normalize_depth 为 True THEN THE DisplayRenderer SHALL 使用百分位数归一化深度值
5. THE DisplayRenderer SHALL 处理深度图中的无效值（NaN、Inf）
6. THE 深度图 SHALL 与 RGB 图像尺寸一致

**实现要点**：
- 参考旧实现的百分位数归一化方法（更鲁棒）：
  ```python
  depth_downscaled = depthFrame[::4]  # 下采样提高性能
  if np.all(depth_downscaled == 0):
      min_depth = 0
  else:
      min_depth = np.percentile(depth_downscaled[depth_downscaled != 0], 1)
  max_depth = np.percentile(depth_downscaled, 99)
  depthFrameColor = np.interp(depthFrame, (min_depth, max_depth), (0, 255)).astype(np.uint8)
  depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_HOT)
  ```
- 固定使用 HOT 颜色映射（简化配置）
- 无效值处理：`depth[np.isnan(depth)] = 0`
- 深度图显示为可选功能，由 enable_depth_output 配置控制

---

## 需求 11：窗口管理 🚀 P1

**用户故事**：作为用户，我希望能够调整窗口大小和位置，以适应不同的显示需求。

### 验收标准

1. THE DisplayRenderer SHALL 根据配置设置窗口初始大小
2. THE DisplayRenderer SHALL 根据配置设置窗口初始位置
3. WHEN enable_fullscreen 为 True THEN THE DisplayRenderer SHALL 以全屏模式显示
4. WHEN 用户按下 'f' 键 THEN THE DisplayRenderer SHALL 切换全屏/窗口模式
5. THE DisplayRenderer SHALL 允许用户手动调整窗口大小
6. THE DisplayRenderer SHALL 在窗口标题显示设备别名

**实现要点**：
- 窗口创建：`cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)`
- 窗口大小：`cv2.resizeWindow(window_name, width, height)`
- 窗口位置：`cv2.moveWindow(window_name, x, y)`
- 全屏模式：`cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)`

---


## 需求 12：性能优化 🚀 P1

**用户故事**：作为系统开发者，我希望显示模块能够高效运行，不影响整体系统性能。

### 验收标准

1. THE DisplayRenderer SHALL 根据 target_fps 配置限制渲染帧率
2. WHEN 渲染速度超过 target_fps THEN THE DisplayRenderer SHALL 主动休眠以降低 CPU 占用
3. THE RenderPacketPackager SHALL 在队列满时丢弃旧帧，保持实时性
4. THE DisplayRenderer SHALL 避免不必要的图像复制
5. THE DisplayRenderer SHALL 使用 NumPy 数组视图而非复制
6. THE DisplayRenderer SHALL 在空闲时释放 GIL（使用 cv2.waitKey）

**实现要点**：
- 帧率限制：计算帧间隔，使用 `time.sleep()` 控制
- 队列策略：RenderPacketPackager 使用 `OverflowQueue` 自动丢弃旧数据
- 避免复制：直接在原始数组上绘制

---

## 需求 13：统计和监控 🚀 P1

**用户故事**：作为系统维护员，我希望能够查询显示模块的运行统计信息。

### 验收标准

1. THE Display_Module SHALL 提供 get_stats() 方法返回统计信息
2. THE 统计信息 SHALL 包含以下指标：
   - 当前 FPS
   - 总渲染帧数
   - 丢弃帧数（来自 RenderPacketPackager）
   - 队列使用率
   - 运行时长
3. THE Display_Module SHALL 在日志中定期输出统计信息（可选）
4. THE 统计信息 SHALL 线程安全

**实现要点**：
- DisplayRenderer 维护渲染统计：`_render_stats = {"frames": 0, ...}`
- RenderPacketPackager 维护配对统计：`_packager_stats = {"drops": 0, ...}`
- DisplayManager 聚合两个子模块的统计信息
- 使用锁保护统计数据：`threading.Lock()`

---

## 需求 14：优雅关闭 🚀 P1

**用户故事**：作为系统开发者，我希望显示模块能够优雅地关闭，释放所有资源。

### 验收标准

1. WHEN 调用 stop() 方法 THEN THE Display_Module SHALL 停止两个子模块
2. THE RenderPacketPackager SHALL 停止接收新事件并处理完队列中的剩余数据
3. THE DisplayRenderer SHALL 处理完队列中的剩余数据后退出
4. THE DisplayRenderer SHALL 关闭所有 OpenCV 窗口
5. THE RenderPacketPackager SHALL 取消事件订阅
6. THE Display_Module SHALL 在超时时间内强制退出
7. THE Display_Module SHALL 记录关闭统计信息

**实现要点**：
- 使用 `threading.Event` 作为停止信号
- 使用 `thread.join(timeout)` 等待线程结束
- DisplayRenderer 使用 `cv2.destroyAllWindows()` 关闭窗口
- RenderPacketPackager 取消事件订阅
- DisplayManager 协调两个子模块的关闭顺序

---

## 需求 16：多设备支持 🚀 P1

**用户故事**：作为用户，我希望能够同时查看多个设备的视频流和检测结果，并通过按键切换显示模式。

### 验收标准

1. THE RenderPacketPackager SHALL 为每个设备维护独立的渲染包队列
2. THE DisplayRenderer SHALL 使用单窗口显示所有设备（不是每个设备一个窗口）
3. THE DisplayRenderer SHALL 使用 `get_packets()` 方法一次性获取所有设备的渲染包
4. WHEN 某个设备的队列为空 THEN THE DisplayRenderer SHALL 使用该设备的缓存帧（如果未过期）
5. THE DisplayRenderer SHALL 支持按数字键切换显示特定设备
6. THE DisplayRenderer SHALL 支持 Combined 模式（多设备 RGB 水平拼接）
7. THE DisplayRenderer SHALL 在每个设备的图像上显示设备名称标签
8. WHEN 只有一个设备在线 THEN THE DisplayRenderer SHALL 自动使用单设备全屏显示
9. WHEN 用户按下 'q' 键 THEN THE 窗口 SHALL 关闭

**实现要点**：
- RenderPacketPackager 已实现：`packet_queue: Dict[str, OverflowQueue[RenderPacket]]`
- DisplayRenderer 需要：
  - 单窗口策略：只创建一个主窗口
  - 显示模式管理：维护当前显示模式（单设备索引 或 Combined）
  - 循环调用 `get_packets()` 获取所有设备的数据
  - 根据显示模式选择渲染策略：
    - 单设备模式：只渲染选中设备的帧
    - Combined 模式：水平拼接所有设备的帧
  - 设备标签：在每个设备图像上显示设备名称
- 缓存机制：`get_packets()` 已实现缓存逻辑
- 按键映射：
  - '1': 第一个设备
  - '2': 第二个设备
  - '3': Combined 模式
  - 'f': 全屏切换
  - 'q': 退出

**当前实现状态**：
- ✅ RenderPacketPackager 已支持多设备（按设备ID分组队列）
- ✅ 缓存机制已实现（`_latest_packets` + `cache_max_age_sec`）
- ⏳ DisplayRenderer 单窗口多模式显示待实现

---

**用户故事**：作为系统开发者，我希望显示模块能够正确处理空检测帧，不影响显示流畅性。

### 验收标准

1. WHEN 渲染包包含空检测数据 THEN THE DisplayRenderer SHALL 仅显示视频帧
2. THE DisplayRenderer SHALL 不绘制任何检测框或标签
3. THE DisplayRenderer SHALL 正常显示 FPS 和设备信息
4. THE DisplayRenderer SHALL 不记录错误日志
5. THE 空帧处理 SHALL 与非空帧处理使用相同的代码路径
6. THE RenderPacketPackager SHALL 正确配对包含空检测数据的渲染包

**实现要点**：
- DisplayRenderer 检查 `processed_detections.coords.shape[0] == 0`
- 跳过检测框绘制循环
- 保持其他叠加信息正常显示
- RenderPacketPackager 正确处理空的 ProcessedDataDTO

---


## 需求总结

### MVP 需求（P0）- 必须实现

**目标**：验证数据流，快速看到效果

| 需求 | 描述 | 估计时间 |
|------|------|---------|
| 需求 1 | 基础架构和线程管理（适配器 + 渲染器） | 40 分钟 |
| 需求 2 | 基础窗口显示（支持多设备） | 30 分钟 |
| 需求 3 | 基础检测框绘制 | 20 分钟 |
| 需求 4 | 配置加载 | 15 分钟 |
| 需求 5 | 错误处理 | 15 分钟 |
| **总计** | **MVP 功能** | **2-2.5 小时** |

**MVP 验收标准**：
- ✅ 能够启动显示模块（包含适配器和渲染器两个子模块）
- ✅ RenderPacketPackager 能够订阅外部事件并配对数据（已实现）
- ✅ RenderPacketPackager 支持多设备队列（已实现）
- ✅ DisplayRenderer 能够通过 `get_packets()` 接收渲染包
- ✅ 能够显示视频帧（支持多设备）
- ✅ 能够绘制绿色检测框
- ✅ 按 'q' 键能够退出
- ✅ 不崩溃，能够处理空帧
- ✅ 适配器和渲染器通过内部队列通信（不使用事件总线）
- ✅ 缓存机制工作正常（队列为空时使用缓存帧）

---

### 完整需求（P1）- 后续实现

**目标**：提供完整的用户体验

| 需求 | 描述 | 估计时间 |
|------|------|---------|
| 需求 6 | 完整的检测信息叠加 | 30 分钟 |
| 需求 7 | 按标签着色 | 15 分钟 |
| 需求 8 | FPS 和设备信息显示 | 20 分钟 |
| 需求 9 | 多种显示模式 | 30 分钟 |
| 需求 10 | 深度图可视化 | 20 分钟 |
| 需求 11 | 窗口管理 | 15 分钟 |
| 需求 12 | 性能优化 | 20 分钟 |
| 需求 13 | 统计和监控 | 15 分钟 |
| 需求 14 | 优雅关闭 | 15 分钟 |
| 需求 15 | 空帧处理 | 10 分钟 |
| 需求 16 | 多设备支持（已部分实现） | 20 分钟 |
| **总计** | **完整功能** | **3.5-4 小时** |

**完整版验收标准**：
- ✅ 所有 MVP 功能正常
- ✅ RenderPacketPackager 多设备支持（已实现）
- ✅ 缓存机制（已实现）
- ✅ DisplayRenderer 多设备窗口管理
- ✅ 显示标签、置信度、3D 坐标
- ✅ 不同类别使用不同颜色
- ✅ 显示 FPS 和设备信息
- ✅ 支持 4 种显示模式切换
- ✅ 深度图正确可视化
- ✅ 窗口大小和位置可配置
- ✅ 性能满足 target_fps 要求
- ✅ 统计信息准确
- ✅ 优雅关闭，无资源泄漏

---

## 实施优先级

### 第一阶段：MVP 实现（立即开始）

**目标**：验证数据流完整性

**任务**：
1. ✅ RenderPacketPackager（适配器子模块）- 已实现
   - ✅ 订阅外部事件（RAW_FRAME_DATA + PROCESSED_DATA）
   - ✅ 配对数据
   - ✅ 维护按设备ID分组的内部队列
   - ✅ 缓存机制（`cache_max_age_sec`）
   - ✅ 提供 `get_packets()` 和 `get_packet_by_mxid()` 接口
2. ⏳ DisplayRenderer（渲染器子模块）- 待实现
   - 通过 `get_packets()` 读取所有设备的渲染包
   - 基础窗口显示（支持多设备）
   - 基础检测框绘制
3. ⏳ DisplayManager（主控制器）- 待实现
   - 协调两个子模块
   - 提供统一接口
4. 进行端到端测试
5. 验证能否看到检测框

**成功标准**：
- ✅ RenderPacketPackager 能够从 Collector 和 DataProcessor 接收数据（已实现）
- ✅ RenderPacketPackager 能够正确配对数据（已实现）
- ✅ RenderPacketPackager 支持多设备（已实现）
- ⏳ DisplayRenderer 能够显示视频帧和检测框
- ⏳ 系统不崩溃
- **关键**：验证适配器模式工作正常（内部队列通信）

### 第二阶段：完整功能实现（MVP 验证通过后）

**目标**：提供完整的用户体验

**任务**：
1. 实现需求 6-15（完整需求）
2. 进行功能测试
3. 进行性能测试

**成功标准**：
- 所有功能正常工作
- 性能满足要求
- 用户体验良好

---

## 测试策略

### MVP 测试

**单元测试**（可选）：
- 测试队列接收和处理
- 测试基础绘制函数

**集成测试**（必需）：
- 端到端测试：Collector → DataProcessor → RenderPacketPackager → Display
- 验证数据流完整性
- 验证能否看到检测框

### 完整版测试

**单元测试**：
- 测试所有绘制函数
- 测试显示模式切换
- 测试统计计数

**集成测试**：
- 测试所有显示模式
- 测试空帧处理
- 测试性能（FPS）

**压力测试**：
- 测试高帧率场景
- 测试长时间运行稳定性

---

## 技术约束

1. **OpenCV 版本**：需要 OpenCV 4.x 或更高版本
2. **线程安全**：所有共享数据必须使用锁保护
3. **性能要求**：渲染延迟 < 50ms
4. **内存占用**：队列大小限制在 10 帧以内
5. **兼容性**：支持 Windows/Linux/macOS

---

## 依赖关系

**输入依赖**：
- Collector 发布的 RAW_FRAME_DATA 事件（通过事件总线）
- DataProcessor 发布的 PROCESSED_DATA 事件（通过事件总线）
- DisplayConfigDTO 配置对象

**内部通信**：
- RenderPacketPackager → 内部队列 → DisplayRenderer（不使用事件总线）

**输出**：
- OpenCV 窗口显示
- 日志输出
- 统计信息

**外部依赖**：
- OpenCV (cv2)
- NumPy
- threading
- queue
- logging

**架构说明**：
- RenderPacketPackager 是 Display 模块的适配器子模块
- 负责将外部异构数据（VideoFrameDTO + ProcessedDataDTO）转换为内部统一格式（RenderPacket）
- 适配器和渲染器之间使用内部队列通信，不使用事件总线
- 这符合"事件总线用于模块间通信，队列用于模块内通信"的设计原则

---

## 风险和缓解

### 风险 1：OpenCV 窗口在某些环境下无法创建

**缓解**：
- 添加环境检测
- 提供无头模式（保存图像到文件）
- 文档说明环境要求

### 风险 2：高帧率下 CPU 占用过高

**缓解**：
- 实现帧率限制
- RenderPacketPackager 使用队列溢出策略
- 优化绘制代码

### 风险 3：多设备显示时窗口管理复杂

**缓解**：
- MVP 阶段只支持单设备
- 完整版再考虑多设备支持

### 风险 4：适配器和渲染器之间的队列可能成为瓶颈

**缓解**：
- 使用 OverflowQueue 自动丢弃旧数据
- 监控队列使用率
- 调整队列大小

---

## 附录A：架构设计说明

### 为什么采用适配器模式？

**RenderPacketPackager 的本质**：
- 将外部异构数据（VideoFrameDTO + ProcessedDataDTO）转换为内部统一格式（RenderPacket）
- 专门为 Display 模块设计，不被其他模块使用
- 这正是适配器模式的核心职责

**为什么不使用事件总线？**：
1. **语义清晰**：RenderPacketPackager 是 Display 的子模块，不是独立模块
2. **性能更好**：减少一层间接调用
3. **符合设计原则**：事件总线用于模块间通信，队列用于模块内通信
4. **紧耦合合理**：既然是子模块，紧耦合是合理的

### 模块结构

```
oak_vision_system/modules/display_modules/
├── __init__.py
├── render_packet_packager.py  # 适配器子模块
├── display_renderer.py         # 渲染器子模块
└── display_manager.py          # 主控制器
```

### 数据流

```
外部模块（通过事件总线）
    ↓
RenderPacketPackager（订阅事件，配对数据）
    ↓
内部队列（线程安全）
    ↓
DisplayRenderer（渲染显示）
    ↓
OpenCV 窗口
```

---

## 附录B：旧实现参考（dual_detectionv2.py）

本节记录旧实现中值得参考的设计和实现细节，供后续任务实现时参考。

### 1. 深度图可视化（参考任务 12.1）

旧实现使用百分位数归一化方法处理深度图，比简单的 `cv2.normalize` 更鲁棒：

```python
# 旧实现的深度图处理方法（推荐）
depth_downscaled = depthFrame[::4]  # 下采样提高性能
if np.all(depth_downscaled == 0):
    min_depth = 0
else:
    min_depth = np.percentile(depth_downscaled[depth_downscaled != 0], 1)
max_depth = np.percentile(depth_downscaled, 99)
depthFrameColor = np.interp(depthFrame, (min_depth, max_depth), (0, 255)).astype(np.uint8)
depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_HOT)
```

**优点**：
- 使用百分位数（1% 和 99%）避免极值影响
- 下采样提高性能
- 处理全零深度图的边界情况

**应用场景**：任务 12.1（实现深度图可视化）

---

### 2. 全屏模式切换（参考任务 13.3）

旧实现的全屏切换逻辑简单有效：

```python
def toggle_fullscreen(self, window_name: str):
    """切换全屏模式"""
    self.fullscreen_mode = not self.fullscreen_mode
    if self.fullscreen_mode:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        print("切换到全屏模式")
    else:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
        print("切换到窗口模式")
```

**应用场景**：任务 13.3（实现全屏切换）

---

### 3. 多设备图像拼接（参考任务 16）

旧实现使用水平拼接方式合并多个设备的图像：

```python
def create_combined_display(self):
    """创建合并的显示窗口"""
    rgb_frames = []
    device_names = []
    
    for alias, frame_data in self.device_frames.items():
        if frame_data['rgb'] is not None:
            rgb_resized = cv2.resize(frame_data['rgb'], (self.single_frame_width, self.single_frame_height))
            rgb_frames.append(rgb_resized)
            device_names.append(alias)
    
    # 水平拼接RGB图像
    if len(rgb_frames) == 1:
        combined_rgb = rgb_frames[0]
    else:
        combined_rgb = np.hstack(rgb_frames)
    
    # 在图像上添加设备名称标签
    for i, name in enumerate(device_names):
        x_offset = i * self.single_frame_width
        cv2.putText(combined_rgb, f"{name}", (x_offset + 10, 30), 
                   cv2.FONT_HERSHEY_TRIPLEX, 0.7, (0, 255, 255), 2)
    
    return combined_rgb
```

**优点**：
- 支持单设备和多设备场景
- 使用 `np.hstack()` 水平拼接
- 为每个设备添加名称标签

**应用场景**：任务 16（多设备支持）

---

### 4. 信息叠加布局（参考任务 9）

旧实现的信息叠加布局清晰，垂直排列多行信息：

```python
# 绘制标签、置信度和坐标信息
cv2.putText(frame, str(label), (x1 + 10, y1 + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, text_color)
cv2.putText(frame, f"{detection.confidence*100:.2f}%", (x1 + 10, y1 + 35), cv2.FONT_HERSHEY_TRIPLEX, 0.5, text_color)

# 显示变换后坐标
cv2.putText(frame, "Transform Coord:", (x1 + 10, y1 + 50), cv2.FONT_HERSHEY_TRIPLEX, 0.4, text_color)
cv2.putText(frame, f"X: {int(trans_coord[0])} mm", (x1 + 10, y1 + 65), cv2.FONT_HERSHEY_TRIPLEX, 0.4, text_color)
cv2.putText(frame, f"Y: {int(trans_coord[1])} mm", (x1 + 10, y1 + 80), cv2.FONT_HERSHEY_TRIPLEX, 0.4, text_color)
cv2.putText(frame, f"Z: {int(trans_coord[2])} mm", (x1 + 10, y1 + 95), cv2.FONT_HERSHEY_TRIPLEX, 0.4, text_color)

# 绘制检测框
cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
```

**对比新实现**：
- 新实现已经实现了类似功能（任务 9 已完成）
- 新实现使用半透明背景提高可读性
- 布局更简洁（标签+置信度在上方，坐标在下方）

---

### 5. 窗口大小自适应（参考任务 13）

旧实现根据全屏模式动态调整窗口大小：

```python
# 根据全屏模式调整尺寸
if self.fullscreen_mode:
    rgb_frame = cv2.resize(frame_data['rgb'], (1920, 1080))
else:
    rgb_frame = cv2.resize(frame_data['rgb'], (1280, 720))
```

**应用场景**：任务 13（窗口管理）

---

### 6. FPS 计算（参考任务 11）

旧实现使用简单的计数器方法计算 FPS：

```python
# FPS计算
counter += 1
current_time = time.monotonic()
if (current_time - startTime) > 1:
    fps = counter / (current_time - startTime)
    counter = 0
    startTime = current_time
```

**对比新实现**：
- 新实现使用滑动窗口（帧时间戳队列）计算 FPS，更准确
- 新实现已完成（任务 11 已完成）

---

### 7. 不建议参考的部分

以下旧实现的部分**不建议**在新设计中参考：

#### a) DepthAI API 直接调用
```python
# 不建议：直接从 DepthAI 获取数据
previewQueue = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
detectionNNQueue = device.getOutputQueue(name="detections", maxSize=4, blocking=False)
```

**原因**：这些逻辑应该在 `Collector` 模块中处理，`DisplayRenderer` 只负责渲染已经处理好的数据。

#### b) 线程管理方式
```python
# 不建议：为每个设备创建独立线程
thread = threading.Thread(target=self.device_detection_thread, args=(alias, mxid))
```

**原因**：新设计使用事件总线和队列机制，更解耦。

#### c) 数据融合逻辑
```python
# 不建议：在 Display 模块中融合数据
def fuse_device_data(self):
    """融合多设备数据，选择最近的目标"""
```

**原因**：这应该在 `DataProcessor` 模块中处理，不是 Display 模块的职责。

---

### 8. 总结

**推荐参考的部分**：
1. ✅ 深度图百分位数归一化（任务 12.1）
2. ✅ 全屏模式切换（任务 13.3）
3. ✅ 多设备图像拼接（任务 16）
4. ✅ 窗口大小自适应（任务 13）

**不建议参考的部分**：
1. ❌ DepthAI API 直接调用（应该在 Collector 中）
2. ❌ 数据融合逻辑（应该在 DataProcessor 中）
3. ❌ 线程管理方式（新设计使用事件总线）

**新设计的优势**：
- 架构更清晰，职责分离
- 数据流更规范，通过事件总线和队列
- 配置驱动，易于调整
- 完整的单元测试覆盖

**继续按照新设计实现后续功能，仅在特定实现细节上参考旧实现的经验。** 🎯

