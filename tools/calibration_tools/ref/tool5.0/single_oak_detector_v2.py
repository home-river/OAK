from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
import time
import threading
import tkinter as tk
from tkinter import ttk
import datetime
import json

# 添加缺失的导入
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
        
        # 运行控制
        self.running = True
        
        # 初始化坐标变换参数
        self.transform_params = {
            'Tx': -1350.0,  # X轴平移 (mm)
            'Ty': -760.0,   # Y轴平移 (mm) 
            'Tz': 1200.0,   # Z轴平移 (mm)
            'Ry': 21,     # 俯仰角 (度)
            'Rz': -30     # 偏航角 (度)
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
        
        # 误差记录相关
        self.reference_position = {'x': 0.0, 'y': 0.0}  # 基准位置
        self.error_data = []  # 误差数据记录
        self.error_folder = Path(__file__).parent / "error"  # 修正为脚本同级目录
        self.error_folder.mkdir(exist_ok=True)  # 创建error文件夹
        self.current_target_coords = None  # 当前检测到的目标坐标
        self.record_target_type = "durian"  # 记录目标类型

    def update_calculation_module(self):
        """根据当前参数更新计算模块"""
        calibration = KinematicCalibration(
            Tx=self.transform_params['Tx'],
            Ty=self.transform_params['Ty'], 
            Tz=self.transform_params['Tz'],
            Ry=self.transform_params['Ry'],
            Rz=self.transform_params['Rz']
        )
        self.calc_module = FilteredCalculateModule(self.labelMap, calibration, filter_window_size=10)
        print(f"更新坐标变换参数: Tx={self.transform_params['Tx']}, Ty={self.transform_params['Ty']}, Tz={self.transform_params['Tz']}, Ry={self.transform_params['Ry']}, Rz={self.transform_params['Rz']}")
        
    def on_gui_param_update(self, new_params):
        """GUI参数更新回调"""
        self.transform_params = new_params
        self.update_calculation_module()
        
    def on_reference_position_update(self, reference_pos):
        """基准位置更新回调"""
        self.reference_position = reference_pos
        print(f"📍 基准位置已更新: X={reference_pos['x']:.1f}mm, Y={reference_pos['y']:.1f}mm")
        
    def record_error_data(self):
        """记录当前目标位置的误差数据"""
        if self.record_target_type is None:
            print("⚠️ 未设置记录目标类型")
            return
            
        if not hasattr(self, 'current_target_coords') or self.current_target_coords is None:
            print(f"⚠️ 未检测到{self.record_target_type}，无法记录数据")
            return
            
        if self.record_target_type not in self.current_target_coords or self.current_target_coords[self.record_target_type] is None:
            print(f"⚠️ 未检测到{self.record_target_type}，无法记录数据")
            return
            
        # 获取当前目标的X,Y坐标
        real_x = self.current_target_coords[self.record_target_type][0]
        real_y = self.current_target_coords[self.record_target_type][1]
        
        # 计算误差向量
        error_x = real_x - self.reference_position['x']
        error_y = real_y - self.reference_position['y']
        
        # 创建数据记录
        data_point = {
            'timestamp': datetime.datetime.now().isoformat(),
            'target_type': self.record_target_type,
            'real_position': [real_x, real_y],
            'error_vector': [error_x, error_y],
            'reference_position': [self.reference_position['x'], self.reference_position['y']]
        }
        
        self.error_data.append(data_point)
        
        # 保存到文件
        self.save_error_data()
        
        # 更新GUI显示
        if self.gui:
            self.gui.update_record_status(len(self.error_data))
        
        print(f"📊 已记录误差数据: 实际位置({real_x:.1f}, {real_y:.1f}), 误差向量({error_x:.1f}, {error_y:.1f})")
        
    def save_error_data(self):
        """保存误差数据到JSON文件（追加模式）"""
        filename = "error_data.json"
        filepath = self.error_folder / filename
        
        # 获取最新记录的数据点
        if not self.error_data:
            return
            
        latest_data = self.error_data[-1]
        
        try:
            # 读取现有数据
            existing_data = []
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            # 追加新数据
            existing_data.append(latest_data)
            
            # 保存回文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
                
            print(f"💾 误差数据已追加到: {filepath} (总计 {len(existing_data)} 条记录)")
        except Exception as e:
            print(f"❌ 保存误差数据失败: {e}")
        
    def create_parameter_gui(self):
        """创建参数调整GUI"""
        from single_oak_with_tuning_v2 import ParameterControlGUI
        self.gui = ParameterControlGUI(
            self.transform_params, 
            self.on_gui_param_update,
            self.on_reference_position_update,  # 传递基准位置更新回调
            self.record_error_data  # 传递记录数据回调
        )

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
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
        stereo.setOutputSize(monoLeft.getResolutionWidth(), monoLeft.getResolutionHeight())
        stereo.setMedianFilter(dai.MedianFilter.KERNEL_7x7)
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
            color = (255, 255, 255)
            
            print("检测开始运行...")
            print("使用GUI窗口调整坐标变换参数")
            print("按键说明:")
            print("  'q' - 退出程序")
            print("  'f' - 切换全屏模式")
            print("  'm' - 切换中屏模式")
            print("  'ESC' - 退出全屏模式")
            print("💡 使用GUI中的'记录误差数据'按钮来记录榴莲位置")

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
                
                # 更新当前目标坐标（用于误差记录）
                self.current_target_coords = final_coords

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
                    # 使用计算模块进行坐标变换
                    transformed_results = self.calc_module.process_and_get_transformed_coords(detections)
                    
                    for i, detection in enumerate(detections):
                        raw_coords = [
                            detection.spatialCoordinates.x,
                            detection.spatialCoordinates.y,
                            detection.spatialCoordinates.z
                        ]
                        
                        label = self.labelMap[detection.label]
                        # 从变换结果中获取对应的坐标
                        if label.lower() in transformed_results:
                            transformed_coords = transformed_results[label.lower()]
                        else:
                            transformed_coords = (0.0, 0.0, 0.0)
                            
                        detection_transformed_coords[i] = {
                            'label': label,
                            'raw': raw_coords,
                            'transformed': transformed_coords
                        }
                
                # 绘制检测框和坐标信息
                for i, detection in enumerate(detections):
                    bbox = self.frameNorm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                    label = self.labelMap[detection.label]
                    confidence = detection.confidence * 100
                    
                    # 绘制检测框
                    cv2.putText(frame, f"{label} {confidence:.1f}%", (bbox[0] + 10, bbox[1] + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255))
                    cv2.putText(frame, f"X: {int(detection.spatialCoordinates.x)} mm", (bbox[0] + 10, bbox[1] + 35), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255))
                    cv2.putText(frame, f"Y: {int(detection.spatialCoordinates.y)} mm", (bbox[0] + 10, bbox[1] + 50), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255))
                    cv2.putText(frame, f"Z: {int(detection.spatialCoordinates.z)} mm", (bbox[0] + 10, bbox[1] + 65), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255))
                    
                    # 显示变换后的坐标
                    if i in detection_transformed_coords:
                        transformed = detection_transformed_coords[i]['transformed']
                        cv2.putText(frame, f"TX: {transformed[0]:.1f} mm", (bbox[0] + 10, bbox[1] + 80), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255))
                        cv2.putText(frame, f"TY: {transformed[1]:.1f} mm", (bbox[0] + 10, bbox[1] + 95), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255))
                        cv2.putText(frame, f"TZ: {transformed[2]:.1f} mm", (bbox[0] + 10, bbox[1] + 110), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255))
                    
                    cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
                
                # 显示最近目标信息
                if self.show_filtered_coords and final_coords:
                    y_offset = 30
                    for target_type, coords in final_coords.items():
                        if coords is not None:
                            cv2.putText(frame, f"Nearest {target_type}:", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                            y_offset += 25
                            cv2.putText(frame, f"X: {coords[0]:.1f} mm", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                            y_offset += 20
                            cv2.putText(frame, f"Y: {coords[1]:.1f} mm", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                            y_offset += 20
                            cv2.putText(frame, f"Z: {coords[2]:.1f} mm", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                            y_offset += 35
                
                # 显示状态信息
                cv2.putText(frame, f"FPS: {fps:.2f}", (width - 150, 30), cv2.FONT_HERSHEY_TRIPLEX, 0.6, (255, 255, 255), 1)
                if self.enable_can:
                    cv2.putText(frame, "CAN: ON", (width - 150, 60), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255), 1)
                else:
                    cv2.putText(frame, "CAN: OFF", (width - 150, 60), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255), 1)
                
                # 显示GUI版本
                cv2.putText(frame, "GUI: V2.0", (width - 150, 90), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255), 1)
                
                # 显示基准位置和误差记录信息
                cv2.putText(frame, f"Ref: ({self.reference_position['x']:.0f}, {self.reference_position['y']:.0f})", 
                           (10, height - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, f"Records: {len(self.error_data)}", 
                           (10, height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, "Use GUI button to record data", 
                           (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
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
        print("=== 单OAK检测系统 - 2.0版本 GUI调参 + 误差记录 ===")
        
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
        print("📊 误差记录功能已启用")
        print("💡 使用说明:")
        print("  1. 在GUI中设置基准位置坐标")
        print("  2. 点击GUI中的'记录误差数据'按钮记录当前目标位置")
        print("  3. 数据将保存到脚本同级的 error/ 文件夹中")
        
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

    def frameNorm(self, frame, bbox):
        """标准化边界框坐标"""
        normVals = np.full(len(bbox), frame.shape[0])
        normVals[::2] = frame.shape[1]
        return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

if __name__ == "__main__":
    detector = SingleOAKDetectorWithTuningV2()
    detector.start()
