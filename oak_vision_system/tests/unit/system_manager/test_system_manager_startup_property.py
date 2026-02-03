"""
SystemManager 模块启动属性测试

使用属性测试（Property-Based Testing）验证模块启动顺序的正确性。

Property 1: Module startup order follows priority
*For any* 模块集合，启动顺序应该按优先级从高到低

Requirements: 2.2
"""

import pytest
from hypothesis import given, strategies as st, settings
from oak_vision_system.core.system_manager import SystemManager, ModuleState
from oak_vision_system.core.event_bus import EventBus


class OrderTrackingModule:
    """用于跟踪启动顺序的模拟模块"""
    
    # 类级别的启动顺序记录器
    _startup_order = []
    
    @classmethod
    def reset_order(cls):
        """重置启动顺序记录"""
        cls._startup_order = []
    
    @classmethod
    def get_order(cls):
        """获取启动顺序"""
        return cls._startup_order.copy()
    
    def __init__(self, name: str, priority: int):
        self.name = name
        self.priority = priority
        self._running = False
    
    def start(self):
        """启动模块并记录启动顺序"""
        OrderTrackingModule._startup_order.append((self.name, self.priority))
        self._running = True
    
    def stop(self):
        """停止模块"""
        self._running = False
    
    def is_running(self):
        """检查模块是否运行中"""
        return self._running


class TestSystemManagerStartupProperty:
    """SystemManager 模块启动属性测试套件"""
    
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
    def test_module_startup_order_follows_priority(self, modules):
        """
        **Property 1: Module startup order follows priority**
        
        *For any* 模块集合，启动顺序应该按优先级从高到低
        
        **Validates: Requirements 2.2**
        
        测试策略：
        1. 生成随机的模块集合（名称和优先级）
        2. 注册所有模块到 SystemManager
        3. 启动所有模块
        4. 验证启动顺序是否按优先级从高到低
        
        Args:
            modules: 模块列表，每个元素是 (name, priority) 元组
        """
        # 重置启动顺序记录
        OrderTrackingModule.reset_order()
        
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册所有模块
        module_instances = []
        for name, priority in modules:
            module = OrderTrackingModule(name, priority)
            module_instances.append(module)
            manager.register_module(name, module, priority)
        
        # 启动所有模块
        manager.start_all()
        
        # 获取实际启动顺序
        actual_order = OrderTrackingModule.get_order()
        
        # 计算期望的启动顺序（按优先级从高到低）
        expected_order = sorted(modules, key=lambda x: x[1], reverse=True)
        
        # 验证启动顺序
        assert len(actual_order) == len(expected_order), \
            f"启动的模块数量不匹配: 期望 {len(expected_order)}, 实际 {len(actual_order)}"
        
        # 逐个验证启动顺序
        for i, (actual, expected) in enumerate(zip(actual_order, expected_order)):
            actual_name, actual_priority = actual
            expected_name, expected_priority = expected
            
            assert actual_name == expected_name, \
                f"位置 {i}: 模块名称不匹配, 期望 {expected_name}, 实际 {actual_name}"
            
            assert actual_priority == expected_priority, \
                f"位置 {i}: 优先级不匹配, 期望 {expected_priority}, 实际 {actual_priority}"
        
        # 验证优先级是降序排列的
        priorities = [priority for _, priority in actual_order]
        for i in range(len(priorities) - 1):
            assert priorities[i] >= priorities[i + 1], \
                f"优先级不是降序: 位置 {i} 的优先级 {priorities[i]} < 位置 {i+1} 的优先级 {priorities[i+1]}"
        
        # 验证所有模块都启动成功
        for module in module_instances:
            assert module.is_running(), f"模块 {module.name} 未启动"
        
        # 验证所有模块状态都为 RUNNING
        for name, _ in modules:
            assert manager._modules[name].state == ModuleState.RUNNING, \
                f"模块 {name} 状态不是 RUNNING"


class TestSystemManagerStartupPropertyEdgeCases:
    """SystemManager 模块启动属性测试 - 边界情况"""
    
    @given(
        # 生成所有模块具有相同优先级的情况
        priority=st.integers(min_value=-100, max_value=100),
        num_modules=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_modules_with_same_priority(self, priority, num_modules):
        """
        测试所有模块具有相同优先级的情况
        
        验证：
        - 所有模块都能成功启动
        - 启动顺序稳定（虽然优先级相同）
        
        **Validates: Requirements 2.2**
        """
        # 重置启动顺序记录
        OrderTrackingModule.reset_order()
        
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册所有模块（相同优先级）
        module_instances = []
        for i in range(num_modules):
            name = f"module_{i}"
            module = OrderTrackingModule(name, priority)
            module_instances.append(module)
            manager.register_module(name, module, priority)
        
        # 启动所有模块
        manager.start_all()
        
        # 获取实际启动顺序
        actual_order = OrderTrackingModule.get_order()
        
        # 验证所有模块都启动了
        assert len(actual_order) == num_modules
        
        # 验证所有模块的优先级都相同
        for _, actual_priority in actual_order:
            assert actual_priority == priority
        
        # 验证所有模块都启动成功
        for module in module_instances:
            assert module.is_running()
    
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
    def test_modules_with_mixed_priorities(self, modules):
        """
        测试包含负数、零、正数优先级的混合情况
        
        验证：
        - 负数优先级的模块最后启动
        - 零优先级的模块在中间启动
        - 正数优先级的模块最先启动
        
        **Validates: Requirements 2.2**
        """
        # 重置启动顺序记录
        OrderTrackingModule.reset_order()
        
        # 创建 SystemManager（使用独立的 EventBus）
        event_bus = EventBus()
        manager = SystemManager(event_bus=event_bus)
        
        # 注册所有模块
        for name, priority in modules:
            module = OrderTrackingModule(name, priority)
            manager.register_module(name, module, priority)
        
        # 启动所有模块
        manager.start_all()
        
        # 获取实际启动顺序
        actual_order = OrderTrackingModule.get_order()
        
        # 验证启动顺序是降序的
        priorities = [priority for _, priority in actual_order]
        for i in range(len(priorities) - 1):
            assert priorities[i] >= priorities[i + 1], \
                f"优先级不是降序: {priorities[i]} < {priorities[i+1]}"
        
        # 验证正数优先级的模块在负数优先级的模块之前启动
        positive_indices = [i for i, (_, p) in enumerate(actual_order) if p > 0]
        negative_indices = [i for i, (_, p) in enumerate(actual_order) if p < 0]
        
        if positive_indices and negative_indices:
            max_positive_index = max(positive_indices)
            min_negative_index = min(negative_indices)
            assert max_positive_index < min_negative_index, \
                "正数优先级的模块应该在负数优先级的模块之前启动"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
