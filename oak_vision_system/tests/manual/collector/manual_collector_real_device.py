#!/usr/bin/env python3
"""
OAK数据采集器实机测试 - Windows端设备连接测试

用途：
- 在Windows端连接真实OAK设备进行collector功能验证
- 提供交互式测试界面，方便开发者验证各项功能
- 支持单设备和多设备测试场景
- 实时显示采集数据统计和设备状态

测试覆盖：
1. 设备发现和连接测试
2. 数据采集功能测试（RGB帧、深度帧、检测数据）
3. 多设备协同测试
4. 性能测试和稳定性测试
5. 背压处理测试
6. 错误恢复测试

运行方式：
    python oak_vision_system/tests/manual/test_collector_real_device_manual.py

作者：OAK Vision System
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict, deque

def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    for p in (current, *current.parents):
        if (p / "pyproject.toml").exists():
            return p
    return start.resolve()

project_root = _find_project_root(Path(__file__).parent)
sys.path.insert(0, str(project_root))

try:
    import click
    import depthai as dai
    import numpy as np
except ImportError as e:
    print(f"错误: 缺少必要的依赖库: {e}")
    print("请运行: pip install click depthai numpy")
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


@dataclass
class TestStatistics:
    """测试统计数据"""
    start_time: float
    frame_count: int = 0
    detection_count: int = 0
    error_count: int = 0
    last_frame_time: float = 0.0
    device_frame_counts: Dict[str, int] = None
    device_detection_counts: Dict[str, int] = None
    fps_history: deque = None
    
    def __post_init__(self):
        if self.device_frame_counts is None:
            self.device_frame_counts = defaultdict(int)
        if self.device_detection_counts is None:
            self.device_detection_counts = defaultdict(int)
        if self.fps_history is None:
            self.fps_history = deque(maxlen=30)  # 保留最近30秒的FPS
    
    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    @property
    def average_fps(self) -> float:
        if self.elapsed_time > 0:
            return self.frame_count / self.elapsed_time
        return 0.0
    
    @property
    def current_fps(self) -> float:
        if len(self.fps_history) > 0:
            return sum(self.fps_history) / len(self.fps_history)
        return 0.0


class CollectorTestRunner:
    """Collector实机测试运行器"""
    
    def __init__(self):
        self.event_bus = EventBus()
        self.collector: Optional[OAKDataCollector] = None
        self.statistics = TestStatistics(start_time=time.time())
        self.running = False
        self._stats_lock = threading.Lock()
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """设置事件处理器"""
        self.event_bus.subscribe(EventType.RAW_FRAME_DATA, self._handle_frame_data)
        self.event_bus.subscribe(EventType.RAW_DETECTION_DATA, self._handle_detection_data)
    
    def _handle_frame_data(self, frame_data: VideoFrameDTO):
        """处理视频帧数据"""
        with self._stats_lock:
            self.statistics.frame_count += 1
            self.statistics.device_frame_counts[frame_data.device_id] += 1
            
            # 计算FPS
            current_time = time.time()
            if self.statistics.last_frame_time > 0:
                frame_interval = current_time - self.statistics.last_frame_time
                if frame_interval > 0:
                    fps = 1.0 / frame_interval
                    self.statistics.fps_history.append(fps)
            self.statistics.last_frame_time = current_time
    
    def _handle_detection_data(self, detection_data: DeviceDetectionDataDTO):
        """处理检测数据"""
        with self._stats_lock:
            self.statistics.detection_count += 1
            self.statistics.device_detection_counts[detection_data.device_id] += 1
    
    def discover_devices(self) -> List[Any]:
        """发现OAK设备"""
        click.echo("🔍 正在扫描OAK设备...")
        try:
            devices = OAKDeviceDiscovery.discover_devices(verbose=True)
            if devices:
                click.echo(f"✅ 发现 {len(devices)} 个设备:")
                for i, device in enumerate(devices, 1):
                    click.echo(f"  [{i}] {device.mxid} ({device.product_name or '未知产品'})")
                
                # 添加延迟确保设备完全释放
                click.echo("⏳ 等待设备释放连接...")
                time.sleep(3)
            else:
                click.echo("❌ 未发现任何OAK设备")
                click.echo("\n请检查:")
                click.echo("  1. 设备是否已连接到计算机")
                click.echo("  2. USB线缆是否正常")
                click.echo("  3. 设备驱动是否已安装")
            return devices
        except Exception as e:
            click.echo(f"❌ 设备发现失败: {e}")
            return []
    
    def create_test_config(self, devices: List[Any], enable_depth: bool = False, 
                          fps: int = 20) -> OAKModuleConfigDTO:
        """创建测试配置"""
        if not devices:
            raise ValueError("没有可用的设备")
        
        # 查找模型文件
        model_paths = [
            "assets/test_config/yolov8.blob",
            "assets/test_config/model.blob",
            "assets/example_config/mobilenet-ssd_openvino_2021.4_6shave.blob",
            "models/mobilenet-ssd_openvino_2021.4_6shave.blob",
            "config/models/mobilenet-ssd_openvino_2021.4_6shave.blob",
        ]
        
        model_path = None
        for path in model_paths:
            if Path(path).exists():
                model_path = path
                break
        
        if not model_path:
            # 使用默认路径，让用户知道需要提供模型文件
            model_path = "assets/test_config/yolov8.blob"
            click.echo(f"⚠️  模型文件未找到，使用默认路径: {model_path}")
            click.echo("   请确保模型文件存在，或修改代码中的模型路径")
        
        # 创建设备绑定
        role_bindings = {}
        device_metadata = {}
        
        # 使用前两个设备（如果有的话）
        roles = [DeviceRole.LEFT_CAMERA, DeviceRole.RIGHT_CAMERA]
        for i, device in enumerate(devices[:2]):
            role = roles[i]
            role_bindings[role] = DeviceRoleBindingDTO(
                role=role,
                active_mxid=device.mxid,
            )
            device_metadata[device.mxid] = device
        
        config = OAKModuleConfigDTO(
            hardware_config=OAKConfigDTO(
                model_path=model_path,
                confidence_threshold=0.5,
                hardware_fps=fps,
                enable_depth_output=enable_depth,
                queue_max_size=4,
                queue_blocking=False,
            ),
            role_bindings=role_bindings,
            device_metadata=device_metadata,
        )
        
        return config
    
    def start_collection(self, config: OAKModuleConfigDTO) -> bool:
        """启动数据采集"""
        try:
            # 重置事件总线和统计
            reset_event_bus()
            self.event_bus = EventBus()
            self._setup_event_handlers()
            self.statistics = TestStatistics(start_time=time.time())
            
            # 创建collector
            self.collector = OAKDataCollector(config=config, event_bus=self.event_bus)
            
            # 启动采集
            result = self.collector.start()

            if result is False or not isinstance(result, dict) or not result.get("started"):
                click.echo(f"❌ 采集启动失败: {result}")
                return False

            click.echo(f"✅ 采集已启动: {result['started']}")
            self.running = True
            return True
                
        except Exception as e:
            click.echo(f"❌ 启动采集失败: {e}")
            return False
    
    def stop_collection(self):
        """停止数据采集"""
        if self.collector:
            try:
                self.collector.stop()
                self.running = False
                click.echo("✅ 采集已停止")
            except Exception as e:
                click.echo(f"❌ 停止采集失败: {e}")
    
    def print_statistics(self):
        """打印统计信息"""
        with self._stats_lock:
            stats = self.statistics
            
            click.echo("\n" + "="*60)
            click.echo("📊 采集统计信息")
            click.echo("="*60)
            click.echo(f"运行时间: {stats.elapsed_time:.1f} 秒")
            click.echo(f"总帧数: {stats.frame_count}")
            click.echo(f"总检测数: {stats.detection_count}")
            click.echo(f"平均帧率: {stats.average_fps:.2f} fps")
            click.echo(f"当前帧率: {stats.current_fps:.2f} fps")
            
            if stats.device_frame_counts:
                click.echo("\n📱 设备帧数统计:")
                for device_id, count in stats.device_frame_counts.items():
                    short_id = device_id[:16] + "..." if len(device_id) > 16 else device_id
                    click.echo(f"  {short_id}: {count} 帧")
            
            if stats.device_detection_counts:
                click.echo("\n🎯 设备检测统计:")
                for device_id, count in stats.device_detection_counts.items():
                    short_id = device_id[:16] + "..." if len(device_id) > 16 else device_id
                    click.echo(f"  {short_id}: {count} 检测")


def run_interactive_test():
    """运行交互式测试"""
    runner = CollectorTestRunner()
    
    click.echo("="*60)
    click.echo("🚀 OAK数据采集器实机测试")
    click.echo("="*60)
    
    # 发现设备
    devices = runner.discover_devices()
    if not devices:
        return
    
    # 选择测试模式
    click.echo("\n📋 选择测试模式:")
    click.echo("1. 单设备测试（RGB + 检测）")
    click.echo("2. 单设备测试（RGB + 深度 + 检测）")
    click.echo("3. 多设备测试（如果有多个设备）")
    click.echo("4. 性能测试（长时间运行）")
    
    choice = click.prompt("请选择测试模式", type=int, default=1)
    
    # 配置参数
    enable_depth = choice == 2
    fps = click.prompt("设置帧率", type=int, default=20)
    
    # 创建配置
    try:
        config = runner.create_test_config(devices, enable_depth=enable_depth, fps=fps)
        click.echo(f"\n📝 测试配置:")
        click.echo(f"  设备数量: {len(config.role_bindings)}")
        click.echo(f"  深度输出: {'启用' if enable_depth else '禁用'}")
        click.echo(f"  目标帧率: {fps} fps")
        click.echo(f"  模型路径: {config.hardware_config.model_path}")
    except Exception as e:
        click.echo(f"❌ 创建配置失败: {e}")
        return
    
    # 启动采集
    if not runner.start_collection(config):
        return
    
    # 运行测试
    try:
        if choice == 4:
            # 性能测试
            duration = click.prompt("运行时长（秒）", type=int, default=60)
            click.echo(f"\n🏃 开始性能测试，运行 {duration} 秒...")
            click.echo("按 Ctrl+C 提前停止")
            
            for i in range(duration):
                time.sleep(1)
                if i % 10 == 9:  # 每10秒显示一次统计
                    runner.print_statistics()
        else:
            # 交互式测试
            click.echo("\n🎮 测试已开始，按以下键进行操作:")
            click.echo("  's' - 显示统计信息")
            click.echo("  'q' - 退出测试")
            click.echo("  Ctrl+C - 强制退出")
            
            while runner.running:
                try:
                    key = click.getchar()
                    if key.lower() == 's':
                        runner.print_statistics()
                    elif key.lower() == 'q':
                        break
                except (KeyboardInterrupt, EOFError):
                    break
                except:
                    time.sleep(0.1)  # 避免CPU占用过高
    
    except KeyboardInterrupt:
        click.echo("\n⚠️  用户中断测试")
    
    finally:
        # 停止采集并显示最终统计
        runner.stop_collection()
        runner.print_statistics()
        
        # 测试总结
        stats = runner.statistics
        click.echo("\n" + "="*60)
        click.echo("📋 测试总结")
        click.echo("="*60)
        
        if stats.frame_count > 0:
            click.echo("✅ 视频帧采集: 正常")
        else:
            click.echo("❌ 视频帧采集: 异常")
        
        if stats.detection_count > 0:
            click.echo("✅ 检测数据采集: 正常")
        else:
            click.echo("❌ 检测数据采集: 异常")
        
        if stats.average_fps > 5.0:
            click.echo("✅ 采集性能: 良好")
        else:
            click.echo("⚠️  采集性能: 需要优化")
        
        click.echo(f"\n总体评价: {'✅ 测试通过' if stats.frame_count > 0 and stats.detection_count > 0 else '❌ 测试失败'}")


@click.command()
@click.option('--auto', is_flag=True, help='自动模式（非交互式）')
@click.option('--duration', default=30, help='自动模式运行时长（秒）')
@click.option('--depth', is_flag=True, help='启用深度输出')
@click.option('--fps', default=20, help='目标帧率')
def main(auto, duration, depth, fps):
    """
    OAK数据采集器实机测试工具
    
    此工具用于在Windows端连接真实OAK设备进行collector功能验证。
    支持交互式测试和自动化测试两种模式。
    """
    if auto:
        # 自动模式
        runner = CollectorTestRunner()
        
        click.echo("🤖 自动测试模式")
        devices = runner.discover_devices()
        if not devices:
            return
        
        config = runner.create_test_config(devices, enable_depth=depth, fps=fps)
        
        if runner.start_collection(config):
            click.echo(f"⏱️  运行 {duration} 秒...")
            time.sleep(duration)
            runner.stop_collection()
            runner.print_statistics()
    else:
        # 交互式模式
        run_interactive_test()


if __name__ == '__main__':
    main()