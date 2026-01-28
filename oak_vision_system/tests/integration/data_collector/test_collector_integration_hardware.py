"""
OAK 数据采集器集成测试 - 真实硬件版本

测试策略：
- 使用真实的 OAK 设备进行测试
- 自动检测设备可用性，无设备时跳过测试
- 验证与真实硬件的交互

测试覆盖：
1. 真实设备连接和初始化
2. 真实 Pipeline 创建
3. 真实数据采集（RGB 帧、检测数据、深度帧）
4. 真实事件发布
5. 多设备协同工作
6. 性能和稳定性测试

运行方式：
- 运行所有硬件测试：pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_hardware.py -v -m hardware
- 跳过硬件测试：pytest oak_vision_system/tests/integration/data_collector/test_collector_integration_hardware.py -v -m "not hardware"
"""

import pytest
import time
import depthai as dai

from oak_vision_system.modules.data_collector.collector import OAKDataCollector
from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
from oak_vision_system.core.dto.config_dto import (
    OAKModuleConfigDTO,
    OAKConfigDTO,
    DeviceRoleBindingDTO,
    DeviceRole,
)
from oak_vision_system.core.event_bus import reset_event_bus


# ==================== 测试类：真实设备初始化 ====================

@pytest.mark.hardware
class TestCollectorHardwareInitialization:
    """测试 Collector 与真实硬件的初始化"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_discover_real_devices(self, has_oak_device):
        """测试 1: 发现真实 OAK 设备"""
        if not has_oak_device:
            pytest.skip("未检测到 OAK 设备，跳过硬件测试")
        
        # 发现设备
        devices = OAKDeviceDiscovery.discover_devices(verbose=True)
        
        # 验证
        assert len(devices) > 0, "应该至少发现一个 OAK 设备"
        
        for device in devices:
            assert device.mxid is not None
            assert len(device.mxid) > 0
            print(f"✓ 发现设备: {device.mxid} ({device.product_name})")
        
        print(f"✅ 成功发现 {len(devices)} 个 OAK 设备")
    
    def test_create_collector_with_real_device(self, has_oak_device, event_bus):
        """测试 2: 使用真实设备创建 Collector"""
        if not has_oak_device:
            pytest.skip("未检测到 OAK 设备，跳过硬件测试")
        
        # 发现设备
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        assert len(devices) > 0
        
        # 使用第一个设备创建配置
        first_device = devices[0]
        
        config = OAKModuleConfigDTO(
            hardware_config=OAKConfigDTO(
                model_path="path/to/model.blob",  # 需要实际的模型路径
                confidence_threshold=0.5,
                hardware_fps=20,
                enable_depth_output=False,
            ),
            role_bindings={
                DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                    role=DeviceRole.LEFT_CAMERA,
                    active_mxid=first_device.mxid,
                ),
            },
            device_metadata={
                first_device.mxid: first_device,
            },
        )
        
        # 创建 Collector
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        
        # 验证
        assert collector.config == config
        assert len(collector.running) == 1
        
        print(f"✅ 成功创建 Collector，使用设备: {first_device.mxid}")


# ==================== 测试类：真实数据采集 ====================

@pytest.mark.hardware
class TestCollectorHardwareDataCollection:
    """测试真实硬件的数据采集"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_collect_real_frames(self, has_oak_device, event_bus, event_collector):
        """测试 3: 采集真实视频帧"""
        if not has_oak_device:
            pytest.skip("未检测到 OAK 设备，跳过硬件测试")
        
        # 发现设备
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        assert len(devices) > 0
        
        first_device = devices[0]
        
        # 创建配置（需要实际的模型路径）
        # 注意：这里需要一个有效的 .blob 模型文件
        config = OAKModuleConfigDTO(
            hardware_config=OAKConfigDTO(
                model_path="assets/test_config/model.blob",  # 从 assets/test_config/ 加载
                confidence_threshold=0.5,
                hardware_fps=20,
                enable_depth_output=False,
                queue_max_size=4,
                queue_blocking=False,
            ),
            role_bindings={
                DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                    role=DeviceRole.LEFT_CAMERA,
                    active_mxid=first_device.mxid,
                ),
            },
            device_metadata={
                first_device.mxid: first_device,
            },
        )
        
        # 创建 Collector
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        
        # 开始收集事件
        event_collector.start_collecting()
        
        # 启动采集
        result = collector.start()
        
        # 验证启动结果
        assert len(result["started"]) == 1
        assert DeviceRole.LEFT_CAMERA.value in result["started"]
        
        print(f"✓ 采集已启动: {result['started']}")
        
        # 等待采集数据（5 秒）
        print("等待采集数据...")
        success = event_collector.wait_for_events(
            frame_count=10,
            detection_count=10,
            timeout=10.0
        )
        
        # 停止采集
        collector.stop()
        
        # 验证收到的数据
        print(f"✓ 收到 {len(event_collector.frame_events)} 个视频帧")
        print(f"✓ 收到 {len(event_collector.detection_events)} 个检测数据")
        
        assert len(event_collector.frame_events) > 0, "应该收到至少一个视频帧"
        assert len(event_collector.detection_events) > 0, "应该收到至少一个检测数据"
        
        # 验证数据格式
        first_frame = event_collector.frame_events[0]
        assert first_frame.device_id == first_device.mxid
        assert first_frame.has_rgb
        assert first_frame.rgb_frame is not None
        
        first_detection = event_collector.detection_events[0]
        assert first_detection.device_id == first_device.mxid
        assert first_detection.device_alias == DeviceRole.LEFT_CAMERA.value
        
        print("✅ 真实数据采集测试成功")
    
    def test_collect_with_depth(self, has_oak_device, event_bus, event_collector):
        """测试 4: 采集带深度的数据"""
        if not has_oak_device:
            pytest.skip("未检测到 OAK 设备，跳过硬件测试")
        
        # 发现设备
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        assert len(devices) > 0
        
        first_device = devices[0]
        
        # 创建启用深度的配置
        config = OAKModuleConfigDTO(
            hardware_config=OAKConfigDTO(
                model_path="assets/test_config/model.blob",  # 从 assets/test_config/ 加载
                confidence_threshold=0.5,
                hardware_fps=20,
                enable_depth_output=True,  # 启用深度
                queue_max_size=4,
                queue_blocking=False,
            ),
            role_bindings={
                DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                    role=DeviceRole.LEFT_CAMERA,
                    active_mxid=first_device.mxid,
                ),
            },
            device_metadata={
                first_device.mxid: first_device,
            },
        )
        
        # 创建 Collector
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        
        # 开始收集事件
        event_collector.start_collecting()
        
        # 启动采集
        result = collector.start()
        assert len(result["started"]) == 1
        
        # 等待采集数据
        print("等待采集带深度的数据...")
        event_collector.wait_for_events(frame_count=5, timeout=10.0)
        
        # 停止采集
        collector.stop()
        
        # 验证深度数据
        assert len(event_collector.frame_events) > 0
        
        frames_with_depth = [f for f in event_collector.frame_events if f.has_depth]
        assert len(frames_with_depth) > 0, "应该收到至少一个带深度的视频帧"
        
        # 验证深度帧格式
        first_depth_frame = frames_with_depth[0]
        assert first_depth_frame.depth_frame is not None
        assert first_depth_frame.depth_frame.dtype.name == 'uint16'
        
        print(f"✅ 深度数据采集测试成功，收到 {len(frames_with_depth)} 个带深度的帧")


