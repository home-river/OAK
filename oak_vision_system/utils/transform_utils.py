


from __future__ import annotations

import numpy as np

from ..core.dto.config_dto.data_processing_config_dto import CoordinateTransformConfigDTO


def build_oak_to_xyz_homogeneous(*, right_multiply: bool = True) -> np.ndarray:
    """
    返回 4*4 的oak手性坐标系到标准右手坐标系的齐次变换矩阵 T，使得
        OAK 原坐标系：z 前, x 右, y 上
        目标坐标系  ：x 前, z 上, y 左

    # 实现中旋转矩阵的4*4形式如下：
    # [[ 0, -1,  0,  0],
    #  [ 0,  0,  1,  0],
    #  [ 1,  0,  0,  0],
    #  [ 0,  0,  0,  1]]
    """

    R = np.array([
        [ 0, -1,  0],
        [0,  0,  1],
        [ 1, 0,  0]
    ])
    
    T = np.eye(4)
    T[:3, :3] = R
    
    return T if right_multiply else T.T
    

def build_translation_homogeneous(tx: float, ty: float, tz: float, *, right_multiply: bool) -> np.ndarray:
    """
    构造仅包含平移的 4x4 齐次变换矩阵,语义为坐标系的位移量。
    相当于把标准的平移矩阵的平移向量取反。
    """
    T = np.eye(4)
    if right_multiply:
        T[3, 0:3] = [-tx, -ty, -tz]
    else:
        T[0:3, 3] = [-tx, -ty, -tz]
    return T


def create_rotation_z_matrix(angle_degrees: float) -> np.ndarray:
    """
    创建一个绕Z轴旋转的4x4齐次旋转矩阵。
    
    Args:
        angle_degrees: 旋转角度 (角度制)。
        
    Returns:
        一个(4, 4)的NumPy数组。
    """
    angle_rad = np.deg2rad(angle_degrees)  # 转换为弧度
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([
        [c, -s, 0, 0],
        [s,  c, 0, 0],
        [0,  0, 1, 0],
        [0,  0, 0, 1]
    ])

def create_rotation_x_matrix(angle_degrees: float) -> np.ndarray:
    """
    创建一个绕X轴旋转的4x4齐次旋转矩阵。
    
    Args:
        angle_degrees: 旋转角度 (角度制)。
        
    Returns:
        一个(4, 4)的NumPy数组。
    """
    angle_rad = np.deg2rad(angle_degrees)  # 转换为弧度
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([
        [1, 0,  0, 0],
        [0, c, -s, 0],
        [0, s,  c, 0],
        [0, 0,  0, 1]
    ])

def create_rotation_y_matrix(angle_degrees: float) -> np.ndarray:
    """
    创建一个绕Y轴旋转的4x4齐次旋转矩阵。
    
    Args:
        angle_degrees: 旋转角度 (角度制)。
        
    Returns:
        一个(4, 4)的NumPy数组。
    """
    angle_rad = np.deg2rad(angle_degrees)  # 转换为弧度
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([
        [ c, 0, s, 0],
        [ 0, 1, 0, 0],
        [-s, 0, c, 0],
        [ 0, 0, 0, 1]
    ])

def build_transform_matrix_v1(config: CoordinateTransformConfigDTO, eps: float = 0.0, *, right_multiply: bool = True) -> np.ndarray:
    """根据坐标变换配置构建 4x4 齐次变换矩阵（v1版本）。
    
    顺序（动作语义）：先 OAK->XYZ，再俯仰(Ry)，再偏航(Rz)，最后平移(T)。

    乘法约定：
    - right_multiply=True（默认）：行向量右乘，p_new^T = p_old^T @ (R @ T)
    - right_multiply=False：列向量左乘，p_new = (T @ R) @ p_old

    Args:
        config: 坐标变换配置 DTO
        eps: 角度近零裁剪阈值（度）。默认为 0 表示不裁剪。
        right_multiply: 是否使用行向量右乘约定。

    Returns:
        np.ndarray: 形状为 (4, 4) 的齐次变换矩阵
    """
    roll = config.roll
    pitch = config.pitch
    yaw = config.yaw

    if eps > 0.0:
        if abs(roll) < eps:
            roll = 0.0
        if abs(pitch) < eps:
            pitch = 0.0
        if abs(yaw) < eps:
            yaw = 0.0

    roll_rad = np.radians(roll) # 暂时不需要翻滚，所以不使用
    pitch_rad = np.radians(pitch)
    yaw_rad = np.radians(yaw)

    # 按公式（右乘行向量）：p_old^T Ry(+pitch) Rz(+yaw) T(-Δt)
    Rz = np.array([
        [np.cos(yaw_rad), -np.sin(yaw_rad), 0],
        [np.sin(yaw_rad),  np.cos(yaw_rad), 0],
        [0, 0, 1]
    ])

    Ry = np.array([
        [ np.cos(pitch_rad), 0, np.sin(pitch_rad)],
        [ 0, 1, 0],
        [-np.sin(pitch_rad), 0, np.cos(pitch_rad)]
    ])

    T_o = build_oak_to_xyz_homogeneous(right_multiply=right_multiply)

    if right_multiply:
        R = T_o @ Ry @ Rz
    else:
        R = Rz @ Ry @ T_o

    # 旋转（4x4）
    T_rot = np.eye(4)
    T_rot[0:3, 0:3] = R

    # 平移（取 -Δt）
    dx = -config.translation_x
    dy = -config.translation_y
    dz = -config.translation_z
    T_trans = build_translation_homogeneous(dx, dy, dz, right_multiply=right_multiply)

    # 合成
    if right_multiply:
        T_total = T_rot @ T_trans
    else:
        T_total = T_trans @ T_rot

    return T_total


def build_transform_matrix_v1_left(config: CoordinateTransformConfigDTO, eps: float = 0.0) -> np.ndarray:
    """左乘（列向量）版本的便捷封装。

    等价于：build_transform_matrix_v1(config, eps, right_multiply=False)
    """
    return build_transform_matrix_v1(config, eps, right_multiply=False)


def build_transform_matrix_v1_right(config: CoordinateTransformConfigDTO, eps: float = 0.0) -> np.ndarray:
    """右乘（行向量）版本的便捷封装（默认行为）。

    等价于：build_transform_matrix_v1(config, eps, right_multiply=True)
    """
    return build_transform_matrix_v1(config, eps, right_multiply=True)


