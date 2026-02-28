这是一个基于**"惰性渲染（Lazy Rendering）"**与**"状态驱动（State-Driven）"**的高性能可视化系统设计方案。

该方案旨在满足双路视频流的灵活切换与拼接显示，同时严格控制 Python 环境下的 CPU 开销。

---

### 一、 系统架构设计

系统逻辑分为四个解耦的模块，数据流向是单向的。

#### 1. 模块划分

| 模块名称                         | 职责描述                                                       |
| :--------------------------- | :--------------------------------------------------------- |
| **数据源接口 (Input Interface)**  | 负责从两个推理设备接收 RGB 帧和检测数据（JSON/Struct）。通常使用非阻塞队列（Queue）作为缓冲区。 |
| **状态控制器 (State Controller)** | 维护当前的显示逻辑状态（单/双模式、窗口尺寸、全屏标志）。响应键盘/鼠标事件并更新状态。               |
| **渲染核心 (Render Engine)**     | **(核心模块)** 根据状态机的指令，执行"按需"图像处理。包含缩放、拼接、坐标映射、图层绘制。          |
| **窗口管理器 (Window Manager)**   | 封装 OpenCV 的 GUI 操作，管理窗口属性（全屏/普通）、分辨率切换和最终上屏。               |

#### 2. 数据流拓扑

[Image of data flow diagram input to display]

`[设备1 & 2]` --> `[数据缓冲区 / 打包器]` --> `[渲染核心]` (根据状态 1 选择取包接口：单路 `get_packet_by_mxid` 或拼接 `get_packets`) --> `[合成画布]` --> `[窗口显示]`

其中「数据缓冲区」对应实现中的 RenderPacketPackager；渲染器按状态 1 决定调用其单包接口还是多包接口。

---

### 二、 核心逻辑设计

#### 1. 双状态驱动（状态机定义）

系统行为由**两个独立状态**驱动，数据取用与渲染流水线均据此分支。

* **状态 1（显示内容 / Mode）：** 左设备 | 右设备 | 拼接
  * 决定**从打包器取哪路数据、调用哪个接口**（见下文「打包器接口与取包策略」）。
  * 左/右对应的设备 mxid **仅**来源于外部传入的 `role_bindings`（见「外部依赖与配置来源」）。
  * 状态 1 还受**当前可运行设备数量与 role** 约束：例如仅左设备有数据时，有效状态 1 仅能为「左设备」或自动切到左；双路都有数据时才允许左 / 右 / 拼接 三种选择。
* **状态 2（视图属性 / View）：** 是否全屏
  * 决定目标分辨率（如 `NORMAL` 1280×720、`FULLSCREEN` 1920×1080）及窗口属性。
  * 仅在用户按键等事件时更新，不每帧查询窗口属性。

与原有命名对应：`SINGLE_SRC1` = 左设备，`SINGLE_SRC2` = 右设备，`DUAL_SPLIT` = 拼接。

#### 2. "漏斗型"渲染流水线 (The Pipeline)

为了节省算力，每一帧的处理流程必须是一个条件分支结构，而非并行结构。

* **第一阶段：目标画布计算**

  * 根据 `View` 状态（全屏/普通），确定最终画布的分辨率 `(Target_W, Target_H)`。
  * *优化点：此数值仅在窗口大小改变时重新计算。*

* **第二阶段：图像处理（按需分支 - Stretch Resize）**

  * **Resize 策略**：使用 `cv2.resize(frame, (dstW, dstH))` 直接拉伸到目标尺寸
    - **不使用** keep-aspect-ratio（等比缩放）
    - **不引入** padding/padX/padY
  * **分支 A (单图模式):** 仅提取对应源的图像 -> Stretch Resize 到 `(Target_W, Target_H)`
  * **分支 B (双图模式):** 提取两个源的图像 -> 分别 Stretch Resize 到各自 ROI 尺寸 -> 水平拼接到画布
    - 左图 ROI: `(Target_W // 2, Target_H)`
    - 右图 ROI: `(Target_W - Target_W // 2, Target_H)`
  * *关键点：未被选中的图像数据在此阶段直接丢弃，不消耗 CPU 进行缩放操作。*

* **第三阶段：UI 投影与绘制（归一化坐标映射）**

  * **坐标映射引擎：** 接收归一化检测框坐标 `bbox_norm = (xmin, ymin, xmax, ymax) ∈ [0,1]`，输出画布像素坐标 `(x1, y1, x2, y2)`
  * **绘制执行：** 在第二阶段生成的"干净底图"上绘制线条和文字
  * *优势：由于是在最终画布上绘制，无论图像在双图模式下被如何拉伸变形（16:9 -> 8:9），文字和线条的比例永远保持正常。*

#### 3. 打包器接口与取包策略

渲染器**根据状态 1** 选择打包器的调用方式，实现按需取包、单路不消费另一路队列：

| 状态 1     | 使用的接口 | 说明 |
|------------|------------|------|
| 左设备     | `get_packet_by_mxid(left_mxid, timeout)`  | 仅取左路一包，带缓存回退（见下） |
| 右设备     | `get_packet_by_mxid(right_mxid, timeout)` | 仅取右路一包，带缓存回退 |
| 拼接       | `get_packets(timeout)`                    | 一次获取两路渲染包，用于拼接 |

**单包接口的缓存机制（打包器需实现的调整）：**

* `get_packet_by_mxid(mxid, timeout)` 在原有「从该设备队列 `get(timeout)`」基础上，增加与 `get_packets` 一致的**缓存回退**：
  * 若 `queue.get(timeout)` 超时（Empty），则检查该设备的 `_latest_packets[mxid]` 与 `_packet_timestamps`；
  * 若未过期（`age <= cache_max_age_sec`），返回该缓存包；
  * 否则返回 `None`。
