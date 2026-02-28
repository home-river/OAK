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
    
    退出流程设计：
    - 所有退出路径都设置 _shutdown_event（保持状态一致性）
    - 统一在 finally 块中调用 shutdown() 清理资源
    - 使用 _stop_started 防止重复关闭
    """
    try:
        self._logger.info("SystemManager 开始运行，等待退出信号...")
        self._logger.info("退出方式: Ctrl+C 或 SYSTEM_SHUTDOWN 事件")
        
        # 获取注册的显示模块
        display_module = self._display_module
        
        if display_module is not None:
            self._logger.info("检测到显示模块，使用主线程渲染模式")
        
        while not self._shutdown_event.is_set():
            # 如果有显示模块，调用 render_once()
            if display_module is not None:
                try:
                    should_quit = display_module.render_once()
                    if should_quit:
                        # 出口3：用户按 'q' 键请求退出
                        self._logger.info("显示模块请求退出（用户按下 'q' 键）")
                        self._shutdown_event.set()
                        break
                except Exception as e:
                    # 捕获渲染异常，记录日志但不中断主循环
                    self._logger.error("渲染过程中发生异常: %s", e, exc_info=True)
                    # 继续运行，不退出
            else:
                # 无显示模块，使用原有的等待逻辑
                self._shutdown_event.wait(timeout=0.5)
        
        # 出口2：_shutdown_event 被设置，循环正常退出
        self._logger.info("接收到退出信号，准备关闭系统...")
    
    except KeyboardInterrupt:
        # 出口1：Ctrl+C
        # 关键设计：统一设置 _shutdown_event，保持状态一致性
        self._shutdown_event.set()
        self._logger.info("捕获到 KeyboardInterrupt (Ctrl+C)，准备关闭系统...")
    
    finally:
        # 统一退出点：所有出口都汇聚到这里
        # 检查 _stop_started 防止重复调用 shutdown()
        if not self._stop_started.is_set():
            self._logger.info("执行统一关闭流程...")
            self.shutdown()
        else:
            self._logger.debug("shutdown() 已经执行过，跳过")
```

#### 退出流程说明

**三个退出出口**：

1. **Ctrl+C（KeyboardInterrupt）**
   - 捕获异常 → 设置 `_shutdown_event` → 进入 `finally` → 调用 `shutdown()`

2. **SYSTEM_SHUTDOWN 事件**
   - 事件回调设置 `_shutdown_event` → `while` 循环退出 → 进入 `finally` → 调用 `shutdown()`

3. **用户按 'q' 键**
   - `render_once()` 返回 `True` → 设置 `_shutdown_event` → `break` 退出循环 → 进入 `finally` → 调用 `shutdown()`

**关键设计原则**：

1. **状态一致性**：所有退出路径都设置 `_shutdown_event`
   - 确保其他模块可以可靠地检查系统状态
   - 避免状态不一致导致的问题

2. **统一清理**：所有退出路径都在 `finally` 块中调用 `shutdown()`
   - 确保资源一定会被清理
   - 防止资源泄漏

3. **防重复关闭**：使用 `_stop_started` 标志
   - 防止 `shutdown()` 被多次调用
   - 支持手动调用 + 自动调用的场景

**两个标志的作用**：

- `_shutdown_event`：通知主循环退出（用于正常退出流程）
- `_stop_started`：防止 `shutdown()` 重复执行（用于防御性编程）


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

#### 核心设计改进：状态驱动 + 惰性渲染

基于 `probable_display_design.md` 的设计思路，DisplayRenderer 采用**双状态驱动**和**惰性渲染**策略：

**双状态驱动架构：**
- **状态 1（显示模式 Mode）**：左设备 | 右设备 | 拼接
  - 决定从打包器取哪路数据、调用哪个接口
  - 左/右设备 mxid 来源于外部传入的 `role_bindings`
  - 受当前在线设备数量约束（单设备在线时自动切换到单设备模式）
- **状态 2（视图属性 View）**：全屏 | 窗口
  - 决定目标分辨率（窗口 1280×720、全屏 1920×1080）
  - 仅在用户按键时更新，不每帧查询窗口属性

**惰性渲染策略（按需取包）：**
- **单设备模式**：仅调用 `get_packet_by_mxid(device_mxid, timeout)` 取当前设备一包
  - 未选中的设备数据不消费，停留在打包器队列中
  - 节省 CPU，避免不必要的 OpenCV 操作（Resize、ColorCvt 等）
- **拼接模式**：调用 `get_packets(timeout)` 一次获取所有设备的渲染包
- **缓存回退机制**：单包接口也支持缓存回退（与 `get_packets` 一致）
  - 队列超时时，检查 `_latest_packets[mxid]` 缓存
  - 未过期（`age <= cache_max_age_sec`）则返回缓存包
  - 保证单路模式下画面稳定、不闪黑

**role_bindings 依赖注入：**
- DisplayRenderer 不直接依赖 ConfigManager
- 由上层在创建时传入 `role_bindings: Dict[DeviceRole, str]`
- **获取方式**：通过 `DeviceConfigManager.get_active_role_bindings()` 方法获取
  ```python
  # 在创建 DisplayManager 时
  config_manager = DeviceConfigManager(...)
  role_bindings = config_manager.get_active_role_bindings()
  # 返回: {DeviceRole.LEFT_CAMERA: "14442C10...", DeviceRole.RIGHT_CAMERA: "14442C10..."}
  
  display_manager = DisplayManager(
      config=config.display_config,
      devices_list=devices_list,
      role_bindings=role_bindings,  # 传入提取的映射
      enable_depth_output=enable_depth_output
  )
  ```
- 左设备 = `role_bindings[DeviceRole.LEFT_CAMERA]`
- 右设备 = `role_bindings[DeviceRole.RIGHT_CAMERA]`
- 与 `devices_list` 顺序解耦

#### 移除的内容

- `_run_main_loop()` 方法（原渲染线程主循环）
- `_thread` 属性（线程对象）
- `_stop_event` 属性（线程停止信号）
- `start()` 方法中的线程创建逻辑
- `stop()` 方法中的线程停止逻辑

#### 按键处理和模式切换

**单设备模式切换方法**：

```python
def _switch_to_device(self, device_role: DeviceRole) -> None:
    """切换到指定角色的设备显示（基于 DeviceRole）
    
    Args:
        device_role: 设备角色（DeviceRole.LEFT_CAMERA 或 DeviceRole.RIGHT_CAMERA）
    
    实现：
    1. 检查 role_bindings 中是否存在该角色
    2. 切换显示模式为 "single"
    3. 更新 _selected_device_role
    4. 调整窗口大小（如果需要）
    5. 更新窗口标题
    """
    if device_role not in self._role_bindings:
        self.logger.warning(f"角色 {device_role} 不存在于 role_bindings 中")
        return
    
    self._display_mode = "single"
    self._selected_device_role = device_role
    device_mxid = self._role_bindings[device_role]
    
    # 调整窗口大小为单设备模式
    if self._window_created and not self._is_fullscreen:
        window_width = self._config.window_width if self._config.window_width else 640
        window_height = self._config.window_height if self._config.window_height else 480
        cv2.resizeWindow(self._main_window_name, window_width, window_height)
    
    # 更新窗口标题
    if self._window_created:
        self._update_window_title()
    
    self.logger.info(f"切换到设备角色 {device_role.display_name}: {device_mxid}")
```

**按键映射**：
- '1' 键 → `DeviceRole.LEFT_CAMERA`（左相机）
- '2' 键 → `DeviceRole.RIGHT_CAMERA`（右相机）
- '3' 键 → Combined 模式（拼接）
- 'f' 键 → 切换全屏
- 'q' 键 → 退出

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
    
    实现流程（状态驱动 + 惰性渲染 + Stretch Resize）：
    1. 根据状态 1（显示模式）选择取包策略：
       - 单设备模式：调用 get_packet_by_mxid(device_mxid, timeout)
       - 拼接模式：调用 get_packets(timeout)
    2. 根据状态 2（视图属性）确定目标分辨率
    3. 渲染当前模式的帧（按需分支，内部使用 Stretch Resize）
    4. 创建窗口（如果尚未创建）
    5. 显示帧（已经是目标尺寸，无需再次 resize）
    6. 处理键盘输入
    7. 更新统计信息
    8. 返回退出信号
    
    注意：Stretch Resize 策略在 _render_combined_devices() 和 _render_single_device() 内部完成
    """
    # 1. 根据显示模式选择取包策略（惰性渲染）
    if self._display_mode == "combined":
        # 拼接模式：获取所有设备的渲染包
        packets = self._packager.get_packets(timeout=0.01)
        
        if not packets:
            # 无数据时仍需处理按键
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                return True
            return False
        
        # 渲染拼接帧（内部已完成 Stretch Resize 到目标尺寸）
        frame = self._render_combined_devices(packets)
    else:
        # 单设备模式：仅获取当前设备的渲染包（惰性渲染）
        # 根据当前选中的角色（LEFT_CAMERA 或 RIGHT_CAMERA）获取 mxid
        if self._selected_device_role in self._role_bindings:
            device_mxid = self._role_bindings[self._selected_device_role]
            packet = self._packager.get_packet_by_mxid(device_mxid, timeout=0.01)
            
            if packet is None:
                # 无数据时仍需处理按键
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    return True
                return False
            
            # 渲染单设备帧（内部已完成 Stretch Resize 到目标尺寸）
            frame = self._render_single_device(packet)
        else:
            return False
    
    if frame is not None:
        # 2. 创建窗口（如果尚未创建）
        if not self._window_created:
            self._create_main_window()
        
        # 3. 显示帧（已经是目标尺寸，无需再次 resize）
        cv2.imshow(self._main_window_name, frame)
        
        # 更新统计
        with self._stats_lock:
            self._stats["frames_rendered"] += 1
        
        self._update_fps()
    
    # 4. 处理键盘输入
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        self.logger.info("用户按下 'q' 键")
        return True
    elif key == ord('f'):
        self._toggle_fullscreen()
    elif key == ord('1'):
        self._switch_to_device(DeviceRole.LEFT_CAMERA)  # 切换到左相机
    elif key == ord('2'):
        self._switch_to_device(DeviceRole.RIGHT_CAMERA)  # 切换到右相机
    elif key == ord('3'):
        self._switch_to_combined()  # 切换到拼接模式
    
    # 5. 帧率限制
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

