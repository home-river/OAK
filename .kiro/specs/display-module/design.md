# 设计文档：显示模块（Display Module）

## 概述

本设计文档描述显示模块的详细设计，包括架构、组件、接口、数据流和正确性属性。显示模块负责将检测结果和视频帧以图形化方式呈现给用户，采用适配器模式和异步渲染架构。

### 设计目标

1. **验证数据流完整性**：确保从 Collector 到 Display 的完整数据流
2. **支持多设备显示**：同时显示多个设备的视频流和检测结果
3. **实时渲染**：满足 20-30 FPS 的实时显示要求
4. **模块化设计**：清晰的职责划分，易于维护和扩展
5. **配置驱动**：所有显示参数可通过配置文件调整

### 设计原则

1. **适配器模式**：RenderPacketPackager 作为数据适配器，将外部异构数据转换为内部统一格式
2. **模块内通信**：适配器和渲染器通过内部队列通信，不使用事件总线
3. **事件总线用于模块间通信**：仅用于跨模块的数据传输
4. **线程安全**：使用线程安全的队列和锁机制
5. **性能优先**：避免不必要的数据复制和日志开销

---

## 架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Display Module                          │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  RenderPacketPackager (适配器子模块)               │    │
│  │  - 订阅外部事件（RAW_FRAME_DATA + PROCESSED_DATA） │    │
│  │  - 配对数据（按 device_id + frame_id）             │    │
│  │  - 转换为 RenderPacket                             │    │
│  │  - 放入内部队列（不发布事件）                      │    │
│  │  - 支持多设备（按设备ID分组队列）                  │    │
│  │  - 缓存机制（cache_max_age_sec）                   │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓ 内部队列                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │  DisplayRenderer (渲染器子模块)                    │    │
│  │  - 从队列读取 RenderPacket                         │    │
│  │  - 绘制检测框、标签、坐标等                        │    │
│  │  - 显示窗口（支持多设备）                          │    │
│  │  - 处理用户输入（键盘事件）                        │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↑                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  DisplayManager (主控制器)                         │    │
│  │  - 协调两个子模块                                  │    │
│  │  - 提供统一的 start/stop 接口                      │    │
│  │  - 聚合统计信息                                    │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

```
外部模块（通过事件总线）
    ↓
    ├─ Collector 发布 RAW_FRAME_DATA 事件
    │  └─ VideoFrameDTO(device_id, frame_id, rgb_frame, depth_frame)
    │
    └─ DataProcessor 发布 PROCESSED_DATA 事件
       └─ DeviceProcessedDataDTO(device_id, frame_id, coords, bbox, ...)
    ↓
RenderPacketPackager（订阅事件，配对数据）
    ↓
内部队列（按设备ID分组，线程安全）
    packet_queue: Dict[str, OverflowQueue[RenderPacket]]
    ↓
DisplayRenderer（渲染显示）
    ↓
OpenCV 窗口（每个设备独立窗口）
```

### 模块职责

| 模块 | 职责 | 线程 |
|------|------|------|
| **DisplayManager** | 协调子模块，提供统一接口 | 主线程 |
| **RenderPacketPackager** | 数据适配，配对，队列管理 | 独立线程 |
| **DisplayRenderer** | 图形渲染，窗口管理 | 独立线程 |

---


## 组件和接口

### 1. DisplayManager（主控制器）

**职责**：
- 创建和管理 RenderPacketPackager 和 DisplayRenderer 两个子模块
- 提供统一的 start/stop 接口
- 聚合统计信息
- 处理配置验证

**类定义**：
```python
class DisplayManager:
    """显示模块主控制器"""
    
    def __init__(
        self,
        *,
        config: DisplayConfigDTO,
        devices_list: List[str],
        event_bus: Optional[EventBus] = None,
    ) -> None:
        """初始化显示管理器
        
        Args:
            config: 显示配置对象
            devices_list: 设备ID列表
            event_bus: 事件总线实例（可选）
        """
        
    def start(self) -> bool:
        """启动显示模块
        
        Returns:
            bool: 是否成功启动
        """
        
    def stop(self, timeout: float = 5.0) -> bool:
        """停止显示模块
        
        Args:
            timeout: 等待超时时间（秒）
            
        Returns:
            bool: 是否成功停止
        """
        
    def get_stats(self) -> dict:
        """获取统计信息
        
        Returns:
            dict: 包含两个子模块的统计信息
        """
        
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
```

**初始化流程**：
1. 验证配置有效性（`config.validate()`）
2. 创建 RenderPacketPackager 实例
3. 创建 DisplayRenderer 实例
4. 传递配置和依赖

