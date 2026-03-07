"""
ErrorRecorder 属性测试

验证误差计算的正确性属性
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pytest
from hypothesis import given, strategies as st, settings

from tools.calibration_tools.core.error_recorder import ErrorRecorder


class TestErrorRecorderProperty:
    """ErrorRecorder 属性测试类"""
    
    @given(
        ref_x=st.floats(
            min_value=-2000.0,
            max_value=2000.0,
            allow_nan=False,
            allow_infinity=False
        ),
        ref_y=st.floats(
            min_value=-2000.0,
            max_value=2000.0,
            allow_nan=False,
            allow_infinity=False
        ),
        actual_x=st.floats(
            min_value=-2000.0,
            max_value=2000.0,
            allow_nan=False,
            allow_infinity=False
        ),
        actual_y=st.floats(
            min_value=-2000.0,
            max_value=2000.0,
            allow_nan=False,
            allow_infinity=False
        ),
        actual_z=st.floats(
            min_value=-100.0,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_error_calculation_correctness(
        self,
        ref_x: float,
        ref_y: float,
        actual_x: float,
        actual_y: float,
        actual_z: float
    ):
        """
        属性测试：误差计算正确性
        
        Feature: calibration-tool-integration, Property 4: 误差计算正确性
        
        验证：对于任意基准位置和实际位置，
        计算的误差向量应该等于（实际位置 - 基准位置），
        且误差大小应该等于误差向量的欧几里得范数
        
        **验证: 需求 3.4**
        """
        # 创建 Mock DecisionLayer
        mock_decision_layer = Mock()
        
        # 使用临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_errors.json"
            recorder = ErrorRecorder(mock_decision_layer, str(log_path))
            
            # Mock DecisionLayer 返回实际位置
            mock_decision_layer.get_target_coords_snapshot.return_value = \
                np.array([actual_x, actual_y, actual_z])
            
            # 记录误差（传入基准位置）
            success = recorder.record_error(ref_x, ref_y)
            
            # 验证记录成功
            assert success is True
            
            # 读取记录
            with open(log_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            assert len(records) == 1
            last_record = records[0]
            
            # 验证基准位置
            assert np.isclose(last_record["reference_position"]["x"], ref_x)
            assert np.isclose(last_record["reference_position"]["y"], ref_y)
            assert np.isclose(last_record["reference_position"]["z"], 0.0)
            
            # 验证实际位置
            assert np.isclose(last_record["actual_position"]["x"], actual_x)
            assert np.isclose(last_record["actual_position"]["y"], actual_y)
            assert np.isclose(last_record["actual_position"]["z"], actual_z)
            
            # 验证误差向量 = 实际位置 - 基准位置
            expected_dx = actual_x - ref_x
            expected_dy = actual_y - ref_y
            expected_dz = actual_z - 0.0
            
            assert np.isclose(
                last_record["error_vector"]["dx"],
                expected_dx,
                rtol=1e-5,
                atol=1e-8
            )
            assert np.isclose(
                last_record["error_vector"]["dy"],
                expected_dy,
                rtol=1e-5,
                atol=1e-8
            )
            assert np.isclose(
                last_record["error_vector"]["dz"],
                expected_dz,
                rtol=1e-5,
                atol=1e-8
            )
            
            # 验证误差大小 = 误差向量的欧几里得范数
            expected_magnitude = np.sqrt(
                expected_dx**2 + expected_dy**2 + expected_dz**2
            )
            assert np.isclose(
                last_record["error_magnitude"],
                expected_magnitude,
                rtol=1e-5,
                atol=1e-8
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
