"""
未来模块集成示例

演示滤波模块、坐标变换模块等如何与配置管理器集成
展示三种配置访问模式：
1. 直接访问完整配置（推荐）
2. 使用通用接口动态访问
3. 为常用模块添加专用接口（可选）
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from oak_vision_system.modules.data_collector import SystemConfigManager


# ========== 模拟未来模块的配置DTO ==========

@dataclass
class FilterConfigDTO:
    """滤波配置（示例）"""
    enable_kalman: bool = True
    kalman_q: float = 0.01
    kalman_r: float = 0.1
    enable_median: bool = True
    median_window: int = 5


@dataclass
class TransformConfigDTO:
    """坐标变换配置（示例）"""
    camera_height: float = 1.5  # 相机高度（米）
    camera_tilt: float = 30.0   # 相机倾角（度）
    world_origin: tuple = (0.0, 0.0, 0.0)


@dataclass
class CalibrationConfigDTO:
    """标定配置（示例）"""
    calibration_file: Optional[str] = None
    auto_calibrate: bool = False
    calibration_interval: int = 3600  # 秒


# ========== 方案1：模块自己提取配置（推荐）==========

class FilterModule:
    """
    滤波模块示例
    
    采用"自己提取配置"的方式，模块独立性强
    """
    
    def __init__(self, config_manager: SystemConfigManager):
        """
        初始化滤波模块
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        
        # 方式1：从完整配置中提取（推荐）
        full_config = config_manager.get_full_config()
        
        # 假设 data_processing 中有 filter_config
        # 实际使用时需要先在 DeviceManagerConfigDTO 中添加这个字段
        self.filter_config = FilterConfigDTO()  # 这里用默认值演示
        
        print(f"[FilterModule] 初始化完成")
        print(f"  - 卡尔曼滤波: {self.filter_config.enable_kalman}")
        print(f"  - 中值滤波: {self.filter_config.enable_median}")
    
    def update_config(self, **kwargs):
        """动态更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.filter_config, key):
                setattr(self.filter_config, key, value)
                print(f"[FilterModule] 更新配置: {key} = {value}")


class TransformModule:
    """
    坐标变换模块示例
    
    使用通用接口动态访问配置
    """
    
    def __init__(self, config_manager: SystemConfigManager):
        """初始化坐标变换模块"""
        self.config_manager = config_manager
        
        # 方式2：使用通用接口（灵活）
        # 尝试从配置中获取，如果不存在则使用默认值
        self.transform_config = TransformConfigDTO()
        
        print(f"[TransformModule] 初始化完成")
        print(f"  - 相机高度: {self.transform_config.camera_height}m")
        print(f"  - 相机倾角: {self.transform_config.camera_tilt}°")
    
    def camera_to_world(self, x, y, z):
        """相机坐标转世界坐标"""
        # 使用配置进行坐标转换
        print(f"[TransformModule] 转换坐标: ({x}, {y}, {z})")
        # ... 转换逻辑


class CalibrationModule:
    """
    标定模块示例
    
    展示如何从配置文件读取和保存标定参数
    """
    
    def __init__(self, config_manager: SystemConfigManager):
        self.config_manager = config_manager
        self.calibration_config = CalibrationConfigDTO()
        
        print(f"[CalibrationModule] 初始化完成")
        print(f"  - 自动标定: {self.calibration_config.auto_calibrate}")
    
    def save_calibration(self):
        """保存标定结果到配置"""
        # 这里演示如何将标定结果保存回配置
        self.calibration_config.calibration_file = "calibration/camera_calib.json"
        
        # 实际项目中，需要将这个配置添加到 DeviceManagerConfigDTO
        # 然后通过配置管理器保存
        print(f"[CalibrationModule] 标定结果已保存")


# ========== 使用示例 ==========

def demonstrate_module_integration():
    """演示模块集成"""
    print("=" * 60)
    print("未来模块集成演示")
    print("=" * 60)
    
    # 1. 创建配置管理器
    print("\n1. 初始化配置管理器")
    config_manager = SystemConfigManager("config/system_config.json")
    print("   ✅ 配置中心已就绪")
    
    # 2. 初始化各个模块（各自提取配置）
    print("\n2. 初始化各个模块")
    filter_module = FilterModule(config_manager)
    transform_module = TransformModule(config_manager)
    calibration_module = CalibrationModule(config_manager)
    
    # 3. 模块使用配置
    print("\n3. 模块使用配置工作")
    filter_module.update_config(kalman_q=0.02)
    transform_module.camera_to_world(1.0, 2.0, 3.0)
    calibration_module.save_calibration()
    
    # 4. 展示配置管理器的职责
    print("\n4. 配置管理器的职责")
    print("   ✅ 提供完整配置对象")
    print("   ✅ 提供通用访问接口")
    print("   ✅ 各模块自己解析配置")
    print("   ❌ 不需要为每个模块写专用方法")


def demonstrate_three_patterns():
    """演示三种配置访问模式"""
    print("\n" + "=" * 60)
    print("三种配置访问模式对比")
    print("=" * 60)
    
    config_manager = SystemConfigManager()
    
    # 模式1：直接访问（最灵活，推荐）
    print("\n【模式1】直接访问完整配置（推荐）")
    print("优点：模块完全独立，配置管理器无需修改")
    print("```python")
    print("config = config_manager.get_full_config()")
    print("filter_config = config.data_processing.filter_config")
    print("```")
    full_config = config_manager.get_full_config()
    print(f"✅ 获取到完整配置: {type(full_config).__name__}")
    
    # 模式2：通用接口（动态访问）
    print("\n【模式2】使用通用接口（灵活）")
    print("优点：支持动态模块名，适合插件化架构")
    print("```python")
    print("oak_config = config_manager.get_module_config('oak_config')")
    print("system_config = config_manager.get_module_config('system')")
    print("```")
    oak_config = config_manager.get_module_config('oak_config')
    print(f"✅ 动态获取OAK配置: {type(oak_config).__name__}")
    
    # 模式3：专用接口（便捷但需预留）
    print("\n【模式3】为常用模块添加专用接口（可选）")
    print("优点：接口清晰，IDE自动补全")
    print("缺点：每个新模块都要添加方法")
    print("```python")
    print("oak_config = config_manager.get_oak_config()")
    print("system_config = config_manager.get_system_config()")
    print("# 未来可以添加：")
    print("# filter_config = config_manager.get_filter_config()")
    print("```")
    oak = config_manager.get_oak_config()
    print(f"✅ 专用接口获取: {type(oak).__name__}")


def demonstrate_best_practice():
    """演示最佳实践"""
    print("\n" + "=" * 60)
    print("推荐的最佳实践")
    print("=" * 60)
    
    print("""
    🎯 推荐方案：混合模式
    
    1. 配置管理器提供：
       ✅ get_full_config() - 返回完整配置
       ✅ get_module_config(name) - 通用动态访问
       ✅ 为核心模块保留专用接口（oak_config, system等）
    
    2. 新模块开发时：
       ✅ 模块自己从完整配置中提取需要的部分
       ✅ 模块内部实现配置到业务对象的转换
       ❌ 不需要修改配置管理器代码
    
    3. 配置结构：
       DeviceManagerConfigDTO
       ├── oak_config (专用接口)
       ├── system (专用接口)
       ├── data_processing
       │   ├── filter_config ← 滤波模块自己提取
       │   ├── transform_config ← 变换模块自己提取
       │   └── calibration_config ← 标定模块自己提取
       └── devices
    
    4. 优势：
       ✅ 配置管理器职责单一（只管配置流通）
       ✅ 模块高度独立（各自提取配置）
       ✅ 易于扩展（添加新模块不影响配置管理器）
       ✅ 灵活性高（模块可自定义配置转换逻辑）
    """)


if __name__ == "__main__":
    try:
        # 演示1：模块集成
        demonstrate_module_integration()
        
        # 演示2：三种模式对比
        demonstrate_three_patterns()
        
        # 演示3：最佳实践
        demonstrate_best_practice()
        
        print("\n" + "=" * 60)
        print("✅ 演示完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