**启动流程**：
1. 启动 RenderPacketPackager（订阅事件，启动工作线程）
2. 启动 DisplayRenderer（启动渲染线程）
3. 记录启动日志

**停止流程**：
1. 停止 DisplayRenderer（关闭窗口，停止线程）
2. 停止 RenderPacketPackager（取消订阅，停止线程）
3. 输出统计信息

---

### 2. RenderPacketPackager（适配器子模块）

**职责**：
- 订阅外部事件（RAW_FRAME_DATA 和 PROCESSED_DATA）
- 配对视频帧和检测数据（按 device_id + frame_id）
- 转换为内部统一格式（RenderPacket）
- 维护按设备ID分组的内部队列
- 提供缓存机制（处理队列为空的情况）

**类定义**：
```python
class RenderPacketPackager:
    """渲染包打包器（适配器）"""
    
    def __init__(
        self,
        *,
        queue_maxsize: int = 8,
        timeout_sec: float = 0.2,
        devices_list: List[str] = [],
        cache_max_age_sec: float = 1.0,
    ) -> None:
        """初始化打包器
        
        Args:
            queue_maxsize: 队列最大长度
            timeout_sec: 配对超时时间（秒）
            devices_list: 设备ID列表
            cache_max_age_sec: 缓存最大年龄（秒）
        """
        
    def start(self) -> None:
        """启动打包线程"""
        
    def stop(self) -> None:
        """停止打包线程"""
        
    def get_packets(self, timeout: float = 0.01) -> Dict[str, RenderPacket]:
        """获取所有设备的渲染包
        
        策略：
        - 尝试获取新帧（timeout）
        - 如果队列为空，使用缓存帧（仅当未过期时）
        - 获取到新帧时，更新缓存和时间戳
        
        Returns:
            Dict[str, RenderPacket]: 设备ID到渲染包的映射
        """
        
    def get_packet_by_mxid(
        self,
        mx_id: str,
        timeout: float = 0.01
    ) -> Optional[RenderPacket]:
        """获取单个设备的渲染包
        
        Args:
            mx_id: 设备ID
            timeout: 超时时间（秒）
            
        Returns:
            Optional[RenderPacket]: 渲染包，如果队列为空则返回 None
        """
        
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息（调试接口）"""
```

**数据结构**：
```python
# 内部队列（按设备ID分组）
packet_queue: Dict[str, OverflowQueue[RenderPacket]]

# 缓存（最新的渲染包）
_latest_packets: Dict[str, RenderPacket]

# 缓存时间戳
_packet_timestamps: Dict[str, float]

# 配对缓冲区
_buffer: Dict[Tuple[str, int], _PartialMatch]
```

**配对逻辑**：
1. 接收外部事件（RAW_FRAME_DATA 或 PROCESSED_DATA）
2. 提取关键信息（device_id, frame_id）
3. 查找缓冲区中的半配对数据
4. 如果找到匹配，创建 RenderPacket 并放入队列
5. 如果未找到，创建半配对数据并放入缓冲区
6. 定期清理超时的半配对数据

**缓存机制**：
- 每次成功获取新帧时，更新缓存和时间戳
- 队列为空时，检查缓存是否过期
- 未过期的缓存帧可以继续使用
- 过期的缓存帧会被清理

---


### 3. DisplayRenderer（渲染器子模块）

**职责**：
- 从 RenderPacketPackager 获取渲染包
- 创建和管理 OpenCV 窗口（支持多设备）
- 绘制检测框、标签、坐标等叠加信息
- 处理用户输入（键盘事件）
- 计算和显示 FPS

**类定义**：
```python
class DisplayRenderer:
    """显示渲染器"""
    
    def __init__(
        self,
        *,
        config: DisplayConfigDTO,
        packager: RenderPacketPackager,
        devices_list: List[str],
    ) -> None:
        """初始化渲染器
        
        Args:
            config: 显示配置对象
            packager: 渲染包打包器实例
            devices_list: 设备ID列表
        """
        
    def start(self) -> bool:
        """启动渲染线程
        
        Returns:
            bool: 是否成功启动
        """
        
    def stop(self, timeout: float = 5.0) -> bool:
        """停止渲染线程
        
        Args:
            timeout: 等待超时时间（秒）
            
        Returns:
            bool: 是否成功停止
        """
        
    def get_stats(self) -> dict:
        """获取渲染统计信息
        
        Returns:
            dict: 包含渲染帧数、FPS等信息
        """
        
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
```

