# 实现计划：显示模块主线程渲染重构

## 概述

本实现计划将显示模块的渲染逻辑从独立线程迁移到主线程，采用单步渲染接口、Stretch Resize 策略、归一化坐标映射和惰性渲染优化。

**当前状态**：所有代码实现已完成（任务 1-7），剩余手动验证测试（任务 7.3）需要用户执行。

## 任务

### 1. 创建渲染配置文件 ✅

- [x] 1.1 创建 render_config.py 配置文件
  - 在 `oak_vision_system/modules/display_modules/` 下创建 `render_config.py`
  - 定义 `STATUS_COLOR_MAP` 字典（DetectionStatusLabel → BGR颜色）
  - 定义 `DEFAULT_DETECTION_COLOR`、`BBOX_THICKNESS`、`LABEL_FONT` 等UI样式常量
  - 添加完整的文档注释说明每个颜色的语义
  - _需求: 12.1, 12.8_

### 2. RenderPacketPackager 接口调整 ✅

- [x] 2.1 修改 get_packet_by_mxid() 方法增加缓存回退机制
  - 在 `RenderPacketPackager` 中修改 `get_packet_by_mxid()` 方法
  - 实现队列超时时检查 `_latest_packets[mxid]` 缓存
  - 实现缓存过期检查（age <= cache_max_age_sec）
  - 缓存未过期时返回缓存帧，已过期时清理缓存并返回 None
  - 与 `get_packets()` 的缓存策略保持一致
  - _需求: 13.1, 13.4, 13.5, 13.6_

- [x] 2.2 编写 get_packet_by_mxid 缓存回退的单元测试
  - 测试队列超时时使用缓存帧
  - 测试缓存过期时清理缓存
  - 测试缓存未过期时返回缓存帧
  - _需求: 13.4, 13.5, 13.6_

### 3. DisplayRenderer 核心重构 ✅

- [x] 3.1 移除 DisplayRenderer 的线程相关代码
  - 移除 `_run_main_loop()` 方法
  - 移除 `_thread` 属性
  - 移除 `_stop_event` 属性
  - 移除 `start()` 方法中的线程创建逻辑
  - 移除 `stop()` 方法中的线程停止逻辑
  - _需求: 1.4, 1.5_

- [x] 3.2 实现 DisplayRenderer.initialize() 方法
  - 初始化统计信息（`_stats["start_time"]`）
  - 设置 `_window_created = False`
  - 记录初始化日志
  - _需求: 1.1_

- [x] 3.3 实现 DisplayRenderer.cleanup() 方法
  - 调用 `cv2.destroyAllWindows()` 关闭所有窗口
  - 输出统计信息（帧数、时长、平均FPS）
  - 记录清理日志
  - _需求: 1.5_

- [x] 3.4 实现双状态驱动架构
  - 修改 `_display_mode` 为 "combined" | "single"
  - 添加 `_selected_device_role` 属性（DeviceRole 类型）
  - 定义窗口层尺寸配置（`_window_width=1280`, `_window_height=720`, `_fullscreen_width=1920`, `_fullscreen_height=1080`）
  - _需求: 7.1, 7.2, 13.7, 13.8_

- [x] 3.5 实现 render_once() 方法（状态驱动 + 惰性渲染）
  - 根据 `_display_mode` 选择取包策略（单设备用 `get_packet_by_mxid`，拼接用 `get_packets`）
  - 调用 `_render_single_device()` 或 `_render_combined_devices()`（返回已 resize 到目标尺寸的帧）
  - 创建窗口（如果尚未创建）
  - 直接 `cv2.imshow()` 显示帧（无需再次 resize）
  - 处理键盘输入（'q'/'f'/'1'/'2'/'3'）
  - 更新统计信息和帧率限制
  - 返回退出信号（True/False）
  - _需求: 1.1, 1.2, 1.3, 6.1, 6.2, 13.1, 13.2, 13.3_

- [x] 3.6 修改 _render_single_device() 方法（Stretch Resize）
  - 根据 `_is_fullscreen` 确定目标尺寸（1280x720 或 1920x1080）
  - 使用 `cv2.resize(frame, (target_width, target_height))` 直接拉伸到目标尺寸
  - 调用 `_draw_detection_boxes_normalized()` 绘制检测框（offsetX=0）
  - 返回已 resize 到目标尺寸的画布
  - _需求: 7.1, 7.2, 7.5, 7.6, 7.7, 7.10_

