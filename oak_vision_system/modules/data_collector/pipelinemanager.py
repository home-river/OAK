from typing import Optional, Self
import depthai as dai

from oak_vision_system.core.dto import (
    VideoFrameDTO,
    DeviceDetectionDataDTO,
    DetectionDTO,
)
from oak_vision_system.core.dto.config_dto import OAKConfigDTO
from oak_vision_system.core.dto.config_dto.system_config_dto import SystemConfigDTO
import logging
from oak_vision_system.utils.logging_utils import configure_logging


"""
    管理pipeline的类
    作用：管理pipeline的创建和配置
"""
class PipelineManager:
    def __init__(self, config: OAKConfigDTO,
                 enable_depth_output:Optional[bool]=True,
                 system_config: Optional[SystemConfigDTO] = None):
        self.config = config
        self.rgb_resolution = self._convert_rgb_resolution()
        self.filterkernel = self._convert_filterkernel()
        self.monocamera_resolution = self._convert_depth_resolution()
        self.logger = logging.getLogger(__name__)
        self.pipeline = None
        self.enable_depth_output = enable_depth_output
        self.system_config = system_config or SystemConfigDTO()
        self.__post_init__()
        self.logger.info("PipelineManager 初始化完成")

    def __post_init__(self):
        # 创建pipeline
        if self.enable_depth_output:
            self.create_pipeline()
        else:
            self.create_pipeline_with_no_depth_output()


    def create_pipeline(self):
        """创建pipeline"""
        self.logger.info("create_pipeline: start")
        stage = "init"
        try:
            stage = "pipeline_init"
            pipeline = dai.Pipeline()
            
            # 创建节点
            stage = "node_creation"
            camRgb = pipeline.create(dai.node.ColorCamera)
            spatialDetectionNetwork = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
            monoLeft = pipeline.create(dai.node.MonoCamera)
            monoRight = pipeline.create(dai.node.MonoCamera)
            stereo = pipeline.create(dai.node.StereoDepth)
            
            # 输出队列
            stage = "xlink_creation"
            xoutRgb = pipeline.create(dai.node.XLinkOut)
            xoutNN = pipeline.create(dai.node.XLinkOut)
            xoutDepth = pipeline.create(dai.node.XLinkOut)
            # nnNetworkOut = pipeline.create(dai.node.XLinkOut)
            
            xoutRgb.setStreamName("rgb")
            xoutNN.setStreamName("detections")
            xoutDepth.setStreamName("depth")
            # nnNetworkOut.setStreamName("nnNetwork")
            
            # 配置相机
            stage = "camera_config"
            camRgb.setPreviewSize(self.config.preview_resolution[0], self.config.preview_resolution[1])
            camRgb.setResolution(self.rgb_resolution)
            camRgb.setInterleaved(False)
            camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
            monoLeft.setResolution(self.monocamera_resolution)
            monoLeft.setCamera("left")
            monoRight.setResolution(self.monocamera_resolution)
            monoRight.setCamera("right")
            
            # 配置立体深度
            stage = "stereo_config"
            stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
            stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
            stereo.setOutputSize(monoLeft.getResolutionWidth(), monoLeft.getResolutionHeight())
            stereo.initialConfig.setMedianFilter(self.filterkernel)
            stereo.setSubpixel(self.config.subpixel)
            stereo.setLeftRightCheck(self.config.left_right_check)
            stereo.setExtendedDisparity(self.config.extended_disparity)
            
            # 配置检测网络
            stage = "nn_config"
            spatialDetectionNetwork.setBlobPath(self.config.model_path)
            spatialDetectionNetwork.setConfidenceThreshold(self.config.confidence_threshold)
            spatialDetectionNetwork.input.setBlocking(False)
            spatialDetectionNetwork.setBoundingBoxScaleFactor(0.5)
            spatialDetectionNetwork.setDepthLowerThreshold(self.config.depth_min_threshold)
            spatialDetectionNetwork.setDepthUpperThreshold(self.config.depth_max_threshold)
            spatialDetectionNetwork.setNumClasses(self.config.num_classes)
            spatialDetectionNetwork.setCoordinateSize(4)
            spatialDetectionNetwork.setIouThreshold(0.5)
            
            # 连接节点
            stage = "link_nodes"
            monoLeft.out.link(stereo.left)
            monoRight.out.link(stereo.right)
            camRgb.preview.link(spatialDetectionNetwork.input)
            spatialDetectionNetwork.passthrough.link(xoutRgb.input)
            # camRgb.preview.link(xoutRgb.input)
            spatialDetectionNetwork.out.link(xoutNN.input)
            stereo.depth.link(spatialDetectionNetwork.inputDepth)
            spatialDetectionNetwork.passthroughDepth.link(xoutDepth.input)
            # spatialDetectionNetwork.outNetwork.link(nnNetworkOut.input)
            self.logger.info("pipeline创建完成")
            self.pipeline = pipeline
        except Exception as e:
            self.pipeline = None
            self.logger.exception("create_pipeline 失败，阶段=%s", stage)
            raise RuntimeError(f"create_pipeline 失败（阶段={stage}）") from e

        

    def create_pipeline_with_no_depth_output(self):
        """创建无深度图的pipeline"""
        self.logger.info("create_pipeline_with_no_depth_output: start")
        stage = "init"
        try:
            stage = "pipeline_init"
            pipeline = dai.Pipeline()
                
            # 创建节点
            stage = "node_creation"
            camRgb = pipeline.create(dai.node.ColorCamera)
            spatialDetectionNetwork = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
            monoLeft = pipeline.create(dai.node.MonoCamera)
            monoRight = pipeline.create(dai.node.MonoCamera)
            stereo = pipeline.create(dai.node.StereoDepth)
            
            # 输出队列
            stage = "xlink_creation"
            xoutRgb = pipeline.create(dai.node.XLinkOut)
            xoutNN = pipeline.create(dai.node.XLinkOut)
            # nnNetworkOut = pipeline.create(dai.node.XLinkOut)
            
            xoutRgb.setStreamName("rgb")
            xoutNN.setStreamName("detections")
            # nnNetworkOut.setStreamName("nnNetwork")
            
            # 配置相机
            stage = "camera_config"
            camRgb.setPreviewSize(self.config.preview_resolution[0], self.config.preview_resolution[1])
            camRgb.setResolution(self.rgb_resolution)
            camRgb.setInterleaved(False)
            camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
            monoLeft.setResolution(self.monocamera_resolution)
            monoLeft.setCamera("left")
            monoRight.setResolution(self.monocamera_resolution)
            monoRight.setCamera("right")
            
            # 配置立体深度
            stage = "stereo_config"
            stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
            stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
            stereo.setOutputSize(monoLeft.getResolutionWidth(), monoLeft.getResolutionHeight())
            stereo.initialConfig.setMedianFilter(self.filterkernel)
            stereo.setSubpixel(self.config.subpixel)
            stereo.setLeftRightCheck(self.config.left_right_check)
            stereo.setExtendedDisparity(self.config.extended_disparity)
            
            # 配置检测网络
            stage = "nn_config"
            spatialDetectionNetwork.setBlobPath(self.config.model_path)
            spatialDetectionNetwork.setConfidenceThreshold(self.config.confidence_threshold)
            spatialDetectionNetwork.input.setBlocking(False)
            spatialDetectionNetwork.setBoundingBoxScaleFactor(0.5)
            spatialDetectionNetwork.setDepthLowerThreshold(self.config.depth_min_threshold)
            spatialDetectionNetwork.setDepthUpperThreshold(self.config.depth_max_threshold)
            spatialDetectionNetwork.setNumClasses(self.config.num_classes)
            spatialDetectionNetwork.setCoordinateSize(4)
            spatialDetectionNetwork.setIouThreshold(0.5)
            
            # 连接节点
            stage = "link_nodes"
            monoLeft.out.link(stereo.left)
            monoRight.out.link(stereo.right)
            camRgb.preview.link(spatialDetectionNetwork.input)
            spatialDetectionNetwork.passthrough.link(xoutRgb.input)
            # camRgb.preview.link(xoutRgb.input)
            spatialDetectionNetwork.out.link(xoutNN.input)
            stereo.depth.link(spatialDetectionNetwork.inputDepth)
            # spatialDetectionNetwork.outNetwork.link(nnNetworkOut.input)
            self.logger.info("pipeline创建完成（无深度输出）")
            self.pipeline = pipeline
        except Exception as e:
            self.pipeline = None
            self.logger.exception("create_pipeline_with_no_depth_output 失败，阶段=%s", stage)
            raise RuntimeError(f"create_pipeline_with_no_depth_output 失败（阶段={stage}）") from e
        
    def get_pipeline(self):
        """
        获取已创建的 pipeline 实例。

        如果 pipeline 尚未初始化，则抛出异常。
        此方法用于外部获取当前 PipelineManager 管理的 pipeline 对象。

        Returns:
            depthai.Pipeline: 已初始化的 pipeline 实例。

        Raises:
            RuntimeError: 如果 pipeline 尚未创建。
            TypeError: 如果 pipeline 类型异常。
        """
        if self.pipeline is None:
            msg = "Pipeline 尚未创建。请先调用 create_pipeline() 或 create_pipeline_with_no_depth_output()。"
            self.logger.error(msg)
            raise RuntimeError(msg)
        if not isinstance(self.pipeline, dai.Pipeline):
            msg = "Pipeline 类型异常：期望为 depthai.Pipeline。"
            self.logger.error(msg)
            raise TypeError(msg)
        return self.pipeline
          
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        # =============== 辅助函数 ===============================================
    def _convert_rgb_resolution(self) -> dai.ColorCameraProperties.SensorResolution:
        """
        转换 RGB 分辨率为 DepthAI 枚举
        
        Returns:
            dai.ColorCameraProperties.SensorResolution 枚举值
        """
        # 分辨率映射表
        resolution_map = {
            (1280, 720): dai.ColorCameraProperties.SensorResolution.THE_720_P,
            (1280, 800): dai.ColorCameraProperties.SensorResolution.THE_800_P,
            (1920, 1080): dai.ColorCameraProperties.SensorResolution.THE_1080_P,
            (1920, 1200): dai.ColorCameraProperties.SensorResolution.THE_1200_P,
            (1440, 1080): dai.ColorCameraProperties.SensorResolution.THE_1440X1080,
            (1352, 1012): dai.ColorCameraProperties.SensorResolution.THE_1352X1012,
            (2024, 1520): dai.ColorCameraProperties.SensorResolution.THE_2024X1520,
            (3840, 2160): dai.ColorCameraProperties.SensorResolution.THE_4_K,
            (4056, 3040): dai.ColorCameraProperties.SensorResolution.THE_12_MP,
            (4000, 3000): dai.ColorCameraProperties.SensorResolution.THE_4000X3000,
            (4208, 3120): dai.ColorCameraProperties.SensorResolution.THE_13_MP,
            (2592, 1944): dai.ColorCameraProperties.SensorResolution.THE_5_MP,
            (5312, 6000): dai.ColorCameraProperties.SensorResolution.THE_5312X6000,
            (8000, 6000): dai.ColorCameraProperties.SensorResolution.THE_48_MP,
        }
        
        result = resolution_map.get(self.config.rgb_resolution)
        if result is None:
            # 使用默认值并记录警告
            self.logger.warning(
                "不支持的 RGB 分辨率 %s，使用默认 1080P", self.config.rgb_resolution
            )
            return dai.ColorCameraProperties.SensorResolution.THE_1080_P
        
        return result
    
    
    
    def _convert_filterkernel(self) -> dai.MedianFilter:
        """
        转换中值滤波核大小为 DepthAI 枚举值
        
        将配置中的中值滤波核大小（整数）转换为 DepthAI 库对应的 MedianFilter 枚举值。
        中值滤波用于减少深度图中的噪声，提高深度估计的准确性。
        
        Returns:
            dai.MedianFilter: 对应的 DepthAI 中值滤波器枚举值
            
        Note:
            支持的中值滤波核大小映射：
            - 3: 3x3 核（较小滤波效果）
            - 5: 5x5 核（中等滤波效果，默认值）
            - 7: 7x7 核（较大滤波效果）
            - 0: 关闭中值滤波
            
            如果配置了不支持的值，将使用 5x5 核作为默认值并记录警告日志。
        """
        map = {
            3: dai.MedianFilter.KERNEL_3x3,
            5: dai.MedianFilter.KERNEL_5x5,
            7: dai.MedianFilter.KERNEL_7x7,
            0: dai.MedianFilter.MEDIAN_OFF,
        }
        result = map.get(self.config.median_filter)
        if result is None:
            # 使用默认值并记录警告
            self.logger.warning(
                "不支持的中值滤波核大小 %s，使用默认 5x5", self.config.median_filter
            )
            return dai.MedianFilter.KERNEL_5x5
        
        return result

    def _convert_depth_resolution(self) -> dai.MonoCameraProperties.SensorResolution:
        """
        转换深度分辨率
        """
        map ={
            (640, 400): dai.MonoCameraProperties.SensorResolution.THE_400_P,
            (1280, 720): dai.MonoCameraProperties.SensorResolution.THE_720_P,
            (1280, 800): dai.MonoCameraProperties.SensorResolution.THE_800_P,
            (640,480): dai.MonoCameraProperties.SensorResolution.THE_480_P,
            (1920,1200): dai.MonoCameraProperties.SensorResolution.THE_1200_P,
        }

        result = map.get(self.config.depth_resolution)
        if result is None:
            # 使用默认值并记录警告
            self.logger.warning(
                "不支持的深度分辨率 %s，使用默认 400P", self.config.depth_resolution
            )
            return dai.MonoCameraProperties.SensorResolution.THE_400_P
        
        return result