**主循环逻辑**（MVP）：
```python
def _run_main_loop(self) -> None:
    """主循环方法（在独立线程中运行）"""
    while not self._stop_event.is_set():
        try:
            # 1. 获取所有设备的渲染包
            packets = self._packager.get_packets(timeout=0.1)
            
            # 2. 为每个设备渲染
            for device_id, packet in packets.items():
                # 2.1 获取或创建窗口
                window_name = self._get_or_create_window(device_id, packet)
                
                # 2.2 提取视频帧
                frame = packet.video_frame.rgb_frame.copy()
                
                # 2.3 绘制检测框（MVP：简单绿色框）
                self._draw_detection_boxes(frame, packet.processed_detections)
                
                # 2.4 显示图像
                cv2.imshow(window_name, frame)
            
            # 3. 处理键盘事件
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self._stop_event.set()
                break
                
        except Exception as e:
            logger.error(f"渲染循环异常: {e}", exc_info=True)
            
    # 清理窗口
    cv2.destroyAllWindows()
```

**绘制方法**（MVP）：
```python
def _draw_detection_boxes(
    self,
    frame: np.ndarray,
    processed_data: DeviceProcessedDataDTO
) -> None:
    """绘制检测框（MVP版本）
    
    Args:
        frame: 视频帧（会被直接修改）
        processed_data: 处理后的检测数据
    """
    # 检查是否有检测结果
    if processed_data.coords.shape[0] == 0:
        return  # 空检测帧，不绘制
    
    # 提取边界框
    bboxes = processed_data.bbox
    
    # 绘制每个检测框
    for bbox in bboxes:
        xmin, ymin, xmax, ymax = bbox
        # 固定颜色：绿色
        color = (0, 255, 0)
        # 固定粗细：2像素
        thickness = 2
        cv2.rectangle(
            frame,
            (int(xmin), int(ymin)),
            (int(xmax), int(ymax)),
            color,
            thickness
        )
```

**窗口管理**（MVP）：
```python
def _get_or_create_window(
    self,
    device_id: str,
    packet: RenderPacket
) -> str:
    """获取或创建窗口
    
    Args:
        device_id: 设备ID
        packet: 渲染包（用于获取设备别名）
        
    Returns:
        str: 窗口名称
    """
    if device_id not in self._windows:
        # 创建窗口名称
        device_alias = packet.processed_detections.device_alias
        window_name = f"{device_alias or device_id} - Display"
        
        # 创建窗口
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        # 设置窗口大小
        if self._config.window_width and self._config.window_height:
            cv2.resizeWindow(
                window_name,
                self._config.window_width,
                self._config.window_height
            )
        
        # 记录窗口
        self._windows[device_id] = window_name
        
    return self._windows[device_id]
```

---

### 4. RenderPacket（内部数据格式）

**定义**：
```python
@dataclass(frozen=True)
class RenderPacket(TransportDTO):
    """单设备渲染数据包"""
    video_frame: VideoFrameDTO  # 视频帧数据
    processed_detections: DeviceProcessedDataDTO  # 处理后的检测数据（必需字段）
    
    def _validate_data(self) -> List[str]:
        """渲染数据包验证"""
        errors = []
        
        # 验证视频帧数据
        errors.extend(self.video_frame._validate_data())
        
        # 验证处理后的检测数据
        errors.extend(self.processed_detections._validate_data())
        
        # 验证帧id和mxid是否一致
        if self.video_frame.device_id != self.processed_detections.device_id:
            errors.append(f"视频帧数据和处理后的检测数据设备ID不一致")
        if self.video_frame.frame_id != self.processed_detections.frame_id:
            errors.append(f"视频帧数据和处理后的检测数据帧ID不一致")
            
        return errors
```

**设计理由**：
- **必需字段**：`processed_detections` 不允许为 `None`，确保渲染包完整性
- **配对保证**：通过验证 device_id 和 frame_id 确保数据一致性
- **支持空检测帧**：`processed_detections` 可以包含空数组（coords.shape[0] == 0）

---


## 数据模型

### 输入数据

**VideoFrameDTO**（来自 Collector）：
```python
@dataclass(frozen=True)
class VideoFrameDTO(TransportDTO):
    device_id: str  # 设备ID
    frame_id: int  # 帧ID
    rgb_frame: np.ndarray  # RGB图像，形状 (H, W, 3)，dtype=uint8
    depth_frame: Optional[np.ndarray] = None  # 深度图，形状 (H, W)，dtype=uint16
```

