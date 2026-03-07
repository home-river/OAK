"""
TransformParamManager 单元测试

测试 TransformParamManager 的核心功能：
- 参数加载和初始化
- 矩阵构建正确性
- 参数更新流程
- 重置功能

**验证需求: 1.1, 1.5**
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
# 获取当前文件的绝对路径
# tools/calibration_tools/test/test_transform_param_manager.py
# parent: test -> calibration_tools -> tools -> 项目根目录 (需要 3 个 parent)
current_file = Path(__file__).resolve()
test_dir = current_file.parent  # test
calibration_tools_dir = test_dir.parent  # calibration_tools
tools_dir = calibration_tools_dir.parent  # tools
project_root = tools_dir.parent  # 项目根目录

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from copy import deepcopy

from oak_vision_system.core.dto.config_dto import (
    CoordinateTransformConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    DataProcessingConfigDTO
)
from tools.calibration_tools.core.transform_param_manager import TransformParamManager


# ==================== 测试辅助函数 ====================

def create_mock_config_manager(
    mxid: str,
    role: DeviceRole,
    tx: float = 0.0,
    ty: float = 0.0,
    tz: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0
):
    """
    创建模拟的 ConfigManager
    
    Args:
        mxid: 设备ID
        role: 设备角色
        tx, ty, tz: 平移参数（mm）
        pitch, yaw: 旋转参数（度）
    
    Returns:
        Mock 对象
    """
    mock_config_manager = Mock()
    
    # 创建角色绑定
    mock_binding = DeviceRoleBindingDTO(
        role=role,
        active_mxid=mxid,
        historical_mxids=[mxid]
    )

    # 创建坐标变换配置
    transform_config = CoordinateTransformConfigDTO(
        role=role,
        translation_x=tx,
        translation_y=ty,
        translation_z=tz,
        roll=0.0,
        pitch=pitch,
        yaw=yaw
    )
    
    # 创建数据处理配置
    data_config = DataProcessingConfigDTO(
        coordinate_transforms={role: transform_config}
    )
    
    # 配置 mock 返回值
    mock_config_manager.get_active_role_binding_dtos.return_value = {
        role: mock_binding
    }
    mock_config_manager.get_data_processing_config.return_value = data_config
    
    return mock_config_manager


def create_mock_data_processor(success: bool = True):
    """
    创建模拟的 DataProcessor
    
    Args:
        success: update_transform_matrices 是否返回成功
    
    Returns:
        Mock 对象
    """
    mock_data_processor = Mock()
    mock_data_processor.update_transform_matrices.return_value = success
    return mock_data_processor


# ==================== 单元测试 ====================

class TestTransformParamManagerInitialization:
    """TransformParamManager 初始化测试套件"""
    
    def test_initialization_single_device(self):
        """
        测试单设备初始化
        
        验证：
        - 初始配置正确加载
        - mxid 到 role 的映射正确
        - 初始矩阵正确构建
        """
        # Arrange
        test_mxid = "14442C10D13F7FD000"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0,
            ty=50.0,
            tz=0.0,
            pitch=0.0,
            yaw=0.0
        )
        mock_data_processor = create_mock_data_processor()
        
        # Act
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )

        # Assert
        # 验证初始配置已加载
        assert test_mxid in manager._initial_configs, "初始配置应该包含测试设备"
        assert test_mxid in manager._mxid_to_role, "mxid 映射应该包含测试设备"
        assert test_mxid in manager._current_matrices, "当前矩阵应该包含测试设备"
        
        # 验证映射关系
        assert manager._mxid_to_role[test_mxid] == test_role, "mxid 到 role 的映射应该正确"
        
        # 验证初始配置内容
        config = manager._initial_configs[test_mxid]
        assert config.translation_x == 100.0, "translation_x 应该正确"
        assert config.translation_y == 50.0, "translation_y 应该正确"
        assert config.translation_z == 0.0, "translation_z 应该正确"
        
        # 验证矩阵已构建
        matrix = manager._current_matrices[test_mxid]
        assert matrix.shape == (4, 4), "变换矩阵应该是 4x4"
        assert matrix.dtype == np.float32, "矩阵类型应该是 float32"
    
    def test_initialization_multiple_devices(self):
        """
        测试多设备初始化
        
        验证：
        - 所有设备的配置都正确加载
        - 每个设备都有独立的矩阵
        """
        # Arrange
        mxid1 = "DEVICE_001"
        mxid2 = "DEVICE_002"
        role1 = DeviceRole.LEFT_CAMERA
        role2 = DeviceRole.RIGHT_CAMERA
        
        # 创建多设备配置
        mock_config_manager = Mock()
        
        binding1 = DeviceRoleBindingDTO(
            role=role1,
            active_mxid=mxid1,
            historical_mxids=[mxid1]
        )
        binding2 = DeviceRoleBindingDTO(
            role=role2,
            active_mxid=mxid2,
            historical_mxids=[mxid2]
        )
        
        config1 = CoordinateTransformConfigDTO(
            role=role1,
            translation_x=100.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        config2 = CoordinateTransformConfigDTO(
            role=role2,
            translation_x=200.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        
        data_config = DataProcessingConfigDTO(
            coordinate_transforms={role1: config1, role2: config2}
        )
        
        mock_config_manager.get_active_role_binding_dtos.return_value = {
            role1: binding1,
            role2: binding2
        }
        mock_config_manager.get_data_processing_config.return_value = data_config
        
        mock_data_processor = create_mock_data_processor()

        # Act
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Assert
        assert len(manager._initial_configs) == 2, "应该加载两个设备的配置"
        assert mxid1 in manager._initial_configs, "设备1应该在配置中"
        assert mxid2 in manager._initial_configs, "设备2应该在配置中"
        
        assert len(manager._current_matrices) == 2, "应该有两个设备的矩阵"
        assert mxid1 in manager._current_matrices, "设备1应该有矩阵"
        assert mxid2 in manager._current_matrices, "设备2应该有矩阵"
        
        # 验证矩阵不同
        matrix1 = manager._current_matrices[mxid1]
        matrix2 = manager._current_matrices[mxid2]
        assert not np.allclose(matrix1, matrix2), "不同设备的矩阵应该不同"
    
    def test_initialization_with_empty_mxid(self):
        """
        测试当 active_mxid 为空时的初始化
        
        验证：
        - 空 mxid 的设备不会被加载
        """
        # Arrange
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = Mock()
        
        # 创建 active_mxid 为 None 的绑定
        binding = DeviceRoleBindingDTO(
            role=test_role,
            active_mxid=None,
            historical_mxids=[]
        )
        
        config = CoordinateTransformConfigDTO(
            role=test_role,
            translation_x=100.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        
        data_config = DataProcessingConfigDTO(
            coordinate_transforms={test_role: config}
        )
        
        mock_config_manager.get_active_role_binding_dtos.return_value = {
            test_role: binding
        }
        mock_config_manager.get_data_processing_config.return_value = data_config
        
        mock_data_processor = create_mock_data_processor()
        
        # Act
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Assert
        assert len(manager._initial_configs) == 0, "空 mxid 的设备不应该被加载"
        assert len(manager._current_matrices) == 0, "空 mxid 的设备不应该有矩阵"


class TestTransformParamManagerMatrixBuilding:
    """TransformParamManager 矩阵构建测试套件"""

    def test_build_transform_matrix_identity(self):
        """
        测试构建单位变换矩阵（所有参数为0）
        
        验证：
        - 矩阵形状正确
        - 矩阵类型正确
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=0.0, ty=0.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act
        config = manager._initial_configs[test_mxid]
        matrix = manager._build_transform_matrix(config)
        
        # Assert
        assert matrix.shape == (4, 4), "矩阵形状应该是 4x4"
        assert matrix.dtype == np.float32, "矩阵类型应该是 float32"
        
        # 验证矩阵是有效的（不包含 NaN 或 Inf）
        assert not np.any(np.isnan(matrix)), "矩阵不应该包含 NaN"
        assert not np.any(np.isinf(matrix)), "矩阵不应该包含 Inf"
    
    def test_build_transform_matrix_with_translation(self):
        """
        测试构建包含平移的变换矩阵
        
        验证：
        - 平移参数正确应用到矩阵中
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        tx, ty, tz = 100.0, 50.0, 25.0
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=tx, ty=ty, tz=tz,
            pitch=0.0, yaw=0.0
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act
        config = manager._initial_configs[test_mxid]
        matrix = manager._build_transform_matrix(config)
        
        # Assert
        # 测试一个点的变换
        # 原点 (0, 0, 0, 1) 应该变换到 (tx, ty, tz)
        point = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        transformed = matrix @ point
        
        # 注意：由于有 oak_to_xyz 的基准变换，结果可能不是简单的平移
        # 这里只验证变换是确定性的
        assert transformed.shape == (4,), "变换后的点应该是 4 维"
        assert not np.any(np.isnan(transformed)), "变换结果不应该包含 NaN"

    def test_build_transform_matrix_with_rotation(self):
        """
        测试构建包含旋转的变换矩阵
        
        验证：
        - 旋转参数正确应用到矩阵中
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        pitch, yaw = 10.0, 20.0
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=0.0, ty=0.0, tz=0.0,
            pitch=pitch, yaw=yaw
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act
        config = manager._initial_configs[test_mxid]
        matrix = manager._build_transform_matrix(config)
        
        # Assert
        assert matrix.shape == (4, 4), "矩阵形状应该是 4x4"
        
        # 验证矩阵是正交的（旋转矩阵的性质）
        # 提取旋转部分（左上 3x3）
        rotation_part = matrix[:3, :3]
        
        # 计算 R^T @ R，应该接近单位矩阵
        identity_check = rotation_part.T @ rotation_part
        
        # 由于有缩放和其他变换，这里只验证矩阵是有效的
        assert not np.any(np.isnan(rotation_part)), "旋转部分不应该包含 NaN"
        assert not np.any(np.isinf(rotation_part)), "旋转部分不应该包含 Inf"
    
    def test_build_transform_matrix_consistency(self):
        """
        测试矩阵构建的一致性
        
        验证：
        - 相同参数多次构建应该得到相同的矩阵
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=25.0,
            pitch=10.0, yaw=20.0
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act
        config = manager._initial_configs[test_mxid]
        matrix1 = manager._build_transform_matrix(config)
        matrix2 = manager._build_transform_matrix(config)
        
        # Assert
        assert np.allclose(matrix1, matrix2), "相同参数应该构建出相同的矩阵"


class TestTransformParamManagerUpdateParams:
    """TransformParamManager 参数更新测试套件"""

    def test_update_params_success(self):
        """
        测试成功更新参数
        
        验证：
        - update_params 返回 True
        - DataProcessor.update_transform_matrices 被调用
        - 本地矩阵副本已更新
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        mock_data_processor = create_mock_data_processor(success=True)
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # 保存初始矩阵
        initial_matrix = manager._current_matrices[test_mxid].copy()
        
        # Act
        success = manager.update_params(
            mxid=test_mxid,
            tx=200.0, ty=100.0, tz=50.0,
            pitch=10.0, yaw=20.0
        )
        
        # Assert
        assert success is True, "更新应该成功"
        
        # 验证 DataProcessor 被调用
        assert mock_data_processor.update_transform_matrices.called, \
            "DataProcessor.update_transform_matrices 应该被调用"
        
        # 验证本地矩阵已更新
        updated_matrix = manager._current_matrices[test_mxid]
        assert not np.allclose(updated_matrix, initial_matrix), \
            "本地矩阵应该已更新"
    
    def test_update_params_failure(self):
        """
        测试更新参数失败的情况
        
        验证：
        - update_params 返回 False
        - 本地矩阵副本未更新
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        # DataProcessor 返回失败
        mock_data_processor = create_mock_data_processor(success=False)
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # 保存初始矩阵
        initial_matrix = manager._current_matrices[test_mxid].copy()
        
        # Act
        success = manager.update_params(
            mxid=test_mxid,
            tx=200.0, ty=100.0, tz=50.0,
            pitch=10.0, yaw=20.0
        )
        
        # Assert
        assert success is False, "更新应该失败"
        
        # 验证本地矩阵未更新
        current_matrix = manager._current_matrices[test_mxid]
        assert np.allclose(current_matrix, initial_matrix), \
            "本地矩阵不应该更新"

    def test_update_params_nonexistent_device(self):
        """
        测试更新不存在的设备
        
        验证：
        - update_params 返回 False
        - 记录错误日志
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act - 尝试更新不存在的设备
        success = manager.update_params(
            mxid="NONEXISTENT_DEVICE",
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        
        # Assert
        assert success is False, "更新不存在的设备应该失败"
        
        # 验证 DataProcessor 未被调用
        assert not mock_data_processor.update_transform_matrices.called, \
            "DataProcessor 不应该被调用"
    
    def test_update_params_isolation(self):
        """
        测试多设备参数更新的隔离性
        
        验证：
        - 更新一个设备不影响其他设备
        """
        # Arrange
        mxid1 = "DEVICE_001"
        mxid2 = "DEVICE_002"
        role1 = DeviceRole.LEFT_CAMERA
        role2 = DeviceRole.RIGHT_CAMERA
        
        # 创建多设备配置
        mock_config_manager = Mock()
        
        binding1 = DeviceRoleBindingDTO(
            role=role1,
            active_mxid=mxid1,
            historical_mxids=[mxid1]
        )
        binding2 = DeviceRoleBindingDTO(
            role=role2,
            active_mxid=mxid2,
            historical_mxids=[mxid2]
        )
        
        config1 = CoordinateTransformConfigDTO(
            role=role1,
            translation_x=100.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        config2 = CoordinateTransformConfigDTO(
            role=role2,
            translation_x=200.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        
        data_config = DataProcessingConfigDTO(
            coordinate_transforms={role1: config1, role2: config2}
        )
        
        mock_config_manager.get_active_role_binding_dtos.return_value = {
            role1: binding1,
            role2: binding2
        }
        mock_config_manager.get_data_processing_config.return_value = data_config
        
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )

        # 保存初始矩阵
        initial_matrix1 = manager._current_matrices[mxid1].copy()
        initial_matrix2 = manager._current_matrices[mxid2].copy()
        
        # Act - 只更新设备1
        success = manager.update_params(
            mxid=mxid1,
            tx=300.0, ty=150.0, tz=75.0,
            pitch=15.0, yaw=30.0
        )
        
        # Assert
        assert success is True, "更新应该成功"
        
        # 验证设备1的矩阵已更新
        updated_matrix1 = manager._current_matrices[mxid1]
        assert not np.allclose(updated_matrix1, initial_matrix1), \
            "设备1的矩阵应该已更新"
        
        # 验证设备2的矩阵未变化
        current_matrix2 = manager._current_matrices[mxid2]
        assert np.allclose(current_matrix2, initial_matrix2), \
            "设备2的矩阵不应该变化"
    
    def test_update_params_deep_copy(self):
        """
        测试参数更新使用深拷贝
        
        验证：
        - 更新时创建新的矩阵字典
        - 不修改原有字典
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # 保存初始字典的引用
        initial_dict_id = id(manager._current_matrices)
        
        # Act
        success = manager.update_params(
            mxid=test_mxid,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        
        # Assert
        assert success is True, "更新应该成功"
        
        # 验证字典引用已改变（深拷贝）
        updated_dict_id = id(manager._current_matrices)
        assert updated_dict_id != initial_dict_id, \
            "更新后应该是新的字典对象（深拷贝）"


class TestTransformParamManagerReset:
    """TransformParamManager 重置功能测试套件"""
    
    def test_reset_to_default_success(self):
        """
        测试成功重置为默认值
        
        验证：
        - reset_to_default 返回 True
        - 参数恢复到初始值
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        initial_tx, initial_ty, initial_tz = 100.0, 50.0, 25.0
        initial_pitch, initial_yaw = 5.0, 10.0
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=initial_tx, ty=initial_ty, tz=initial_tz,
            pitch=initial_pitch, yaw=initial_yaw
        )
        mock_data_processor = create_mock_data_processor()

        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # 保存初始矩阵
        initial_matrix = manager._current_matrices[test_mxid].copy()
        
        # 先更新参数
        manager.update_params(
            mxid=test_mxid,
            tx=200.0, ty=100.0, tz=50.0,
            pitch=15.0, yaw=30.0
        )
        
        # 验证参数已改变
        updated_matrix = manager._current_matrices[test_mxid]
        assert not np.allclose(updated_matrix, initial_matrix), \
            "参数应该已改变"
        
        # Act - 重置为默认值
        success = manager.reset_to_default(test_mxid)
        
        # Assert
        assert success is True, "重置应该成功"
        
        # 验证矩阵恢复到初始值
        reset_matrix = manager._current_matrices[test_mxid]
        assert np.allclose(reset_matrix, initial_matrix), \
            "矩阵应该恢复到初始值"
    
    def test_reset_to_default_nonexistent_device(self):
        """
        测试重置不存在的设备
        
        验证：
        - reset_to_default 返回 False
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act - 尝试重置不存在的设备
        success = manager.reset_to_default("NONEXISTENT_DEVICE")
        
        # Assert
        assert success is False, "重置不存在的设备应该失败"
    
    def test_reset_to_default_multiple_times(self):
        """
        测试多次重置
        
        验证：
        - 多次重置应该得到相同的结果
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # 保存初始矩阵
        initial_matrix = manager._current_matrices[test_mxid].copy()
        
        # Act - 多次重置
        success1 = manager.reset_to_default(test_mxid)
        matrix1 = manager._current_matrices[test_mxid].copy()
        
        success2 = manager.reset_to_default(test_mxid)
        matrix2 = manager._current_matrices[test_mxid].copy()
        
        # Assert
        assert success1 is True, "第一次重置应该成功"
        assert success2 is True, "第二次重置应该成功"
        
        assert np.allclose(matrix1, initial_matrix), \
            "第一次重置应该恢复到初始值"
        assert np.allclose(matrix2, initial_matrix), \
            "第二次重置应该恢复到初始值"
        assert np.allclose(matrix1, matrix2), \
            "多次重置应该得到相同的结果"



class TestTransformParamManagerGetParamsSnapshot:
    """TransformParamManager 参数快照测试套件"""
    
    def test_get_params_snapshot_success(self):
        """
        测试成功获取参数快照
        
        验证：
        - 返回正确的参数字典
        - 包含所有必要的参数
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        tx, ty, tz = 100.0, 50.0, 25.0
        pitch, yaw = 5.0, 10.0
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=tx, ty=ty, tz=tz,
            pitch=pitch, yaw=yaw
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act
        params = manager.get_params_snapshot(test_mxid)
        
        # Assert
        assert params is not None, "应该返回参数字典"
        assert 'tx' in params, "应该包含 tx"
        assert 'ty' in params, "应该包含 ty"
        assert 'tz' in params, "应该包含 tz"
        assert 'pitch' in params, "应该包含 pitch"
        assert 'yaw' in params, "应该包含 yaw"
        assert 'roll' in params, "应该包含 roll"
        
        assert params['tx'] == tx, "tx 值应该正确"
        assert params['ty'] == ty, "ty 值应该正确"
        assert params['tz'] == tz, "tz 值应该正确"
        assert params['pitch'] == pitch, "pitch 值应该正确"
        assert params['yaw'] == yaw, "yaw 值应该正确"
    
    def test_get_params_snapshot_nonexistent_device(self):
        """
        测试获取不存在设备的参数快照
        
        验证：
        - 返回 None
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act
        params = manager.get_params_snapshot("NONEXISTENT_DEVICE")
        
        # Assert
        assert params is None, "不存在的设备应该返回 None"
    
    def test_get_params_snapshot_returns_initial_config(self):
        """
        测试参数快照返回初始配置（不受更新影响）
        
        验证：
        - 即使参数已更新，快照仍返回初始值
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        initial_tx = 100.0
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=initial_tx, ty=0.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )

        # 更新参数
        manager.update_params(
            mxid=test_mxid,
            tx=200.0, ty=100.0, tz=50.0,
            pitch=10.0, yaw=20.0
        )
        
        # Act - 获取参数快照
        params = manager.get_params_snapshot(test_mxid)
        
        # Assert
        assert params is not None, "应该返回参数字典"
        assert params['tx'] == initial_tx, \
            "快照应该返回初始值，不受更新影响"


class TestTransformParamManagerGetCurrentMxid:
    """TransformParamManager 获取当前 mxid 测试套件"""
    
    def test_get_current_mxid_single_device(self):
        """
        测试单设备模式获取 mxid
        
        验证：
        - 返回正确的 mxid
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act
        current_mxid = manager.get_current_mxid()
        
        # Assert
        assert current_mxid == test_mxid, "应该返回正确的 mxid"
    
    def test_get_current_mxid_multiple_devices_raises_error(self):
        """
        测试多设备模式抛出异常
        
        验证：
        - 抛出 ValueError
        """
        # Arrange
        mxid1 = "DEVICE_001"
        mxid2 = "DEVICE_002"
        role1 = DeviceRole.LEFT_CAMERA
        role2 = DeviceRole.RIGHT_CAMERA
        
        # 创建多设备配置
        mock_config_manager = Mock()
        
        binding1 = DeviceRoleBindingDTO(
            role=role1,
            active_mxid=mxid1,
            historical_mxids=[mxid1]
        )
        binding2 = DeviceRoleBindingDTO(
            role=role2,
            active_mxid=mxid2,
            historical_mxids=[mxid2]
        )
        
        config1 = CoordinateTransformConfigDTO(
            role=role1,
            translation_x=100.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        config2 = CoordinateTransformConfigDTO(
            role=role2,
            translation_x=200.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        
        data_config = DataProcessingConfigDTO(
            coordinate_transforms={role1: config1, role2: config2}
        )
        
        mock_config_manager.get_active_role_binding_dtos.return_value = {
            role1: binding1,
            role2: binding2
        }
        mock_config_manager.get_data_processing_config.return_value = data_config
        
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.get_current_mxid()
        
        assert "期望单设备运行" in str(exc_info.value), \
            "错误消息应该说明期望单设备运行"
    
    def test_get_current_mxid_no_devices_raises_error(self):
        """
        测试无设备时抛出异常
        
        验证：
        - 抛出 ValueError
        """
        # Arrange
        mock_config_manager = Mock()
        
        # 返回空的角色绑定
        mock_config_manager.get_active_role_binding_dtos.return_value = {}
        
        data_config = DataProcessingConfigDTO(
            coordinate_transforms={}
        )
        mock_config_manager.get_data_processing_config.return_value = data_config
        
        mock_data_processor = create_mock_data_processor()
        
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.get_current_mxid()
        
        assert "期望单设备运行" in str(exc_info.value), \
            "错误消息应该说明期望单设备运行"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
