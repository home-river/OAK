#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAN控制器脚本 - 基于香橙派CAN模拟器的交互式控制器
支持按键控制发送请求指令，并解析返回的CAN数据

功能特性：
1. 按键控制发送果位置请求
2. 自动解析返回的坐标数据
3. 实时显示坐标信息到终端
4. 支持连续请求和单次请求模式
5. 人员警报信息监听和显示

协议说明：
- 请求果位置：发送 [0x22, 0x22, 0x22, 0x22, 0x22, 0x22, 0x22, 0x22] 到帧ID 0x30
- 响应格式：[0x08, 空, X坐标低位, X坐标高位, Y坐标低位, Y坐标高位, Z坐标低位, Z坐标高位]
- 人员警报：接收 [0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33] 从帧ID 0x30
"""

import can
import time
import threading
import sys
import struct
import os
from typing import Optional, Tuple

class CANController:
    def __init__(self, channel: str = 'can0', bustype: str = 'socketcan', bitrate: int = 250000):
        """
        初始化CAN控制器
        
        Args:
            channel: CAN通道名称，默认'can0'
            bustype: 总线类型，默认'socketcan'
            bitrate: 波特率，默认250000
        """
        self.channel = channel
        self.bustype = bustype
        self.bitrate = bitrate
        self.bus: Optional[can.Bus] = None
        self.running = False
        self.listen_thread = None
        
        # 协议常量
        self.FRAME_ID = 0x30
        self.REQUEST_FRUIT_DATA = [0x22, 0x22, 0x22, 0x22, 0x22, 0x22, 0x22, 0x22]
        self.PERSON_ALERT_DATA = [0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33]
        
        # 统计信息
        self.request_count = 0
        self.response_count = 0
        self.alert_count = 0
        
        # 最新坐标数据
        self.latest_coordinates = None
        self.coordinates_lock = threading.Lock()
        
    def configure_can_interface(self) -> bool:
        """
        配置CAN接口（仅Linux系统）
        
        Returns:
            bool: 配置成功返回True
        """
        if os.name != 'posix':
            print("⚠️  警告: CAN接口配置仅支持Linux系统")
            return True  # Windows下跳过配置
            
        try:
            import subprocess
            print(f"🔧 正在配置CAN接口 {self.channel}...")
            
            # 关闭接口
            subprocess.run(['sudo', 'ip', 'link', 'set', self.channel, 'down'], 
                         check=False, capture_output=True)
            
            # 设置波特率
            subprocess.run(['sudo', 'ip', 'link', 'set', self.channel, 'type', 'can', 
                           'bitrate', str(self.bitrate)], 
                         check=True, capture_output=True)
            
            # 启用接口
            subprocess.run(['sudo', 'ip', 'link', 'set', self.channel, 'up'], 
                         check=True, capture_output=True)
            
            print(f"✅ CAN接口 {self.channel} 配置成功")
            return True
            
        except Exception as e:
            print(f"❌ CAN接口配置失败: {e}")
            return False
    
    def initialize_can_bus(self) -> bool:
        """
        初始化CAN总线连接
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.bus = can.Bus(channel=self.channel, bustype=self.bustype)
            print(f"✅ CAN总线初始化成功: {self.channel} ({self.bustype})")
            return True
        except Exception as e:
            print(f"❌ CAN总线初始化失败: {e}")
            print("💡 提示: 请确保CAN接口已配置")
            return False
    
    def parse_fruit_coordinates(self, data: bytes) -> Optional[Tuple[int, int, int]]:
        """
        解析果位置响应数据
        
        根据抓果车CAN通讯协议规范：
        香橙派响应数据位：[0x08, 空, X低位, X高位, Y低位, Y高位, Z低位, Z高位]
        所有坐标均使用小端序（低位在前）+ 16位补码表示
        
        Args:
            data: CAN消息数据
            
        Returns:
            Tuple[int, int, int]: (X, Y, Z) 坐标，单位毫米，失败返回None
        """
        try:
            if len(data) != 8:
                print(f"❌ 数据长度错误: 期望8字节，实际{len(data)}字节")
                return None
                
            # 检查响应标识符
            if data[0] != 0x08:
                print(f"❌ 响应标识符错误: 期望0x08，实际0x{data[0]:02X}")
                return None
            
            # 使用struct.unpack与发送端格式保持一致
            # 格式：<Bxhhh (小端序，B=标识符0x08，x=填充字节，h=有符号16位整数)
            try:
                first_byte, x, y, z = struct.unpack('<Bxhhh', data)
                
                # 调试信息：显示原始字节和补码解析结果
                data_hex = ' '.join([f"0x{b:02X}" for b in data])
                print(f"🔍 字节解析详情:")
                print(f"   原始字节: [{data_hex}]")
                print(f"   补码解析: X={x:d}mm, Y={y:d}mm, Z={z:d}mm")
                
                # struct.unpack的'h'格式已经自动处理了16位补码转换
                # 直接返回十进制坐标值
                return (x, y, z)
                
            except struct.error as e:
                print(f"❌ struct解析失败: {e}")
                return None
            
        except Exception as e:
            print(f"❌ 坐标解析失败: {e}")
            return None
    
    def send_fruit_request(self) -> bool:
        """
        发送果位置请求
        
        Returns:
            bool: 发送是否成功
        """
        if not self.bus:
            print("❌ CAN总线未初始化")
            return False
            
        try:
            message = can.Message(
                arbitration_id=self.FRAME_ID,
                data=self.REQUEST_FRUIT_DATA,
                is_extended_id=False
            )
            self.bus.send(message)
            self.request_count += 1
            print(f"📤 发送果位置请求 #{self.request_count}")
            return True
            
        except Exception as e:
            print(f"❌ 发送请求失败: {e}")
            return False
    
    def listen_for_responses(self):
        """
        监听CAN总线响应的线程函数
        """
        print("👂 开始监听CAN总线响应...")
        
        while self.running:
            try:
                # 接收消息，超时1秒
                message = self.bus.recv(timeout=1.0)
                
                if message is None:
                    continue
                
                # 检查帧ID
                if message.arbitration_id != self.FRAME_ID:
                    continue
                
                data = list(message.data)
                
                # 先打印原始数据
                data_hex = ' '.join([f"0x{b:02X}" for b in data])
                print(f"📨 原始数据: ID=0x{message.arbitration_id:02X}, Data=[{data_hex}]")
                
                # 检查是否为果位置响应
                if len(data) == 8 and data[0] == 0x08:
                    coordinates = self.parse_fruit_coordinates(message.data)
                    if coordinates:
                        with self.coordinates_lock:
                            self.latest_coordinates = coordinates
                        self.response_count += 1
                        x, y, z = coordinates
                        print(f"🍎 解析后果位置响应 #{self.response_count}: X={x}mm, Y={y}mm, Z={z}mm")
                    else:
                        print(f"❌ 果位置数据解析失败")
                
                # 检查是否为人员警报
                elif len(data) == 8 and data == self.PERSON_ALERT_DATA:
                    self.alert_count += 1
                    print(f"🚨 解析后人员警报 #{self.alert_count}")
                
                else:
                    # 其他未知消息
                    print(f"❓ 未知消息类型，无法解析")
                    
            except Exception as e:
                if self.running:
                    print(f"❌ 监听过程中出错: {e}")
                time.sleep(0.1)
        
        print("👂 监听线程已停止")
    
    def start_listening(self):
        """
        启动监听线程
        """
        if self.listen_thread and self.listen_thread.is_alive():
            return
            
        self.running = True
        self.listen_thread = threading.Thread(target=self.listen_for_responses, daemon=True)
        self.listen_thread.start()
    
    def stop_listening(self):
        """
        停止监听线程
        """
        self.running = False
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2.0)
    
    def get_latest_coordinates(self) -> Optional[Tuple[int, int, int]]:
        """
        获取最新的坐标数据
        
        Returns:
            Tuple[int, int, int]: 最新坐标，如果没有则返回None
        """
        with self.coordinates_lock:
            return self.latest_coordinates
    
    def print_statistics(self):
        """
        打印统计信息
        """
        print(f"\n📊 统计信息:")
        print(f"   请求发送次数: {self.request_count}")
        print(f"   坐标响应次数: {self.response_count}")
        print(f"   人员警报次数: {self.alert_count}")
        
        latest = self.get_latest_coordinates()
        if latest:
            x, y, z = latest
            print(f"   最新坐标: X={x}mm, Y={y}mm, Z={z}mm")
        else:
            print(f"   最新坐标: 无")
    
    def shutdown(self):
        """
        关闭CAN控制器
        """
        print("\n🔌 正在关闭CAN控制器...")
        self.stop_listening()
        
        if self.bus:
            try:
                self.bus.shutdown()
                print("✅ CAN总线已关闭")
            except Exception as e:
                print(f"⚠️  关闭CAN总线时出现警告: {e}")