- [x] 3.7 修改 _render_combined_devices() 方法（Stretch Resize）
  - 根据 `_is_fullscreen` 确定目标画布尺寸
  - 计算 ROI 尺寸（`roiW_left = target_width // 2`, `roiW_right = target_width - roiW_left`）
  - 对每个设备帧分别 `cv2.resize()` 到对应 ROI 尺寸
  - 使用 `np.hstack()` 水平拼接
  - 调用 `_draw_detection_boxes_normalized()` 绘制检测框（带 offsetX）
  - 返回已 resize 到目标尺寸的画布
  - _需求: 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.10_

- [x] 3.8 实现 _draw_detection_boxes_normalized() 方法
  - 从 `render_config` 导入 `STATUS_COLOR_MAP` 和样式配置
  - 遍历检测结果，根据 `status_label` 获取颜色
  - 使用归一化坐标映射公式：`x1 = int(xmin * roiW) + offsetX`, `y1 = int(ymin * roiH)`
  - 使用状态对应的颜色绘制矩形框
  - 绘制标签背景（填充矩形）和标签文字（白色）
  - _需求: 12.1, 12.2, 12.3, 12.4, 12.5, 12.7, 12.8_

- [x] 3.9 修改 _switch_to_device() 方法
  - 修改参数为 `device_role: DeviceRole`
  - 检查 `device_role` 是否存在于 `_role_bindings`
  - 切换 `_display_mode = "single"`
  - 更新 `_selected_device_role`
  - 从 `_role_bindings` 获取 `device_mxid`
  - 记录日志
  - _需求: 5.4, 5.5, 5.7, 8.3_

- [x] 3.10 修改按键处理逻辑
  - 修改 '1' 键映射到 `DeviceRole.LEFT_CAMERA`
  - 修改 '2' 键映射到 `DeviceRole.RIGHT_CAMERA`
  - 保持 '3' 键切换到 Combined 模式
  - _需求: 8.1, 8.2, 8.3_

### 4. DisplayManager 重构 ✅

- [x] 4.1 修改 DisplayManager.start() 方法
  - 只启动 `RenderPacketPackager` 的打包线程
  - 不启动 `DisplayRenderer` 的渲染线程
  - 调用 `self._renderer.initialize()`（如果 `enable_display=True`）
  - 设置 `_is_running = True`
  - _需求: 1.4, 4.1, 4.4_

- [x] 4.2 修改 DisplayManager.stop() 方法
  - 调用 `self._renderer.cleanup()`（如果 renderer 存在）
  - 停止 `RenderPacketPackager` 的打包线程
  - 设置 `_is_running = False`
  - _需求: 1.5, 4.2, 4.5_

- [x] 4.3 实现 DisplayManager.render_once() 方法
  - 检查 `enable_display` 配置
  - 检查 `_renderer` 是否存在
  - 调用 `self._renderer.render_once()` 并返回结果
  - 捕获异常并记录错误日志，返回 False
  - _需求: 6.1, 6.2, 6.3, 6.4, 6.5, 9.1, 9.2_

### 5. SystemManager 重构 ✅

- [x] 5.1 实现 SystemManager.register_display_module() 方法
  - 在 `SystemManager` 类中添加 `_display_module` 属性（初始化为 None）
  - 实现 `register_display_module(name, instance, priority)` 方法
  - 存储 DisplayManager 实例到 `self._display_module`
  - 同时调用 `register_module()` 进行常规注册（用于 start/stop 管理）
  - 记录注册日志，标记该模块需要主线程渲染
  - _需求: 3.1, 3.2_

