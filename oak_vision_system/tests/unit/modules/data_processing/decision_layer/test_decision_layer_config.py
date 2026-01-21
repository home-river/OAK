"""
决策层配置验证测试

测试决策层配置的验证逻辑，包括：
- 配置参数验证
- 无效配置错误处理
"""

import pytest

from oak_vision_system.core.dto.config_dto import (
    DecisionLayerConfigDTO,
    PersonWarningConfigDTO,
    ObjectZonesConfigDTO,
    GraspZoneConfigDTO,
)


class TestPersonWarningConfigValidation:
    """测试人员警告配置验证"""
    
    def test_valid_person_warning_config(self):
        """测试有效的人员警告配置"""
        config = PersonWarningConfigDTO(
            d_in=3000.0,
            d_out=3200.0,
            T_warn=3.0,
            T_clear=3.0,
            grace_time=0.5
        )
        
        errors = config._validate_data()
        assert len(errors) == 0
    
    def test_d_out_must_be_greater_than_d_in(self):
        """测试 d_out 必须大于 d_in"""
        config = PersonWarningConfigDTO(
            d_in=3200.0,
            d_out=3000.0,  # d_out < d_in，无效
            T_warn=3.0,
            T_clear=3.0,
            grace_time=0.5
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("d_out 必须大于 d_in" in error for error in errors)
    
    def test_d_out_equal_to_d_in_invalid(self):
        """测试 d_out 等于 d_in 无效"""
        config = PersonWarningConfigDTO(
            d_in=3000.0,
            d_out=3000.0,  # d_out = d_in，无效
            T_warn=3.0,
            T_clear=3.0,
            grace_time=0.5
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("d_out 必须大于 d_in" in error for error in errors)
    
    def test_negative_d_in_invalid(self):
        """测试负数 d_in 无效"""
        config = PersonWarningConfigDTO(
            d_in=-1000.0,  # 负数，无效
            d_out=3200.0,
            T_warn=3.0,
            T_clear=3.0,
            grace_time=0.5
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
    
    def test_negative_T_warn_invalid(self):
        """测试负数 T_warn 无效"""
        config = PersonWarningConfigDTO(
            d_in=3000.0,
            d_out=3200.0,
            T_warn=-1.0,  # 负数，无效
            T_clear=3.0,
            grace_time=0.5
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
    
    def test_negative_grace_time_invalid(self):
        """测试负数 grace_time 无效"""
        config = PersonWarningConfigDTO(
            d_in=3000.0,
            d_out=3200.0,
            T_warn=3.0,
            T_clear=3.0,
            grace_time=-0.5  # 负数，无效
        )
        
        errors = config._validate_data()
        assert len(errors) > 0


class TestGraspZoneConfigValidation:
    """测试抓取区域配置验证"""
    
    def test_valid_rect_grasp_zone(self):
        """测试有效的矩形抓取区域配置"""
        config = GraspZoneConfigDTO(
            mode="rect",
            x_min=500.0,
            x_max=2000.0,
            y_min=1000.0,
            y_max=2000.0
        )
        
        errors = config._validate_data()
        assert len(errors) == 0
    
    def test_valid_radius_grasp_zone(self):
        """测试有效的半径抓取区域配置"""
        config = GraspZoneConfigDTO(
            mode="radius",
            r_min=1000.0,
            r_max=3000.0
        )
        
        errors = config._validate_data()
        assert len(errors) == 0
    
    def test_invalid_mode(self):
        """测试无效的模式"""
        config = GraspZoneConfigDTO(
            mode="invalid_mode",  # 无效模式
            x_min=500.0,
            x_max=2000.0,
            y_min=1000.0,
            y_max=2000.0
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("不支持的抓取区域模式" in error for error in errors)
    
    def test_rect_x_min_greater_than_x_max_invalid(self):
        """测试矩形模式下 x_min > x_max 无效"""
        config = GraspZoneConfigDTO(
            mode="rect",
            x_min=2000.0,
            x_max=500.0,  # x_min > x_max，无效
            y_min=1000.0,
            y_max=2000.0
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("x_min 必须小于 x_max" in error for error in errors)
    
    def test_rect_y_min_greater_than_y_max_invalid(self):
        """测试矩形模式下 y_min > y_max 无效"""
        config = GraspZoneConfigDTO(
            mode="rect",
            x_min=500.0,
            x_max=2000.0,
            y_min=2000.0,
            y_max=1000.0  # y_min > y_max，无效
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("y_min 必须小于 y_max" in error for error in errors)
    
    def test_radius_r_min_greater_than_r_max_invalid(self):
        """测试半径模式下 r_min > r_max 无效"""
        config = GraspZoneConfigDTO(
            mode="radius",
            r_min=3000.0,
            r_max=1000.0  # r_min > r_max，无效
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("r_min 必须小于 r_max" in error for error in errors)
    
    def test_radius_missing_r_min_invalid(self):
        """测试半径模式下缺少 r_min 无效"""
        config = GraspZoneConfigDTO(
            mode="radius",
            r_min=None,  # 缺少 r_min
            r_max=3000.0
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("半径模式需要 r_min 和 r_max" in error for error in errors)
    
    def test_radius_missing_r_max_invalid(self):
        """测试半径模式下缺少 r_max 无效"""
        config = GraspZoneConfigDTO(
            mode="radius",
            r_min=1000.0,
            r_max=None  # 缺少 r_max
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("半径模式需要 r_min 和 r_max" in error for error in errors)


class TestObjectZonesConfigValidation:
    """测试物体区域配置验证"""
    
    def test_valid_object_zones_config(self):
        """测试有效的物体区域配置"""
        grasp_zone = GraspZoneConfigDTO(
            mode="rect",
            x_min=500.0,
            x_max=2000.0,
            y_min=1000.0,
            y_max=2000.0
        )
        config = ObjectZonesConfigDTO(
            danger_y_threshold=1500.0,
            grasp_zone=grasp_zone
        )
        
        errors = config._validate_data()
        assert len(errors) == 0
    
    def test_negative_danger_y_threshold_invalid(self):
        """测试负数 danger_y_threshold 无效"""
        grasp_zone = GraspZoneConfigDTO(
            mode="rect",
            x_min=500.0,
            x_max=2000.0,
            y_min=1000.0,
            y_max=2000.0
        )
        config = ObjectZonesConfigDTO(
            danger_y_threshold=-1500.0,  # 负数，无效
            grasp_zone=grasp_zone
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
    
    def test_invalid_grasp_zone_propagates_errors(self):
        """测试无效的抓取区域配置会传播错误"""
        grasp_zone = GraspZoneConfigDTO(
            mode="rect",
            x_min=2000.0,
            x_max=500.0,  # x_min > x_max，无效
            y_min=1000.0,
            y_max=2000.0
        )
        config = ObjectZonesConfigDTO(
            danger_y_threshold=1500.0,
            grasp_zone=grasp_zone
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("x_min 必须小于 x_max" in error for error in errors)


class TestDecisionLayerConfigValidation:
    """测试决策层配置验证"""
    
    def test_valid_decision_layer_config(self):
        """测试有效的决策层配置"""
        person_warning = PersonWarningConfigDTO(
            d_in=3000.0,
            d_out=3200.0,
            T_warn=3.0,
            T_clear=3.0,
            grace_time=0.5
        )
        grasp_zone = GraspZoneConfigDTO(
            mode="rect",
            x_min=500.0,
            x_max=2000.0,
            y_min=1000.0,
            y_max=2000.0
        )
        object_zones = ObjectZonesConfigDTO(
            danger_y_threshold=1500.0,
            grasp_zone=grasp_zone
        )
        config = DecisionLayerConfigDTO(
            person_label_ids=[0],
            person_warning=person_warning,
            object_zones=object_zones,
            state_expiration_time=1.0
        )
        
        errors = config._validate_data()
        assert len(errors) == 0
    
    def test_invalid_person_warning_propagates_errors(self):
        """测试无效的人员警告配置会传播错误"""
        person_warning = PersonWarningConfigDTO(
            d_in=3200.0,
            d_out=3000.0,  # d_out < d_in，无效
            T_warn=3.0,
            T_clear=3.0,
            grace_time=0.5
        )
        config = DecisionLayerConfigDTO(
            person_warning=person_warning
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("d_out 必须大于 d_in" in error for error in errors)
    
    def test_invalid_object_zones_propagates_errors(self):
        """测试无效的物体区域配置会传播错误"""
        grasp_zone = GraspZoneConfigDTO(
            mode="rect",
            x_min=2000.0,
            x_max=500.0,  # x_min > x_max，无效
            y_min=1000.0,
            y_max=2000.0
        )
        object_zones = ObjectZonesConfigDTO(
            danger_y_threshold=1500.0,
            grasp_zone=grasp_zone
        )
        config = DecisionLayerConfigDTO(
            object_zones=object_zones
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("x_min 必须小于 x_max" in error for error in errors)
    
    def test_negative_state_expiration_time_invalid(self):
        """测试负数 state_expiration_time 无效"""
        config = DecisionLayerConfigDTO(
            state_expiration_time=-1.0  # 负数，无效
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
    
    def test_invalid_person_label_ids_type(self):
        """测试无效的 person_label_ids 类型"""
        config = DecisionLayerConfigDTO(
            person_label_ids="invalid"  # 应该是列表，不是字符串
        )
        
        errors = config._validate_data()
        assert len(errors) > 0
        assert any("person_label_ids 必须为列表类型" in error for error in errors)


class TestDefaultConfigValues:
    """测试默认配置值"""
    
    def test_default_person_warning_config(self):
        """测试默认人员警告配置"""
        config = PersonWarningConfigDTO()
        
        # 默认值单位：毫米（mm）
        assert config.d_in == 3000.0
        assert config.d_out == 3050.0
        assert config.T_warn == 3.0
        assert config.T_clear == 3.0
        assert config.grace_time == 0.5
    
    def test_default_grasp_zone_config(self):
        """测试默认抓取区域配置"""
        config = GraspZoneConfigDTO()
        
        # 默认值单位：毫米（mm）
        assert config.mode == "rect"
        assert config.x_min == -200.0
        assert config.x_max == 2000.0
        assert config.y_min == 1550.0
        assert config.y_max == 2500.0
    
    def test_default_object_zones_config(self):
        """测试默认物体区域配置"""
        config = ObjectZonesConfigDTO()
        
        assert config.danger_y_threshold == 1500.0
        assert isinstance(config.grasp_zone, GraspZoneConfigDTO)
    
    def test_default_decision_layer_config(self):
        """测试默认决策层配置"""
        config = DecisionLayerConfigDTO()
        
        assert config.person_label_ids == [0]
        assert isinstance(config.person_warning, PersonWarningConfigDTO)
        assert isinstance(config.object_zones, ObjectZonesConfigDTO)
        assert config.state_expiration_time == 1.0
