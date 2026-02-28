# 需求文档：显示模块主线程渲染重构

## 简介

本需求文档描述了将显示模块的渲染逻辑从独立线程迁移到主线程的重构需求。当前实现中，DisplayRenderer 在独立线程中运行 OpenCV 渲染循环，这在某些环境下（特别是 Windows）容易导致窗口卡死或无响应。重构后，渲染逻辑将由 SystemManager 在主线程中驱动，DisplayManager 只负责状态管理和数据打包。

## 术语表

- **SystemManager**: 系统管理器，负责协调所有模块的生命周期和主循环调度
- **DisplayManager**: 显示模块管理器，负责管理 RenderPacketPackager 和 DisplayRenderer
- **RenderPacketPackager**: 渲染包打包器，负责订阅事件并将数据打包成渲染包
- **DisplayRenderer**: 显示渲染器，负责使用 OpenCV 渲染视频帧和检测结果
- **Main_Thread**: 主线程，Python 程序的主执行线程，OpenCV 窗口必须在此线程中创建和更新
- **Render_Once**: 单步渲染接口，执行一次渲染循环并返回控制权
- **Shutdown_Signal**: 关闭信号，用于通知 SystemManager 终止主循环
- **Stretch_Resize**: 拉伸缩放策略，使用 cv2.resize(frame, (dstW, dstH)) 直接拉伸到目标尺寸，不保持宽高比
- **Normalized_Coordinates**: 归一化坐标，检测框坐标格式为 (xmin, ymin, xmax, ymax) ∈ [0,1]
- **ROI**: 感兴趣区域（Region of Interest），在合并显示模式下，每个设备帧占据的画布区域
- **Target_Resolution**: 目标分辨率，最终显示的窗口尺寸（窗口模式 1280x720 或全屏模式 1920x1080）

## 需求

### 需求 1: 主线程渲染架构

**用户故事**: 作为系统开发者，我希望显示模块的渲染逻辑在主线程中执行，以避免 OpenCV 窗口在某些平台上的卡死问题。

#### 验收标准

1. WHEN SystemManager 运行主循环 THEN DisplayManager SHALL 提供单步渲染接口供主线程调用
2. WHEN 单步渲染接口被调用 THEN DisplayManager SHALL 执行一次渲染循环并立即返回控制权
3. WHEN 用户按下退出键（'q'）THEN 单步渲染接口 SHALL 返回退出信号
4. WHEN DisplayManager 启动 THEN DisplayManager SHALL NOT 创建独立的渲染线程
5. WHEN DisplayManager 关闭 THEN DisplayManager SHALL 只关闭打包线程而不关闭渲染线程

### 需求 2: SystemManager 主循环驱动

**用户故事**: 作为系统架构师，我希望 SystemManager 的主循环能够驱动显示模块的渲染，实现统一的调度机制。

#### 验收标准

1. WHEN SystemManager.run() 执行主循环 THEN SystemManager SHALL 每轮循环调用一次 DisplayManager.render_once()
2. WHEN DisplayManager.render_once() 返回退出信号 THEN SystemManager SHALL 触发 SYSTEM_SHUTDOWN 事件
3. WHEN 用户按下 Ctrl+C THEN SystemManager SHALL 捕获 KeyboardInterrupt 并触发关闭流程
4. WHEN 关闭流程触发 THEN SystemManager SHALL 调用 shutdown() 方法关闭所有模块
5. WHEN 模块关闭超时 THEN SystemManager SHALL 使用兜底机制强制退出进程

### 需求 3: DisplayManager 特殊注册接口

**用户故事**: 作为系统开发者，我希望 DisplayManager 有专门的注册接口，以表明它需要主线程渲染的特殊处理。

#### 验收标准

