"""
SystemManager 模块关闭属性测试

使用属性测试（Property-Based Testing）验证模块关闭顺序的正确性。

Property 2: Module shutdown order follows priority
*For any* 模块集合，关闭顺序应该按优先级从低到高

Requirements: 8.2
"""

import pytest
from hypothesis import given, strategies as st, settings
from oak_vision_system.core.system_manager import SystemManager, ModuleState
from oak_vision_system.core.event_bus import EventBus


class ShutdownOrderTrackingModule:
    """用于跟踪关闭顺序的模拟模块"""
    
    # 类级别的关闭顺序记录器
    _shutdown_order = []
    
    @classmethod
    def reset_order(cls):
        """重置关闭顺序记录"""
        cls._shutdown_order = []
    
    @classmethod
    def get_order(cls):
        """获取关闭顺序"""
        return cls._shutdown_order.copy()
    
    def __init__(self, name: str, priority: int):
        self.name = name
        self.priority = priority
        self._running = False
    
    def start(self):
        """启动模块"""
        self._running = True
    
    def stop(self):
        """停止模块并记录关闭顺序"""
        ShutdownOrderTrackingModule._shutdown_order.append((self.name, self.priority))
        self._running = False
    
    def is_running(self):
        """检查模块是否运行中"""
        return self._running


class TestSystemManagerShutdownProperty:
    """SystemManager 模块关闭属性测试套件"""
    
    @given(
        # 生成模块列表：每个模块有名称和优先级
        # 名称：使用字母和数字组合，确保唯一性
        # 优先级：使用整数范围 -100 到 100
        modules=st.lists(
            st.tuples(
                st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=1, max_size=20),
                st.integers(min_value=-100, max_value=100)
            ),
            min_size=1,  # 至少1个模块
            max_size=20,  # 最多20个模块
            unique_by=lambda x: x[0]  # 确保模块名称唯一
        )
    )
    @settings(max_examples=100)  # 运行100次测试
    def test_module_shutdown_order_follows_priority(self, modules):
        """
        **Property 2: Module shutdown order follows priority**
        
        *For any* 模块集合，关闭顺序应该按优先级从低到高
        
        **Validates: Requirements 8.2**
        
        测试策略：
        1. 生成随机的模块集合（名称和优先级）
        2. 注册所有模块到 SystemManager
        3. 启动所有模块
        4. 关闭所有模块
        5. 验证关闭顺序是否按优先级从低到高
        
        Args:
            modules: 模块列表，每个元素是 (name, priority) 元组
        """
        # 重置关闭顺序记录
        ShutdownOrderTrackingModule.reset_order()
        
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册所有模块
        module_instances = []
        for name, priority in modules:
            module = ShutdownOrderTrackingModule(name, priority)
            module_instances.append(module)
            manager.register_module(name, module, priority)
        
        # 启动所有模块
        manager.start_all()
        
        # 验证所有模块都启动成功
        for module in module_instances:
            assert module.is_running(), f"模块 {module.name} 未启动"
        
        # 关闭所有模块
        manager.shutdown()
        
        # 获取实际关闭顺序
        actual_order = ShutdownOrderTrackingModule.get_order()
        
        # 计算期望的关闭顺序（按优先级从低到高）
        expected_order = sorted(modules, key=lambda x: x[1])  # 升序排序
        
        # 验证关闭顺序
        assert len(actual_order) == len(expected_order), \
            f"关闭的模块数量不匹配: 期望 {len(expected_order)}, 实际 {len(actual_order)}"
        
        # 逐个验证关闭顺序
        for i, (actual, expected) in enumerate(zip(actual_order, expected_order)):
            actual_name, actual_priority = actual
            expected_name, expected_priority = expected
            
            assert actual_name == expected_name, \
                f"位置 {i}: 模块名称不匹配, 期望 {expected_name}, 实际 {actual_name}"
            
            assert actual_priority == expected_priority, \
                f"位置 {i}: 优先级不匹配, 期望 {expected_priority}, 实际 {actual_priority}"
        
        # 验证优先级是升序排列的
        priorities = [priority for _, priority in actual_order]
        for i in range(len(priorities) - 1):
            assert priorities[i] <= priorities[i + 1], \
                f"优先级不是升序: 位置 {i} 的优先级 {priorities[i]} > 位置 {i+1} 的优先级 {priorities[i+1]}"
        
        # 验证所有模块都停止成功
        for module in module_instances:
            assert not module.is_running(), f"模块 {module.name} 未停止"
        
        # 验证所有模块状态都为 STOPPED
        for name, _ in modules:
            assert manager._modules[name].state == ModuleState.STOPPED, \
                f"模块 {name} 状态不是 STOPPED"


