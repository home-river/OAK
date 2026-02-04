# 设计文档：显示模块主线程渲染重构

## 概述

本设计文档描述了将显示模块的渲染逻辑从独立线程迁移到主线程的技术方案。当前实现中，`DisplayRenderer` 在独立线程中运行 OpenCV 渲染循环，这在某些平台（特别是 Windows）上容易导致窗口卡死或无响应。重构后，渲染逻辑将由 `SystemManager` 在主线程中驱动，`DisplayManager` 只负责状态管理和数据打包。

### 核心设计原则

1. **主线程渲染**：所有 OpenCV 窗口操作必须在主线程中执行
2. **单步渲染**：提供 `render_once()` 接口，每次调用执行一次渲染循环
3. **职责分离**：`DisplayManager` 管理打包线程，`SystemManager` 驱动渲染循环
4. **向后兼容**：保持现有接口和配置格式不变
5. **性能优化**：保持 30+ FPS 的渲染性能

## 架构设计

### 当前架构（重构前）

```
SystemManager
    └─> DisplayManager
            ├─> RenderPacketPackager (独立线程)
            │       └─> 订阅事件，打包渲染数据
            └─> DisplayRenderer (独立线程)
                    └─> 渲染循环 + OpenCV 窗口操作
```

### 新架构（重构后）

```
SystemManager (主线程)
    ├─> 主循环驱动
    │   └─> 调用 DisplayManager.render_once()
    └─> DisplayManager
            ├─> RenderPacketPackager (独立线程)
            │       └─> 订阅事件，打包渲染数据
            └─> DisplayRenderer (无线程)
                    └─> 提供单步渲染接口
```

### 关键变化

1. **DisplayRenderer 不再创建独立线程**
2. **SystemManager.run() 主循环调用 render_once()**
3. **render_once() 返回布尔值指示是否退出**
4. **DisplayManager.stop() 只关闭打包线程**

## 组件设计

### 1. SystemManager 主循环重构

#### 新增方法

```python
def register_display_module(
    self, 
    name: str, 
    instance: Any, 
    priority: int
) -> None:
    """注册显示模块（需要主线程渲染）
    
    Args:
        name: 模块名称
        instance: DisplayManager 实例
        priority: 优先级
    """
```

#### 主循环修改

```python
def run(self) -> None:
    """运行系统并阻塞主线程
    
    新增：
    - 检查是否有注册的显示模块
    - 每轮循环调用 display_module.render_once()
    - 根据返回值决定是否触发 SYSTEM_SHUTDOWN
    """
    try:
        self._logger.info("SystemManager 开始运行...")
        
        # 获取注册的显示模块
        display_module = self._display_module
        
        while not self._shutdown_event.is_set():
            # 如果有显示模块，调用 render_once()
            if display_module is not None:
                should_quit = display_module.render_once()
                if should_quit:
                    self._logger.info("显示模块请求退出")
                    self._shutdown_event.set()
                    break
            else:
                # 无显示模块，使用原有的等待逻辑
                self._shutdown_event.wait(timeout=0.5)
        
        self._logger.info("接收到退出信号，准备关闭系统...")
    
    except KeyboardInterrupt:
        self._logger.info("捕获到 KeyboardInterrupt (Ctrl+C)...")
    
    finally:
        if not self._stop_started.is_set():
            self.shutdown()
```


### 2. DisplayManager 重构

#### 修改的方法

```python
def start(self) -> bool:
    """启动显示模块
    
    修改：
    - 只启动 RenderPacketPackager 的打包线程
    - 不启动 DisplayRenderer 的渲染线程
    - 初始化 DisplayRenderer 的状态（创建窗口等）
    """
    with self._running_lock:
        if self._is_running:
            return False
        
        # 启动 RenderPacketPackager
        packager_started = self._packager.start()
        if not packager_started:
            raise RuntimeError("RenderPacketPackager 启动失败")
        
        # 初始化 DisplayRenderer（但不启动线程）
        if self._config.enable_display:
            self._renderer.initialize()  # 新增方法
        
        self._is_running = True
        return True

def stop(self, timeout: float = 5.0) -> bool:
    """停止显示模块
    
    修改：
    - 只停止 RenderPacketPackager 的打包线程
    - 清理 DisplayRenderer 的资源（关闭窗口等）
    """
    with self._running_lock:
        if not self._is_running:
            return True
        
        # 清理 DisplayRenderer 资源
        if self._renderer is not None:
            self._renderer.cleanup()  # 新增方法
        
        # 停止 RenderPacketPackager
        packager_success = self._packager.stop(timeout=timeout)
        
        self._is_running = False
        return packager_success
```

#### 新增方法

```python
def render_once(self) -> bool:
    """执行一次渲染循环（主线程调用）
    
    Returns:
        bool: True 表示请求退出，False 表示继续运行
    
    实现：
    - 检查是否启用显示
    - 调用 DisplayRenderer.render_once()
    - 处理异常并记录日志
    - 返回退出信号
    """
    if not self._config.enable_display:
        return False
    
    if self._renderer is None:
        return False
    
    try:
        return self._renderer.render_once()
    except Exception as e:
        self.logger.error(
            "渲染过程中发生异常: %s", 
            e, 
            exc_info=True
        )
        return False
```

