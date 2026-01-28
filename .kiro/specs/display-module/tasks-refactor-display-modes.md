# 实现任务：重构显示模式为多设备切换模式

## 概述

根据用户需求，重构显示模块的显示模式，从当前的"RGB/Depth/Combined/Side-by-Side"模式改为"单设备切换 + Combined拼接"模式。

**核心变更**：
1. **Combined 模式重新定义**：从"RGB+深度叠加"改为"多设备RGB水平拼接"
2. **移除 Side-by-Side 模式**：不再需要RGB+深度并排显示
3. **单窗口策略**：使用一个主窗口，根据按键切换显示内容
4. **按键控制**：1/2切换单设备，3切换Combined模式，F切换全屏，Q退出
5. **深度数据可选**：通过 enable_depth_output 配置控制是否处理深度数据

**参考旧实现**：`plan/modules/display/dual_detectionv2.py`

---

## 任务列表

- [x] 1. 更新配置DTO（DisplayConfigDTO）
  - [x] 1.1 移除 side_by_side 显示模式
  - [x] 1.2 更新 DISPLAY_MODES 为 ("rgb",)
  - [x] 1.3 移除 depth_alpha 配置项（不再需要叠加）
  - [x] 1.4 确保 window_position_x/y 配置存在
  - _需求: 需求 9, 需求 10_

- [x] 2. 重构 DisplayRenderer 的显示模式逻辑
  - [x] 2.1 移除 _render_combined_mode() 方法（旧的RGB+深度叠加）
  - [x] 2.2 移除 _render_side_by_side_mode() 方法
  - [x] 2.3 移除 _render_depth_mode() 方法（深度图显示为可选功能）
  - [x] 2.4 简化 _render_rgb_mode() 为主要渲染方法
  - _需求: 需求 9_

- [x] 3. 实现单窗口多模式显示
  - [x] 3.1 修改 _create_window() 创建单个主窗口（不是每个设备一个窗口）
  - [x] 3.2 添加显示模式状态管理
    - 维护当前显示模式：单设备索引（0, 1, 2...）或 Combined
    - 维护设备列表和在线状态
  - [x] 3.3 实现 _render_single_device() 方法
    - 渲染单个设备的RGB帧
    - 添加设备信息叠加
    - 全屏显示
  - [x] 3.4 实现 _render_combined_devices() 方法（新的Combined模式）
    - 水平拼接所有设备的RGB帧
    - 在每个设备图像上添加设备名称标签
    - 参考旧实现的 create_combined_display() 方法
  - _需求: 需求 2, 需求 9, 需求 16_

- [x] 4. 实现按键切换逻辑
  - [x] 4.1 修改 _run_main_loop() 的按键处理
    - 移除 'm' 键（切换显示模式）
    - 添加数字键 '1', '2', '3'... 处理
    - 保留 'f' 键（全屏切换）
    - 保留 'q' 键（退出）
  - [x] 4.2 实现 _switch_to_device() 方法
    - 切换到指定设备的单设备显示
    - 更新窗口标题
  - [x] 4.3 实现 _switch_to_combined() 方法
    - 切换到Combined模式
    - 更新窗口标题
  - [x] 4.4 添加按键提示信息显示
    - 在窗口底部显示："1:Device1 2:Device2 3:Combined F:Fullscreen Q:Quit"
  - _需求: 需求 9, 需求 16_

- [x] 5. 实现双设备自适应（固定双设备场景）
  - [x] 5.0 前置准备：在 DeviceConfigManager 中新增接口
    - 新增 `get_active_role_bindings()` 方法
    - 返回 `Dict[DeviceRole, str]`（role -> mxid 映射）
    - 供外部获取当前激活的设备角色绑定
  - [x] 5.1 修改 DisplayRenderer 初始化参数
    - 在 `__init__` 方法中新增 `role_bindings: Dict[DeviceRole, str]` 参数
    - 存储为实例变量 `self._role_bindings`
    - 由外部通过配置管理器获取并传入（不需要每次检查）
  - [x] 5.2 实现 _get_active_devices() 方法
    - 基于 `self._role_bindings` 和 packager 缓存检测设备在线状态
    - 检查两个设备是否有最近的数据（未过期）
    - 返回在线设备ID列表（最多2个）
  - [x] 5.3 实现单设备自动切换逻辑
    - 当只有一个设备在线时，自动切换到单设备模式
    - 避免Combined模式下的半边黑屏
  - [x] 5.4 固定窗口大小（双设备场景）
    - 单设备模式：使用配置的窗口大小（默认640x480）
    - Combined模式：固定为双倍宽度（1280x480）
    - 不需要考虑更多设备的扩展
  - _需求: 需求 9, 需求 16_
  - _注意: 系统固定为双设备配置，不需要支持任意数量设备_
  - _设计理由: 通过配置传入 role_bindings，避免每次检查，性能更好；未来可通过掉线重连机制更新_