**DeviceProcessedDataDTO**（来自 DataProcessor）：
```python
@dataclass(frozen=True)
class DeviceProcessedDataDTO(TransportDTO):
    device_id: str  # 设备ID
    frame_id: int  # 帧ID
    labels: np.ndarray  # 标签数组，形状 (N,)，dtype=int32
    bbox: np.ndarray  # 边界框数组，形状 (N, 4)，dtype=float32
    coords: np.ndarray  # 坐标数组，形状 (N, 3)，dtype=float32
    confidence: np.ndarray  # 置信度数组，形状 (N,)，dtype=float32
    state_label: List[DetectionStatusLabel]  # 状态标签列表
    device_alias: Optional[str] = None  # 设备别名
```

### 内部数据

**RenderPacket**（内部统一格式）：
```python
@dataclass(frozen=True)
class RenderPacket(TransportDTO):
    video_frame: VideoFrameDTO
    processed_detections: DeviceProcessedDataDTO
```

### 空检测帧示例

```python
# 空检测帧的 DeviceProcessedDataDTO
DeviceProcessedDataDTO(
    device_id="18443010D116441200",
    frame_id=42,
    device_alias="left_camera",
    coords=np.empty((0, 3), dtype=np.float32),  # 空数组
    bbox=np.empty((0, 4), dtype=np.float32),
    confidence=np.empty((0,), dtype=np.float32),
    labels=np.empty((0,), dtype=np.int32),
    state_label=[],  # 空列表
)

# 对应的 RenderPacket
RenderPacket(
    video_frame=VideoFrameDTO(...),  # 正常的视频帧
    processed_detections=DeviceProcessedDataDTO(...)  # 包含空数组
)
```

### 配置数据

**DisplayConfigDTO**：
```python
@dataclass(frozen=True)
class DisplayConfigDTO(BaseConfigDTO):
    # 显示开关
    enable_display: bool = True
    
    # 窗口配置（MVP）
    window_width: int = 1280
    window_height: int = 720
    
    # 渲染参数（MVP）
    target_fps: int = 20
    
    # 叠加信息（P1）
    show_detection_boxes: bool = True
    show_labels: bool = True
    show_confidence: bool = True
    show_coordinates: bool = True
    show_fps: bool = True
    show_device_info: bool = True
    
    # 深度图显示（P1）
    depth_colormap: str = "JET"
    depth_alpha: float = 0.6
    normalize_depth: bool = True
    
    # 检测框样式（P1）
    bbox_thickness: int = 2
    bbox_color_by_label: bool = True
    text_scale: float = 0.6
    
    # 窗口管理（P1）
    default_display_mode: str = "combined"
    enable_fullscreen: bool = False
    window_position_x: int = 0
    window_position_y: int = 0
```

---

## 正确性属性

*属性是一种特征或行为，应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的正式陈述。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*

### 属性 1：RenderPacketPackager 正确配对数据

*对于任何*设备ID和帧ID，当 RenderPacketPackager 接收到对应的 VideoFrameDTO 和 DeviceProcessedDataDTO 时，应该创建一个有效的 RenderPacket，其中 device_id 和 frame_id 一致。

**验证：需求 1.4, 1.5, 1.6**

### 属性 2：RenderPacketPackager 支持多设备

*对于任何*设备列表，RenderPacketPackager 应该为每个设备维护独立的队列，并且不同设备的数据不会相互干扰。

**验证：需求 1.5, 16.1**

### 属性 3：DisplayRenderer 正确显示视频帧

*对于任何*有效的 RenderPacket，DisplayRenderer 应该能够提取 RGB 帧并在窗口中显示，不崩溃。

**验证：需求 2.1, 2.2, 2.3**

### 属性 4：DisplayRenderer 正确绘制检测框

*对于任何*包含非空检测数据的 RenderPacket，DisplayRenderer 应该在视频帧上绘制对应数量的检测框。

**验证：需求 3.1, 3.2**

### 属性 5：DisplayRenderer 正确处理空检测帧

*对于任何*包含空检测数据的 RenderPacket（coords.shape[0] == 0），DisplayRenderer 应该仅显示视频帧，不绘制任何检测框，不崩溃。

**验证：需求 3.5, 3.6, 15.1, 15.2**

### 属性 6：DisplayRenderer 支持多设备窗口

*对于任何*设备列表，DisplayRenderer 应该为每个设备创建独立的窗口，并且窗口名称包含设备别名或设备ID。

**验证：需求 2.7, 16.2, 16.6**

### 属性 7：缓存机制正确工作

*对于任何*设备，当队列为空且缓存未过期时，`get_packets()` 应该返回缓存帧；当缓存过期时，应该清理缓存并返回空字典。

**验证：需求 1.9, 16.4**

