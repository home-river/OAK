"""
坐标修正器模块
提供简单的坐标修正功能，包括固定修正、线性修正等。
"""
from typing import Tuple


class CoordinateCorrector:
    """简化的坐标修正器类"""
    
    def __init__(self):
        """初始化坐标修正器"""
        # 固定修正参数
        self.fixed_offset_x = 100.0
        self.fixed_offset_y = 100.0
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
    
    def apply_correction(self, coordinates: Tuple[float, float, float], strategy: str = "fixed") -> Tuple[float, float, float]:
        """
        根据策略名称应用对应的坐标修正
        
        Args:
            coordinates: 输入坐标 (x, y, z)
            strategy: 修正策略 ("fixed", "linear", "quadratic")
            
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
        elif strategy == "none":
            return coordinates  # 不进行任何修正
        else:
            raise ValueError(f"不支持的修正策略: {strategy}. 支持的策略: 'fixed', 'linear', 'quadratic', 'none'")
    
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
    
    # 4. 统一策略应用
    unified_result = corrector.apply_correction(test_coords, strategy="fixed")
    print(f"统一策略应用结果（固定修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="linear")
    print(f"统一策略应用结果（线性修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="quadratic")
    print(f"统一策略应用结果（二次修正）: {unified_result}")
    unified_result = corrector.apply_correction(test_coords, strategy="none")
    print(f"统一策略应用结果（不修正）: {unified_result}")


if __name__ == "__main__":
    example_usage()
