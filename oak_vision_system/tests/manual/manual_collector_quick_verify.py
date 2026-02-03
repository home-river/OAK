#!/usr/bin/env python3
"""
OAK数据采集器快速验证测试

用途：
- 快速验证OAK设备连接和基本数据采集功能
- 适合开发过程中的快速测试和验证
- 提供简洁的测试结果输出

测试内容：
1. 设备发现测试
2. 基本数据采集测试（10秒）
3. 数据完整性验证

运行方式：
    python oak_vision_system/tests/manual/test_collector_quick_verify.py

作者：OAK Vision System
"""

import sys
import time
from pathlib import Path
from typing import List, Any

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import depthai as dai
except ImportError as e:
    print(f"错误: 缺少depthai库: {e}")
    print("请运行: pip install depthai")
    sys.exit(1)

from oak_vision_system.modules.data_collector.collector import OAKDataCollector
from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
from oak_vision_system.core.dto.config_dto import (
    OAKModuleConfigDTO,
    OAKConfigDTO,
    DeviceRoleBindingDTO,
    DeviceRole,
)
from oak_vision_system.core.event_bus import EventBus, EventType, reset_event_bus
from oak_vision_system.core.dto import VideoFrameDTO, DeviceDetectionDataDTO


class QuickTestCollector:
    """快速测试数据收集器"""
    
    def __init__(self):
        self.frame_count = 0
        self.detection_count = 0
        self.device_frames = {}
        self.device_detections = {}
        self.start_time = None
    
    def handle_frame(self, frame_data: VideoFrameDTO):
        """处理视频帧"""
        self.frame_count += 1
        device_id = frame_data.device_id
        self.device_frames[device_id] = self.device_frames.get(device_id, 0) + 1
    
    def handle_detection(self, detection_data: DeviceDetectionDataDTO):
        """处理检测数据"""
        self.detection_count += 1
        device_id = detection_data.device_id
        self.device_detections[device_id] = self.device_detections.get(device_id, 0) + 1
    
    def get_stats(self):
        """获取统计信息"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        fps = self.frame_count / elapsed if elapsed > 0 else 0
        return {
            'elapsed': elapsed,
            'frames': self.frame_count,
            'detections': self.detection_count,
            'fps': fps,
            'device_frames': dict(self.device_frames),
            'device_detections': dict(self.device_detections)
        }


def discover_devices() -> List[Any]:
    """发现设备"""
    print("🔍 正在扫描OAK设备...")
    try:
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        if devices:
            print(f"✅ 发现 {len(devices)} 个设备")
            for i, device in enumerate(devices, 1):
                print(f"  [{i}] {device.mxid} ({device.product_name or '未知'})")
                print(f"      连接状态: {device.connection_status.value}")
                print(f"      MXID长度: {len(device.mxid)} 字符")
        else:
            print("❌ 未发现任何OAK设备")
        return devices
    except Exception as e:
        print(f"❌ 设备发现失败: {e}")
        return []


def create_quick_config(devices: List[Any]) -> OAKModuleConfigDTO:
    """创建快速测试配置"""
    if not devices:
        raise ValueError("没有可用的设备")
    
    # 查找模型文件
    model_paths = [
        "assets/test_config/yolov8.blob",
        "assets/example_config/mobilenet-ssd_openvino_2021.4_6shave.blob",
        "models/mobilenet-ssd_openvino_2021.4_6shave.blob",
    ]
    
    model_path = "assets/test_config/yolov8.blob"  # 默认路径
    for path in model_paths:
        if Path(path).exists():
            model_path = path
            break
    
    # 使用第一个设备
    device = devices[0]
    
    config = OAKModuleConfigDTO(
        hardware_config=OAKConfigDTO(
            model_path=model_path,
            confidence_threshold=0.5,
            hardware_fps=20,
            enable_depth_output=False,  # 快速测试不启用深度
            queue_max_size=4,
            queue_blocking=False,
        ),
        role_bindings={
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid=device.mxid,
            ),
        },
        device_metadata={
            device.mxid: device,
        },
    )
    
    return config


def run_quick_test():
    """运行快速测试"""
    print("="*50)
    print("🚀 OAK数据采集器快速验证测试")
    print("="*50)
    
    # 1. 设备发现测试
    print("\n📋 步骤 1: 设备发现测试")
    devices = discover_devices()
    if not devices:
        print("❌ 测试失败: 未发现设备")
        return False
    
    # 等待设备完全释放
    print("⏳ 等待设备完全释放...")
    time.sleep(3)  # 等待3秒确保设备发现阶段的连接完全释放
    print("✅ 设备释放等待完成")
    
    # 2. 配置创建
    print("\n📋 步骤 2: 创建测试配置")
    try:
        config = create_quick_config(devices)
        print(f"✅ 配置创建成功")
        print(f"   设备MXID: {devices[0].mxid}")
        print(f"   设备状态: {devices[0].connection_status.value}")
        print(f"   模型路径: {config.hardware_config.model_path}")
    except Exception as e:
        print(f"❌ 配置创建失败: {e}")
        return False
    
    # 3. 数据采集测试
    print("\n📋 步骤 3: 数据采集测试")
    
    # 重置事件总线
    reset_event_bus()
    event_bus = EventBus()
    
    # 创建测试收集器
    test_collector = QuickTestCollector()
    event_bus.subscribe(EventType.RAW_FRAME_DATA, test_collector.handle_frame)
    event_bus.subscribe(EventType.RAW_DETECTION_DATA, test_collector.handle_detection)
    
    # 创建并启动collector
    try:
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        result = collector.start()
        
        if not result["started"]:
            print(f"❌ 采集启动失败: {result}")
            return False
        
        print("✅ 采集已启动")
        print("⏱️  运行10秒测试...")
        
        # 记录开始时间
        test_collector.start_time = time.time()
        
        # 运行10秒
        for i in range(10):
            time.sleep(1)
            stats = test_collector.get_stats()
            print(f"   {i+1:2d}s: 帧={stats['frames']:3d}, 检测={stats['detections']:3d}, FPS={stats['fps']:5.1f}")
        
        # 停止采集
        collector.stop()
        print("✅ 采集已停止")
        
    except Exception as e:
        print(f"❌ 采集测试失败: {e}")
        return False
    
    # 4. 结果验证
    print("\n📋 步骤 4: 结果验证")
    stats = test_collector.get_stats()
    
    success = True
    
    # 检查视频帧
    if stats['frames'] > 0:
        print(f"✅ 视频帧采集: {stats['frames']} 帧")
    else:
        print("❌ 视频帧采集: 无数据")
        success = False
    
    # 检查检测数据
    if stats['detections'] > 0:
        print(f"✅ 检测数据采集: {stats['detections']} 个")
    else:
        print("❌ 检测数据采集: 无数据")
        success = False
    
    # 检查帧率
    if stats['fps'] > 5.0:
        print(f"✅ 采集帧率: {stats['fps']:.1f} fps")
    else:
        print(f"⚠️  采集帧率: {stats['fps']:.1f} fps (偏低)")
    
    # 5. 测试总结
    print("\n" + "="*50)
    print("📋 测试总结")
    print("="*50)
    print(f"运行时间: {stats['elapsed']:.1f} 秒")
    print(f"总帧数: {stats['frames']}")
    print(f"总检测数: {stats['detections']}")
    print(f"平均帧率: {stats['fps']:.1f} fps")
    
    if success:
        print("\n🎉 快速验证测试通过!")
        print("   OAK设备连接正常，数据采集功能正常")
    else:
        print("\n❌ 快速验证测试失败!")
        print("   请检查设备连接和模型文件")
    
    return success


if __name__ == '__main__':
    try:
        success = run_quick_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  用户中断测试")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
        sys.exit(1)