* 这样单路模式下画面稳定、不闪黑，且仍只消费当前需要的那一路队列。

**左/右 mxid 的来源：** 仅使用外部传入的 `role_bindings` 字典：左 = `role_bindings[DeviceRole.LEFT_CAMERA]`，右 = `role_bindings[DeviceRole.RIGHT_CAMERA]`（见「外部依赖与配置来源」）。

---

### 三、 外部依赖与配置来源

* **左/右设备 mxid：** 渲染器不直接依赖 ConfigManager，而是由**上层**在创建 DisplayManager / DisplayRenderer 时，从 ConfigManager 调用 `get_active_role_bindings()`，将得到的 `Dict[DeviceRole, str]` 以 **`role_bindings`** 参数传入。
* **约定：** 显示模块仅依赖这份 `role_bindings` 定义左/右语义与 mxid；左 = `role_bindings[DeviceRole.LEFT_CAMERA]`，右 = `role_bindings[DeviceRole.RIGHT_CAMERA]`。与 `devices_list` 顺序解耦。

---

### 四、 关键算法逻辑

#### 1. 坐标映射公式 (归一化坐标映射)

**输入格式**：归一化检测框坐标 `bbox_norm = (xmin, ymin, xmax, ymax) ∈ [0,1]`

**单图模式映射**：

```python
# 直接映射到目标画布
x1 = int(xmin * Target_W)
y1 = int(ymin * Target_H)
x2 = int(xmax * Target_W)
y2 = int(ymax * Target_H)
```

**双图模式映射（左右并排）**：

```python
# 定义 ROI（注意取整一致性）
roiW_left = Target_W // 2
roiW_right = Target_W - roiW_left

# 左图：offsetX = 0, roiW = roiW_left
# 右图：offsetX = roiW_left, roiW = roiW_right

# 对每一路 bbox（归一化）映射到画布
x1 = int(xmin * roiW) + offsetX
y1 = int(ymin * Target_H)
x2 = int(xmax * roiW) + offsetX
y2 = int(ymax * Target_H)
```

**设计优势**：
- 不依赖"原始图像宽高"参与计算
- 归一化坐标直接映射到任意目标尺寸
- 只需 offset 和 roiW，无需 padding 变量

#### 2. 拉伸变形策略（接受变形以换取性能）

* **变形现象：** 在双图模式下，16:9 的图像被 stretch resize 到 8:9 的 ROI，图像内容会在水平方向被压缩约 50%（变瘦）
* **设计选择：** **这是预期行为** - 我们选择接受变形以换取：
  - 简单的坐标映射（无需 letterbox 计算）
  - 更低的 CPU 开销（无需 padding 操作）
  - 统一的处理流程（单图和双图逻辑一致）
* **视觉补偿：** 渲染引擎**先拉伸底图，后绘制 UI**
  - 虽然视频内容变形，但覆盖在上面的文字（Label）和矩形框（BBox）在最终画布上绘制
  - UI 元素依然保持标准的宽高比，确保数据的可读性

---

### 五、 性能优化策略

1. **零拷贝原则 (Zero-Copy Logic):**
   单路模式下仅调用 `get_packet_by_mxid` 取当前路一包，不消费另一路队列；未选中的那一视频帧仅停留在打包器侧，渲染器不进行任何 OpenCV 操作（如 Resize, ColorCvt, Concat）。

2. **事件驱动的分辨率更新:**
   不要在每一帧的 `while` 循环里查询 `cv2.getWindowProperty`。只有当用户按下切换键（如 'F' 键）时，才触发窗口属性的变更和目标分辨率的重算。

3. **Stretch Resize 策略:**
   使用直接拉伸而非 letterbox，避免额外的 padding 计算和内存分配，简化坐标映射逻辑。

4. **对象复用:**
   虽然 Python 会自动管理内存，但在高帧率下，尽量减少大数组（如 4K 画布）的反复创建和销毁。虽然 OpenCV 的 Python 接口较难控制这一点，但逻辑上保持流程简洁是关键。

### 六、 设计约束（禁止项）

为确保设计的简洁性和性能，以下做法**明确禁止**：

❌ **不使用 keep-aspect-ratio resize**
- 不使用 letterbox（等比缩放 + padding）
- 不计算 padX/padY
- 直接使用 `cv2.resize(frame, (dstW, dstH))` 拉伸

❌ **不使用内容层固定单帧尺寸作为中间层**
- 不先 resize 到 640x360 再拼接
- 直接从原始帧 stretch resize 到目标 ROI 尺寸

❌ **不使用两层 resize**
- 单次 resize 直接到目标尺寸
- 避免"内容层 → 窗口层"的二次缩放

✅ **允许的做法**：
- 直接 stretch resize 到目标尺寸
- 归一化坐标直接映射
- 接受双图模式的拉伸变形

### 七、 开发建议

* **类结构建议：** `DisplayManager` 对外暴露主线程驱动的 `render_once()`（内部按状态 1 调用 `get_packet_by_mxid` 或 `get_packets`，再按状态 2 做 resize + 窗口设置 + 绘制），以及按键在 `render_once()` 内处理（或单独 `handle_input(key_code)`）。内部状态对调用者透明。
* **配置注入：** 创建时由上层传入 `role_bindings`（来自 ConfigManager 的 `get_active_role_bindings()`），用于解析左/右 mxid，显示模块不直接依赖 ConfigManager 实例。
* **异常处理：** 考虑到推理设备可能会有网络波动导致丢帧，渲染核心需要处理 `frame is None` 或取包返回 `None` 的情况，避免程序崩溃（可以显示"NO SIGNAL"黑屏）。
