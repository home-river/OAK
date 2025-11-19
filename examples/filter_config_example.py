"""
滤波器配置使用示例

展示策略模式的滤波器配置设计的优势
"""

from oak_vision_system.core.dto.config_dto.enums import FilterType
from oak_vision_system.core.dto.config_dto.data_processing_config_dto import (
    FilterConfigDTO,
    MovingAverageFilterConfigDTO,
    KalmanFilterConfigDTO,
    LowpassFilterConfigDTO,
    MedianFilterConfigDTO,
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
    print(f"  - 加权模式: {'是' if active_config.weighted else '否'}")
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
        weighted=True    # 使用加权平均（越新的数据权重越大）
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
    print(f"  - 加权模式: {'是' if active_config.weighted else '否'}")
    print()


def example_3_custom_kalman_filter():
    """示例3: 自定义卡尔曼滤波器参数"""
    print("=" * 60)
    print("示例3: 自定义卡尔曼滤波器参数")
    print("=" * 60)
    
    # 创建自定义的卡尔曼滤波配置
    kalman_config = KalmanFilterConfigDTO(
        kalman_gain=0.8,
        process_noise=0.05,
        measurement_noise=0.3
    )
    
    # 创建滤波器配置
    filter_config = FilterConfigDTO(
        filter_type=FilterType.KALMAN,
        kalman_config=kalman_config
    )
    
    print(f"当前滤波器类型: {filter_config.filter_type.value}")
    active_config = filter_config.get_active_filter_config()
    print(f"自定义参数:")
    print(f"  - 卡尔曼增益: {active_config.kalman_gain}")
    print(f"  - 过程噪声: {active_config.process_noise}")
    print(f"  - 测量噪声: {active_config.measurement_noise}")
    print()


def example_4_lowpass_filter():
    """示例4: 切换到低通滤波器"""
    print("=" * 60)
    print("示例3: 低通滤波器配置")
    print("=" * 60)
    
    # 创建低通滤波配置
    lowpass_config = LowpassFilterConfigDTO(
        cutoff_frequency=10.0
    )
    
    # 创建滤波器配置
    filter_config = FilterConfigDTO(
        filter_type=FilterType.LOWPASS,
        lowpass_config=lowpass_config
    )
    
    print(f"当前滤波器类型: {filter_config.filter_type.value}")
    active_config = filter_config.get_active_filter_config()
    print(f"低通滤波参数:")
    print(f"  - 截止频率: {active_config.cutoff_frequency} Hz")
    print()


def example_5_median_filter():
    """示例5: 切换到中值滤波器"""
    print("=" * 60)
    print("示例4: 中值滤波器配置")
    print("=" * 60)
    
    # 创建中值滤波配置
    median_config = MedianFilterConfigDTO(
        window_size=7  # 必须为奇数
    )
    
    # 创建滤波器配置
    filter_config = FilterConfigDTO(
        filter_type=FilterType.MEDIAN,
        median_config=median_config
    )
    
    print(f"当前滤波器类型: {filter_config.filter_type.value}")
    active_config = filter_config.get_active_filter_config()
    print(f"中值滤波参数:")
    print(f"  - 窗口大小: {active_config.window_size}")
    print()


def example_6_runtime_switch():
    """示例6: 运行时切换滤波器"""
    print("=" * 60)
    print("示例5: 运行时切换滤波器")
    print("=" * 60)
    
    # 创建包含所有滤波器配置的对象
    filter_config = FilterConfigDTO(
        filter_type=FilterType.MOVING_AVERAGE,
        moving_average_config=MovingAverageFilterConfigDTO(
            window_size=8,
            weighted=False
        ),
        kalman_config=KalmanFilterConfigDTO(
            kalman_gain=0.7,
            process_noise=0.1,
            measurement_noise=0.4
        ),
        lowpass_config=LowpassFilterConfigDTO(
            cutoff_frequency=8.0
        ),
        median_config=MedianFilterConfigDTO(
            window_size=5
        )
    )
    
    print("初始配置:")
    print(f"  当前滤波器: {filter_config.filter_type.value}")
    print(f"  激活配置: {filter_config.get_active_filter_config()}")
    
    # 注意：由于 DTO 是 frozen=True，无法直接修改
    # 实际使用中需要创建新的配置对象
    print("\n注意: DTO是不可变的，运行时切换需要创建新实例")
    
    # 创建新的配置（切换到低通滤波）
    new_filter_config = FilterConfigDTO(
        filter_type=FilterType.LOWPASS,
        moving_average_config=filter_config.moving_average_config,  # 复用已有配置
        lowpass_config=filter_config.lowpass_config,
        kalman_config=filter_config.kalman_config,
        median_config=filter_config.median_config
    )
    
    print(f"\n切换后:")
    print(f"  当前滤波器: {new_filter_config.filter_type.value}")
    print(f"  激活配置: {new_filter_config.get_active_filter_config()}")
    print()


def example_7_validation():
    """示例7: 配置验证"""
    print("=" * 60)
    print("示例6: 配置验证")
    print("=" * 60)
    
    # 示例: 中值滤波窗口大小必须为奇数
    try:
        median_config = MedianFilterConfigDTO(
            window_size=6  # 偶数，会报错
        )
        median_config.validate()
    except ValueError as e:
        print(f"❌ 验证失败: {e}")
    
    # 正确的配置
    median_config = MedianFilterConfigDTO(
        window_size=7  # 奇数，正确
    )
    median_config.validate()
    print(f"✅ 验证成功: window_size={median_config.window_size}")
    print()


def example_8_data_processing_module_usage():
    """示例8: 在数据处理模块中使用"""
    print("=" * 60)
    print("示例7: 数据处理模块中使用滤波器")
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
            
            # 根据滤波器类型执行不同的处理逻辑
            if self.filter_config.filter_type == FilterType.MOVING_AVERAGE:
                print(f"  应用滑动平均滤波 (window={config.window_size}, weighted={config.weighted})")
                # 实际的滑动平均滤波逻辑...
            
            elif self.filter_config.filter_type == FilterType.KALMAN:
                print(f"  应用卡尔曼滤波 (gain={config.kalman_gain})")
                # 实际的卡尔曼滤波逻辑...
            
            elif self.filter_config.filter_type == FilterType.LOWPASS:
                print(f"  应用低通滤波 (cutoff={config.cutoff_frequency}Hz)")
                # 实际的低通滤波逻辑...
            
            elif self.filter_config.filter_type == FilterType.MEDIAN:
                print(f"  应用中值滤波 (window={config.window_size})")
                # 实际的中值滤波逻辑...
    
    # 创建处理器（使用默认的滑动平均滤波）
    filter_config = FilterConfigDTO()  # 默认使用滑动平均
    
    processor = DataProcessor(filter_config)
    processor.process_data([1, 2, 3, 4, 5])
    print()


def main():
    """运行所有示例"""
    print("\n" + "🎯" * 30)
    print("滤波器配置策略模式示例")
    print("🎯" * 30 + "\n")
    
    example_1_default_moving_average_filter()
    example_2_custom_moving_average_filter()
    example_3_custom_kalman_filter()
    example_4_lowpass_filter()
    example_5_median_filter()
    example_6_runtime_switch()
    example_7_validation()
    example_8_data_processing_module_usage()
    
    print("=" * 60)
    print("✅ 所有示例运行完成！")
    print("=" * 60)
    
    print("\n设计优势总结:")
    print("  ✅ 职责分离：每个滤波器管理自己的参数")
    print("  ✅ 类型安全：通过枚举明确滤波器类型")
    print("  ✅ 易于扩展：添加新滤波器只需新增配置类")
    print("  ✅ 清晰明了：一眼看出当前使用哪个滤波器")
    print("  ✅ 配置隔离：切换滤波器时无关参数不会干扰")


if __name__ == "__main__":
    main()

