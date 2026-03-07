下面是基于当前 `DisplayRenderer` 实现（）整理的**全部修复 tasks 总结**（按优先级从高到低）。每个 task 都包含：**问题/原因 → 修复方法 → 关键代码点**。其中 **Task 3 已按你最新补充**（`config.window_width/height` 作为全屏尺寸，小窗宽高减半）。

---

## Task 1：单次循环只调用一次 `cv2.waitKey`（修复吞键/切换键不生效）

**问题/原因**
`render_once()` 在“无数据分支”里会 `waitKey` 一次（只处理 `q`），后面又统一 `waitKey` 一次，导致 `f/1/2/3` 等键在无数据时被吞掉、切换不稳定。

**修复方法**

* 删除“无数据分支”里的 `waitKey`
* 无论有没有 frame，都走统一的按键处理
* 保证每次 `render_once()` **只调用一次** `waitKey`

**关键代码点**

* 无数据时改为 `frame=None`，不读键
* 末尾统一：

```python
key = cv2.waitKey(delay_ms) & 0xFF
# 统一处理 q/f/1/2/3
```

---

## Task 2：用 `waitKey(delay_ms)` 做帧率控制，替代 `time.sleep`（修复窗口假死/拖动卡顿）

**问题/原因**
使用 `time.sleep()` 节流会让 HighGUI 事件泵停顿，某些平台表现为窗口拖动卡顿、短暂无响应。

**修复方法**

* 计算剩余时间 `remain`
* 把节流延迟转换为 `delay_ms`
* 使用 `cv2.waitKey(delay_ms)` 同时完成“节流 + GUI事件泵”
* 与 Task 1 配合：确保只有这一次 waitKey

**关键代码点**

```python
delay_ms = 1
if self._target_frame_interval > 0:
    remain = self._target_frame_interval - (now - self._last_frame_time)
    if remain > 0:
        delay_ms = max(1, int(remain * 1000))
    self._last_frame_time = now

key = cv2.waitKey(delay_ms) & 0xFF
```

---

## Task 3：尺寸策略重构（按你最新要求）

### 配置仅提供全屏尺寸：`config.window_width / config.window_height`

### 小窗默认宽高减半；切全屏前先 `resizeWindow` 再切换全屏属性

**问题/原因**

* renderer 内部硬编码窗口/全屏尺寸（1280×720/1920×1080）导致配置不可用、难维护。
* 你补充：配置只给“全屏尺寸”，所以小窗需要策略（宽高减半）。
* `WINDOW_NORMAL` 下不 `resizeWindow` 会导致 window 尺寸不受控（frame≠window）。

**修复方法**

1. 从 `config.window_width/height` 缓存全屏目标尺寸：`_fullscreen_width/_fullscreen_height`
2. 小窗尺寸派生：`_window_width/_window_height = fullscreen // 2`（可加最小值 + 偶数对齐）
3. `_create_main_window()` 创建后先 `resizeWindow` 到小窗尺寸
4. 全屏切换采用稳妥顺序：

   * **先** `resizeWindow(fullscreen)`
   * **再** `setWindowProperty(FULLSCREEN)`
   * 回小窗：先 NORMAL 再 resizeWindow(window)

**关键代码点**

```python
# init：用 config 的全屏尺寸 + 小窗减半
self._fullscreen_width  = int(self._config.window_width)
self._fullscreen_height = int(self._config.window_height)
self._window_width  = max(640, self._fullscreen_width // 2)
self._window_height = max(360, self._fullscreen_height // 2)

# create window：强制小窗初始大小
cv2.namedWindow(name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(name, self._window_width, self._window_height)

# toggle fullscreen：先 resize 再 fullscreen
cv2.resizeWindow(name, self._fullscreen_width, self._fullscreen_height)
cv2.setWindowProperty(name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
```

---

## Task 4：修复窗口位置判断 bug（0 坐标失效）

**问题/原因**
`if x or y` 导致 `0` 被当 False，配置 `(0,0)` 无法生效。

**修复方法**
用 `is not None` 判断是否配置了坐标。

**关键代码点**

```python
x = self._config.window_position_x
y = self._config.window_position_y
if x is not None and y is not None:
    cv2.moveWindow(name, x, y)
```

---

## Task 5：移除对 `packager._latest_packets` 私有成员的直接访问（线程安全/稳定性）

**问题/原因**
`_draw_key_hints()` 直接访问 `self._packager._latest_packets`（私有字段且无锁），若 packager 在其他线程更新，可能出现低频崩溃或显示错乱。

**修复方法**（二选一）

* 最小改动：key hints 不再依赖 `_latest_packets`，只显示 `device_id`
* 更规范：packager 提供线程安全 snapshot getter（需要改 packager）

**关键代码点（最小改动）**

```python
for i, device_id in enumerate(self._devices_list):
    hints.append(f"{i+1}:{device_id}")
```

---

## 建议落地顺序

1. **Task 1**（吞键/双 waitKey）
2. **Task 2**（sleep→waitKey 节流）
3. **Task 3**（配置驱动尺寸 + 小窗减半 + resizeWindow + 切换顺序）
4. **Task 4**（position bug）
5. **Task 5**（线程安全/去私有访问）


