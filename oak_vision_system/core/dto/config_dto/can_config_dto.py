"""
CAN通信模块配置DTO
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import re

from .base_config_dto import BaseConfigDTO


@dataclass(frozen=True)
class CanFrameMeta:
    """单个 CAN 帧的元信息。

    - frame_id 统一使用十进制 int 存储（外部可接受 0x 前缀/字符串后统一转换）
    - is_extended 为 True 表示 29-bit 扩展帧，False 表示 11-bit 标准帧
    - comment 为可选备注
    """

    frame_id: int          # 帧ID（十进制整数，外部支持0x前缀或字符串，统一转为int）
    is_extended: bool      # 是否为扩展帧（True=29位扩展帧，False=11位标准帧）
    comment: str = ""      # 可选备注信息


@dataclass(frozen=True)
class FrameIdConfigDTO(BaseConfigDTO):
    """帧ID配置
    
    设计目标：
    - 提供类型安全的帧ID容器（含扩展帧标志与备注）
    - 在此集中进行范围、唯一性与字段合法性校验
    """
    
    # 键为语义名称（如 "heartbeat"），值为该帧的元信息
    frames: Dict[str, CanFrameMeta] = field(default_factory=dict)

    def _validate_data(self) -> List[str]:
        errors: List[str] = []

        # 保证 (frame_id, is_extended) 维度的唯一性
        seen_pairs: Set[Tuple[int, bool]] = set()

        for name, meta in self.frames.items():
            # 类型校验
            if not isinstance(meta, CanFrameMeta):
                errors.append(f"{name}: 值必须为CanFrameMeta类型")
                # 跳过后续与此条目相关的校验
                continue

            # ID 范围校验
            if meta.is_extended:
                if not (0 <= meta.frame_id <= 0x1FFFFFFF):
                    errors.append(f"{name}: 扩展帧ID超范围(0..0x1FFFFFFF): {meta.frame_id}")
            else:
                if not (0 <= meta.frame_id <= 0x7FF):
                    errors.append(f"{name}: 标准帧ID超范围(0..0x7FF): {meta.frame_id}")

            # 唯一性校验（按 (frame_id, is_extended) 组合）
            pair_key = (meta.frame_id, meta.is_extended)
            if pair_key in seen_pairs:
                errors.append(f"{name}: 与其他条目发生重复(frame_id+is_extended)={pair_key}")
            else:
                seen_pairs.add(pair_key)

            # 备注长度（可根据项目需要调整范围）
            # 延迟导入的 helper 在文件后部声明，此处调用在运行期有效
            try:
                errors.extend(validate_string_length(meta.comment, f"{name}.comment", min_length=0, max_length=200))
            except NameError:
                # 若工具函数尚未导入，忽略备注长度校验（不影响其他校验）
                pass

        return errors

from ..base_dto import validate_string_length

# 可维护的接口白名单与通道格式（Linux 常见接口）
ALLOWED_CAN_INTERFACES: tuple[str, ...] = ("socketcan", "vcan", "slcan")
CAN_CHANNEL_PATTERNS: Dict[str, re.Pattern[str]] = {
    "socketcan": re.compile(r"^can\d+$"),
    "vcan": re.compile(r"^vcan\d+$"),
    "slcan": re.compile(r"^slcan\d+$"),
}

# 允许的 CAN 波特率（常用值）
ALLOWED_CAN_BITRATES: tuple[int, ...] = (
    20000,
    50000,
    100000,
    125000,
    250000,
    500000,
    800000,
    1000000,
)


@dataclass(frozen=True)
class CANConfigDTO(BaseConfigDTO):
    """CAN通信模块配置"""
    
    # 基本配置
    enable_can: bool = True    # 默认启用CAN通信
    can_interface: str = 'socketcan'
    can_channel: str = 'can0'
    can_bitrate: int = 250000
    
    # 通信超时配置（协议层）
    send_timeout_ms: int = 100
    receive_timeout_ms: int = 10
    
    # 接口管理配置
    enable_auto_configure: bool = True    # 是否自动配置CAN接口（Linux系统）
    sudo_password: Optional[str] = "orangepi"   # sudo密码（用于自动配置）
    
    # 警报配置
    alert_interval_ms: int = 500    # 警报发送间隔（毫秒）
    
    # 帧 ID 配置（直接采用 DTO）
    frame_ids: FrameIdConfigDTO = field(default_factory=FrameIdConfigDTO)
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        # 验证波特率（白名单）
        if self.can_bitrate not in ALLOWED_CAN_BITRATES:
            errors.append(f"can_bitrate必须为有效值之一: {ALLOWED_CAN_BITRATES}")
        
        # 验证接口（白名单）
        if self.can_interface not in ALLOWED_CAN_INTERFACES:
            errors.append(f"can_interface必须为: {ALLOWED_CAN_INTERFACES}")
        else:
            # 根据接口类型校验通道名格式
            pattern = CAN_CHANNEL_PATTERNS.get(self.can_interface)
            channel = self.can_channel or ""
            if pattern and not pattern.fullmatch(channel):
                examples = {
                    "socketcan": "can0/can1",
                    "vcan": "vcan0",
                    "slcan": "slcan0",
                }
                errors.append(
                    f"{self.can_interface} 通道名格式无效，应类似 '{examples[self.can_interface]}'，当前: {channel}"
                )
        # 额外长度保护
        errors.extend(validate_string_length(
            self.can_channel, 'can_channel', min_length=1, max_length=50
        ))
        
        # 验证警报间隔
        if self.alert_interval_ms <= 0:
            errors.append(f"alert_interval_ms必须为正数，当前值: {self.alert_interval_ms}")
        
        # 验证帧 ID 配置
        if not isinstance(self.frame_ids, FrameIdConfigDTO):
            errors.append("frame_ids必须为FrameIdConfigDTO类型")
        else:
            # 级联校验帧ID配置内部各项
            errors.extend(self.frame_ids._validate_data())
        
        return errors
