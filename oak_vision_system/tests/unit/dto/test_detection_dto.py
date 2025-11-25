"""
数据采集模块DTO单元测试

测试以下DTO类的功能：
- SpatialCoordinatesDTO: 空间坐标数据传输对象
- BoundingBoxDTO: 边界框数据传输对象  
- DetectionDTO: 单个检测结果数据传输对象
- DeviceDetectionDataDTO: 单个设备的检测数据传输对象
- VideoFrameDTO: 视频帧数据传输对象
- OAKDataCollectionDTO: OAK数据采集模块综合数据传输对象
"""

import time
import pytest
import numpy as np

from oak_vision_system.core.dto import (
    SpatialCoordinatesDTO,
    BoundingBoxDTO,
    DetectionDTO,
    DeviceDetectionDataDTO,
    VideoFrameDTO,
    OAKDataCollectionDTO,
)


class TestSpatialCoordinatesDTO:
    """空间坐标DTO测试套件"""
    
    def test_valid_coordinates_creation(self):
        """测试创建有效的空间坐标"""
        coords = SpatialCoordinatesDTO(x=100.5, y=-50.2, z=200.0)
        
        # 显式调用验证
        assert coords.validate() is True, \
            f"验证失败: {coords.get_validation_errors()}"
        assert coords.x == 100.5
        assert coords.y == -50.2
        assert coords.z == 200.0
    
    def test_invalid_coordinates_creation(self):
        """测试创建无效的空间坐标"""
        coords = SpatialCoordinatesDTO(x="not_a_number", y=50.0, z=200.0)
        
        # 显式调用验证
        assert coords.validate() is False
        assert len(coords.get_validation_errors()) > 0
    
    def test_distance_from_origin(self):
        """测试距离原点的距离计算"""
        coords = SpatialCoordinatesDTO(x=3.0, y=4.0, z=0.0)
        distance = coords.distance_from_origin
        distance_squared = coords.distance_squared_from_origin
        
        assert distance == 5.0  # 3-4-5直角三角形
        assert distance_squared == 25.0  # 距离平方
    
    def test_distance_to_other_point(self):
        """测试到另一点的距离计算"""
        coords1 = SpatialCoordinatesDTO(x=0.0, y=0.0, z=0.0)
        coords2 = SpatialCoordinatesDTO(x=3.0, y=4.0, z=0.0)
        
        distance = coords1.distance_to(coords2)
        distance_squared = coords1.distance_squared_to(coords2)
        
        assert distance == 5.0
        assert distance_squared == 25.0
        
        # 测试类型错误
        with pytest.raises(TypeError):
            coords1.distance_to("not_a_coordinate")
        
        with pytest.raises(TypeError):
            coords1.distance_squared_to("not_a_coordinate")


class TestBoundingBoxDTO:
    """边界框DTO测试套件"""
    
    def test_valid_bbox_creation(self):
        """测试创建有效的边界框"""
        bbox = BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0)
        
        # 显式调用验证
        assert bbox.validate() is True, \
            f"验证失败: {bbox.get_validation_errors()}"
        assert bbox.xmin == 10.0
        assert bbox.ymin == 20.0
        assert bbox.xmax == 100.0
        assert bbox.ymax == 80.0
    
    def test_invalid_bbox_creation(self):
        """测试创建无效的边界框"""
        # xmin >= xmax的情况
        bbox = BoundingBoxDTO(xmin=100.0, ymin=20.0, xmax=50.0, ymax=80.0)
        
        # 显式调用验证
        assert bbox.validate() is False
        assert len(bbox.get_validation_errors()) > 0
    
    def test_bbox_properties(self):
        """测试边界框属性计算"""
        bbox = BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=60.0, ymax=70.0)
        
        assert bbox.width == 50.0
        assert bbox.height == 50.0
        assert bbox.area == 2500.0
        assert bbox.center_x == 35.0
        assert bbox.center_y == 45.0
        assert bbox.center_point == (35.0, 45.0)


