"""
坐标变换模块
用于提供快速的坐标变换方法的工具类

调用get_trans_matrices方法，传入mxid和detections，返回转换后的坐标矩阵。
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
import logging
from threading import RLock


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
        
        # 初始化线程安全锁（用于保护 trans_matrices 的并发访问）
        self._lock = RLock()
        
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
            trans_matrices[mxid] = np.eye(4, dtype=np.float32)
            
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
                calibration.translation_z,
            )
            
            # 组合所有变换：先旋转（pitch -> yaw），再平移，最后应用基准变换
            # 矩阵乘法顺序：从右到左依次应用变换
            T_total = (T_trans @ R_yaw @ R_pitch @ T_oak_to_xyz).astype(
                np.float32, copy=False
            )
            trans_matrices[mxid] = T_total
        
        return trans_matrices



    def transform_coordinates(self, mxid: str, coords_homogeneous: np.ndarray) -> np.ndarray:
        """
        将齐次坐标从OAK设备坐标系变换到自定义坐标系（线程安全）
        
        Args:
            mxid: 设备ID（用于查找对应的变换矩阵）
            coords_homogeneous: 齐次坐标矩阵，形状为 (N, 4)，每行为 [x, y, z, 1]
        
        Returns:
            np.ndarray: 变换后的坐标，形状为 (N, 3)
        """
        if len(coords_homogeneous) == 0:
            return np.empty((0, 3), dtype=np.float32)
        
        # 使用读锁保护矩阵访问
        with self._lock:
            trans_matrix = self.trans_matrices[mxid]
        
        # 在锁外进行计算（避免长时间持有锁）
        trans_h = coords_homogeneous @ trans_matrix.T
        return trans_h[:, :3]
    
    def update_matrices(self, new_matrices: Dict[str, np.ndarray]) -> bool:
        """
        更新变换矩阵字典（线程安全，原子替换）
        
        此方法用于校准工具实时更新坐标变换参数。
        采用原子替换策略：在锁内一次性替换整个字典引用，
        确保读线程始终看到完整一致的矩阵状态。
        
        Args:
            new_matrices: 新的变换矩阵字典 {mxid: 4x4 matrix}
        
        Returns:
            bool: 更新成功返回True，失败返回False
        """
        try:
            with self._lock:
                # 原子替换整个字典引用
                self.trans_matrices = new_matrices
            
            logger = logging.getLogger(__name__)
            logger.info(f"变换矩阵已更新: devices={list(new_matrices.keys())}")
            return True
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"更新变换矩阵失败: {e}", exc_info=True)
            return False
