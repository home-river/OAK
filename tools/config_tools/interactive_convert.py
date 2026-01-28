#!/usr/bin/env python3
"""
OAK Vision System - 交互式配置格式转换工具

提供友好的终端交互界面，支持：
- 智能文件路径输入和验证
- 自动格式检测和建议
- 实时转换预览
- 安全的文件覆盖确认
- 可选的配置验证
- 连续转换多个文件
"""

import sys
import os
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oak_vision_system.modules.config_manager import ConfigConverter, DeviceConfigManager


class InteractiveConfigConverter:
    """交互式配置转换工具"""
    
    def __init__(self):
        self.converter = ConfigConverter
        
    def print_welcome(self):
        """显示欢迎信息"""
        print("=" * 70)
        print("OAK Vision System - 交互式配置格式转换工具")
        print("=" * 70)
        print()
        print("功能特点：")
        print("  • 支持 JSON ↔ YAML 双向转换")
        print("  • 自动格式检测和智能建议")
        print("  • 转换后文件自动保存到同一目录")
        print("  • 支持注释保持（使用 ruamel.yaml）")
        print("  • 可选的配置验证功能")
        print()
        print("支持的文件格式：.json, .yaml, .yml")
        print("输入 'quit' 或 'exit' 退出程序")
        print("-" * 70)
        
    def get_file_path(self) -> Optional[Path]:
        """获取用户输入的文件路径"""
        while True:
            print()
            user_input = input("请输入配置文件路径: ").strip()
            
            # 检查退出命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                return None
                
            # 处理空输入
            if not user_input:
                print("错误: 请输入有效的文件路径")
                continue
                
            # 处理引号（支持拖拽文件）
            user_input = user_input.strip('"\'')
            
            # 转换为 Path 对象
            file_path = Path(user_input)
            
            # 检查文件是否存在
            if not file_path.exists():
                print(f"错误: 文件不存在: {file_path}")
                print("提示: 请检查路径是否正确，支持相对路径和绝对路径")
                continue
                
            # 检查是否为文件
            if not file_path.is_file():
                print(f"错误: 路径不是文件: {file_path}")
                continue
                
            return file_path
            
    def detect_and_suggest_format(self, input_path: Path) -> tuple[str, str]:
        """检测输入格式并建议目标格式"""
        try:
            input_format = self.converter.detect_format(input_path)
            target_format = 'yaml' if input_format == 'json' else 'json'
            return input_format, target_format
        except ValueError as e:
            raise ValueError(f"不支持的文件格式: {e}")
            
    def get_target_format(self, suggested_format: str) -> str:
        """获取目标格式"""
        while True:
            print(f"\n建议转换为: {suggested_format.upper()}")
            choice = input(f"按 Enter 使用建议格式，或输入 json/yaml: ").strip().lower()
            
            if not choice:
                return suggested_format
                
            if choice in ['json', 'yaml']:
                return choice
                
            print("错误: 请输入 'json' 或 'yaml'")
            
    def preview_conversion(self, input_path: Path, target_format: str) -> Path:
        """预览转换结果"""
        if target_format == 'yaml':
            output_path = input_path.with_suffix('.yaml')
        else:
            output_path = input_path.with_suffix('.json')
            
        print(f"\n转换预览:")
        print(f"  输入文件: {input_path}")
        print(f"  输出文件: {output_path}")
        print(f"  转换类型: {input_path.suffix.upper()} → {target_format.upper()}")
        
        return output_path
        
    def confirm_conversion(self, output_path: Path) -> bool:
        """确认转换操作"""
        # 检查输出文件是否存在
        if output_path.exists():
            print(f"\n警告: 文件已存在 {output_path}")
            while True:
                choice = input("是否覆盖? (y/N): ").strip().lower()
                if choice in ['y', 'yes']:
                    return True
                elif choice in ['n', 'no', '']:
                    return False
                else:
                    print("请输入 y 或 n")
        else:
            while True:
                choice = input(f"\n确认转换? (Y/n): ").strip().lower()
                if choice in ['y', 'yes', '']:
                    return True
                elif choice in ['n', 'no']:
                    return False
                else:
                    print("请输入 y 或 n")
                    
    def perform_conversion(self, input_path: Path, output_path: Path, target_format: str):
        """执行转换"""
        print(f"\n正在转换...")
        
        try:
            if target_format == 'yaml':
                self.converter.json_to_yaml(input_path, output_path)
            else:
                self.converter.yaml_to_json(input_path, output_path)
                
            print(f"转换成功!")
            print(f"文件已保存: {output_path}")
            
            # 显示文件大小
            size = output_path.stat().st_size
            print(f"文件大小: {size} 字节")
            
        except Exception as e:
            print(f"转换失败: {e}")
            return False
            
        return True
        
    def validate_config(self, config_path: Path) -> bool:
        """验证配置文件"""
        print(f"\n正在验证配置...")
        
        try:
            manager = DeviceConfigManager(str(config_path), auto_create=False)
            result = manager.load_config(validate=True)
            
            if result:
                print("配置验证通过")
                return True
            else:
                print("配置验证失败")
                return False
                
        except Exception as e:
            print(f"配置验证出错: {e}")
            return False
            
    def ask_for_validation(self) -> bool:
        """询问是否进行配置验证"""
        while True:
            choice = input("\n是否验证转换后的配置? (y/N): ").strip().lower()
            if choice in ['y', 'yes']:
                return True
            elif choice in ['n', 'no', '']:
                return False
            else:
                print("请输入 y 或 n")
                
    def ask_continue(self) -> bool:
        """询问是否继续转换其他文件"""
        while True:
            choice = input("\n是否转换其他文件? (y/N): ").strip().lower()
            if choice in ['y', 'yes']:
                return True
            elif choice in ['n', 'no', '']:
                return False
            else:
                print("请输入 y 或 n")
                
    def run(self):
        """运行交互式转换工具"""
        self.print_welcome()
        
        while True:
            try:
                # 1. 获取输入文件路径
                input_path = self.get_file_path()
                if input_path is None:
                    break
                    
                # 2. 检测格式并建议目标格式
                try:
                    input_format, suggested_format = self.detect_and_suggest_format(input_path)
                    print(f"\n检测到文件格式: {input_format.upper()}")
                except ValueError as e:
                    print(f"错误: {e}")
                    continue
                    
                # 3. 获取目标格式
                target_format = self.get_target_format(suggested_format)
                
                # 检查是否为相同格式
                if input_format == target_format:
                    print(f"警告: 输入和输出格式相同 ({target_format.upper()})，无需转换")
                    if not self.ask_continue():
                        break
                    continue
                    
                # 4. 预览转换
                output_path = self.preview_conversion(input_path, target_format)
                
                # 5. 确认转换
                if not self.confirm_conversion(output_path):
                    print("已取消转换")
                    if not self.ask_continue():
                        break
                    continue
                    
                # 6. 执行转换
                success = self.perform_conversion(input_path, output_path, target_format)
                
                if success:
                    # 7. 可选验证
                    if self.ask_for_validation():
                        self.validate_config(output_path)
                        
                # 8. 询问是否继续
                if not self.ask_continue():
                    break
                    
            except KeyboardInterrupt:
                print("\n\n用户中断，程序退出")
                break
            except Exception as e:
                print(f"\n发生错误: {e}")
                if not self.ask_continue():
                    break
                    
        print("\n感谢使用 OAK Vision System 配置转换工具!")


def main():
    """主函数"""
    converter = InteractiveConfigConverter()
    converter.run()


if __name__ == '__main__':
    main()