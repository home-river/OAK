#!/usr/bin/env python3

"""
OAK设备配置管理模块 
"""

import json
import depthai as dai
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import tempfile
import os


class OAKDeviceManager:
    """OAK设备配置管理器"""
    
    def __init__(self, config_path: str = None):
        """
        初始化设备管理器
        
        Args:
            config_path: 配置文件路径
        """
        # 配置文件路径
        if config_path is not None: 

            self.config_path = Path(config_path)

        else:
            self.config_path = Path(__file__).parent/"config/OAK_config.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 内存中的配置数据
        self.config = {
            "config_version": "1.0.0",
            "updated_at": "",
            "filter": {"type": "moving_average", "window": 5},
            "devices": []
        }
        
        # 设备别名到MXid的双向映射
        self._alias_to_mxid: Dict[str, str] = {}
        self._mxid_to_alias: Dict[str, str] = {}
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    # ==================== 设备发现 ====================
    
    def list_connected(self) -> List[Dict[str, Any]]:
        """
        列出已连接的OAK设备
        
        Returns:
            设备信息列表 [{mxid, name?, state?}, ...]
        """
        devices = []
        try:
            # 获取所有可用设备
            for device_info in dai.Device.getAllAvailableDevices():
                device_data = {
                    "mxid": device_info.getMxId(),  
                    "name": getattr(device_info, 'name', device_info.name if hasattr(device_info, 'name') else None),
                    "state": device_info.state.name if hasattr(device_info.state, 'name') else str(device_info.state)
                }
                devices.append(device_data)
                
            print(f"发现 {len(devices)} 个OAK设备")
            return devices
            
        except Exception as e:
            print(f"设备发现失败: {e}")
            return []
    
    # ==================== 配置创建 ====================
    
    def create_new_config(self, 
                         mxids: List[str],
                         aliases: List[str], 
                         kinematics_list: List[Dict[str, float]],
                         filter_type: str = "moving_average",
                         filter_window: int = 10) -> None:
        """
        创建新的配置，自动为不同设备绑定坐标变换参数
        
        Args:
            mxids: 设备MXid列表
            aliases: 设备别名列表，与mxids一一对应
            kinematics_list: 外参配置列表，与设备一一对应
            filter_type: 滤波类型，默认"moving_average"
            filter_window: 滤波窗口大小，默认10
        
        Example:
            manager.create_new_config(
                mxids=["MXID_LEFT_ABCDEFG123", "MXID_RIGHT_HIJKLMN456"],
                aliases=["left_oak", "right_oak"],
                kinematics_list=[
                    {"Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Ry": 22.9, "Rz": -25.2},
                    {"Tx": -1600.0, "Ty": -800.0, "Tz": 1250.0, "Ry": 25.0, "Rz": -30.0}
                ]
            )
        """
        # 参数长度校验
        if len(mxids) != len(aliases):
            raise ValueError(f"MXid数量({len(mxids)})与别名数量({len(aliases)})不匹配")
        if len(mxids) != len(kinematics_list):
            raise ValueError(f"MXid数量({len(mxids)})与外参配置数量({len(kinematics_list)})不匹配")
        
        # 重置配置
        self.config = {
            "config_version": "1.0.0",
            "updated_at": "",
            "filter": {"type": filter_type, "window": filter_window},
            "devices": []
        }
        
        # 清空别名映射
        self._alias_to_mxid.clear()
        self._mxid_to_alias.clear()
        
        # 添加设备配置
        for i, (mxid, alias, kinematics) in enumerate(zip(mxids, aliases, kinematics_list)):
            # 校验必要字段
            if not mxid or not isinstance(mxid, str):
                raise ValueError(f"第{i+1}个设备的MXid无效: {mxid}")
            if not alias or not isinstance(alias, str):
                raise ValueError(f"第{i+1}个设备的别名无效: {alias}")
            
            # 检查重复
            if alias in self._alias_to_mxid:
                raise ValueError(f"别名 '{alias}' 重复")
            if mxid in self._mxid_to_alias:
                raise ValueError(f"MXid '{mxid}' 重复")
            
            # 校验外参字段
            if not isinstance(kinematics, dict):
                raise ValueError(f"设备 {alias} 的外参配置必须是字典类型")
            
            valid_fields = {"Tx", "Ty", "Tz", "Ry", "Rz"}
            for field, value in kinematics.items():
                if field not in valid_fields:
                    raise ValueError(f"设备 {alias} 包含无效外参字段: {field}")
                if not isinstance(value, (int, float)):
                    raise ValueError(f"设备 {alias} 外参 {field} 必须是数值: {value}")
            
            # 添加设备配置
            self.config["devices"].append({
                "mxid": mxid,
                "alias": alias,
                "kinematics": {k: float(v) for k, v in kinematics.items()}
            })
            
            # 更新别名映射
            self._alias_to_mxid[alias] = mxid
            self._mxid_to_alias[mxid] = alias
        
        self.logger.info(f"已创建包含 {len(mxids)} 个设备的新配置")
    
    def add_device_config(self, mxid: str, alias: str, 
                         Tx: float = 0.0, Ty: float = 0.0, Tz: float = 0.0,
                         Ry: float = 0.0, Rz: float = 0.0) -> None:
        """
        添加单个设备配置的便捷方法
        
        Args:
            mxid: 设备MXid
            alias: 设备别名
            Tx, Ty, Tz: 平移参数
            Ry, Rz: 旋转参数
        
        Example:
            manager.add_device_config("MXID_LEFT_123", "left_oak", 
                                    Tx=-1500.0, Ty=-760.0, Tz=1200.0, Ry=22.9, Rz=-25.2)
        """
        kinematics = {"Tx": Tx, "Ty": Ty, "Tz": Tz, "Ry": Ry, "Rz": Rz}
        
        # 如果是第一个设备，初始化配置
        if not self.config.get("devices"):
            self.config = {
                "config_version": "1.0.0",
                "updated_at": "",
                "filter": self.config.get("filter", {"type": "moving_average", "window": 5}),
                "devices": []
            }
        
        # 校验重复
        if alias in self._alias_to_mxid:
            raise ValueError(f"别名 '{alias}' 已存在")
        if mxid in self._mxid_to_alias:
            raise ValueError(f"MXid '{mxid}' 已存在")
        
        # 添加设备
        self.config["devices"].append({
            "mxid": mxid,
            "alias": alias,
            "kinematics": kinematics
        })
        
        # 更新映射
        self._alias_to_mxid[alias] = mxid
        self._mxid_to_alias[mxid] = alias
        
        self.logger.info(f"已添加设备配置: {alias} ({mxid})")
    
    def auto_bind_devices(self, device_aliases: Dict[str, str], 
                         default_kinematics: Optional[Dict[str, Dict[str, float]]] = None) -> List[Dict[str, Any]]:
        """
        自动发现并绑定连接的设备
        
        Args:
            device_aliases: MXid到别名的映射 {"MXID_xxx": "alias_name"}
            default_kinematics: 默认外参配置 {"alias_name": {"Tx": -1500.0, ...}}
            
        Returns:
            成功绑定的设备列表
        """
        connected_devices = self.list_connected()
        bound_devices = []
        
        for device in connected_devices:
            mxid = device["mxid"]
            if mxid in device_aliases:
                alias = device_aliases[mxid]
                
                try:
                    # 绑定别名
                    self.bind_alias(mxid, alias)
                    
                    # 设置默认外参（如果提供）
                    if default_kinematics and alias in default_kinematics:
                        self.set_kinematics(alias, **default_kinematics[alias])
                    
                    bound_devices.append({
                        "mxid": mxid,
                        "alias": alias,
                        "state": device["state"]
                    })
                    
                    self.logger.info(f"已绑定设备: {mxid} -> {alias}")
                    
                except ValueError as e:
                    self.logger.warning(f"绑定设备 {mxid} 失败: {e}")
        
        return bound_devices
    
    def create_interactive_config(self, 
                                 kinematics_presets: Dict[str, Dict[str, float]],
                                 filter_config: Optional[Dict[str, Any]] = None) -> bool:
        """
        交互式创建配置：发现设备 -> 终端选择绑定 -> 自动配置
        
        Args:
            kinematics_presets: 预设的坐标变换参数 {"preset_name": {"Tx": -1500.0, ...}}
            filter_config: 滤波配置，默认为 {"type": "moving_average", "window": 5}
            
        Returns:
            是否成功创建配置
            
        Example:
            kinematics_presets = {
                "left_position": {"Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Rx": 0.0, "Ry": 22.9, "Rz": -25.2},
                "right_position": {"Tx": -1600.0, "Ty": -800.0, "Tz": 1250.0, "Rx": 0.0, "Ry": 25.0, "Rz": -30.0}
            }
        """
        print("=== 交互式OAK配置创建 ===")
        
        # 1. 发现连接的设备
        print("\n🔍 正在发现连接的OAK设备...")
        connected_devices = self.list_connected()
        
        if not connected_devices:
            print("❌ 未发现任何OAK设备，请检查设备连接")
            return False
        
        print(f"✅ 发现 {len(connected_devices)} 个OAK设备:")
        for i, device in enumerate(connected_devices):
            print(f"  [{i+1}] MXid: {device['mxid'][:20]}... 状态: {device['state']}")
        
        # 2. 显示可用的坐标变换预设
        print(f"\n📐 可用的坐标变换预设:")
        preset_list = list(kinematics_presets.keys())
        for i, preset_name in enumerate(preset_list):
            preset = kinematics_presets[preset_name]
            print(f"  [{i+1}] {preset_name}:")
            print(f"      平移: Tx={preset.get('Tx', 0):.1f}, Ty={preset.get('Ty', 0):.1f}, Tz={preset.get('Tz', 0):.1f}")
            print(f"      旋转: Rx={preset.get('Rx', 0):.1f}, Ry={preset.get('Ry', 0):.1f}, Rz={preset.get('Rz', 0):.1f}")
        
        # 3. 交互式绑定
        device_configs = []
        used_aliases = set()
        
        for i, device in enumerate(connected_devices):
            mxid = device['mxid']
            print(f"\n🔧 配置设备 [{i+1}]: {mxid[:20]}...")
            
            # 选择别名
            while True:
                alias = input(f"  请输入设备别名 (如: left_oak, right_oak): ").strip()
                if not alias:
                    print("  ❌ 别名不能为空")
                    continue
                if alias in used_aliases:
                    print(f"  ❌ 别名 '{alias}' 已被使用")
                    continue
                used_aliases.add(alias)
                break
            
            # 选择坐标变换预设
            while True:
                try:
                    preset_choice = input(f"  选择坐标变换预设 [1-{len(preset_list)}] (或输入 's' 跳过): ").strip()
                    
                    if preset_choice.lower() == 's':
                        print(f"  ⏭️  跳过设备 {alias} 的坐标变换配置")
                        device_configs.append({
                            "mxid": mxid,
                            "alias": alias,
                            "kinematics": {}
                        })
                        break
                    
                    preset_idx = int(preset_choice) - 1
                    if 0 <= preset_idx < len(preset_list):
                        preset_name = preset_list[preset_idx]
                        selected_preset = kinematics_presets[preset_name]
                        
                        print(f"  ✅ 已选择预设 '{preset_name}' 用于设备 '{alias}'")
                        device_configs.append({
                            "mxid": mxid,
                            "alias": alias,
                            "kinematics": selected_preset.copy()
                        })
                        break
                    else:
                        print(f"  ❌ 请输入 1-{len(preset_list)} 之间的数字")
                        
                except ValueError:
                    print(f"  ❌ 请输入有效的数字 (1-{len(preset_list)}) 或 's'")
        
        # 4. 确认配置
        print(f"\n📋 配置摘要:")
        for config in device_configs:
            print(f"  • {config['alias']}: {config['mxid'][:20]}...")
            if config['kinematics']:
                preset = config['kinematics']
                print(f"    坐标变换: Tx={preset.get('Tx', 0):.1f}, Ty={preset.get('Ty', 0):.1f}, Tz={preset.get('Tz', 0):.1f}")
            else:
                print(f"    坐标变换: 未配置")
        
        confirm = input(f"\n❓ 确认创建此配置? [y/N]: ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ 配置创建已取消")
            return False
        
        # 5. 创建配置
        try:
            # 提取参数列表
            mxids = [config['mxid'] for config in device_configs]
            aliases = [config['alias'] for config in device_configs]
            kinematics_list = [config['kinematics'] for config in device_configs]
            
            # 使用新的参数结构
            self.create_new_config(
                mxids=mxids,
                aliases=aliases,
                kinematics_list=kinematics_list,
                filter_type=filter_config.get('type', 'moving_average'),
                filter_window=filter_config.get('window', 5)
            )
            print("✅ 交互式配置创建成功!")
            
            # 自动保存
            save_confirm = input("💾 是否立即保存配置? [Y/n]: ").strip().lower()
            if save_confirm not in ['n', 'no']:
                if self.validate():
                    self.save()
                    print("✅ 配置已保存")
                else:
                    print("❌ 配置校验失败")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ 配置创建失败: {e}")
            return False
    
    # ==================== 绑定管理 ====================
    
    def bind_alias(self, mxid: str, alias: str) -> None:
        """
        将MXid与alias双向绑定
        
        Args:
            mxid: 设备MXid
            alias: 设备别名

        Raises:
            ValueError: 当别名或MXid已被使用时
        """

        # 检查是否已初始化
        if not hasattr(self, "_alias_to_mxid"):
            self._alias_to_mxid = {}
        if not hasattr(self, "_mxid_to_alias"):
            self._mxid_to_alias = {}

        # 校验输入
        if not isinstance(mxid, str) or not mxid or len(mxid) < 10:
            raise ValueError("MXid不能为空且长度需≥10")
        if not isinstance(alias, str) or not alias:
            raise ValueError("alias不能为空")

        # 检查别名是否已被占用
        if alias in self._alias_to_mxid:
            raise ValueError(f"别名 '{alias}' 已被绑定到MXid '{self._alias_to_mxid[alias]}'")
        # 检查MXid是否已被占用
        if mxid in self._mxid_to_alias:
            raise ValueError(f"MXid '{mxid}' 已被绑定到别名 '{self._mxid_to_alias[mxid]}'")

        # 绑定
        self._alias_to_mxid[alias] = mxid
        self._mxid_to_alias[mxid] = alias
    
    def get_mxid(self, alias: str) -> Optional[str]:
        """
        根据别名获取MXid
        
        Args:
            alias: 设备别名
            
        Returns:
            MXid或None
        """
        return self._alias_to_mxid.get(alias)
    
    def get_alias(self, mxid: str) -> Optional[str]:
        """
        根据MXid获取别名
        
        Args:
            mxid: 设备MXid
            
        Returns:
            别名或None
        """
        return self._mxid_to_alias.get(mxid)
    
    # ==================== 配置生命周期 ====================
    
    def load(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        从JSON加载配置
        
        Args:
            path: 配置文件路径，默认使用初始化时的路径
            
        Returns:
            加载的配置数据
        """
        try:
            with open(path or self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # 同步配置到实例变量
            self._sync_config_to_variables()
            
            return self.config
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            return None
    
    def _sync_config_to_variables(self) -> None:
        """将配置数据同步到实例变量"""
        if not self.config:
            return
            
        # 重建别名映射字典
        self._alias_to_mxid.clear()
        self._mxid_to_alias.clear()
        
        devices = self.config.get('devices', [])
        for device_config in devices:
            mxid = device_config.get('mxid')
            alias = device_config.get('alias')
            if mxid and alias:
                self._alias_to_mxid[alias] = mxid
                self._mxid_to_alias[mxid] = alias
    
    def save(self, path: Optional[str] = None, atomic: bool = True) -> None:
        """
        保存配置到JSON文件
        
        Args:
            path: 配置文件路径，默认使用初始化时的路径
            atomic: 是否使用原子化写入
        """
        target_path = Path(path) if path else self.config_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 更新时间戳
        self.config["updated_at"] = datetime.now().isoformat()
        
        try:
            if atomic:
                # 使用原子化写入
                with tempfile.NamedTemporaryFile(
                    mode='w', 
                    encoding='utf-8', 
                    dir=target_path.parent, 
                    delete=False,
                    suffix='.tmp'
                ) as temp_file:
                    json.dump(self.config, temp_file, indent=2, ensure_ascii=False)
                    temp_path = temp_file.name
                
                # 原子化替换
                os.replace(temp_path, target_path)
            else:
                # 直接写入
                with open(target_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
                    
            self.logger.info(f"配置已保存到: {target_path}")
            
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            # 清理临时文件
            if atomic and 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            raise
    
    # ==================== 配置读取接口 ====================
    
    def get_device(self, alias_or_mxid: str) -> Optional[Dict[str, Any]]:
        """
        按alias或MXid获取设备配置
        
        Args:
            alias_or_mxid: 设备别名或MXid
            
        Returns:
            设备配置字典或None
        """
        # 先尝试作为别名查找MXid
        mxid = self.get_mxid(alias_or_mxid)
        if mxid is None:
            # 如果不是别名，直接作为MXid使用
            mxid = alias_or_mxid
            
        # 在设备数组中查找匹配的mxid
        devices = self.config.get("devices", [])
        for device in devices:
            if device.get("mxid") == mxid:
                return device
        return None
    
    def get_kinematics(self, alias_or_mxid: str) -> Dict[str, float]:
        """
        读取设备外参
        
        Args:
            alias_or_mxid: 设备别名或MXid
            
        Returns:
            外参字典 {Tx, Ty, Tz, Rx, Ry, Rz}
        """
        device_config = self.get_device(alias_or_mxid)
        if device_config is None:
            raise ValueError(f"设备 {alias_or_mxid} 不存在")
        
        kinematics = device_config.get("kinematics")
        if kinematics is None:
            raise ValueError(f"设备 {alias_or_mxid} 的外参配置不存在")
        
        return kinematics

    def plot_all_config(self):
        """
        打印所有配置
        """
        print(self.config)
        
    
    def get_filter(self) -> Dict[str, Any]:
        """
        读取全局滤波参数
        
        Returns:
            滤波参数字典 {type, window}
        """
        filter_config = self.config.get("filter", {})
        return filter_config
    
    # ==================== 配置修改接口 ====================
    
    def set_kinematics(self, alias_or_mxid: str, **fields) -> None:
        """
        更新设备外参
        
        Args:
            alias_or_mxid: 设备别名或MXid
            **fields: 外参字段 (Tx, Ty, Tz, Rx, Ry, Rz)
        """
        # 先尝试作为别名查找MXid
        mxid = self.get_mxid(alias_or_mxid)
        if mxid is None:
            # 如果不是别名，直接作为MXid使用
            mxid = alias_or_mxid
            
        # 查找现有设备
        device_config = self.get_device(mxid)
        if device_config is None:
            # 如果设备不存在，创建新设备配置
            device_config = {
                "mxid": mxid,
                "alias": self.get_alias(mxid),
                "kinematics": {}
            }
            self.config["devices"].append(device_config)
            
        # 更新外参
        kinematics = device_config.setdefault("kinematics", {})
        valid_fields = {"Tx", "Ty", "Tz", "Ry", "Rz"}
        
        for field, value in fields.items():
            if field not in valid_fields:
                raise ValueError(f"无效的外参字段: {field}，有效字段: {valid_fields}")
            if not isinstance(value, (int, float)):
                raise ValueError(f"外参 {field} 必须是数值类型，得到: {type(value)}")
            kinematics[field] = float(value)
    
    def set_filter(self, type: Optional[str] = None, window: Optional[int] = None) -> None:
        """
        更新全局滤波参数
        
        Args:
            type: 滤波类型 ("moving_average", "median")当前只有moving_average
            window: 滤波窗口大小 (1~101)
        """
        # 确保滤波配置存在，不存在则创建默认配置
        filter_config = self.config.setdefault("filter", {"type": "moving_average", "window": 10})
        
        if type is not None:
            filter_config["type"] = type
        if window is not None:
            filter_config["window"] = window
    
    def validate(self) -> bool:
        """
        校验当前配置
        
        Returns:
            配置是否有效
            
        Raises:
            ValueError: 配置无效时抛出详细错误信息
        """
        # 校验配置版本
        if "config_version" not in self.config:
            raise ValueError("缺少配置版本号")
            
        # 校验滤波配置
        filter_config = self.config.get("filter", {})
        if "type" in filter_config:
            valid_types = {"moving_average",}
            if filter_config["type"] not in valid_types:
                raise ValueError(f"无效的滤波类型: {filter_config['type']}\n当前仅支持{valid_types}")
                
        if "window" in filter_config:
            window = filter_config["window"]
            if not isinstance(window, int) or window < 1 or window > 101:
                raise ValueError(f"无效的滤波窗口: {window}")
                
        # 校验设备配置
        devices = self.config.get("devices", [])
        for device_config in devices:
            mxid = device_config.get("mxid", "未知设备")
            
            # 校验mxid
            if not device_config.get("mxid"):
                raise ValueError(f"设备配置缺少mxid字段")
                
            # 校验别名
            if "alias" in device_config:
                alias = device_config["alias"]
                if not isinstance(alias, str) or not alias:
                    raise ValueError(f"设备 {mxid} 的别名无效: {alias}")
                    
            # 校验外参
            if "kinematics" in device_config:
                kinematics = device_config["kinematics"]
                valid_fields = {"Tx", "Ty", "Tz", "Ry", "Rz"}
                for field, value in kinematics.items():
                    if field not in valid_fields:
                        raise ValueError(f"设备 {mxid} 包含无效外参字段: {field}")
                    if not isinstance(value, (int, float)):
                        raise ValueError(f"设备 {mxid} 外参 {field} 必须是数值: {value}")
                        
        return True


# ==============================================================================
#    使用示例和测试函数
# ==============================================================================

def example_usage():
    """使用示例"""
    print("=== OAK设备管理器使用示例 ===")
    
    # 创建设备管理器
    manager = OAKDeviceManager("configs/dual_oak_example.json")
    
    try:
        # 1. 发现连接的设备
        print("\n1. 发现OAK设备:")
        devices = manager.list_connected()
        for device in devices:
            print(f"  - MXid: {device['mxid']}, 状态: {device['state']}")
        
        if not devices:
            print("  未发现OAK设备，使用模拟数据演示...")
            # 使用模拟MXid进行演示
            devices = [
                {"mxid": "MXID_LEFT_ABCDEFG123", "state": "BOOTLOADER"},
                {"mxid": "MXID_RIGHT_HIJKLMN456", "state": "BOOTLOADER"}
            ]
        
        # 2. 绑定设备别名
        print("\n2. 绑定设备别名:")
        if len(devices) >= 1:
            manager.bind_alias(devices[0]["mxid"], "left_oak")
            print(f"  绑定: {devices[0]['mxid']} -> 'left_oak'")
        
        if len(devices) >= 2:
            manager.bind_alias(devices[1]["mxid"], "right_oak")
            print(f"  绑定: {devices[1]['mxid']} -> 'right_oak'")
        
        # 3. 设置设备外参
        print("\n3. 设置设备外参:")
        if len(devices) >= 1:
            manager.set_kinematics("left_oak", 
                                 Tx=-1500.0, Ty=-760.0, Tz=1200.0,
                                 Rx=0.0, Ry=22.9, Rz=-25.2)
            print("  left_oak外参已设置")
        
        if len(devices) >= 2:
            manager.set_kinematics("right_oak",
                                 Tx=-1600.0, Ty=-800.0, Tz=1250.0,
                                 Rx=0.0, Ry=25.0, Rz=-30.0)
            print("  right_oak外参已设置")
        
        # 4. 设置全局滤波参数
        print("\n4. 设置滤波参数:")
        manager.set_filter(type="moving_average", window=5)
        print("  滤波类型: moving_average, 窗口: 5")
        
        # 5. 校验配置
        print("\n5. 校验配置:")
        if manager.validate():
            print("  ✓ 配置校验通过")
        
        # 6. 保存配置
        print("\n6. 保存配置:")
        manager.save()
        print("  ✓ 配置已保存")
        
        # 7. 读取配置演示
        print("\n7. 读取配置演示:")
        if len(devices) >= 1:
            kinematics = manager.get_kinematics("left_oak")
            print(f"  left_oak外参: {kinematics}")
        
        filter_config = manager.get_filter()
        print(f"  滤波配置: {filter_config}")
        
        # 8. 重新加载配置
        print("\n8. 重新加载配置:")
        loaded_config = manager.load()
        if loaded_config:
            print("  ✓ 配置重新加载成功")
            print(f"  配置版本: {loaded_config.get('config_version')}")
            print(f"  更新时间: {loaded_config.get('updated_at')}")
        
        print("\n=== 演示完成 ===")
        
    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


def example_create_new_config():
    """创建新配置的使用示例"""
    print("\n=== 创建新配置功能演示 ===")
    
    # 创建设备管理器
    manager = OAKDeviceManager("configs/dual_oak_new.json")
    
    try:
        # 方法1: 使用create_new_config直接创建完整配置
        print("\n1. 使用create_new_config创建完整配置:")
        
        manager.create_new_config(
            mxids=["MXID_LEFT_ABCDEFG123", "MXID_RIGHT_HIJKLMN456"],
            aliases=["left_oak", "right_oak"],
            kinematics_list=[
                {"Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Ry": 22.9, "Rz": -25.2},
                {"Tx": -1600.0, "Ty": -800.0, "Tz": 1250.0, "Ry": 25.0, "Rz": -30.0}
            ],
            filter_type="moving_average",
            filter_window=8
        )
        print("  ✓ 新配置创建成功")
        
        # 校验并保存
        if manager.validate():
            print("  ✓ 配置校验通过")
            manager.save()
            print("  ✓ 配置已保存")
        
        # 方法1.1: 使用add_device_config逐个添加设备的便捷方式
        print("\n1.1 使用add_device_config逐个添加设备:")
        manager_alt = OAKDeviceManager("configs/dual_oak_alt.json")
        
        # 设置滤波参数
        manager_alt.set_filter(type="moving_average", window=6)
        
        # 逐个添加设备
        manager_alt.add_device_config(
            "MXID_LEFT_ABCDEFG123", "left_oak",
            Tx=-1500.0, Ty=-760.0, Tz=1200.0, Rx=0.0, Ry=22.9, Rz=-25.2
        )
        manager_alt.add_device_config(
            "MXID_RIGHT_HIJKLMN456", "right_oak", 
            Tx=-1600.0, Ty=-800.0, Tz=1250.0, Rx=0.0, Ry=25.0, Rz=-30.0
        )
        
        if manager_alt.validate():
            manager_alt.save()
            print("  ✓ 逐个添加的配置已保存")
        
        # 方法2: 使用auto_bind_devices自动绑定连接的设备
        print("\n2. 使用auto_bind_devices自动绑定设备:")
        
        # 定义设备别名映射
        device_aliases = {
            "MXID_LEFT_ABCDEFG123": "left_oak",
            "MXID_RIGHT_HIJKLMN456": "right_oak"
        }
        
        # 定义默认外参
        default_kinematics = {
            "left_oak": {
                "Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0,
                "Ry": 22.9, "Rz": -25.2
            },
            "right_oak": {
                "Tx": -1600.0, "Ty": -800.0, "Tz": 1250.0,
                "Ry": 25.0, "Rz": -30.0
            }
        }
        
        # 创建新的管理器实例演示自动绑定
        manager2 = OAKDeviceManager("configs/dual_oak_auto.json")
        bound_devices = manager2.auto_bind_devices(device_aliases, default_kinematics)
        
        print(f"  成功绑定 {len(bound_devices)} 个设备:")
        for device in bound_devices:
            print(f"    - {device['alias']}: {device['mxid']} ({device['state']})")
        
        # 设置滤波参数并保存
        manager2.set_filter(type="moving_average", window=6)
        if manager2.validate():
            manager2.save()
            print("  ✓ 自动绑定配置已保存")
        
        print("\n=== 新配置创建演示完成 ===")
        
    except Exception as e:
        print(f"\n❌ 创建新配置过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


def example_interactive_config():
    """交互式配置创建演示"""
    print("\n=== 交互式配置创建演示 ===")
    
    # 创建设备管理器
    manager = OAKDeviceManager("configs/dual_oak_interactive.json")
    
    # 定义坐标变换预设
    kinematics_presets = {
        "left_position": {
            "Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0,
            "Ry": 22.9, "Rz": -25.2
        },
        "right_position": {
            "Tx": -1600.0, "Ty": -800.0, "Tz": 1250.0,
            "Ry": 25.0, "Rz": -30.0
        },
        "center_position": {
            "Tx": -1550.0, "Ty": -780.0, "Tz": 1225.0,
            "Ry": 24.0, "Rz": -27.5
        }
    }
    
    # 自定义滤波配置
    filter_config = {"type": "moving_average", "window": 6}
    
    try:
        # 启动交互式配置创建
        success = manager.create_interactive_config(kinematics_presets, filter_config)
        
        if success:
            print("\n🎉 交互式配置创建完成!")
            
            # 显示最终配置
            print("\n📄 最终配置预览:")
            manager.plot_all_config()
        else:
            print("\n❌ 交互式配置创建失败或被取消")
            
    except Exception as e:
        print(f"\n❌ 交互式配置过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        # 运行交互式配置创建演示
        example_interactive_config()
    else:
        # 运行基础功能演示
        example_usage()
        
        # 运行新配置创建演示
        example_create_new_config()