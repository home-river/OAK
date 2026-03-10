下面是一份可以直接丢给 IDE/代码助手执行的改动任务说明，目标是把方案 A 落地，同时尽量保持外部接口不变。

---

# Task: 重构 `CANCommunicator` 的 Listener 结构，消除 `Notifier.stop()` 导致的 `stop()` 重入死锁

## 背景

当前 `CANCommunicator` 既是通信管理器，又直接继承 `can.Listener`，并在 `start()` 中通过 `self.notifier = can.Notifier(self.bus, [self])` 将自己注册为 listener。

在 `stop()` 中调用 `self.notifier.stop(timeout=timeout)` 时，`python-can` 会对 listener 调用 `stop()`；由于 listener 就是 `self`，因此会再次进入 `CANCommunicator.stop()`，第二次进入时阻塞在 `_running_lock`，形成自重入死锁。相关 traceback 已明确显示该调用链。

---

## 改动目标

将 listener 从 `CANCommunicator` 中拆分为独立的私有适配类，使：

1. `CANCommunicator` 只负责资源生命周期管理

   * `start()/stop()`
   * `bus/notifier`
   * event bus 订阅
   * 警报线程
   * 业务处理

2. 独立 listener 只负责：

   * 接收 `Notifier` 的 `on_message_received(msg)` 回调
   * 将消息转发给 `CANCommunicator`
   * 可提供轻量 `stop()`，但绝不能调用 `communicator.stop()`

3. 保持对外接口和行为基本不变

   * 外部仍通过 `communicator.start()` / `communicator.stop()` 使用
   * 现有业务逻辑尽量不改或少改

---

## 需要修改的文件

主要修改：

* `oak_vision_system/modules/can_communication/can_communicator.py`

可能需要同步检查：

* `oak_vision_system/modules/can_communication/__init__.py`
* 相关单元测试 / 手动测试文件

---

## 具体改动要求

### 1. 去掉 `CANCommunicator` 对 `can.Listener` 的直接继承

当前类定义类似：

```python
class CANCommunicator(CANCommunicatorBase, can.Listener):
```

改为：

```python
class CANCommunicator(CANCommunicatorBase):
```

并删除 `__init__` 中对 `can.Listener.__init__(self)` 的直接初始化。当前文件文档里也明确写了“直接继承 `can.Listener`”这一设计点，需要同步修正文档说明。

---

### 2. 在 `can_communicator.py` 内新增一个私有 listener 类

建议新增：

```python
class _CANMessageListener(can.Listener):
    def __init__(self, communicator: "CANCommunicator"):
        super().__init__()
        self._communicator = communicator

    def on_message_received(self, msg: can.Message):
        try:
            self._communicator.on_message_received(msg)
        except Exception:
            logger.exception("Listener 转发 CAN 消息时发生异常")

    def stop(self):
        # 仅做 listener 自身清理；不要调用 communicator.stop()
        pass
```

要求：

* 类名私有化，避免暴露为对外 API
* `stop()` 必须是轻量/空实现
* 绝不能在该类中关闭 bus、notifier、event subscription
* 绝不能在该类中调用 `communicator.stop()`

---

### 3. 在 `CANCommunicator.__init__()` 中新增 listener 成员

新增成员，例如：

```python
self._listener: Optional[_CANMessageListener] = None
```

保留现有：

* `self.bus`
* `self.notifier`
* `_running_lock`
* `_alert_*`
* `_person_warning_subscription_id`

---

### 4. 修改 `start()`，改为注册独立 listener

当前 `start()` 里是：

```python
self.notifier = can.Notifier(self.bus, [self])
```

改为：

```python
self._listener = _CANMessageListener(self)
self.notifier = can.Notifier(self.bus, [self._listener])
```

当前代码和注释已经明确说明“使用 self 作为 Listener”，这些注释和文档字符串都需要一起改掉。

建议把启动流程描述改成：

* 创建 `can.Bus`
* 创建 `_CANMessageListener`
* 创建 `can.Notifier(bus, [listener])`
* 订阅 `PERSON_WARNING`

