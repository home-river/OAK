#!/usr/bin/env python3
"""
显示模块完整测试运行脚本

运行所有显示模块的集成测试，并生成详细的测试报告。

使用方法:
    python oak_vision_system/tests/integration/display_modules/run_all_tests.py
    
或者:
    python -m oak_vision_system.tests.integration.display_modules.run_all_tests
"""

import sys
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Tuple


def run_test_file(test_file: str, description: str) -> Tuple[bool, str, float]:
    """运行单个测试文件
    
    Args:
        test_file: 测试文件路径
        description: 测试描述
        
    Returns:
        (success, output, duration): 成功状态、输出内容、运行时长
    """
    print(f"\n{'='*60}")
    print(f"运行测试: {description}")
    print(f"文件: {test_file}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # 运行pytest命令
        cmd = [
            sys.executable, "-m", "pytest",
            test_file,
            "-v",
            "--tb=short",
            "--no-header",
            "--disable-warnings"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ 测试通过 ({duration:.1f}s)")
            return True, result.stdout, duration
        else:
            print(f"❌ 测试失败 ({duration:.1f}s)")
            print("错误输出:")
            print(result.stderr)
            return False, result.stdout + "\n" + result.stderr, duration
            
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"⏰ 测试超时 ({duration:.1f}s)")
        return False, "测试超时", duration
    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 测试异常: {e} ({duration:.1f}s)")
        return False, str(e), duration


def main():
    """主函数"""
    print("🚀 开始运行显示模块完整测试套件")
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {Path.cwd()}")
    
    # 定义测试文件列表
    test_files = [
        {
            "file": "oak_vision_system/tests/integration/display_modules/test_display_module_mvp.py",
            "description": "MVP基础功能测试",
            "category": "基础功能"
        },
        {
            "file": "oak_vision_system/tests/integration/display_modules/test_display_renderer_core.py", 
            "description": "DisplayRenderer核心功能测试",
            "category": "核心渲染"
        },
        {
            "file": "oak_vision_system/tests/integration/display_modules/test_display_module_complete.py",
            "description": "完整高级功能测试", 
            "category": "高级功能"
        },
        {
            "file": "oak_vision_system/tests/integration/display_modules/test_display_ui_interactions.py",
            "description": "UI交互和窗口管理测试",
            "category": "UI交互"
        },
    ]
    
    # 运行测试
    results = []
    total_start_time = time.time()
    
    for test_info in test_files:
        success, output, duration = run_test_file(
            test_info["file"], 
            test_info["description"]
        )
        
        results.append({
            "file": test_info["file"],
            "description": test_info["description"],
            "category": test_info["category"],
            "success": success,
            "output": output,
            "duration": duration
        })
    
    total_duration = time.time() - total_start_time
    
    # 生成测试报告
    print("\n" + "="*80)
    print("📊 测试结果汇总")
    print("="*80)
    
    passed_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    
    print(f"总测试文件数: {total_count}")
    print(f"通过测试数: {passed_count}")
    print(f"失败测试数: {total_count - passed_count}")
    print(f"总运行时间: {total_duration:.1f}s")
    print(f"成功率: {passed_count/total_count*100:.1f}%")
    
    # 按类别显示结果
    categories = {}
    for result in results:
        category = result["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(result)
    
    print(f"\n📋 分类测试结果:")
    for category, category_results in categories.items():
        category_passed = sum(1 for r in category_results if r["success"])
        category_total = len(category_results)
        status = "✅" if category_passed == category_total else "❌"
        print(f"  {status} {category}: {category_passed}/{category_total} 通过")
    
    # 详细结果
    print(f"\n📝 详细测试结果:")
    for result in results:
        status = "✅ 通过" if result["success"] else "❌ 失败"
        print(f"  {status} {result['description']} ({result['duration']:.1f}s)")
        if not result["success"]:
            print(f"    文件: {result['file']}")
    
    # 失败详情
    failed_tests = [r for r in results if not r["success"]]
    if failed_tests:
        print(f"\n🔍 失败测试详情:")
        for result in failed_tests:
            print(f"\n❌ {result['description']}")
            print(f"   文件: {result['file']}")
            print(f"   输出:")
            # 只显示最后几行输出
            output_lines = result["output"].split('\n')
            for line in output_lines[-10:]:
                if line.strip():
                    print(f"     {line}")
    
    # 建议
    print(f"\n💡 建议:")
    if passed_count == total_count:
        print("  🎉 所有测试都通过了！显示模块测试覆盖完整。")
        print("  📈 可以考虑添加性能基准测试和真实硬件测试。")
    else:
        print("  🔧 请检查失败的测试，确保代码质量。")
        print("  📚 查看测试输出了解具体失败原因。")
        print("  🐛 修复问题后重新运行测试。")
    
    print(f"\n🏁 测试完成！")
    
    # 返回退出码
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)