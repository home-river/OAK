#!/usr/bin/env python3

"""
测试同名包导入冲突
"""

import sys
import os

def test_import_path():
    """测试导入路径"""
    print("🔍 当前Python路径:")
    for i, path in enumerate(sys.path):
        print(f"  {i}: {path}")
    
    print(f"\n📁 当前工作目录: {os.getcwd()}")
    print(f"📄 脚本所在目录: {os.path.dirname(os.path.abspath(__file__))}")

def test_oak_modules_import():
    """测试oak_modules导入"""
    try:
        print("\n🔧 尝试导入 oak_modules...")
        import oak_modules
        print(f"✅ 成功导入: {oak_modules}")
        print(f"📂 模块路径: {oak_modules.__file__}")
        
        # 尝试导入具体模块
        try:
            from oak_modules import calculate_module
            print(f"✅ 成功导入 calculate_module: {calculate_module}")
        except ImportError as e:
            print(f"❌ 导入 calculate_module 失败: {e}")
            
    except ImportError as e:
        print(f"❌ 导入 oak_modules 失败: {e}")

if __name__ == "__main__":
    test_import_path()
    test_oak_modules_import()