### 3. DisplayRenderer 重构

#### 移除的内容

- `_run_main_loop()` 方法（原渲染线程主循环）
- `_thread` 属性（线程对象）
- `_stop_event` 属性（线程停止信号）
- `start()` 方法中的线程创建逻辑
- `stop()` 方法中的线程停止逻辑

#### 新增方法

```python
def initialize(self) -> None:
    """初始化渲染器（在 start 时调用）
    
    功能：
    - 初始化统计信息
    - 准备窗口创建（但不立即创建）
    - 设置初始状态
    """
    with self._stats_lock:
        self._stats["start_time"] = time.time()
    
    self._window_created = False
    self.logger.info("DisplayRenderer 已初始化")

def cleanup(self) -> None:
    """清理渲染器资源（在 stop 时调用）
    
    功能：
    - 关闭所有 OpenCV 窗口
    - 输出统计信息
    - 清理状态
    """
    cv2.destroyAllWindows()
    
    with self._stats_lock:
        runtime = time.time() - self._stats["start_time"]
        frames = self._stats["frames_rendered"]
        avg_fps = frames / runtime if runtime > 0 else 0
        
        self.logger.info(
            "DisplayRenderer 已清理 - 帧数: %d, 时长: %.1fs, 平均FPS: %.1f",
            frames, runtime, avg_fps
        )

def render_once(self) -> bool:
    """执行一次渲染循环（主线程调用）
    
    Returns:
        bool: True 表示用户按下 'q' 键请求退出，False 表示继续运行
    
    实现流程：
    1. 获取渲染数据包（带超时）
    2. 渲染当前模式的帧
    3. 创建窗口（如果尚未创建）
    4. 显示帧
    5. 处理键盘输入
    6. 更新统计信息
    7. 返回退出信号
    """
    # 1. 获取渲染数据包
    packets = self._packager.get_packets(timeout=0.01)
    
    if not packets:
        # 无数据时仍需处理按键
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            return True
        return False
    
    # 2. 渲染当前模式的帧
    frame = self._render_current_mode(packets)
    
    if frame is not None:
        # 3. 创建窗口（如果尚未创建）
        if not self._window_created:
            self._create_main_window()
        
        # 4. 显示帧
        cv2.imshow(self._main_window_name, frame)
        
        # 更新统计
        with self._stats_lock:
            self._stats["frames_rendered"] += 1
        
        self._update_fps()
    
    # 5. 处理键盘输入
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        self.logger.info("用户按下 'q' 键")
        return True
    elif key == ord('f'):
        self._toggle_fullscreen()
    elif key == ord('1'):
        self._switch_to_device(0)
    elif key == ord('2'):
        self._switch_to_device(1)
    elif key == ord('3'):
        self._switch_to_combined()
    
    # 6. 帧率限制
    if self._target_frame_interval > 0:
        current_time = time.time()
        elapsed = current_time - self._last_frame_time
        sleep_time = self._target_frame_interval - elapsed
        
        if sleep_time > 0:
            time.sleep(sleep_time)
        
        self._last_frame_time = time.time()
    
    return False
```


## 数据模型

### SystemManager 新增属性

```python
class SystemManager:
    def __init__(self, ...):
        # 新增：显示模块引用
        self._display_module: Optional[Any] = None
```

### DisplayRenderer 修改属性

```python
class DisplayRenderer:
    def __init__(self, ...):
        # 移除：线程相关属性
        # self._stop_event = threading.Event()  # 删除
        # self._thread: Optional[threading.Thread] = None  # 删除
        
        # 保留：状态管理
        self._window_created = False
        self._is_fullscreen = False
        self._display_mode = "combined"
        
        # 保留：统计信息
        self._stats = {...}
        self._stats_lock = threading.Lock()
```

## 窗口分辨率设计

### 16:9 比例配置

参考 `dual_detectionv2.py` 的实现，窗口分辨率应保持 16:9 比例：

```python
# 单设备模式（小窗口）
SINGLE_DEVICE_WIDTH = 1280
SINGLE_DEVICE_HEIGHT = 720  # 16:9 比例

# 合并模式（小窗口）
COMBINED_WIDTH = 1280
COMBINED_HEIGHT = 720  # 16:9 比例

# 全屏模式
FULLSCREEN_WIDTH = 1920
FULLSCREEN_HEIGHT = 1080  # 16:9 比例

# 单帧尺寸（用于拼接）
SINGLE_FRAME_WIDTH = 640
SINGLE_FRAME_HEIGHT = 360  # 16:9 比例
```

### 窗口创建逻辑