### 属性 8：配置验证正确

*对于任何*无效的 DisplayConfigDTO（例如 window_width < 320），DisplayManager 应该在初始化时抛出 ValueError。

**验证：需求 4.6**

---


## 错误处理

### 1. RenderPacketPackager 错误处理

**场景 1：配对超时**
- **处理**：通过 `_clean_buffer()` 方法定期清理超时的半配对数据
- **统计**：记录丢弃数量（`_stats["drops"]`）
- **日志**：不记录（避免日志开销）

**场景 2：重复数据**
- **处理**：抛出 ValueError，记录错误日志
- **影响**：该帧数据被丢弃，不影响后续处理

**场景 3：缓存帧过期**
- **处理**：自动清理过期缓存
- **日志**：DEBUG 级别记录

**场景 4：队列溢出**
- **处理**：OverflowQueue 自动丢弃最旧的数据
- **统计**：通过 `get_drop_count()` 查询

### 2. DisplayRenderer 错误处理

**场景 1：渲染包数据无效**
- **处理**：记录错误日志，跳过该帧，继续循环
- **代码**：
```python
try:
    self._draw_detection_boxes(frame, packet.processed_detections)
except Exception as e:
    logger.error(f"绘制检测框失败: {e}", exc_info=True)
    # 继续显示视频帧，不中断
```

**场景 2：OpenCV 操作失败**
- **处理**：记录错误日志，继续运行
- **代码**：
```python
try:
    cv2.imshow(window_name, frame)
except Exception as e:
    logger.error(f"显示图像失败: {e}", exc_info=True)
```

**场景 3：队列获取超时**
- **处理**：继续循环，不退出
- **代码**：
```python
packets = self._packager.get_packets(timeout=0.1)
if not packets:
    continue  # 队列为空，继续等待
```

**场景 4：窗口创建失败**
- **处理**：记录错误日志，跳过该设备
- **代码**：
```python
try:
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
except Exception as e:
    logger.error(f"创建窗口失败: {e}", exc_info=True)
    return None
```

### 3. DisplayManager 错误处理

**场景 1：配置无效**
- **处理**：在初始化时抛出 ValueError
- **代码**：
```python
errors = config.validate()
if errors:
    raise ValueError(f"配置无效: {errors}")
```

**场景 2：子模块启动失败**
- **处理**：记录错误日志，停止已启动的子模块
- **代码**：
```python
try:
    self._packager.start()
    self._renderer.start()
except Exception as e:
    logger.error(f"启动失败: {e}", exc_info=True)
    self.stop()  # 清理已启动的子模块
    raise
```

**场景 3：停止超时**
- **处理**：记录警告日志，强制退出
- **代码**：
```python
if not self._renderer.stop(timeout=timeout):
    logger.warning("DisplayRenderer 停止超时")
```

---

## 测试策略

### 单元测试

**RenderPacketPackager 测试**：
```python
def test_packager_pairs_data_correctly():
    """测试打包器正确配对数据"""
    # 创建 VideoFrameDTO 和 DeviceProcessedDataDTO
    # 发布事件
    # 验证生成的 RenderPacket
    pass

def test_packager_handles_empty_detection_frame():
    """测试打包器正确处理空检测帧"""
    # 创建包含空数组的 DeviceProcessedDataDTO
    # 验证配对成功
    pass

def test_packager_supports_multiple_devices():
    """测试打包器支持多设备"""
    # 创建多个设备的数据
    # 验证每个设备有独立队列
    pass

def test_packager_cache_mechanism():
    """测试缓存机制"""
    # 获取新帧，验证缓存更新
    # 队列为空时，验证返回缓存帧
    # 缓存过期后，验证清理
    pass
```

**DisplayRenderer 测试**：
```python
def test_renderer_displays_video_frame():
    """测试渲染器显示视频帧"""
    # 模拟 RenderPacket
    # 验证窗口创建
    # 验证图像显示
    pass

def test_renderer_draws_detection_boxes():
    """测试渲染器绘制检测框"""
    # 创建包含检测数据的 RenderPacket
    # 验证检测框绘制
    pass

def test_renderer_handles_empty_detection_frame():
    """测试渲染器处理空检测帧"""
    # 创建包含空数组的 RenderPacket
    # 验证不崩溃，仅显示视频帧
    pass

def test_renderer_supports_multiple_devices():
    """测试渲染器支持多设备"""
    # 创建多个设备的 RenderPacket
    # 验证每个设备有独立窗口
    pass
```

