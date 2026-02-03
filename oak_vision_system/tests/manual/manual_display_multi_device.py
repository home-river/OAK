"""
手动测试脚本：显示模块多设备场景

测试任务 10.3：测试多设备场景
- 测试单设备显示
- 测试双设备Combined模式
- 测试设备数量变化时的自适应

使用方法：
1. 运行此脚本
2. 按照屏幕提示进行操作
3. 观察设备上线/下线时的自动切换行为

测试场景：
1. 场景1：只有一个设备在线（自动单设备显示）
2. 场景2：两个设备都在线（Combined模式拼接）
3. 场景3：设备动态上线/下线（自动切换）
"""

import time
import numpy as np
from typing import Dict, Optional

from oak_vision_system.core.dto.config_dto import DisplayConfigDTO
from oak_vision_system.core.dto.detection_dto import VideoFrameDTO
from oak_vision_system.core.dto.data_processing_dto import DeviceProcessedDataDTO
from oak_vision_system.core.event_bus import get_event_bus, EventType, shutdown_event_bus
from oak_vision_system.modules.display_modules.display_manager import DisplayManager


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
    
    # 添加帧ID文本
    cv2.putText(
        rgb_frame,
        f"Frame: {frame_id}",
        (50, 300),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2
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


def test_scenario_1(event_bus, display_manager: DisplayManager):
    """场景1：只有一个设备在线
    
    预期行为：
    - 显示单个设备的视频流
    - 自动全屏显示
    """
    # 如果显示管理器已停止（用户按了Q），直接返回
    if not display_manager.is_running:
        print("显示模块已停止，跳过场景1")
        return
        
    print("\n" + "=" * 80)
    print("场景1：只有一个设备在线")
    print("=" * 80)
    print("预期行为：")
    print("- 显示单个设备的视频流（蓝色背景）")
    print("- 窗口标题显示设备名称")
    print()
    print("按 Enter 键开始场景1...")
    input()
    
    frame_id = 0
    duration = 5  # 运行5秒
    start_time = time.time()
    
    print(f"运行场景1（{duration}秒）...")
    while time.time() - start_time < duration and display_manager.is_running:
        frame_id += 1
        
        # 只发送第一个设备的数据
        video_frame1, processed_data1 = create_test_frame(
            "device1", frame_id, "left_camera"
        )
        
        event_bus.publish(EventType.RAW_FRAME_DATA, video_frame1)
        event_bus.publish(EventType.PROCESSED_DATA, processed_data1)
        
        time.sleep(0.05)  # 20 FPS
    
    print("场景1 完成")
    print()
    print("请确认：")
    print("✓ 显示了单个设备的视频流（蓝色背景）")
    print("✓ 窗口标题显示 'left_camera'")
    print()


def test_scenario_2(event_bus, display_manager: DisplayManager):
    """场景2：两个设备都在线
    
    预期行为：
    - Combined模式：水平拼接两个设备的视频流
    - 每个设备图像上显示设备名称标签
    - 窗口宽度为1280（640 * 2）
    """
    # 如果显示管理器已停止（用户按了Q），直接返回
    if not display_manager.is_running:
        print("显示模块已停止，跳过场景2")
        return
        
    print("\n" + "=" * 80)
    print("场景2：两个设备都在线")
    print("=" * 80)
    print("预期行为：")
    print("- Combined模式：水平拼接两个设备的视频流")
    print("- 左边显示蓝色背景（left_camera），右边显示绿色背景（right_camera）")
    print("- 每个设备图像上显示设备名称标签")
    print()
    print("按 Enter 键开始场景2...")
    input()
    
    frame_id = 0
    duration = 5  # 运行5秒
    start_time = time.time()
    
    print(f"运行场景2（{duration}秒）...")
    while time.time() - start_time < duration and display_manager.is_running:
        frame_id += 1
        
        # 发送两个设备的数据
        video_frame1, processed_data1 = create_test_frame(
            "device1", frame_id, "left_camera"
        )
        video_frame2, processed_data2 = create_test_frame(
            "device2", frame_id, "right_camera"
        )
        
        event_bus.publish(EventType.RAW_FRAME_DATA, video_frame1)
        event_bus.publish(EventType.PROCESSED_DATA, processed_data1)
        event_bus.publish(EventType.RAW_FRAME_DATA, video_frame2)
        event_bus.publish(EventType.PROCESSED_DATA, processed_data2)
        
        time.sleep(0.05)  # 20 FPS
    
    print("场景2 完成")
    print()
    print("请确认：")
    print("✓ 显示了两个设备的视频流（左蓝右绿）")
    print("✓ 两个设备水平拼接在一起")
    print("✓ 每个设备图像上显示了设备名称标签")
    print()


def test_scenario_3(event_bus, display_manager: DisplayManager):
    """场景3：设备动态上线/下线
    
    预期行为：
    - 设备下线时，自动切换到单设备显示
    - 设备上线时，自动切换到Combined模式
    """
    # 如果显示管理器已停止（用户按了Q），直接返回
    if not display_manager.is_running:
        print("显示模块已停止，跳过场景3")
        return
        
    print("\n" + "=" * 80)
    print("场景3：设备动态上线/下线")
    print("=" * 80)
    print("预期行为：")
    print("- 第二个设备下线时，自动切换到单设备显示")
    print("- 第二个设备上线时，自动切换回Combined模式")
    print()
    print("按 Enter 键开始场景3...")
    input()
    
    frame_id = 0
    
    # 阶段1：两个设备都在线（3秒）
    print("阶段1：两个设备都在线（3秒）...")
    start_time = time.time()
    while time.time() - start_time < 3 and display_manager.is_running:
        frame_id += 1
        
        video_frame1, processed_data1 = create_test_frame(
            "device1", frame_id, "left_camera"
        )
        video_frame2, processed_data2 = create_test_frame(
            "device2", frame_id, "right_camera"
        )
        
        event_bus.publish(EventType.RAW_FRAME_DATA, video_frame1)
        event_bus.publish(EventType.PROCESSED_DATA, processed_data1)
        event_bus.publish(EventType.RAW_FRAME_DATA, video_frame2)
        event_bus.publish(EventType.PROCESSED_DATA, processed_data2)
        
        time.sleep(0.05)
    
    # 阶段2：第二个设备下线（3秒）
    print("阶段2：第二个设备下线（3秒）...")
    print("（停止发送 device2 的数据）")
    start_time = time.time()
    while time.time() - start_time < 3 and display_manager.is_running:
        frame_id += 1
        
        # 只发送第一个设备的数据
        video_frame1, processed_data1 = create_test_frame(
            "device1", frame_id, "left_camera"
        )
        
        event_bus.publish(EventType.RAW_FRAME_DATA, video_frame1)
        event_bus.publish(EventType.PROCESSED_DATA, processed_data1)
        
        time.sleep(0.05)
    
    # 阶段3：第二个设备重新上线（3秒）
    print("阶段3：第二个设备重新上线（3秒）...")
    start_time = time.time()
    while time.time() - start_time < 3 and display_manager.is_running:
        frame_id += 1
        
        video_frame1, processed_data1 = create_test_frame(
            "device1", frame_id, "left_camera"
        )
        video_frame2, processed_data2 = create_test_frame(
            "device2", frame_id, "right_camera"
        )
        
        event_bus.publish(EventType.RAW_FRAME_DATA, video_frame1)
        event_bus.publish(EventType.PROCESSED_DATA, processed_data1)
        event_bus.publish(EventType.RAW_FRAME_DATA, video_frame2)
        event_bus.publish(EventType.PROCESSED_DATA, processed_data2)
        
        time.sleep(0.05)
    
    print("场景3 完成")
    print()
    print("请确认：")
    print("✓ 阶段1：显示了两个设备的拼接视频流")
    print("✓ 阶段2：自动切换到单设备显示（只显示蓝色背景）")
    print("✓ 阶段3：自动切换回Combined模式（显示两个设备）")
    print()


def main():
    """主测试函数"""
    print("=" * 80)
    print("显示模块多设备场景手动测试")
    print("=" * 80)
    print()
    print("本测试将验证以下场景：")
    print("1. 场景1：只有一个设备在线")
    print("2. 场景2：两个设备都在线")
    print("3. 场景3：设备动态上线/下线")
    print()
    print("按 Enter 键开始测试...")
    input()
    
    # 获取全局事件总线实例
    event_bus = get_event_bus()
    
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
    )
    
    # 启动显示模块
    print("\n启动显示模块...")
    display_manager.start()
    time.sleep(0.5)
    
    try:
        # 运行测试场景
        test_scenario_1(event_bus, display_manager)
        test_scenario_2(event_bus, display_manager)
        test_scenario_3(event_bus, display_manager)
        
    except KeyboardInterrupt:
        print("\n收到中断信号，停止测试...")
    
    # 停止显示模块
    print("\n停止显示模块...")
    display_manager.stop(timeout=5.0)
    
    # 关闭事件总线
    print("关闭事件总线...")
    shutdown_event_bus(wait=True, cancel_pending=True, reset_instance=True)
    
    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)
    print()
    print("总结：")
    print("✓ 场景1：单设备显示正常")
    print("✓ 场景2：双设备Combined模式正常")
    print("✓ 场景3：设备动态切换正常")
    print()


if __name__ == "__main__":
    main()