- [x] 6. 更新深度图处理（可选功能）
  - [x] 6.1 添加 enable_depth_output 配置检查
    - 仅当配置为True时处理深度帧
    - 否则忽略深度数据
  - [x] 6.2 保留 _visualize_depth() 方法（已使用百分位数归一化）
    - 确认使用HOT颜色映射
    - 确认百分位数归一化逻辑正确
  - [x] 6.3 深度图显示为独立功能（不与RGB混合）
    - 可以作为未来扩展：按'd'键切换深度图显示
  - _需求: 需求 10_

- [x] 7. 更新窗口管理
  - [x] 7.1 修改 _toggle_fullscreen() 方法
    - 只处理单个主窗口的全屏切换
    - 移除多窗口循环逻辑
  - [x] 7.2 确保窗口位置配置生效
    - 使用 window_position_x/y 设置初始位置
  - [x] 7.3 更新窗口标题
    - 单设备模式：显示设备名称
    - Combined模式：显示 "Combined View"
  - _需求: 需求 11_

- [x] 8. 更新测试文件
  - [x] 8.1 更新 test_display_renderer_display_modes.py
    - 移除 side_by_side 模式测试
    - 移除旧的 combined 模式测试（RGB+深度叠加）
    - 添加新的单设备切换测试
    - 添加新的 Combined 模式测试（多设备拼接）
  - [x] 8.2 更新其他相关测试
    - 确保所有测试使用新的显示模式定义
  - _需求: 所有需求_

- [x] 9. 更新配置模板和示例
  - [x] 9.1 更新 config_template.py
    - 移除 depth_colormap 配置
    - 移除 depth_alpha 配置
    - 确保 window_position_x/y 存在
  - [x] 9.2 更新示例文件
    - 更新 config_architecture_example.py
    - 移除过时的配置项
  - _需求: 需求 4_

- [x] 10. 集成测试和验证
  - [x] 10.1 运行所有显示模块测试
    - 确保所有测试通过
  - [x] 10.2 手动测试按键切换
    - 测试1/2/3键切换
    - 测试F键全屏切换
    - 测试Q键退出
  - [x] 10.3 测试多设备场景
    - 测试单设备显示
    - 测试双设备Combined模式
    - 测试设备数量变化时的自适应
  - _需求: 所有需求_

---

## 实现要点

### 1. 单窗口策略

**当前实现问题**：
```python
# 当前：为每个设备创建独立窗口
for device_id, packet in packets.items():
    self._render_packet(device_id, packet)
```

**新实现**：
```python
# 新：使用单窗口，根据模式选择渲染内容
packets = self._packager.get_packets(timeout=0.1)
if self._display_mode == "combined":
    frame = self._render_combined_devices(packets)
else:
    # 单设备模式
    device_id = self._devices_list[self._selected_device_index]
    if device_id in packets:
        frame = self._render_single_device(packets[device_id])
cv2.imshow(self._main_window_name, frame)
```

### 2. Combined 模式实现（双设备场景）

```python
def _render_combined_devices(self, packets: Dict[str, RenderPacket]) -> np.ndarray:
    """渲染双设备RGB拼接（新的Combined模式）
    
    注意：固定为双设备场景，不需要支持任意数量设备
    """
    rgb_frames = []
    device_names = []
    
    # 收集两个设备的RGB帧（按设备列表顺序）
    for device_id in self._devices_list[:2]:  # 只处理前两个设备
        if device_id in packets:
            packet = packets[device_id]
            # 渲染单个设备的RGB帧（包含检测框等）
            frame = self._render_single_device_frame(packet)
            rgb_frames.append(frame)
            device_names.append(packet.processed_detections.device_alias or device_id)
    
    if not rgb_frames:
        return None
    
    # 水平拼接（双设备场景）
    if len(rgb_frames) == 1:
        # 只有一个设备在线，直接返回
        combined = rgb_frames[0]
    else:
        # 两个设备都在线，水平拼接（宽度=1280）
        combined = np.hstack(rgb_frames)
    
    # 添加设备名称标签
    frame_width = rgb_frames[0].shape[1]  # 640
    for i, name in enumerate(device_names):
        x_offset = i * frame_width
        cv2.putText(combined, name, (x_offset + 10, 30), 
                   cv2.FONT_HERSHEY_TRIPLEX, 0.7, (0, 255, 255), 2)
    
    return combined
```

