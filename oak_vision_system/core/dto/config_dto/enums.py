"""
配置相关的枚举类型定义
"""

from enum import Enum


class DeviceType(Enum):
    """OAK设备类型枚举"""
    OAK_D = "OAK-D"
    OAK_D_LITE = "OAK-D-Lite"
    OAK_D_PRO = "OAK-D-Pro"
    OAK_D_S2 = "OAK-D-S2"
    OAK_1 = "OAK-1"
    UNKNOWN = "Unknown"


class DeviceRole(Enum):
    """
    设备功能角色枚举
    
    表示设备在系统中的功能位置（固定），而不是具体的物理设备。
    暂定只有左右两个相机
    """
    LEFT_CAMERA = "left_camera"
    RIGHT_CAMERA = "right_camera"
    UNKNOWN = "unknown"
    
    @property
    def display_name(self) -> str:
        """获取显示名称（中文）"""
        names = {
            DeviceRole.LEFT_CAMERA: "左相机",
            DeviceRole.RIGHT_CAMERA: "右相机",
            DeviceRole.UNKNOWN: "未知"
        }
        return names.get(self, self.value)

    @classmethod
    def get_expected_roles(cls) -> set['DeviceRole']:
        """
        获取预期望的设备功能角色集合
        
        该集合用于检查设备功能角色是否符合预期望
        
        Returns:
            set['DeviceRole']: 预期望的设备功能角色集合
        """
        return {cls.LEFT_CAMERA, cls.RIGHT_CAMERA}
    
    @classmethod
    def get_expected_roles_ordered(cls) -> list['DeviceRole']:
        """
        获取预期角色的稳定顺序列表。
        
        Returns:
            list['DeviceRole']: [LEFT_CAMERA, RIGHT_CAMERA]
        """
        return [cls.LEFT_CAMERA, cls.RIGHT_CAMERA]
        


class ConnectionStatus(Enum):
    """设备连接状态枚举"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


class FilterType(Enum):
    """滤波器类型枚举"""
    MOVING_AVERAGE = "moving_average"  # 滑动平均滤波（默认推荐）
    KALMAN = "kalman"
    LOWPASS = "lowpass"
    MEDIAN = "median"