**DisplayManager 测试**：
```python
def test_manager_validates_config():
    """测试管理器验证配置"""
    # 创建无效配置
    # 验证抛出 ValueError
    pass

def test_manager_starts_and_stops_correctly():
    """测试管理器启动和停止"""
    # 启动管理器
    # 验证子模块启动
    # 停止管理器
    # 验证子模块停止
    pass

def test_manager_aggregates_stats():
    """测试管理器聚合统计信息"""
    # 获取统计信息
    # 验证包含两个子模块的数据
    pass
```

### 集成测试

**完整数据流测试**：
```python
def test_end_to_end_data_flow():
    """测试完整数据流"""
    # 1. 模拟 Collector 发布 RAW_FRAME_DATA
    # 2. 模拟 DataProcessor 发布 PROCESSED_DATA
    # 3. 验证 RenderPacketPackager 配对成功
    # 4. 验证 DisplayRenderer 显示成功
    pass
```

**混合场景测试**：
```python
def test_mixed_empty_and_non_empty_frames():
    """测试空帧和非空帧混合场景"""
    # 交替发送空帧和非空帧
    # 验证系统稳定性
    pass
```

**多设备测试**：
```python
def test_multiple_devices_display():
    """测试多设备显示"""
    # 同时发送多个设备的数据
    # 验证每个设备独立显示
    pass
```

### 性能测试

**渲染性能测试**：
```python
def test_rendering_performance():
    """测试渲染性能"""
    # 发送连续帧
    # 测量 FPS
    # 验证满足 target_fps 要求
    pass
```

**内存占用测试**：
```python
def test_memory_usage():
    """测试内存占用"""
    # 长时间运行
    # 监控内存占用
    # 验证无内存泄漏
    pass
```

---


## 实施计划

### MVP 实现（优先级 P0）

#### 阶段 1：DisplayRenderer 基础实现

**文件**：`oak_vision_system/modules/display_modules/display_renderer.py`

**任务**：
1. 创建 DisplayRenderer 类
2. 实现初始化方法（接收配置和 RenderPacketPackager）
3. 实现主循环方法（`_run_main_loop`）
4. 实现基础窗口显示（`_get_or_create_window`）
5. 实现基础检测框绘制（`_draw_detection_boxes`）
6. 实现 start/stop 方法
7. 实现错误处理

**关键代码**：
```python
class DisplayRenderer:
    def __init__(
        self,
        *,
        config: DisplayConfigDTO,
        packager: RenderPacketPackager,
        devices_list: List[str],
    ):
        self._config = config
        self._packager = packager
        self._devices_list = devices_list
        self._windows: Dict[str, str] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running_lock = threading.RLock()
        self._is_running = False
        self.logger = logging.getLogger(__name__)
    
    def start(self) -> bool:
        """启动渲染线程"""
        with self._running_lock:
            if self._is_running:
                return False
            
            self._stop_event.clear()
            self._is_running = True
            
            self._thread = threading.Thread(
                target=self._run_main_loop,
                name="DisplayRenderer",
                daemon=False
            )
            self._thread.start()
            return True
    
    def _run_main_loop(self) -> None:
        """主循环方法"""
        while not self._stop_event.is_set():
            try:
                # 获取渲染包
                packets = self._packager.get_packets(timeout=0.1)
                
                # 渲染每个设备
                for device_id, packet in packets.items():
                    self._render_packet(device_id, packet)
                
                # 处理键盘事件
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self._stop_event.set()
                    break
                    
            except Exception as e:
                self.logger.error(f"渲染循环异常: {e}", exc_info=True)
        
        # 清理窗口
        cv2.destroyAllWindows()
```

**测试**：
- 单元测试：验证窗口创建
- 单元测试：验证检测框绘制
- 单元测试：验证空检测帧处理

---

#### 阶段 2：DisplayManager 实现

**文件**：`oak_vision_system/modules/display_modules/display_manager.py`

**任务**：
1. 创建 DisplayManager 类
2. 实现初始化方法（创建子模块）
3. 实现 start/stop 方法（协调子模块）
4. 实现 get_stats 方法（聚合统计信息）
5. 实现配置验证