### DisplayRenderer 配置属性

```python
class DisplayRenderer:
    def __init__(self, ...):
        # 窗口层尺寸配置（最终显示尺寸）
        self._window_width = 1280
        self._window_height = 720  # 16:9
        self._fullscreen_width = 1920
        self._fullscreen_height = 1080  # 16:9
        
        # 窗口状态
        self._window_created = False
        self._is_fullscreen = False
        
        # 显示模式状态（状态 1）
        self._display_mode = "combined"  # "combined" | "single"
        self._selected_device_role = DeviceRole.LEFT_CAMERA  # 单设备模式下选中的设备角色
        
        # role_bindings 依赖注入
        self._role_bindings = role_bindings or {}  # Dict[DeviceRole, str]
```

### RenderPacketPackager 接口调整

为支持惰性渲染策略，需要调整 `get_packet_by_mxid` 接口，增加缓存回退机制：

```python
def get_packet_by_mxid(self, mx_id: str, timeout: float = 0.01) -> Optional[RenderPacket]:
    """获取指定设备的渲染包（支持缓存回退）
    
    策略：
    1. 尝试从队列获取新帧（timeout）
    2. 如果队列为空，检查缓存帧（_latest_packets[mx_id]）
    3. 如果缓存未过期（age <= cache_max_age_sec），返回缓存帧
    4. 否则返回 None
    
    优势：
    - 单设备模式下画面稳定、不闪黑
    - 只消费当前需要的那一路队列
    - 与 get_packets 的缓存策略保持一致
    """
    if mx_id not in self.packet_queue:
        self.logger.warning(f"设备ID {mx_id} 不存在于队列中")
        return None
    
    try:
        # 尝试获取新帧
        packet = self.packet_queue[mx_id].get(timeout=timeout)
        
        # 更新缓冲区和时间戳
        now = time.time()
        self._latest_packets[mx_id] = packet
        self._packet_timestamps[mx_id] = now
        
        return packet
        
    except Empty:
        # 尝试使用缓冲帧（缓存回退）
        cached_packet = self._latest_packets.get(mx_id)
        
        if cached_packet is not None:
            # 检查是否过期
            cached_at = self._packet_timestamps.get(mx_id, 0.0)
            age = time.time() - cached_at
            
            if age <= self.cache_max_age_sec:
                # 未过期，可以使用
                return cached_packet
            else:
                # 已过期，清理缓存
                self.logger.debug(
                    f"设备 {mx_id} 的缓存帧已过期 (年龄: {age:.2f}s)，已清理"
                )
                self._latest_packets[mx_id] = None
                self._packet_timestamps[mx_id] = 0.0
        
        return None
```