class TestSystemManagerShutdownPropertyEdgeCases:
    """SystemManager 模块关闭属性测试 - 边界情况"""
    
    @given(
        # 生成所有模块具有相同优先级的情况
        priority=st.integers(min_value=-100, max_value=100),
        num_modules=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_modules_with_same_priority_shutdown(self, priority, num_modules):
        """
        测试所有模块具有相同优先级的关闭情况
        
        验证：
        - 所有模块都能成功关闭
        - 关闭顺序稳定（虽然优先级相同）
        
        **Validates: Requirements 8.2**
        """
        # 重置关闭顺序记录
        ShutdownOrderTrackingModule.reset_order()
        
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册所有模块（相同优先级）
        module_instances = []
        for i in range(num_modules):
            name = f"module_{i}"
            module = ShutdownOrderTrackingModule(name, priority)
            module_instances.append(module)
            manager.register_module(name, module, priority)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭所有模块
        manager.shutdown()
        
        # 获取实际关闭顺序
        actual_order = ShutdownOrderTrackingModule.get_order()
        
        # 验证所有模块都关闭了
        assert len(actual_order) == num_modules
        
        # 验证所有模块的优先级都相同
        for _, actual_priority in actual_order:
            assert actual_priority == priority
        
        # 验证所有模块都停止成功
        for module in module_instances:
            assert not module.is_running()
    
    @given(
        # 生成包含负数、零、正数优先级的混合情况
        modules=st.lists(
            st.tuples(
                st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=10),
                st.sampled_from([-100, -50, -10, -1, 0, 1, 10, 50, 100])
            ),
            min_size=3,
            max_size=10,
            unique_by=lambda x: x[0]
        )
    )
    @settings(max_examples=50)
    def test_modules_with_mixed_priorities_shutdown(self, modules):
        """
        测试包含负数、零、正数优先级的混合关闭情况
        
        验证：
        - 负数优先级的模块最先关闭
        - 零优先级的模块在中间关闭
        - 正数优先级的模块最后关闭
        
        **Validates: Requirements 8.2**
        """
        # 重置关闭顺序记录
        ShutdownOrderTrackingModule.reset_order()
        
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册所有模块
        for name, priority in modules:
            module = ShutdownOrderTrackingModule(name, priority)
            manager.register_module(name, module, priority)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭所有模块
        manager.shutdown()
        
        # 获取实际关闭顺序
        actual_order = ShutdownOrderTrackingModule.get_order()
        
        # 验证关闭顺序是升序的
        priorities = [priority for _, priority in actual_order]
        for i in range(len(priorities) - 1):
            assert priorities[i] <= priorities[i + 1], \
                f"优先级不是升序: {priorities[i]} > {priorities[i+1]}"
        
        # 验证负数优先级的模块在正数优先级的模块之前关闭
        negative_indices = [i for i, (_, p) in enumerate(actual_order) if p < 0]
        positive_indices = [i for i, (_, p) in enumerate(actual_order) if p > 0]
        
        if negative_indices and positive_indices:
            max_negative_index = max(negative_indices)
            min_positive_index = min(positive_indices)
            assert max_negative_index < min_positive_index, \
                "负数优先级的模块应该在正数优先级的模块之前关闭"
    
    @given(
        # 生成启动和关闭顺序应该相反的情况
        modules=st.lists(
            st.tuples(
                st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=10),
                st.integers(min_value=1, max_value=100)
            ),
            min_size=2,
            max_size=10,
            unique_by=lambda x: x[0]
        ).filter(lambda mods: len(set(p for _, p in mods)) == len(mods))  # 确保所有优先级都不同
    )
    @settings(max_examples=50)
    def test_shutdown_order_is_reverse_of_startup(self, modules):
        """
        测试关闭顺序是启动顺序的反向
        
        验证：
        - 启动顺序：优先级从高到低
        - 关闭顺序：优先级从低到高
        - 关闭顺序 = 启动顺序的反向
        
        **Validates: Requirements 8.2**
        """
        # 创建一个同时跟踪启动和关闭顺序的模块
        class DualTrackingModule:
            _startup_order = []
            _shutdown_order = []
            
            @classmethod
            def reset_order(cls):
                cls._startup_order = []
                cls._shutdown_order = []
            
            def __init__(self, name: str, priority: int):
                self.name = name
                self.priority = priority
                self._running = False
            
            def start(self):
                DualTrackingModule._startup_order.append(self.name)
                self._running = True
            
            def stop(self):
                DualTrackingModule._shutdown_order.append(self.name)
                self._running = False
        
        # 重置顺序记录
        DualTrackingModule.reset_order()
        
        # 创建独立的事件总线和 SystemManager
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册所有模块
        for name, priority in modules:
            module = DualTrackingModule(name, priority)
            manager.register_module(name, module, priority)
        
        # 启动所有模块
        manager.start_all()
        
        # 关闭所有模块
        manager.shutdown()
        
        # 获取启动和关闭顺序
        startup_order = DualTrackingModule._startup_order
        shutdown_order = DualTrackingModule._shutdown_order
        
        # 验证关闭顺序是启动顺序的反向
        assert shutdown_order == list(reversed(startup_order)), \
            f"关闭顺序不是启动顺序的反向:\n启动: {startup_order}\n关闭: {shutdown_order}\n期望: {list(reversed(startup_order))}"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