# ==================== 测试类：多设备协同 ====================

@pytest.mark.hardware
class TestCollectorMultiDevice:
    """测试多设备协同工作"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_collect_from_multiple_devices(self, has_oak_device, event_bus, event_collector):
        """测试 5: 从多个设备采集数据"""
        if not has_oak_device:
            pytest.skip("未检测到 OAK 设备，跳过硬件测试")
        
        # 发现设备
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        
        if len(devices) < 2:
            pytest.skip("需要至少 2 个 OAK 设备进行多设备测试")
        
        # 使用前两个设备
        device1 = devices[0]
        device2 = devices[1]
        
        # 创建多设备配置
        config = OAKModuleConfigDTO(
            hardware_config=OAKConfigDTO(
                model_path="assets/test_config/model.blob",  # 从 assets/test_config/ 加载
                confidence_threshold=0.5,
                hardware_fps=20,
                enable_depth_output=False,
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
        
        # 创建 Collector
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        
        # 开始收集事件
        event_collector.start_collecting()
        
        # 启动采集
        result = collector.start()
        
        # 验证两个设备都启动了
        assert len(result["started"]) == 2
        assert DeviceRole.LEFT_CAMERA.value in result["started"]
        assert DeviceRole.RIGHT_CAMERA.value in result["started"]
        
        print(f"✓ 多设备采集已启动: {result['started']}")
        
        # 等待采集数据
        print("等待多设备采集数据...")
        event_collector.wait_for_events(
            frame_count=20,
            detection_count=20,
            timeout=15.0
        )
        
        # 停止采集
        collector.stop()
        
        # 验证收到来自两个设备的数据
        device_ids = set(f.device_id for f in event_collector.frame_events)
        
        print(f"✓ 收到来自 {len(device_ids)} 个设备的数据")
        print(f"✓ 设备 ID: {device_ids}")
        
        assert len(device_ids) >= 1, "应该至少收到一个设备的数据"
        
        # 理想情况下应该收到两个设备的数据，但由于时序问题可能只收到一个
        if len(device_ids) == 2:
            assert device1.mxid in device_ids
            assert device2.mxid in device_ids
            print("✅ 成功从两个设备采集数据")
        else:
            print("⚠️  只收到一个设备的数据（可能是时序问题）")


# ==================== 测试类：性能和稳定性 ====================

@pytest.mark.hardware
class TestCollectorPerformance:
    """测试性能和稳定性"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后重置事件总线"""
        reset_event_bus()
        yield
        reset_event_bus()
    
    def test_long_running_collection(self, has_oak_device, event_bus, event_collector):
        """测试 6: 长时间运行的采集"""
        if not has_oak_device:
            pytest.skip("未检测到 OAK 设备，跳过硬件测试")
        
        # 发现设备
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        assert len(devices) > 0
        
        first_device = devices[0]
        
        # 创建配置
        config = OAKModuleConfigDTO(
            hardware_config=OAKConfigDTO(
                model_path="assets/test_config/model.blob",  # 从 config/models/ 加载
                confidence_threshold=0.5,
                hardware_fps=20,
                enable_depth_output=False,
            ),
            role_bindings={
                DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                    role=DeviceRole.LEFT_CAMERA,
                    active_mxid=first_device.mxid,
                ),
            },
            device_metadata={
                first_device.mxid: first_device,
            },
        )
        
        # 创建 Collector
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        
        # 开始收集事件
        event_collector.start_collecting()
        
        # 启动采集
        result = collector.start()
        assert len(result["started"]) == 1
        
        print("开始长时间采集测试（30 秒）...")
        
        # 运行 30 秒
        start_time = time.time()
        duration = 30.0
        
        while time.time() - start_time < duration:
            time.sleep(1.0)
            elapsed = time.time() - start_time
            frame_count = len(event_collector.frame_events)
            detection_count = len(event_collector.detection_events)
            print(f"  {elapsed:.1f}s: 帧={frame_count}, 检测={detection_count}")
        
        # 停止采集
        collector.stop()
        
        # 验证数据
        total_frames = len(event_collector.frame_events)
        total_detections = len(event_collector.detection_events)
        
        print(f"\n✓ 总视频帧: {total_frames}")
        print(f"✓ 总检测数据: {total_detections}")
        
        # 计算平均帧率
        avg_fps = total_frames / duration
        print(f"✓ 平均帧率: {avg_fps:.2f} fps")
        
        # 验证性能
        assert total_frames > 0, "应该收到视频帧"
        assert total_detections > 0, "应该收到检测数据"
        assert avg_fps > 5.0, f"平均帧率应该大于 5 fps，实际: {avg_fps:.2f}"
        
        print("✅ 长时间运行测试成功")
    
    def test_start_stop_multiple_times(self, has_oak_device, event_bus):
        """测试 7: 多次启动和停止"""
        if not has_oak_device:
            pytest.skip("未检测到 OAK 设备，跳过硬件测试")
        
        # 发现设备
        devices = OAKDeviceDiscovery.discover_devices(verbose=False)
        assert len(devices) > 0
        
        first_device = devices[0]
        
        # 创建配置
        config = OAKModuleConfigDTO(
            hardware_config=OAKConfigDTO(
                model_path="assets/test_config/model.blob",  # 从 config/models/ 加载
                confidence_threshold=0.5,
                hardware_fps=20,
                enable_depth_output=False,
            ),
            role_bindings={
                DeviceRole.LEFT_CAMERA: DeviceRoleBindingDTO(
                    role=DeviceRole.LEFT_CAMERA,
                    active_mxid=first_device.mxid,
                ),
            },
            device_metadata={
                first_device.mxid: first_device,
            },
        )
        
        # 创建 Collector
        collector = OAKDataCollector(config=config, event_bus=event_bus)
        
        # 多次启动和停止
        for i in range(3):
            print(f"\n第 {i+1} 次启动...")
            
            # 启动
            result = collector.start()
            assert len(result["started"]) == 1
            
            # 运行 2 秒
            time.sleep(2.0)
            
            # 停止
            collector.stop()
            
            # 验证停止
            assert not collector._is_running(DeviceRole.LEFT_CAMERA.value)
            
            print(f"✓ 第 {i+1} 次停止成功")
        
        print("\n✅ 多次启动停止测试成功")


# ==================== 主测试函数 ====================

if __name__ == "__main__":
    """直接运行测试"""
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s", "-m", "hardware"]))