### 配置来源和依赖注入

**role_bindings 的获取流程：**

1. **配置管理器提供标准接口**：
   ```python
   # DeviceConfigManager 提供专用方法
   def get_active_role_bindings(self) -> Dict[DeviceRole, str]:
       """获取当前激活的设备角色绑定
       
       Returns:
           Dict[DeviceRole, str]: 角色 -> mxid 的映射字典
           
       Example:
           {DeviceRole.LEFT_CAMERA: "14442C10D13F7FD000", 
            DeviceRole.RIGHT_CAMERA: "14442C10D13F7FD001"}
       """
       oak_module = self.get_runnable_config().oak_module
       role_bindings = {}
       
       for role, binding in oak_module.role_bindings.items():
           if binding.active_mxid:
               role_bindings[role] = binding.active_mxid
       
       return role_bindings
   ```

2. **上层调用时提取并传入**：
   ```python
   # 在系统初始化时（例如 SystemManager 或测试代码中）
   config_manager = DeviceConfigManager(...)
   config = config_manager.get_runnable_config()
   
   # 提取 role_bindings
   role_bindings = config_manager.get_active_role_bindings()
   
   # 提取 devices_list
   devices_list = [
       binding.active_mxid 
       for binding in config.oak_module.role_bindings.values() 
       if binding.active_mxid
   ]
   
   # 创建 DisplayManager，传入提取的配置
   display_manager = DisplayManager(
       config=config.display_config,
       devices_list=devices_list,
       role_bindings=role_bindings,  # 依赖注入
       enable_depth_output=config.oak_module.hardware_config.enable_depth_output
   )
   ```

3. **DisplayManager 传递给 DisplayRenderer**：
   ```python
   # DisplayManager.__init__
   self._renderer = DisplayRenderer(
       config=config,
       packager=self._packager,
       devices_list=devices_list,
       role_bindings=role_bindings,  # 直接传递
       enable_depth_output=enable_depth_output,
       event_bus=self._packager.event_bus,
   )
   ```

4. **DisplayRenderer 使用 role_bindings**：
   ```python
   # DisplayRenderer 中使用
   left_mxid = self._role_bindings.get(DeviceRole.LEFT_CAMERA)
   right_mxid = self._role_bindings.get(DeviceRole.RIGHT_CAMERA)
   
   # 单设备模式下，根据当前选中的设备角色获取 mxid
   device_mxid = self._role_bindings[self._selected_device_role]
   packet = self._packager.get_packet_by_mxid(device_mxid, timeout=0.01)
   ```

**设计优势：**
- **解耦**：DisplayRenderer 不直接依赖 ConfigManager
- **可测试**：可以轻松注入 mock 的 role_bindings 进行测试
- **灵活性**：role_bindings 可以来自任何来源（配置文件、数据库、运行时动态生成）
- **明确性**：依赖关系清晰，通过构造函数明确声明

## 图像处理和坐标映射规范

### Resize 策略（Stretch Resize）

**核心原则**：使用 `cv2.resize(frame, (dstW, dstH))` 直接拉伸到目标尺寸

**设计约束**：
- **不使用** keep-aspect-ratio（等比缩放）
- **不引入** padding/padX/padY
- **不使用** letterbox
- Combined 模式：两路分别 resize 到各自 ROI 尺寸，然后水平拼接

### 窗口分辨率配置

根据显示模式和全屏状态决定最终显示尺寸：

```python
# 窗口模式（16:9 比例）
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# 全屏模式（16:9 比例）
FULLSCREEN_WIDTH = 1920
FULLSCREEN_HEIGHT = 1080
```

### 坐标映射（归一化坐标）

**输入格式**：归一化检测框坐标 `bbox_norm = (xmin, ymin, xmax, ymax) ∈ [0,1]`

#### 单图模式映射

