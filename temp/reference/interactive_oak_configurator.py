#!/usr/bin/env python3

"""
交互式OAK设备配置脚本
自动发现OAK设备，交互式输入坐标变换参数，保存配置文件
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 添加oak_modules路径
sys.path.append(str(Path(__file__).parent.parent.parent / "oak_modules"))
from oak_modules import OAKDeviceManager


class InteractiveOAKConfigurator:
    """交互式OAK设备配置器"""
    
    def __init__(self):
        self.config_dir = Path(__file__).parent / "configs"
        self.config_dir.mkdir(exist_ok=True)
        self.manager = None
        self.discovered_devices = []
        
    def print_header(self):
        """打印程序头部信息"""
        print("=" * 60)
        print("交互式OAK设备配置工具")
        print("=" * 60)
    
    def discover_devices(self) -> bool:
        """自动发现OAK设备"""
        print("\n正在扫描连接的OAK设备...")
        
        # 创建临时管理器用于设备发现
        temp_config = self.config_dir / "temp_discovery.json"
        self.manager = OAKDeviceManager(str(temp_config))
        
        try:
            self.discovered_devices = self.manager.list_connected()
            
            if not self.discovered_devices:
                print("未发现任何OAK设备")
                print("\n请检查:")
                print("  1. OAK设备是否正确连接到USB端口")
                print("  2. USB线缆是否支持数据传输")
                print("  3. 设备驱动是否正确安装")
                print("  4. 是否有其他程序占用设备")
                return False
            
            print(f"\n发现 {len(self.discovered_devices)} 个OAK设备:")
            print("-" * 40)
            
            for i, device in enumerate(self.discovered_devices):
                print(f"设备 {i+1}: {device['mxid']}")
            
            return True
            
        except Exception as e:
            print(f"设备发现失败: {e}")
            return False
        finally:
            # 清理临时配置文件
            if temp_config.exists():
                temp_config.unlink()
    
    def get_float_input(self, prompt: str, default: float, min_val: float = None, max_val: float = None) -> float:
        """获取浮点数输入，带验证"""
        while True:
            try:
                range_info = ""
                if min_val is not None and max_val is not None:
                    range_info = f" (范围: {min_val} ~ {max_val})"
                elif min_val is not None:
                    range_info = f" (最小值: {min_val})"
                elif max_val is not None:
                    range_info = f" (最大值: {max_val})"
                
                user_input = input(f"{prompt} [默认: {default}]{range_info}: ").strip()
                
                if not user_input:
                    return default
                
                value = float(user_input)
                
                # 范围验证
                if min_val is not None and value < min_val:
                    print(f"输入值 {value} 小于最小值 {min_val}，请重新输入")
                    continue
                if max_val is not None and value > max_val:
                    print(f"输入值 {value} 大于最大值 {max_val}，请重新输入")
                    continue
                
                return value
                
            except ValueError:
                print("请输入有效的数字")
    
    def get_string_input(self, prompt: str, default: str = "") -> str:
        """获取字符串输入"""
        user_input = input(f"{prompt} [默认: {default}]: ").strip()
        return user_input if user_input else default
    
    def configure_device_parameters(self, device_info: Dict, device_index: int) -> Tuple[str, Dict]:
        """为单个设备配置参数"""
        mxid = device_info['mxid']
        
        print(f"\n配置设备 {device_index + 1}")
        print(f"MXid: {mxid}")
        print("-" * 40)
        
        # 设备别名
        default_alias = f"oak_device_{device_index + 1}"
        alias = self.get_string_input("设备别名", default_alias)
        
        print(f"\n坐标变换参数配置:")
        print("提示: 直接按回车使用默认值")
        
        # 坐标变换参数 - 基于记忆中的参数范围
        kinematics = {}
        
        print(f"\n平移参数 (单位: mm):")
        kinematics['Tx'] = self.get_float_input("  Tx (X轴平移)", -1500.0, -3000.0, 3000.0)
        kinematics['Ty'] = self.get_float_input("  Ty (Y轴平移)", -760.0, -3000.0, 3000.0)
        kinematics['Tz'] = self.get_float_input("  Tz (Z轴平移)", 1200.0, 0.0, 5000.0)
        
        print(f"\n旋转参数 (单位: 度):")
        kinematics['Ry'] = self.get_float_input("  Ry (Y轴旋转)", 22.9, -180.0, 180.0)
        kinematics['Rz'] = self.get_float_input("  Rz (Z轴旋转)", -25.2, -180.0, 180.0)
        
        # 显示配置摘要
        print(f"\n设备 {device_index + 1} 配置摘要:")
        print(f"  别名: {alias}")
        print(f"  平移: Tx={kinematics['Tx']:.1f}, Ty={kinematics['Ty']:.1f}, Tz={kinematics['Tz']:.1f}")
        print(f"  旋转: Ry={kinematics['Ry']:.1f}, Rz={kinematics['Rz']:.1f}")
        
        # 确认配置
        while True:
            confirm = input(f"\n确认此配置? (y/n) [默认: y]: ").strip().lower()
            if confirm in ['', 'y', 'yes', '是']:
                break
            elif confirm in ['n', 'no', '否']:
                print("重新配置此设备...")
                return self.configure_device_parameters(device_info, device_index)
            else:
                print("请输入 y 或 n")
        
        return alias, kinematics
    
    def configure_filter_parameters(self) -> Dict:
        """配置滤波参数"""
        print(f"\n滤波参数配置:")
        print("-" * 30)
        
        # 滤波类型选择
        filter_types = {
            '1': 'moving_average',
            '2': 'exponential',
            '3': 'adaptive_exponential'
        }
        
        print("选择滤波类型:")
        print("  1. 滑动平均滤波 (moving_average) - 推荐")
        print("  2. 指数滤波 (exponential)")
        print("  3. 自适应指数滤波 (adaptive_exponential)")
        
        while True:
            choice = input("请选择 (1-3) [默认: 1]: ").strip()
            if not choice:
                choice = '1'
            
            if choice in filter_types:
                filter_type = filter_types[choice]
                break
            else:
                print("请输入 1、2 或 3")
        
        # 滤波窗口大小
        if filter_type == 'moving_average':
            window_size = int(self.get_float_input("滤波窗口大小", 5, 1, 20))
        else:
            window_size = 5  # 其他滤波类型使用默认值
        
        filter_config = {
            'type': filter_type,
            'window': window_size
        }
        
        print(f"滤波配置: {filter_type}, 窗口大小: {window_size}")
        return filter_config
    
    def get_config_filename(self) -> str:
        """获取配置文件名"""
        print(f"\n配置文件名设置:")
        print("-" * 30)
        
        default_filename = "dual_oak_config.json"
        filename = self.get_string_input("配置文件名", default_filename)
        
        # 确保文件名以.json结尾
        if not filename.endswith('.json'):
            filename += '.json'
        
        print(f"配置文件名: {filename}")
        return filename
    
    def save_configuration(self, device_configs: List[Tuple[str, str, Dict]], filter_config: Dict, config_filename: str) -> bool:
        """保存配置到文件"""
        print(f"\n保存配置文件...")
        
        try:
            config_path = self.config_dir / config_filename
            
            # 手动构建正确的配置格式
            config_data = {
                "config_version": "1.0.0",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "filter": filter_config,
                "devices": {}
            }
            
            # 将设备配置转换为字典格式（以MXid为key）
            for alias, mxid, kinematics in device_configs:
                config_data["devices"][mxid] = {
                    "alias": alias,
                    "kinematics": kinematics
                }
            
            # 直接保存配置数据
            import json
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            print(f"配置已保存到: {config_path}")
            return True
                
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def run(self):
        """运行交互式配置流程"""
        self.print_header()
        
        # 1. 发现设备
        if not self.discover_devices():
            return
        
        # 2. 确认开始配置
        print(f"\n准备为 {len(self.discovered_devices)} 个设备配置参数")
        input("按回车键开始配置...")
        
        # 3. 逐个配置设备
        device_configs = []
        
        for i, device in enumerate(self.discovered_devices):
            alias, kinematics = self.configure_device_parameters(device, i)
            device_configs.append((alias, device['mxid'], kinematics))
        
        # 4. 配置滤波参数
        filter_config = self.configure_filter_parameters()
        
        # 5. 获取配置文件名
        config_filename = self.get_config_filename()
        
        # 6. 显示完整配置摘要
        print(f"\n" + "=" * 60)
        print(f"完整配置摘要")
        print(f"=" * 60)
        
        print(f"设备配置 ({len(device_configs)} 个设备):")
        for i, (alias, mxid, kinematics) in enumerate(device_configs):
            print(f"  设备 {i+1}: {alias}")
            print(f"    MXid: {mxid[:20]}...")
            print(f"    平移: Tx={kinematics['Tx']:.1f}, Ty={kinematics['Ty']:.1f}, Tz={kinematics['Tz']:.1f}")
            print(f"    旋转: Ry={kinematics['Ry']:.1f}, Rz={kinematics['Rz']:.1f}")
        
        print(f"\n滤波配置:")
        print(f"  类型: {filter_config['type']}")
        print(f"  窗口: {filter_config['window']}")
        
        # 7. 最终确认并保存
        while True:
            confirm = input(f"\n确认保存配置? (y/n) [默认: y]: ").strip().lower()
            if confirm in ['', 'y', 'yes', '是']:
                if self.save_configuration(device_configs, filter_config, config_filename):
                    print(f"\n配置完成!")
                    print(f"配置文件位置: {self.config_dir}")
                else:
                    print(f"\n配置保存失败")
                break
            elif confirm in ['n', 'no', '否']:
                print(f"\n配置已取消")
                break
            else:
                print("请输入 y 或 n")


def main():
    """主函数"""
    try:
        configurator = InteractiveOAKConfigurator()
        configurator.run()
        
    except KeyboardInterrupt:
        print(f"\n\n配置被用户中断")
    except Exception as e:
        print(f"\n配置过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
