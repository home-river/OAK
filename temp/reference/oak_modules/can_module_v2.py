import can
import struct
import sys
import time
import threading
import subprocess
import os

"""
CAN通信模块 V2 - 支持香橙派CAN接口自动配置和智能权限处理

新增功能:
1. 自动配置香橙派can0接口的波特率和启用状态
2. 支持系统级CAN接口管理
3. 智能权限检测和sudo密码处理
4. 在初始化时自动配置，关闭时自动重置

使用方法:
- 默认启用自动配置: can_comm = CANCommunicator(shared_data, lock)
- 禁用自动配置: can_comm = CANCommunicator(shared_data, lock, auto_configure=False)
- 自定义波特率: can_comm = CANCommunicator(shared_data, lock, bitrate=250000)
- 普通用户提供sudo密码: can_comm = CANCommunicator(shared_data, lock, sudo_password="your_password")

权限处理:
1. root用户: 直接执行CAN配置命令，无需sudo
2. 普通用户 + 提供密码: 使用sudo -S自动输入密码
3. 普通用户 + 免密sudo: 使用sudo命令（需要配置sudoers）
4. 普通用户 + 无配置: 尝试交互式sudo（可能需要手动输入密码）

注意事项:
1. 自动配置功能仅在Linux系统（如香橙派）上有效
2. 普通用户需要sudo权限来配置CAN接口
3. 确保系统已安装can-utils工具包: sudo apt-get install can-utils
4. 为安全起见，建议配置sudo免密或使用systemd服务以root身份运行
"""

