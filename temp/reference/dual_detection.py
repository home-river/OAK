"""
双OAK设备检测系统
通过设备管理器获取多个OAK设备的MXid，为每个设备启动独立的检测线程，
分别处理数据并融合为最优结果，最后写入CAN通信共享数据区。

按键控制说明:
- 1: 左相机RGB显示
- 2: 右相机RGB显示  
- 3: 合并显示
- F: 切换全屏/窗口模式
- Q: 退出系统
"""

#!/usr/bin/env python3

# ================== 1. 导入所需库 ==================
from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
import time
import threading
from math import pi
from typing import Dict, List, Tuple, Optional

# 导入自定义的坐标计算模块
from oak_modules.calculate_module import *
from oak_modules.coordinate_corrector import CoordinateCorrector
# 导入CAN通信模块
from oak_modules.can_module import CANCommunicator
# 导入OAK设备管理器
from oak_modules.oak_device_manager import OAKDeviceManager

'''
双OAK检测系统：多设备并行检测 + 数据融合 + CAN通信
'''
current_path = Path(__file__).parent
class DualOAKDetector:
    def __init__(self, config_file=current_path/"configs/dual_oak_config.json", enable_alert=False,enable_can=False, can_bitrate=250000):
        """
        初始化双OAK检测器
        
        Args:
            config_file: OAK设备配置文件路径
            enable_can: 是否启用CAN通信，默认为True
            can_bitrate: CAN通信波特率，默认为250000
        """
        # 模型配置
        self.nnPath = str((Path(__file__).parent / 'best_openvino_2022.1_6shave.blob').resolve())
        if not Path(self.nnPath).exists():
            raise FileNotFoundError(f'模型文件未找到: {self.nnPath}')

        self.labelMap = ["durian", "person"]
        self.coordinate_corrector = CoordinateCorrector()
        self.left_correction_strategy = "left_regression"  # 使用新的线性回归修正策略
        self.right_correction_strategy = "right_regression"  # 使用新的线性回归修正策略
        self.enabled_correction = True  # 启用坐标修正
        
        # CAN通信配置
        self.enable_can = enable_can
        self.can_bitrate = can_bitrate
        self.enable_alert = enable_alert

        # 分辨率设计
        self.previewWIDTH = 512
        self.previewHEIGHT= 288
        self.videoWIDTH = 1920
        self.videoHEIGHT = 1080
        
        # 初始化OAK设备管理器
        self.device_manager = OAKDeviceManager(str(config_file))
        
        # 尝试加载配置文件，如果失败则创建新配置
        loaded_config = self.device_manager.load()
        if loaded_config is None:
            print(f"配置文件 {config_file} 不存在或加载失败，正在创建双设备配置...")
            self._create_dual_device_config(str(config_file))
        
        # 获取配置的设备列表
        self.devices = self._get_configured_devices()
        if not self.devices:
            print("配置文件中无设备配置，尝试发现连接的设备并应用双设备配置...")
            self._setup_dual_devices()
            # 重新获取设备列表
            self.devices = self._get_configured_devices()
            if not self.devices:
                raise ValueError("未发现任何OAK设备，请检查设备连接")
        
        print(f"发现 {len(self.devices)} 个配置的OAK设备:")
        for alias, device_info in self.devices.items():
            print(f"  - {alias}: {device_info['mxid']}")
        
        # 多设备数据存储结构
        self.device_data = {}  # 按设备别名存储原始数据
        self.device_calc_modules = {}  # 每个设备的计算模块
        self.device_threads = {}  # 设备检测线程
        
        # 图像缓存用于合并显示
        self.device_frames = {}  # 存储每个设备的最新帧
        self.frame_lock = threading.Lock()  # 帧数据锁
        
        # 初始化每个设备的数据结构和计算模块
        for alias, device_info in self.devices.items():
            # 获取设备的外参配置
            kinematics = self.device_manager.get_kinematics(alias)
            calibration = KinematicCalibration(
                Tx=kinematics.get('Tx', 0.0),
                Ty=kinematics.get('Ty', 0.0),
                Tz=kinematics.get('Tz', 0.0),
                Ry=kinematics.get('Ry', 0.0),
                Rz=kinematics.get('Rz', 0.0)
            )
            
            # 为每个设备创建独立的计算模块
            self.device_calc_modules[alias] = FilteredCalculateModule(
                self.labelMap, calibration, filter_window_size=20
            )
            
            # 初始化设备数据存储
            self.device_data[alias] = {
                'durian': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'timestamp': 0},
                'person': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'timestamp': 0}
            }
            
            # 初始化设备帧缓存
            self.device_frames[alias] = {
                'rgb': None,
                'depth': None,
                'timestamp': 0
            }
        
        # 初始化CAN模块数据
        self.can_data = {
            'durian': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'timestamp': 0, 'source_device': ''},
            'person': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'timestamp': 0, 'source_device': ''}
        }
        
        self.data_lock = threading.Lock()
        
        # 控制标志
        self.running = True
        
        # 人员检测时间跟踪
        self.last_person_detection_time = 1.0
        self.person_timeout_seconds = 5.0  # 3秒超时
        
        # 显示模式控制
        self.fullscreen_mode = False  # False: 窗口模式, True: 全屏模式
        self.display_mode = "combined"  # "combined", "oak_left", "oak_right"
        
        # 根据配置决定是否初始化CAN模块（使用融合数据）
        if self.enable_can:
            self.can_comm = CANCommunicator(
                self.can_data, 
                self.data_lock, 
                interface='socketcan',
                channel='can0',
                bitrate=self.can_bitrate, 
                auto_configure=True,
                enable_alert=self.enable_alert
            )
            print(f"CAN通信已启用，波特率: {self.can_bitrate}")
        else:
            self.can_comm = None
            print("CAN通信已禁用")

    def create_pipeline(self):
        """创建pipeline"""
        pipeline = dai.Pipeline()
        
        # 创建节点
        camRgb = pipeline.create(dai.node.ColorCamera)
        spatialDetectionNetwork = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
        monoLeft = pipeline.create(dai.node.MonoCamera)
        monoRight = pipeline.create(dai.node.MonoCamera)
        stereo = pipeline.create(dai.node.StereoDepth)
        
        # 输出队列
        xoutRgb = pipeline.create(dai.node.XLinkOut)
        xoutNN = pipeline.create(dai.node.XLinkOut)
        xoutDepth = pipeline.create(dai.node.XLinkOut)
        nnNetworkOut = pipeline.create(dai.node.XLinkOut)
        
        xoutRgb.setStreamName("rgb")
        xoutNN.setStreamName("detections")
        xoutDepth.setStreamName("depth")
        nnNetworkOut.setStreamName("nnNetwork")
        
        # 配置相机
        camRgb.setPreviewSize(self.previewWIDTH, self.previewHEIGHT)
        camRgb.setVideoSize(self.videoWIDTH,self.videoHEIGHT)
        camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        
        monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoLeft.setCamera("left")
        monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoRight.setCamera("right")
        
        # 配置立体深度
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
        stereo.setOutputSize(monoLeft.getResolutionWidth(), monoLeft.getResolutionHeight())
        stereo.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7)
        stereo.setSubpixel(True)
        stereo.setLeftRightCheck(True)
        stereo.setExtendedDisparity(False)
        
        
        
        # 配置检测网络
        spatialDetectionNetwork.setBlobPath(self.nnPath)
        spatialDetectionNetwork.setConfidenceThreshold(0.5)
        spatialDetectionNetwork.input.setBlocking(False)
        spatialDetectionNetwork.setBoundingBoxScaleFactor(0.5)
        spatialDetectionNetwork.setDepthLowerThreshold(400)
        spatialDetectionNetwork.setDepthUpperThreshold(7000)
        spatialDetectionNetwork.setNumClasses(2)
        spatialDetectionNetwork.setCoordinateSize(4)
        spatialDetectionNetwork.setIouThreshold(0.5)
        
        # 连接节点
        monoLeft.out.link(stereo.left)
        monoRight.out.link(stereo.right)
        camRgb.preview.link(spatialDetectionNetwork.input)
        # spatialDetectionNetwork.passthrough.link(xoutRgb.input)
        camRgb.video.link(xoutRgb.input)
        spatialDetectionNetwork.out.link(xoutNN.input)
        stereo.depth.link(spatialDetectionNetwork.inputDepth)
        spatialDetectionNetwork.passthroughDepth.link(xoutDepth.input)
        spatialDetectionNetwork.outNetwork.link(nnNetworkOut.input)
        
        return pipeline
    
    def _get_configured_devices(self):
        """从配置中获取所有设备信息"""
        devices = {}
        config_devices = self.device_manager.config.get("devices", {})
        
        # 检查devices字段的格式
        if isinstance(config_devices, dict):
            # 处理字典格式的设备配置（以MXid为key）
            for mxid, device_config in config_devices.items():
                alias = device_config.get("alias")
                if alias:
                    devices[alias] = {
                        'mxid': mxid,  # 使用字典的key作为mxid
                        'kinematics': device_config.get("kinematics", {}),
                        'alias': alias
                    }
        elif isinstance(config_devices, list):
            # 处理列表格式的设备配置
            for device_config in config_devices:
                mxid = device_config.get("mxid")
                alias = device_config.get("alias")
                if mxid and alias:
                    devices[alias] = {
                        'mxid': mxid,
                        'kinematics': device_config.get("kinematics", {}),
                        'alias': alias
                    }
        else:
            print(f"警告: 不支持的devices配置格式: {type(config_devices)}")
        
        return devices
    
    def _create_dual_device_config(self, config_file: str):
        """创建双设备硬编码配置文件"""
        config_path = Path(config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建空的设备管理器来生成基础配置
        temp_manager = OAKDeviceManager(config_file)
        temp_manager.save()  # 保存空配置
        print(f"已创建双设备配置文件: {config_file}")
    
    def _setup_dual_devices(self):
        """设置双设备硬编码配置"""
        try:
            # 获取连接的设备
            connected_devices = self.device_manager.list_connected()
            
            if not connected_devices:
                print("未发现连接的OAK设备")
                return
            
            if len(connected_devices) < 2:
                print(f"只发现 {len(connected_devices)} 个设备，双设备系统需要至少2个设备")
                print("将使用发现的设备创建配置...")
            
            # 硬编码的双设备配置
            dual_config = [
                {
                    "alias": "oak_left",
                    "kinematics": {
                        "Tx": -1650.0,
                        "Ty": -900.0,  # 左侧设备
                        "Tz": 1200.0,
                        "Ry": 19.8,
                        "Rz": -31
                    }
                },
                {
                    "alias": "oak_right", 
                    "kinematics": {
                        "Tx": -1550.0,
                        "Ty": 900.0,   # 右侧设备，镜像对称
                        "Tz": 1200.0,
                        "Ry": 20.5,
                        "Rz": 29.1     # 偏航角镜像对称
                    }
                }
            ]
            
            # 为连接的设备分配配置
            mxids = []
            aliases = []
            kinematics_list = []
            
            for i, device in enumerate(connected_devices[:2]):  # 只取前两个设备
                mxid = device['mxid']
                config = dual_config[i] if i < len(dual_config) else dual_config[0]
                
                mxids.append(mxid)
                aliases.append(config["alias"])
                kinematics_list.append(config["kinematics"])
                
                print(f"  配置设备 {config['alias']}: {mxid}")
            
            # 创建双设备配置
            self.device_manager.create_new_config(
                mxids=mxids,
                aliases=aliases,
                kinematics_list=kinematics_list,
                filter_type="moving_average",
                filter_window=5
            )
            
            # 保存配置到文件
            self.device_manager.save()
            
            print(f"成功创建双设备配置，共 {len(mxids)} 个设备")
                
        except Exception as e:
            print(f"设置双设备配置时出现错误: {e}")
            import traceback
            traceback.print_exc()

    def fuse_device_data(self):
        """融合多设备数据，选择最近的目标"""
        current_time = time.time()
        
        with self.data_lock:
            for obj_type in ['durian', 'person']:
                best_device = None
                min_distance = float('inf')
                best_data = None
                
                # 遍历所有设备的数据
                for device_alias, device_data in self.device_data.items():
                    obj_data = device_data[obj_type]
                    
                    # 检查数据有效性（时间戳不能太旧）
                    if current_time - obj_data['timestamp'] > 2.0:  # 2秒超时
                        continue
                    
                    # 检查坐标是否有效
                    if obj_data['x'] == 0.0 and obj_data['y'] == 0.0 and obj_data['z'] == 0.0:
                        continue
                    
                    # 计算到原点的距离
                    distance = np.sqrt(obj_data['x']**2 + obj_data['y']**2 + obj_data['z']**2)
                    
                    if distance < min_distance and distance > 0:
                        min_distance = distance
                        best_device = device_alias
                        best_data = obj_data
                
                # 更新融合数据
                if best_device and best_data:
                    self.can_data[obj_type].update({
                        'x': best_data['x'],
                        'y': best_data['y'],
                        'z': best_data['z'],
                        'timestamp': best_data['timestamp'],
                        'source_device': best_device
                    })
                else:
                    # 如果没有有效数据，清空融合数据
                    self.can_data[obj_type].update({
                        'x': 0.0,
                        'y': 0.0,
                        'z': 0.0,
                        'timestamp': 0,
                        'source_device': ''
                    })
    
    def create_combined_display(self):
        """创建合并的显示窗口"""
        with self.frame_lock:
            # 收集所有设备的有效帧
            rgb_frames = []
            depth_frames = []
            device_names = []
            
            for alias, frame_data in self.device_frames.items():
                if frame_data['rgb'] is not None and frame_data['depth'] is not None:
                    # 调整RGB帧大小为统一尺寸
                    rgb_resized = cv2.resize(frame_data['rgb'], (640, 480))
                    depth_resized = cv2.resize(frame_data['depth'], (640, 480))
                    
                    rgb_frames.append(rgb_resized)
                    depth_frames.append(depth_resized)
                    device_names.append(alias)
            
            if not rgb_frames:
                return None, None
            
            # 水平拼接RGB图像
            if len(rgb_frames) == 1:
                combined_rgb = rgb_frames[0]
            else:
                combined_rgb = np.hstack(rgb_frames)
            
            # 水平拼接深度图像
            if len(depth_frames) == 1:
                combined_depth = depth_frames[0]
            else:
                combined_depth = np.hstack(depth_frames)
            
            # 在图像上添加设备名称标签
            for i, name in enumerate(device_names):
                x_offset = i * 640
                cv2.putText(combined_rgb, f"{name}", (x_offset + 10, 30), 
                           cv2.FONT_HERSHEY_TRIPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(combined_depth, f"{name}", (x_offset + 10, 30), 
                           cv2.FONT_HERSHEY_TRIPLEX, 0.7, (255, 255, 255), 2)
            
            return combined_rgb, combined_depth
    
    def create_single_display(self, device_alias: str):
        """创建单设备RGB显示"""
        with self.frame_lock:
            if device_alias in self.device_frames:
                frame_data = self.device_frames[device_alias]
                if frame_data['rgb'] is not None:
                    # 根据全屏模式调整尺寸
                    if self.fullscreen_mode:
                        rgb_frame = cv2.resize(frame_data['rgb'], (1920, 1080))
                    else:
                        rgb_frame = cv2.resize(frame_data['rgb'], (1280, 720))
                    
                    # 添加设备信息和状态提示
                    device_name = device_alias.replace('_', ' ').title()
                    font_scale = 1.2 if self.fullscreen_mode else 0.8
                    thickness = 3 if self.fullscreen_mode else 2
                    
                    cv2.putText(rgb_frame, f"{device_name} - RGB View", 
                               (20, 50), cv2.FONT_HERSHEY_TRIPLEX, font_scale, (0, 255, 255), thickness)
                    
                    # 添加模式和按键提示
                    mode_text = "Fullscreen" if self.fullscreen_mode else "Window"
                    cv2.putText(rgb_frame, f"Mode: {mode_text}", 
                               (20, rgb_frame.shape[0] - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    
                    help_text = "1:Left 2:Right 3:Combined F:Fullscreen Q:Quit"
                    cv2.putText(rgb_frame, help_text, 
                               (20, rgb_frame.shape[0] - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    
                    return rgb_frame
        return None
    
    def toggle_fullscreen(self, window_name: str):
        """切换全屏模式"""
        self.fullscreen_mode = not self.fullscreen_mode
        if self.fullscreen_mode:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            print("切换到全屏模式")
        else:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
            print("切换到窗口模式")
    
    def device_detection_thread(self, device_alias: str, mxid: str):
        """为特定设备运行的检测线程"""
        pipeline = self.create_pipeline()
        device_info = dai.DeviceInfo(mxid)
        
        print(f"启动设备 {device_alias} ({mxid}) 的检测线程")
        
        try:
            with dai.Device(pipeline, device_info,usb2Mode=True) as device:
                previewQueue = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
                detectionNNQueue = device.getOutputQueue(name="detections", maxSize=4, blocking=False)
                depthQueue = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
                networkQueue = device.getOutputQueue(name="nnNetwork", maxSize=4, blocking=False)

                startTime = time.monotonic()
                counter = 0
                fps = 0
                color = (0, 255, 0)  # 绿色框
                text_color = (255, 255, 255)  # 白色文字 (BGR格式)

                while self.running:
                    # 获取数据
                    inPreview = previewQueue.get()
                    inDet = detectionNNQueue.get()
                    depth = depthQueue.get()
                    inNN = networkQueue.get()

                    # 处理图像
                    frame = inPreview.getCvFrame()
                    depthFrame = depth.getFrame()
                    detections = inDet.detections

                    # 深度图处理
                    depth_downscaled = depthFrame[::4]
                    if np.all(depth_downscaled == 0):
                        min_depth = 0
                    else:
                        min_depth = np.percentile(depth_downscaled[depth_downscaled != 0], 1)
                    max_depth = np.percentile(depth_downscaled, 99)
                    depthFrameColor = np.interp(depthFrame, (min_depth, max_depth), (0, 255)).astype(np.uint8)
                    depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_HOT)

                    # FPS计算
                    counter += 1
                    current_time = time.monotonic()
                    if (current_time - startTime) > 1:
                        fps = counter / (current_time - startTime)
                        counter = 0
                        startTime = current_time

                    # 绘制检测结果
                    height = frame.shape[0]
                    width = frame.shape[1]
                    for detection in detections:
                        # 深度图ROI
                        roiData = detection.boundingBoxMapping
                        roi = roiData.roi
                        roi = roi.denormalize(depthFrameColor.shape[1], depthFrameColor.shape[0])
                        topLeft = roi.topLeft()
                        bottomRight = roi.bottomRight()
                        cv2.rectangle(depthFrameColor, (int(topLeft.x), int(topLeft.y)), 
                                    (int(bottomRight.x), int(bottomRight.y)), color, 1)

                        # RGB图检测框
                        x1 = int(detection.xmin * width)
                        x2 = int(detection.xmax * width)
                        y1 = int(detection.ymin * height)
                        y2 = int(detection.ymax * height)
                        
                        # 获取标签
                        try:
                            label = self.labelMap[detection.label]
                        except:
                            label = detection.label

                        # 直接转换当前检测框的坐标
                        raw_coords = (
                            detection.spatialCoordinates.x,
                            detection.spatialCoordinates.y,
                            detection.spatialCoordinates.z
                        )
                        trans_coord = self.device_calc_modules[device_alias].coordinate_transformer.transform_point(raw_coords)

                        # 绘制标签、置信度和坐标信息
                        cv2.putText(frame, str(label), (x1 + 10, y1 + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, text_color)
                        cv2.putText(frame, f"{detection.confidence*100:.2f}%", (x1 + 10, y1 + 35), cv2.FONT_HERSHEY_TRIPLEX, 0.5, text_color)
                        
                        # 显示变换后坐标
                        cv2.putText(frame, "Transform Coord:", (x1 + 10, y1 + 50), cv2.FONT_HERSHEY_TRIPLEX, 0.4, text_color)
                        cv2.putText(frame, f"X: {int(trans_coord[0])} mm", (x1 + 10, y1 + 65), cv2.FONT_HERSHEY_TRIPLEX, 0.4, text_color)
                        cv2.putText(frame, f"Y: {int(trans_coord[1])} mm", (x1 + 10, y1 + 80), cv2.FONT_HERSHEY_TRIPLEX, 0.4, text_color)
                        cv2.putText(frame, f"Z: {int(trans_coord[2])} mm", (x1 + 10, y1 + 95), cv2.FONT_HERSHEY_TRIPLEX, 0.4, text_color)
                        
                        # 绘制检测框
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                    # 获取该设备的计算模块
                    calc_module = self.device_calc_modules[device_alias]
                    
                    # 坐标处理和更新设备数据
                    filtered_coords = calc_module.process_and_get_final_coords_v2(detections)
                    
                    if self.enabled_correction:
                        # 应用坐标修正 - 根据设备别名选择修正策略
                        final_coords = {}
                        for obj_type, coords in filtered_coords.items():
                            if obj_type == "durian" and coords != (0.0, 0.0, 0.0):
                                # 根据设备别名选择修正策略
                                if device_alias == "oak_left":
                                    final_coords[obj_type] = self.coordinate_corrector.apply_correction(coords, strategy=self.left_correction_strategy)
                                elif device_alias == "oak_right":
                                    final_coords[obj_type] = self.coordinate_corrector.apply_correction(coords, strategy=self.right_correction_strategy)
                                else:
                                    # 未知设备，不修正
                                    final_coords[obj_type] = coords
                            else:
                                # 人员坐标不修正
                                final_coords[obj_type] = coords
                    else:
                        final_coords = filtered_coords.copy()
                    
                    # 检查是否检测到人员，更新人员检测时间
                    current_time = time.time()
                    person_detected = False
                    for detection in detections:
                        try:
                            label = self.labelMap[detection.label]
                            if label == "person":
                                person_detected = True
                                self.last_person_detection_time = current_time
                                break
                        except:
                            pass
                    
                    # 检查人员检测超时，如果超过3秒未检测到人员，清空人员历史信息
                    if not person_detected and self.last_person_detection_time > 0:
                        time_since_last_person = current_time - self.last_person_detection_time
                        if time_since_last_person > self.person_timeout_seconds:
                            calc_module.reset_person_filters()
                            self.last_person_detection_time = 0  # 重置时间戳，避免重复清空
                    
                    # 更新该设备的数据
                    with self.data_lock:
                        for obj_type, coords in final_coords.items():
                            if obj_type in self.device_data[device_alias]:
                                self.device_data[device_alias][obj_type].update({
                                    'x': coords[0],
                                    'y': coords[1],
                                    'z': coords[2],
                                    'timestamp': current_time
                                })
                    
                    # 触发数据融合
                    self.fuse_device_data()

                    # 简化显示信息
                    cv2.putText(frame, f"{device_alias}", (2, 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (0, 255, 0))
                    cv2.putText(frame, "NN fps: {:.2f}".format(fps), (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color)
                    
                    # 更新共享帧缓存
                    with self.frame_lock:
                        self.device_frames[device_alias]['rgb'] = frame.copy()
                        self.device_frames[device_alias]['depth'] = depthFrameColor.copy()
        
        except Exception as e:
            print(f"设备 {device_alias} 检测线程出现错误: {e}")
        finally:
            print(f"设备 {device_alias} 检测线程已停止")

    def main_display_loop(self):
        """主显示循环 - 支持按键切换显示模式和全屏"""
        print("\n双OAK检测系统已启动")
        print("按键控制:")
        print("  1 - 左相机RGB显示")
        print("  2 - 右相机RGB显示")
        print("  3 - 合并显示")
        print("  F - 切换全屏/窗口模式")
        print("  Q - 退出系统")
        
        current_window = "OAK Display"
        
        try:
            while self.running:
                display_frame = None
                
                # 根据显示模式选择显示内容
                if self.display_mode == "combined":
                    combined_rgb, combined_depth = self.create_combined_display()
                    if combined_rgb is not None:
                        # 为合并显示添加提示信息
                        if self.fullscreen_mode:
                            display_frame = cv2.resize(combined_rgb, (1920, 1080))
                        else:
                            display_frame = cv2.resize(combined_rgb, (1280, 480))
                        
                        # 添加模式和按键提示
                        mode_text = "Fullscreen" if self.fullscreen_mode else "Window"
                        cv2.putText(display_frame, f"Combined View - {mode_text}", 
                                   (20, 40), cv2.FONT_HERSHEY_TRIPLEX, 0.8, (0, 255, 255), 2)
                        
                        help_text = "1:Left 2:Right 3:Combined F:Fullscreen Q:Quit"
                        cv2.putText(display_frame, help_text, 
                                   (20, display_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                
                elif self.display_mode in ["oak_left", "oak_right"]:
                    display_frame = self.create_single_display(self.display_mode)
                
                # 显示图像
                if display_frame is not None:
                    cv2.imshow(current_window, display_frame)
                
                # 检查按键
                key = cv2.waitKey(30) & 0xFF
                if key == ord('q') or key == ord('Q'):
                    print("用户按下 'Q' 键，正在退出...")
                    break
                elif key == ord('1'):
                    self.display_mode = "oak_left"
                    print("切换到左相机RGB显示")
                elif key == ord('2'):
                    self.display_mode = "oak_right"
                    print("切换到右相机RGB显示")
                elif key == ord('3'):
                    self.display_mode = "combined"
                    print("切换到合并显示")
                elif key == ord('f') or key == ord('F'):
                    self.toggle_fullscreen(current_window)
                
                # 检查是否有CAN数据需要发送
                if self.enable_can and hasattr(self, 'can_comm'):
                    # 这里可以添加CAN数据发送逻辑
                    pass
                    
        except KeyboardInterrupt:
            print("\n检测到键盘中断，正在停止系统...")
        finally:
            self.stop()
            cv2.destroyAllWindows()
    
    def print_fused_status(self):
        """打印融合数据状态"""
        with self.data_lock:
            print("\n=== 融合数据状态 ===")
            for obj_type, data in self.can_data.items():
                if data['timestamp'] > 0:
                    print(f"{obj_type}: ({data['x']:.1f}, {data['y']:.1f}, {data['z']:.1f}) from {data['source_device']}")
                else:
                    print(f"{obj_type}: 无有效数据")
    
    def print_device_status(self):
        """打印所有设备数据状态"""
        with self.data_lock:
            print("\n=== 设备数据状态 ===")
            for device_alias, device_data in self.device_data.items():
                print(f"设备 {device_alias}:")
                for obj_type, data in device_data.items():
                    if data['timestamp'] > 0:
                        age = time.time() - data['timestamp']
                        print(f"  {obj_type}: ({data['x']:.1f}, {data['y']:.1f}, {data['z']:.1f}) [{age:.1f}s ago]")
                    else:
                        print(f"  {obj_type}: 无数据")
    
    def start(self):
        """启动双OAK检测系统"""
        print(f"\n启动双OAK检测系统，共 {len(self.devices)} 个设备")
        
        # 启动CAN通信线程（使用融合数据）
        if self.enable_can and self.can_comm is not None:
            can_thread = threading.Thread(target=lambda: self.can_comm.start_thread())
            can_thread.daemon = True
            can_thread.start()
            print("CAN通信线程已启动（使用融合数据）")
        else:
            print("跳过CAN通信线程启动")
        
        # 为每个设备启动检测线程
        for alias, device_info in self.devices.items():
            mxid = device_info['mxid']
            thread = threading.Thread(
                target=self.device_detection_thread,
                args=(alias, mxid),
                name=f"Detection-{alias}"
            )
            thread.daemon = True
            thread.start()
            self.device_threads[alias] = thread
            print(f"已启动设备 {alias} ({mxid}) 的检测线程")
        
        # 等待线程启动
        time.sleep(2)
        
        # 主线程处理用户输入和显示
        self.main_display_loop()

    def stop(self):
        """停止系统"""
        print("\n正在停止双OAK检测系统...")
        self.running = False
        
        # 等待检测线程结束
        for alias, thread in self.device_threads.items():
            if thread.is_alive():
                print(f"等待设备 {alias} 线程结束...")
                thread.join(timeout=2)
        
        # 停止CAN通信
        if self.enable_can and self.can_comm is not None:
            self.can_comm.stop_thread()
            print("CAN通信已停止")
        else:
            print("无需停止CAN通信")
        
        print("双OAK检测系统已完全停止")


if __name__ == "__main__":
    # 使用示例：
    # 1. 使用默认配置文件启动双OAK系统
    # detector = DualOAKDetector()
    
    # 2. 指定配置文件和禁用CAN通信
    # detector = DualOAKDetector("configs/my_dual_config.json", enable_can=False)
    
    # 3. 启用CAN通信并指定波特率
    # detector = DualOAKDetector(enable_can=True, can_bitrate=500000)
    
    try:
        # 默认配置：启用CAN通信
        detector = DualOAKDetector()
        detector.start()
    except FileNotFoundError as e:
        print(f"配置文件未找到: {e}")
        print("请先创建双OAK配置文件，或运行设备管理器测试脚本创建配置")
    except ValueError as e:
        print(f"配置错误: {e}")
    except Exception as e:
        print(f"系统启动失败: {e}")
        import traceback
        traceback.print_exc()
