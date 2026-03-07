"""
误差数据记录模块

ErrorRecorder 类负责：
- 接收基准位置参数
- 从 DecisionLayer 获取实际目标位置
- 计算误差向量（实际位置 - 基准位置）
- 保存误差数据到 JSON 文件
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import numpy as np


class ErrorRecorder:
    """
    误差数据记录模块
    
    职责：
    - 从 DecisionLayer 获取实际位置
    - 计算误差向量
    - 保存误差数据到 JSON 文件
    - 提供统计信息接口
    """
    
    def __init__(
        self,
        decision_layer,
        log_file_path: str = "logs/calibration_errors.json"
    ):
        """
        初始化误差记录器
        
        Args:
            decision_layer: DecisionLayer 实例
            log_file_path: 误差数据保存路径
        """
        self.decision_layer = decision_layer
        self.log_file_path = Path(log_file_path)
        self.logger = logging.getLogger(__name__)
        
        # 记录计数
        self.record_count = 0
        
        # 确保日志目录存在
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"误差记录器初始化完成，日志文件: {self.log_file_path}")
    
    def record_error(
        self,
        reference_x: float,
        reference_y: float,
        target_type: str = "durian"
    ) -> bool:
        """
        记录一次误差数据
        
        从 DecisionLayer 获取当前目标位置，计算与基准位置的误差，
        并保存到 JSON 文件。
        
        Args:
            reference_x: 基准位置 X 坐标（mm）
            reference_y: 基准位置 Y 坐标（mm）
            target_type: 目标类型（如 "durian"）
        
        Returns:
            bool: 记录成功返回 True，失败返回 False
        """
        # 使用传入的基准位置
        reference_position = np.array([reference_x, reference_y, 0.0])
        
        # 1. 从 DecisionLayer 获取当前目标位置
        target_coords = self.decision_layer.get_target_coords_snapshot()
        
        if target_coords is None:
            self.logger.warning("未检测到目标，无法记录误差")
            return False
        
        # 2. 计算误差向量（实际位置 - 基准位置）
        error_vector = target_coords - reference_position
        
        # 3. 构造误差数据记录
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "target_type": target_type,
            "reference_position": {
                "x": float(reference_position[0]),
                "y": float(reference_position[1]),
                "z": float(reference_position[2])
            },
            "actual_position": {
                "x": float(target_coords[0]),
                "y": float(target_coords[1]),
                "z": float(target_coords[2])
            },
            "error_vector": {
                "dx": float(error_vector[0]),
                "dy": float(error_vector[1]),
                "dz": float(error_vector[2])
            },
            "error_magnitude": float(np.linalg.norm(error_vector))
        }
        
        # 4. 追加保存到 JSON 文件
        try:
            self._append_to_json(error_data)
            self.record_count += 1
            self.logger.info(
                f"误差数据已记录 (#{self.record_count}): "
                f"误差大小 = {error_data['error_magnitude']:.2f} mm"
            )
            return True
        except Exception as e:
            self.logger.error(f"保存误差数据失败: {e}")
            return False

    
    def _append_to_json(self, data: Dict) -> None:
        """
        追加数据到 JSON 文件
        
        以追加模式保存误差数据，确保不覆盖历史记录。
        
        Args:
            data: 误差数据字典
        
        Raises:
            OSError: 文件操作失败
            json.JSONDecodeError: JSON 解析失败
        """
        # 读取现有数据
        if self.log_file_path.exists():
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                try:
                    records = json.load(f)
                except json.JSONDecodeError:
                    # 文件损坏或为空，重新开始
                    self.logger.warning("JSON 文件损坏，将创建新文件")
                    records = []
        else:
            records = []
        
        # 追加新数据
        records.append(data)
        
        # 写回文件
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    
    def get_statistics(self) -> Dict:
        """
        获取误差统计信息
        
        计算并返回误差数据的统计信息，包括：
        - 记录数
        - 平均误差
        - 标准差
        - 最大误差
        - 最小误差
        
        Returns:
            统计信息字典
        """
        if not self.log_file_path.exists():
            return {"record_count": 0}
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self.logger.error(f"读取误差数据失败: {e}")
            return {"record_count": 0, "error": str(e)}
        
        if not records:
            return {"record_count": 0}
        
        # 提取误差大小
        errors = [r["error_magnitude"] for r in records]
        
        # 计算统计信息
        return {
            "record_count": len(records),
            "mean_error": float(np.mean(errors)),
            "std_error": float(np.std(errors)),
            "max_error": float(np.max(errors)),
            "min_error": float(np.min(errors))
        }
