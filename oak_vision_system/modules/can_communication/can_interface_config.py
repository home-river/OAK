"""
CAN接口配置工具模块

提供CAN接口的自动配置和重置功能，支持Linux系统的socketCAN接口。
使用subprocess执行系统命令，智能处理sudo权限。

主要功能：
- configure_can_interface(): 配置CAN接口（关闭、加载模块、设置波特率、启用、验证）
- reset_can_interface(): 重置CAN接口（关闭接口）

设计要点：
- 智能sudo处理：root用户直接执行，普通用户使用sudo -S传递密码
- 完整的错误处理和日志记录
- 支持跨平台检测（仅在Linux系统执行）
"""

import logging
import os
import subprocess
import sys
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


def _is_root() -> bool:
    """
    检查当前用户是否为root
    
    Returns:
        bool: 如果是root用户返回True，否则返回False
    """
    return os.geteuid() == 0 if hasattr(os, 'geteuid') else False


def _execute_command(
    cmd: List[str],
    sudo_password: Optional[str] = None,
    use_sudo: bool = True
) -> Tuple[bool, str, str]:
    """
    执行系统命令，智能处理sudo权限
    
    Args:
        cmd: 命令列表（如['ip', 'link', 'set', 'can0', 'down']）
        sudo_password: sudo密码（可选）
        use_sudo: 是否使用sudo（如果不是root用户）
        
    Returns:
        Tuple[bool, str, str]: (成功标志, stdout输出, stderr输出)
    """
    # 如果需要sudo且不是root用户，添加sudo前缀
    if use_sudo and not _is_root():
        if sudo_password:
            # 使用sudo -S从stdin读取密码
            cmd = ['sudo', '-S'] + cmd
        else:
            # 不提供密码，依赖系统的sudo配置（可能需要交互输入）
            cmd = ['sudo'] + cmd
    
    try:
        # 准备输入（如果有sudo密码）
        input_data = f"{sudo_password}\n".encode() if sudo_password and use_sudo and not _is_root() else None
        
        # 执行命令
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            timeout=10,  # 10秒超时
            check=False
        )
        
        stdout = result.stdout.decode('utf-8', errors='ignore').strip()
        stderr = result.stderr.decode('utf-8', errors='ignore').strip()
        success = result.returncode == 0
        
        return success, stdout, stderr
        
    except subprocess.TimeoutExpired:
        logger.error(f"命令执行超时: {' '.join(cmd)}")
        return False, "", "命令执行超时"
    except Exception as e:
        logger.error(f"命令执行异常: {e}")
        return False, "", str(e)


def configure_can_interface(
    channel: str,
    bitrate: int,
    sudo_password: Optional[str] = None
) -> bool:
    """
    配置CAN接口
    
    执行步骤：
    1. 关闭CAN接口（如果已启用）
    2. 加载CAN内核模块（如果未加载）
    3. 设置CAN接口波特率
    4. 启用CAN接口
    5. 验证接口状态
    
    Args:
        channel: CAN通道名称（如'can0'）
        bitrate: 波特率（如250000）
        sudo_password: sudo密码（可选，用于普通用户执行sudo命令）
        
    Returns:
        bool: 配置成功返回True，失败返回False
        
    Note:
        - 仅在Linux系统上执行
        - root用户直接执行命令，普通用户使用sudo
        - 如果命令失败，会记录详细的错误日志
    """
    # 检查操作系统
    if sys.platform not in ['linux', 'linux2']:
        logger.warning(f"CAN接口自动配置仅支持Linux系统，当前系统: {sys.platform}")
        return False
    
    logger.info(f"开始配置CAN接口: {channel}, 波特率: {bitrate}")
    
    # 步骤1: 关闭接口（如果已启用）
    logger.debug(f"步骤1: 关闭接口 {channel}")
    success, stdout, stderr = _execute_command(
        ['ip', 'link', 'set', channel, 'down'],
        sudo_password=sudo_password
    )
    if not success:
        # 接口可能本来就是关闭的，这不是致命错误
        logger.debug(f"关闭接口时出现警告（可能接口本来就是关闭的）: {stderr}")
    
    # 步骤2: 加载CAN内核模块
    logger.debug("步骤2: 加载CAN内核模块")
    modules = ['can', 'can_raw', 'vcan']
    for module in modules:
        success, stdout, stderr = _execute_command(
            ['modprobe', module],
            sudo_password=sudo_password
        )
        if not success:
            # 模块可能已经加载，这不是致命错误
            logger.debug(f"加载模块 {module} 时出现警告（可能已加载）: {stderr}")
    
    # 步骤3: 设置波特率
    logger.debug(f"步骤3: 设置波特率 {bitrate}")
    success, stdout, stderr = _execute_command(
        ['ip', 'link', 'set', channel, 'type', 'can', 'bitrate', str(bitrate)],
        sudo_password=sudo_password
    )
    if not success:
        logger.error(f"设置波特率失败: {stderr}")
        return False
    
    # 步骤4: 启用接口
    logger.debug(f"步骤4: 启用接口 {channel}")
    success, stdout, stderr = _execute_command(
        ['ip', 'link', 'set', channel, 'up'],
        sudo_password=sudo_password
    )
    if not success:
        logger.error(f"启用接口失败: {stderr}")
        return False
    
    # 步骤5: 验证接口状态
    logger.debug(f"步骤5: 验证接口状态")
    success, stdout, stderr = _execute_command(
        ['ip', 'link', 'show', channel],
        sudo_password=sudo_password,
        use_sudo=False  # 查看状态不需要sudo
    )
    if not success:
        logger.warning(f"验证接口状态失败: {stderr}")
        # 不返回False，因为接口可能已经配置成功
    else:
        logger.debug(f"接口状态: {stdout}")
        # 检查是否包含"UP"状态
        if 'UP' in stdout:
            logger.info(f"CAN接口 {channel} 配置成功，波特率: {bitrate}")
            return True
        else:
            logger.warning(f"接口 {channel} 配置完成，但状态可能不正确: {stdout}")
            return False
    
    # 如果验证失败但前面的步骤都成功了，仍然返回True
    logger.info(f"CAN接口 {channel} 配置完成（未能验证状态）")
    return True


def reset_can_interface(
    channel: str,
    sudo_password: Optional[str] = None
) -> bool:
    """
    重置CAN接口（关闭接口）
    
    Args:
        channel: CAN通道名称（如'can0'）
        sudo_password: sudo密码（可选，用于普通用户执行sudo命令）
        
    Returns:
        bool: 重置成功返回True，失败返回False
        
    Note:
        - 仅在Linux系统上执行
        - root用户直接执行命令，普通用户使用sudo
    """
    # 检查操作系统
    if sys.platform not in ['linux', 'linux2']:
        logger.warning(f"CAN接口重置仅支持Linux系统，当前系统: {sys.platform}")
        return False
    
    logger.info(f"开始重置CAN接口: {channel}")
    
    # 关闭接口
    success, stdout, stderr = _execute_command(
        ['ip', 'link', 'set', channel, 'down'],
        sudo_password=sudo_password
    )
    
    if not success:
        logger.error(f"重置接口失败: {stderr}")
        return False
    
    logger.info(f"CAN接口 {channel} 已重置（关闭）")
    return True
