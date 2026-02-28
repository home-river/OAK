"""
显示渲染相关的固有配置

本模块定义了显示渲染器使用的固有配置，包括：
- 状态标签到颜色的映射（STATUS_COLOR_MAP）
- UI 样式常量（边框粗细、字体等）

这些配置独立于运行时配置（DisplayConfigDTO），属于系统的固有设计。
"""

from oak_vision_system.core.dto.data_processing_dto import DetectionStatusLabel
import cv2

# ============================================================================
# 状态标签颜色映射
# ============================================================================

STATUS_COLOR_MAP = {
    # 物体状态 (0-99)
    # 绿色 - 表示可抓取，系统可以安全地执行抓取操作
    DetectionStatusLabel.OBJECT_GRASPABLE: (0, 255, 0),
    
    # 红色 - 表示危险状态，不可抓取（例如：物体处于不稳定状态）
    DetectionStatusLabel.OBJECT_DANGEROUS: (0, 0, 255),
    
    # 橙色 - 表示超出范围，无法抓取（例如：物体距离过远或过近）
    DetectionStatusLabel.OBJECT_OUT_OF_RANGE: (0, 165, 255),
    
    # 蓝色 - 表示待抓取，物体已被标记但尚未执行抓取
    DetectionStatusLabel.OBJECT_PENDING_GRASP: (255, 0, 0),
    
    # 人类状态 (100-199)
    # 绿色 - 表示安全，人类距离机器人足够远，无危险
    DetectionStatusLabel.HUMAN_SAFE: (0, 255, 0),
    
    # 红色 - 表示危险，人类距离机器人过近，需要停止操作
    DetectionStatusLabel.HUMAN_DANGEROUS: (0, 0, 255),
}

# 默认颜色（用于未知状态或未映射状态）
# 白色 - 表示状态未知或未定义
DEFAULT_DETECTION_COLOR = (255, 255, 255)

# ============================================================================
# UI 样式配置
# ============================================================================

# 检测框边框粗细（像素）
BBOX_THICKNESS = 2

# 标签字体
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX

# 标签字体缩放比例
LABEL_FONT_SCALE = 0.5

# 标签文字粗细（像素）
LABEL_THICKNESS = 1
