"""
端到端集成测试

测试完整的校准工作流程和主系统与校准工具的协同工作：
- 完整的校准工作流程
- 主系统和校准工具的协同工作
- 性能影响验证

**验证需求: 4.1, 4.2, 4.6**
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
import time
import json
from unittest.mock import Mock, MagicMock, patch
from threading import Thread
from copy import deepcopy

from oak_vision_system.core.dto.config_dto import (
    CoordinateTransformConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    DataProcessingConfigDTO
)
from oak_vision_system.modules.data_processing.transform_module import CoordinateTransfomer
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


def create_real_data_processor(config_manager):
    """创建真实的 DataProcessor（用于端到端测试）"""
    from oak_vision_system.modules.data_processing.data_processor import DataProcessor
    
    # 获取配置
    data_config = config_manager.get_data_processing_config()
    role_bindings = config_manager.get_active_role_binding_dtos()
    
    # 创建设备元数据
    device_metadata = {}
    for role, binding in role_bindings.items():
        device_metadata[binding.active_mxid] = Mock(
            mxid=binding.active_mxid,
            role=role
        )
    
    # 创建有效的 label_map（至少包含一个标签）
    label_map = ["durian", "person"]
    
    # 创建 DataProcessor
    processor = DataProcessor(
        config=data_config,
        device_metadata=device_metadata,
        bindings=role_bindings,
        label_map=label_map
    )
    
    return processor


def create_mock_decision_layer(target_coords=None):
    """创建模拟的 DecisionLayer"""
    mock_decision_layer = Mock()
    mock_decision_layer.get_target_coords_snapshot.return_value = target_coords
    return mock_decision_layer


# ==================== 端到端集成测试 ====================

class TestEndToEndCalibrationWorkflow:
    """端到端校准工作流程测试套件"""
    
    def test_complete_calibration_workflow_with_real_components(self):
        """
        测试完整的校准工作流程（使用真实组件）
        
        验证需求 4.1: WHEN 校准工具启动时 THEN 主系统的性能 SHALL 不受显著影响
        验证需求 4.2: WHEN 校准工具未启动时 THEN 系统 SHALL 正常运行，无任何功能缺失
        
        流程：
        1. 创建真实的 DataProcessor（模拟主系统）
        2. 创建校准工具组件
        3. 执行完整的校准流程：
           a. 初始化 GUI
           b. 调整参数
           c. 设置参数
           d. 验证坐标变换结果
           e. 记录误差数据
           f. 重置参数
        4. 验证所有组件协同工作
        """
        # Arrange
        test_mxid = "TEST_DEVICE_E2E"
        test_role = DeviceRole.LEFT_CAMERA
        
        initial_tx, initial_ty, initial_tz = 100.0, 50.0, 25.0
        initial_pitch, initial_yaw = 5.0, 10.0
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=initial_tx, ty=initial_ty, tz=initial_tz,
            pitch=initial_pitch, yaw=initial_yaw
        )
        
        # 创建真实的 DataProcessor
        data_processor = create_real_data_processor(mock_config_manager)
        
        # 创建模拟的 DecisionLayer
        target_coords = np.array([1005.0, 505.0, 2.0])
        mock_decision_layer = create_mock_decision_layer(target_coords=target_coords)
        
        # 创建校准工具组件
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_e2e_workflow.json"
        )
        
        # 创建 GUI
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # Step 1: 验证初始化
        assert gui.mxid == test_mxid, "mxid 应该正确"
        assert gui.params["tx"].get() == initial_tx, "初始 tx 应该正确"
        
        # Step 2: 调整参数
        new_tx, new_ty, new_tz = 200.0, 100.0, 50.0
        new_pitch, new_yaw = 10.0, 20.0
        
        gui.params["tx"].set(new_tx)
        gui.params["ty"].set(new_ty)
        gui.params["tz"].set(new_tz)
        gui.params["pitch"].set(new_pitch)
        gui.params["yaw"].set(new_yaw)
        
        # Step 3: 设置参数
        gui._on_set_params()
        
        assert "成功" in gui.status_label.cget("text"), \
            "设置参数应该成功"
        
        # Step 4: 验证坐标变换结果（使用真实的 CoordinateTransformer）
        # 创建测试坐标
        test_coords = np.array([[100.0, 200.0, 300.0, 1.0]])  # 齐次坐标
        
        # 使用 DataProcessor 的 CoordinateTransformer 进行变换
        transformed_coords = data_processor._transformer.transform_coordinates(
            mxid=test_mxid,
            coords_homogeneous=test_coords
        )
        
        # 验证变换结果不为空
        assert transformed_coords is not None, \
            "变换结果不应该为空"
        assert transformed_coords.shape == (1, 3), \
            "变换结果形状应该正确"
        
        # Step 5: 记录误差数据
        gui.ref_params["ref_x"].set(1000.0)
        gui.ref_params["ref_y"].set(500.0)
        gui._on_record_error()
        
        assert gui.record_count == 1, "应该记录 1 条误差"
        assert "成功" in gui.status_label.cget("text"), \
            "记录误差应该成功"
        
        # 验证误差数据文件
        error_log_path = Path("logs/test_e2e_workflow.json")
        assert error_log_path.exists(), "误差日志文件应该存在"
        
        with open(error_log_path, 'r', encoding='utf-8') as f:
            error_records = json.load(f)
        
        assert len(error_records) == 1, "应该有 1 条误差记录"
        
        record = error_records[0]
        assert "timestamp" in record, "记录应该包含时间戳"
        assert "reference_position" in record, "记录应该包含基准位置"
        assert "actual_position" in record, "记录应该包含实际位置"
        assert "error_vector" in record, "记录应该包含误差向量"
        assert "error_magnitude" in record, "记录应该包含误差大小"
        
        # Step 6: 重置参数
        gui._on_reset()
        
        assert gui.params["tx"].get() == initial_tx, \
            "重置后 tx 应该恢复到初始值"
        assert gui.params["ty"].get() == initial_ty, \
            "重置后 ty 应该恢复到初始值"
        assert "重置" in gui.status_label.cget("text"), \
            "重置应该成功"
        
        # Step 7: 再次验证坐标变换（使用重置后的参数）
        transformed_coords_after_reset = data_processor._transformer.transform_coordinates(
            mxid=test_mxid,
            coords_homogeneous=test_coords
        )
        
        assert transformed_coords_after_reset is not None, \
            "重置后变换结果不应该为空"
        
        # 清理
        gui.root.destroy()
        
        # 清理测试文件
        import os
        if os.path.exists("logs/test_e2e_workflow.json"):
            os.remove("logs/test_e2e_workflow.json")
    
    def test_system_runs_without_calibration_tool(self):
        """
        测试主系统在没有校准工具的情况下正常运行
        
        验证需求 4.2: WHEN 校准工具未启动时 THEN 系统 SHALL 正常运行，无任何功能缺失
        
        流程：
        1. 创建真实的 DataProcessor（不创建校准工具）
        2. 执行坐标变换
        3. 验证系统正常工作
        """
        # Arrange
        test_mxid = "TEST_DEVICE_NO_CALIB"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        
        # 创建真实的 DataProcessor（不创建校准工具）
        data_processor = create_real_data_processor(mock_config_manager)
        
        # Act - 执行坐标变换
        test_coords = np.array([[100.0, 200.0, 300.0, 1.0]])
        transformed_coords = data_processor._transformer.transform_coordinates(
            mxid=test_mxid,
            coords_homogeneous=test_coords
        )
        
        # Assert
        assert transformed_coords is not None, \
            "没有校准工具时，坐标变换应该正常工作"
        assert transformed_coords.shape == (1, 3), \
            "变换结果形状应该正确"
        
        # 验证 DataProcessor 的其他功能也正常
        assert data_processor._transformer is not None, \
            "CoordinateTransformer 应该存在"
        assert data_processor.decision_layer is not None, \
            "DecisionLayer 应该存在"


class TestSystemPerformanceImpact:
    """系统性能影响测试套件"""
    
    def test_calibration_tool_performance_impact(self):
        """
        测试校准工具对主系统性能的影响
        
        验证需求 4.1: WHEN 校准工具启动时 THEN 主系统的性能 SHALL 不受显著影响（性能损失<5%）
        
        流程：
        1. 测量无校准工具时的性能基线
        2. 启动校准工具
        3. 测量有校准工具时的性能
        4. 验证性能损失 < 5%
        """
        # Arrange
        test_mxid = "TEST_DEVICE_PERF"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        
        # 创建真实的 DataProcessor
        data_processor = create_real_data_processor(mock_config_manager)
        
        # 创建测试数据
        test_coords = np.array([[100.0, 200.0, 300.0, 1.0]] * 1000)  # 1000 个坐标点
        
        # Step 1: 测量无校准工具时的性能基线
        num_iterations = 100
        
        start_time = time.time()
        for _ in range(num_iterations):
            data_processor._transformer.transform_coordinates(
                mxid=test_mxid,
                coords_homogeneous=test_coords
            )
        baseline_time = time.time() - start_time
        baseline_avg = baseline_time / num_iterations
        
        # Step 2: 创建校准工具组件
        mock_decision_layer = create_mock_decision_layer()
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_perf.json"
        )
        
        # 创建 GUI（但不启动主循环）
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # Step 3: 测量有校准工具时的性能
        start_time = time.time()
        for _ in range(num_iterations):
            data_processor._transformer.transform_coordinates(
                mxid=test_mxid,
                coords_homogeneous=test_coords
            )
        with_tool_time = time.time() - start_time
        with_tool_avg = with_tool_time / num_iterations
        
        # Step 4: 计算性能损失
        performance_loss = ((with_tool_avg - baseline_avg) / baseline_avg) * 100
        
        # Assert
        print(f"\n性能测试结果:")
        print(f"  基线性能: {baseline_avg*1000:.3f} ms/次")
        print(f"  校准工具性能: {with_tool_avg*1000:.3f} ms/次")
        print(f"  性能损失: {performance_loss:.2f}%")
        
        assert performance_loss < 5.0, \
            f"性能损失应该 < 5%，实际: {performance_loss:.2f}%"
        
        # 清理
        gui.root.destroy()
        
        # 清理测试文件
        import os
        if os.path.exists("logs/test_perf.json"):
            os.remove("logs/test_perf.json")
    
    def test_parameter_update_latency(self):
        """
        测试参数更新延迟
        
        验证：参数更新延迟 < 1ms
        
        流程：
        1. 创建校准工具组件
        2. 测量参数更新时间
        3. 验证延迟 < 1ms
        """
        # Arrange
        test_mxid = "TEST_DEVICE_LATENCY"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        
        data_processor = create_real_data_processor(mock_config_manager)
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=data_processor
        )
        
        # Act - 测量参数更新时间
        num_updates = 100
        update_times = []
        
        for i in range(num_updates):
            new_tx = 100.0 + i
            
            start_time = time.time()
            success = param_manager.update_params(
                mxid=test_mxid,
                tx=new_tx, ty=50.0, tz=0.0,
                pitch=0.0, yaw=0.0
            )
            update_time = time.time() - start_time
            
            assert success, f"第 {i+1} 次参数更新应该成功"
            update_times.append(update_time)
        
        # Assert
        avg_update_time = np.mean(update_times)
        max_update_time = np.max(update_times)
        
        print(f"\n参数更新延迟测试结果:")
        print(f"  平均延迟: {avg_update_time*1000:.3f} ms")
        print(f"  最大延迟: {max_update_time*1000:.3f} ms")
        
        assert avg_update_time < 0.001, \
            f"平均参数更新延迟应该 < 1ms，实际: {avg_update_time*1000:.3f} ms"


class TestCalibrationToolExceptionHandling:
    """校准工具异常处理测试套件"""
    
    def test_gui_exception_does_not_affect_main_system(self):
        """
        测试 GUI 异常不影响主系统
        
        验证需求 4.6: WHEN 校准工具发生异常时 THEN 主系统 SHALL 继续正常运行
        
        流程：
        1. 创建主系统和校准工具
        2. 模拟 GUI 异常
        3. 验证主系统继续正常工作
        """
        # Arrange
        test_mxid = "TEST_DEVICE_EXCEPTION"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        
        data_processor = create_real_data_processor(mock_config_manager)
        mock_decision_layer = create_mock_decision_layer()
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=data_processor
        )
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_exception.json"
        )
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # Act - 模拟 GUI 异常（设置无效参数）
        gui.params["tx"].set("invalid_value")  # 设置非数字值
        
        # 尝试设置参数（应该捕获异常）
        gui._on_set_params()
        
        # 验证 GUI 显示错误
        assert "错误" in gui.status_label.cget("text") or \
               "失败" in gui.status_label.cget("text"), \
            "GUI 应该显示错误"
        
        # Assert - 验证主系统继续正常工作
        test_coords = np.array([[100.0, 200.0, 300.0, 1.0]])
        transformed_coords = data_processor._transformer.transform_coordinates(
            mxid=test_mxid,
            coords_homogeneous=test_coords
        )
        
        assert transformed_coords is not None, \
            "GUI 异常后，主系统应该继续正常工作"
        assert transformed_coords.shape == (1, 3), \
            "变换结果形状应该正确"
        
        # 清理
        gui.root.destroy()
        
        # 清理测试文件
        import os
        if os.path.exists("logs/test_exception.json"):
            os.remove("logs/test_exception.json")
    
    def test_error_recorder_file_write_failure(self):
        """
        测试误差记录器文件写入失败
        
        验证：文件写入失败不影响 GUI 继续运行
        
        流程：
        1. 创建误差记录器
        2. Mock 文件写入失败
        3. 尝试记录误差
        4. 验证 GUI 显示错误但继续运行
        """
        # Arrange
        test_mxid = "TEST_DEVICE_FILE_ERROR"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role
        )
        
        data_processor = create_real_data_processor(mock_config_manager)
        
        # 创建 DecisionLayer mock
        target_coords = np.array([1005.0, 505.0, 2.0])
        mock_decision_layer = create_mock_decision_layer(target_coords=target_coords)
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=data_processor
        )
        
        # 创建正常的误差记录器
        error_recorder = ErrorRecorder(
            decision_layer=mock_decision_layer,
            log_file_path="logs/test_file_error.json"
        )
        
        # Mock _append_to_json 方法使其抛出异常
        original_append = error_recorder._append_to_json
        def mock_append_to_json(data):
            raise OSError("模拟文件写入失败")
        
        error_recorder._append_to_json = mock_append_to_json
        
        gui = CalibrationGUI(
            param_manager=param_manager,
            error_recorder=error_recorder
        )
        
        # Act - 尝试记录误差
        gui.ref_params["ref_x"].set(1000.0)
        gui.ref_params["ref_y"].set(500.0)
        gui._on_record_error()
        
        # Assert - 验证 GUI 显示错误但继续运行
        assert "错误" in gui.status_label.cget("text") or \
               "失败" in gui.status_label.cget("text"), \
            f"GUI 应该显示错误，实际显示: {gui.status_label.cget('text')}"
        
        # 验证 GUI 仍然可以使用
        gui.params["tx"].set(200.0)
        gui._on_set_params()
        
        # 清理
        gui.root.destroy()
        
        # 清理测试文件
        import os
        if os.path.exists("logs/test_file_error.json"):
            os.remove("logs/test_file_error.json")


class TestMultiThreadedCalibration:
    """多线程校准测试套件"""
    
    def test_concurrent_parameter_updates(self):
        """
        测试并发参数更新
        
        验证：多个线程同时更新参数时，系统应该保持一致性
        
        流程：
        1. 创建校准工具组件
        2. 启动多个线程同时更新参数
        3. 验证所有更新都成功
        4. 验证最终状态一致
        """
        # Arrange
        test_mxid = "TEST_DEVICE_CONCURRENT"
        test_role = DeviceRole.LEFT_CAMERA
        
        mock_config_manager = create_mock_config_manager(
            mxid=test_mxid,
            role=test_role,
            tx=100.0, ty=50.0, tz=0.0,
            pitch=0.0, yaw=0.0
        )
        
        data_processor = create_real_data_processor(mock_config_manager)
        
        param_manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=data_processor
        )
        
        # Act - 启动多个线程同时更新参数
        num_threads = 10
        num_updates_per_thread = 10
        results = []
        
        def update_params(thread_id):
            thread_results = []
            for i in range(num_updates_per_thread):
                tx = 100.0 + thread_id * 10 + i
                success = param_manager.update_params(
                    mxid=test_mxid,
                    tx=tx, ty=50.0, tz=0.0,
                    pitch=0.0, yaw=0.0
                )
                thread_results.append(success)
            results.append(thread_results)
        
        threads = []
        for i in range(num_threads):
            thread = Thread(target=update_params, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Assert
        # 验证所有更新都成功
        for thread_results in results:
            assert all(thread_results), \
                "所有参数更新都应该成功"
        
        # 验证最终状态一致（能够正常进行坐标变换）
        test_coords = np.array([[100.0, 200.0, 300.0, 1.0]])
        transformed_coords = data_processor._transformer.transform_coordinates(
            mxid=test_mxid,
            coords_homogeneous=test_coords
        )
        
        assert transformed_coords is not None, \
            "并发更新后，坐标变换应该正常工作"
        assert transformed_coords.shape == (1, 3), \
            "变换结果形状应该正确"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