1. WHEN 注册 DisplayManager THEN SystemManager SHALL 提供 register_display_module() 专用接口
2. WHEN DisplayManager 被注册 THEN SystemManager SHALL 标记该模块需要主线程渲染
3. WHEN SystemManager 启动模块 THEN DisplayManager SHALL 按照正常优先级顺序启动
4. WHEN SystemManager 关闭模块 THEN DisplayManager SHALL 按照正常优先级顺序关闭
5. WHEN SystemManager 执行主循环 THEN SystemManager SHALL 自动调用已注册的 DisplayManager.render_once()

### 需求 4: 渲染包打包线程管理

**用户故事**: 作为模块开发者，我希望 DisplayManager 继续管理 RenderPacketPackager 的打包线程，保持数据流的异步处理。

#### 验收标准

1. WHEN DisplayManager.start() 被调用 THEN DisplayManager SHALL 启动 RenderPacketPackager 的打包线程
2. WHEN DisplayManager.stop() 被调用 THEN DisplayManager SHALL 停止 RenderPacketPackager 的打包线程
3. WHEN 打包线程运行 THEN RenderPacketPackager SHALL 订阅事件并将数据打包成渲染包
4. WHEN DisplayManager.start() 被调用 THEN DisplayManager SHALL NOT 启动 DisplayRenderer 的渲染线程
5. WHEN DisplayManager.stop() 被调用 THEN DisplayManager SHALL NOT 尝试停止不存在的渲染线程

### 需求 5: role_bindings 依赖注入和设备角色管理

**用户故事**: 作为系统开发者，我希望 DisplayRenderer 通过依赖注入获取设备角色绑定，实现解耦和可测试性。

#### 验收标准

1. WHEN 创建 DisplayManager THEN 上层 SHALL 从 DeviceConfigManager 调用 get_active_role_bindings() 获取角色绑定
2. WHEN 创建 DisplayManager THEN role_bindings SHALL 作为参数传入构造函数
3. WHEN DisplayManager 创建 DisplayRenderer THEN role_bindings SHALL 传递给 DisplayRenderer
4. WHEN DisplayRenderer 需要左设备 mxid THEN DisplayRenderer SHALL 使用 role_bindings[DeviceRole.LEFT_CAMERA]
5. WHEN DisplayRenderer 需要右设备 mxid THEN DisplayRenderer SHALL 使用 role_bindings[DeviceRole.RIGHT_CAMERA]
6. WHEN DisplayRenderer 运行 THEN DisplayRenderer SHALL NOT 直接依赖 ConfigManager
7. WHEN 单设备模式切换设备 THEN 系统 SHALL 根据 _selected_device_role 从 role_bindings 获取对应 mxid
8. WHEN role_bindings 为空或缺少角色 THEN 系统 SHALL 记录警告并优雅降级

### 需求 6: 单步渲染接口设计

**用户故事**: 作为 SystemManager 开发者，我希望 DisplayManager 提供清晰的单步渲染接口，返回值明确指示是否需要退出。

#### 验收标准

1. WHEN DisplayManager.render_once() 被调用 THEN DisplayManager SHALL 执行一次完整的渲染循环
2. WHEN 渲染成功完成 THEN render_once() SHALL 返回 False（表示继续运行）
3. WHEN 用户按下 'q' 键 THEN render_once() SHALL 返回 True（表示请求退出）
4. WHEN 渲染过程中发生异常 THEN render_once() SHALL 记录错误日志并返回 False
5. WHEN DisplayManager 未启用显示 THEN render_once() SHALL 立即返回 False

### 需求 7: 窗口分辨率和 Stretch Resize 策略

**用户故事**: 作为用户，我希望显示窗口使用单次 Stretch Resize 策略直接拉伸到目标尺寸，保持窗口 16:9 宽高比，并接受双图模式下的拉伸变形以换取性能。

#### 验收标准

