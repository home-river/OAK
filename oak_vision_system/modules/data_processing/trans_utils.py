import numpy as np
from oak_vision_system.core.dto.config_dto import CoordinateTransformConfigDTO


def build_oak_to_xyz_homogeneous(*, right_multiply: bool = True) -> np.ndarray:
    """
    返回左乘体系下 4*4 的oak手性坐标系到标准右手坐标系的齐次变换矩阵 T，使得
        OAK 原坐标系：z 前, x 右, y 上
        目标坐标系  ：x 前, z 上, y 左

    # 实现中旋转矩阵的4*4形式如下：
    # [[ 0, -1,  0,  0],
    #  [ 0,  0,  1,  0],
    #  [ 1,  0,  0,  0],
    #  [ 0,  0,  0,  1]]
    """

    R = np.array(
        [
            [0, -1, 0],
            [0, 0, 1],
            [1, 0, 0],
        ],
        dtype=np.float32,
    )
    
    T = np.eye(4, dtype=np.float32)
    T[:3, :3] = R
    
    return T if right_multiply else T.T
    

def build_translation_homogeneous(
    tx: float, ty: float, tz: float, *, right_multiply: bool = True
) -> np.ndarray:
    """
    构造左乘体系下仅包含平移的 4x4 齐次变换矩阵,语义为坐标系的位移量。
    相当于把标准的平移矩阵的平移向量取反。
    """
    T = np.eye(4, dtype=np.float32)
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
    c = np.float32(np.cos(angle_rad))
    s = np.float32(np.sin(angle_rad))
    return np.array(
        [
            [c, -s, 0, 0],
            [s, c, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float32,
    )


def create_rotation_x_matrix(angle_degrees: float) -> np.ndarray:
    """
    创建一个绕X轴旋转的4x4齐次旋转矩阵。
    
    Args:
        angle_degrees: 旋转角度 (角度制)。
        
    Returns:
        一个(4, 4)的NumPy数组。
    """
    angle_rad = np.deg2rad(angle_degrees)  # 转换为弧度
    c = np.float32(np.cos(angle_rad))
    s = np.float32(np.sin(angle_rad))
    return np.array(
        [
            [1, 0, 0, 0],
            [0, c, -s, 0],
            [0, s, c, 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float32,
    )


def create_rotation_y_matrix(angle_degrees: float) -> np.ndarray:
    """
    创建一个绕Y轴旋转的4x4齐次旋转矩阵。
    
    Args:
        angle_degrees: 旋转角度 (角度制)。
        
    Returns:
        一个(4, 4)的NumPy数组。
    """
    angle_rad = np.deg2rad(angle_degrees)  # 转换为弧度
    c = np.float32(np.cos(angle_rad))
    s = np.float32(np.sin(angle_rad))
    return np.array(
        [
            [c, 0, s, 0],
            [0, 1, 0, 0],
            [-s, 0, c, 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float32,
    )