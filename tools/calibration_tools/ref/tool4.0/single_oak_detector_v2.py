from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
import time
import threading
import tkinter as tk
from tkinter import ttk

# 添加reference目录到路径，以便导入模块
sys.path.append(str(Path(__file__).parent.parent / 'reference'))

from calculate_module import FilteredCalculateModule, KinematicCalibration
from can_module import CANCommunicator

"""
单OAK设备检测脚本 - 2.0版本主检测器类
继承自single_oak_with_tuning_v2.py的GUI组件
"""

class SingleOAKDetectorWithTuningV2:
    def __init__(self):
        # 模型配置
        self.nnPath = str(Path(__file__).parent / "best_openvino_2022.1_6shave.blob")
        if not Path(self.nnPath).exists():
            print(f"警告: 模型文件未找到 {self.nnPath}")
            print("请确保模型文件存在，或修改路径")
            
        self.labelMap = ["durian", "person"]
        
        # 颜色配置 - 方便管理和调整
        self.colors = {
            'detection_box': (0, 255, 0),      # 检测框颜色 - 绿色
            'depth_roi': (255, 255, 255),      # 深度图ROI框颜色 - 白色
            'label_text': (0, 255, 0),         # 标签文字颜色 - 绿色
            'confidence_text': (0, 255, 0),    # 置信度文字颜色 - 绿色
            'coordinates_text': (255, 255, 255), # 坐标文字颜色 - 白色
            'filtered_coords_text': (255, 255, 255), # 滤波坐标文字颜色 - 白色
            'status_text': (255, 255, 255),    # 状态信息文字颜色 - 白色
            'can_on_text': (0, 255, 0),        # CAN开启状态颜色 - 绿色
            'can_off_text': (0, 0, 255),       # CAN关闭状态颜色 - 红色
            'gui_version_text': (255, 255, 0)  # GUI版本文字颜色 - 黄色
        }
        
        # 运行控制
        self.running = True
        
        # 初始化坐标变换参数
        self.transform_params = {
            'Tx': -1400.0,  # X轴平移 (mm)
            'Ty': -560.0,   # Y轴平移 (mm) 
            'Tz': 1200.0,   # Z轴平移 (mm)
            'Ry': 21.0,     # 俯仰角 (度)
            'Rz': -30.0     # 偏航角 (度)
        }
        
        # 初始化计算模块
        self.update_calculation_module()
        
        # CAN通信相关
        self.enable_can = False
        self.can_comm = None
        self.shared_data = {
            'durian': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'timestamp': 0},
            'person': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'timestamp': 0}
        }
        self.data_lock = threading.Lock()
        
        # 显示选项
        self.show_filtered_coords = False
        
        # CV显示模式控制
        self.display_mode = 'medium'  # 'fullscreen' 或 'medium'
        self.rgb_window_name = "RGB Detection"
        
        # GUI相关
        self.gui = None
        self.gui_thread = None
        
    def update_calculation_module(self):
        """根据当前参数更新计算模块"""
        calibration = KinematicCalibration(
            Tx=self.transform_params['Tx'],
            Ty=self.transform_params['Ty'], 
            Tz=self.transform_params['Tz'],
            Ry=self.transform_params['Ry'],
            Rz=self.transform_params['Rz']
        )
        self.calc_module = FilteredCalculateModule(self.labelMap, calibration, filter_window_size=20)
        print(f"更新坐标变换参数: Tx={self.transform_params['Tx']}, Ty={self.transform_params['Ty']}, Tz={self.transform_params['Tz']}, Ry={self.transform_params['Ry']}, Rz={self.transform_params['Rz']}")
        
    def on_gui_param_update(self, new_params):
        """GUI参数更新回调"""
        self.transform_params = new_params
        self.update_calculation_module()
        
    def create_parameter_gui(self):
        """创建参数调整GUI"""
        from single_oak_with_tuning_v2 import ParameterControlGUI
        self.gui = ParameterControlGUI(self.transform_params, self.on_gui_param_update)
        
    def start_gui_thread(self):
        """在独立线程中启动GUI"""
        def gui_worker():
            self.create_parameter_gui()
            self.gui.start()
        
        self.gui_thread = threading.Thread(target=gui_worker, daemon=True)
        self.gui_thread.start()
        
        # 等待GUI初始化
        time.sleep(1)
        
    def ask_can_enable(self):
        """询问是否启用CAN通信"""
        while True:
            choice = input("是否启用CAN通信? (y/n): ").lower().strip()
            if choice in ['y', 'yes', '是']:
                self.enable_can = True
                print("CAN通信已启用")
                break
            elif choice in ['n', 'no', '否']:
                self.enable_can = False
                print("CAN通信已禁用")
                break
            else:
                print("请输入 y/n")
                
    def ask_show_filtered_coords(self):
        """询问是否显示滤波后的坐标"""
        while True:
            choice = input("是否在窗口左上角显示滤波后的最近目标坐标? (y/n): ").lower().strip()
            if choice in ['y', 'yes', '是']:
                self.show_filtered_coords = True
                print("已启用滤波坐标显示")
                break
            elif choice in ['n', 'no', '否']:
                self.show_filtered_coords = False
                print("已禁用滤波坐标显示")
                break
            else:
                print("请输入 y/n")
                
    def initialize_can(self):
        """初始化CAN通信"""
        if self.enable_can:
            try:
                self.can_comm = CANCommunicator(
                    self.shared_data,
                    self.data_lock,
                    auto_configure=True
                )
                print("CAN通信模块初始化成功")
                return True
            except Exception as e:
                print(f"CAN通信初始化失败: {e}")
                self.enable_can = False
                return False
        return True
        
    def create_pipeline(self):
        """创建检测pipeline"""
        pipeline = dai.Pipeline()
        
        # 定义节点
        camRgb = pipeline.create(dai.node.ColorCamera)
        spatialDetectionNetwork = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
        monoLeft = pipeline.create(dai.node.MonoCamera)
        monoRight = pipeline.create(dai.node.MonoCamera)
        stereo = pipeline.create(dai.node.StereoDepth)
        nnNetworkOut = pipeline.create(dai.node.XLinkOut)
        
        xoutRgb = pipeline.create(dai.node.XLinkOut)
        xoutNN = pipeline.create(dai.node.XLinkOut)
        xoutDepth = pipeline.create(dai.node.XLinkOut)
        
        xoutRgb.setStreamName("rgb")
        xoutNN.setStreamName("detections")
        xoutDepth.setStreamName("depth")
        nnNetworkOut.setStreamName("nnNetwork")
        
        # 相机属性设置
        camRgb.setPreviewSize(512, 288)
        camRgb.setVideoSize(1920, 1080)
        camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        
        monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoLeft.setCamera("left")
        monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoRight.setCamera("right")
        
        # 深度相机设置
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_ACCURACY)
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
        stereo.setOutputSize(monoLeft.getResolutionWidth(), monoLeft.getResolutionHeight())
        stereo.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7)
        stereo.setSubpixel(True)
        stereo.setLeftRightCheck(True)
        stereo.setExtendedDisparity(False)
        
        
        # 检测网络设置
        if Path(self.nnPath).exists():
            spatialDetectionNetwork.setBlobPath(self.nnPath)
        spatialDetectionNetwork.setConfidenceThreshold(0.5)
        spatialDetectionNetwork.input.setBlocking(False)
        spatialDetectionNetwork.setBoundingBoxScaleFactor(0.5)
        spatialDetectionNetwork.setDepthLowerThreshold(400)
        spatialDetectionNetwork.setDepthUpperThreshold(4500)
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
            color = (255, 255, 255)
            
            print("检测开始运行...")
            print("使用GUI窗口调整坐标变换参数")
            print("按键说明:")
            print("  'q' - 退出程序")
            print("  'f' - 切换全屏模式")
            print("  'm' - 切换中屏模式")
            print("  'ESC' - 退出全屏模式")
            
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
                
                # 计算FPS
                counter += 1
                current_time = time.monotonic()
                if (current_time - startTime) > 1:
                    fps = counter / (current_time - startTime)
                    counter = 0
                    startTime = current_time
                
                # 处理检测结果
                height = frame.shape[0]
                width = frame.shape[1]
                
                # 使用计算模块处理检测结果
                final_coords = self.calc_module.process_and_get_final_coords(detections)
                
                # 更新共享数据（用于CAN通信）
                if self.enable_can and final_coords:
                    with self.data_lock:
                        current_time = time.time()
                        if 'durian' in final_coords:
                            coords = final_coords['durian']
                            self.shared_data['durian'].update({
                                'x': coords[0],
                                'y': coords[1],
                                'z': coords[2],
                                'timestamp': current_time
                            })
                        if 'person' in final_coords:
                            coords = final_coords['person']
                            self.shared_data['person'].update({
                                'x': coords[0],
                                'y': coords[1],
                                'z': coords[2],
                                'timestamp': current_time
                            })
                
                # 计算每个检测目标的变换坐标
                detection_transformed_coords = {}
                if detections:
                    for i, detection in enumerate(detections):
                        raw_coords = [
                            detection.spatialCoordinates.x,
                            detection.spatialCoordinates.y, 
                            detection.spatialCoordinates.z
                        ]
                        
                        try:
                            transformed_point = self.calc_module.coordinate_transformer.transform_point(raw_coords)
                            detection_transformed_coords[i] = transformed_point
                        except Exception as e:
                            print(f"坐标变换错误: {e}")
                            detection_transformed_coords[i] = raw_coords
                
                # 绘制检测结果
                for i, detection in enumerate(detections):
                    # 深度图上的ROI
                    roiData = detection.boundingBoxMapping
                    roi = roiData.roi
                    roi = roi.denormalize(depthFrameColor.shape[1], depthFrameColor.shape[0])
                    topLeft = roi.topLeft()
                    bottomRight = roi.bottomRight()
                    xmin = int(topLeft.x)
                    ymin = int(topLeft.y)
                    xmax = int(bottomRight.x)
                    ymax = int(bottomRight.y)
                    cv2.rectangle(depthFrameColor, (xmin, ymin), (xmax, ymax), self.colors['depth_roi'], 1)
                    
                    # RGB图上的检测框
                    x1 = int(detection.xmin * width)
                    x2 = int(detection.xmax * width)
                    y1 = int(detection.ymin * height)
                    y2 = int(detection.ymax * height)
                    
                    try:
                        label = self.labelMap[detection.label]
                    except:
                        label = str(detection.label)
                    
                    # 显示标签和置信度
                    cv2.putText(frame, str(label), (x1 + 10, y1 + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, self.colors['label_text'], 1)
                    cv2.putText(frame, "{:.2f}%".format(detection.confidence*100), (x1 + 10, y1 + 35), cv2.FONT_HERSHEY_TRIPLEX, 0.4, self.colors['confidence_text'], 1)
                    
                    # 显示变换后的坐标
                    if i in detection_transformed_coords:
                        coords = detection_transformed_coords[i]
                        cv2.putText(frame, f"X: {coords[0]:.1f} mm", (x1 + 10, y1 + 50), cv2.FONT_HERSHEY_TRIPLEX, 0.4, self.colors['coordinates_text'], 1)
                        cv2.putText(frame, f"Y: {coords[1]:.1f} mm", (x1 + 10, y1 + 65), cv2.FONT_HERSHEY_TRIPLEX, 0.4, self.colors['coordinates_text'], 1)
                        cv2.putText(frame, f"Z: {coords[2]:.1f} mm", (x1 + 10, y1 + 80), cv2.FONT_HERSHEY_TRIPLEX, 0.4, self.colors['coordinates_text'], 1)
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), self.colors['detection_box'], 2)
                
                # 显示最近目标信息
                if self.show_filtered_coords and final_coords:
                    y_offset = 30
                    for target_type, coords in final_coords.items():
                        if coords is not None:
                            cv2.putText(frame, f"Nearest {target_type}:", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['filtered_coords_text'], 2)
                            y_offset += 25
                            cv2.putText(frame, f"X: {coords[0]:.1f} mm", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['filtered_coords_text'], 1)
                            y_offset += 20
                            cv2.putText(frame, f"Y: {coords[1]:.1f} mm", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['filtered_coords_text'], 1)
                            y_offset += 20
                            cv2.putText(frame, f"Z: {coords[2]:.1f} mm", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['filtered_coords_text'], 1)
                            y_offset += 35
                
                # 显示状态信息
                cv2.putText(frame, f"FPS: {fps:.2f}", (width - 150, 30), cv2.FONT_HERSHEY_TRIPLEX, 0.6, self.colors['status_text'], 1)
                if self.enable_can:
                    cv2.putText(frame, "CAN: ON", (width - 150, 60), cv2.FONT_HERSHEY_TRIPLEX, 0.5, self.colors['can_on_text'], 1)
                else:
                    cv2.putText(frame, "CAN: OFF", (width - 150, 60), cv2.FONT_HERSHEY_TRIPLEX, 0.5, self.colors['can_off_text'], 1)
                
                # 显示GUI版本
                cv2.putText(frame, "GUI: V2.0", (width - 150, 90), cv2.FONT_HERSHEY_TRIPLEX, 0.5, self.colors['gui_version_text'], 1)
                
                # 显示窗口
                cv2.imshow("Depth", depthFrameColor)
                self._display_rgb_frame(frame)
                
                # 检查退出条件和模式切换
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.stop()
                    break
                elif key == ord('f'):
                    self._switch_to_fullscreen()
                elif key == ord('m'):
                    self._switch_to_medium()
                elif key == 27:  # ESC键
                    if self.display_mode == 'fullscreen':
                        self._switch_to_medium()
                    
    def start(self):
        """启动系统"""
        print("=== 单OAK检测系统 - 2.0版本 GUI调参 ===")
        
        # 询问是否启用CAN通信
        self.ask_can_enable()
        
        # 询问是否显示滤波坐标
        self.ask_show_filtered_coords()
        
        # 初始化CAN通信
        if not self.initialize_can():
            return
            
        # 启动CAN线程（如果启用）
        if self.enable_can and self.can_comm:
            can_thread = threading.Thread(target=lambda: self.can_comm.start_thread())
            can_thread.daemon = True
            can_thread.start()
            print("CAN通信线程已启动")
        
        # 启动GUI线程
        self.start_gui_thread()
        print("GUI参数调整窗口已启动")
        
        # 启动检测线程
        try:
            self.detection_thread()
        except KeyboardInterrupt:
            print("检测到键盘中断")
            self.stop()
        except Exception as e:
            print(f"检测过程中出现错误: {e}")
            self.stop()
        finally:
            cv2.destroyAllWindows()
            
    def _display_rgb_frame(self, frame):
        """根据当前显示模式显示RGB帧"""
        if self.display_mode == 'fullscreen':
            # 全屏模式 - 使用原始分辨率
            cv2.namedWindow(self.rgb_window_name, cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(self.rgb_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            cv2.imshow(self.rgb_window_name, frame)
        else:
            # 中屏模式 - 调整到800x600
            cv2.namedWindow(self.rgb_window_name, cv2.WINDOW_AUTOSIZE)
            cv2.setWindowProperty(self.rgb_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
            resized_frame = cv2.resize(frame, (800, 600))
            cv2.imshow(self.rgb_window_name, resized_frame)
    
    def _switch_to_fullscreen(self):
        """切换到全屏模式"""
        if self.display_mode != 'fullscreen':
            self.display_mode = 'fullscreen'
            print("📺 切换到全屏模式 (按ESC或'm'键退出全屏)")
    
    def _switch_to_medium(self):
        """切换到中屏模式"""
        if self.display_mode != 'medium':
            self.display_mode = 'medium'
            print("🖥️ 切换到中屏模式 (800x600)")
    
    def stop(self):
        """停止系统"""
        print("正在停止系统...")
        self.running = False
        if self.enable_can and self.can_comm:
            self.can_comm.stop_thread()
            print("CAN通信已停止")
        print("系统已停止")


if __name__ == "__main__":
    detector = SingleOAKDetectorWithTuningV2()
    detector.start()