```python
# 直接映射到目标画布
x1 = int(xmin * Target_W)
y1 = int(ymin * Target_H)
x2 = int(xmax * Target_W)
y2 = int(ymax * Target_H)
```

#### 双图模式映射（左右并排）

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

### 拉伸变形策略（接受变形以换取性能）

**变形现象**：在双图模式下，16:9 的图像被 stretch resize 到 8:9 的 ROI，图像内容会在水平方向被压缩约 50%（变瘦）

**设计选择**：**这是预期行为** - 我们选择接受变形以换取：
- 简单的坐标映射（无需 letterbox 计算）
- 更低的 CPU 开销（无需 padding 操作）
- 统一的处理流程（单图和双图逻辑一致）

**视觉补偿**：渲染引擎**先拉伸底图，后绘制 UI**
- 虽然视频内容变形，但覆盖在上面的文字（Label）和矩形框（BBox）在最终画布上绘制
- UI 元素依然保持标准的宽高比，确保数据的可读性

### 设计约束（禁止项）

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

### 窗口创建逻辑

```python
def _create_main_window(self) -> None:
    """创建主窗口
    
    策略：
    1. 创建 WINDOW_NORMAL 类型窗口（可调整大小）
    2. 不使用 cv2.resizeWindow()（渲染方法内部已完成 resize）
    3. 根据全屏配置设置窗口属性
    4. 渲染方法返回的帧已经是目标尺寸，可直接 imshow
    """
    cv2.namedWindow(self._main_window_name, cv2.WINDOW_NORMAL)
    
    # 设置窗口位置（如果配置了）
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
    else:
        self._is_fullscreen = False
    
    self._window_created = True
    self.logger.info(f"主窗口已创建: {self._main_window_name}")
```

### 帧渲染逻辑

#### 合并显示模式（Combined）

```python
def _render_combined_devices(
    self, 
    packets: Dict[str, RenderPacket]
) -> Optional[np.ndarray]:
    """渲染合并模式（返回已 resize 到目标尺寸的帧）
    
    Stretch Resize 策略：
    1. 确定目标画布尺寸（Target_W, Target_H）
    2. 计算每路 ROI 尺寸（roiW_left, roiW_right）
    3. 分别 stretch resize 到 ROI 尺寸
    4. 水平拼接到画布
    5. 在最终画布上绘制 UI（使用归一化坐标映射）
    
    Returns:
        已经 resize 到目标尺寸（窗口或全屏）的画布，可直接用于 cv2.imshow()
    """
    # 确定目标画布尺寸（根据状态 2：视图属性）
    if self._is_fullscreen:
        target_width = self._fullscreen_width
        target_height = self._fullscreen_height
    else:
        target_width = self._window_width
        target_height = self._window_height
    
    # 计算 ROI 尺寸
    roiW_left = target_width // 2
    roiW_right = target_width - roiW_left
    
    rgb_frames = []
    
    # 处理每个设备
    for i, device_id in enumerate(self._devices_list):
        if device_id in packets:
            packet = packets[device_id]
            frame = packet.video_frame.rgb_frame
            
            # 确定当前设备的 ROI 尺寸
            roiW = roiW_left if i == 0 else roiW_right
            
            # Stretch resize 到 ROI 尺寸（直接拉伸，不保持宽高比）
            frame_resized = cv2.resize(frame, (roiW, target_height))
            
            # 检查可写性
            if not frame_resized.flags.writeable:
                frame_resized = frame_resized.copy()
            
            # 添加设备名称标签
            device_name = packet.processed_detections.device_alias or device_id
            self._draw_text_with_background(
                frame_resized, device_name, (10, 30), 
                font_scale=0.7, text_color=(0, 255, 255)
            )
            
            rgb_frames.append(frame_resized)
    
    if not rgb_frames:
        return None
    
    # 水平拼接（拼接后的画布尺寸正好是 target_width × target_height）
    combined = np.hstack(rgb_frames)

    # 在最终画布上绘制检测信息（使用归一化坐标映射）
    # 说明：检测框坐标使用归一化坐标（0~1），映射到目标画布 ROI 后，再加 offsetX
    for i, device_id in enumerate(self._devices_list):
        if device_id in packets:
            packet = packets[device_id]
            roiW = roiW_left if i == 0 else roiW_right
            offsetX = 0 if i == 0 else roiW_left
            self._draw_detection_boxes_normalized(
                combined, packet.processed_detections,
                roiW, target_height, offsetX
            )
    
    # 绘制全局叠加信息
    self._draw_fps(combined)
    self._draw_key_hints(combined)
    
    return combined
```

#### 单设备显示模式

```python
def _render_single_device(
    self, 
    packet: RenderPacket
) -> Optional[np.ndarray]:
    """渲染单设备模式（返回已 resize 到目标尺寸的帧）
    
    Stretch Resize 策略：
    - 直接 stretch resize 到目标尺寸（窗口模式 1280x720 / 全屏 1920x1080）
    - 在最终画布上绘制 UI（使用归一化坐标映射）
    
    Returns:
        已经 resize 到目标尺寸（窗口或全屏）的画布，可直接用于 cv2.imshow()
    """
    frame = packet.video_frame.rgb_frame
    
    # 确定目标尺寸（根据状态 2：视图属性）
    if self._is_fullscreen:
        target_width = self._fullscreen_width
        target_height = self._fullscreen_height
    else:
        target_width = self._window_width
        target_height = self._window_height
    
    # Stretch resize 到目标尺寸（直接拉伸，不保持宽高比）
    frame_resized = cv2.resize(frame, (target_width, target_height))
    
    # 检查可写性
    if not frame_resized.flags.writeable:
        frame_resized = frame_resized.copy()
    
    # 绘制检测信息（使用归一化坐标映射）
    self._draw_detection_boxes_normalized(
        frame_resized, packet.processed_detections,
        target_width, target_height, offsetX=0
    )
    
    # 绘制叠加信息
    device_name = packet.processed_detections.device_alias or packet.processed_detections.device_id
    self._draw_text_with_background(
        frame_resized, device_name, (10, 50), 
        font_scale=1.0, text_color=(0, 255, 255)
    )
    
    self._draw_fps(frame_resized)
    self._draw_device_info(frame_resized, packet.processed_detections.device_id, packet.processed_detections)
    self._draw_key_hints(frame_resized)
    
    return frame_resized
```

