"""
一个集成的计算模块。
它负责从原始检测数据中筛选目标、进行必要的计算（如未来的坐标变换），
并准备好最终待发送的坐标数据。

修改版本：移除了会导致内存泄漏的历史数据存储，优化了内存管理。
角度制版本：所有旋转角度参数使用度为单位。
"""
import numpy as np
from dataclasses import dataclass
from math import pi
from typing import Tuple, List, Sequence, Optional, Dict
from collections import deque
import gc


# ==============================================================================
#    矩阵构造函数 - 修改为角度制
# ==============================================================================

def create_translation_matrix(x: float, y: float, z: float) -> np.ndarray:
    """
    创建一个4x4的齐次平移矩阵。
    
    Args:
        x: 沿X轴的平移量。
        y: 沿Y轴的平移量。
        z: 沿Z轴的平移量。
        
    Returns:
        一个(4, 4)的NumPy数组。
    """
    T = np.eye(4)
    T[0, 3] = x
    T[1, 3] = y
    T[2, 3] = z
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


def build_oak_to_xyz_homogeneous() -> np.ndarray:
    """
    返回 4×4 齐次变换矩阵 T，使得
        OAK 原坐标系：z 前, x 右, y 上
        目标坐标系  ：x 前, z 上, y 左

    变换矩阵（含旋转与零平移）直接写为：
        [[ 0,  0,  1, 0],
         [-1,  0,  0, 0],
         [ 0,  1,  0, 0],
         [ 0,  0,  0, 1]]
    """
    # 取左上3×3部分作为旋转矩阵 R
    R = np.array([
        [ 0,  0,  1],
        [-1,  0,  0],
        [ 0,  1,  0]
    ])

    # 构造齐次变换矩阵
    T = np.eye(4)
    T[:3, :3] = R
    # 平移向量默认为 [0,0,0]^T

    return T


    

@dataclass
class KinematicCalibration:
    """存放相机运动学标定参数的配置类 - 角度制版本"""
    # 平移 (单位：毫米或米，根据具体应用)
    Tx: float = 0.0
    Ty: float = 0.0 
    Tz: float = 0.0
    # 偏航角 (单位：度)
    Rz: float = 0.0
    # 俯仰角 (单位：度)
    Ry: float = 0.0
    
    
    @classmethod
    def create_default(cls) -> 'KinematicCalibration':
        """创建默认参数的标定配置"""
        return cls()
    
    @classmethod  
    def create_with_translation(cls, tx: float, ty: float, tz: float) -> 'KinematicCalibration':
        """创建仅包含平移的标定配置"""
        return cls(Tx=tx, Ty=ty, Tz=tz)
    
    @classmethod
    def create_with_rotation(cls, ry: float, rz: float) -> 'KinematicCalibration':
        """
        创建仅包含旋转的标定配置
        
        Args:
            ry: 俯仰角 (度)
            rz: 偏航角 (度)
        """
        return cls(Ry=ry, Rz=rz)
    
    @classmethod
    def create_full(cls, tx: float, ty: float, tz: float, 
                   ry: float, rz: float) -> 'KinematicCalibration':
        """
        创建完整的标定配置
        
        Args:
            tx, ty, tz: 平移量
            ry: 俯仰角 (度)
            rz: 偏航角 (度)
        """
        return cls(Tx=tx, Ty=ty, Tz=tz, Ry=ry, Rz=rz)
    
    def __str__(self) -> str:
        """返回友好的字符串表示"""
        return (f"KinematicCalibration(平移: ({self.Tx:.2f}, {self.Ty:.2f}, {self.Tz:.2f}), "
                f"俯仰角: {self.Ry:.1f}°, 偏航角: {self.Rz:.1f}°)")
    

# ==============================================================================
#    坐标变换类
# ==============================================================================