**关键代码**：
```python
class DisplayManager:
    def __init__(
        self,
        *,
        config: DisplayConfigDTO,
        devices_list: List[str],
        event_bus: Optional[EventBus] = None,
    ):
        # 验证配置
        errors = config.validate()
        if errors:
            raise ValueError(f"配置无效: {errors}")
        
        self._config = config
        self._devices_list = devices_list
        self._event_bus = event_bus or get_event_bus()
        
        # 创建 RenderPacketPackager
        self._packager = RenderPacketPackager(
            queue_maxsize=8,
            timeout_sec=0.2,
            devices_list=devices_list,
            cache_max_age_sec=1.0,
        )
        
        # 创建 DisplayRenderer
        self._renderer = DisplayRenderer(
            config=config,
            packager=self._packager,
            devices_list=devices_list,
        )
        
        self.logger = logging.getLogger(__name__)
    
    def start(self) -> bool:
        """启动显示模块"""
        try:
            # 启动打包器
            self._packager.start()
            
            # 启动渲染器
            if self._config.enable_display:
                self._renderer.start()
            
            self.logger.info("DisplayManager 已启动")
            return True
            
        except Exception as e:
            self.logger.error(f"启动失败: {e}", exc_info=True)
            self.stop()
            raise
    
    def stop(self, timeout: float = 5.0) -> bool:
        """停止显示模块"""
        success = True
        
        # 停止渲染器
        if not self._renderer.stop(timeout=timeout):
            self.logger.warning("DisplayRenderer 停止超时")
            success = False
        
        # 停止打包器
        self._packager.stop()
        
        self.logger.info("DisplayManager 已停止")
        return success
```

**测试**：
- 单元测试：验证配置验证
- 单元测试：验证启动/停止
- 集成测试：验证完整数据流

---

#### 阶段 3：集成测试和调试

**任务**：
1. 端到端测试（Collector → DataProcessor → Display）
2. 多设备测试
3. 空检测帧测试
4. 性能测试
5. 错误处理测试

**验收标准**：
- ✅ 能够启动显示模块
- ✅ 能够显示视频帧
- ✅ 能够绘制绿色检测框
- ✅ 按 'q' 键能够退出
- ✅ 不崩溃，能够处理空帧
- ✅ 支持多设备显示
- ✅ 缓存机制工作正常

---

### 完整功能实现（优先级 P1）

#### 阶段 4：完整的叠加信息

**任务**：
1. 实现标签显示（`_draw_labels`）
2. 实现置信度显示
3. 实现 3D 坐标显示（`_draw_coordinates`）
4. 实现 FPS 显示（`_draw_fps`）
5. 实现设备信息显示（`_draw_device_info`）

**估计时间**：30 分钟

---

#### 阶段 5：按标签着色

**任务**：
1. 定义颜色映射表
2. 修改 `_draw_detection_boxes` 方法
3. 根据 label_id 选择颜色

**估计时间**：15 分钟

---

#### 阶段 6：多种显示模式

**任务**：
1. 实现深度图可视化（`_visualize_depth`）
2. 实现 RGB 模式
3. 实现 Depth 模式
4. 实现 Combined 模式
5. 实现 Side-by-Side 模式
6. 实现模式切换（'m' 键）

**估计时间**：30 分钟

---

#### 阶段 7：窗口管理

**任务**：
1. 实现窗口位置设置
2. 实现全屏模式
3. 实现全屏切换（'f' 键）

**估计时间**：15 分钟

---

#### 阶段 8：性能优化

**任务**：
1. 实现帧率限制
2. 优化图像复制
3. 监控队列使用率

**估计时间**：20 分钟

---

#### 阶段 9：统计和监控

**任务**：
1. 实现 FPS 计算
2. 实现统计信息收集
3. 实现 get_stats 方法

**估计时间**：15 分钟

---

#### 阶段 10：优雅关闭

**任务**：
1. 实现超时机制
2. 实现资源清理
3. 输出统计信息

**估计时间**：15 分钟

---

## 性能考虑

### 渲染性能

**目标**：
- 渲染帧率：20-30 FPS
- 渲染延迟：< 50ms
- CPU 占用：< 30%

**优化策略**：
1. **避免不必要的复制**：直接在原始数组上绘制
2. **使用 NumPy 数组视图**：避免数据复制
3. **帧率限制**：根据 target_fps 主动休眠
4. **队列溢出策略**：自动丢弃旧数据

### 内存占用

**目标**：
- 队列内存：< 100MB（8 帧 × 10 设备 × 1MB/帧）
- 缓存内存：< 10MB（1 帧 × 10 设备 × 1MB/帧）
- 总内存：< 200MB

**优化策略**：
1. **限制队列大小**：maxsize=8
2. **缓存过期清理**：cache_max_age_sec=1.0
3. **及时释放资源**：使用 `cv2.destroyAllWindows()`

### 线程开销

**线程数量**：
- RenderPacketPackager：1 个工作线程
- DisplayRenderer：1 个渲染线程
- 总计：2 个线程

**线程同步**：
- 使用 `threading.Event` 作为停止信号
- 使用 `threading.RLock` 保护共享状态
- 使用 `OverflowQueue` 实现线程安全的队列

