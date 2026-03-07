"""
CoordinateTransformer 扩展功能属性测试

使用属性测试（Property-Based Testing）验证坐标变换矩阵原子替换的正确性。

Property 1: 变换矩阵原子替换一致性
*For any* 设备mxid和任意时刻，读取该设备的变换矩阵应该得到一个完整且一致的4x4矩阵，
不会出现部分更新的中间状态

**Validates: Requirements 7.3, 7.6**
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings
from threading import Thread, Event
from typing import Dict
import time

from oak_vision_system.modules.data_processing.transform_module import CoordinateTransfomer
from oak_vision_system.core.dto.config_dto import (
    CoordinateTransformConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO
)


# ==================== 测试策略生成器 ====================

@st.composite
def valid_transform_params(draw):
    """生成有效的坐标变换参数"""
    return {
        'translation_x': draw(st.floats(min_value=-2000.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        'translation_y': draw(st.floats(min_value=-2000.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        'translation_z': draw(st.floats(min_value=-2000.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        'roll': draw(st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)),
        'pitch': draw(st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)),
        'yaw': draw(st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False))
    }


@st.composite
def mxid_strategy(draw):
    """生成有效的设备mxid"""
    # 生成类似真实mxid的字符串（16进制字符）
    return draw(st.text(
        alphabet='0123456789ABCDEF',
        min_size=16,
        max_size=16
    ))


# ==================== 辅助函数 ====================

def create_test_transformer(mxid: str, params: Dict) -> CoordinateTransfomer:
    """
    创建用于测试的 CoordinateTransformer 实例
    
    Args:
        mxid: 设备ID
        params: 变换参数字典
    
    Returns:
        CoordinateTransfomer 实例
    """
    # 创建配置DTO
    calibration = CoordinateTransformConfigDTO(
        role=DeviceRole.LEFT_CAMERA,
        translation_x=params['translation_x'],
        translation_y=params['translation_y'],
        translation_z=params['translation_z'],
        roll=params['roll'],
        pitch=params['pitch'],
        yaw=params['yaw']
    )
    
    # 创建绑定DTO
    binding = DeviceRoleBindingDTO(
        role=DeviceRole.LEFT_CAMERA,
        historical_mxids=[mxid],
        active_mxid=mxid,
        last_active_mxid=mxid
    )
    
    # 创建变换器
    calibrations = {DeviceRole.LEFT_CAMERA: calibration}
    bindings = {DeviceRole.LEFT_CAMERA: binding}
    
    return CoordinateTransfomer(calibrations, bindings)


def build_new_matrix(transformer: CoordinateTransfomer, mxid: str, params: Dict) -> Dict[str, np.ndarray]:
    """
    构建新的变换矩阵字典（用于更新）
    
    Args:
        transformer: CoordinateTransformer 实例
        mxid: 设备ID
        params: 新的变换参数
    
    Returns:
        新的变换矩阵字典
    """
    from oak_vision_system.modules.data_processing.trans_utils import (
        build_oak_to_xyz_homogeneous,
        build_translation_homogeneous,
        create_rotation_y_matrix,
        create_rotation_z_matrix
    )
    
    # 构建变换矩阵（与 CoordinateTransfomer._create_trans_matrix 相同的流程）
    T_oak_to_xyz = build_oak_to_xyz_homogeneous()
    R_yaw = create_rotation_z_matrix(params['yaw'])
    R_pitch = create_rotation_y_matrix(params['pitch'])
    T_trans = build_translation_homogeneous(
        params['translation_x'],
        params['translation_y'],
        params['translation_z']
    )
    
    T_total = (T_trans @ R_yaw @ R_pitch @ T_oak_to_xyz).astype(np.float32, copy=False)
    
    # 返回新的矩阵字典
    return {mxid: T_total}


def is_valid_transform_matrix(matrix: np.ndarray) -> bool:
    """
    验证矩阵是否是有效的4x4齐次变换矩阵
    
    注意：此项目使用特殊的左乘体系，平移向量在第4行（索引3）的前3列，
    最后一行的格式为 [-tx, -ty, -tz, 1]，而不是标准的 [0, 0, 0, 1]
    
    Args:
        matrix: 待验证的矩阵
    
    Returns:
        bool: 如果是有效的变换矩阵返回True
    """
    if matrix is None:
        return False
    
    # 检查形状
    if matrix.shape != (4, 4):
        return False
    
    # 检查最后一行的最后一个元素是否为 1
    # 注意：前3个元素是平移向量的负值，可以是任意值
    if not np.isclose(matrix[3, 3], 1.0, rtol=1e-5, atol=1e-5):
        return False
    
    # 检查是否包含NaN或Inf
    if np.any(np.isnan(matrix)) or np.any(np.isinf(matrix)):
        return False
    
    return True


# ==================== 属性测试 ====================

class TestCoordinateTransformerAtomicReplacement:
    """CoordinateTransformer 原子替换属性测试套件"""
    
    @given(
        mxid=mxid_strategy(),
        initial_params=valid_transform_params(),
        updated_params=valid_transform_params()
    )
    @settings(max_examples=100, deadline=None)
    def test_atomic_replacement_consistency(self, mxid, initial_params, updated_params):
        """
        **Property 1: 变换矩阵原子替换一致性**
        
        *For any* 设备mxid和任意时刻，读取该设备的变换矩阵应该得到一个完整且一致的4x4矩阵，
        不会出现部分更新的中间状态
        
        **Validates: Requirements 7.3, 7.6**
        
        测试策略：
        1. 创建 CoordinateTransformer 实例并初始化
        2. 启动多个并发读线程持续读取矩阵
        3. 在主线程中更新变换矩阵
        4. 验证所有读取到的矩阵都是完整且一致的4x4矩阵
        5. 验证不会出现部分更新的中间状态
        
        Args:
            mxid: 设备ID
            initial_params: 初始变换参数
            updated_params: 更新后的变换参数
        """
        # 1. 创建变换器
        transformer = create_test_transformer(mxid, initial_params)
        
        # 2. 用于记录读取结果的列表（线程安全）
        read_results = []
        read_errors = []
        stop_event = Event()
        
        def read_matrix_continuously():
            """持续读取矩阵的线程函数"""
            try:
                while not stop_event.is_set():
                    # 读取矩阵
                    with transformer._lock:
                        matrix = transformer.trans_matrices.get(mxid)
                    
                    # 验证矩阵
                    if matrix is not None:
                        # 记录矩阵的副本
                        matrix_copy = matrix.copy()
                        read_results.append(matrix_copy)
                        
                        # 立即验证矩阵的完整性
                        if not is_valid_transform_matrix(matrix_copy):
                            read_errors.append(f"Invalid matrix shape or content: {matrix_copy.shape}")
                    
                    # 短暂休眠，让出CPU
                    time.sleep(0.0001)
            except Exception as e:
                read_errors.append(f"Read thread exception: {e}")
        
        # 3. 启动多个并发读线程
        num_readers = 5
        reader_threads = []
        for _ in range(num_readers):
            thread = Thread(target=read_matrix_continuously)
            thread.start()
            reader_threads.append(thread)
        
        # 4. 让读线程运行一小段时间
        time.sleep(0.01)
        
        # 5. 更新变换矩阵
        new_matrices = build_new_matrix(transformer, mxid, updated_params)
        success = transformer.update_matrices(new_matrices)
        
        # 6. 继续让读线程运行一小段时间
        time.sleep(0.01)
        
        # 7. 停止所有读线程
        stop_event.set()
        for thread in reader_threads:
            thread.join(timeout=1.0)
        
        # 8. 验证结果
        assert success, "矩阵更新应该成功"
        assert len(read_errors) == 0, f"读取过程中不应该有错误: {read_errors}"
        assert len(read_results) > 0, "应该至少读取到一些矩阵"
        
        # 9. 验证所有读取到的矩阵都是有效的4x4变换矩阵
        for i, matrix in enumerate(read_results):
            assert is_valid_transform_matrix(matrix), \
                f"第{i}次读取的矩阵应该是有效的4x4变换矩阵，但得到形状: {matrix.shape}"
        
        # 10. 验证最终矩阵是更新后的矩阵
        final_matrix = transformer.trans_matrices[mxid]
        assert is_valid_transform_matrix(final_matrix), "最终矩阵应该是有效的4x4变换矩阵"
        assert np.allclose(final_matrix, new_matrices[mxid], rtol=1e-5, atol=1e-5), \
            "最终矩阵应该等于更新后的矩阵"
    
    @given(
        mxid=mxid_strategy(),
        params=valid_transform_params()
    )
    @settings(max_examples=100, deadline=None)
    def test_matrix_always_complete_during_read(self, mxid, params):
        """
        **Property 1 (简化版): 矩阵读取时总是完整的**
        
        *For any* 设备mxid，在任意时刻读取的矩阵都应该是完整的4x4矩阵
        
        **Validates: Requirements 7.3, 7.6**
        
        测试策略：
        1. 创建 CoordinateTransformer 实例
        2. 直接读取矩阵
        3. 验证矩阵是完整且一致的4x4矩阵
        
        Args:
            mxid: 设备ID
            params: 变换参数
        """
        # 1. 创建变换器
        transformer = create_test_transformer(mxid, params)
        
        # 2. 读取矩阵
        with transformer._lock:
            matrix = transformer.trans_matrices.get(mxid)
        
        # 3. 验证矩阵
        assert matrix is not None, "矩阵不应该为None"
        assert is_valid_transform_matrix(matrix), \
            f"矩阵应该是有效的4x4变换矩阵，但得到形状: {matrix.shape}"
        
        # 4. 验证最后一行的最后一个元素是1（左乘体系）
        assert np.isclose(matrix[3, 3], 1.0, rtol=1e-5, atol=1e-5), \
            f"矩阵最后一行的最后一个元素应该是 1，但得到: {matrix[3, 3]}"
    
    @given(
        mxid=mxid_strategy(),
        initial_params=valid_transform_params(),
        update_sequence=st.lists(valid_transform_params(), min_size=1, max_size=5)
    )
    @settings(max_examples=50, deadline=None)
    def test_multiple_updates_maintain_consistency(self, mxid, initial_params, update_sequence):
        """
        **Property 1 (扩展): 多次更新后矩阵仍保持一致性**
        
        *For any* 设备mxid和任意更新序列，每次更新后矩阵都应该保持完整且一致
        
        **Validates: Requirements 7.3, 7.6**
        
        测试策略：
        1. 创建 CoordinateTransformer 实例
        2. 执行多次矩阵更新
        3. 每次更新后验证矩阵的完整性和一致性
        
        Args:
            mxid: 设备ID
            initial_params: 初始变换参数
            update_sequence: 更新参数序列
        """
        # 1. 创建变换器
        transformer = create_test_transformer(mxid, initial_params)
        
        # 2. 执行多次更新
        for i, params in enumerate(update_sequence):
            # 构建新矩阵
            new_matrices = build_new_matrix(transformer, mxid, params)
            
            # 更新矩阵
            success = transformer.update_matrices(new_matrices)
            assert success, f"第{i}次更新应该成功"
            
            # 验证更新后的矩阵
            current_matrix = transformer.trans_matrices[mxid]
            assert is_valid_transform_matrix(current_matrix), \
                f"第{i}次更新后的矩阵应该是有效的4x4变换矩阵"
            
            # 验证矩阵内容与预期一致
            assert np.allclose(current_matrix, new_matrices[mxid], rtol=1e-5, atol=1e-5), \
                f"第{i}次更新后的矩阵应该等于新矩阵"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
