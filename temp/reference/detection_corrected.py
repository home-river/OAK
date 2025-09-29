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

# 导入自定义的坐标计算模块
from oak_modules.calculate_module import *
from oak_modules.coordinate_corrector import CoordinateCorrector
# 导入CAN通信模块
from oak_modules.can_module import CANCommunicator

'''
简化的两线程版本：检测线程 + CAN线程（无打印版本）
'''

class OAKDetector:
    def __init__(self, enable_can=True, can_bitrate=250000):
        """
        初始化OAK检测器
        
        Args:
            enable_can: 是否启用CAN通信，默认为True
            can_bitrate: CAN通信波特率，默认为250000
        """
        # 模型配置
        self.nnPath = str((Path(__file__).parent / 'best_openvino_2022.1_6shave.blob').resolve())
        if not Path(self.nnPath).exists():
            raise FileNotFoundError(f'模型文件未找到: {self.nnPath}')

        self.labelMap = ["durian", "person"]
        self.coordinate_corrector = CoordinateCorrector()
        self.correction_strategy = "regression"  # 使用新的线性回归修正策略
        self.enabled_correction = True  # 启用坐标修正
        
        # CAN通信配置
        self.enable_can = enable_can
        self.can_bitrate = can_bitrate

        # 分辨率设计
        self.previewWIDTH = 512
        self.previewHEIGHT= 288
        self.videoWIDTH = 1920
        self.videoHEIGHT = 1080
        
        # 共享数据和锁
        self.shared_data = {
            'durian': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'timestamp': 0},
            'person': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'timestamp': 0}
        }
        self.data_lock = threading.Lock()
        
        # 控制标志
        self.running = True
        
        # 人员检测时间跟踪
        self.last_person_detection_time = 1.0
        self.person_timeout_seconds = 3.0  # 3秒超时
        
        # 显示模式控制
        self.fullscreen_mode = False  # False: 960x540模式, True: 全屏模式
        
        # 初始化计算模块
        # calibration = KinematicCalibration(Tx=-1500, Ty=-760, Tz=1200, Ry=22.9, Rz=-25.2)
        calibration = KinematicCalibration(Tx=-1500, Ty=-900, Tz=1200, Ry=21.0, Rz=-22)
        self.calc_module = FilteredCalculateModule(self.labelMap, calibration, filter_window_size=20)
        
        # 根据配置决定是否初始化CAN模块
        if self.enable_can:
            self.can_comm = CANCommunicator(self.shared_data, self.data_lock, bitrate=self.can_bitrate)
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
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_ACCURACY)
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
        spatialDetectionNetwork.setDepthUpperThreshold(5000)
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

    def detection_thread(self):
        """检测线程"""
        pipeline = self.create_pipeline()
        
        with dai.Device(pipeline) as device:
            previewQueue = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            detectionNNQueue = device.getOutputQueue(name="detections", maxSize=4, blocking=False)
            depthQueue = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
            networkQueue = device.getOutputQueue(name="nnNetwork", maxSize=4, blocking=False)

            startTime = time.monotonic()
            counter = 0
            fps = 0
            color = (0, 255, 0)  # 绿色框
            text_color = (0, 255, 255)  # 黄色文字 (BGR格式)

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
                    trans_coord = self.calc_module.coordinate_transformer.transform_point(raw_coords)

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

                # 坐标处理和更新共享数据
                filtered_coords = self.calc_module.process_and_get_final_coords(detections)
                

                if self.enabled_correction:
                    # 应用坐标修正
                    final_coords = {}
                    for obj_type, coords in filtered_coords.items():
                        if obj_type == "durian" and coords != (0.0, 0.0, 0.0):
                            # 对榴莲坐标应用固定修正
                            final_coords[obj_type] = self.coordinate_corrector.apply_correction(coords,strategy=self.correction_strategy)
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
                        self.calc_module.reset_person_filters()
                        self.last_person_detection_time = 0  # 重置时间戳，避免重复清空
                
                with self.data_lock:
                    for obj_type, coords in final_coords.items():
                        if obj_type in self.shared_data:
                            self.shared_data[obj_type].update({
                                'x': coords[0],
                                'y': coords[1], 
                                'z': coords[2],
                                'timestamp': current_time
                            })

                # 显示模式状态提示
                mode_text = "960x540 Mode (Press F)" if not self.fullscreen_mode else "Fullscreen Mode (Press F)"
                cv2.putText(frame, mode_text, (2, 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (0, 255, 0))
                
                # 显示FPS
                cv2.putText(frame, "NN fps: {:.2f}".format(fps), (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color)
                
                # 深度图显示
                cv2.imshow("depth", depthFrameColor)
                
                # RGB图像显示 - 根据模式选择尺寸
                if not self.fullscreen_mode:
                    # 960x540模式
                    cv2.namedWindow("rgb", cv2.WINDOW_NORMAL)
                    cv2.setWindowProperty("rgb", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                    cv2.imshow("rgb", cv2.resize(frame, (960, 540)))
                else:
                    # 全屏模式
                    cv2.namedWindow("rgb", cv2.WINDOW_NORMAL)
                    cv2.setWindowProperty("rgb", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    cv2.imshow("rgb", frame)

                # 按键处理
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.stop()
                    break
                elif key == ord('f') or key == ord('F'):
                    # 切换显示模式
                    self.fullscreen_mode = not self.fullscreen_mode
                    print(f"切换到{'960x540' if not self.fullscreen_mode else '全屏'}模式")

    def start(self):
        """启动系统"""
        # 根据配置决定是否启动CAN线程
        if self.enable_can and self.can_comm is not None:
            can_thread = threading.Thread(target=lambda: self.can_comm.start_thread())
            can_thread.daemon = True
            can_thread.start()
            print("CAN通信线程已启动")
        else:
            print("跳过CAN通信线程启动")
        
        # 检测线程在主线程运行
        try:
            self.detection_thread()
        except KeyboardInterrupt:
            self.stop()
        
        cv2.destroyAllWindows()

    def stop(self):
        """停止系统"""
        self.running = False
        if self.enable_can and self.can_comm is not None:
            self.can_comm.stop_thread()
            print("CAN通信已停止")
        else:
            print("无需停止CAN通信")


if __name__ == "__main__":
    # 使用示例：
    # 1. 启用CAN通信（默认）
    # detector = OAKDetector()
    
    # 2. 禁用CAN通信
    # detector = OAKDetector(enable_can=False)
    
    # 3. 启用CAN通信并指定波特率
    # detector = OAKDetector(enable_can=True, can_bitrate=500000)
    
    # 默认配置：启用CAN通信
    detector = OAKDetector()
    detector.start()