1. WHEN 单设备显示且窗口模式 THEN 系统 SHALL 使用 cv2.resize 直接将原始帧拉伸到 1280x720（16:9 比例）
2. WHEN 单设备显示且全屏模式 THEN 系统 SHALL 使用 cv2.resize 直接将原始帧拉伸到 1920x1080（16:9 比例）
3. WHEN 合并显示且窗口模式 THEN 系统 SHALL 将每路帧分别拉伸到对应 ROI 尺寸（640x720 和 640x720），然后水平拼接成 1280x720
4. WHEN 合并显示且全屏模式 THEN 系统 SHALL 将每路帧分别拉伸到对应 ROI 尺寸（960x1080 和 960x1080），然后水平拼接成 1920x1080
5. WHEN 执行 resize 操作 THEN 系统 SHALL NOT 使用 keep-aspect-ratio（等比缩放）
6. WHEN 执行 resize 操作 THEN 系统 SHALL NOT 引入 padding/padX/padY
7. WHEN 执行 resize 操作 THEN 系统 SHALL NOT 使用 letterbox 策略
8. WHEN 合并显示模式 THEN 系统 SHALL 接受 16:9 图像被拉伸到 8:9 ROI 导致的水平压缩变形
9. WHEN 切换全屏/窗口模式 THEN 系统 SHALL 使用 cv2.setWindowProperty 切换窗口属性，并在下一帧渲染时根据 _is_fullscreen 标志选择对应的目标尺寸
10. WHEN 渲染方法返回帧 THEN 返回的帧 SHALL 已经是目标尺寸（窗口或全屏），可直接用于 cv2.imshow()

### 需求 8: 按键处理逻辑

**用户故事**: 作为用户，我希望按键处理逻辑保持在 DisplayRenderer 中，并通过返回值传递给 SystemManager。

#### 验收标准

1. WHEN 用户按下 'q' 键 THEN DisplayRenderer SHALL 检测到按键并设置退出标志
2. WHEN render_once() 检测到退出标志 THEN render_once() SHALL 返回 True
3. WHEN 用户按下其他功能键 THEN DisplayRenderer SHALL 处理相应的功能（如切换显示模式）
4. WHEN 按键处理完成 THEN DisplayRenderer SHALL 继续渲染下一帧
5. WHEN 没有按键输入 THEN render_once() SHALL 正常渲染并返回 False

### 需求 9: 异常处理和日志记录

**用户故事**: 作为系统维护者，我希望渲染过程中的异常能够被正确捕获和记录，不影响系统的稳定性。

#### 验收标准

1. WHEN render_once() 执行过程中发生异常 THEN DisplayManager SHALL 捕获异常并记录错误日志
2. WHEN 渲染异常被捕获 THEN render_once() SHALL 返回 False 以继续运行
3. WHEN 连续发生多次渲染异常 THEN DisplayManager SHALL 记录警告日志
4. WHEN 关键异常发生（如窗口创建失败）THEN DisplayManager SHALL 记录 CRITICAL 日志
5. WHEN 系统关闭 THEN DisplayManager SHALL 记录统计信息到日志

### 需求 10: 向后兼容性

**用户故事**: 作为现有代码的维护者，我希望重构后的接口保持向后兼容，最小化对现有代码的影响。

#### 验收标准

1. WHEN 使用旧的 register_module() 接口 THEN DisplayManager SHALL 仍然能够正常注册
2. WHEN DisplayManager 配置 enable_display=False THEN 系统 SHALL 正常运行而不渲染
3. WHEN 其他模块调用 DisplayManager 的公共接口 THEN 接口行为 SHALL 保持不变
4. WHEN 配置文件格式不变 THEN DisplayManager SHALL 正常加载配置
5. WHEN 事件总线消息格式不变 THEN DisplayManager SHALL 正常接收和处理事件

### 需求 11: 性能和响应性

**用户故事**: 作为用户，我希望重构后的渲染性能不低于原实现，并且窗口响应流畅。

#### 验收标准

