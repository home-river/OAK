"""
显示模块 MVP 集成测试运行脚本

使用方法：
    python oak_vision_system/tests/integration/display_modules/run_mvp_tests.py

或者使用 pytest：
    pytest oak_vision_system/tests/integration/display_modules/test_display_module_mvp.py -v
"""

import sys
from test_display_module_mvp import run_all_tests

if __name__ == "__main__":
    sys.exit(run_all_tests())
