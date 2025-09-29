"""
坐标修正器模块
提供简单的坐标修正功能，包括固定修正、线性修正等。
"""
from typing import Tuple
import math


class CoordinateCorrector:
    """简化的坐标修正器类"""
    
    def __init__(self):
        """初始化坐标修正器"""
        # 固定修正参数
        self.fixed_offset_x = 0
        self.fixed_offset_y = 0
        self.fixed_offset_z = 0.0
        
        # 线性修正参数
        self.linear_scale_x = -0.1
        self.linear_scale_y = -0.1
        self.linear_scale_z = -0.1
        self.linear_offset_x = 0.0
        self.linear_offset_y = 0.0
        self.linear_offset_z = 0.0
        
        # 二次修正参数（待实现）
        self.quadratic_a_x = 0.0
        self.quadratic_a_y = 0.0
        self.quadratic_a_z = 0.0
        self.quadratic_b_x = 0.0
        self.quadratic_b_y = 0.0
        self.quadratic_b_z = 0.0
        self.quadratic_c_x = 0.0
        self.quadratic_c_y = 0.0
        self.quadratic_c_z = 0.0
        
        # 偏移式修正参数
        self.offset_x_scale = 0.9
        self.offset_y_threshold = 1930.0
        self.offset_y_scale = 0.9
        self.offset_z_scale = 1.0
        
        # # 左相机线性回归修正参数 - 基于坐标的线性模型
        # self.left_regression_x_coeff = 0.089655
        # self.left_regression_y_coeff = -0.260155
        # self.left_regression_x_const = -477.48
        # self.left_regression_y_x_coeff = -0.028946
        # self.left_regression_y_const = 13.61
        
        # # 右相机线性回归修正参数 (基于8-28数据拟合结果)
        # self.right_regression_k_x = 0.085346
        # self.right_regression_b_x = -20.64
        # self.right_regression_constant_y = -10.61
    
        self.left_start_radius = 1500
        self.left_end_radius = 3000
        self.left_correction_magnitude = 300
        
        self.right_start_radius = 1500
        self.right_end_radius = 3000
        self.right_correction_magnitude = 300
        
        
        # # 左相机线性回归修正参数
        # self.left_regression_x_coeff = 0.089655
        # self.left_regression_y_coeff = -0.260155
        # self.left_regression_x_const = -477.48
        # self.left_regression_y_x_coeff = -0.028946
        # self.left_regression_y_const = 13.61
        
        # # 右相机线性回归修正参数
        # self.right_regression_k_x = 0.085346
        # self.right_regression_b_x = -20.64
        # self.right_regression_constant_y = -10.61
    
    def get_fixed_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        获取固定修正值 - 根据坐标正负号决定修正方向
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            固定修正值 (dx, dy, dz) - 使用坐标正负号作为系数
        """
        x, y, z = coordinates
        sign_x = 1 if x <= 0 else -1
        sign_y = 1 if y <= 0 else -1
        sign_z = 1 if z <= 0 else -1
        return (sign_x * self.fixed_offset_x, sign_y * self.fixed_offset_y, sign_z * self.fixed_offset_z)
    
    def get_linear_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        获取线性修正值
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            线性修正值 (dx, dy, dz)
        """
        x, y, z = coordinates
        return (
            x * (self.linear_scale_x - 1.0) + self.linear_offset_x,
            y * (self.linear_scale_y - 1.0) + self.linear_offset_y,
            z * (self.linear_scale_z - 1.0) + self.linear_offset_z
        )
    
    def get_quadratic_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        获取二次修正值 (ax² + bx + c)
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            二次修正值 (dx, dy, dz)
        """
        x, y, z = coordinates
        return (
            self.quadratic_a_x * x * x + self.quadratic_b_x * x + self.quadratic_c_x,
            self.quadratic_a_y * y * y + self.quadratic_b_y * y + self.quadratic_c_y,
            self.quadratic_a_z * z * z + self.quadratic_b_z * z + self.quadratic_c_z
        )
    
    def get_offset_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        获取偏移式修正值
        
        x轴修正：对绝对值从0开始使用系数0.9进行线性修正
        y轴修正：绝对值超过基准1930时，应用当前值*0.9的修正
        z轴修正：使用设定的修正系数
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            偏移式修正值 (dx, dy, dz)
        """
        x, y, z = coordinates
        
        # x轴修正：对绝对值使用0.9系数进行线性修正
        # 修正值 = 原值 * (系数 - 1)，这样应用后得到 原值 + 修正值 = 原值 * 系数
        dx = x * (self.offset_x_scale - 1.0)
        
        # y轴修正：绝对值超过基准时应用修正
        abs_y = abs(y)
        if abs_y > self.offset_y_threshold:
            dy = y * (self.offset_y_scale - 1.0)
        else:
            dy = 0.0  # 未超过基准，不进行修正
        
        # z轴修正：使用设定的修正系数
        dz = z * (self.offset_z_scale - 1.0)
        
        return (dx, dy, dz)
    
    def get_left_regression_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        获取基于坐标线性回归的左相机修正值
        
        优化的坐标线性修正模型：
        X方向：使用双变量模型（R²=0.7675，改进51.8%）
        Y方向：使用基于X坐标的单变量模型（R²=0.2773，改进15.0%）
        Z方向：固定修正到100mm
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            线性回归修正值 (dx, dy, dz)
        """
        x, y, z = coordinates
        px, py, pz = self.get_polar_correction(coordinates=coordinates,
                                            start_radius=self.left_start_radius,
                                            end_radius=self.left_end_radius,
                                            correction_magnitude=self.left_correction_magnitude)
        # # X方向修正：双变量线性模型（效果最佳）
        # # 修正公式：X_error = 0.089655 * X + (-0.260155) * Y + (-477.48)
        # dx = -(self.left_regression_x_coeff * x + self.left_regression_y_coeff * y + self.left_regression_x_const)
        # dx += px
        # # dx = -100
        
        # # Y方向修正：基于X坐标的单变量模型
        # # 修正公式：Y_error = (-0.028946) * X + 13.61
        # # dy = self.left_regression_y_x_coeff * x + self.left_regression_y_const
        # dy = 0
        # dy += py

        dx = -(0.044460 * x + (-0.196588) * y + (-422.00))
        dx += px

        dy = -(0.021864 * x + (-8.66))
        dy += py
        
        # Z方向修正：固定修正到100mm（保持不变）
        dz = self.get_grid_z_correction(coordinates=coordinates) - z
        dz += pz
        
        return (dx, dy, dz)
    
    def get_right_regression_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        获取基于线性回归的右相机修正值
        
        基于最新误差分析的距离修正模型：
        X_error = 0.146145 * distance_from_camera - 247.60
        Y_error = constant_y (基于原有模型)
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            回归修正值 (dx, dy, dz)
        """
        x, y, z = coordinates
        
        # # 硬编码相机原点位置 (基于误差分析结果)
        # camera_origin_x = 0
        # camera_origin_y = 0
        
        # # 计算到相机原点的距离
        # distance_from_camera = ((x - camera_origin_x)**2 + (y - camera_origin_y)**2)**0.5

        px, py, pz = self.get_polar_correction(coordinates=coordinates,
                                            start_radius=self.right_start_radius,
                                            end_radius=self.right_end_radius,
                                            correction_magnitude=self.right_correction_magnitude)
        
        # # X方向修正: 基于距离的修正模型 (R²=0.7866, 可解释78.7%的误差变异)
        # # 修正公式: X_error = 0.146145 * distance_from_camera - 247.60
        # dx = -(0.146145 * distance_from_camera - 247.60)
        # dx += px
        
        # # Y方向修正: 使用原有的常数修正
        # dy = 0
        # dy += py

        dx = -(0.034262 * x + 0.152278 * y + -293.48)
        dx += px
        dy = -(0.015738 * y + (-66.74))
        dy += py
        
        # Z方向修正：总是修正到100mm
        dz = self.get_grid_z_correction(coordinates=coordinates) - z
        # dz += dz
        
        return (dx, dy, dz)
    
    def get_grid_z_correction(self, coordinates: Tuple[float, float, float]) -> float:
        """
        获取基于二次多项式的Z修正值
        
        使用二次多项式拟合结果进行Z修正：
        correction = 0.154879*x - 0.000008*x² - 0.000076*x*y + 0.000003*y²
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            Z修正目标值（绝对值，限制负值为零）
        """
        x, y, z = coordinates
        
        # 基于二次多项式计算修正值(区分y的正负，来区分左右)
        if y > 0:
            correction = 0.341519 * x + -0.000000 * y + -0.000075 * x**2 + -0.000121 * x * y + -0.000024 * y**2
        else:
            correction = 0.038437 * x + -0.000000 * y + -0.000030 * x**2 + -0.000076 * x * y + -0.000027 * y**2
        
        # 限制负值为零
        return max(0.0, correction)
    
    def get_polar_correction(self, coordinates: Tuple[float, float, float],start_radius=1500,end_radius=3000,correction_magnitude=20) -> Tuple[float, float, float]:
        """
        获取极坐标修正值
        
        修正强度：
        - 半径1500时，修正为0
        - 半径3000时，修正为20
        - 线性插值：correction = (r - 1500) * 20 / (3000 - 1500) = (r - 1500) * 20 / 1500
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            极坐标修正值 (dx, dy, dz)
        """
        x, y, z = coordinates
        
        # 计算极坐标
        r = math.sqrt(x**2 + y**2)
        theta = math.atan2(y, x)
        
        # 计算修正强度：线性插值
        # 在半径1500时修正为0，半径3000时修正为20
        if r <= start_radius:
            correction_magnitude = 0.0
        else:
            # 线性插值：correction = (r - 1500) * 20 / 1500
            correction_magnitude = (r - start_radius) * correction_magnitude / (end_radius - start_radius)
        
        # 应用修正：减少半径
        r_corrected = r - correction_magnitude
        
        # 极坐标转换回直角坐标
        x_corrected = r_corrected * math.cos(theta)
        y_corrected = r_corrected * math.sin(theta)
        
        # Z轴保持不变
        z_corrected = z
        
        # 计算修正值（负值，表示向内修正）
        dx = x_corrected - x
        dy = y_corrected - y
        dz = z_corrected - z
        
        return (dx, dy, dz)
    
    def apply_fixed_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        应用固定修正
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            修正后的坐标 (x', y', z')
        """
        x, y, z = coordinates
        sign_x = 1 if x <= 0 else -1
        sign_y = 1 if y <= 0 else -1
        sign_z = 1 if z <= 0 else -1
        return (
            x + sign_x * self.fixed_offset_x,
            y + sign_y * self.fixed_offset_y,
            z + sign_z * self.fixed_offset_z
        )
    
    def apply_linear_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        应用线性修正
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            修正后的坐标 (x', y', z')
        """
        x, y, z = coordinates
        return (
            x * self.linear_scale_x + self.linear_offset_x,
            y * self.linear_scale_y + self.linear_offset_y,
            z * self.linear_scale_z + self.linear_offset_z
        )
    
    def apply_quadratic_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        应用二次修正
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            修正后的坐标 (x', y', z')
        """
        x, y, z = coordinates
        dx, dy, dz = self.get_quadratic_correction(coordinates)
        return (x + dx, y + dy, z + dz)
    
    def apply_offset_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        应用偏移式修正
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            修正后的坐标 (x', y', z')
        """
        x, y, z = coordinates
        dx, dy, dz = self.get_offset_correction(coordinates)
        return (x + dx, y + dy, z + dz)
    
    def apply_left_regression_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        应用基于坐标线性回归的左相机修正
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            修正后的坐标 (x', y', z')
        """
        x, y, z = coordinates
        dx, dy, dz = self.get_left_regression_correction(coordinates)
        return (x + dx, y + dy, z + dz)  # 减去预测的误差
    
    def apply_right_regression_correction(self, coordinates: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        应用基于线性回归的右相机修正
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            
        Returns:
            修正后的坐标 (x', y', z')
        """
        x, y, z = coordinates
        dx, dy, dz = self.get_right_regression_correction(coordinates)
        return (x + dx, y + dy, z + dz)  # 预测的误差
    
    
    def apply_correction(self, coordinates: Tuple[float, float, float], strategy: str = "fixed") -> Tuple[float, float, float]:
        """
        根据策略名称应用对应的坐标修正
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            strategy: 修正策略 ("fixed", "linear", "quadratic", "offset", "left_regression", "right_regression", "grid_z", "none")
            
        Returns:
            修正后的坐标 (x', y', z')
            
        Raises:
            ValueError: 当策略名称不支持时抛出异常
        """
        if strategy == "fixed":
            return self.apply_fixed_correction(coordinates)
        elif strategy == "linear":
            return self.apply_linear_correction(coordinates)
        elif strategy == "quadratic":
            return self.apply_quadratic_correction(coordinates)
        elif strategy == "offset":
            return self.apply_offset_correction(coordinates)
        elif strategy == "left_regression":
            return self.apply_left_regression_correction(coordinates)
        elif strategy == "right_regression":
            return self.apply_right_regression_correction(coordinates)
        elif strategy == "none":
            return coordinates  # 不进行任何修正
        else:
            raise ValueError(f"不支持的修正策略: {strategy}. 支持的策略: 'fixed', 'linear', 'quadratic', 'offset', 'left_regression', 'right_regression', 'grid_z', 'none'")
    
    def set_fixed_parameters(self, offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0) -> None:
        """设置固定修正参数"""
        self.fixed_offset_x = offset_x
        self.fixed_offset_y = offset_y
        self.fixed_offset_z = offset_z
    
    def set_linear_parameters(self, scale_x: float = 1.0, scale_y: float = 1.0, scale_z: float = 1.0,
                             offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0) -> None:
        """设置线性修正参数"""
        self.linear_scale_x = scale_x
        self.linear_scale_y = scale_y
        self.linear_scale_z = scale_z
        self.linear_offset_x = offset_x
        self.linear_offset_y = offset_y
        self.linear_offset_z = offset_z
    
    def set_quadratic_parameters(self, a_x: float = 0.0, b_x: float = 0.0, c_x: float = 0.0,
                                a_y: float = 0.0, b_y: float = 0.0, c_y: float = 0.0,
                                a_z: float = 0.0, b_z: float = 0.0, c_z: float = 0.0) -> None:
        """设置二次修正参数"""
        self.quadratic_a_x, self.quadratic_b_x, self.quadratic_c_x = a_x, b_x, c_x
        self.quadratic_a_y, self.quadratic_b_y, self.quadratic_c_y = a_y, b_y, c_y
        self.quadratic_a_z, self.quadratic_b_z, self.quadratic_c_z = a_z, b_z, c_z
    
    def set_offset_parameters(self, x_scale: float = 0.9, y_threshold: float = 1930.0, y_scale: float = 0.9, z_scale: float = 1.0) -> None:
        """设置偏移式修正参数"""
        self.offset_x_scale = x_scale
        self.offset_y_threshold = y_threshold
        self.offset_y_scale = y_scale
        self.offset_z_scale = z_scale
    
    def set_left_regression_parameters(self, x_coeff: float = 0.089655, y_coeff: float = -0.260155, x_const: float = -477.48,
                                     y_x_coeff: float = -0.028946, y_const: float = 13.61) -> None:
        """设置左相机线性回归修正参数"""
        self.left_regression_x_coeff = x_coeff
        self.left_regression_y_coeff = y_coeff
        self.left_regression_x_const = x_const
        self.left_regression_y_x_coeff = y_x_coeff
        self.left_regression_y_const = y_const
    
    def set_right_regression_parameters(self, k_x: float = 0.085346, b_x: float = -20.64, constant_y: float = 10.61) -> None:
        """设置右相机线性回归修正参数"""
        self.right_regression_k_x = k_x
        self.right_regression_b_x = b_x
        self.right_regression_constant_y = constant_y



# ==============================================================================
#    使用示例和测试函数
# ==============================================================================

def example_usage():
    """使用示例"""
    print("=== 坐标修正器使用示例 ===")
    
    # 创建修正器实例
    corrector = CoordinateCorrector()
    
    # 测试坐标
    test_coords = (100.0, 200.0, 300.0)
    print(f"原始坐标: {test_coords}")
    
    # 1. 固定修正
    corrector.set_fixed_parameters(10.0, -5.0, 15.0)
    fixed_correction = corrector.get_fixed_correction(test_coords)
    fixed_result = corrector.apply_fixed_correction(test_coords)
    print(f"固定修正值: {fixed_correction}")
    print(f"固定修正结果: {fixed_result}")
    
    # 2. 线性修正
    corrector.set_linear_parameters(1.1, 0.9, 1.05, 5.0, -2.0, 8.0)
    linear_correction = corrector.get_linear_correction(test_coords)
    linear_result = corrector.apply_linear_correction(test_coords)
    print(f"线性修正值: {linear_correction}")
    print(f"线性修正结果: {linear_result}")
    
    # 3. 二次修正
    corrector.set_quadratic_parameters(0.001, 0.1, 2.0, 0.002, 0.05, 1.0, 0.0005, 0.08, 3.0)
    quadratic_correction = corrector.get_quadratic_correction(test_coords)
    quadratic_result = corrector.apply_quadratic_correction(test_coords)
    print(f"二次修正值: {quadratic_correction}")
    print(f"二次修正结果: {quadratic_result}")
    
    # 4. 偏移式修正
    corrector.set_offset_parameters()
    offset_correction = corrector.get_offset_correction(test_coords)
    offset_result = corrector.apply_offset_correction(test_coords)
    print(f"偏移式修正值: {offset_correction}")
    print(f"偏移式修正结果: {offset_result}")
    
    # 5. 左相机线性回归修正（基于坐标的线性模型）
    corrector.set_left_regression_parameters()
    left_regression_correction = corrector.get_left_regression_correction(test_coords)
    left_regression_result = corrector.apply_left_regression_correction(test_coords)
    print(f"左相机坐标回归修正值: {left_regression_correction}")
    print(f"左相机坐标回归修正结果: {left_regression_result}")
    
    # 6. 右相机线性回归修正
    corrector.set_right_regression_parameters()
    right_regression_correction = corrector.get_right_regression_correction(test_coords)
    right_regression_result = corrector.apply_right_regression_correction(test_coords)
    print(f"右相机线性回归修正值: {right_regression_correction}")
    print(f"右相机线性回归修正结果: {right_regression_result}")
    
    # 7. 网格Z修正
    grid_z_target = corrector.get_grid_z_correction(test_coords)
    grid_z_result = corrector.apply_grid_z_correction(test_coords)
    print(f"网格Z修正目标值: {grid_z_target}")
    print(f"网格Z修正结果: {grid_z_result}")
    
    # 8. 统一策略应用
    unified_result = corrector.apply_correction(test_coords, strategy="fixed")
    print(f"统一策略应用结果（固定修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="linear")
    print(f"统一策略应用结果（线性修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="quadratic")
    print(f"统一策略应用结果（二次修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="offset")
    print(f"统一策略应用结果（偏移式修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="left_regression")
    print(f"统一策略应用结果（左相机回归修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="right_regression")
    print(f"统一策略应用结果（右相机回归修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="grid_z")
    print(f"统一策略应用结果（网格Z修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="none")
    print(f"统一策略应用结果（不修正）: {unified_result}")


if __name__ == "__main__":
    example_usage()