```python
def _create_main_window(self) -> None:
    """创建主窗口
    
    根据显示模式设置窗口大小：
    - 单设备模式：1280x720
    - 合并模式：1280x720（拼接后的帧会被 resize）
    - 全屏模式：1920x1080
    """
    cv2.namedWindow(self._main_window_name, cv2.WINDOW_NORMAL)
    
    # 设置窗口大小（保持 16:9 比例）
    if self._config.enable_fullscreen:
        window_width = 1920
        window_height = 1080
    else:
        window_width = 1280
        window_height = 720
    
    cv2.resizeWindow(self._main_window_name, window_width, window_height)
    
    # 设置窗口位置
    if self._config.window_position_x or self._config.window_position_y:
        cv2.moveWindow(
            self._main_window_name,
            self._config.window_position_x,
            self._config.window_position_y
        )
    
    # 设置全屏模式
    if self._config.enable_fullscreen:
        cv2.setWindowProperty(
            self._main_window_name,
            cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_FULLSCREEN
        )
        self._is_fullscreen = True
    
    self._window_created = True
```

### 帧调整逻辑

```python
def _render_combined_devices(
    self, 
    packets: Dict[str, RenderPacket]
) -> Optional[np.ndarray]:
    """渲染合并模式
    
    步骤：
    1. 收集所有设备的帧
    2. 将每个帧 resize 到 640x360（16:9）
    3. 水平拼接（1280x360）
    4. Resize 到窗口大小（1280x720）
    """
    rgb_frames = []
    
    for device_id in self._devices_list:
        if device_id in packets:
            packet = packets[device_id]
            frame = packet.video_frame.rgb_frame
            
            # Resize 到单帧尺寸（640x360）
            frame_resized = cv2.resize(frame, (640, 360))
            
            # 绘制检测信息
            self._draw_detection_boxes(frame_resized, packet.processed_detections)
            self._draw_labels(frame_resized, packet.processed_detections)
            self._draw_coordinates(frame_resized, packet.processed_detections)
            
            rgb_frames.append(frame_resized)
    
    if not rgb_frames:
        return None
    
    # 水平拼接（1280x360）
    combined = np.hstack(rgb_frames)
    
    # Resize 到窗口大小（1280x720）
    combined_resized = cv2.resize(combined, (1280, 720))
    
    # 绘制叠加信息
    self._draw_fps(combined_resized)
    self._draw_key_hints(combined_resized)
    
    return combined_resized
```

## 正确性属性

*属性是系统应该满足的特征或行为，它们在所有有效执行中都应该成立。属性是人类可读规范和机器可验证正确性保证之间的桥梁。*

### 属性 1：主线程渲染调用

*对于任意* 运行中的 SystemManager，当主循环执行时，如果注册了显示模块，则每轮循环应该调用一次 `render_once()` 方法

**验证：需求 2.1**

### 属性 2：退出信号传递

*对于任意* DisplayManager 实例，当 `render_once()` 返回 True 时，SystemManager 应该触发 SYSTEM_SHUTDOWN 事件

**验证：需求 2.2**

### 属性 3：无渲染线程创建

*对于任意* DisplayManager 实例，当调用 `start()` 方法后，系统中不应该存在名为 "DisplayRenderer" 的线程

**验证：需求 1.4**

### 属性 4：打包线程独立运行

*对于任意* DisplayManager 实例，当调用 `start()` 方法后，RenderPacketPackager 的打包线程应该被创建并运行

**验证：需求 4.1**

### 属性 5：单步渲染返回控制权

*对于任意* DisplayManager 实例，调用 `render_once()` 方法应该在合理时间内（< 100ms）返回控制权

**验证：需求 1.2**

### 属性 6：按键退出信号

*对于任意* DisplayManager 实例，当模拟用户按下 'q' 键时，`render_once()` 应该返回 True

**验证：需求 1.3, 5.3**

### 属性 7：正常渲染返回 False

*对于任意* DisplayManager 实例，当没有按下 'q' 键且渲染正常时，`render_once()` 应该返回 False

**验证：需求 5.2**

### 属性 8：异常处理不中断

*对于任意* DisplayManager 实例，当渲染过程中发生异常时，`render_once()` 应该捕获异常、记录日志并返回 False

**验证：需求 5.4, 8.1, 8.2**

### 属性 9：禁用显示时立即返回

*对于任意* DisplayManager 实例，当 `enable_display=False` 时，`render_once()` 应该立即返回 False 而不执行渲染

**验证：需求 5.5**

### 属性 10：窗口比例保持 16:9

*对于任意* 创建的窗口，其宽高比应该等于 16:9（误差 < 0.01）

**验证：需求 6.1**

### 属性 11：帧率限制生效

*对于任意* DisplayManager 实例，当设置 `target_fps=30` 时，实际渲染帧率应该在 28-32 FPS 范围内

**验证：需求 10.1**

### 属性 12：按键响应及时

*对于任意* DisplayManager 实例，从按键输入到 `render_once()` 返回的时间应该小于 100ms

**验证：需求 10.2**

### 属性 13：队列溢出不阻塞

*对于任意* DisplayManager 实例，当渲染队列满时，新数据应该丢弃旧帧而不阻塞生产者

**验证：需求 10.4**

### 属性 14：关闭时间限制

*对于任意* DisplayManager 实例，调用 `stop()` 方法应该在 5 秒内完成

**验证：需求 10.5**

### 属性 15：向后兼容性

*对于任意* 使用旧 `register_module()` 接口注册的 DisplayManager，系统应该正常运行

**验证：需求 9.1**

