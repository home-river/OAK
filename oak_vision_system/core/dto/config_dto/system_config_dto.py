"""
系统配置DTO

管理系统级通用配置：队列、日志、性能优化等。
"""

from dataclasses import dataclass
from typing import List, Optional

from ..base_dto import validate_numeric_range, validate_string_length
from .base_config_dto import BaseConfigDTO


# 模块内维护的日志级别白名单（提取自 DTO 外部）
LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass(frozen=True)
class SystemConfigDTO(BaseConfigDTO):
    """
    系统级配置
    
    职责：
    - 日志配置
    - 性能优化选项
    - 系统行为控制
    - 数据录制
    
    注意：
    - OAK Pipeline的队列配置在 OAKConfigDTO 中
    - 这里管理的是应用层面的系统配置
    """
    
    # ========== 日志配置 ==========
    log_level: str = "INFO"  # DEBUG/INFO/WARNING/ERROR/CRITICAL
    log_to_file: bool = False  # 是否写入日志文件
    log_file_path: Optional[str] = None  # 日志文件路径
    log_max_size_mb: int = 100  # 单个日志文件最大大小(MB)
    log_backup_count: int = 7  # 日志文件备份数量
    log_rotate_mode: str = "time"
    log_rotate_when: str = "MIDNIGHT"
    log_rotate_interval: int = 1
    log_rotate_utc: bool = False
    
    # ========== 性能配置 ==========
    enable_profiling: bool = False  # 启用性能分析
    max_worker_threads: int = 4  # 最大工作线程数
    
    # ========== 系统行为 ==========
    auto_reconnect: bool = True  # 设备断开后自动重连
    reconnect_interval: float = 5.0  # 重连间隔(秒)
    max_reconnect_attempts: int = 10  # 最大重连次数
    graceful_shutdown_timeout: float = 5.0  # 优雅关闭超时(秒)
    
    
    def _validate_data(self) -> List[str]:
        errors = []
        
        # 日志级别验证
        if self.log_level not in LOG_LEVELS:
            errors.append(f"log_level必须为: {'/'.join(LOG_LEVELS)}")
        
        if self.log_file_path is not None:
            errors.extend(validate_string_length(
                self.log_file_path, 'log_file_path', min_length=1, max_length=500
            ))
        
        errors.extend(validate_numeric_range(
            self.log_max_size_mb, 'log_max_size_mb', min_value=1, max_value=1000
        ))

        if self.log_rotate_mode not in ("time", "size"):
            errors.append("log_rotate_mode必须为: time/size")
        if self.log_rotate_mode == "time":
            allowed_when = {"S", "M", "H", "D", "MIDNIGHT", "W0", "W1", "W2", "W3", "W4", "W5", "W6"}
            if self.log_rotate_when.upper() not in allowed_when:
                errors.append("log_rotate_when必须为: S/M/H/D/MIDNIGHT/W0-W6")
            errors.extend(validate_numeric_range(
                self.log_rotate_interval, 'log_rotate_interval', min_value=1, max_value=10000
            ))
        
        # 性能参数验证
        errors.extend(validate_numeric_range(
            self.max_worker_threads, 'max_worker_threads', min_value=1, max_value=32
        ))
        
        # 重连参数验证
        errors.extend(validate_numeric_range(
            self.reconnect_interval, 'reconnect_interval', min_value=0.5, max_value=60.0
        ))
        errors.extend(validate_numeric_range(
            self.max_reconnect_attempts, 'max_reconnect_attempts', min_value=1, max_value=100
        ))
        
        return errors

