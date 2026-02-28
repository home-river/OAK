"""
显示模块窗口管理功能示例

演示如何使用窗口管理功能：
- 设置窗口位置
- 启用全屏模式
- 运行时切换全屏模式（按 'f' 键）
- 自定义窗口标题
"""

import numpy as np
import time
from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.core.event_bus import get_event_bus, EventType


def create_test_data(device_id: str, frame_id: int):
    """创建测试数据
    
    Args:
        device_id: 设备ID
        frame_id: 帧ID
    """
    # 创建测试视频帧
    rgb_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    depth_frame = np.random.randint(0, 5000, (480, 640), dtype=np.uint16)
    
    video_frame = VideoFrameDTO(
        device_id=device_id,
        frame_id=frame_id,
        rgb_frame=rgb_frame,
        depth_frame=depth_frame,
    )
    
    # 创建测试检测数据
    coords = np.array([[100, 200, 300]], dtype=np.float32)
    bbox = np.array([[50, 50, 150, 150]], dtype=np.float32)
    confidence = np.array([0.95], dtype=np.float32)
    labels = np.array([0], dtype=np.int32)
    
    processed_data = DeviceProcessedDataDTO(
        device_id=device_id,
        frame_id=frame_id,
        device_alias="test_camera",
        coords=coords,
        bbox=bbox,
        confidence=confidence,
        labels=labels,
        state_label=[],
    )
    
    return video_frame, processed_data


def example_window_position():
    """示例 1：设置窗口位置"""
    print("\n=== 示例 1：设置窗口位置 ===")
    print("窗口将显示在屏幕位置 (100, 50)")
    
    # 创建配置（设置窗口位置）
    config = DisplayConfigDTO(
        enable_display=True,
        window_width=800,
        window_height=600,
        window_position_x=100,  # 窗口 X 位置
        window_position_y=50,   # 窗口 Y 位置
        target_fps=20,
    )
    
    # 创建显示管理器
    event_bus = get_event_bus()
    display_manager = DisplayManager(
        config=config,
        devices_list=["device1"],
        event_bus=event_bus,
    )
    
    # 启动显示模块
    display_manager.start()
    
    try:
        # 发送测试数据
        for i in range(100):
            video_frame, processed_data = create_test_data("device1", i)
            
            # 发布事件
            event_bus.publish(EventType.RAW_FRAME_DATA, video_frame)
            event_bus.publish(EventType.PROCESSED_DATA, processed_data)
            
            time.sleep(0.05)  # 20 FPS
            
    finally:
        # 停止显示模块
        display_manager.stop()
        print("示例 1 完成")


def example_fullscreen_mode():
    """示例 2：启用全屏模式"""
    print("\n=== 示例 2：启用全屏模式 ===")
    print("窗口将以全屏模式启动")
    print("按 'f' 键可以切换全屏/窗口模式")
    print("按 'q' 键退出")
    
    # 创建配置（启用全屏）
    config = DisplayConfigDTO(
        enable_display=True,
        enable_fullscreen=True,  # 启用全屏模式
        target_fps=20,
    )
    
    # 创建显示管理器
    event_bus = get_event_bus()
    display_manager = DisplayManager(
        config=config,
        devices_list=["device1"],
        event_bus=event_bus,
    )
    
    # 启动显示模块
    display_manager.start()
    
    try:
        # 发送测试数据
        for i in range(200):
            video_frame, processed_data = create_test_data("device1", i)
            
            # 发布事件
            event_bus.publish(EventType.RAW_FRAME_DATA, video_frame)
            event_bus.publish(EventType.PROCESSED_DATA, processed_data)
            
            time.sleep(0.05)  # 20 FPS
            
    finally:
        # 停止显示模块
        display_manager.stop()
        print("示例 2 完成")


