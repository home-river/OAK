"""
TransformParamManager 基本功能验证脚本

这个脚本用于验证 TransformParamManager 的基本功能是否正常工作。
"""

import sys
from pathlib import Path
import os

# 添加项目根目录到 Python 路径
# 获取当前文件的绝对路径
# tools/calibration_tools/test/test_transform_param_manager_basic.py
# parent: test -> calibration_tools -> tools -> 项目根目录 (需要 3 个 parent)
current_file = Path(__file__).resolve()
test_dir = current_file.parent  # test
calibration_tools_dir = test_dir.parent  # calibration_tools
tools_dir = calibration_tools_dir.parent  # tools
project_root = tools_dir.parent  # 项目根目录

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
from unittest.mock import Mock, MagicMock
from oak_vision_system.core.dto.config_dto import (
    CoordinateTransformConfigDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
    DataProcessingConfigDTO
)
from tools.calibration_tools.core.transform_param_manager import TransformParamManager


def test_basic_functionality():
    """测试基本功能"""
    print("=" * 60)
    print("测试 TransformParamManager 基本功能")
    print("=" * 60)
    
    # 1. 创建模拟对象
    print("\n1. 创建模拟对象...")
    
    # 模拟 ConfigManager
    mock_config_manager = Mock()
    
    # 创建测试用的角色绑定
    test_mxid = "14442C10D13F7FD000"
    test_role = DeviceRole.LEFT_CAMERA
    
    mock_binding = DeviceRoleBindingDTO(
        role=test_role,
        active_mxid=test_mxid,
        historical_mxids=[test_mxid]
    )

    
    # 创建测试用的坐标变换配置
    test_transform_config = CoordinateTransformConfigDTO(
        role=test_role,
        translation_x=100.0,
        translation_y=50.0,
        translation_z=0.0,
        roll=0.0,
        pitch=0.0,
        yaw=0.0
    )
    
    # 创建数据处理配置
    mock_data_config = DataProcessingConfigDTO(
        coordinate_transforms={test_role: test_transform_config}
    )
    
    # 配置 mock 返回值
    mock_config_manager.get_active_role_binding_dtos.return_value = {
        test_role: mock_binding
    }
    mock_config_manager.get_data_processing_config.return_value = mock_data_config
    
    # 模拟 DataProcessor
    mock_data_processor = Mock()
    mock_data_processor.update_transform_matrices.return_value = True
    
    print("✓ 模拟对象创建完成")
    
    # 2. 初始化 TransformParamManager
    print("\n2. 初始化 TransformParamManager...")
    try:
        manager = TransformParamManager(
            config_manager=mock_config_manager,
            data_processor=mock_data_processor
        )
        print("✓ TransformParamManager 初始化成功")
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        return False
    
    # 3. 测试获取参数快照
    print("\n3. 测试获取参数快照...")
    params = manager.get_params_snapshot(test_mxid)
    if params:
        print(f"✓ 参数快照获取成功:")
        print(f"  - tx: {params['tx']}")
        print(f"  - ty: {params['ty']}")
        print(f"  - tz: {params['tz']}")
        print(f"  - pitch: {params['pitch']}")
        print(f"  - yaw: {params['yaw']}")
    else:
        print("✗ 参数快照获取失败")
        return False
    
    # 4. 测试更新参数
    print("\n4. 测试更新参数...")
    success = manager.update_params(
        mxid=test_mxid,
        tx=150.0,
        ty=75.0,
        tz=10.0,
        pitch=5.0,
        yaw=10.0
    )
    if success:
        print("✓ 参数更新成功")
        # 验证 DataProcessor 的 update_transform_matrices 被调用
        if mock_data_processor.update_transform_matrices.called:
            print("✓ DataProcessor.update_transform_matrices 已被调用")
        else:
            print("✗ DataProcessor.update_transform_matrices 未被调用")
            return False
    else:
        print("✗ 参数更新失败")
        return False
    
    # 5. 测试重置为默认值
    print("\n5. 测试重置为默认值...")
    success = manager.reset_to_default(test_mxid)
    if success:
        print("✓ 重置为默认值成功")
    else:
        print("✗ 重置为默认值失败")
        return False
    
    # 6. 测试获取当前 mxid（单设备模式）
    print("\n6. 测试获取当前 mxid...")
    try:
        current_mxid = manager.get_current_mxid()
        if current_mxid == test_mxid:
            print(f"✓ 当前 mxid 获取成功: {current_mxid}")
        else:
            print(f"✗ mxid 不匹配: 期望 {test_mxid}, 实际 {current_mxid}")
            return False
    except Exception as e:
        print(f"✗ 获取 mxid 失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
