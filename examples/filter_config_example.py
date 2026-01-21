"""
滤波器配置使用示例

展示滑动平均滤波器配置的使用方法
"""

from oak_vision_system.core.dto.config_dto.enums import FilterType
from oak_vision_system.core.dto.config_dto.data_processing_config_dto import (
    FilterConfigDTO,
    MovingAverageFilterConfigDTO,
)


def example_1_default_moving_average_filter():
    """示例1: 使用默认的滑动平均滤波器（推荐）"""
    print("=" * 60)
    print("示例1: 默认滑动平均滤波器配置（推荐）")
    print("=" * 60)
    
    # 创建滤波器配置（默认使用滑动平均滤波）
    filter_config = FilterConfigDTO()
    
    print(f"当前滤波器类型: {filter_config.filter_type.value}")
    
    # 获取当前激活的滤波器配置
    active_config = filter_config.get_active_filter_config()
    print(f"激活的配置: {active_config}")
    print(f"  - 窗口大小: {active_config.window_size}")
    print(f"\n💡 滑动平均滤波器优势：")
    print(f"  - 简单高效，计算量小")
    print(f"  - 适合实时系统（15fps场景）")
    print(f"  - 平滑效果好，易于调参")
    print()


def example_2_custom_moving_average_filter():
    """示例2: 自定义滑动平均滤波器参数"""
    print("=" * 60)
    print("示例2: 自定义滑动平均滤波器参数")
    print("=" * 60)
    
    # 创建自定义的滑动平均滤波配置
    moving_avg_config = MovingAverageFilterConfigDTO(
        window_size=10,  # 使用最近10个数据点
    )
    
    # 创建滤波器配置
    filter_config = FilterConfigDTO(
        filter_type=FilterType.MOVING_AVERAGE,
        moving_average_config=moving_avg_config
    )
    
    print(f"当前滤波器类型: {filter_config.filter_type.value}")
    active_config = filter_config.get_active_filter_config()
    print(f"自定义参数:")
    print(f"  - 窗口大小: {active_config.window_size}")
    print()


def example_3_validation():
    """示例3: 配置验证"""
    print("=" * 60)
    print("示例3: 配置验证")
    print("=" * 60)
    
    # 示例: 窗口大小必须 >= 1
    try:
        moving_avg_config = MovingAverageFilterConfigDTO(
            window_size=0  # 无效值，会报错
        )
        moving_avg_config.validate()
    except ValueError as e:
        print(f"❌ 验证失败: {e}")
    
    # 正确的配置
    moving_avg_config = MovingAverageFilterConfigDTO(
        window_size=5  # 有效值
    )
    moving_avg_config.validate()
    print(f"✅ 验证成功: window_size={moving_avg_config.window_size}")
    print()


def example_4_data_processing_module_usage():
    """示例4: 在数据处理模块中使用"""
    print("=" * 60)
    print("示例4: 数据处理模块中使用滤波器")
    print("=" * 60)
    
    class DataProcessor:
        """模拟的数据处理器"""
        
        def __init__(self, filter_config: FilterConfigDTO):
            self.filter_config = filter_config
        
        def process_data(self, data):
            """处理数据"""
            print(f"使用 {self.filter_config.filter_type.value} 滤波器处理数据")
            
            # 获取当前滤波器配置
            config = self.filter_config.get_active_filter_config()
            
            # 应用滑动平均滤波
            print(f"  应用滑动平均滤波 (window={config.window_size})")
            # 实际的滑动平均滤波逻辑...
    
    # 创建处理器（使用默认的滑动平均滤波）
    filter_config = FilterConfigDTO()  # 默认使用滑动平均
    
    processor = DataProcessor(filter_config)
    processor.process_data([1, 2, 3, 4, 5])
    print()


def main():
    """运行所有示例"""
    print("\n" + "🎯" * 30)
    print("滑动平均滤波器配置示例")
    print("🎯" * 30 + "\n")
    
    example_1_default_moving_average_filter()
    example_2_custom_moving_average_filter()
    example_3_validation()
    example_4_data_processing_module_usage()
    
    print("=" * 60)
    print("✅ 所有示例运行完成！")
    print("=" * 60)
    
    print("\n设计优势总结:")
    print("  ✅ 简单高效：滑动平均滤波计算量小")
    print("  ✅ 实时性好：适合 15-30 FPS 的实时系统")
    print("  ✅ 易于调参：只需调整窗口大小")
    print("  ✅ 平滑效果：有效减少噪声和抖动")


if __name__ == "__main__":
    main()
