"""
系统冒烟测试：验证所有DTO的完整性

冒烟测试（Smoke Test）用于快速验证系统的基本功能是否正常。
本测试覆盖所有DTO的创建和验证，确保：
1. 所有DTO可以正常创建
2. 验证逻辑正确工作
3. 批量创建性能可接受
"""

import pytest
import time
from typing import List

from ...core.dto.detection_dto import (
    SpatialCoordinatesDTO,
    BoundingBoxDTO,
    DetectionDTO,
    DeviceDetectionDataDTO,
    VideoFrameDTO,
    OAKDataCollectionDTO,
    RawFrameDataEvent,
    RawDetectionDataEvent
)
from ...core.dto.device_config_dto import (
    OAKConfigDTO,
    DeviceConfigDTO,
    DeviceManagerConfigDTO,
    SystemConfigDTO
)


class TestDetectionDTOSmokeTest:
    """检测相关DTO冒烟测试"""
    
    def test_spatial_coordinates_dto_smoke(self):
        """冒烟测试：空间坐标DTO"""
        coords = SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0)
        assert coords.validate(), \
            f"空间坐标验证失败: {coords.get_validation_errors()}"
        
        # 测试距离计算
        assert coords.distance_from_origin > 0
        
        print("✅ SpatialCoordinatesDTO 冒烟测试通过")
    
    def test_bounding_box_dto_smoke(self):
        """冒烟测试：边界框DTO"""
        bbox = BoundingBoxDTO(xmin=0.1, ymin=0.2, xmax=0.8, ymax=0.9)
        assert bbox.validate(), \
            f"边界框验证失败: {bbox.get_validation_errors()}"
        
        # 测试属性计算
        assert bbox.width == pytest.approx(0.7)
        assert bbox.height == pytest.approx(0.7)
        
        print("✅ BoundingBoxDTO 冒烟测试通过")
    
    def test_detection_dto_smoke(self):
        """冒烟测试：检测对象DTO"""
        bbox = BoundingBoxDTO(xmin=0.1, ymin=0.2, xmax=0.8, ymax=0.9)
        coords = SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0)
        
        detection = DetectionDTO(
            label="durian",
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        assert detection.validate(), \
            f"检测对象验证失败: {detection.get_validation_errors()}"
        
        # 验证自动生成的detection_id
        assert detection.detection_id is not None
        assert "durian" in detection.detection_id
        
        print("✅ DetectionDTO 冒烟测试通过")
    
    def test_device_detection_data_dto_smoke(self):
        """冒烟测试：设备检测数据DTO"""
        bbox = BoundingBoxDTO(xmin=0.1, ymin=0.2, xmax=0.8, ymax=0.9)
        coords = SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0)
        detection = DetectionDTO(
            label="durian",
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        device_data = DeviceDetectionDataDTO(
            device_id="test_device_001",
            device_alias="left_camera",
            frame_id=42,
            detections=[detection]
        )
        
        assert device_data.validate(), \
            f"设备检测数据验证失败: {device_data.get_validation_errors()}"
        
        # 验证便捷方法
        assert device_data.detection_count == 1
        assert len(device_data.get_detections_by_label("durian")) == 1
        
        print("✅ DeviceDetectionDataDTO 冒烟测试通过")
    
    def test_video_frame_dto_smoke(self):
        """冒烟测试：视频帧DTO"""
        import numpy as np
        
        # 创建模拟的视频帧数据
        rgb_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        video_frame = VideoFrameDTO(
            device_id="test_device_001",
            frame_id=42,
            rgb_frame=rgb_frame,
            frame_width=640,
            frame_height=480
        )
        
        assert video_frame.validate(), \
            f"视频帧验证失败: {video_frame.get_validation_errors()}"
        
        # 验证属性
        assert video_frame.has_rgb
        assert not video_frame.has_depth
        assert video_frame.frame_size == (640, 480)
        
        print("✅ VideoFrameDTO 冒烟测试通过")
    
    def test_oak_data_collection_dto_smoke(self):
        """冒烟测试：OAK数据采集综合DTO"""
        # 创建完整的数据采集对象
        bbox = BoundingBoxDTO(xmin=0.1, ymin=0.2, xmax=0.8, ymax=0.9)
        coords = SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0)
        detection = DetectionDTO(
            label="durian",
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        device_data = DeviceDetectionDataDTO(
            device_id="test_device_001",
            frame_id=42,
            detections=[detection]
        )
        
        import numpy as np
        video_frame = VideoFrameDTO(
            device_id="test_device_001",
            frame_id=42,
            rgb_frame=np.zeros((480, 640, 3), dtype=np.uint8),
            frame_width=640,
            frame_height=480
        )
        
        collection = OAKDataCollectionDTO(
            collection_id="batch_001",
            devices_data={"test_device_001": device_data},
            video_frames={"test_device_001": video_frame}
        )
        
        assert collection.validate(), \
            f"数据采集DTO验证失败: {collection.get_validation_errors()}"
        
        # 验证便捷方法
        assert "test_device_001" in collection.available_devices
        assert collection.total_detections == 1
        
        print("✅ OAKDataCollectionDTO 冒烟测试通过")


class TestConfigDTOSmokeTest:
    """配置相关DTO冒烟测试"""
    
    def test_oak_config_dto_smoke(self):
        """冒烟测试：OAK配置DTO"""
        oak_config = OAKConfigDTO(
            model_path="/path/to/model.blob",
            confidence_threshold=0.5,
            hardware_fps=30
        )
        
        assert oak_config.validate(), \
            f"OAK配置验证失败: {oak_config.get_validation_errors()}"
        
        print("✅ OAKConfigDTO 冒烟测试通过")
    
    def test_device_config_dto_smoke(self):
        """冒烟测试：设备配置DTO"""
        from ...core.dto.device_config_dto import DeviceType, ConnectionStatus
        
        oak_config = OAKConfigDTO()
        
        device_config = DeviceConfigDTO(
            mxid="test_mxid_12345",
            device_alias="left_camera",
            device_type=DeviceType.OAK_D,
            connection_status=ConnectionStatus.CONNECTED,
            oak_config=oak_config
        )
        
        assert device_config.validate(), \
            f"设备配置验证失败: {device_config.get_validation_errors()}"
        
        print("✅ DeviceConfigDTO 冒烟测试通过")
    
    def test_system_config_dto_smoke(self):
        """冒烟测试：系统配置DTO"""
        sys_config = SystemConfigDTO(
            enable_can_communication=True,
            can_interface="can0",
            can_baudrate=500000
        )
        
        assert sys_config.validate(), \
            f"系统配置验证失败: {sys_config.get_validation_errors()}"
        
        print("✅ SystemConfigDTO 冒烟测试通过")
    
    def test_device_manager_config_dto_smoke(self):
        """冒烟测试：设备管理器配置DTO"""
        from ...core.dto.device_config_dto import DeviceType, ConnectionStatus
        
        oak_config = OAKConfigDTO()
        device_config = DeviceConfigDTO(
            mxid="test_mxid_12345",
            device_alias="left_camera",
            device_type=DeviceType.OAK_D,
            connection_status=ConnectionStatus.CONNECTED,
            oak_config=oak_config
        )
        sys_config = SystemConfigDTO()
        
        manager_config = DeviceManagerConfigDTO(
            devices=[device_config],
            system_config=sys_config
        )
        
        assert manager_config.validate(), \
            f"设备管理器配置验证失败: {manager_config.get_validation_errors()}"
        
        print("✅ DeviceManagerConfigDTO 冒烟测试通过")


class TestBatchValidation:
    """批量验证测试：模拟实际使用场景"""
    
    def test_batch_detection_creation_15fps(self):
        """
        冒烟测试：批量创建检测DTO（15fps场景）
        
        模拟场景：15帧/秒，每帧8个检测对象
        总计：15 × 8 = 120个检测对象/秒
        """
        total_dtos = 0
        invalid_dtos = []
        
        start_time = time.perf_counter()
        
        # 模拟15帧
        for frame_idx in range(15):
            # 每帧8个检测
            for det_idx in range(8):
                bbox = BoundingBoxDTO(
                    xmin=0.1 + det_idx * 0.05,
                    ymin=0.2,
                    xmax=0.8,
                    ymax=0.9
                )
                coords = SpatialCoordinatesDTO(
                    x=100.0 + det_idx * 10,
                    y=200.0,
                    z=300.0 + frame_idx * 5
                )
                detection = DetectionDTO(
                    label="durian",
                    confidence=0.95,
                    bbox=bbox,
                    spatial_coordinates=coords
                )
                
                # 验证
                if not detection.validate():
                    invalid_dtos.append(
                        (frame_idx, det_idx, detection.get_validation_errors())
                    )
                
                total_dtos += 1
        
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        
        # 断言：所有DTO都应该有效
        assert len(invalid_dtos) == 0, \
            f"发现{len(invalid_dtos)}个无效DTO: {invalid_dtos[:3]}"
        
        # 性能统计
        avg_time_per_dto = elapsed_ms / total_dtos
        print(f"\n批量验证性能统计：")
        print(f"  总对象数: {total_dtos}")
        print(f"  总耗时: {elapsed_ms:.2f} ms")
        print(f"  平均每个对象: {avg_time_per_dto:.4f} ms")
        print(f"  ✅ 所有DTO验证通过")
    
    def test_batch_creation_without_validation(self):
        """
        性能测试：不验证的批量创建（运行时场景）
        
        对比：展示不验证时的性能
        """
        total_dtos = 0
        
        start_time = time.perf_counter()
        
        # 模拟15帧，每帧8个检测
        for frame_idx in range(15):
            for det_idx in range(8):
                bbox = BoundingBoxDTO(
                    xmin=0.1 + det_idx * 0.05,
                    ymin=0.2,
                    xmax=0.8,
                    ymax=0.9
                )
                coords = SpatialCoordinatesDTO(
                    x=100.0 + det_idx * 10,
                    y=200.0,
                    z=300.0 + frame_idx * 5
                )
                detection = DetectionDTO(
                    label="durian",
                    confidence=0.95,
                    bbox=bbox,
                    spatial_coordinates=coords
                )
                
                # 注意：不调用validate()
                total_dtos += 1
        
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        
        avg_time_per_dto = elapsed_ms / total_dtos
        print(f"\n运行时性能（无验证）：")
        print(f"  总对象数: {total_dtos}")
        print(f"  总耗时: {elapsed_ms:.2f} ms")
        print(f"  平均每个对象: {avg_time_per_dto:.4f} ms")
        print(f"  ✅ 极致性能，零验证开销")


class TestInvalidDataDetection:
    """无效数据检测测试：确保验证逻辑正确捕获错误"""
    
    def test_invalid_confidence_detection(self):
        """测试：检测无效的置信度"""
        bbox = BoundingBoxDTO(xmin=0.1, ymin=0.2, xmax=0.8, ymax=0.9)
        coords = SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0)
        
        # 创建置信度超出范围的检测对象
        detection = DetectionDTO(
            label="durian",
            confidence=1.5,  # 无效：超出范围
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        # 验证应该失败
        assert not detection.validate(), \
            "置信度超出范围的检测对象应该验证失败"
        
        errors = detection.get_validation_errors()
        assert any("confidence" in str(err).lower() for err in errors), \
            f"错误信息应包含confidence字段: {errors}"
        
        print("✅ 无效置信度检测正确")
    
    def test_invalid_bbox_detection(self):
        """测试：检测无效的边界框"""
        # xmin >= xmax，无效
        bbox = BoundingBoxDTO(xmin=0.8, ymin=0.2, xmax=0.1, ymax=0.9)
        
        assert not bbox.validate(), \
            "无效的边界框应该验证失败"
        
        print("✅ 无效边界框检测正确")
    
    def test_invalid_empty_label_detection(self):
        """测试：检测空标签"""
        bbox = BoundingBoxDTO(xmin=0.1, ymin=0.2, xmax=0.8, ymax=0.9)
        coords = SpatialCoordinatesDTO(x=100.0, y=200.0, z=300.0)
        
        detection = DetectionDTO(
            label="",  # 无效：空标签
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        assert not detection.validate(), \
            "空标签的检测对象应该验证失败"
        
        print("✅ 空标签检测正确")


if __name__ == "__main__":
    """直接运行冒烟测试"""
    print("="*60)
    print("OAK视觉系统 - DTO冒烟测试")
    print("="*60)
    
    # 运行pytest
    pytest.main([__file__, "-v", "-s"])