1. WHEN 系统运行 THEN 渲染帧率 SHALL 不低于 30 FPS
2. WHEN 用户按下按键 THEN 系统 SHALL 在 100ms 内响应
3. WHEN 主循环执行 THEN CPU 使用率 SHALL 保持在合理范围（不超过 50%）
4. WHEN 渲染队列满 THEN 系统 SHALL 丢弃旧帧而不阻塞
5. WHEN 系统关闭 THEN 所有模块 SHALL 在 5 秒内完成关闭

### 需求 12: 归一化坐标映射

**用户故事**: 作为系统开发者，我希望使用归一化坐标进行检测框映射，简化坐标转换逻辑并提高可维护性。

#### 验收标准

1. WHEN 接收检测框坐标 THEN 系统 SHALL 使用归一化格式 (xmin, ymin, xmax, ymax) ∈ [0,1]
2. WHEN 单设备模式映射坐标 THEN 系统 SHALL 使用公式 x1 = int(xmin * Target_W), y1 = int(ymin * Target_H)
3. WHEN 合并模式映射坐标 THEN 系统 SHALL 使用公式 x1 = int(xmin * roiW) + offsetX, y1 = int(ymin * Target_H)
4. WHEN 计算坐标映射 THEN 系统 SHALL NOT 依赖原始图像宽高参与计算
5. WHEN 计算坐标映射 THEN 系统 SHALL NOT 使用 padding 变量（padX/padY）
6. WHEN 合并模式计算 ROI THEN 系统 SHALL 使用 roiW_left = Target_W // 2, roiW_right = Target_W - roiW_left
7. WHEN 绘制检测框 THEN 系统 SHALL 在已 resize 到目标尺寸的画布上绘制
8. WHEN 绘制 UI 元素 THEN UI 元素 SHALL 保持标准宽高比（不受底图拉伸变形影响）

### 需求 13: 惰性渲染和状态驱动

**用户故事**: 作为系统开发者，我希望使用惰性渲染策略和双状态驱动架构，优化 CPU 使用率并简化渲染逻辑。

#### 验收标准

1. WHEN 单设备模式渲染 THEN 系统 SHALL 仅调用 get_packet_by_mxid(device_mxid, timeout) 获取当前设备的渲染包
2. WHEN 单设备模式渲染 THEN 未选中设备的数据 SHALL 停留在打包器队列中不被消费
3. WHEN 合并模式渲染 THEN 系统 SHALL 调用 get_packets(timeout) 一次获取所有设备的渲染包
4. WHEN get_packet_by_mxid 队列超时 THEN 系统 SHALL 检查缓存帧 _latest_packets[mxid]
5. WHEN 缓存帧未过期（age <= cache_max_age_sec）THEN 系统 SHALL 返回缓存帧
6. WHEN 缓存帧已过期 THEN 系统 SHALL 清理缓存并返回 None
7. WHEN 维护显示状态 THEN 系统 SHALL 使用状态 1（显示模式：左设备|右设备|拼接）决定取包策略
8. WHEN 维护显示状态 THEN 系统 SHALL 使用状态 2（视图属性：全屏|窗口）决定目标分辨率
9. WHEN 切换全屏模式 THEN 系统 SHALL 仅更新 _is_fullscreen 标志，不每帧查询窗口属性
10. WHEN 单设备模式 CPU 使用 THEN CPU 使用率 SHALL 比合并模式降低约 50%（避免处理未选中设备）

### 需求 14: 测试和验证

**用户故事**: 作为质量保证工程师，我希望重构后的代码有完整的测试覆盖，确保功能正确性。

#### 验收标准

1. WHEN 运行冒烟测试 THEN 系统 SHALL 正常启动、运行和关闭
2. WHEN 运行单元测试 THEN DisplayManager.render_once() SHALL 通过所有测试用例
3. WHEN 运行集成测试 THEN SystemManager 和 DisplayManager 的交互 SHALL 正常工作
4. WHEN 模拟用户按键 THEN 系统 SHALL 正确响应并退出
5. WHEN 模拟渲染异常 THEN 系统 SHALL 正确处理并继续运行
