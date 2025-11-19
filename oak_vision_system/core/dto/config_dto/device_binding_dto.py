"""
设备绑定相关DTO

包含设备角色绑定、设备元数据。
"""

import time
from dataclasses import dataclass, field
from tkinter.tix import MAX
from typing import List, Optional

from ..base_dto import validate_string_length
from .base_config_dto import BaseConfigDTO
from .enums import DeviceRole, ConnectionStatus


# 历史MXid列表的最大长度
MAX_HISTORICAL_MXIDS = 5

@dataclass(frozen=True)
class DeviceMetadataDTO(BaseConfigDTO):
    """
    设备元数据DTO
    
    按MXid索引，记录每个物理设备的详细信息。
    """
    
    mxid: str                                 # 设备MXid（主键）
    product_name: Optional[str] = None        # 设备产品名（可选）
    connection_status: ConnectionStatus = ConnectionStatus.UNKNOWN
    notes: Optional[str] = None               # 用户备注
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        errors.extend(validate_string_length(self.mxid, 'mxid', min_length=10, max_length=100))
        
        if self.product_name is not None:
            errors.extend(validate_string_length(self.product_name, 'product_name', min_length=1, max_length=200))
        
        if not isinstance(self.connection_status, ConnectionStatus):
            errors.append("connection_status必须为ConnectionStatus枚举类型")
        
        if self.notes is not None:
            errors.extend(validate_string_length(self.notes, 'notes', min_length=1, max_length=500))
        
        return errors
    



@dataclass(frozen=True)
class DeviceRoleBindingDTO(BaseConfigDTO):
    """
    设备角色绑定DTO
    
    核心设计：role是固定功能位置，MXid是可更换的物理设备。
    """
    
    role: DeviceRole                          # 功能角色（主键）
    historical_mxids: List[str] = field(default_factory=list)  # 历史MXid（最多5个）
    MAX_HISTORICAL_MXIDS_LENGTH: int = MAX_HISTORICAL_MXIDS
    active_mxid: Optional[str] = None         # 当前激活MXid（运行时）
    last_active_mxid: Optional[str] = None    # 上次使用MXid（持久化）
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        if not isinstance(self.role, DeviceRole):
            errors.append("role必须为DeviceRole枚举类型")
        
        if not isinstance(self.historical_mxids, list):
            errors.append("historical_mxids必须为列表类型")
        elif len(self.historical_mxids) > MAX_HISTORICAL_MXIDS:
            errors.append(f"historical_mxids最多{MAX_HISTORICAL_MXIDS}个")
        
        if self.active_mxid and self.active_mxid not in self.historical_mxids:
            errors.append("active_mxid不在historical_mxids列表中")
        
        return errors
    
    @property
    def has_active_device(self) -> bool:
        """是否有激活的设备"""
        return self.active_mxid is not None
    
    def add_mxid_to_history(self, mxid: str) -> 'DeviceRoleBindingDTO':
        """
        添加新的 mxid 到历史记录（LIFO，自动限制长度）
        
        行为：
        - 如果 mxid 已存在，直接返回原对象（去重）
        - 添加到列表开头（最新的在前面）
        - 如果超过最大数量，截断保留前 N 个
        - 自动更新 last_active_mxid
        
        Args:
            mxid: 要添加的设备 mxid
        
        Returns:
            新的 DeviceRoleBindingDTO 对象（如果 mxid 已存在则返回原对象）
        
        Example:
            >>> binding = binding.add_mxid_to_history("14442C10D13D0D0003")
        """
        # 如果已存在，直接返回原对象（避免重复）
        if mxid in self.historical_mxids:
            return self
        
        # 添加到列表开头（最新的在前）
        mxids = [mxid] + self.historical_mxids
        
        # 超出限制，截断保留前 N 个
        if len(mxids) > MAX_HISTORICAL_MXIDS:
            mxids = mxids[:MAX_HISTORICAL_MXIDS]
        
        # 返回新对象
        return self.with_updates(
            historical_mxids=mxids,
            last_active_mxid=mxid
        )
    

    def remove_mxid_from_history(self, mxid: str) -> 'DeviceRoleBindingDTO':
        """
        从历史记录中移除指定 mxid
        
        行为：
        - 如果 mxid 不存在，直接返回原对象
        - 从历史列表中移除该 mxid
        - 如果移除的是 active_mxid，自动清空它
        - 如果移除的是 last_active_mxid，自动清空它
        
        Args:
            mxid: 要移除的设备 mxid
        
        Returns:
            新的 DeviceRoleBindingDTO 对象（如果 mxid 不存在则返回原对象）
        
        Example:
            >>> binding = binding.remove_mxid_from_history("14442C10D13D0D0000")
        """
        # 如果不存在，直接返回原对象
        if mxid not in self.historical_mxids:
            return self
        
        # 过滤掉要删除的 mxid
        mxids = [m for m in self.historical_mxids if m != mxid]
        
        # 如果删除的是 active_mxid，清空它
        new_active_mxid = None if self.active_mxid == mxid else self.active_mxid
        
        # 如果删除的是 last_active_mxid，清空它
        new_last_active_mxid = None if self.last_active_mxid == mxid else self.last_active_mxid
        
        # 返回新对象
        return self.with_updates(
            historical_mxids=mxids,
            active_mxid=new_active_mxid,
            last_active_mxid=new_last_active_mxid
        )
    

    def get_history_count(self) -> int:
        """
        获取历史记录数量
        
        Returns:
            历史设备数量
        
        Example:
            >>> count = binding.get_history_count()
            >>> print(f"历史设备数: {count}")
        """
        return len(self.historical_mxids)
    
    def is_mxid_in_history(self, mxid: str) -> bool:
        """
        检查 mxid 是否在历史记录中
        
        Args:
            mxid: 要检查的设备 mxid
        
        Returns:
            是否存在
        """
        return mxid in self.historical_mxids
    

    @staticmethod
    def create_default_bingdings() -> List['DeviceRoleBindingDTO']:
        """
        创建默认的设备绑定对象列表，分别是左右相机的绑定配置
        """
        return[
            DeviceRoleBindingDTO(
                role=DeviceRole.LEFT_CAMERA,
                historical_mxids=[],
                active_mxid=None,
                last_active_mxid=None
            ),
            DeviceRoleBindingDTO(
                role=DeviceRole.RIGHT_CAMERA,
                historical_mxids=[],
                active_mxid=None,
                last_active_mxid=None
            )
        ]
    
    def set_active_Mxid_by_device(self, device: DeviceMetadataDTO) -> 'DeviceRoleBindingDTO':
        """
        传入设备元数据对象，给当前绑定设置激活的设备 MXid
        
        如果设备 MXid 不在历史记录中，添加到历史记录中
        否则更新历史记录到最大数量
        
        Args:
            device: 设备元数据对象
        
        Returns:
            新的 DeviceRoleBindingDTO 对象，active_mxid 和 last_active_mxid 都设置为新的设备 MXid
        
        Raises:
            ValueError: 如果 device 为 None 或 device.mxid 为空
        """
        # 参数验证
        if device is None:
            raise ValueError("device 不能为 None")
        if not device.mxid:
            raise ValueError(f"device.mxid 不能为空，当前值: {device.mxid}")
        
        if device.mxid not in self.historical_mxids:
            new_historical_mxids = [device.mxid] + self.historical_mxids
        else:
            new_historical_mxids = self.historical_mxids

        return self.with_updates(
            historical_mxids=new_historical_mxids[:MAX_HISTORICAL_MXIDS],
            active_mxid=device.mxid,
            last_active_mxid=device.mxid
        )










