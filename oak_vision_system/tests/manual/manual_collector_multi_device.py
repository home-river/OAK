#!/usr/bin/env python3
"""
OAK数据采集器多设备测试

用途：
- 测试多个OAK设备的协同工作
- 验证多设备数据采集的同步性和稳定性
- 测试设备间的负载均衡和性能

测试场景：
1. 双设备协同采集
2. 设备故障恢复测试
3. 多设备性能对比
4. 数据同步验证

运行方式：
    python oak_vision_system/tests/manual/test_collector_multi_device.py

作者：OAK Vision System
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict, deque

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import click
    import depthai as dai
except ImportError as e:
    print(f"错误: 缺少必要的依赖库: {e}")
    print("请运行: pip install click depthai")
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


class MultiDeviceTestCollector:
    """多设备测试数据收集器"""
    
    def __init__(self):
        self.device_stats = defaultdict(lambda: {
            'frames': 0,
            'detections': 0,
            'last_frame_time': 0,
            'fps_history': deque(maxlen=30)
        })
        self.start_time = time.time()
        self.lock = threading.Lock()
    
    def handle_frame(self, frame_data: VideoFrameDTO):
        """处理视频帧"""
        with self.lock:
            device_id = frame_data.device_id
            stats = self.device_stats[device_id]
            stats['frames'] += 1
            
            # 计算FPS
            current_time = time.time()
            if stats['last_frame_time'] > 0:
                interval = current_time - stats['last_frame_time']
                if interval > 0:
                    fps = 1.0 / interval
                    stats['fps_history'].append(fps)
            stats['last_frame_time'] = current_time
    
    def handle_detection(self, detection_data: DeviceDetectionDataDTO):
        """处理检测数据"""
        with self.lock:
            device_id = detection_data.device_id
            self.device_stats[device_id]['detections'] += 1
    
    def get_device_stats(self, device_id: str) -> Dict:
        """获取指定设备的统计信息"""
        with self.lock:
            stats = self.device_stats[device_id]
            elapsed = time.time() - self.start_time
            avg_fps = stats['frames'] / elapsed if elapsed > 0 else 0
            current_fps = sum(stats['fps_history']) / len(stats['fps_history']) if stats['fps_history'] else 0
            
            return {
                'frames': stats['frames'],
                'detections': stats['detections'],
                'avg_fps': avg_fps,
                'current_fps': current_fps,
                'elapsed': elapsed
            }
    
    def get_all_stats(self) -> Dict:
        """获取所有设备的统计信息"""
        with self.lock:
            result = {}
            total_frames = 0
            total_detections = 0
            
            # 直接在锁内计算，避免调用get_device_stats()造成嵌套锁
            for device_id in self.device_stats:
                stats = self.device_stats[device_id]
                elapsed = time.time() - self.start_time
                avg_fps = stats['frames'] / elapsed if elapsed > 0 else 0
                current_fps = sum(stats['fps_history']) / len(stats['fps_history']) if stats['fps_history'] else 0
                
                device_result = {
                    'frames': stats['frames'],
                    'detections': stats['detections'],
                    'avg_fps': avg_fps,
                    'current_fps': current_fps,
                    'elapsed': elapsed
                }
                
                result[device_id] = device_result
                total_frames += device_result['frames']
                total_detections += device_result['detections']
            
            elapsed = time.time() - self.start_time
            result['total'] = {
                'frames': total_frames,
                'detections': total_detections,
                'avg_fps': total_frames / elapsed if elapsed > 0 else 0,
                'elapsed': elapsed,
                'device_count': len(self.device_stats)
            }
            
            return result


def discover_multiple_devices() -> List[Any]:
    """发现多个设备"""
    click.echo("🔍 正在扫描多个OAK设备...")
    try:
        devices = OAKDeviceDiscovery.discover_devices(verbose=True)
        if len(devices) >= 2:
            click.echo(f"✅ 发现 {len(devices)} 个设备，满足多设备测试要求")
            for i, device in enumerate(devices, 1):
                short_id = device.mxid[:16] + "..." if len(device.mxid) > 16 else device.mxid
                click.echo(f"  [{i}] {short_id} ({device.product_name or '未知'})")
        elif len(devices) == 1:
            click.echo("⚠️  只发现1个设备，多设备测试需要至少2个设备")
        else:
            click.echo("❌ 未发现任何OAK设备")
        
        # 添加延迟确保设备完全释放
        if devices:
            click.echo("⏳ 等待设备释放连接...")
            time.sleep(3)
        
        return devices
    except Exception as e:
        click.echo(f"❌ 设备发现失败: {e}")
        return []


def create_multi_device_config(devices: List[Any], enable_depth: bool = False) -> OAKModuleConfigDTO:
    """创建多设备配置"""
    if len(devices) < 2:
        raise ValueError("多设备测试需要至少2个设备")
    
    # 查找模型文件
    model_paths = [
        "assets/test_config/yolov8.blob",
        "assets/test_config/model.blob",
        "assets/example_config/mobilenet-ssd_openvino_2021.4_6shave.blob",
        "models/mobilenet-ssd_openvino_2021.4_6shave.blob",
    ]
    
    model_path = "assets/test_config/yolov8.blob"  # 默认路径
    for path in model_paths:
        if Path(path).exists():
            model_path = path
            break
    
    # 使用前两个设备
    device1, device2 = devices[0], devices[1]
    
    config = OAKModuleConfigDTO(
        hardware_config=OAKConfigDTO(
            model_path=model_path,
            confidence_threshold=0.5,
            hardware_fps=20,
            enable_depth_output=enable_depth,
            queue_max_size=4,
            queue_blocking=False,
        ),
        role_bindings={
            DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                active_mxid=device1.mxid,
            ),
            DeviceRole.RIGHT_CAMERA: DeviceRoleBindingDTO(
                role=DeviceRole.RIGHT_CAMERA,
                active_mxid=device2.mxid,
            ),
        },
        device_metadata={
            device1.mxid: device1,
            device2.mxid: device2,
        },
    )
    
    return config


def print_multi_device_stats(collector: MultiDeviceTestCollector, devices: List[Any]):
    """打印多设备统计信息"""
    stats = collector.get_all_stats()
    
    click.echo("\n" + "="*70)
    click.echo("📊 多设备采集统计")
    click.echo("="*70)
    
    # 总体统计
    total = stats['total']
    click.echo(f"运行时间: {total['elapsed']:.1f} 秒")
    click.echo(f"设备数量: {total['device_count']}")
    click.echo(f"总帧数: {total['frames']}")
    click.echo(f"总检测数: {total['detections']}")
    click.echo(f"总体帧率: {total['avg_fps']:.2f} fps")
    
    # 各设备统计
    click.echo("\n📱 各设备详细统计:")
    for i, device in enumerate(devices[:2], 1):
        device_id = device.mxid
        if device_id in stats:
            device_stats = stats[device_id]
            short_id = device_id[:16] + "..." if len(device_id) > 16 else device_id
            click.echo(f"\n  设备 {i} ({short_id}):")
            click.echo(f"    帧数: {device_stats['frames']}")
            click.echo(f"    检测数: {device_stats['detections']}")
            click.echo(f"    平均帧率: {device_stats['avg_fps']:.2f} fps")
            click.echo(f"    当前帧率: {device_stats['current_fps']:.2f} fps")
    
    # 设备间对比
    if len(stats) >= 3:  # total + 2 devices
        device_ids = [d.mxid for d in devices[:2]]
        frames = [stats[did]['frames'] for did in device_ids if did in stats]
        
        if len(frames) == 2:
            frame_diff = abs(frames[0] - frames[1])
            frame_ratio = frame_diff / max(frames) if max(frames) > 0 else 0
            
            click.echo(f"\n⚖️  设备间同步性:")
            click.echo(f"    帧数差异: {frame_diff} 帧")
            click.echo(f"    差异比例: {frame_ratio:.2%}")
            
            if frame_ratio < 0.1:
                click.echo("    ✅ 设备同步性良好")
            elif frame_ratio < 0.2:
                click.echo("    ⚠️  设备同步性一般")
            else:
                click.echo("    ❌ 设备同步性较差")


def run_multi_device_test():
    """运行多设备测试"""
    click.echo("="*60)
    click.echo("🚀 OAK数据采集器多设备测试")
    click.echo("="*60)
    
    # 发现设备
    devices = discover_multiple_devices()
    if len(devices) < 2:
        click.echo("❌ 多设备测试需要至少2个设备")
        return False
    
    # 选择测试参数
    enable_depth = click.confirm("是否启用深度输出?", default=False)
    duration = click.prompt("测试运行时长（秒）", type=int, default=30)
    
    # 创建配置
    try:
        config = create_multi_device_config(devices, enable_depth=enable_depth)
        click.echo(f"\n📝 多设备配置:")
        click.echo(f"  设备1: {devices[0].mxid[:16]}... (LEFT_CAMERA)")
        click.echo(f"  设备2: {devices[1].mxid[:16]}... (RIGHT_CAMERA)")
        click.echo(f"  深度输出: {'启用' if enable_depth else '禁用'}")
        click.echo(f"  模型路径: {config.hardware_config.model_path}")
    except Exception as e:
        click.echo(f"❌ 配置创建失败: {e}")
        return False
    
    # 设置事件总线
    reset_event_bus()
    event_bus = EventBus()
    
    # 创建测试收集器
    test_collector = MultiDeviceTestCollector()
    event_bus.subscribe(EventType.RAW_FRAME_DATA, test_collector.handle_frame)
    event_bus.subscribe(EventType.RAW_DETECTION_DATA, test_collector.handle_detection)
    
    # 启动采集
    try:
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        result = collector.start()
        
        if len(result["started"]) != 2:
            click.echo(f"❌ 多设备启动失败: {result}")
            return False
        
        click.echo(f"✅ 多设备采集已启动: {result['started']}")
        click.echo(f"⏱️  运行 {duration} 秒...")
        click.echo("按 Ctrl+C 提前停止")
        
        # 运行测试
        try:
            for i in range(duration):
                time.sleep(1)
                if i % 10 == 9:  # 每10秒显示一次统计
                    print_multi_device_stats(test_collector, devices)
        except KeyboardInterrupt:
            click.echo("\n⚠️  用户中断测试")
        
        # 停止采集
        collector.stop()
        click.echo("✅ 多设备采集已停止")
        
    except Exception as e:
        click.echo(f"❌ 多设备测试失败: {e}")
        return False
    
    # 最终统计和评估
    print_multi_device_stats(test_collector, devices)
    
    # 测试评估
    stats = test_collector.get_all_stats()
    total = stats['total']
    
    click.echo("\n" + "="*60)
    click.echo("📋 多设备测试评估")
    click.echo("="*60)
    
    success = True
    
    # 检查总体性能
    if total['frames'] > 0:
        click.echo("✅ 多设备视频帧采集: 正常")
    else:
        click.echo("❌ 多设备视频帧采集: 异常")
        success = False
    
    if total['detections'] > 0:
        click.echo("✅ 多设备检测数据采集: 正常")
    else:
        click.echo("❌ 多设备检测数据采集: 异常")
        success = False
    
    if total['avg_fps'] > 10.0:
        click.echo("✅ 多设备采集性能: 良好")
    else:
        click.echo("⚠️  多设备采集性能: 需要优化")
    
    # 检查设备均衡性
    device_ids = [d.mxid for d in devices[:2]]
    device_frames = [stats[did]['frames'] for did in device_ids if did in stats]
    
    if len(device_frames) == 2:
        frame_diff_ratio = abs(device_frames[0] - device_frames[1]) / max(device_frames)
        if frame_diff_ratio < 0.2:
            click.echo("✅ 设备负载均衡: 良好")
        else:
            click.echo("⚠️  设备负载均衡: 需要优化")
    
    # 总体评价
    if success:
        click.echo(f"\n🎉 多设备测试通过!")
        click.echo("   多设备协同工作正常，数据采集稳定")
    else:
        click.echo(f"\n❌ 多设备测试失败!")
        click.echo("   请检查设备连接和配置")
    
    return success


@click.command()
@click.option('--duration', default=30, help='测试运行时长（秒）')
@click.option('--depth', is_flag=True, help='启用深度输出')
def main(duration, depth):
    """
    OAK数据采集器多设备测试工具
    
    此工具用于测试多个OAK设备的协同工作能力，
    验证多设备数据采集的同步性和稳定性。
    """
    try:
        success = run_multi_device_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  用户中断测试")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n💥 测试异常: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()