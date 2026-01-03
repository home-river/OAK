"""
坐标变换模块
用于提供快速的坐标变换方法的工具类

可选：
1. 传入DeviceDetectionDataDTO，
    - 通过get_trans_detection方法直接返回转换后的DeviceDetectionDataDTO

    
2. 传入list[DetectionDTO]和mxid，
    - 通过get_trans_batch方法直接返回转换后的list[DetectionDTO]
"""

from .trans_utils import (build_oak_to_xyz_homogeneous, 
                            build_translation_homogeneous,
                            create_rotation_x_matrix, 
                            create_rotation_y_matrix, 
                            create_rotation_z_matrix)
from oak_vision_system.core.dto.config_dto import (
    CoordinateTransformConfigDTO,DeviceRole,DeviceRoleBindingDTO)
from oak_vision_system.core.dto import DeviceDetectionDataDTO, SpatialCoordinatesDTO,DetectionDTO

from typing import Optional,Dict,List
import numpy as np


class CoordinateTransfomer:
    """
    坐标变换器
    
    用于将OAK设备坐标系下的点坐标变换到统一的XYZ世界坐标系。
    支持为每个设备（通过mxid标识）维护独立的变换矩阵，实现多设备并行坐标变换。
    
    核心功能：
    - 根据设备校准参数构建4x4齐次变换矩阵
    - 提供单点和批量点的坐标变换接口
    - 通过mxid快速查找对应设备的变换矩阵
    """
    
    def __init__(self, calibrations: Dict[DeviceRole, CoordinateTransformConfigDTO],
                 bindings: Dict[DeviceRole, DeviceRoleBindingDTO]):
        """
        初始化坐标变换器
        
        Args:
            calibrations: 设备角色到校准配置的映射字典
                         key为DeviceRole枚举，value为对应的坐标变换配置（包含yaw、pitch、平移等参数）
            bindings: 设备角色到设备绑定的映射字典
                     key为DeviceRole枚举，value为设备绑定信息（包含active_mxid等）
        
        初始化流程：
        1. 保存设备绑定信息
        2. 将校准配置从role索引转换为mxid索引（便于运行时通过设备ID快速查找）
        3. 为每个设备预计算变换矩阵（提升运行时性能）
        """
        self.bindings = bindings
        
        # 使用 mxid 作为 key，calibration 作为 value 的字典
        # 这样可以通过设备ID快速查找对应的校准配置，而不需要通过role查找
        self.calibrations: Dict[str, CoordinateTransformConfigDTO] = {}
        for role, calibration in calibrations.items():
            # 获取该 role 对应的 active_mxid（当前激活的设备ID）
            active_mxid = self.bindings[role].active_mxid
            if active_mxid is not None:
                # 建立 mxid -> calibration 的映射关系
                self.calibrations[active_mxid] = calibration
        
        # 预计算所有设备的变换矩阵（避免每次变换时重复计算）
        self.trans_matrices = self._create_trans_matrix()

    
    def _create_trans_matrix(self) -> Dict[str, np.ndarray]:
        """
        为每个设备创建4x4齐次变换矩阵
        
        变换矩阵的构成（从右到左应用）：
        1. T_oak_to_xyz: OAK设备坐标系到标准XYZ坐标系的基准变换
        2. R_pitch: 绕Y轴的俯仰角旋转矩阵
        3. R_yaw: 绕Z轴的偏航角旋转矩阵
        4. T_trans: 平移变换矩阵（x, y, z方向的偏移）
        
        最终变换顺序：T_trans @ R_yaw @ R_pitch @ T_oak_to_xyz
        
        Returns:
            Dict[str, np.ndarray]: mxid到4x4变换矩阵的映射字典
                                  每个矩阵形状为(4, 4)，用于齐次坐标变换
        """
        trans_matrices: Dict[str, np.ndarray] = {}
        
        for mxid, calibration in self.calibrations.items():
            # 初始化4x4单位矩阵（齐次变换矩阵）
            trans_matrices[mxid] = np.eye(4)
            
            # 构建OAK坐标系到XYZ坐标系的基准变换矩阵
            T_oak_to_xyz = build_oak_to_xyz_homogeneous()
            
            # 构建绕Z轴的偏航角（yaw）旋转矩阵
            R_yaw = create_rotation_z_matrix(calibration.yaw)
            
            # 构建绕Y轴的俯仰角（pitch）旋转矩阵
            R_pitch = create_rotation_y_matrix(calibration.pitch)
            
            # 构建平移变换矩阵（x, y, z方向的偏移量）
            T_trans = build_translation_homogeneous(
                calibration.translation_x, 
                calibration.translation_y, 
                calibration.translation_z
            )
            
            # 组合所有变换：先旋转（pitch -> yaw），再平移，最后应用基准变换
            # 矩阵乘法顺序：从右到左依次应用变换
            T_total = T_trans @ R_yaw @ R_pitch @ T_oak_to_xyz
            trans_matrices[mxid] = T_total
        
        return trans_matrices



    def _matrix_helper(self,Detections: list[DetectionDTO]) -> np.ndarray:
        """
        用于批量转换检测结果坐标为矩阵的内部方法

        args:
            Detections: list[DetectionDTO]，需要被转换的检测数据
        return:
            np.ndarray，转换后的坐标矩阵
        """
        if len(Detections) == 0:
            return np.empty((0, 4), dtype=np.float32)

        points_h = np.asarray(
            [
                [
                    float(det.spatial_coordinates.x),
                    float(det.spatial_coordinates.y),
                    float(det.spatial_coordinates.z),
                    1.0,
                ]
                for det in Detections
            ],
            dtype=np.float32,
        )

        return points_h


    def transform_points_batch(self, mxid: str, points: np.ndarray) -> np.ndarray:
        """
        批量将多个点从OAK设备坐标系变换到自定义坐标系
        
        Args:
            mxid: 设备ID（用于查找对应的变换矩阵）
            points: 输入点集，形状为(N, 4)的numpy数组
                    N为点的数量，每行为一个点的坐标
                    - (N, 4): 齐次坐标 [x, y, z, 1]
        
        Returns:
            np.ndarray: 变换后的点集，形状与输入相同
        """
        trans_h = points @ self.trans_matrices[mxid].T

        return trans_h[:,:3]




    def get_trans_matrices(self,mxid: str, detections: list[DetectionDTO]) -> np.ndarray:
        """
        将检测数据转换为齐次坐标矩阵返回
        
        args:
            mxid: str，设备ID，用于区分设备
            detections: list[DetectionDTO]，需要被转换的检测数据
        return:
            np.ndarray，转换后的坐标矩阵
        """
        points_h = self._matrix_helper(detections)
        trans_points = self.transform_points_batch(mxid, points_h)
        return trans_points












    # ------------暂弃接口-------
    
    def assemble_detection(self,detection_data:DeviceDetectionDataDTO,matrics:np.ndarray) -> DeviceDetectionDataDTO:
        """
        将坐标变换后的坐标矩阵重新封装成DeviceDetectionDataDTO

        args:
            detection_data: DeviceDetectionDataDTO，需要被转换的检测数据
            matrics: np.ndarray，转换后的坐标矩阵
        """
        new_detections:list[DetectionDTO] = []
        # 对nparray迭代时，按行返回
        for detection, row in zip(detection_data.detections,matrics):
            new_Coord = SpatialCoordinatesDTO(row[0],row[1],row[2])
            label, conf, bbox = detection.label, detection.confidence, detection.bbox
            new_detection = DetectionDTO(label=label,confidence=conf,bbox=bbox,spatial_coordinates=new_Coord)
            new_detections.append(new_detection)

        

        return detection_data.with_updates(detections=new_detections)

    def assemble_detection_batch(self,detection_data:DeviceDetectionDataDTO,matrics:np.ndarray) -> list[DetectionDTO]:
        """
        将坐标变换后的坐标矩阵重新封装成DetectionDTO列表

        args:
            detection_data: DeviceDetectionDataDTO，需要被转换的检测数据
            matrics: np.ndarray，转换后的坐标矩阵
        """
        new_detections:list[DetectionDTO] = []
        for detection, row in zip(detection_data.detections,matrics):
            new_Coord = SpatialCoordinatesDTO(row[0],row[1],row[2])
            label, conf, bbox = detection.label, detection.confidence, detection.bbox
            new_detection = DetectionDTO(label=label,confidence=conf,bbox=bbox,spatial_coordinates=new_Coord)
            new_detections.append(new_detection)

        return new_detections

    
    def get_trans_batch(self,mxid: str, detections: list[DetectionDTO]) -> list[DetectionDTO]:
        """
        批量将多个点从OAK设备坐标系变换到自定义坐标系

        args:
            mxid: str，设备ID
            detections: list[DetectionDTO]，需要被转换的检测数据
        return:
            list[DetectionDTO]，转换后的检测数据
        """
        #将检测数据转换为齐次坐标矩阵
        points_h = self._matrix_helper(detections)
        #将齐次坐标矩阵变换到自定义坐标系
        trans_points = self.transform_points_batch(mxid, points_h)
        #将齐次坐标矩阵转换为检测数据
        new_detections = self.assemble_detection_batch(detections, trans_points)
        #返回转换后的检测数据
        return new_detections

    
    def get_trans_detection(self,Detectiondata:DeviceDetectionDataDTO) -> DeviceDetectionDataDTO:
        """
        将完整的检测结果进行坐标变换后重新封装

        args:
            Detectiondata: DeviceDetectionDataDTO，需要被转换的检测数据
        return:
            DeviceDetectionDataDTO，转换后的检测数据
        """
        #将检测数据转换为齐次坐标矩阵
        points_h = self._matrix_helper(Detectiondata.detections)
        #将齐次坐标矩阵变换到自定义坐标系
        trans_points = self.transform_points_batch(Detectiondata.device_id, points_h)
        #将齐次坐标矩阵转换为检测数据
        new_detection = self.assemble_detection(Detectiondata, trans_points)
        #返回转换后的检测数据
        return new_detection
