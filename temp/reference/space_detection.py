#!/usr/bin/env python3

# ================== 1. 导入所需库 ==================
from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
import time

'''
纯OAK检测版本：只进行目标检测和显示，不包含坐标变换和CAN通信
'''

class OAKDetector:
    def __init__(self):
        # 模型配置
        self.nnPath = str( 'use_model/model1/best_openvino_2022.1_6shave.blob')
        if not Path(self.nnPath).exists():
            raise FileNotFoundError(f'模型文件未找到: {self.nnPath}')

        self.labelMap = ["durian", "person"]
        
        # 控制标志
        self.running = True

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
        camRgb.setPreviewSize(512, 288)
        camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        
        monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoLeft.setCamera("left")
        monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoRight.setCamera("right")
        
        # 配置立体深度
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
        stereo.setOutputSize(monoLeft.getResolutionWidth(), monoLeft.getResolutionHeight())
        stereo.setSubpixel(True)
        
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
        spatialDetectionNetwork.passthrough.link(xoutRgb.input)
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
            color = (255, 255, 255)

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
                    
                    try:
                        label = self.labelMap[detection.label]
                    except:
                        label = detection.label

                    # 绘制标签、置信度和坐标信息
                    cv2.putText(frame, str(label), (x1 + 10, y1 + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, color)
                    cv2.putText(frame, f"{detection.confidence*100:.2f}%", (x1 + 10, y1 + 35), cv2.FONT_HERSHEY_TRIPLEX, 0.5, color)
                    
                    # 显示相机坐标
                    cv2.putText(frame, "Camera Coord:", (x1 + 10, y1 + 50), cv2.FONT_HERSHEY_TRIPLEX, 0.4, (255, 255, 255))
                    cv2.putText(frame, f"X: {int(detection.spatialCoordinates.x)} mm", (x1 + 10, y1 + 65), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color)
                    cv2.putText(frame, f"Y: {int(detection.spatialCoordinates.y)} mm", (x1 + 10, y1 + 80), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color)
                    cv2.putText(frame, f"Z: {int(detection.spatialCoordinates.z)} mm", (x1 + 10, y1 + 95), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color)
                    
                    # 绘制检测框
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # 显示
                cv2.putText(frame, "NN fps: {:.2f}".format(fps), (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color)
                cv2.imshow("depth", depthFrameColor)
                cv2.imshow("rgb", cv2.resize(frame, (800, 600)))

                if cv2.waitKey(1) == ord('q'):
                    self.stop()
                    break

    def start(self):
        """启动系统"""
        # 检测线程在主线程运行
        try:
            self.detection_thread()
        except KeyboardInterrupt:
            self.stop()
        
        cv2.destroyAllWindows()

    def stop(self):
        """停止系统"""
        self.running = False


if __name__ == "__main__":
    detector = OAKDetector()
    detector.start()
