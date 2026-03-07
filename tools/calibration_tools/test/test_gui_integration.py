"""
CalibrationGUI 集成测试

测试 CalibrationGUI 与 TransformParamManager 和 ErrorRecorder 的集成：
- 参数更新流程
- 误差记录流程
- 重置功能

**验证需求: 2.5, 2.6, 2.7, 3.2**
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
current_file = Path(__file__).resolve()
test_dir = current_file.parent
calibration_tools_dir = test_dir.parent
tools_dir = calibration_tools_dir.parent
project_root = tools_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from copy import deepcopy

from oak_vision_system.core.dto.config_dto import (
    CoordinateTransformConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    DataProcessingConfigDTO
)
from tools.calibration_tools.core.transform_param_manager import TransformParamManager
from tools.calibration_tools.core.error_recorder import ErrorRecorder
from tools.calibration_tools.gui.calibration_gui import CalibrationGUI


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
    """创建模拟的 ConfigManager"""
    mock_config_manager = Mock()
    
    mock_binding = DeviceRoleBindingDTO(
        role=role,
        active_mxid=mxid,
        historical_mxids=[mxid]
    )

    transform_config = CoordinateTransformConfigDTO(
        role=role,
        translation_x=tx,
        translation_y=ty,
        translation_z=tz,
        roll=0.0,
        pitch=pitch,
        yaw=yaw
    )
    
    data_config = DataProcessingConfigDTO(
        coordinate_transforms={role: transform_config}
    )
    
    mock_config_manager.get_active_role_binding_dtos.return_value = {
        role: mock_binding
    }
    mock_config_manager.get_data_processing_config.return_value = data_config
    
    return mock_config_manager


def create_mock_data_processor(success: bool = True):
    """创建模拟的 DataProcessor"""
    mock_data_processor = Mock()
    mock_data_processor.update_transform_matrices.return_value = success
    return mock_data_processor


def create_mock_decision_layer(target_coords=None):
    """创建模拟的 DecisionLayer"""
    mock_decision_layer = Mock()
    mock_decision_layer.get_target_coords_snapshot.return_value = target_coords
    return mock_decision_layer


# ==================== 集成测试 ====================

class TestGUIParameterUpdateIntegration:
    """GUI 参数更新集成测试套件"""
    
    def test_gui_set_params_success(self):
        """
        测试通过 GUI 成功设置参数
        
        验证需求 2.5: WHEN 用户点击"设置参数"按钮 THEN GUI SHALL 将当前参数和目标mxid发送到CoordinateTransformer
        验证需求 2.6: WHEN 参数更新成功 THEN GUI SHALL 显示更新成功的状态反馈
        
        流程：
        1. 创建 GUI 实例
        2. 修改参数值
        3. 调用 _on_set_params
        4. 验证 TransformParamManager.update_params 被调用
        5. 验证状态标签显示成功
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
        mock_decision_layer = create_mock_decision_layer()
        
        # 创建真实的 TransformParamManager 和 ErrorRecorder
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration.json"
        )
        
        # 创建 GUI（不启动主循环）
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # 修改参数值
        new_tx, new_ty, new_tz = 200.0, 100.0, 50.0
        new_pitch, new_yaw = 10.0, 20.0
        
        gui.params["tx"].set(new_tx)
        gui.params["ty"].set(new_ty)
        gui.params["tz"].set(new_tz)
        gui.params["pitch"].set(new_pitch)
        gui.params["yaw"].set(new_yaw)
        
        # Act - 调用设置参数回调
        gui._on_set_params()
        
        # Assert
        # 验证 DataProcessor 被调用
        assert mock_data_processor.update_transform_matrices.called, \
            "DataProcessor.update_transform_matrices 应该被调用"
        
        # 验证状态标签显示成功
        assert "成功" in gui.status_label.cget("text"), \
            "状态标签应该显示成功"
        assert str(gui.status_label.cget("foreground")) == "green", \
            "状态标签颜色应该是绿色"
        
        # 清理
        gui.root.destroy()
    
    def test_gui_set_params_failure(self):
        """
        测试通过 GUI 设置参数失败
        
        验证需求 2.7: WHEN 参数更新失败 THEN GUI SHALL 显示错误信息和失败原因
        
        流程：
        1. 创建 GUI 实例（DataProcessor 返回失败）
        2. 修改参数值
        3. 调用 _on_set_params
        4. 验证状态标签显示失败
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        # DataProcessor 返回失败
        mock_data_processor = create_mock_data_processor(success=False)
        mock_decision_layer = create_mock_decision_layer()
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # 修改参数值
        gui.params["tx"].set(200.0)
        gui.params["ty"].set(100.0)
        gui.params["tz"].set(50.0)
        gui.params["pitch"].set(10.0)
        gui.params["yaw"].set(20.0)
        
        # Act
        gui._on_set_params()
        
        # Assert
        # 验证状态标签显示失败
        assert "失败" in gui.status_label.cget("text"), \
            "状态标签应该显示失败"
        assert str(gui.status_label.cget("foreground")) == "red", \
            "状态标签颜色应该是红色"
        
        # 清理
        gui.root.destroy()
    
    def test_gui_param_adjustment_buttons(self):
        """
        测试 GUI 参数微调按钮
        
        验证：
        - [+] 按钮增加参数值
        - [-] 按钮减少参数值
        - 步长正确（平移 1.0mm，旋转 0.1度）
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=5.0, yaw=10.0
        )
        mock_data_processor = create_mock_data_processor()
        mock_decision_layer = create_mock_decision_layer()
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # Act & Assert - 测试平移参数微调（步长 1.0mm）
        initial_tx = gui.params["tx"].get()
        gui._adjust_param("tx", 1.0)  # [+] 按钮
        assert gui.params["tx"].get() == initial_tx + 1.0, \
            "tx 应该增加 1.0mm"
        
        gui._adjust_param("tx", -1.0)  # [-] 按钮
        assert gui.params["tx"].get() == initial_tx, \
            "tx 应该减少 1.0mm 回到初始值"
        
        # Act & Assert - 测试旋转参数微调（步长 0.1度）
        initial_pitch = gui.params["pitch"].get()
        gui._adjust_param("pitch", 0.1)  # [+] 按钮
        assert abs(gui.params["pitch"].get() - (initial_pitch + 0.1)) < 1e-6, \
            "pitch 应该增加 0.1度"
        
        gui._adjust_param("pitch", -0.1)  # [-] 按钮
        assert abs(gui.params["pitch"].get() - initial_pitch) < 1e-6, \
            "pitch 应该减少 0.1度 回到初始值"
        
        # 清理
        gui.root.destroy()