class TestDetectionDTO:
    """检测结果DTO测试套件"""
    
    def test_valid_detection_creation(self):
        """测试创建有效的检测结果"""
        bbox = BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0)
        coords = SpatialCoordinatesDTO(x=100.0, y=50.0, z=300.0)
        
        detection = DetectionDTO(
            label=1,
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        assert detection.validate() is True, \
            f"验证失败: {detection.get_validation_errors()}"
        assert detection.label == 1
        assert detection.confidence == 0.95
        assert detection.bbox == bbox
        assert detection.spatial_coordinates == coords
        assert detection.created_at is not None  # 应该自动生成
    
    def test_invalid_detection_creation(self):
        """测试创建无效的检测结果"""
        bbox = BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0)
        coords = SpatialCoordinatesDTO(x=100.0, y=50.0, z=300.0)
        
        # 置信度超出范围
        detection = DetectionDTO(
            label=1,
            confidence=1.5,  # 无效的置信度
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        assert detection.validate() is False
        assert len(detection.get_validation_errors()) > 0


class TestDeviceDetectionDataDTO:
    """设备检测数据DTO测试套件"""
    
    def test_valid_device_data_creation(self):
        """测试创建有效的设备检测数据"""
        device_data = DeviceDetectionDataDTO(
            device_id="OAK_001",
            device_alias="left_camera",
            frame_id=123
        )
        
        assert device_data.validate() is True, \
            f"验证失败: {device_data.get_validation_errors()}"
        assert device_data.device_id == "OAK_001"
        assert device_data.device_alias == "left_camera"
        assert device_data.frame_id == 123
        assert device_data.detection_count == 0  # 默认空列表
        assert device_data.created_at is not None  # 应该自动生成
    
    def test_device_data_with_detections(self):
        """测试带检测结果的设备数据"""
        bbox = BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0)
        coords = SpatialCoordinatesDTO(x=100.0, y=50.0, z=300.0)
        detection = DetectionDTO(
            label=1,
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        device_data = DeviceDetectionDataDTO(
            device_id="OAK_001",
            frame_id=123,
            detections=[detection]
        )
        
        assert device_data.detection_count == 1
        assert len(device_data.get_detections_by_class_id(1)) == 1
        assert len(device_data.get_detections_by_class_id(2)) == 0
        assert len(device_data.get_high_confidence_detections(0.9)) == 1
        assert len(device_data.get_high_confidence_detections(0.99)) == 0
    
    def test_invalid_device_data_creation(self):
        """测试创建无效的设备检测数据"""
        device_data = DeviceDetectionDataDTO(
            device_id="",  # 空设备ID
            frame_id=-1    # 负帧ID
        )
        
        assert device_data.validate() is False
        assert len(device_data.get_validation_errors()) > 0


class TestVideoFrameDTO:
    """视频帧DTO测试套件"""
    
    def test_valid_video_frame_creation(self):
        """测试创建有效的视频帧"""
        # 模拟numpy数组
        rgb_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        frame = VideoFrameDTO(
            device_id="OAK_001",
            frame_id=123,
            rgb_frame=rgb_frame
        )
        
        assert frame.validate() is True, \
            f"验证失败: {frame.get_validation_errors()}"
        assert frame.device_id == "OAK_001"
        assert frame.frame_id == 123
        assert frame.has_rgb is True
        assert frame.has_depth is False
        assert frame.frame_size == (640, 480)
        assert frame.created_at is not None
    
    def test_video_frame_with_depth(self):
        """测试带深度信息的视频帧"""
        depth_frame = np.zeros((480, 640), dtype=np.uint16)
        
        frame = VideoFrameDTO(
            device_id="OAK_001",
            frame_id=123,
            depth_frame=depth_frame
        )
        
        assert frame.has_rgb is False
        assert frame.has_depth is True
    
    def test_invalid_video_frame_creation(self):
        """测试创建无效的视频帧"""
        # 没有任何帧数据
        frame = VideoFrameDTO(
            device_id="OAK_001",
            frame_id=123
        )
        
        assert frame.validate() is False
        assert len(frame.get_validation_errors()) > 0


class TestOAKDataCollectionDTO:
    """OAK数据采集DTO测试套件"""
    
    def test_valid_collection_creation(self):
        """测试创建有效的数据采集DTO"""
        collection = OAKDataCollectionDTO(
            collection_id="batch_001"
        )
        
        assert collection.validate() is True, \
            f"验证失败: {collection.get_validation_errors()}"
        assert collection.collection_id == "batch_001"
        assert len(collection.available_devices) == 0
        assert collection.total_detections == 0
        assert collection.created_at is not None
    
    def test_collection_with_data(self):
        """测试带数据的采集DTO"""
        # 创建设备数据
        bbox = BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0)
        coords = SpatialCoordinatesDTO(x=100.0, y=50.0, z=300.0)
        detection = DetectionDTO(
            label=1,
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        device_data = DeviceDetectionDataDTO(
            device_id="OAK_001",
            detections=[detection]
        )
        
        # 创建视频帧
        rgb_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        video_frame = VideoFrameDTO(
            device_id="OAK_001",
            frame_id=123,
            rgb_frame=rgb_frame
        )
        
        collection = OAKDataCollectionDTO(
            collection_id="batch_001",
            devices_data={"OAK_001": device_data},
            video_frames={"OAK_001": video_frame}
        )
        
        assert "OAK_001" in collection.available_devices
        assert collection.total_detections == 1
        assert collection.get_device_data("OAK_001") == device_data
        assert collection.get_video_frame("OAK_001") == video_frame
        assert collection.has_device_data("OAK_001") is True
        assert collection.has_device_data("OAK_002") is False
    
    def test_invalid_collection_creation(self):
        """测试创建无效的数据采集DTO"""
        collection = OAKDataCollectionDTO(
            collection_id=""  # 空采集ID
        )
        
        assert collection.validate() is False
        assert len(collection.get_validation_errors()) > 0


 


class TestDTOIntegration:
    """DTO集成测试套件"""
    
    def test_dto_serialization(self):
        """测试DTO序列化和反序列化"""
        coords = SpatialCoordinatesDTO(x=100.0, y=50.0, z=300.0)
        
        # 测试JSON序列化
        json_str = coords.to_json()
        assert isinstance(json_str, str)
        
        # 测试从JSON反序列化
        coords_from_json = SpatialCoordinatesDTO.from_json(json_str)
        assert coords_from_json.x == coords.x
        assert coords_from_json.y == coords.y
        assert coords_from_json.z == coords.z
    
    def test_dto_dict_conversion(self):
        """测试DTO字典转换"""
        bbox = BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0)
        
        # 测试转换为字典
        bbox_dict = bbox.to_dict()
        assert isinstance(bbox_dict, dict)
        assert bbox_dict['xmin'] == 10.0
        
        # 测试从字典创建
        bbox_from_dict = BoundingBoxDTO.from_dict(bbox_dict)
        assert bbox_from_dict.xmin == bbox.xmin
        assert bbox_from_dict.ymin == bbox.ymin
    
    def test_complex_dto_composition(self):
        """测试复杂DTO组合"""
        # 创建完整的数据采集场景
        bbox = BoundingBoxDTO(xmin=10.0, ymin=20.0, xmax=100.0, ymax=80.0)
        coords = SpatialCoordinatesDTO(x=100.0, y=50.0, z=300.0)
        detection = DetectionDTO(
            label="apple",
            confidence=0.95,
            bbox=bbox,
            spatial_coordinates=coords
        )
        
        device_data = DeviceDetectionDataDTO(
            device_id="OAK_001",
            frame_id=123,
            detections=[detection]
        )
        
        rgb_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        video_frame = VideoFrameDTO(
            device_id="OAK_001",
            frame_id=123,
            rgb_frame=rgb_frame
        )
        
        collection = OAKDataCollectionDTO(
            collection_id="batch_001",
            devices_data={"OAK_001": device_data},
            video_frames={"OAK_001": video_frame}
        )
        
        # 验证整个组合的有效性
        assert collection.validate() is True, \
            f"验证失败: {collection.get_validation_errors()}"
        assert device_data.validate() is True, \
            f"验证失败: {device_data.get_validation_errors()}"
        assert detection.validate() is True, \
            f"验证失败: {detection.get_validation_errors()}"
        assert bbox.validate() is True, \
            f"验证失败: {bbox.get_validation_errors()}"
        assert coords.validate() is True, \
            f"验证失败: {coords.get_validation_errors()}"
        assert video_frame.validate() is True, \
            f"验证失败: {video_frame.get_validation_errors()}"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
