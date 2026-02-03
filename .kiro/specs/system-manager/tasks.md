# Implementation Plan: SystemManager（简化版）

## Overview

本文档定义了 SystemManager（简化版）的实现任务。所有任务都基于 `requirements.md` 和 `design.md` 中定义的需求和设计。

**实现原则：**
- 按任务顺序逐步实现
- 每个任务完成后编写测试验证
- 保持代码简洁清晰
- 遵循设计文档中的架构

---

## Tasks

- [x] 1. 创建基础数据结构
  - 在 `oak_vision_system/core/system_manager/data_structures.py` 中创建 `ModuleState` 枚举（4个状态）
  - 创建 `ManagedModule` 数据类（name, instance, priority, state）
  - 创建 `ShutdownEvent` 数据类（reason）
  - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.2, 4.3_

- [x] 2. 实现 SystemManager 初始化
  - [x] 2.1 实现 `__init__` 方法接受参数（event_bus, system_config, default_stop_timeout）
    - 初始化日志系统（如果提供 system_config）
    - 初始化内部数据结构（_modules, _shutdown_event, _stop_started）
    - _Requirements: 11.1, 11.2, 11.4, 11.5, 15.1, 15.2, 15.3_
  
  - [x] 2.2 订阅 SYSTEM_SHUTDOWN 事件
    - 使用 `self._event_bus.subscribe("SYSTEM_SHUTDOWN", self._on_shutdown_event, ...)`
    - _Requirements: 5.1_
  
  - [x] 2.3 安装异常钩子
    - 使用 `attach_exception_logger(..., ignore_keyboard_interrupt=True)`
    - 保存句柄到 `self._exception_handle`
    - _Requirements: 16.1, 16.2, 16.3, 16.4_

- [x] 3. 实现模块注册功能
  - [x] 3.1 实现 `register_module` 方法
    - 检查模块名称是否已存在，如果存在抛出 ValueError
    - 创建 ManagedModule 对象（state = NOT_STARTED）
    - 存储到 `self._modules` 字典
    - 记录注册日志
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 13.1_
  
  - [x] 3.2 为模块注册编写单元测试

    - 测试成功注册单个模块
    - 测试注册多个模块
    - 测试重复注册抛出异常
    - 测试模块初始状态为 NOT_STARTED
    - 验证日志记录
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 4. 实现模块启动功能
  - [x] 4.1 实现 `start_all` 方法
    - 按优先级降序排序模块（优先级高的先启动）
    - 遍历模块并启动：记录日志 → 调用 start() → 设置状态为 RUNNING
    - 如果启动失败：捕获异常 → 设置状态为 ERROR → 调用回滚 → 重新抛出异常
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 13.2_
  
  - [x] 4.2 为模块启动编写单元测试

    - 测试启动单个模块
    - 测试启动多个模块
    - 测试启动成功后状态为 RUNNING
    - 验证日志记录
    - _Requirements: 2.1, 2.3, 2.4, 2.5_
  
  - [x] 4.3 编写属性测试：模块启动顺序遵循优先级

    - **Property 1: Module startup order follows priority**
    - *For any* 模块集合，启动顺序应该按优先级从高到低
    - **Validates: Requirements 2.2**

- [x] 5. 实现启动失败回滚
  - [x] 5.1 实现 `_rollback_startup` 私有方法
    - 按相反顺序遍历已启动的模块
    - 对每个模块：记录回滚日志 → 调用 stop() → 设置状态为 STOPPED
    - 捕获异常并记录错误（不抛出）
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 13.4_
  
  - [x] 5.2 为启动回滚编写单元测试

    - 测试启动失败触发回滚
    - 测试回滚按相反顺序执行
    - 测试回滚后模块状态为 STOPPED
    - 测试回滚中的异常不阻塞其他模块
    - 验证日志记录
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. 实现事件处理回调
  - [x] 6.1 实现 `_on_shutdown_event` 方法
    - 获取停止原因：`reason = getattr(event, 'reason', 'unknown')`
    - 记录日志（INFO 级别，包含 reason）
    - 设置退出标志：`self._shutdown_event.set()`
    - **重要**：只做置位操作，不执行其他复杂逻辑
    - _Requirements: 5.2, 5.3, 5.4, 13.3_
  
  - [x] 6.2 为事件处理编写单元测试

    - 测试接收 SYSTEM_SHUTDOWN 事件
    - 测试 _shutdown_event 被正确设置
    - 测试日志记录包含 reason
    - 测试方法不抛出异常
    - _Requirements: 5.2, 5.3, 5.4_

- [x] 7. 实现主循环和退出控制
  - [x] 7.1 实现 `run` 方法
    - 使用 `try-except-finally` 结构
    - try 块：主循环等待退出信号（`while not self._shutdown_event.is_set(): self._shutdown_event.wait(timeout=0.5)`）
    - except KeyboardInterrupt 块：记录日志
    - finally 块：统一调用 `shutdown()`（检查 `_stop_started` 防止重复）
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [x] 7.2 为主循环编写单元测试

    - 测试主循环阻塞（使用线程）
    - 测试 SYSTEM_SHUTDOWN 事件触发退出
    - 测试 finally 块调用 shutdown()
    - 验证日志记录
    - _Requirements: 6.3, 6.4, 6.6, 7.2, 7.3, 7.5, 7.6_