### 3. 按键映射

```python
# 在 _run_main_loop() 中
key = cv2.waitKey(1) & 0xFF
if key == ord('q'):
    self._stop_event.set()
elif key == ord('1'):
    self._switch_to_device(0)
elif key == ord('2'):
    self._switch_to_device(1)
elif key == ord('3'):
    self._switch_to_combined()
elif key == ord('f'):
    self._toggle_fullscreen()
```

### 4. 双设备自适应（简化版）

```python
def _get_active_devices(self) -> List[str]:
    """获取当前有数据的设备列表（固定双设备场景）"""
    active = []
    # 只检查两个设备
    for device_id in self._devices_list[:2]:  # 最多检查2个设备
        # 检查该设备是否有最近的数据
        if device_id in self._packager._latest_packets:
            packet = self._packager._latest_packets[device_id]
            if packet is not None:
                # 检查数据是否过期
                age = time.time() - self._packager._packet_timestamps.get(device_id, 0)
                if age <= self._packager.cache_max_age_sec:
                    active.append(device_id)
    return active

def _auto_adjust_display_mode(self, packets: Dict[str, RenderPacket]) -> None:
    """根据在线设备数量自动调整显示模式（双设备场景）"""
    active_devices = self._get_active_devices()
    
    # 如果只有一个设备在线，自动切换到单设备模式
    if len(active_devices) == 1:
        self._display_mode = "single"
        self._selected_device_index = self._devices_list.index(active_devices[0])
    # 如果两个设备都在线，使用Combined模式
    elif len(active_devices) == 2:
        if self._display_mode != "combined":
            self._display_mode = "combined"
```

---

## 测试策略

### 单元测试

1. **测试单设备渲染**
   - 输入：单个设备的RenderPacket
   - 验证：返回正确的RGB帧，包含检测框和叠加信息

2. **测试Combined模式渲染（双设备）**
   - 输入：两个设备的RenderPacket字典
   - 验证：返回水平拼接的帧（宽度=1280），每个设备有名称标签

3. **测试按键切换**
   - 模拟按键输入
   - 验证：显示模式正确切换

4. **测试双设备自适应**
   - 输入：1个或2个在线设备
   - 验证：单设备时自动切换到单设备模式，双设备时使用Combined模式
   - 验证：单设备时自动全屏，多设备时使用Combined

### 集成测试

1. **端到端测试**
   - 启动完整的数据流：Collector → DataProcessor → Display
   - 验证：能够正常显示和切换

2. **多设备测试**
   - 模拟多个设备的数据流
   - 验证：Combined模式正确拼接

3. **按键交互测试**
   - 手动测试所有按键功能
   - 验证：响应正确，无崩溃

---

## 风险和注意事项

1. **向后兼容性**
   - 移除了多个显示模式，可能影响现有配置
   - 缓解：更新配置模板和文档

2. **测试覆盖**
   - 需要更新大量测试用例
   - 缓解：逐步更新，确保每个测试都通过

3. **性能影响**
   - Combined模式需要拼接多个帧，可能影响性能
   - 缓解：使用NumPy的高效操作，避免不必要的复制

4. **窗口管理**
   - 从多窗口改为单窗口，需要仔细处理窗口生命周期
   - 缓解：参考旧实现的窗口管理逻辑

---

## 参考资料

1. **旧实现**：`plan/modules/display/dual_detectionv2.py`
   - 参考 `create_combined_display()` 方法
   - 参考 `create_single_display()` 方法
   - 参考 `main_display_loop()` 的按键处理

2. **需求文档**：`.kiro/specs/display-module/requirements.md`
   - 需求 9：多设备显示模式切换
   - 需求 16：多设备支持

3. **当前实现**：
   - `oak_vision_system/modules/display_modules/display_renderer.py`
   - `oak_vision_system/core/dto/config_dto/display_config_dto.py`

---

## 预期成果

完成本任务后，显示模块将：

1. ✅ 使用单窗口显示所有内容
2. ✅ 支持按1/2/3键切换单设备和Combined模式
3. ✅ Combined模式正确拼接多设备RGB帧
4. ✅ 单设备时自动全屏显示
5. ✅ 深度数据处理为可选功能（enable_depth_output控制）
6. ✅ 所有测试通过
7. ✅ 配置和文档更新完成

**用户体验**：
- 启动后默认显示Combined模式（多设备拼接）
- 按1或2键查看单个设备的详细信息
- 按3键返回Combined模式
- 按F键切换全屏
- 按Q键退出
- 界面简洁，操作直观
