"""
CAN协议编解码模块

提供CAN通信协议的编解码功能，包括：
- 协议常量定义
- 消息类型识别
- 坐标响应编码
- 警报帧编码
"""

import struct
from typing import Optional
import can


class CANProtocol:
    """
    CAN通信协议编解码器
    
    定义协议常量并提供消息识别和编码功能。
    协议规范：
    - 帧ID: 0x30
    - 坐标请求: 8字节全为0x22
    - 坐标响应: Byte0=0x08, Byte1=0x00, Byte2-7为xyz坐标（小端序，每个2字节）
    - 警报帧: 8字节全为0x33
    """
    
    # 协议常量
    FRAME_ID = 0x30
    MSG_TYPE_REQUEST = 0x22
    MSG_TYPE_RESPONSE = 0x08
    MSG_TYPE_ALERT = 0x33
    
    @staticmethod
    def identify_message(msg: can.Message) -> Optional[str]:
        """
        识别CAN消息类型，暂时只识别坐标请求
        
        Args:
            msg: CAN消息对象
            
        Returns:
            消息类型字符串（如"coordinate_request"）或None（无法识别）
            
        识别规则：
        - 帧ID必须为0x30
        - 数据长度必须为8字节
        - 8字节全为0x22 -> "coordinate_request"
        - 其他情况 -> None
        """
        # 验证帧ID
        if msg.arbitration_id != CANProtocol.FRAME_ID:
            return None
        
        # 验证数据长度
        if len(msg.data) != 8:
            return None
        
        # 识别坐标请求：8字节全为0x22
        if all(byte == CANProtocol.MSG_TYPE_REQUEST for byte in msg.data):
            return "coordinate_request"
        
        # 无法识别的消息
        return None
    
    @staticmethod
    def encode_coordinate_response(x: int, y: int, z: int) -> bytes:
        """
        使用补码编码坐标响应帧
        
        Args:
            x: X坐标（毫米，整数，范围-32768到32767）
            y: Y坐标（毫米，整数，范围-32768到32767）
            z: Z坐标（毫米，整数，范围-32768到32767）
            
        Returns:
            8字节CAN数据，格式：
            - Byte0: 0x08 (响应类型标识)
            - Byte1: 0x00 (预留)
            - Byte2-3: X坐标（小端序，有符号16位整数）
            - Byte4-5: Y坐标（小端序，有符号16位整数）
            - Byte6-7: Z坐标（小端序，有符号16位整数）
            
        小端序说明：
            对于坐标值100（0x0064），小端序表示为：0x64 0x00
            对于坐标值-100（0xFF9C），小端序表示为：0x9C 0xFF
        """
        # 使用struct.pack进行小端序打包
        # '<' 表示小端序
        # 'B' 表示无符号字节（Byte0）
        # 'x' 表示填充字节（Byte1，填充0x00）
        # 'h' 表示有符号短整型（2字节，用于xyz坐标）
        data = struct.pack('<Bxhhh', CANProtocol.MSG_TYPE_RESPONSE, x, y, z)
        
        return data
    
    @staticmethod
    def encode_alert() -> bytes:
        """
        编码警报帧
        
        Returns:
            8字节CAN数据，全为0x33
        """
        # 创建8字节全为0x33的数据
        data = bytes([CANProtocol.MSG_TYPE_ALERT] * 8)
        
        return data
