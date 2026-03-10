# 实施计划：修复 CANCommunicator 死锁问题

## 概述

重构 `CANCommunicator` 的 Listener 结构，通过分离 listener 职责消除 `Notifier.stop()` 导致的 `stop()` 重入死锁。

## 任务列表

- [ ] 1. 创建独立的私有 Listener 类
  - 在 `can_communicator.py` 中新增 `_CANMessageListener` 类
  - 实现消息转发和轻量级 `stop()` 方法
  - 确保不会调用 `communicator.stop()` 造成重入
  - _需求: 消除死锁重入链_

- [ ] 2. 重构 CANCommunicator 类定义
  - 移除对 `can.Listener` 的直接继承
  - 删除 `can.Listener.__init__(self)` 调用
  - 更新类文档字符串，移除"直接继承 can.Listener"的描述
  - _需求: 分离职责_

- [ ] 3. 修改 CANCommunicator 初始化
  - 在 `__init__()` 中添加 `_listener` 成员变量
  - 保持现有的其他成员变量不变
  - _需求: 支持独立 listener_

- [ ] 4. 重构 start() 方法
  - 修改 Notifier 创建逻辑，使用独立 listener
  - 更新相关注释和文档字符串
  - 保持其他启动流程不变
  - _需求: 使用新的 listener 架构_

- [ ] 5. 增强 stop() 方法
  - 在资源清理中添加 `_listener` 引用清理
  - 保持现有的停止顺序和逻辑
  - 确保所有资源正确释放
  - _需求: 完整的资源清理_

- [ ] 6. 保留现有业务处理方法
  - 保持 `on_message_received()` 方法作为内部业务入口
  - 确保坐标请求和警报功能不受影响
  - _需求: 业务逻辑兼容性_

- [ ] 7. 验证修复效果
  - 运行手动测试脚本验证功能正常
  - 确认 stop() 不再出现死锁
  - 检查日志中不再有重入调用
  - _需求: 功能验收_

## 注意事项

- 保持对外接口完全兼容
- 最小化业务逻辑改动
- 确保线程安全
- 完整的异常处理