def print_help():
    """
    打印帮助信息
    """
    print("\n" + "="*60)
    print("🎮 CAN控制器 - 按键控制说明")
    print("="*60)
    print("📤 r/R     - 发送单次果位置请求")
    print("🔄 c/C     - 开始/停止连续请求模式（每2秒一次）")
    print("📊 s/S     - 显示统计信息")
    print("🍎 l/L     - 显示最新坐标")
    print("❓ h/H     - 显示此帮助信息")
    print("🚪 q/Q     - 退出程序")
    print("-"*60)

def main():
    """
    主函数
    """
    print("\n" + "="*60)
    print("🍊 CAN控制器 - 基于香橙派CAN模拟器")
    print("="*60)
    
    # 创建控制器实例
    controller = CANController()
    
    # 配置CAN接口（Linux系统）
    controller.configure_can_interface()
    
    # 初始化CAN总线
    if not controller.initialize_can_bus():
        print("❌ 无法初始化CAN总线，程序退出")
        return
    
    # 启动监听
    controller.start_listening()
    
    # 显示帮助信息
    print_help()
    
    # 连续请求模式控制
    continuous_mode = False
    continuous_thread = None
    
    def continuous_request_worker():
        """连续请求工作线程"""
        while continuous_mode and controller.running:
            controller.send_fruit_request()
            time.sleep(2.0)  # 每2秒发送一次
    
    try:
        while True:
            try:
                # 获取用户输入
                user_input = input("\n请输入命令 (h查看帮助): ").strip().lower()
                
                if user_input in ['q', 'quit', 'exit']:
                    break
                    
                elif user_input in ['r', 'request']:
                    controller.send_fruit_request()
                    
                elif user_input in ['c', 'continuous']:
                    if not continuous_mode:
                        continuous_mode = True
                        continuous_thread = threading.Thread(target=continuous_request_worker, daemon=True)
                        continuous_thread.start()
                        print("🔄 连续请求模式已启动（每2秒一次）")
                    else:
                        continuous_mode = False
                        if continuous_thread:
                            continuous_thread.join(timeout=1.0)
                        print("⏹️  连续请求模式已停止")
                        
                elif user_input in ['s', 'stats', 'statistics']:
                    controller.print_statistics()
                    
                elif user_input in ['l', 'latest']:
                    latest = controller.get_latest_coordinates()
                    if latest:
                        x, y, z = latest
                        print(f"🍎 最新坐标: X={x}mm, Y={y}mm, Z={z}mm")
                    else:
                        print("❌ 暂无坐标数据")
                        
                elif user_input in ['h', 'help']:
                    print_help()
                    
                elif user_input == '':
                    continue
                    
                else:
                    print(f"❓ 未知命令: '{user_input}'，输入 'h' 查看帮助")
                    
            except KeyboardInterrupt:
                print("\n🛑 检测到Ctrl+C，正在退出...")
                break
                
    except Exception as e:
        print(f"❌ 程序运行时出错: {e}")
        
    finally:
        # 停止连续模式
        continuous_mode = False
        if continuous_thread:
            continuous_thread.join(timeout=1.0)
            
        # 关闭控制器
        controller.shutdown()
        controller.print_statistics()
        print("👋 程序已退出")

if __name__ == "__main__":
    main()
