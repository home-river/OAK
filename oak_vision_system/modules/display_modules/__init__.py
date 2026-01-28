"""
显示模块

负责将检测结果和视频帧以图形化方式呈现给用户。

模块架构：
- RenderPacketPackager: 适配器子模块，将外部异构数据转换为内部统一格式
- DisplayRenderer: 渲染器子模块，负责实际的图形渲染
- DisplayManager: 主控制器，协调两个子模块（待实现）

数据流：
    外部事件（通过事件总线）
        ↓
    RenderPacketPackager（订阅事件，配对数据）
        ↓
    内部队列（线程安全）
        ↓
    DisplayRenderer（渲染显示）
        ↓
    OpenCV 窗口
"""

from .render_packet_packager import (
    RenderPacket,
    RenderPacketPackager,
    RawDataEvent,
    DataType,
)

from .display_renderer import DisplayRenderer
from .display_manager import DisplayManager

__all__ = [
    # 数据类型
    "RenderPacket",
    "RawDataEvent",
    "DataType",
    
    # 子模块
    "RenderPacketPackager",
    "DisplayRenderer",
    
    # 主控制器
    "DisplayManager",
]