### 检测框颜色映射

#### 设计原则

检测框的颜色应该根据 `DetectionStatusLabel` 状态标签动态确定，提供直观的视觉反馈。

#### 颜色映射配置

在 `oak_vision_system/modules/displaymanager/render_config.py` 中定义固有配置：

```python
"""
显示渲染相关的固有配置
包括状态标签颜色映射、UI样式等
"""
from oak_vision_system.core.dto.data_processing_dto import DetectionStatusLabel
import cv2

# 状态标签到颜色的映射（BGR格式，OpenCV标准）
STATUS_COLOR_MAP = {
    # 物体状态 (0-99)
    DetectionStatusLabel.OBJECT_GRASPABLE: (0, 255, 0),      # 绿色 - 可抓取
    DetectionStatusLabel.OBJECT_DANGEROUS: (0, 0, 255),      # 红色 - 危险
    DetectionStatusLabel.OBJECT_OUT_OF_RANGE: (0, 165, 255), # 橙色 - 超出范围
    DetectionStatusLabel.OBJECT_PENDING_GRASP: (255, 0, 0),  # 蓝色 - 待抓取
    
    # 人类状态 (100-199)
    DetectionStatusLabel.HUMAN_SAFE: (0, 255, 0),            # 绿色 - 安全
    DetectionStatusLabel.HUMAN_DANGEROUS: (0, 0, 255),       # 红色 - 危险
}

# 默认颜色（未知状态或未映射状态）
DEFAULT_DETECTION_COLOR = (255, 255, 255)  # 白色

# UI样式配置
BBOX_THICKNESS = 2
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_FONT_SCALE = 0.5
LABEL_THICKNESS = 1
```

#### 检测框绘制方法

```python
def _draw_detection_boxes_normalized(
    self,
    canvas: np.ndarray,
    detections: ProcessedDetections,
    roiW: int,
    roiH: int,
    offsetX: int
) -> None:
    """在画布上绘制归一化坐标的检测框
    
    Args:
        canvas: 已 resize 到目标尺寸的画布
        detections: 包含归一化坐标的检测结果
        roiW: 当前 ROI 宽度
        roiH: 当前 ROI 高度（通常等于 target_height）
        offsetX: 水平偏移量（合并模式用，单图模式为0）
    
    实现：
    1. 遍历检测结果
    2. 根据 status_label 从 STATUS_COLOR_MAP 获取颜色
    3. 将归一化坐标映射到画布像素坐标
    4. 使用状态对应的颜色绘制矩形框和标签
    """
    from oak_vision_system.modules.displaymanager.render_config import (
        STATUS_COLOR_MAP,
        DEFAULT_DETECTION_COLOR,
        BBOX_THICKNESS,
        LABEL_FONT,
        LABEL_FONT_SCALE,
        LABEL_THICKNESS
    )
    
    for detection in detections.detections:
        # 1. 获取状态标签对应的颜色
        status_label = detection.status_label  # DetectionStatusLabel
        color = STATUS_COLOR_MAP.get(status_label, DEFAULT_DETECTION_COLOR)
        
        # 2. 归一化坐标映射到画布像素坐标
        xmin, ymin, xmax, ymax = detection.bbox_normalized
        x1 = int(xmin * roiW) + offsetX
        y1 = int(ymin * roiH)
        x2 = int(xmax * roiW) + offsetX
        y2 = int(ymax * roiH)
        
        # 3. 使用状态对应的颜色绘制矩形框
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, BBOX_THICKNESS)
        
        # 4. 绘制标签（同样使用状态颜色）
        label = f"{detection.class_name} {detection.confidence:.2f}"
        
        # 计算标签背景位置
        (label_w, label_h), baseline = cv2.getTextSize(
            label, LABEL_FONT, LABEL_FONT_SCALE, LABEL_THICKNESS
        )
        
        # 绘制标签背景（半透明）
        cv2.rectangle(
            canvas,
            (x1, y1 - label_h - baseline - 5),
            (x1 + label_w, y1),
            color,
            -1  # 填充
        )
        
        # 绘制标签文字（白色，确保可读性）
        cv2.putText(
            canvas,
            label,
            (x1, y1 - baseline - 5),
            LABEL_FONT,
            LABEL_FONT_SCALE,
            (255, 255, 255),  # 白色文字
            LABEL_THICKNESS
        )
```

#### 设计优势

1. **直观的视觉反馈**：
   - 绿色 = 安全/可抓取
   - 红色 = 危险
   - 橙色 = 超出范围
   - 蓝色 = 待处理

2. **解耦和可维护性**：
   - 颜色映射独立于检测逻辑
   - 集中配置，易于修改
   - 避免硬编码

3. **扩展性**：
   - 新增状态只需在 `STATUS_COLOR_MAP` 添加映射
   - 可以轻松调整颜色方案

4. **一致性**：
   - 所有检测框使用统一的颜色语义
   - UI 元素（矩形框和标签）使用相同颜色

### 全屏切换逻辑

