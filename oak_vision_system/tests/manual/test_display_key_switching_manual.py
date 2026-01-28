"""
手动测试脚本：显示模块按键切换功能

测试任务 10.2：手动测试按键切换
- 测试1/2/3键切换
- 测试F键全屏切换
- 测试Q键退出

使用方法：
1. 运行此脚本
2. 按照屏幕提示进行操作
3. 验证各个按键功能是否正常

按键说明：
- 1: 切换到第一个设备（单设备显示）
- 2: 切换到第二个设备（单设备显示）
- 3: 切换到 Combined 模式（双设备拼接）
- F: 切换全屏/窗口模式
- Q: 退出程序
"""

import time
import numpy as np
from typing import Dict

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.event_bus import EventBus, EventType
from oak_vision_system.modules.display_modules.display_manager import DisplayManager
from oak_vision_system.modules.display_modules.render_packet_packager import RenderPacket


def create_test_frame(device_id: str, frame_id: int, device_alias: str) -> tuple:
    """创建测试用的视频帧和检测数据
    
    Args:
        device_id: 设备ID
        frame_id: 帧ID
        device_alias: 设备别名
        
    Returns:
        tuple: (VideoFrameDTO, DeviceProcessedDataDTO)
    """
    # 创建彩色测试图像（不同设备使用不同颜色）
    if device_alias == "left_camera":
        # 左相机：蓝色背景
        rgb_frame = np.full((480, 640, 3), [255, 0, 0], dtype=np.uint8)
    else:
        # 右相机：绿色背景
        rgb_frame = np.full((480, 640, 3), [0, 255, 0], dtype=np.uint8)
    
    # 添加设备名称文本
    import cv2
    cv2.putText(
        rgb_frame,
        device_alias,
        (50, 240),
        cv2.FONT_HERSHEY_TRIPLEX,
        2.0,
        (255, 255, 255),
        3
    )
    
    depth_frame = np.zeros((480, 640), dtype=np.uint16)
    
    video_frame = VideoFrameDTO(
        device_id=device_id,
        frame_id=frame_id,
        rgb_frame=rgb_frame,
        depth_frame=depth_frame,
    )
    
    # 创建模拟检测数据（一个检测框）
    coords = np.array([[320, 240, 1000]], dtype=np.float32)
    bbox = np.array([[200, 150, 440, 330]], dtype=np.float32)
    confidence = np.array([0.95], dtype=np.float32)
    labels = np.array([0], dtype=np.int32)
    
    processed_data = DeviceProcessedDataDTO(
        device_id=device_id,
        frame_id=frame_id,
        device_alias=device_alias,
        coords=coords,
        bbox=bbox,
        confidence=confidence,
        labels=labels,
        state_label=[],
    )
    
    return video_frame, processed_data


def main():
    """主测试函数"""
    print("=" * 80)
    print("显示模块按键切换手动测试")
    print("=" * 80)
    print()
    print("测试说明：")
    print("1. 程序将启动显示窗口，显示两个模拟设备的视频流")
    print("2. 请按照以下按键进行测试：")
    print("   - 按 '1' 键：切换到第一个设备（蓝色背景）")
    print("   - 按 '2' 键：切换到第二个设备（绿色背景）")
    print("   - 按 '3' 键：切换到 Combined 模式（双设备拼接）")
    print("   - 按 'F' 键：切换全屏/窗口模式")
    print("   - 按 'Q' 键：退出程序")
    print()
    print("3. 验证每个按键功能是否正常工作")
    print()
    print("按 Enter 键开始测试...")
    input()
    
    # 创建事件总线
    event_bus = EventBus()
    
    # 创建显示配置
    config = DisplayConfigDTO(
        enable_display=True,
        window_width=640,
        window_height=480,
        target_fps=20,
        show_detection_boxes=True,
        show_labels=True,
        show_confidence=True,
        show_fps=True,
        show_device_info=True,
    )
    
    # 设备列表
    devices_list = ["device1", "device2"]
    
    # 创建显示管理器
    display_manager = DisplayManager(
        config=config,
        devices_list=devices_list,
        event_bus=event_bus,
    )
    
    # 启动显示模块
    print("启动显示模块...")
    display_manager.start()
    time.sleep(0.5)
    
    # 模拟数据发送循环
    print("开始发送测试数据...")
    print("窗口应该已经打开，请开始测试按键功能")
    print()
    
    frame_id = 0
    try:
        while display_manager.is_running:
            frame_id += 1
            
            # 为两个设备创建测试数据
            video_frame1, processed_data1 = create_test_frame(
                "device1", frame_id, "left_camera"
            )
            video_frame2, processed_data2 = create_test_frame(
                "device2", frame_id, "right_camera"
            )
            
            # 发布事件
            event_bus.publish(EventType.RAW_FRAME_DATA, video_frame1)
            event_bus.publish(EventType.PROCESSED_DATA, processed_data1)
            event_bus.publish(EventType.RAW_FRAME_DATA, video_frame2)
            event_bus.publish(EventType.PROCESSED_DATA, processed_data2)
            
            # 控制帧率
            time.sleep(0.05)  # 20 FPS
            
    except KeyboardInterrupt:
        print("\n收到中断信号，停止测试...")
    
    # 停止显示模块
    print("停止显示模块...")
    display_manager.stop(timeout=5.0)
    
    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)
    print()
    print("请确认以下功能是否正常：")
    print("✓ 按 '1' 键能切换到第一个设备（蓝色背景）")
    print("✓ 按 '2' 键能切换到第二个设备（绿色背景）")
    print("✓ 按 '3' 键能切换到 Combined 模式（双设备拼接）")
    print("✓ 按 'F' 键能切换全屏/窗口模式")
    print("✓ 按 'Q' 键能退出程序")
    print()


if __name__ == "__main__":
    main()
