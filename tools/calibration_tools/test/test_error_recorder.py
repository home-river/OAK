"""
ErrorRecorder 单元测试
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pytest

from tools.calibration_tools.core.error_recorder import ErrorRecorder


class TestErrorRecorder:
    """ErrorRecorder 单元测试类"""
    
    def test_init(self):
        """测试初始化"""
        mock_decision_layer = Mock()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_errors.json"
            recorder = ErrorRecorder(mock_decision_layer, str(log_path))
            
            assert recorder.decision_layer == mock_decision_layer
            assert recorder.log_file_path == log_path
            assert recorder.record_count == 0
            assert log_path.parent.exists()
    
    def test_record_error_success(self):
        """测试成功记录误差"""
        mock_decision_layer = Mock()
        # Mock 返回目标坐标
        mock_decision_layer.get_target_coords_snapshot.return_value = \
            np.array([1005.0, 502.0, 3.0])
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_errors.json"
            recorder = ErrorRecorder(mock_decision_layer, str(log_path))
            
            # 记录误差
            success = recorder.record_error(1000.0, 500.0, "durian")
            
            assert success is True
            assert recorder.record_count == 1
            
            # 验证文件内容
            with open(log_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            assert len(records) == 1
            record = records[0]
            
            # 验证基准位置
            assert record["reference_position"]["x"] == 1000.0
            assert record["reference_position"]["y"] == 500.0
            assert record["reference_position"]["z"] == 0.0
            
            # 验证实际位置
            assert record["actual_position"]["x"] == 1005.0
            assert record["actual_position"]["y"] == 502.0
            assert record["actual_position"]["z"] == 3.0
            
            # 验证误差向量
            assert record["error_vector"]["dx"] == 5.0
            assert record["error_vector"]["dy"] == 2.0
            assert record["error_vector"]["dz"] == 3.0
            
            # 验证误差大小
            expected_magnitude = np.sqrt(5.0**2 + 2.0**2 + 3.0**2)
            assert abs(record["error_magnitude"] - expected_magnitude) < 0.01
    
    def test_record_error_no_target(self):
        """测试无目标时的处理"""
        mock_decision_layer = Mock()
        # Mock 返回 None（无目标）
        mock_decision_layer.get_target_coords_snapshot.return_value = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_errors.json"
            recorder = ErrorRecorder(mock_decision_layer, str(log_path))
            
            # 记录误差
            success = recorder.record_error(1000.0, 500.0)
            
            assert success is False
            assert recorder.record_count == 0
            
            # 验证文件未创建或为空
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                assert len(records) == 0
    
    def test_append_mode(self):
        """测试追加模式不覆盖历史"""
        mock_decision_layer = Mock()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_errors.json"
            recorder = ErrorRecorder(mock_decision_layer, str(log_path))
            
            # 记录多次误差
            for i in range(3):
                mock_decision_layer.get_target_coords_snapshot.return_value = \
                    np.array([1000.0 + i, 500.0 + i, float(i)])
                recorder.record_error(1000.0, 500.0)
            
            # 验证所有记录都存在
            with open(log_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            assert len(records) == 3
            assert recorder.record_count == 3
            
            # 验证每条记录的实际位置不同
            for i, record in enumerate(records):
                assert record["actual_position"]["x"] == 1000.0 + i
                assert record["actual_position"]["y"] == 500.0 + i
                assert record["actual_position"]["z"] == float(i)
    
    def test_get_statistics_empty(self):
        """测试空文件的统计信息"""
        mock_decision_layer = Mock()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_errors.json"
            recorder = ErrorRecorder(mock_decision_layer, str(log_path))
            
            stats = recorder.get_statistics()
            
            assert stats["record_count"] == 0
    
    def test_get_statistics(self):
        """测试统计信息计算"""
        mock_decision_layer = Mock()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_errors.json"
            recorder = ErrorRecorder(mock_decision_layer, str(log_path))
            
            # 记录多次误差，误差大小分别为 5, 10, 15
            test_data = [
                (1000.0, 500.0, 1005.0, 500.0, 0.0),  # 误差 5
                (1000.0, 500.0, 1010.0, 500.0, 0.0),  # 误差 10
                (1000.0, 500.0, 1015.0, 500.0, 0.0),  # 误差 15
            ]
            
            for ref_x, ref_y, actual_x, actual_y, actual_z in test_data:
                mock_decision_layer.get_target_coords_snapshot.return_value = \
                    np.array([actual_x, actual_y, actual_z])
                recorder.record_error(ref_x, ref_y)
            
            # 获取统计信息
            stats = recorder.get_statistics()
            
            assert stats["record_count"] == 3
            assert abs(stats["mean_error"] - 10.0) < 0.01
            assert abs(stats["min_error"] - 5.0) < 0.01
            assert abs(stats["max_error"] - 15.0) < 0.01
            # 标准差 = sqrt(((5-10)^2 + (10-10)^2 + (15-10)^2) / 3) = sqrt(50/3) ≈ 4.08
            assert abs(stats["std_error"] - 4.08) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