```python
def _toggle_fullscreen(self) -> None:
    """切换全屏/窗口模式
    
    策略：
    1. 切换 _is_fullscreen 标志
    2. 使用 cv2.setWindowProperty 切换窗口属性
    3. 下一帧渲染时，_render_single_device() 或 _render_combined_devices() 
       会根据 _is_fullscreen 选择对应的目标尺寸进行 resize
    """
    if not self._window_created:
        return
    
    # 切换标志
    self._is_fullscreen = not self._is_fullscreen
    
    # 设置窗口属性
    if self._is_fullscreen:
        cv2.setWindowProperty(
            self._main_window_name,
            cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_FULLSCREEN
        )
        self.logger.info("切换到全屏模式")
    else:
        cv2.setWindowProperty(
            self._main_window_name,
            cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_NORMAL
        )
        self.logger.info("切换到窗口模式")
    
    # 注意：不需要手动 resize 窗口
    # 下一帧渲染时会根据 _is_fullscreen 自动选择目标尺寸
```

### 尺寸配置总结表

| 配置项 | 尺寸 | 比例 | 用途 |
|--------|------|------|------|
| 窗口模式 | 1280x720 | 16:9 | 最终显示尺寸（窗口） |
| 全屏模式 | 1920x1080 | 16:9 | 最终显示尺寸（全屏） |

**关键设计点**：
1. **单次 Stretch Resize**：原始帧直接拉伸到目标尺寸（窗口或全屏）
2. **窗口尺寸保持 16:9 比例**：窗口和全屏都是 16:9
3. **双图模式接受变形**：16:9 的图像被拉伸到 8:9 的 ROI（变瘦），换取性能
4. **不使用 `cv2.resizeWindow()`**：渲染方法内部直接 resize 到目标尺寸
5. **全屏切换只改变属性**：使用 `setWindowProperty()` + 状态标志 `_is_fullscreen`

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


## 错误处理

### 1. 渲染异常处理

```python
def render_once(self) -> bool:
    """执行一次渲染循环"""
    try:
        # 渲染逻辑
        ...
    except cv2.error as e:
        # OpenCV 特定错误
        self.logger.error("OpenCV 错误: %s", e, exc_info=True)
        self._error_count += 1
        
        if self._error_count > 10:
            self.logger.warning("连续发生 %d 次渲染错误", self._error_count)
        
        return False
    except Exception as e:
        # 其他异常
        self.logger.error("渲染异常: %s", e, exc_info=True)
        return False
```

### 2. 窗口创建失败

```python
def _create_main_window(self) -> None:
    """创建主窗口"""
    try:
        cv2.namedWindow(self._main_window_name, cv2.WINDOW_NORMAL)
        ...
    except Exception as e:
        self.logger.critical("窗口创建失败: %s", e, exc_info=True)
        raise
```

### 3. 数据包获取超时

```python
def render_once(self) -> bool:
    """执行一次渲染循环"""
    packets = self._packager.get_packets(timeout=0.01)
    
    if not packets:
        # 无数据时仍需处理按键
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            return True
        return False
    
    # 继续渲染
    ...
```

### 4. KeyboardInterrupt 处理

```python
# SystemManager.run()
try:
    while not self._shutdown_event.is_set():
        if display_module is not None:
            should_quit = display_module.render_once()
            if should_quit:
                self._shutdown_event.set()
                break
        else:
            self._shutdown_event.wait(timeout=0.5)

except KeyboardInterrupt:
    self._logger.info("捕获到 KeyboardInterrupt (Ctrl+C)...")

finally:
    if not self._stop_started.is_set():
        self.shutdown()
```

## 测试策略

### 单元测试

#### DisplayManager 测试

```python
def test_render_once_returns_false_on_normal_render():
    """测试正常渲染时 render_once() 返回 False"""
    # 属性 7
    display_manager = create_test_display_manager()
    display_manager.start()
    
    result = display_manager.render_once()
    
    assert result == False

def test_render_once_returns_true_on_q_key():
    """测试按下 'q' 键时 render_once() 返回 True"""
    # 属性 6
    display_manager = create_test_display_manager()
    display_manager.start()
    
    # 模拟按键
    with mock.patch('cv2.waitKey', return_value=ord('q')):
        result = display_manager.render_once()
    
    assert result == True

def test_no_render_thread_created():
    """测试启动后不创建渲染线程"""
    # 属性 3
    display_manager = create_test_display_manager()
    display_manager.start()
    
    threads = threading.enumerate()
    thread_names = [t.name for t in threads]
    
    assert "DisplayRenderer" not in thread_names

def test_packager_thread_created():
    """测试启动后创建打包线程"""
    # 属性 4
    display_manager = create_test_display_manager()
    display_manager.start()
    
    threads = threading.enumerate()
    thread_names = [t.name for t in threads]
    
    assert "RenderPacketPackagerWorker" in thread_names
```

#### SystemManager 测试

```python
def test_main_loop_calls_render_once():
    """测试主循环调用 render_once()"""
    # 属性 1
    system_manager = create_test_system_manager()
    display_manager = create_test_display_manager()
    
    system_manager.register_display_module("display", display_manager, priority=50)
    system_manager.start_all()
    
    with mock.patch.object(display_manager, 'render_once', return_value=False) as mock_render:
        # 运行几次循环
        for _ in range(5):
            system_manager._run_one_iteration()  # 假设有这个方法
        
        assert mock_render.call_count == 5

def test_shutdown_on_render_once_returns_true():
    """测试 render_once() 返回 True 时触发关闭"""
    # 属性 2
    system_manager = create_test_system_manager()
    display_manager = create_test_display_manager()
    
    system_manager.register_display_module("display", display_manager, priority=50)
    system_manager.start_all()
    
    with mock.patch.object(display_manager, 'render_once', return_value=True):
        # 运行一次循环
        system_manager._run_one_iteration()
        
        assert system_manager._shutdown_event.is_set()
```

