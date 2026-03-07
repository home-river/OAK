"""
pytest 配置文件

确保项目根目录在 Python 路径中，以便导入 tools 模块
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
