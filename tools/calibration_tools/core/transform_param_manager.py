"""
坐标变换参数管理器

职责：
- 保存初始配置参数
- 构建变换矩阵
- 管理参数更新
- 提供参数查询和重置功能
"""

from threading import RLock
from typing import Dict, Optional
from copy import deepcopy
import numpy as np
import logging

from oak_vision_system.core.dto.config_dto import (
    CoordinateTransformConfigDTO,
    DeviceRole
)
from oak_vision_system.modules.config_manager.device_config_manager import DeviceConfigManager
from oak_vision_system.modules.data_processing.data_processor import DataProcessor
from oak_vision_system.modules.data_processing.trans_utils import (
    build_oak_to_xyz_homogeneous,
    build_translation_homogeneous,
    create_rotation_y_matrix,
    create_rotation_z_matrix
)


class TransformParamManager:
    """
    坐标变换参数管理器
    
    职责：
    - 保存初始配置参数
    - 构建变换矩阵
    - 管理参数更新
    - 提供参数查询和重置功能
    """
    
    def __init__(
        self,
        config_manager,
        data_processor
    ):
        """
        初始化参数管理器
        
        Args:
            config_manager: DeviceConfigManager 实例
            data_processor: DataProcessor 实例
        """
        self.config_manager : DeviceConfigManager = config_manager
        self.data_processor : DataProcessor = data_processor
        self._lock = RLock()
        self.logger = logging.getLogger(__name__)
        
        # 保存初始配置: {mxid: CoordinateTransformConfigDTO}
        self._initial_configs: Dict[str, CoordinateTransformConfigDTO] = {}
        
        # 保存 mxid 到 role 的映射
        self._mxid_to_role: Dict[str, DeviceRole] = {}
        
        # 当前矩阵字典的副本
        self._current_matrices: Dict[str, np.ndarray] = {}
        
        # 初始化
        self._load_initial_configs()
    
    def _load_initial_configs(self) -> None:
        """从配置管理器加载初始配置"""
        try:
            # 获取角色绑定
            role_bindings = self.config_manager.get_active_role_binding_dtos()
            
            # 获取数据处理配置
            data_config = self.config_manager.get_data_processing_config()
            
            # 保存初始配置和映射关系
            for role, binding in role_bindings.items():
                mxid = binding.active_mxid
                # 只取激活的设备
                if mxid:
                    transform_config = data_config.coordinate_transforms[role]
                    self._initial_configs[mxid] = transform_config
                    self._mxid_to_role[mxid] = role
                    
                    # 构建初始矩阵
                    matrix = self._build_transform_matrix(transform_config)
                    self._current_matrices[mxid] = matrix
            
            self.logger.info(
                f"初始配置加载完成: devices={list(self._initial_configs.keys())}"
            )
        except Exception as e:
            self.logger.error(f"加载初始配置失败: {e}", exc_info=True)
            raise

    def _build_transform_matrix(
        self,
        config: CoordinateTransformConfigDTO
    ) -> np.ndarray:
        """
        根据配置构建变换矩阵
        
        使用与 CoordinateTransfomer._create_trans_matrix 相同的流程：
        T_total = T_trans @ R_yaw @ R_pitch @ T_oak_to_xyz
        
        Args:
            config: 坐标变换配置对象
        
        Returns:
            np.ndarray: 4x4 变换矩阵
        """
        # 基准变换
        T_oak_to_xyz = build_oak_to_xyz_homogeneous()
        
        # 旋转变换
        R_yaw = create_rotation_z_matrix(config.yaw)
        R_pitch = create_rotation_y_matrix(config.pitch)
        
        # 平移变换
        T_trans = build_translation_homogeneous(
            config.translation_x,
            config.translation_y,
            config.translation_z
        )
        
        # 组合变换（从右到左应用）
        T_total = (T_trans @ R_yaw @ R_pitch @ T_oak_to_xyz).astype(
            np.float32, copy=False
        )
        
        return T_total

    def update_params(
        self,
        mxid: str,
        tx: float, ty: float, tz: float,
        pitch: float, yaw: float
    ) -> bool:
        """
        更新指定设备的变换参数
        
        Args:
            mxid: 设备ID
            tx, ty, tz: 平移参数（mm）
            pitch, yaw: 旋转参数（度）
        
        Returns:
            bool: 更新成功返回True，失败返回False
        """
        try:
            with self._lock:
                # 验证设备是否存在
                if mxid not in self._mxid_to_role:
                    self.logger.error(f"设备 {mxid} 不存在于配置中")
                    return False
                
                # 1. 构建新矩阵
                # 创建临时配置对象
                role = self._mxid_to_role[mxid]
                temp_config = CoordinateTransformConfigDTO(
                    role=role,
                    translation_x=tx,
                    translation_y=ty,
                    translation_z=tz,
                    roll=0.0,
                    pitch=pitch,
                    yaw=yaw
                )
                new_matrix = self._build_transform_matrix(temp_config)
                
                # 2. 深拷贝当前矩阵字典
                new_matrices = deepcopy(self._current_matrices)
                
                # 3. 更新指定设备的矩阵
                new_matrices[mxid] = new_matrix
                
                # 4. 调用 DataProcessor 更新
                success = self.data_processor.update_transform_matrices(new_matrices)
                
                if success:
                    # 5. 更新本地副本
                    self._current_matrices = new_matrices
                    self.logger.info(
                        f"参数更新成功: mxid={mxid}, tx={tx}, ty={ty}, tz={tz}, "
                        f"pitch={pitch}, yaw={yaw}"
                    )
                else:
                    self.logger.error(f"DataProcessor 更新矩阵失败: mxid={mxid}")
                
                return success
        except Exception as e:
            self.logger.error(f"更新参数失败: {e}", exc_info=True)
            return False

    def get_params_snapshot(self, mxid: str) -> Optional[Dict[str, float]]:
        """
        获取指定设备的参数快照（从初始配置读取）
        
        Args:
            mxid: 设备ID
        
        Returns:
            参数字典或None（如果设备不存在）
        """
        with self._lock:
            if mxid not in self._initial_configs:
                self.logger.warning(f"设备 {mxid} 不存在于初始配置中")
                return None
            
            config = self._initial_configs[mxid]
            return {
                'tx': config.translation_x,
                'ty': config.translation_y,
                'tz': config.translation_z,
                'roll': config.roll,
                'pitch': config.pitch,
                'yaw': config.yaw
            }
    
    def reset_to_default(self, mxid: str) -> bool:
        """
        重置指定设备为初始参数
        
        Args:
            mxid: 设备ID
        
        Returns:
            bool: 重置成功返回True，失败返回False
        """
        try:
            if mxid not in self._initial_configs:
                self.logger.error(f"未找到设备 {mxid} 的初始配置")
                return False
            
            config = self._initial_configs[mxid]
            
            success = self.update_params(
                mxid,
                config.translation_x,
                config.translation_y,
                config.translation_z,
                config.pitch,
                config.yaw
            )
            
            if success:
                self.logger.info(f"设备 {mxid} 已重置为初始参数")
            
            return success
        except Exception as e:
            self.logger.error(f"重置参数失败: {e}", exc_info=True)
            return False
    
    def get_current_mxid(self) -> str:
        """
        获取当前设备的mxid（单设备模式）
        
        Returns:
            str: 设备mxid
        
        Raises:
            ValueError: 如果不是单设备运行模式
        """
        mxids = list(self._mxid_to_role.keys())
        if len(mxids) != 1:
            raise ValueError(f"期望单设备运行，实际发现 {len(mxids)} 个设备")
        return mxids[0]