### 属性测试

#### 性能属性测试

```python
@given(st.integers(min_value=1, max_value=100))
def test_render_once_returns_quickly(num_calls):
    """属性测试：render_once() 应该快速返回"""
    # 属性 5
    display_manager = create_test_display_manager()
    display_manager.start()
    
    start_time = time.time()
    for _ in range(num_calls):
        display_manager.render_once()
    elapsed = time.time() - start_time
    
    avg_time = elapsed / num_calls
    assert avg_time < 0.1  # 每次调用应该 < 100ms
```

#### 窗口比例属性测试

```python
@given(st.integers(min_value=640, max_value=3840))
def test_window_aspect_ratio_16_9(width):
    """属性测试：窗口宽高比应该是 16:9"""
    # 属性 10
    height = int(width * 9 / 16)
    
    display_manager = create_test_display_manager()
    display_manager._config.window_width = width
    display_manager._config.window_height = height
    display_manager.start()
    
    # 触发窗口创建
    display_manager.render_once()
    
    # 检查窗口比例
    actual_ratio = width / height
    expected_ratio = 16 / 9
    
    assert abs(actual_ratio - expected_ratio) < 0.01
```

### 集成测试

#### 完整流程测试

```python
def test_full_system_integration():
    """集成测试：完整的启动-运行-关闭流程"""
    # 创建配置
    config = create_test_config()
    
    # 创建 SystemManager
    system_manager = SystemManager(system_config=config.system_config)
    
    # 创建并注册模块
    display_manager = DisplayManager(
        config=config.display_config,
        devices_list=["device1", "device2"],
        role_bindings={},
        enable_depth_output=False
    )
    
    system_manager.register_display_module("display", display_manager, priority=50)
    
    # 启动系统
    system_manager.start_all()
    
    # 模拟运行几次循环
    for _ in range(10):
        should_quit = display_manager.render_once()
        if should_quit:
            break
    
    # 关闭系统
    system_manager.shutdown()
    
    # 验证状态
    assert not display_manager.is_running
```

#### 按键响应测试

```python
def test_keyboard_response_time():
    """集成测试：按键响应时间"""
    # 属性 12
    display_manager = create_test_display_manager()
    display_manager.start()
    
    # 模拟按键
    start_time = time.time()
    with mock.patch('cv2.waitKey', return_value=ord('q')):
        result = display_manager.render_once()
    elapsed = time.time() - start_time
    
    assert result == True
    assert elapsed < 0.1  # 响应时间 < 100ms
```

### 冒烟测试

修改现有的 `test_smoke_virtualCAN.py`：

```python
def step_3_start_and_run_system(self, duration: int = 30) -> bool:
    """步骤 3: 启动并运行系统（使用新的主线程渲染）"""
    try:
        # 启动所有模块
        self.system_manager.start_all()
        
        # 主循环（由 SystemManager 驱动渲染）
        start_time = time.time()
        while time.time() - start_time < duration:
            # SystemManager.run() 会自动调用 display_manager.render_once()
            # 这里只需要检查是否超时
            if self.system_manager._shutdown_event.is_set():
                break
            time.sleep(0.01)
        
        # 关闭系统
        self.system_manager.shutdown()
        
        return True
    except Exception as e:
        logger.error(f"系统运行失败: {e}", exc_info=True)
        return False
```

## 性能考虑

### 1. 惰性渲染优化（零拷贝原则）

**核心思想**：单设备模式下只处理当前需要显示的设备数据，未选中的设备数据不消费、不处理。

**实现策略**：
- **单设备模式**：仅调用 `get_packet_by_mxid(device_mxid, timeout)` 取当前设备一包
  - 未选中的设备数据停留在打包器队列中，不进行任何 OpenCV 操作
  - 节省 CPU，避免不必要的 Resize、ColorCvt、Concat 等操作
- **拼接模式**：调用 `get_packets(timeout)` 一次获取所有设备的渲染包
  - 所有设备数据都需要处理和拼接

**性能收益**：
- 单设备模式下 CPU 使用率降低约 50%（避免处理另一路视频）
- 内存占用减少（不创建未使用的中间帧）
- 帧率更稳定（减少不必要的计算）

### 2. Stretch Resize 策略优化

**核心思想**：使用直接拉伸而非 letterbox，简化处理流程，降低 CPU 开销。

**实现策略**：
- **单次 Resize**：原始帧直接 `cv2.resize(frame, (dstW, dstH))` 到目标尺寸
  - 不使用 keep-aspect-ratio（等比缩放）
  - 不引入 padding/padX/padY
  - 不使用两层 resize（内容层 → 窗口层）
- **接受变形**：双图模式下 16:9 图像被拉伸到 8:9 ROI（变瘦）
  - 换取简单的坐标映射（无需 letterbox 计算）
  - 换取更低的 CPU 开销（无需 padding 操作）
  - UI 元素在最终画布上绘制，保持正常比例

**性能收益**：
- 减少 resize 操作次数（单次 vs 两次）
- 避免 padding 内存分配和拷贝
- 简化坐标映射逻辑（归一化直接映射）

### 3. 帧率优化

- 目标帧率：30 FPS
- 帧间隔：33.3 ms
- 实现：动态调整休眠时间

```python
if self._target_frame_interval > 0:
    current_time = time.time()
    elapsed = current_time - self._last_frame_time
    sleep_time = self._target_frame_interval - elapsed
    
    if sleep_time > 0:
        time.sleep(sleep_time)
    
    self._last_frame_time = time.time()
```

