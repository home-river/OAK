#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAN通信手动测试脚本

测试目标：
1. 测试CANCommunicator的坐标响应功能
2. 测试人员警报功能
3. 配合 tools/can_controller.py 观察实际通信效果

使用方法：
    # 终端1: 启动can_controller（接收端）
    python tools/can_controller.py
    
    # 终端2: 运行此测试脚本（发送端）
    python oak_vision_system/tests/manual/test_can_communication_manual.py

注意：
- 需要先配置CAN接口（can0或vcan0）
- 两个终端需要使用相同的CAN接口
- 可以在can_controller终端观察接收到的消息
"""

import os
import sys
import time
import threading
import numpy as np

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from oak_vision_system.modules.can_communication.can_communicator import CANCommunicator
from oak_vision_system.core.dto.config_dto.can_config_dto import CANConfigDTO
from oak_vision_system.modules.data_processing.decision_layer.types import PersonWarningStatus


class MockDecisionLayer:
    """模拟决策层 - 提供测试坐标"""
    
    def __init__(self):
        self._target_coords = None
        self._lock = threading.Lock()
        print("📦 MockDecisionLayer 已创建")
    
    def set_target_coords(self, coords: np.ndarray):
        """设置目标坐标"""
        with self._lock:
            self._target_coords = coords
            if coords is not None:
                print(f"   📍 设置坐标: X={coords[0]:.0f}mm, Y={coords[1]:.0f}mm, Z={coords[2]:.0f}mm")
    
    def get_target_coords_snapshot(self):
        """获取目标坐标快照"""
        with self._lock:
            return self._target_coords.copy() if self._target_coords is not None else None


class MockEventBus:
    """模拟事件总线 - 用于触发警报"""
    
    def __init__(self):
        self._subscribers = {}
        self._subscription_counter = 0
        print("📡 MockEventBus 已创建")
    
    def subscribe(self, event_type, callback, subscriber_name: str) -> str:
        """订阅事件"""
        subscription_id = f"sub_{self._subscription_counter}"
        self._subscription_counter += 1
        self._subscribers[subscription_id] = {
            'event_type': event_type,
            'callback': callback,
            'subscriber_name': subscriber_name
        }
        print(f"   ✅ {subscriber_name} 已订阅事件")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str):
        """取消订阅"""
        if subscription_id in self._subscribers:
            del self._subscribers[subscription_id]
    
    def publish_person_warning(self, status: PersonWarningStatus):
        """发布人员警报事件"""
        event_data = {
            'status': status,
            'timestamp': time.time()
        }
        
        status_text = "触发" if status == PersonWarningStatus.TRIGGERED else "清除"
        print(f"   🚨 发布人员警报事件: {status_text}")
        
        # 通知所有订阅者
        from oak_vision_system.core.event_bus.event_types import EventType
        for sub_info in self._subscribers.values():
            if sub_info['event_type'] == EventType.PERSON_WARNING:
                try:
                    sub_info['callback'](event_data)
                except Exception as e:
                    print(f"   ❌ 事件回调异常: {e}")


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_coordinate_response(communicator: CANCommunicator, decision_layer: MockDecisionLayer):
    """测试坐标响应功能"""
    print_section("测试1: 坐标响应功能")
    
    print("\n📝 说明:")
    print("   - 此测试会设置不同的坐标值")
    print("   - 在can_controller终端按 'r' 发送请求")
    print("   - 观察can_controller是否收到正确的坐标响应")
    
    # 测试用例
    test_cases = [
        (100, 200, 300, "基本坐标"),
        (1000, 2000, 3000, "较大坐标"),
        (-500, -1000, -1500, "负数坐标"),
        (32767, -32768, 0, "边界值坐标"),
        (0, 0, 0, "零坐标"),
    ]
    
    for x, y, z, description in test_cases:
        print(f"\n📍 设置坐标: {description}")
        coords = np.array([x, y, z], dtype=np.float32)
        decision_layer.set_target_coords(coords)
        
        print(f"   期望值: X={x}mm, Y={y}mm, Z={z}mm")
        print(f"   👉 请在can_controller终端按 'r' 发送请求")
        print(f"   👉 观察can_controller是否收到正确的坐标")
        
        input("   按 Enter 继续下一个测试...")


def test_person_alert(communicator: CANCommunicator, event_bus: MockEventBus):
    """测试人员警报功能"""
    print_section("测试2: 人员警报功能")
    
    print("\n📝 说明:")
    print("   - 此测试会触发和清除人员警报")
    print("   - 观察can_controller终端是否收到警报消息")
    print("   - 警报会以100ms间隔持续发送")
    
    # 测试1: 短时间警报
    print("\n🚨 测试1: 短时间警报 (3秒)")
    print("   👉 观察can_controller终端的警报消息")
    
    event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
    print("   ✅ 警报已触发，持续3秒...")
    
    time.sleep(3)
    
    event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
    print("   ✅ 警报已清除")
    
    time.sleep(1)
    
    # 测试2: 长时间警报
    print("\n🚨 测试2: 长时间警报 (10秒)")
    print("   👉 观察can_controller终端的警报消息")
    print("   👉 可以按 Ctrl+C 提前停止")
    
    try:
        event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
        print("   ✅ 警报已触发，持续10秒...")
        
        for i in range(10):
            time.sleep(1)
            print(f"   ⏱️  {i+1}/10 秒...")
        
        event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
        print("   ✅ 警报已清除")
        
    except KeyboardInterrupt:
        print("\n   ⚠️  警报测试被中断")
        event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
        print("   ✅ 警报已清除")


def test_mixed_scenario(communicator: CANCommunicator, decision_layer: MockDecisionLayer, event_bus: MockEventBus):
    """测试混合场景（坐标响应 + 警报）"""
    print_section("测试3: 混合场景")
    
    print("\n📝 说明:")
    print("   - 此测试会同时进行坐标响应和警报")
    print("   - 观察can_controller是否能同时接收两种消息")
    
    # 设置坐标
    coords = np.array([5000, 6000, 7000], dtype=np.float32)
    decision_layer.set_target_coords(coords)
    print(f"\n📍 设置坐标: X=5000mm, Y=6000mm, Z=7000mm")
    
    # 触发警报
    print("\n🚨 触发警报...")
    event_bus.publish_person_warning(PersonWarningStatus.TRIGGERED)
    
    print("\n👉 在警报期间，请在can_controller终端按 'r' 发送坐标请求")
    print("👉 观察是否能同时收到坐标响应和警报消息")
    print("👉 警报将持续5秒...")
    
    time.sleep(5)
    
    # 清除警报
    event_bus.publish_person_warning(PersonWarningStatus.CLEARED)
    print("\n✅ 警报已清除")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  CAN通信手动测试")
    print("=" * 70)
    
    print("\n📝 使用说明:")
    print("   1. 确保CAN接口已配置（can0或vcan0）")
    print("   2. 在另一个终端启动: python tools/can_controller.py")
    print("   3. 在can_controller终端观察接收到的消息")
    print("   4. 按照提示进行测试")
    
    # 配置参数
    print("\n⚙️  配置参数:")
    can_channel = input("   CAN接口 (默认: can0): ").strip() or 'can0'
    
    print(f"\n   使用接口: {can_channel}")
    print(f"   波特率: 250000")
    print(f"   警报间隔: 100ms")
    
    # 创建配置
    can_config = CANConfigDTO(
        enable_can=True,
        can_interface='socketcan',
        can_channel=can_channel,
        can_bitrate=250000,
        enable_auto_configure=False,  # 假设接口已配置
        sudo_password=None,
        alert_interval_ms=100,
        send_timeout_ms=50,
        receive_timeout_ms=10
    )
    
    # 创建模拟对象
    print("\n🔧 初始化组件...")
    decision_layer = MockDecisionLayer()
    event_bus = MockEventBus()
    
    # 创建CAN通信器
    print("\n🔧 创建CAN通信器...")
    communicator = CANCommunicator(
        config=can_config,
        decision_layer=decision_layer,
        event_bus=event_bus
    )
    
    # 启动通信器
    print("\n🚀 启动CAN通信器...")
    if not communicator.start():
        print("❌ CAN通信器启动失败")
        print("💡 请检查:")
        print("   1. CAN接口是否已配置")
        print("   2. 接口名称是否正确")
        print("   3. 是否有权限访问CAN接口")
        return
    
    print("✅ CAN通信器启动成功")
    
    try:
        input("\n按 Enter 键开始测试...")
        
        # 测试1: 坐标响应
        test_coordinate_response(communicator, decision_layer)
        
        # 测试2: 人员警报
        test_person_alert(communicator, event_bus)
        
        # 测试3: 混合场景
        test_mixed_scenario(communicator, decision_layer, event_bus)
        
        print_section("测试完成")
        print("\n✅ 所有测试已完成")
        print("💡 请检查can_controller终端的输出，确认消息接收正确")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 停止通信器
        print("\n🔌 停止CAN通信器...")
        communicator.stop()
        print("✅ CAN通信器已停止")
    
    print("\n" + "=" * 70)
    print("  测试结束")
    print("=" * 70)


if __name__ == "__main__":
    main()