class TestGUIResetIntegration:
    """GUI 重置功能集成测试套件"""
    
    def test_gui_reset_to_default(self):
        """
        测试通过 GUI 重置为默认值
        
        验证需求 2.6: GUI 提供重置为默认值的功能
        
        流程：
        1. 创建 GUI 实例
        2. 修改参数值
        3. 调用 _on_reset
        4. 验证参数恢复到初始值
        5. 验证状态标签显示成功
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
        mock_decision_layer = create_mock_decision_layer()
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # 修改参数值
        gui.params["tx"].set(200.0)
        gui.params["ty"].set(100.0)
        gui.params["tz"].set(50.0)
        gui.params["pitch"].set(15.0)
        gui.params["yaw"].set(30.0)
        
        # 先设置参数（使其生效）
        gui._on_set_params()
        
        # Act - 重置为默认值
        gui._on_reset()
        
        # Assert
        # 验证 GUI 显示的参数恢复到初始值
        assert gui.params["tx"].get() == initial_tx, \
            "tx 应该恢复到初始值"
        assert gui.params["ty"].get() == initial_ty, \
            "ty 应该恢复到初始值"
        assert gui.params["tz"].get() == initial_tz, \
            "tz 应该恢复到初始值"
        assert gui.params["pitch"].get() == initial_pitch, \
            "pitch 应该恢复到初始值"
        assert gui.params["yaw"].get() == initial_yaw, \
            "yaw 应该恢复到初始值"
        
        # 验证状态标签显示成功
        assert "重置" in gui.status_label.cget("text"), \
            "状态标签应该显示重置成功"
        assert str(gui.status_label.cget("foreground")) == "green", \
            "状态标签颜色应该是绿色"
        
        # 清理
        gui.root.destroy()
    
    def test_gui_reset_multiple_times(self):
        """
        测试多次重置
        
        验证：
        - 多次重置应该得到相同的结果
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
        mock_decision_layer = create_mock_decision_layer()
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # 修改参数
        gui.params["tx"].set(200.0)
        gui._on_set_params()
        
        # Act - 第一次重置
        gui._on_reset()
        tx_after_first_reset = gui.params["tx"].get()
        
        # 再次修改参数
        gui.params["tx"].set(300.0)
        gui._on_set_params()
        
        # Act - 第二次重置
        gui._on_reset()
        tx_after_second_reset = gui.params["tx"].get()
        
        # Assert
        assert tx_after_first_reset == initial_tx, \
            "第一次重置应该恢复到初始值"
        assert tx_after_second_reset == initial_tx, \
            "第二次重置应该恢复到初始值"
        assert tx_after_first_reset == tx_after_second_reset, \
            "多次重置应该得到相同的结果"
        
        # 清理
        gui.root.destroy()