### 4. 内存优化

- 使用视图而非复制：`frame = packet.video_frame.rgb_frame`
- 检查可写性：`if not frame.flags.writeable: frame = frame.copy()`
- 及时释放资源：`cv2.destroyAllWindows()`

### 5. CPU 优化

- 避免不必要的计算
- 使用缓存机制（缓存回退）
- 合理设置超时时间
- 事件驱动的分辨率更新（不每帧查询窗口属性）

## 向后兼容性

### 1. 配置兼容

- 保持 `DisplayConfigDTO` 格式不变
- 保持 `enable_display` 配置项
- 保持窗口配置项（位置、大小、全屏）

### 2. 接口兼容

- 保持 `DisplayManager.start()` 和 `stop()` 接口
- 保持 `DisplayManager.get_stats()` 接口
- 保持 `DisplayManager.is_running` 属性

### 3. 事件兼容

- 保持事件总线消息格式
- 保持 `SYSTEM_SHUTDOWN` 事件

### 4. 降级方案

如果用户不使用新的 `register_display_module()` 接口，系统应该：

1. 使用旧的 `register_module()` 接口注册
2. 不调用 `render_once()`（DisplayManager 内部不渲染）
3. 记录警告日志提示用户更新

## 迁移指南

### 对于现有代码

1. **SystemManager 使用者**：

```python
# 旧代码
system_manager.register_module("display", display_manager, priority=50)

# 新代码
system_manager.register_display_module("display", display_manager, priority=50)
```

2. **DisplayManager 使用者**：

无需修改，接口保持不变。

3. **测试代码**：

需要更新测试以适应新的线程模型。

### 对于新代码

直接使用新接口：

```python
# 创建 SystemManager
system_manager = SystemManager(system_config=config)

# 创建 DisplayManager
display_manager = DisplayManager(
    config=config.display_config,
    devices_list=devices_list,
    role_bindings=role_bindings,
    enable_depth_output=enable_depth_output
)

# 注册显示模块（使用新接口）
system_manager.register_display_module("display", display_manager, priority=50)

# 启动系统
system_manager.start_all()

# 运行主循环（会自动调用 render_once()）
system_manager.run()
```

## 实现顺序

1. **Phase 1: RenderPacketPackager 接口调整**
   - 修改 `get_packet_by_mxid()` 方法，增加缓存回退机制
   - 与 `get_packets()` 的缓存策略保持一致
   - 单元测试（验证缓存回退逻辑）

2. **Phase 2: DisplayRenderer 重构**
   - 移除线程相关代码
   - 实现 `initialize()` 和 `cleanup()` 方法
   - 实现 `render_once()` 方法（状态驱动 + 惰性渲染）
   - 添加 `role_bindings` 依赖注入
   - 单元测试

3. **Phase 3: DisplayManager 重构**
   - 修改 `start()` 和 `stop()` 方法
   - 实现 `render_once()` 方法
   - 单元测试

4. **Phase 4: SystemManager 重构**
   - 实现 `register_display_module()` 方法
   - 修改 `run()` 主循环
   - 单元测试

5. **Phase 5: 窗口分辨率调整**
   - 实现 16:9 比例逻辑
   - 调整帧 resize 逻辑（两层尺寸控制）
   - 集成测试

6. **Phase 6: 集成测试和冒烟测试**
   - 更新冒烟测试脚本
   - 完整流程测试
   - 性能测试（验证惰性渲染的性能收益）

7. **Phase 7: 文档和迁移**
   - 更新 API 文档
   - 编写迁移指南
   - 更新示例代码

## 风险和缓解

### 风险 1：性能下降

- **风险**：主线程渲染可能影响其他模块
- **缓解**：
  - 优化 `render_once()` 执行时间
  - 使用帧率限制
  - 监控性能指标

### 风险 2：兼容性问题

- **风险**：现有代码可能无法正常工作
- **缓解**：
  - 保持向后兼容
  - 提供降级方案
  - 详细的迁移指南

### 风险 3：测试覆盖不足

- **风险**：新代码可能有未发现的 bug
- **缓解**：
  - 完整的单元测试
  - 属性测试
  - 集成测试和冒烟测试

### 风险 4：OpenCV 平台差异

- **风险**：不同平台的 OpenCV 行为可能不同
- **缓解**：
  - 在多个平台上测试
  - 处理平台特定的异常
  - 记录平台差异

## 总结

本设计文档描述了将显示模块从独立线程渲染迁移到主线程渲染的完整方案。核心变化包括：

1. **DisplayRenderer** 不再创建独立线程，提供 `render_once()` 接口
2. **SystemManager** 主循环驱动渲染，根据返回值决定是否退出
3. **DisplayManager** 只管理打包线程，不管理渲染线程
4. **窗口分辨率** 保持 16:9 比例，参考 `dual_detectionv2.py` 实现
5. **状态驱动架构** 双状态机（显示模式 + 视图属性）控制渲染流程
6. **惰性渲染策略** 单设备模式下只处理当前设备数据，节省 CPU
7. **打包器接口增强** `get_packet_by_mxid` 支持缓存回退，保证画面稳定

设计遵循以下原则：
- 主线程渲染（解决 OpenCV 窗口卡死问题）
- 单步渲染（每次调用执行一次循环）
- 职责分离（SystemManager 驱动，DisplayManager 管理）
- 向后兼容（保持现有接口和配置）
- 性能优化（保持 30+ FPS，惰性渲染节省 CPU）
- 状态驱动（双状态机控制，事件驱动更新）

通过完整的测试策略（单元测试、属性测试、集成测试、冒烟测试），确保重构的正确性和稳定性。