- [x] 5.2 修改 SystemManager.run() 主循环
  - 在主循环开始前获取 `_display_module`
  - 添加日志记录（"SystemManager 开始运行，等待退出信号..."）
  - 修改 while 循环逻辑：
    - 如果 `_display_module` 存在，调用 `display_module.render_once()`
    - 如果返回 True，设置 `_shutdown_event` 并 break
    - 如果 `_display_module` 不存在，使用原有的 `wait(timeout=0.5)` 逻辑
  - 添加渲染异常处理（try-except），记录日志但不中断主循环
  - **关键改进**：在 `except KeyboardInterrupt` 块中添加 `self._shutdown_event.set()`
    - 确保所有退出路径都设置 `_shutdown_event`（状态一致性）
    - Ctrl+C、SYSTEM_SHUTDOWN 事件、'q' 键三种退出方式状态统一
  - 在 `finally` 块中检查 `_stop_started` 防止重复关闭
  - 添加详细的退出流程注释（三个出口：Ctrl+C、事件、'q' 键）
  - _需求: 2.1, 2.2, 2.3, 2.4_
  
  **退出流程设计**：
  - 出口1：Ctrl+C → 设置 `_shutdown_event` → `finally` → `shutdown()`
  - 出口2：SYSTEM_SHUTDOWN 事件 → 设置 `_shutdown_event` → 循环退出 → `finally` → `shutdown()`
  - 出口3：'q' 键 → `render_once()` 返回 True → 设置 `_shutdown_event` → `finally` → `shutdown()`
  
  **两个标志的作用**：
  - `_shutdown_event`：通知主循环退出（用于正常退出流程）
  - `_stop_started`：防止 `shutdown()` 重复执行（用于防御性编程）

### 6. 集成和配置调整 ✅

- [x] 6.1 更新 DeviceConfigManager 添加 get_active_role_bindings() 方法
  - 已实现 `get_active_role_bindings()` 方法
  - 遍历 `oak_module.role_bindings`，提取 `active_mxid`
  - 返回 `Dict[DeviceRole, str]` 格式的映射
  - _需求: 5.1_

- [x] 6.2 修改系统初始化代码传递 role_bindings
  - 冒烟测试中已正确传递 `role_bindings`
  - 使用 `register_display_module()` 注册显示模块
  - 确保 `devices_list` 和 `role_bindings` 都正确传递
  - _需求: 5.1, 5.2, 5.3_

- [x] 6.3 检查虚拟 CAN 配置
  - 确认配置文件中 `enable_can=false`（使用虚拟 CAN）
  - 冒烟测试会检查并提示 CAN 模式
  - 虚拟 CAN 适用于 Windows 开发环境

### 7. 集成测试和冒烟测试 ✅

- [x] 7.1 更新冒烟测试脚本
  - 修改 `test_smoke_virtualCAN.py` 使用 `register_display_module()`
  - 更新文档说明主线程渲染架构
  - 添加按键说明（'1'/'2'/'3'/'f'/'q'）
  - 验证系统正常启动、运行和关闭
  - _需求: 14.1_

- [x] 7.2 虚拟 CAN 配置验证
  - 确认配置文件 `assets/test_config/config.json` 中 `enable_can=false`
  - 冒烟测试会自动检测并提示使用虚拟 CAN 模式
  - 适用于 Windows 开发环境，无需真实 CAN 硬件
  - _需求: 14.1_

- [ ] 7.3 手动验证测试（需要用户执行）
  - 运行冒烟测试脚本：`python oak_vision_system/tests/smoke/test_smoke_virtualCAN.py`
  - 验证窗口正常显示
  - 验证按键响应（'1', '2', '3', 'f', 'q'）
  - 验证全屏切换功能
  - 验证单设备/拼接模式切换
  - 验证 'q' 键退出功能
  - _需求: 14.1, 14.2, 14.3_
  
  **说明**：此任务需要用户手动执行，无法由代码自动完成。

## 注意事项

- **任务 1-4 已完成**：核心渲染逻辑重构已完成，DisplayRenderer 和 DisplayManager 已支持主线程渲染
- **任务 5 是关键**：需要在 SystemManager 中添加显示模块的特殊处理逻辑
- **任务 6-7 是集成**：将所有组件连接起来并验证功能
- 每个任务都标注了对应的需求编号，便于追溯
- 建议按顺序执行任务，确保每个阶段完成后再进入下一阶段

## 实现优先级

1. **任务 5**：SystemManager 集成（必须，核心功能）
2. **任务 6**：配置和集成调整（必须，连接所有组件）
3. **任务 7**：测试和验证（推荐，确保功能正常）

## 下一步行动

**所有代码实现已完成！** 🎉

剩余工作：
- **任务 7.3**：手动运行冒烟测试验证功能
  ```bash
  python oak_vision_system/tests/smoke/test_smoke_virtualCAN.py
  ```

验证项目：
- ✅ 窗口正常显示
- ✅ 按键响应（'1', '2', '3', 'f', 'q'）
- ✅ 全屏切换功能
- ✅ 单设备/拼接模式切换
- ✅ 'q' 键退出功能

如果测试通过，主线程渲染架构重构即全部完成。