class CoordinateTransformer:
    """
    负责处理基于机器人运动学的坐标系变换。
    在初始化时预计算变换矩阵，提高后续变换性能。
    角度制版本：所有角度参数使用度为单位。
    """
    
    def __init__(self, calibration: KinematicCalibration):
        """
        初始化坐标变换器
        
        Args:
            calibration: 运动学标定参数 (角度使用度)
        """
        self.calib = calibration
        
        # 预计算变换矩阵
        self._build_transform_matrices()
    
    def _build_transform_matrices(self) -> None:
        """
        构建并缓存变换矩阵
        注意：旋转角度参数现在使用角度制
        """
        # 构造各个变换矩阵 - 现在传入角度制参数
        R_pitch = create_rotation_y_matrix(self.calib.Ry)  # 俯仰角(度)
        R_yaw = create_rotation_z_matrix(self.calib.Rz)    # 偏航角(度)
        T_trans = create_translation_matrix(self.calib.Tx, self.calib.Ty, self.calib.Tz)
        R_OAK_to_camera = build_oak_to_xyz_homogeneous()
        
        # 组合变换矩阵
        self.transform_matrix = T_trans @ R_yaw @ R_pitch @ R_OAK_to_camera
        
        # 计算相机在基座坐标系中的位置
        camera_origin_h = np.array([0.0, 0.0, 0.0, 1.0])
        self.camera_position_in_base = (self.transform_matrix @ camera_origin_h)[:3]
    
    def transform_point(self, point: Sequence[float]) -> np.ndarray:
        """
        将相机坐标系下的点变换到基座坐标系
        
        Args:
            point: 相机坐标系下的三维点 [x, y, z]
            
        Returns:
            基座坐标系下的三维点 [x', y', z']
        """
        p_h = np.array([point[0], point[1], point[2], 1.0])
        p_out_h = self.transform_matrix @ p_h
        return p_out_h[:3]
    
    def transform_points_batch(self, points: np.ndarray) -> np.ndarray:
        """
        批量变换点从相机坐标系到基座坐标系
        
        Args:
            points: 形状为 (N, 3) 的点云数组
            
        Returns:
            变换后的点云数组 (N, 3)
        """
        # 转换为齐次坐标 (N, 4)
        ones = np.ones((points.shape[0], 1))
        points_h = np.hstack([points, ones])
        
        # 批量变换：(4,4) @ (4,N) -> (4,N) -> (N,4) -> (N,3)
        transformed_h = (self.transform_matrix @ points_h.T).T
        return transformed_h[:, :3]
    
    def update_calibration(self, new_calibration: KinematicCalibration) -> None:
        """
        更新标定参数并重新计算变换矩阵
        
        Args:
            new_calibration: 新的标定参数 (角度使用度)
        """
        self.calib = new_calibration
        self._build_transform_matrices()
    
    @property
    def camera_position(self) -> np.ndarray:
        """获取相机在基座坐标系中的位置"""
        return self.camera_position_in_base.copy()
    
    @property
    def transform_matrix_copy(self) -> np.ndarray:
        """获取变换矩阵的副本"""
        return self.transform_matrix.copy()
    
    def get_calibration_info(self) -> str:
        """获取当前标定参数的详细信息字符串"""
        return str(self.calib)


# 优化后的滤波器类，增强内存管理
class SingleChannelMovingAverageFilter:
    """
    单通道滑动窗口平均滤波器，内置内存管理优化。
    """
    def __init__(self, window_size: int):
        self.N = window_size
        self.buffer = deque(maxlen=window_size)  # 自动限制大小，防止内存泄漏
        self.sum = 0.0
        self._sample_count = 0  # 添加计数器用于精度校正

    def add_sample(self, sample: float) -> float:
        """
        添加一个新样本并返回滤波后的结果。
        
        参数:
            sample: 新的输入样本
            
        返回:
            滤波后的输出值
        """
        # 如果缓冲区已满，减去即将被移出的值
        if len(self.buffer) == self.N:
            self.sum -= self.buffer[0]
        
        # 添加新样本并更新和
        self.buffer.append(sample)
        self.sum += sample
        self._sample_count += 1
        
        # 定期重新计算sum以避免浮点累积误差
        if self._sample_count % (self.N * 10) == 0:
            self.sum = sum(self.buffer)  # 重新精确计算
        
        # 返回平均值
        return self.sum / len(self.buffer)

    def reset(self):
        """重置滤波器状态"""
        self.buffer.clear()
        self.sum = 0.0
        self._sample_count = 0

    def get_buffer_size(self) -> int:
        """返回当前缓冲区大小"""
        return len(self.buffer)




