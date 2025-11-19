"""
OAK设备交互式绑定工具

提供用户友好的设备配置界面，支持：
- 自动设备发现
- 交互式RGB预览
- 别名选择和绑定
- 配置保存和管理
"""

from typing import List, Optional

from oak_vision_system.modules.data_collector.config_manager import SystemConfigManager

# 向后兼容别名
OAKDeviceManager = SystemConfigManager


class OAKDeviceBindingTool:
    """
    OAK设备交互式绑定工具类
    
    这是一个用户友好的工具，封装了设备发现、预览和绑定的完整流程
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化绑定工具
        
        Args:
            config_path: 配置文件路径，默认使用标准路径
        """
        self.device_manager = OAKDeviceManager(config_path)
        
        # 常用的预定义别名
        self.default_aliases = [
            "left_camera",      # 左相机
            "right_camera",     # 右相机
            "front_camera",     # 前相机
            "back_camera",      # 后相机
            "main_camera",      # 主相机
            "aux_camera",       # 辅助相机
            "detection_cam",    # 检测相机
            "monitoring_cam",   # 监控相机
        ]
    
    def run_interactive_binding(self, 
                              custom_aliases: Optional[List[str]] = None,
                              use_default_aliases: bool = True) -> bool:
        """
        运行交互式设备绑定流程
        
        Args:
            custom_aliases: 自定义别名列表
            use_default_aliases: 是否使用默认别名
            
        Returns:
            是否成功完成绑定
        """
        print("🚀 OAK设备交互式绑定工具")
        print("=" * 50)
        
        # 准备别名列表
        predefined_aliases = []
        if use_default_aliases:
            predefined_aliases.extend(self.default_aliases)
        if custom_aliases:
            predefined_aliases.extend(custom_aliases)
        
        # 显示工具信息
        self._show_tool_info()
        
        # 确认开始
        if not self._confirm_start():
            print("❌ 用户取消操作")
            return False
        
        # 执行交互式绑定
        try:
            success = self.device_manager.interactive_device_binding(
                predefined_aliases=predefined_aliases,
                save_after_binding=True
            )
            
            if success:
                self._show_completion_summary()
                return True
            else:
                print("❌ 绑定过程未成功完成")
                return False
                
        except KeyboardInterrupt:
            print("\n❌ 用户中断操作")
            return False
        except Exception as e:
            print(f"❌ 绑定过程出错: {e}")
            return False
    
    def _show_tool_info(self):
        """显示工具使用说明"""
        print("\n📖 使用说明:")
        print("1. 工具将自动发现所有连接的OAK设备")
        print("2. 依次显示每个设备的RGB图像预览")
        print("3. 观察图像后，按 'q' 退出预览")
        print("4. 为设备选择或输入别名")
        print("5. 完成后自动保存配置")
        print("\n💡 提示:")
        print("- 通过观察RGB图像可以确定设备的安装位置")
        print("- 可以选择预定义别名或输入自定义别名")
        print("- 可以跳过不需要配置的设备")
        print("- 配置会自动保存到配置文件")
    
    def _confirm_start(self) -> bool:
        """确认开始绑定流程"""
        print("\n" + "=" * 50)
        while True:
            confirm = input("🤔 是否开始设备绑定流程？(y/n): ").strip().lower()
            if confirm in ['y', 'yes', '是']:
                return True
            elif confirm in ['n', 'no', '否']:
                return False
            else:
                print("   请输入 y/yes 或 n/no")
    
    def _show_completion_summary(self):
        """显示完成摘要"""
        print("\n" + "=" * 50)
        print("🎉 设备绑定完成!")
        
        # 显示当前配置的设备
        devices = self.device_manager.list_devices()
        if devices:
            print(f"\n📋 当前配置的设备 ({len(devices)} 个):")
            for device in devices:
                status = "✅ 启用" if device.enabled else "❌ 禁用"
                print(f"   • {device.alias} ({device.mxid}) - {device.device_type.value} {status}")
        
        print(f"\n💾 配置文件位置: {self.device_manager.config_path}")
        print("✨ 您现在可以使用这些设备进行OAK应用开发了!")
    
    def show_current_devices(self):
        """显示当前配置的设备"""
        print("📋 当前配置的设备:")
        print("-" * 30)
        
        devices = self.device_manager.list_devices()
        if not devices:
            print("   暂无配置的设备")
            return
        
        for device in devices:
            print(f"别名: {device.alias}")
            print(f"MX ID: {device.mxid}")
            print(f"设备类型: {device.device_type.value}")
            print(f"产品名称: {device.product_name or 'N/A'}")
            print(f"连接状态: {device.connection_state.value}")
            print(f"启用状态: {'✅ 启用' if device.enabled else '❌ 禁用'}")
            if device.properties:
                print(f"属性: {device.properties}")
            print("-" * 30)
    
    def quick_discovery(self):
        """快速设备发现（不绑定）"""
        print("🔍 快速设备发现...")
        devices = self.device_manager.discover_devices()
        
        if not devices:
            print("❌ 未发现任何设备")
            return
        
        print(f"✅ 发现 {len(devices)} 个设备:")
        for i, device in enumerate(devices, 1):
            print(f"{i}. {device.device_name} ({device.mxid})")
            print(f"   类型: {device.device_type.value}")
            print(f"   状态: {device.connection_state.value}")


def main():
    """主函数 - 命令行工具入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OAK设备交互式绑定工具")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--aliases", "-a", nargs="*", help="自定义别名列表")
    parser.add_argument("--no-defaults", action="store_true", help="不使用默认别名")
    parser.add_argument("--show-devices", "-s", action="store_true", help="显示当前配置的设备")
    parser.add_argument("--quick-discovery", "-q", action="store_true", help="快速设备发现")
    
    args = parser.parse_args()
    
    # 创建工具实例
    tool = OAKDeviceBindingTool(args.config)
    
    # 执行相应操作
    if args.show_devices:
        tool.show_current_devices()
    elif args.quick_discovery:
        tool.quick_discovery()
    else:
        # 运行交互式绑定
        success = tool.run_interactive_binding(
            custom_aliases=args.aliases,
            use_default_aliases=not args.no_defaults
        )
        
        if success:
            print("\n✅ 绑定工具执行成功")
            sys.exit(0)
        else:
            print("\n❌ 绑定工具执行失败")
            sys.exit(1)


if __name__ == "__main__":
    main()