---

### 5. 保留现有业务处理入口，避免大范围改动

为了最小化修改，`_CANMessageListener.on_message_received()` 可以先直接转发到：

```python
self._communicator.on_message_received(msg)
```

也就是说，`CANCommunicator` 仍然可以保留现有 `on_message_received()` 方法，作为内部业务处理入口，而不再是 `Notifier` 直接调用的 listener 实现。

如果你愿意顺手提升可读性，也可以把业务入口重命名为：

```python
handle_received_message()
```

然后 listener 转发到这个新方法。
但这不是必须项，优先保证最小改动落地。

---

### 6. 修改 `stop()` 的资源清理逻辑，补充 listener 引用清理

在 `stop()` 完成 `notifier.stop()` 后，增加：

```python
self._listener = None
```

要求：

* 先停 notifier，再清掉 listener 引用
* listener 自身不负责主停机
* 保持现有 stop 顺序基本不变：

  * 停警报线程
  * 取消事件订阅
  * 停 notifier
  * 关 bus
  * reset interface

当前 stop 逻辑和顺序定义已写在代码中，可在此基础上改。

---

## 本次必须解决的问题

本次改动必须确保以下链路不再出现：

```text
communicator.stop()
  -> notifier.stop()
    -> listener.stop()
      -> communicator.stop()   # 禁止再发生
```

也就是说，`Notifier.stop()` 调用到的只能是独立 listener 的轻量 `stop()`，而不能再回到 `CANCommunicator.stop()`。日志中当前正是这条重入链导致了死锁。

---

## 本次尽量不要做的额外重构

为了控制改动范围，这一轮先不要大改以下内容：

1. 不要改外部工厂接口

   * `create_can_communicator(...)` 保持不变

2. 不要改对外类名

   * 仍然使用 `CANCommunicator`

3. 不要改事件总线行为

   * `PERSON_WARNING` 订阅逻辑保持不变

4. 不要改坐标响应和警报发送业务逻辑

   * 除非必须适配新 listener

---

## 建议顺手做的低风险改进

不是本次必须，但如果改动方便，建议一起做：

### A. 修正文档和注释

当前类文档、注释、启动流程说明里都写着“直接继承 `can.Listener`”“使用 self 作为 Listener”，这些会过时，需要更新。

### B. `stop()` 中显式清理 `_listener`

避免 stop 后仍残留旧 listener 引用。

---

## 验收标准

### 功能验收

1. `start()` 后 CAN 收包逻辑仍正常
2. 坐标请求响应功能不变
3. 人员警报功能不变
4. 混合场景不变

### 关键问题验收

1. 执行手动测试后，`communicator.stop()` 不再卡死
2. 日志中不应再出现停机过程中第二次进入：
   `========== 开始 stop() 方法 ==========`
3. 不再出现：

   * `KeyboardInterrupt` 卡在 `_running_lock`
   * `SocketcanBus was not properly shut down`

当前失败日志已经显示 stop 会在 `notifier.stop()` 期间重入 `stop()`，本次修改后该现象应消失。

---

## 建议测试项

### 手动回归

使用你现有手动测试脚本再次验证：

```bash
python oak_vision_system/tests/manual/can/test_can_communication_manual.py
```

重点观察：

* 坐标响应测试是否正常
* 警报测试是否正常
* 混合场景是否正常
* 脚本结束后 stop 是否能自然退出

### 推荐新增单测

可以补一个 mock 级别测试，验证：

* `start()` 后 `notifier` 注册的是 `_CANMessageListener`，不是 `self`
* `stop()` 调用时不会递归调用自身
* listener 的 `on_message_received()` 能正确转发给 communicator

---

## 输出要求

请直接修改代码并给出：

1. 修改后的关键 diff
2. 改动点说明
3. 是否存在兼容性影响
4. 建议的后续优化项

---

如果你愿意，我下一条可以直接给你一版“按这个 task 对应的参考补丁骨架”。
