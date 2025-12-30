"""
简单的导入测试：检查linear_sum_assignment是否可以正常导入
"""
if __name__ == "__main__":
    print("正在测试 scipy.optimize.linear_sum_assignment 的导入...")
    
    try:
        import scipy
        print(f"✓ scipy 导入成功，版本: {scipy.__version__}")
    except ImportError as e:
        print(f"✗ scipy 导入失败: {e}")
        exit(1)
    
    try:
        from scipy.optimize import linear_sum_assignment
        print("✓ linear_sum_assignment 导入成功")
        print(f"  linear_sum_assignment 位置: {linear_sum_assignment}")
    except ImportError as e:
        print(f"✗ linear_sum_assignment 导入失败: {e}")
        exit(1)
    
    print("\n所有导入测试通过！")