class FilteredCalculateModule:
    """
    封装从数据筛选到计算准备的完整流程。
     1. 使用欧氏距离。 2. 在机器人基座坐标系中进行距离比较。
    """
    def __init__(self, label_map: List[str], calib: Optional[KinematicCalibration] = None, 
                 filter_window_size: int = 20):
        # ... __init__ 方法的其他部分保持不变 ...
        try:
            self.DURIAN_LABEL_INDEX = label_map.index("durian")
            self.PERSON_LABEL_INDEX = label_map.index("person")
        except ValueError:
            print("错误： 'durian' 或 'person' 不在提供的 label_map 中！")
            raise
        if calib is None:
            calib = KinematicCalibration.create_default()
        self.coordinate_transformer = CoordinateTransformer(calib)
        self.durian_filter_x = SingleChannelMovingAverageFilter(filter_window_size)
        self.durian_filter_y = SingleChannelMovingAverageFilter(filter_window_size)
        self.durian_filter_z = SingleChannelMovingAverageFilter(filter_window_size)
        self.person_filter_x = SingleChannelMovingAverageFilter(filter_window_size)
        self.person_filter_y = SingleChannelMovingAverageFilter(filter_window_size)
        self.person_filter_z = SingleChannelMovingAverageFilter(filter_window_size)
        self.last_valid_durian = (0.0, 0.0, 0.0)
        self.last_valid_person = (0.0, 0.0, 0.0)
        self.process_counter = 0
        self.gc_interval = 100
        print("集成计算模块已初始化【最终优化版】。")
        print(f"筛选逻辑: 在机器人基座坐标系中，基于欧氏距离。")

    def process_and_get_transformed_coords(self, detections) -> Dict[str, Tuple[float, float, float]]:
        """
        返回坐标变换后但未滤波的坐标（用于显示）
        """
        # 为每个目标类别创建一个列表，存放它们在基座坐标系下的坐标
        raw_durians_list = []
        raw_persons_list = []

        for det in detections:
            # 提取相机坐标
            raw_coords = (
                det.spatialCoordinates.x,
                det.spatialCoordinates.y,
                det.spatialCoordinates.z
            )
            
            # 根据标签分类存储
            if det.label == self.DURIAN_LABEL_INDEX:
                raw_durians_list.append(raw_coords)
            elif det.label == self.PERSON_LABEL_INDEX:
                raw_persons_list.append(raw_coords)

        # 处理榴莲 - 找到距离原点最近的目标
        closest_durian_coord = None
        if raw_durians_list:
            raw_durians_np = np.array(raw_durians_list)
            transformed_durians_np = self.coordinate_transformer.transform_points_batch(raw_durians_np)
            dist_sq_durians = np.sum(transformed_durians_np**2, axis=1)
            min_idx = np.argmin(dist_sq_durians)
            closest_durian_coord = transformed_durians_np[min_idx]

        # 处理人
        closest_person_coord = None
        if raw_persons_list:
            raw_persons_np = np.array(raw_persons_list)
            transformed_persons_np = self.coordinate_transformer.transform_points_batch(raw_persons_np)
            dist_sq_persons = np.sum(transformed_persons_np**2, axis=1)
            min_idx = np.argmin(dist_sq_persons)
            closest_person_coord = transformed_persons_np[min_idx]

        # 返回变换后的坐标（未滤波）
        return {
            "durian": tuple(closest_durian_coord) if closest_durian_coord is not None else (0.0, 0.0, 0.0),
            "person": tuple(closest_person_coord) if closest_person_coord is not None else (0.0, 0.0, 0.0)
        }

    def process_and_get_final_coords(self, detections) -> Dict[str, Tuple[float, float, float]]:
        """
        接收一帧的原始检测数据，完成所有处理，并返回最终坐标。
        【核心逻辑修改】:
        1. 先将所有检测到的目标变换到机器人基座坐标系。
        2. 然后在基座坐标系中计算欧氏距离，找出最近的目标。
        3. 最后对选中的目标坐标进行滤波。
        """
        # --- 步骤 1: 将所有检测到的目标变换到机器人基座坐标系 ---
        
        # 为每个目标类别创建一个列表，存放它们在基座坐标系下的坐标
        raw_durians_list = []
        raw_persons_list = []

        for det in detections:
            # 提取相机坐标
            raw_coords = (
                det.spatialCoordinates.x,
                det.spatialCoordinates.y,
                det.spatialCoordinates.z
            )
            
            # 根据标签分类存储
            if det.label == self.DURIAN_LABEL_INDEX:
                raw_durians_list.append(raw_coords)
            elif det.label == self.PERSON_LABEL_INDEX:
                raw_persons_list.append(raw_coords)

        # --- 步骤 2: 在基座坐标系中，找到距离原点最近的目标 ---

        # 处理榴莲
        closest_durian_coord = None
        if raw_durians_list:
            # a) 将列表转换为 (N, 3) NumPy 数组
            raw_durians_np = np.array(raw_durians_list)
            
            # b) 调用transform_points_batch进行一次性批量变换
            transformed_durians_np = self.coordinate_transformer.transform_points_batch(raw_durians_np)
            
            # c) 向量化计算所有点到基座原点的距离的平方
            # np.sum(array**2, axis=1) 会对每一行(每个点)的x,y,z平方求和，得到一个(N,)的距离数组
            dist_sq_durians = np.sum(transformed_durians_np**2, axis=1)
            
            # d) 找到距离最小的点的索引
            min_idx = np.argmin(dist_sq_durians)
            
            # e) 提取该点的坐标
            closest_durian_coord = transformed_durians_np[min_idx]

        # 处理人 (逻辑同上)
        closest_person_coord = None
        if raw_persons_list:
            raw_persons_np = np.array(raw_persons_list)
            transformed_persons_np = self.coordinate_transformer.transform_points_batch(raw_persons_np)
            dist_sq_persons = np.sum(transformed_persons_np**2, axis=1)
            min_idx = np.argmin(dist_sq_persons)
            closest_person_coord = transformed_persons_np[min_idx]

        # --- 步骤 3: 对选中的坐标进行滤波或使用历史值 ---

        # 滤波榴莲坐标
        if closest_durian_coord is not None:
            final_durian_coords = self._apply_filter_to_target(
                closest_durian_coord, 'durian'
            )
        else:
            final_durian_coords = self._get_last_filtered_coords('durian', (0.0, 0.0, 0.0))

        # 滤波人坐标
        if closest_person_coord is not None:
            final_person_coords = self._apply_filter_to_target(
                closest_person_coord, 'person'
            )
        else:
            final_person_coords = self._get_last_filtered_coords('person', (0.0, 0.0, 0.0))

        # --- 步骤 4: 内存管理 ---
        self.process_counter += 1
        if self.process_counter >= self.gc_interval:
            self._lightweight_cleanup()
            self.process_counter = 0

        return {
            "durian": final_durian_coords,
            "person": final_person_coords
        }

    # ... 类中的其他方法 (_apply_filter_to_target, _get_last_filtered_coords, etc.) 保持不变 ...
    def _apply_filter_to_target(self, coords: np.ndarray, target_type: str) -> Tuple[float, float, float]:
        x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
        if target_type == 'durian':
            filtered_x = self.durian_filter_x.add_sample(x)
            filtered_y = self.durian_filter_y.add_sample(y)
            filtered_z = self.durian_filter_z.add_sample(z)
            result = (filtered_x, filtered_y, filtered_z)
            self.last_valid_durian = result
            return result
        elif target_type == 'person':
            filtered_x = self.person_filter_x.add_sample(x)
            filtered_y = self.person_filter_y.add_sample(y)
            filtered_z = self.person_filter_z.add_sample(z)
            result = (filtered_x, filtered_y, filtered_z)
            self.last_valid_person = result
            return result
        else:
            raise ValueError(f"未知的目标类型: {target_type}")

    def _get_last_filtered_coords(self, target_type: str, default: Tuple[float, float, float]) -> Tuple[float, float, float]:
        if target_type == 'durian':
            return self.last_valid_durian if self.last_valid_durian != (0.0, 0.0, 0.0) else default
        elif target_type == 'person':
            return self.last_valid_person if self.last_valid_person != (0.0, 0.0, 0.0) else default
        else:
            return default

    def _lightweight_cleanup(self):
        gc.collect()

    def reset_filters(self):
        self.durian_filter_x.reset()
        self.durian_filter_y.reset()
        self.durian_filter_z.reset()
        self.person_filter_x.reset()
        self.person_filter_y.reset()
        self.person_filter_z.reset()
        self.last_valid_durian = (0.0, 0.0, 0.0)
        self.last_valid_person = (0.0, 0.0, 0.0)
        self.process_counter = 0
        print("滤波器已重置，内存已清理")

    def update_calibration(self, new_calib: KinematicCalibration) -> None:
        self.coordinate_transformer.update_calibration(new_calib)
        print(f"坐标变换参数已更新: {self.coordinate_transformer.get_calibration_info()}")

    def get_camera_position(self) -> Tuple[float, float, float]:
        pos = self.coordinate_transformer.camera_position
        return (float(pos[0]), float(pos[1]), float(pos[2]))

    def get_filter_status(self) -> Dict[str, Dict[str, int]]:
        return {
            'durian': {'x_buffer_size': self.durian_filter_x.get_buffer_size(), 'y_buffer_size': self.durian_filter_y.get_buffer_size(), 'z_buffer_size': self.durian_filter_z.get_buffer_size()},
            'person': {'x_buffer_size': self.person_filter_x.get_buffer_size(), 'y_buffer_size': self.person_filter_y.get_buffer_size(), 'z_buffer_size': self.person_filter_z.get_buffer_size()}
        }

    def set_calibration_degrees(self, tx: float = 0.0, ty: float = 0.0, tz: float = 0.0, ry_degrees: float = 0.0, rz_degrees: float = 0.0) -> None:
        new_calib = KinematicCalibration(Tx=tx, Ty=ty, Tz=tz, Ry=ry_degrees, Rz=rz_degrees)
        self.update_calibration(new_calib)

    def reset_person_filters(self):
        """专门清空人员的滤波器和历史信息"""
        self.person_filter_x.reset()
        self.person_filter_y.reset()
        self.person_filter_z.reset()
        self.last_valid_person = (0.0, 0.0, 0.0)
        print("人员滤波器已重置，历史信息已清空")



# ==============================================================================
#    使用示例和测试函数
# ==============================================================================

def example_usage():
    """使用示例 - 展示角度制的使用方法"""
    print("=== 角度制版本使用示例 ===")
    
    # 1. 创建标定配置 - 现在使用角度制
    calib = KinematicCalibration(
        Tx=100.0, Ty=50.0, Tz=200.0,  # 平移 (mm)
        Ry=15.0,   # 俯仰角 15度
        Rz=30.0    # 偏航角 30度
    )
    
    print(f"标定参数: {calib}")
    
    # 2. 创建计算模块
    label_map = ["durian", "person", "other"]
    module = FilteredCalculateModule(label_map, calib, filter_window_size=10)
    
    # 3. 便捷设置方法
    module.set_calibration_degrees(
        tx=150.0, ty=75.0, tz=250.0,
        ry_degrees=20.0,  # 20度俯仰
        rz_degrees=45.0   # 45度偏航
    )
    
    print("角度制版本设置完成！")

if __name__ == "__main__":
    example_usage()
