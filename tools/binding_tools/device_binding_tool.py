"""
OAK设备绑定工具

功能：
- 从 assets/ 目录选择配置文件夹
- 加载现有配置（不创建新配置）
- 自动发现 OAK 设备
- 交互式绑定设备到角色
- 验证并保存配置

使用方法：
    python device_binding_tool.py
    python device_binding_tool.py --config-dir /path/to/configs
    python device_binding_tool.py --config-folder test_config
    python device_binding_tool.py --show-devices
"""

import sys
import argparse
import time
from pathlib import Path
from typing import List, Optional, Dict

from oak_vision_system.modules.config_manager.device_config_manager import (
    DeviceConfigManager,
    ConfigNotFoundError,
    ConfigValidationError,
)
from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery
from oak_vision_system.core.dto.config_dto import (
    DeviceMetadataDTO,
    DeviceRole,
    DeviceRoleBindingDTO,
)


class DeviceBindingTool:
    """设备绑定工具主类"""
    
    def __init__(self, config_dir: str = "assets"):
        """
        初始化工具
        
        Args:
            config_dir: 配置根目录路径（默认: assets）
        """
        self.config_dir = Path(config_dir)
        self.config_manager: Optional[DeviceConfigManager] = None
        self.discovered_devices: List[DeviceMetadataDTO] = []
        self.selected_config_path: Optional[Path] = None
    
    def run(self) -> bool:
        """
        运行完整的绑定流程
        
        Returns:
            bool: 是否成功完成
        """
        print("🚀 OAK 设备绑定工具")
        print("=" * 80)
        
        try:
            # 1. 选择配置文件夹
            config_path = self.select_config_folder()
            if config_path is None:
                print("❌ 未选择配置文件夹")
                return False
            
            # 2. 加载配置文件
            if not self.load_config(config_path):
                return False

            time.sleep(6)
            
            # 3. 发现设备
            self.discovered_devices = self.discover_devices()
            if not self.discovered_devices:
                print("❌ 未发现任何设备，无法继续")
                return False
            
            # 4. 交互式绑定设备
            if not self.interactive_bind_devices(self.discovered_devices):
                print("❌ 设备绑定失败")
                return False
            
            # 5. 验证配置
            if not self.validate_config():
                # 验证失败，询问是否仍要保存
                while True:
                    choice = input("\n是否仍要保存配置？(y/n): ").strip().lower()
                    if choice in ['y', 'yes', '是']:
                        break
                    elif choice in ['n', 'no', '否']:
                        print("❌ 用户取消保存")
                        return False
                    else:
                        print("   请输入 y/yes 或 n/no")
            
            # 6. 保存配置
            if not self.save_config():
                return False
            
            print("\n" + "=" * 80)
            print("🎉 设备绑定完成！")
            return True
            
        except KeyboardInterrupt:
            print("\n\n❌ 用户中断操作")
            return False
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def select_config_folder(self) -> Optional[Path]:
        """
        选择配置文件夹
        
        Returns:
            Optional[Path]: 选择的配置文件夹路径，取消则返回 None
        """
        print("\n📂 扫描配置文件夹...")
        
        # 检查配置根目录是否存在
        if not self.config_dir.exists():
            print(f"❌ 配置根目录不存在: {self.config_dir}")
            return None
        
        # 扫描所有子文件夹
        config_folders = []
        for item in self.config_dir.iterdir():
            if not item.is_dir():
                continue
            
            # 检查是否包含配置文件
            has_json = (item / "config.json").exists()
            has_yaml = (item / "config.yaml").exists()
            
            if has_json or has_yaml:
                config_type = "JSON" if has_json else "YAML"
                config_folders.append((item, config_type))
        
        if not config_folders:
            print(f"❌ 在 {self.config_dir} 下未找到任何配置文件夹")
            print("   提示：配置文件夹应包含 config.json 或 config.yaml")
            return None
        
        # 显示配置文件夹列表
        print(f"\n✅ 发现 {len(config_folders)} 个配置文件夹：")
        print("-" * 80)
        for idx, (folder, config_type) in enumerate(config_folders, 1):
            print(f"{idx}. {folder.name}/ ({config_type})")
        print("-" * 80)
        
        # 用户选择
        while True:
            try:
                choice = input(f"\n请选择配置文件夹 (输入序号 1-{len(config_folders)}, 或 'q' 退出): ").strip()
                
                if choice.lower() == 'q':
                    return None
                
                idx = int(choice)
                if 1 <= idx <= len(config_folders):
                    selected_folder, config_type = config_folders[idx - 1]
                    print(f"\n✅ 已选择: {selected_folder.name}/ ({config_type})")
                    return selected_folder
                else:
                    print(f"   ⚠️ 请输入 1-{len(config_folders)} 之间的数字")
            except ValueError:
                print("   ⚠️ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n")
                return None
    
    def load_config(self, config_path: Path) -> bool:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件夹路径
        
        Returns:
            bool: 是否成功加载
        """
        print(f"\n📄 正在加载配置...")
        
        # 确定配置文件路径
        json_path = config_path / "config.json"
        yaml_path = config_path / "config.yaml"
        
        if json_path.exists():
            config_file = json_path
        elif yaml_path.exists():
            config_file = yaml_path
        else:
            print(f"❌ 配置文件不存在: {config_path}")
            return False
        
        try:
            # 创建配置管理器并加载配置
            self.config_manager = DeviceConfigManager(
                config_path=str(config_file),
                auto_create=False,  # 不自动创建
                eager_load=False,   # 手动加载
            )
            
            self.config_manager.load_config(
                validate=True,
                auto_create=False,  # 不自动创建
            )
            
            self.selected_config_path = config_path
            
            print(f"✅ 配置加载成功: {config_file}")
            
            # 显示当前配置的角色
            config = self.config_manager.get_config()
            role_bindings = config.oak_module.role_bindings
            
            print(f"\n📋 当前配置包含以下设备角色：")
            for role, binding in role_bindings.items():
                status = f"(已绑定: {binding.last_active_mxid[:16]}...)" if binding.last_active_mxid else "(未绑定)"
                print(f"  - {role.value} {status}")
            
            return True
            
        except ConfigNotFoundError as e:
            print(f"❌ 配置文件不存在: {e}")
            return False
        except ConfigValidationError as e:
            print(f"❌ 配置验证失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 加载配置失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def discover_devices(self) -> List[DeviceMetadataDTO]:
        """
        发现设备
        
        Returns:
            List[DeviceMetadataDTO]: 发现的设备列表
        """
        print(f"\n🔍 正在扫描 OAK 设备...")
        
        try:
            devices = OAKDeviceDiscovery.discover_devices(verbose=False)
            
            if not devices:
                print("❌ 未发现任何设备")
                print("   提示：请确保设备已连接并正确安装驱动")
                return []
            
            print(f"\n✅ 发现 {len(devices)} 个设备：")
            print("-" * 80)
            for idx, device in enumerate(devices, 1):
                print(f"{idx}. 设备 {chr(64 + idx)}")
                print(f"   MX ID: {device.mxid}")
                print(f"   产品名称: {device.product_name or '未知'}")
                print(f"   连接状态: {device.connection_status.value}")
                print()
            print("-" * 80)
            
            return devices
            
        except Exception as e:
            print(f"❌ 设备发现失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def interactive_bind_devices(self, devices: List[DeviceMetadataDTO]) -> bool:
        """
        交互式绑定设备
        
        Args:
            devices: 发现的设备列表
        
        Returns:
            bool: 是否成功完成绑定
        """
        print(f"\n🔗 开始设备绑定流程")
        print("=" * 80)
        
        if self.config_manager is None:
            print("❌ 配置管理器未初始化")
            return False
        
        # 获取当前配置
        config = self.config_manager.get_config()
        role_bindings = dict(config.oak_module.role_bindings)  # 复制一份
        
        # 跟踪已绑定的设备
        bound_devices = set()
        
        # 遍历所有角色
        for role, binding in role_bindings.items():
            print(f"\n为角色 {role.value} 选择设备：")
            print("━" * 80)
            
            # 显示可用设备（排除已绑定的）
            available_devices = [d for d in devices if d.mxid not in bound_devices]
            
            if not available_devices:
                print("⚠️ 没有可用设备")
                print(f"   角色 {role.value} 将保持未绑定状态")
                continue
            
            print("\n可用设备：")
            for idx, device in enumerate(available_devices, 1):
                print(f"{idx}. 设备 {chr(64 + devices.index(device) + 1)} ({device.mxid[:16]}...) - {device.product_name or '未知'}")
            print("s. 跳过此角色")
            
            # 用户选择
            while True:
                try:
                    choice = input(f"\n请选择设备 (输入序号或 's' 跳过): ").strip().lower()
                    
                    if choice == 's':
                        print(f"⏭️  已跳过角色 {role.value}")
                        break
                    
                    idx = int(choice)
                    if 1 <= idx <= len(available_devices):
                        selected_device = available_devices[idx - 1]
                        
                        # 更新绑定
                        new_binding = binding.set_active_Mxid_by_device(selected_device)
                        role_bindings[role] = new_binding
                        bound_devices.add(selected_device.mxid)
                        
                        device_label = chr(64 + devices.index(selected_device) + 1)
                        print(f"✅ 已将设备 {device_label} ({selected_device.mxid[:16]}...) 绑定到角色 {role.value}")
                        break
                    else:
                        print(f"   ⚠️ 请输入 1-{len(available_devices)} 之间的数字，或 's' 跳过")
                except ValueError:
                    print("   ⚠️ 请输入有效的数字或 's'")
                except KeyboardInterrupt:
                    print("\n")
                    return False
        
        # 显示绑定摘要
        print("\n" + "━" * 80)
        print("绑定完成！")
        print("\n📋 绑定摘要：")
        for role, binding in role_bindings.items():
            if binding.active_mxid:
                device = next((d for d in devices if d.mxid == binding.active_mxid), None)
                device_label = chr(64 + devices.index(device) + 1) if device else "?"
                print(f"  ✅ {role.value:15} → 设备 {device_label} ({binding.active_mxid[:16]}...)")
            else:
                print(f"  ⏭️  {role.value:15} → 未绑定（已跳过）")
        
        # 更新配置
        try:
            # 1. 构建 device_metadata 字典（将发现的设备添加到配置中）
            device_metadata = dict(config.oak_module.device_metadata)  # 保留原有的
            for device in devices:
                device_metadata[device.mxid] = device  # 添加新发现的设备
            
            # 2. 更新 oak_module（同时更新 role_bindings 和 device_metadata）
            new_oak_module = config.oak_module.with_updates(
                role_bindings=role_bindings,
                device_metadata=device_metadata
            )
            new_config = config.with_updates(oak_module=new_oak_module)
            
            # 更新配置管理器的内部状态
            self.config_manager._config = new_config
            self.config_manager._dirty = True
            
            return True
            
        except Exception as e:
            print(f"\n❌ 更新配置失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def validate_config(self) -> bool:
        """
        验证配置
        
        Returns:
            bool: 配置是否有效
        """
        print(f"\n🔍 正在验证配置...")
        
        if self.config_manager is None:
            print("❌ 配置管理器未初始化")
            return False
        
        try:
            # 使用静态验证（不检查运行时的 mxid 是否在线）
            # 因为这是配置阶段，允许部分角色未绑定
            is_valid, errors = self.config_manager.validate_config(
                include_runtime_checks=False  # 只做静态验证
            )
            
            if is_valid:
                print("✅ 配置验证通过")
                print("  - 设备绑定信息完整")
                print("  - 设备角色定义有效")
                print("  - 配置结构正确")
                return True
            else:
                print("❌ 配置验证失败：")
                for error in errors:
                    print(f"  - {error}")
                return False
                
        except Exception as e:
            print(f"❌ 验证过程出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_config(self) -> bool:
        """
        保存配置
        
        Returns:
            bool: 是否成功保存
        """
        print(f"\n💾 正在保存配置...")
        
        if self.config_manager is None:
            print("❌ 配置管理器未初始化")
            return False
        
        try:
            # 晋升为可运行配置
            self.config_manager.promote_runnable_if_valid(
                include_runtime_checks=False,  # 静态验证
                persist=False,  # 不立即保存
            )
            
            # 保存配置
            self.config_manager.save_config(validate=True)
            
            # 统计绑定数量
            config = self.config_manager.get_runnable_config()
            bound_count = sum(
                1 for binding in config.oak_module.role_bindings.values()
                if binding.active_mxid
            )
            
            print(f"✅ 配置已保存到: {self.config_manager._config_path}")
            print(f"\n📋 保存摘要：")
            print(f"  - 已更新 {bound_count} 个设备绑定")
            print(f"  - 配置文件格式: {'JSON' if self.config_manager._config_path.endswith('.json') else 'YAML'}")
            print(f"  - 保存时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return True
            
        except ConfigValidationError as e:
            print(f"❌ 配置验证失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def show_devices_only(self) -> bool:
        """
        仅显示发现的设备（不进行绑定）
        
        Returns:
            bool: 是否成功
        """
        print("🚀 OAK 设备发现工具")
        print("=" * 80)
        
        devices = self.discover_devices()
        return len(devices) > 0


def main():
    """主函数 - 命令行工具入口"""
    parser = argparse.ArgumentParser(
        description="OAK 设备绑定工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  # 交互式绑定（默认）
  python device_binding_tool.py
  
  # 指定配置目录
  python device_binding_tool.py --config-dir /path/to/configs
  
  # 直接使用指定配置文件夹
  python device_binding_tool.py --config-folder test_config
  
  # 仅显示设备
  python device_binding_tool.py --show-devices
        """
    )
    
    parser.add_argument(
        "--config-dir", "-d",
        default="assets",
        help="配置根目录路径（默认: assets）"
    )
    
    parser.add_argument(
        "--config-folder", "-f",
        help="直接指定配置文件夹名称（跳过选择步骤）"
    )
    
    parser.add_argument(
        "--show-devices", "-s",
        action="store_true",
        help="仅显示发现的设备，不进行绑定"
    )
    
    args = parser.parse_args()
    
    # 创建工具实例
    tool = DeviceBindingTool(config_dir=args.config_dir)
    
    # 执行相应操作
    try:
        if args.show_devices:
            # 仅显示设备
            success = tool.show_devices_only()
        elif args.config_folder:
            # 直接使用指定配置文件夹
            config_path = tool.config_dir / args.config_folder
            if not config_path.exists():
                print(f"❌ 配置文件夹不存在: {config_path}")
                sys.exit(1)
            
            # 跳过选择步骤，直接加载
            if not tool.load_config(config_path):
                sys.exit(1)
            
            # 继续后续流程
            tool.discovered_devices = tool.discover_devices()
            if not tool.discovered_devices:
                sys.exit(1)
            
            if not tool.interactive_bind_devices(tool.discovered_devices):
                sys.exit(1)
            
            if not tool.validate_config():
                # 验证失败，询问是否仍要保存
                while True:
                    choice = input("\n是否仍要保存配置？(y/n): ").strip().lower()
                    if choice in ['y', 'yes', '是']:
                        break
                    elif choice in ['n', 'no', '否']:
                        print("❌ 用户取消保存")
                        sys.exit(1)
                    else:
                        print("   请输入 y/yes 或 n/no")
            
            success = tool.save_config()
        else:
            # 运行完整流程
            success = tool.run()
        
        if success:
            print("\n✅ 工具执行成功")
            sys.exit(0)
        else:
            print("\n❌ 工具执行失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