class CANCommunicator:
    """
    一个用于处理特定抓果车项目CAN通信的类。
    【多线程优化版】: 通过共享数据和锁与视觉线程解耦，安全地在独立线程中运行。
    """
    # --- 协议常量定义 ---
    PROTOCOL_ID = 0x30
    REQUEST_FRUIT_DATA = bytes([0x22] * 8)
    PERSON_ALERT_DATA = bytes([0x33] * 8)

    def __init__(self, shared_data: dict, lock: threading.Lock, 
                 interface: str = 'socketcan', channel: str = 'can0', bitrate: int = 250000,
                 auto_configure: bool = True, enable_alert: bool = True, sudo_password: str = "orangepi"):
        """
        初始化CAN通信器的配置。
        
        参数:
            shared_data: 共享数据字典
            lock: 线程锁
            interface: CAN接口类型，默认'socketcan'
            channel: CAN通道名称，默认'can0'
            bitrate: CAN波特率，默认250000
            auto_configure: 是否自动配置CAN接口，默认True
            enable_alert: 是否启用人员警报功能，默认True
            sudo_password: sudo密码，用于普通用户自动配置CAN接口
        """
        self.bus = None
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self.auto_configure = auto_configure
        # 默认密码为orangepi
        self.sudo_password = sudo_password
        
        # --- 核心修改：保存对共享资源和锁的引用 ---
        self.shared_data = shared_data
        self.data_lock = lock
        
        # 用于判断是否发送过"无人"状态，避免在无人时重复发送0坐标
        self._is_last_known_person_state = False

        
        # 【新增】线程控制标志
        self._running = False
        self._thread = None

        # 【新增】延时警报控制
        self.enable_alert = enable_alert
        self._person_enter_time = None  # 人员进入警报范围的时间
        self._alert_delay = 3.0  # 延迟3秒
        self._alert_started = False  # 是否已开始发送警报
        
        # 【新增】如果启用自动配置，则在初始化时配置CAN接口
        if self.auto_configure:
            self.configure_can_interface()

    def _run_sudo_command(self, cmd: list, check: bool = True) -> subprocess.CompletedProcess:
        """
        执行需要sudo权限的命令，智能处理权限和密码
        
        参数:
            cmd: 要执行的命令列表（不包含sudo）
            check: 是否检查返回码
        
        返回:
            subprocess.CompletedProcess: 命令执行结果
        """
        # 检查当前用户权限
        is_root = os.geteuid() == 0 if hasattr(os, 'geteuid') else False
        
        if is_root:
            # root用户直接执行
            full_cmd = cmd
        else:
            # 普通用户需要sudo
            if self.sudo_password:
                # 使用密码认证
                full_cmd = ['sudo', '-S'] + cmd
            else:
                # 尝试免密sudo
                full_cmd = ['sudo'] + cmd
        
        # 执行命令
        if not is_root and self.sudo_password:
            # 通过stdin传递密码
            return subprocess.run(full_cmd, 
                                input=f"{self.sudo_password}\n", 
                                text=True, 
                                check=check, 
                                capture_output=True)
        else:
            # 直接执行或免密sudo
            return subprocess.run(full_cmd, 
                                check=check, 
                                capture_output=True, 
                                text=True)

    def configure_can_interface(self) -> bool:
        """
        配置香橙派的CAN接口（can0）
        设置波特率并启用接口
        
        返回:
            bool: 配置成功返回True，失败返回False
        """
        try:
            print(f"正在配置CAN接口 {self.channel}，波特率: {self.bitrate}")
            
            # 检查是否为Linux系统
            if os.name != 'posix':
                print("警告: CAN接口配置仅支持Linux系统（如香橙派）")
                return False
            
            # 检查当前用户权限并显示状态
            is_root = os.geteuid() == 0 if hasattr(os, 'geteuid') else False
            
            if is_root:
                print("✓ 检测到root权限，直接配置CAN接口")
            else:
                if self.sudo_password:
                    print("✓ 检测到普通用户权限，使用提供的密码进行sudo认证")
                else:
                    print("⚠ 检测到普通用户权限，尝试免密sudo（可能需要交互式输入密码）")
            
            # 1. 关闭CAN接口（如果已启用）
            try:
                self._run_sudo_command(['ip', 'link', 'set', self.channel, 'down'], check=False)
                print(f"✓ 已关闭CAN接口 {self.channel}")
            except Exception as e:
                print(f"⚠ 关闭CAN接口时出现警告: {e}")
            
            # 2. 加载CAN内核模块
            try:
                self._run_sudo_command(['modprobe', 'can'], check=True)
                self._run_sudo_command(['modprobe', 'can-raw'], check=True)
                print(f"✓ 已加载CAN内核模块")
            except subprocess.CalledProcessError as e:
                print(f"⚠ 加载CAN模块失败: {e.stderr}")
                # 模块可能已加载，继续执行
            
            # 3. 设置CAN接口类型和波特率（合并为一步）
            try:
                self._run_sudo_command(['ip', 'link', 'set', self.channel, 'type', 'can', 
                                       'bitrate', str(self.bitrate)], check=True)
                print(f"✓ 已设置 {self.channel} 类型为CAN，波特率: {self.bitrate}")
            except subprocess.CalledProcessError as e:
                print(f"✗ 设置CAN接口失败: {e.stderr}")
                return False
            
            # 4. 启用CAN接口
            try:
                self._run_sudo_command(['ip', 'link', 'set', self.channel, 'up'], check=True)
                print(f"✓ 已启用CAN接口 {self.channel}")
            except subprocess.CalledProcessError as e:
                print(f"✗ 启用CAN接口失败: {e.stderr}")
                return False
            
            # 5. 验证接口状态
            try:
                result = subprocess.run(['ip', 'link', 'show', self.channel], 
                                      check=True, capture_output=True, text=True)
                if 'UP' in result.stdout:
                    print(f"✓ CAN接口 {self.channel} 配置成功并已启用")
                    return True
                else:
                    print(f"✗ CAN接口 {self.channel} 配置完成但状态异常")
                    return False
            except subprocess.CalledProcessError as e:
                print(f"✗ 验证CAN接口状态失败: {e.stderr}")
                return False
                
        except Exception as e:
            print(f"配置CAN接口时发生未知错误: {e}")
            return False

    def reset_can_interface(self) -> bool:
        """
        重置CAN接口配置
        
        返回:
            bool: 重置成功返回True，失败返回False
        """
        try:
            print(f"正在重置CAN接口 {self.channel}")
            
            # 检查是否为Linux系统
            if os.name != 'posix':
                print("警告: CAN接口重置仅支持Linux系统")
                return False
            
            # 关闭接口
            try:
                self._run_sudo_command(['ip', 'link', 'set', self.channel, 'down'], check=False)
                print(f"✓ CAN接口 {self.channel} 已关闭")
                return True
            except Exception as e:
                print(f"⚠ 关闭CAN接口时出现警告: {e}")
                return True  # 即使关闭失败也返回True，因为可能接口本来就是关闭的
            
        except Exception as e:
            print(f"重置CAN接口时发生错误: {e}")
            return False

    def start(self) -> bool:
        """
        启动并连接到CAN总线。
        """
        try:
            self.bus = can.interface.Bus(
                channel=self.channel,
                bustype=self.interface,
                bitrate=self.bitrate,
                receive_own_messages=False
            )
            print(f"成功连接到CAN总线: {self.bus.channel_info}")
            return True
        except can.CanError as e:
            print(f"错误：连接CAN总线失败: {e}", file=sys.stderr)
            print("提示：请确保硬件已连接，并在系统中正确配置接口。", file=sys.stderr)
            return False

    def _calculate_euclidean_distance(self, coords):
        """
        计算欧氏距离（从原点到目标点）
        
        参数:
            coords: 坐标字典 {'x': x, 'y': y, 'z': z} 或元组 (x, y, z)
        返回:
            float: 欧氏距离（单位：毫米）
        """
        if isinstance(coords, dict):
            x, y, z = coords.get('x', 0), coords.get('y', 0), coords.get('z', 0)
        else:
            x, y, z = coords if len(coords) >= 3 else (0, 0, 0)
        
        # 计算3D欧氏距离: √(x² + y² + z²)
        distance = (x**2 + y**2 + z**2)**0.5
        return distance

    def send_fruit_position_response(self, x: float, y: float, z: float):
        """
        根据协议，打包并发送水果位置的响应帧。
        """
        if self.bus is None:
            return
            
        try:
            packer = struct.Struct('<Bxhhh')
            x_int, y_int, z_int = int(round(x)), int(round(y)), int(round(z))
            can_data = packer.pack(0x08, x_int, y_int, z_int)
            
            message = can.Message(
                arbitration_id=self.PROTOCOL_ID,
                data=can_data,
                is_extended_id=False
            )
            self.bus.send(message)
            print(f"响应果位置: ID={hex(self.PROTOCOL_ID)}, Coords(X,Y,Z)={x_int, y_int, z_int}")
        except struct.error as e:
            print(f"错误：坐标打包失败。确保值在-32768到32767之间。Error: {e}", file=sys.stderr)
        except can.CanError as e:
            print(f"错误：发送CAN消息失败: {e}", file=sys.stderr)


    
    def send_alert(self, distance: float):
        """
        单纯发送警报的函数
        直接发送CAN人员警报消息，无任何条件判断
        
        返回:
            bool: 发送成功返回True，失败返回False
        """
        if self.bus is None:
            print("错误：CAN总线未初始化", file=sys.stderr)
            return False
        
        try:
            message = can.Message(
                arbitration_id=self.PROTOCOL_ID,
                data=self.PERSON_ALERT_DATA,
                is_extended_id=False
            )
            self.bus.send(message)
            print(f"发送CAN人员警报信号 - 距离: {distance:.1f}mm")
            return True
            
        except can.CanError as e:
            print(f"错误：发送CAN警报帧失败: {e}", file=sys.stderr)
            return False

    def send_no_fruit_waiting(self):
        """
        单纯发送警报的函数
        直接发送CAN人员警报消息，用于单片机的等待
        
        返回:
            bool: 发送成功返回True，失败返回False
        """
        if self.bus is None:
            print("错误：CAN总线未初始化", file=sys.stderr)
            return False
        
        try:
            message = can.Message(
                arbitration_id=self.PROTOCOL_ID,
                data=self.PERSON_ALERT_DATA,
                is_extended_id=False
            )
            self.bus.send(message)
            # print(f"发送CAN人员警报信号 - 距离: {distance:.1f}mm")
            return True
            
        except can.CanError as e:
            print(f"错误：发送CAN警报帧失败: {e}", file=sys.stderr)
            return False


    def send_person_alert(self, person_coords=None):
        """
        根据协议，发送"有人进入"的报警帧。
        只有当人员距离在3米（3000毫米）以内时才发送警报。
        
        参数:
            person_coords: 人员坐标，如果不提供则从共享数据中获取
        """
        if self.bus is None:
            return False
        
        # 获取人员坐标
        if person_coords is None:
            with self.data_lock:
                person_coords = self.shared_data.get('person', {'x': 0, 'y': 0, 'z': 0})
        
        # 计算欧氏距离
        distance = self._calculate_euclidean_distance(person_coords)
        
        # 只有在3米（3000毫米）以内，时间超过规定值才发送警报
        if distance > 0 and distance <= 3000:
            try:
                message = can.Message(
                    arbitration_id=self.PROTOCOL_ID,
                    data=self.PERSON_ALERT_DATA,
                    is_extended_id=False
                )
                self.bus.send(message)
                print(f"发送人员报警信号 - 距离: {distance:.1f}mm")
                return True
            except can.CanError as e:
                print(f"错误：发送报警帧失败: {e}", file=sys.stderr)
                return False
        else:
            # 距离超出警报范围，不发送
            if distance > 3000:
                # 可选：打印调试信息
                # print(f"人员距离{distance:.1f}mm超出警报范围(3000mm)，不发送警报")
                pass
            return False


    def listen_and_process(self):
        """
        持续监听总线，并根据共享数据处理消息。
        """
        if not self.bus:
            print("错误：无法监听，总线未启动。", file=sys.stderr)
            return
        
        print("CAN通信线程已启动，开始监听和处理...")
        last_alert_time = 0
        
        while self._running:
            try:
                # 检查总线是否仍然有效
                if not self.bus or not self._running:
                    break
                
                # --- 1. 主动报警逻辑 (基于共享数据和距离判断) ---
                with self.data_lock:
                    person_coords = self.shared_data.get('person', {'x': 0, 'y': 0, 'z': 0})
                
                # 计算距离并判断是否需要发送警报
                distance = self._calculate_euclidean_distance(person_coords)
                is_person_in_alert_range = (distance > 0 and distance <= 5000)
                
                # # 状态机：仅在人员进入警报范围时发送
                # if is_person_in_alert_range:
                #     if time.time() - last_alert_time > 0.1:  # 每100ms发送一次
                #         if self.send_person_alert(person_coords):
                #             last_alert_time = time.time()
                #     self._is_last_known_person_state = True
                # elif self._is_last_known_person_state:
                #     print("人员已离开警报区域")
                #     self._is_last_known_person_state = False
                if self.enable_alert:
                    if is_person_in_alert_range:
                        if self._person_enter_time is None:
                            # 首次进入，开始计时
                            self._person_enter_time = time.time()
                            print(f"人员进入警戒范围，距离: {distance:.1f}mm，开始计时...")
                        elif not self._alert_started:
                            # 检查是否超过延迟时间
                            elapsed_time = time.time() - self._person_enter_time
                            if elapsed_time >= self._alert_delay:
                                print(f"延时{self._alert_delay}秒已到，开始发送警报")
                                self._alert_started = True
                            else:
                                # 显示倒计时（每秒显示一次）
                                # 如果当前秒数 != 上次打印的秒数
                                if int(elapsed_time) != getattr(self, '_last_print_second', -1):
                                    print(f"人员停留中，距离: {distance:.1f}mm，剩余时间: {self._alert_delay - elapsed_time:.1f}秒")
                                    self._last_print_second = int(elapsed_time)
                        
                        # 如果已开始警报，持续发送
                        if self._alert_started and time.time() - last_alert_time > 0.1:
                            self.send_alert(distance)
                            last_alert_time = time.time()
                    else:
                        # 人员离开警报范围，重置所有状态
                        if self._person_enter_time is not None:
                            elapsed_time = time.time() - self._person_enter_time
                            alert_status = "已发送警报" if self._alert_started else "未发送警报"
                            print(f"人员离开警戒范围，总停留时间: {elapsed_time:.1f}秒，{alert_status}")
                        
                        self._person_enter_time = None
                        self._alert_started = False
                        self._last_print_second = -1

                # --- 2. 被动响应逻辑 ---
                # 再次检查总线状态，避免在关闭过程中访问
                if not self.bus or not self._running:
                    break
                    
                try:
                    message = self.bus.recv(timeout=0.01)
                except (AttributeError, can.CanError):
                    # 总线已关闭或出现错误，退出循环
                    break
                
                if message is not None:
                    # 调试：打印收到的消息信息
                    if message.arbitration_id == self.PROTOCOL_ID:
                        print(f"收到帧 -> ID={hex(message.arbitration_id)} dlc={len(message.data)} data={list(message.data)}")
                    
                    # 参考stable1.0的匹配方式：ID匹配 + DLC=8 + 数据内容为8个0x22
                    if (
                        message.arbitration_id == self.PROTOCOL_ID and
                        len(message.data) == 8 and
                        list(message.data) == [0x22] * 8
                    ):
                        print("收到果位置请求...")
                        
                        with self.data_lock:
                            fruit_coords = self.shared_data.get('durian', {'x': 0, 'y': 0, 'z': 0})
                            if isinstance(fruit_coords, dict):
                                x, y, z = fruit_coords['x'], fruit_coords['y'], fruit_coords['z']
                            else:
                                x, y, z = fruit_coords
                        
                        if not (x == 0 and y == 0 and z == 0):
                            self.send_fruit_position_response(x, y, z)
                        else:
                            self.send_fruit_position_response(0.0, 0.0, 0.0)
                            print("警告：收到了请求，但没有可用的果坐标，已回复(0,0,0)。")
                            # self.send_no_fruit_waiting()
                            
            except can.CanError as e:
                if self._running and "Network is down" not in str(e):
                    print(f"CAN网络错误: {e}", file=sys.stderr)
                break  # CAN网络错误时退出循环
            except AttributeError as e:
                if self._running and "'NoneType'" in str(e):
                    # 总线已被设置为None，正常退出
                    break
                else:
                    print(f"CAN属性错误: {e}", file=sys.stderr)
                    break
            except Exception as e:
                if self._running:
                    print(f"CAN通信处理错误: {e}", file=sys.stderr)
                time.sleep(0.01)
        
        print("CAN通信线程正常退出")

    
    # 【新增】启动线程方法
    def start_thread(self):
        """
        在独立线程中启动CAN通信
        """
        if not self.start():
            return False
            
        self._running = True
        self._thread = threading.Thread(target=self.listen_and_process, name="CAN-Communication")
        self._thread.daemon = True
        self._thread.start()
        print("CAN通信线程已启动")
        return True
    
    # 【新增】停止线程方法
    def stop_thread(self):
        """
        停止CAN通信线程
        """
        print("正在停止CAN通信线程...")
        self._running = False
        
        # 等待线程结束
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                print("警告: CAN通信线程未能在超时时间内停止")
            else:
                print("CAN通信线程已停止")
        
        # 清理资源
        self.shutdown()
    
    def shutdown(self):
        """
        安全地关闭CAN总线连接，并可选择性地重置CAN接口。
        """
        self._running = False
        
        # 安全关闭CAN总线
        if self.bus:
            try:
                self.bus.shutdown()
                print("CAN总线已关闭。")
            except Exception as e:
                print(f"关闭CAN总线时出现警告: {e}")
            finally:
                self.bus = None  # 确保总线引用被清空
        
        # 如果启用了自动配置，在关闭时重置接口
        if self.auto_configure:
            self.reset_can_interface()
            self.bus = None