- [x] 8. Checkpoint - 确保核心功能正常
  - 确保所有测试通过
  - 如有问题请询问用户

- [x] 9. 实现模块关闭功能
  - [x] 9.1 实现 `shutdown` 方法
    - 防重复关闭检查：检查 `_stop_started`，如果已设置则直接返回
    - 设置 `_stop_started` 标志
    - 按优先级升序排序模块（优先级低的先关闭）
    - 遍历模块并关闭：跳过非 RUNNING 状态 → 记录日志 → 调用 stop() → 设置状态为 STOPPED
    - 捕获异常并记录错误（不抛出）
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 13.2, 13.4_
  
  - [x] 9.2 关闭事件总线
    - 调用 `self._event_bus.close(wait=True, cancel_pending=False)`
    - 捕获异常并记录错误（不抛出）
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [x] 9.3 恢复异常钩子
    - 调用 `self._exception_handle.detach()`
    - 捕获异常并记录错误（不抛出）
    - _Requirements: 16.5_
  
  - [x] 9.4 为模块关闭编写单元测试

    - 测试关闭单个模块
    - 测试关闭多个模块
    - 测试防重复关闭
    - 测试关闭失败不阻塞其他模块
    - 测试事件总线关闭
    - 验证日志记录
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.4_
  
  - [x] 9.5 编写属性测试：模块关闭顺序遵循优先级

    - **Property 2: Module shutdown order follows priority**
    - *For any* 模块集合，关闭顺序应该按优先级从低到高
    - **Validates: Requirements 8.2**

- [x] 10. 实现状态查询功能
  - [x] 10.1 实现 `get_status` 方法
    - 返回字典：模块名称 → 状态字符串
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [x] 10.2 实现 `is_shutting_down` 方法
    - 返回 `self._stop_started.is_set()`
    - _Requirements: 12.4, 12.5_
  
  - [x] 10.3 为状态查询编写单元测试

    - 测试 get_status 返回正确状态
    - 测试 is_shutting_down 在不同阶段的返回值
    - 测试状态字符串格式
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 11. 实现上下文管理器
  - [x] 11.1 实现 `__enter__` 和 `__exit__` 方法
    - `__enter__`：调用 `start_all()` 并返回 self
    - `__exit__`：调用 `shutdown()` 并返回 False
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [x] 11.2 为上下文管理器编写单元测试

    - 测试 with 语句自动启动模块
    - 测试 with 语句自动关闭模块
    - 测试异常不被抑制
    - _Requirements: 14.3, 14.4, 14.5_

- [x] 12. 更新文档和导出
  - [x] 12.1 更新 `__init__.py` 导出所有公共类
    - 导出 SystemManager、ModuleState、ManagedModule、ShutdownEvent
    - 添加模块级文档字符串
    - 确保类型注解完整
    - _Requirements: 所有需求_

- [ ] 13. 创建使用示例
  - [ ] 13.1 创建 `examples/system_manager_example.py`
    - 基本用法（注册、启动、运行、关闭）
    - 使用上下文管理器
    - 多模块场景
    - 状态查询
    - 日志配置
    - 演示两个退出出口
    - _Requirements: 所有需求_

- [x] 14. 编写集成测试
  - [x] 14.1 创建集成测试文件
    - 测试完整生命周期
    - 测试 KeyboardInterrupt 退出
    - 测试 SYSTEM_SHUTDOWN 事件退出
    - 测试多模块场景
    - 测试启动失败场景
    - 测试关闭失败场景
    - _Requirements: 所有需求_

- [ ] 15. Final Checkpoint - 确保所有测试通过
  - 确保所有测试通过
  - 如有问题请询问用户

---

## Notes

**不要实现的功能：**
- ❌ 信号处理器（signal.signal）
- ❌ SIGTERM 支持
- ❌ 异常钩子触发退出
- ❌ 关闭回调机制
- ❌ 复杂的超时处理

**使用已有工具：**
- ✅ `oak_vision_system.utils.logging_utils.configure_logging`
- ✅ `oak_vision_system.utils.logging_utils.attach_exception_logger`
- ✅ `oak_vision_system.core.event_bus.EventBus`

**后续适配工作**（不在本次实现范围）：
- 子模块 `stop()` 方法规范化
- 显示模块 'q' 键退出逻辑修改

**代码风格：**
- 使用类型注解
- 添加文档字符串
- 遵循 PEP 8
- 保持代码简洁

---

## Summary

本任务列表定义了 SystemManager（简化版）的完整实现计划：

- **15个主要任务**
- **包含可选的测试子任务**（标记为 `*`）
- **2个检查点**
- **清晰的实现顺序**
- **完整的测试策略**

预计代码量：~200行（不含测试），相比之前的实现减少约60%。