def example_custom_window_title():
    """示例 3：自定义窗口标题"""
    print("\n=== 示例 3：自定义窗口标题 ===")
    print("窗口标题将显示设备别名")
    
    # 创建配置
    config = DisplayConfigDTO(
        enable_display=True,
        window_width=800,
        window_height=600,
        target_fps=20,
    )
    
    # 创建显示管理器
    event_bus = get_event_bus()
    display_manager = DisplayManager(
        config=config,
        devices_list=["device1"],
        event_bus=event_bus,
    )
    
    # 启动显示模块
    display_manager.start()
    
    try:
        # 发送测试数据（带自定义设备别名）
        for i in range(100):
            rgb_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            depth_frame = np.random.randint(0, 5000, (480, 640), dtype=np.uint16)
            
            video_frame = VideoFrameDTO(
                device_id="device1",
                frame_id=i,
                rgb_frame=rgb_frame,
                depth_frame=depth_frame,
            )
            
            # 使用自定义设备别名
            processed_data = DeviceProcessedDataDTO(
                device_id="device1",
                frame_id=i,
                device_alias="左侧摄像头",  # 自定义别名
                coords=np.array([[100, 200, 300]], dtype=np.float32),
                bbox=np.array([[50, 50, 150, 150]], dtype=np.float32),
                confidence=np.array([0.95], dtype=np.float32),
                labels=np.array([0], dtype=np.int32),
                state_label=[],
            )
            
            # 发布事件
            event_bus.publish(EventType.RAW_FRAME_DATA, video_frame)
            event_bus.publish(EventType.PROCESSED_DATA, processed_data)
            
            time.sleep(0.05)  # 20 FPS
            
    finally:
        # 停止显示模块
        display_manager.stop()
        print("示例 3 完成")


def example_multiple_windows():
    """示例 4：多窗口管理"""
    print("\n=== 示例 4：多窗口管理 ===")
    print("将创建两个窗口，每个窗口显示不同设备的数据")
    print("按 'f' 键可以同时切换所有窗口的全屏模式")
    print("按 'q' 键退出")
    
    # 创建配置
    config = DisplayConfigDTO(
        enable_display=True,
        window_width=640,
        window_height=480,
        window_position_x=0,
        window_position_y=0,
        target_fps=20,
    )
    
    # 创建显示管理器（两个设备）
    event_bus = get_event_bus()
    display_manager = DisplayManager(
        config=config,
        devices_list=["device1", "device2"],
        event_bus=event_bus,
    )
    
    # 启动显示模块
    display_manager.start()
    
    try:
        # 发送测试数据
        for i in range(100):
            # 设备 1 的数据
            video_frame1, processed_data1 = create_test_data("device1", i)
            processed_data1 = DeviceProcessedDataDTO(
                device_id="device1",
                frame_id=i,
                device_alias="左侧摄像头",
                coords=processed_data1.coords,
                bbox=processed_data1.bbox,
                confidence=processed_data1.confidence,
                labels=processed_data1.labels,
                state_label=[],
            )
            
            # 设备 2 的数据
            video_frame2, processed_data2 = create_test_data("device2", i)
            processed_data2 = DeviceProcessedDataDTO(
                device_id="device2",
                frame_id=i,
                device_alias="右侧摄像头",
                coords=processed_data2.coords,
                bbox=processed_data2.bbox,
                confidence=processed_data2.confidence,
                labels=processed_data2.labels,
                state_label=[],
            )
            
            # 发布事件
            event_bus.publish(EventType.RAW_FRAME_DATA, video_frame1)
            event_bus.publish(EventType.PROCESSED_DATA, processed_data1)
            event_bus.publish(EventType.RAW_FRAME_DATA, video_frame2)
            event_bus.publish(EventType.PROCESSED_DATA, processed_data2)
            
            time.sleep(0.05)  # 20 FPS
            
    finally:
        # 停止显示模块
        display_manager.stop()
        print("示例 4 完成")


if __name__ == "__main__":
    print("显示模块窗口管理功能示例")
    print("=" * 50)
    
    # 运行示例
    # 注意：这些示例需要在有显示器的环境中运行
    
    # 示例 1：设置窗口位置
    # example_window_position()
    
    # 示例 2：启用全屏模式
    # example_fullscreen_mode()
    
    # 示例 3：自定义窗口标题
    # example_custom_window_title()
    
    # 示例 4：多窗口管理
    # example_multiple_windows()
    
    print("\n提示：取消注释上面的示例函数调用来运行示例")
    print("注意：这些示例需要在有显示器的环境中运行")