class TestGUIErrorRecordingIntegration:
    """GUI 误差记录集成测试套件"""
    
    def test_gui_record_error_success(self):
        """
        测试通过 GUI 成功记录误差
        
        验证需求 3.2: WHEN 用户触发误差记录 THEN 系统 SHALL 读取输入框中的基准位置值
        
        流程：
        1. 创建 GUI 实例
        2. 设置基准位置
        3. Mock DecisionLayer 返回目标坐标
        4. 调用 _on_record_error
        5. 验证误差记录成功
        6. 验证记录计数增加
        7. 验证状态标签显示成功
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        mock_data_processor = create_mock_data_processor()
        
        # Mock DecisionLayer 返回目标坐标
        target_coords = np.array([1005.0, 505.0, 2.0])
        mock_decision_layer = create_mock_decision_layer(target_coords=target_coords)
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration_error.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # 设置基准位置
        ref_x, ref_y = 1000.0, 500.0
        gui.ref_params["ref_x"].set(ref_x)
        gui.ref_params["ref_y"].set(ref_y)
        
        # 记录初始计数
        initial_count = gui.record_count
        
        # Act - 记录误差
        gui._on_record_error()
        
        # Assert
        # 验证记录计数增加
        assert gui.record_count == initial_count + 1, \
            "记录计数应该增加 1"
        
        # 验证记录计数标签更新
        assert f"{gui.record_count} 条" in gui.record_count_label.cget("text"), \
            "记录计数标签应该更新"
        
        # 验证状态标签显示成功
        assert "成功" in gui.status_label.cget("text"), \
            "状态标签应该显示成功"
        assert str(gui.status_label.cget("foreground")) == "green", \
            "状态标签颜色应该是绿色"
        
        # 验证 DecisionLayer 被调用
        assert mock_decision_layer.get_target_coords_snapshot.called, \
            "DecisionLayer.get_target_coords_snapshot 应该被调用"
        
        # 清理
        gui.root.destroy()
        
        # 清理测试文件
        import os
        if os.path.exists("logs/test_gui_integration_error.json"):
            os.remove("logs/test_gui_integration_error.json")
    
    def test_gui_record_error_no_target(self):
        """
        测试当没有检测到目标时记录误差
        
        验证：
        - 记录失败
        - 状态标签显示失败原因
        - 记录计数不增加
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        mock_data_processor = create_mock_data_processor()
        
        # Mock DecisionLayer 返回 None（未检测到目标）
        mock_decision_layer = create_mock_decision_layer(target_coords=None)
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration_error.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # 设置基准位置
        gui.ref_params["ref_x"].set(1000.0)
        gui.ref_params["ref_y"].set(500.0)
        
        # 记录初始计数
        initial_count = gui.record_count
        
        # Act - 尝试记录误差
        gui._on_record_error()
        
        # Assert
        # 验证记录计数未增加
        assert gui.record_count == initial_count, \
            "记录计数不应该增加"
        
        # 验证状态标签显示失败
        assert "失败" in gui.status_label.cget("text") or \
               "未检测到目标" in gui.status_label.cget("text"), \
            "状态标签应该显示失败或未检测到目标"
        assert str(gui.status_label.cget("foreground")) == "red", \
            "状态标签颜色应该是红色"
        
        # 清理
        gui.root.destroy()
    
    def test_gui_record_error_multiple_times(self):
        """
        测试多次记录误差
        
        验证：
        - 记录计数正确累加
        - 每次记录都成功
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        mock_data_processor = create_mock_data_processor()
        
        # Mock DecisionLayer 返回目标坐标
        target_coords = np.array([1005.0, 505.0, 2.0])
        mock_decision_layer = create_mock_decision_layer(target_coords=target_coords)
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration_error_multiple.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # 设置基准位置
        gui.ref_params["ref_x"].set(1000.0)
        gui.ref_params["ref_y"].set(500.0)
        
        # Act - 记录多次误差
        num_records = 3
        for i in range(num_records):
            gui._on_record_error()
        
        # Assert
        # 验证记录计数正确
        assert gui.record_count == num_records, \
            f"记录计数应该是 {num_records}"
        
        # 验证记录计数标签正确
        assert f"{num_records} 条" in gui.record_count_label.cget("text"), \
            "记录计数标签应该显示正确的数量"
        
        # 清理
        gui.root.destroy()
        
        # 清理测试文件
        import os
        if os.path.exists("logs/test_gui_integration_error_multiple.json"):
            os.remove("logs/test_gui_integration_error_multiple.json")


class TestGUICompleteWorkflow:
    """GUI 完整工作流程集成测试套件"""
    
    def test_complete_calibration_workflow(self):
        """
        测试完整的校准工作流程
        
        验证：
        1. 初始化 GUI
        2. 调整参数
        3. 设置参数
        4. 记录误差
        5. 重置参数
        6. 再次记录误差
        
        这是一个端到端的集成测试，验证所有组件协同工作
        """
        # Arrange
        test_mxid = "TEST_DEVICE"
        test_role = DeviceRole.LEFT_CAMERA
        
        initial_tx, initial_ty = 100.0, 50.0
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=initial_tx, ty=initial_ty, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        mock_data_processor = create_mock_data_processor()
        
        # Mock DecisionLayer 返回目标坐标
        target_coords = np.array([1005.0, 505.0, 2.0])
        mock_decision_layer = create_mock_decision_layer(target_coords=target_coords)
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration_workflow.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # Step 1: 验证初始化
        assert gui.mxid == test_mxid, "mxid 应该正确"
        assert gui.params["tx"].get() == initial_tx, "初始 tx 应该正确"
        assert gui.params["ty"].get() == initial_ty, "初始 ty 应该正确"
        
        # Step 2: 调整参数
        gui._adjust_param("tx", 10.0)  # 增加 10mm
        gui._adjust_param("ty", -5.0)  # 减少 5mm
        
        assert gui.params["tx"].get() == initial_tx + 10.0, \
            "tx 应该增加 10mm"
        assert gui.params["ty"].get() == initial_ty - 5.0, \
            "ty 应该减少 5mm"
        
        # Step 3: 设置参数
        gui._on_set_params()
        
        assert "成功" in gui.status_label.cget("text"), \
            "设置参数应该成功"
        
        # Step 4: 记录误差
        gui.ref_params["ref_x"].set(1000.0)
        gui.ref_params["ref_y"].set(500.0)
        gui._on_record_error()
        
        assert gui.record_count == 1, "应该记录 1 条误差"
        assert "成功" in gui.status_label.cget("text"), \
            "记录误差应该成功"
        
        # Step 5: 重置参数
        gui._on_reset()
        
        assert gui.params["tx"].get() == initial_tx, \
            "重置后 tx 应该恢复到初始值"
        assert gui.params["ty"].get() == initial_ty, \
            "重置后 ty 应该恢复到初始值"
        assert "重置" in gui.status_label.cget("text"), \
            "重置应该成功"
        
        # Step 6: 再次记录误差
        gui._on_record_error()
        
        assert gui.record_count == 2, "应该记录 2 条误差"
        
        # 清理
        gui.root.destroy()
        
        # 清理测试文件
        import os
        if os.path.exists("logs/test_gui_integration_workflow.json"):
            os.remove("logs/test_gui_integration_workflow.json")
    
    def test_gui_initialization_with_invalid_config(self):
        """
        测试使用无效配置初始化 GUI
        
        验证：
        - 多设备配置应该抛出 ValueError
        """
        # Arrange - 创建多设备配置
        mxid1 = "DEVICE_001"
        mxid2 = "DEVICE_002"
        role1 = DeviceRole.LEFT_CAMERA
        role2 = DeviceRole.RIGHT_CAMERA
        
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
        mock_decision_layer = create_mock_decision_layer()
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_gui_integration.json"
        )
        
        # Act & Assert - 应该抛出 ValueError
        with pytest.raises(ValueError) as exc_info:
            gui = CalibrationGUI(
                param_manager=param_manager,
                error_recorder=error_recorder
            )
        
        assert "期望单设备运行" in str(exc_info.value), \
            "错误消息应该说明期望单设备运行"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
