"""
CoordinateTransformer 扩展功能单元测试

测试 CoordinateTransformer 的线程安全接口，包括：
- 矩阵更新的线程安全性
- 并发读写安全性

**验证需求: 8.2**
"""

import pytest
import numpy as np
from threading import Thread, Barrier, Event
from typing import Dict, List
import time

from oak_vision_system.modules.data_processing.transform_module import CoordinateTransfomer
from oak_vision_system.core.dto.config_dto import (
    CoordinateTransformConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO
)


# ==================== 测试辅助函数 ====================

def create_test_transformer(
    mxid: str,
    translation_x: float = 0.0,
    translation_y: float = 0.0,
    translation_z: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0
) -> CoordinateTransfomer:
    """
    创建用于测试的 CoordinateTransformer 实例
    
    Args:
        mxid: 设备ID
        translation_x, translation_y, translation_z: 平移参数（mm）
        pitch, yaw: 旋转参数（度）
    
    Returns:
        CoordinateTransfomer 实例
    """
    # 创建配置DTO
    calibration = CoordinateTransformConfigDTO(
        role=DeviceRole.LEFT_CAMERA,
        translation_x=translation_x,
        translation_y=translation_y,
        translation_z=translation_z,
        roll=0.0,
        pitch=pitch,
        yaw=yaw
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


def build_new_matrix_dict(
    mxid: str,
    translation_x: float = 0.0,
    translation_y: float = 0.0,
    translation_z: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0
) -> Dict[str, np.ndarray]:
    """
    构建新的变换矩阵字典
    
    Args:
        mxid: 设备ID
        translation_x, translation_y, translation_z: 平移参数（mm）
        pitch, yaw: 旋转参数（度）
    
    Returns:
        变换矩阵字典 {mxid: 4x4 matrix}
    """
    from oak_vision_system.modules.data_processing.trans_utils import (
        build_oak_to_xyz_homogeneous,
        build_translation_homogeneous,
        create_rotation_y_matrix,
        create_rotation_z_matrix
    )
    
    # 构建变换矩阵
    T_oak_to_xyz = build_oak_to_xyz_homogeneous()
    R_yaw = create_rotation_z_matrix(yaw)
    R_pitch = create_rotation_y_matrix(pitch)
    T_trans = build_translation_homogeneous(
        translation_x,
        translation_y,
        translation_z
    )
    
    T_total = (T_trans @ R_yaw @ R_pitch @ T_oak_to_xyz).astype(np.float32, copy=False)
    
    return {mxid: T_total}


# ==================== 单元测试 ====================

class TestCoordinateTransformerThreadSafety:
    """CoordinateTransformer 线程安全单元测试套件"""
    
    def test_update_matrices_basic(self):
        """测试基本的矩阵更新功能"""
        # Arrange
        mxid = "TEST_DEVICE_001"
        transformer = create_test_transformer(mxid, translation_x=100.0)
        
        # 获取初始矩阵
        initial_matrix = transformer.trans_matrices[mxid].copy()
        
        # Act - 更新矩阵
        new_matrices = build_new_matrix_dict(mxid, translation_x=200.0)
        success = transformer.update_matrices(new_matrices)
        
        # Assert
        assert success, "矩阵更新应该成功"
        
        # 验证矩阵已更新
        updated_matrix = transformer.trans_matrices[mxid]
        assert not np.allclose(updated_matrix, initial_matrix), "矩阵应该已更新"
        assert np.allclose(updated_matrix, new_matrices[mxid]), "更新后的矩阵应该与新矩阵一致"
    
    def test_update_matrices_with_invalid_data(self):
        """测试使用无效数据更新矩阵"""
        # Arrange
        mxid = "TEST_DEVICE_002"
        transformer = create_test_transformer(mxid)
        
        # Act - 尝试更新为无效矩阵（形状错误）
        invalid_matrices = {mxid: np.array([[1, 2], [3, 4]])}  # 2x2 矩阵
        
        # 注意：update_matrices 不验证矩阵内容，只是原子替换
        # 这里测试的是即使传入无效数据，也不会崩溃
        success = transformer.update_matrices(invalid_matrices)
        
        # Assert
        assert success, "即使数据无效，update_matrices 也应该成功（不验证内容）"
    
    def test_concurrent_reads_no_blocking(self):
        """
        测试并发读取不会相互阻塞
        
        **验证需求: 8.2**
        
        测试策略：
        1. 创建 CoordinateTransformer 实例
        2. 启动多个读线程同时读取矩阵
        3. 使用 Barrier 确保所有线程同时开始
        4. 验证所有读取都能快速完成（无死锁）
        """
        # Arrange
        mxid = "TEST_DEVICE_003"
        transformer = create_test_transformer(mxid)
        
        num_readers = 10
        barrier = Barrier(num_readers)
        read_times: List[float] = []
        read_errors: List[str] = []
        
        def read_matrix():
            """读取矩阵的线程函数"""
            try:
                # 等待所有线程就绪
                barrier.wait()
                
                # 记录开始时间
                start_time = time.time()
                
                # 读取矩阵
                with transformer._lock:
                    matrix = transformer.trans_matrices[mxid]
                
                # 记录结束时间
                end_time = time.time()
                read_times.append(end_time - start_time)
                
                # 验证矩阵
                assert matrix is not None
                assert matrix.shape == (4, 4)
            except Exception as e:
                read_errors.append(str(e))
        
        # Act - 启动多个读线程
        threads = []
        for _ in range(num_readers):
            thread = Thread(target=read_matrix)
            thread.start()
            threads.append(thread)
        
        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Assert
        assert len(read_errors) == 0, f"读取过程中不应该有错误: {read_errors}"
        assert len(read_times) == num_readers, "所有读线程都应该完成"
        
        # 验证读取时间都很短（无阻塞）
        max_read_time = max(read_times)
        assert max_read_time < 1.0, f"读取时间应该很短，但最大读取时间为 {max_read_time}s"
    
    def test_concurrent_read_during_write(self):
        """
        测试写操作期间的并发读取
        
        **验证需求: 8.2**
        
        测试策略：
        1. 创建 CoordinateTransformer 实例
        2. 启动多个读线程持续读取
        3. 在主线程中执行写操作
        4. 验证读线程能够正常完成（可能等待写锁）
        5. 验证读取到的矩阵都是有效的
        """
        # Arrange
        mxid = "TEST_DEVICE_004"
        transformer = create_test_transformer(mxid, translation_x=100.0)
        
        read_results: List[np.ndarray] = []
        read_errors: List[str] = []
        stop_event = Event()
        
        def read_matrix_continuously():
            """持续读取矩阵的线程函数"""
            try:
                while not stop_event.is_set():
                    with transformer._lock:
                        matrix = transformer.trans_matrices[mxid]
                    
                    # 记录矩阵副本
                    read_results.append(matrix.copy())
                    
                    # 验证矩阵形状
                    assert matrix.shape == (4, 4), f"矩阵形状应该是 (4, 4)，但得到 {matrix.shape}"
                    
                    # 短暂休眠
                    time.sleep(0.001)
            except Exception as e:
                read_errors.append(str(e))
        
        # Act - 启动读线程
        num_readers = 5
        reader_threads = []
        for _ in range(num_readers):
            thread = Thread(target=read_matrix_continuously)
            thread.start()
            reader_threads.append(thread)
        
        # 让读线程运行一段时间
        time.sleep(0.05)
        
        # 执行写操作
        new_matrices = build_new_matrix_dict(mxid, translation_x=200.0)
        success = transformer.update_matrices(new_matrices)
        
        # 继续让读线程运行
        time.sleep(0.05)
        
        # 停止读线程
        stop_event.set()
        for thread in reader_threads:
            thread.join(timeout=2.0)
        
        # Assert
        assert success, "矩阵更新应该成功"
        assert len(read_errors) == 0, f"读取过程中不应该有错误: {read_errors}"
        assert len(read_results) > 0, "应该至少读取到一些矩阵"
        
        # 验证所有读取到的矩阵都是有效的
        for matrix in read_results:
            assert matrix.shape == (4, 4), "所有读取到的矩阵形状都应该是 (4, 4)"
    
    def test_multiple_concurrent_writes(self):
        """
        测试多个并发写操作
        
        测试策略：
        1. 创建 CoordinateTransformer 实例
        2. 启动多个写线程同时更新矩阵
        3. 验证所有写操作都能成功完成
        4. 验证最终矩阵是有效的
        """
        # Arrange
        mxid = "TEST_DEVICE_005"
        transformer = create_test_transformer(mxid)
        
        num_writers = 5
        write_results: List[bool] = []
        write_errors: List[str] = []
        barrier = Barrier(num_writers)
        
        def write_matrix(tx_value: float):
            """写入矩阵的线程函数"""
            try:
                # 等待所有线程就绪
                barrier.wait()
                
                # 构建新矩阵
                new_matrices = build_new_matrix_dict(mxid, translation_x=tx_value)
                
                # 更新矩阵
                success = transformer.update_matrices(new_matrices)
                write_results.append(success)
            except Exception as e:
                write_errors.append(str(e))
        
        # Act - 启动多个写线程
        threads = []
        for i in range(num_writers):
            thread = Thread(target=write_matrix, args=(float(i * 100),))
            thread.start()
            threads.append(thread)
        
        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Assert
        assert len(write_errors) == 0, f"写入过程中不应该有错误: {write_errors}"
        assert len(write_results) == num_writers, "所有写线程都应该完成"
        assert all(write_results), "所有写操作都应该成功"
        
        # 验证最终矩阵是有效的
        final_matrix = transformer.trans_matrices[mxid]
        assert final_matrix.shape == (4, 4), "最终矩阵形状应该是 (4, 4)"
    
    def test_read_write_interleaved(self):
        """
        测试读写交替进行
        
        **验证需求: 8.2**
        
        测试策略：
        1. 创建 CoordinateTransformer 实例
        2. 交替执行读和写操作
        3. 验证所有操作都能正常完成
        4. 验证读取到的矩阵都是有效的
        """
        # Arrange
        mxid = "TEST_DEVICE_006"
        transformer = create_test_transformer(mxid)
        
        num_iterations = 10
        read_results: List[np.ndarray] = []
        
        # Act - 交替读写
        for i in range(num_iterations):
            # 写操作
            new_matrices = build_new_matrix_dict(mxid, translation_x=float(i * 10))
            success = transformer.update_matrices(new_matrices)
            assert success, f"第 {i} 次写操作应该成功"
            
            # 读操作
            with transformer._lock:
                matrix = transformer.trans_matrices[mxid]
            read_results.append(matrix.copy())
        
        # Assert
        assert len(read_results) == num_iterations, "应该完成所有读操作"
        
        # 验证所有读取到的矩阵都是有效的
        for i, matrix in enumerate(read_results):
            assert matrix.shape == (4, 4), f"第 {i} 次读取的矩阵形状应该是 (4, 4)"
    
    def test_transform_coordinates_during_update(self):
        """
        测试在矩阵更新期间调用 transform_coordinates
        
        测试策略：
        1. 创建 CoordinateTransformer 实例
        2. 启动线程持续调用 transform_coordinates
        3. 在主线程中更新矩阵
        4. 验证坐标变换能够正常完成
        """
        # Arrange
        mxid = "TEST_DEVICE_007"
        transformer = create_test_transformer(mxid, translation_x=100.0)
        
        # 测试坐标（齐次坐标）
        test_coords = np.array([
            [1000.0, 500.0, 200.0, 1.0],
            [2000.0, 1000.0, 300.0, 1.0]
        ], dtype=np.float32)
        
        transform_results: List[np.ndarray] = []
        transform_errors: List[str] = []
        stop_event = Event()
        
        def transform_continuously():
            """持续进行坐标变换的线程函数"""
            try:
                while not stop_event.is_set():
                    result = transformer.transform_coordinates(mxid, test_coords)
                    transform_results.append(result.copy())
                    
                    # 验证结果形状
                    assert result.shape == (2, 3), f"结果形状应该是 (2, 3)，但得到 {result.shape}"
                    
                    time.sleep(0.001)
            except Exception as e:
                transform_errors.append(str(e))
        
        # Act - 启动变换线程
        num_transformers = 3
        transformer_threads = []
        for _ in range(num_transformers):
            thread = Thread(target=transform_continuously)
            thread.start()
            transformer_threads.append(thread)
        
        # 让变换线程运行一段时间
        time.sleep(0.05)
        
        # 更新矩阵
        new_matrices = build_new_matrix_dict(mxid, translation_x=200.0)
        success = transformer.update_matrices(new_matrices)
        
        # 继续让变换线程运行
        time.sleep(0.05)
        
        # 停止变换线程
        stop_event.set()
        for thread in transformer_threads:
            thread.join(timeout=2.0)
        
        # Assert
        assert success, "矩阵更新应该成功"
        assert len(transform_errors) == 0, f"变换过程中不应该有错误: {transform_errors}"
        assert len(transform_results) > 0, "应该至少完成一些坐标变换"
        
        # 验证所有变换结果都是有效的
        for result in transform_results:
            assert result.shape == (2, 3), "所有变换结果形状都应该是 (2, 3)"
            assert not np.any(np.isnan(result)), "变换结果不应该包含 NaN"
            assert not np.any(np.isinf(result)), "变换结果不应该包含 Inf"


class TestCoordinateTransformerUpdateMatrices:
    """CoordinateTransformer update_matrices 方法单元测试"""
    
    def test_update_matrices_returns_true_on_success(self):
        """测试成功更新时返回 True"""
        # Arrange
        mxid = "TEST_DEVICE_008"
        transformer = create_test_transformer(mxid)
        new_matrices = build_new_matrix_dict(mxid, translation_x=100.0)
        
        # Act
        result = transformer.update_matrices(new_matrices)
        
        # Assert
        assert result is True, "成功更新应该返回 True"
    
    def test_update_matrices_replaces_entire_dict(self):
        """测试 update_matrices 替换整个字典"""
        # Arrange
        mxid1 = "TEST_DEVICE_009"
        mxid2 = "TEST_DEVICE_010"
        
        # 创建包含两个设备的变换器
        calibration1 = CoordinateTransformConfigDTO(
            role=DeviceRole.LEFT_CAMERA,
            translation_x=100.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        calibration2 = CoordinateTransformConfigDTO(
            role=DeviceRole.RIGHT_CAMERA,
            translation_x=200.0,
            translation_y=0.0,
            translation_z=0.0,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
        
        binding1 = DeviceRoleBindingDTO(
            role=DeviceRole.LEFT_CAMERA,
            historical_mxids=[mxid1],
            active_mxid=mxid1,
            last_active_mxid=mxid1
        )
        binding2 = DeviceRoleBindingDTO(
            role=DeviceRole.RIGHT_CAMERA,
            historical_mxids=[mxid2],
            active_mxid=mxid2,
            last_active_mxid=mxid2
        )
        
        calibrations = {
            DeviceRole.LEFT_CAMERA: calibration1,
            DeviceRole.RIGHT_CAMERA: calibration2
        }
        bindings = {
            DeviceRole.LEFT_CAMERA: binding1,
            DeviceRole.RIGHT_CAMERA: binding2
        }
        
        transformer = CoordinateTransfomer(calibrations, bindings)
        
        # 保存初始矩阵
        initial_matrix1 = transformer.trans_matrices[mxid1].copy()
        initial_matrix2 = transformer.trans_matrices[mxid2].copy()
        
        # Act - 只更新 mxid1 的矩阵
        new_matrix1 = build_new_matrix_dict(mxid1, translation_x=300.0)
        new_matrices = {
            mxid1: new_matrix1[mxid1],
            mxid2: initial_matrix2  # 保持 mxid2 不变
        }
        
        success = transformer.update_matrices(new_matrices)
        
        # Assert
        assert success, "更新应该成功"
        
        # 验证 mxid1 的矩阵已更新
        assert not np.allclose(transformer.trans_matrices[mxid1], initial_matrix1), \
            "mxid1 的矩阵应该已更新"
        assert np.allclose(transformer.trans_matrices[mxid1], new_matrix1[mxid1]), \
            "mxid1 的矩阵应该等于新矩阵"
        
        # 验证 mxid2 的矩阵保持不变
        assert np.allclose(transformer.trans_matrices[mxid2], initial_matrix2), \
            "mxid2 的矩阵应该保持不变"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