---


## 向后兼容性

### API 兼容性

**新增模块**：
- DisplayManager
- DisplayRenderer

**现有模块**：
- RenderPacketPackager（已实现，无需修改）

**配置兼容性**：
- DisplayConfigDTO（已存在，无需修改）

### 事件兼容性

**订阅的事件**：
- RAW_FRAME_DATA（已存在）
- PROCESSED_DATA（已存在）

**发布的事件**：
- 无（Display 模块不发布事件）

### 数据兼容性

**输入数据**：
- VideoFrameDTO（已存在）
- DeviceProcessedDataDTO（已存在）

**内部数据**：
- RenderPacket（已存在）

---

## 风险和缓解

### 风险 1：OpenCV 窗口在某些环境下无法创建

**描述**：无头环境（无显示器）或 SSH 连接时，OpenCV 窗口可能无法创建

**缓解**：
- 添加环境检测（检查 DISPLAY 环境变量）
- 提供无头模式（保存图像到文件）
- 文档说明环境要求

**代码示例**：
```python
import os

if not os.environ.get('DISPLAY'):
    logger.warning("无显示环境，禁用显示功能")
    self._config.enable_display = False
```

---

### 风险 2：高帧率下 CPU 占用过高

**描述**：高帧率（> 30 FPS）时，渲染可能占用过多 CPU

**缓解**：
- 实现帧率限制（target_fps）
- 使用 OverflowQueue 自动丢弃旧数据
- 优化绘制代码（避免不必要的复制）

**代码示例**：
```python
# 计算帧间隔
frame_interval = 1.0 / self._config.target_fps

# 主循环中控制帧率
last_time = time.time()
while not self._stop_event.is_set():
    # 渲染逻辑...
    
    # 帧率限制
    elapsed = time.time() - last_time
    if elapsed < frame_interval:
        time.sleep(frame_interval - elapsed)
    last_time = time.time()
```

---

### 风险 3：多设备显示时窗口管理复杂

**描述**：多个设备同时显示时，窗口位置可能重叠

**缓解**：
- MVP 阶段使用默认窗口位置
- P1 阶段实现自动窗口布局
- 允许用户手动调整窗口位置

**代码示例**：
```python
# 自动计算窗口位置（P1）
def _calculate_window_position(self, device_index: int) -> Tuple[int, int]:
    """计算窗口位置（避免重叠）"""
    x = (device_index % 2) * self._config.window_width
    y = (device_index // 2) * self._config.window_height
    return x, y
```

---

### 风险 4：适配器和渲染器之间的队列可能成为瓶颈

**描述**：高帧率或多设备场景下，队列可能成为性能瓶颈

**缓解**：
- 使用 OverflowQueue 自动丢弃旧数据
- 监控队列使用率
- 调整队列大小（maxsize）
- 优化配对逻辑

**监控代码**：
```python
def get_stats(self) -> dict:
    """获取统计信息"""
    queue_stats = {}
    for device_id, queue in self._packager.packet_queue.items():
        queue_stats[device_id] = {
            "size": queue.qsize(),
            "maxsize": queue.maxsize,
            "usage_ratio": queue.get_usage_ratio(),
            "drop_count": queue.get_drop_count(),
        }
    return {"queue_stats": queue_stats}
```

---

## 总结

本设计文档描述了显示模块的完整设计，包括：

1. **架构设计**：采用适配器模式，清晰的职责划分
2. **组件设计**：DisplayManager、RenderPacketPackager、DisplayRenderer
3. **数据模型**：RenderPacket、VideoFrameDTO、DeviceProcessedDataDTO
4. **正确性属性**：8 个核心属性，覆盖所有关键功能
5. **错误处理**：完善的异常处理和日志记录
6. **测试策略**：单元测试、集成测试、性能测试
7. **实施计划**：分阶段实施，MVP 优先
8. **性能考虑**：渲染性能、内存占用、线程开销
9. **风险缓解**：4 个主要风险及缓解措施

**关键设计决策**：

1. **适配器模式**：RenderPacketPackager 作为数据适配器，将外部异构数据转换为内部统一格式
2. **模块内通信**：适配器和渲染器通过内部队列通信，不使用事件总线
3. **多设备支持**：按设备ID分组的队列和窗口
4. **缓存机制**：处理队列为空的情况，提高用户体验
5. **MVP 优先**：先实现核心功能，验证数据流，再实现完整功能

**下一步**：
- 创建任务文档（tasks.md）
- 开始实现 MVP 功能
- 进行端到端测试

