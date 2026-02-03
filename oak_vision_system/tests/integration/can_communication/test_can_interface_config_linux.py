"""
CAN接口配置工具Linux环境测试

专门测试CAN接口配置工具在Linux环境下的功能：
1. Linux系统下的配置命令构造
2. sudo权限处理逻辑
3. 命令执行成功和失败的情况

注意：此测试创建后不立即运行，留待Linux环境执行
运行环境：Linux（香橙派）⚠️

验证需求：
- 需求 1.4: 系统命令执行
- 需求 1.5: sudo权限处理
"""

import os
import sys
import subprocess
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Tuple, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from oak_vision_system.modules.can_communication.can_interface_config import (
    configure_can_interface,
    reset_can_interface,
    _is_root,
    _execute_command
)

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ==================== 测试辅助函数 ====================

def create_mock_subprocess_result(returncode: int, stdout: str = "", stderr: str = ""):
    """创建mock的subprocess.run结果"""
    mock_result = Mock()
    mock_result.returncode = returncode
    mock_result.stdout = stdout.encode('utf-8')
    mock_result.stderr = stderr.encode('utf-8')
    return mock_result


# ==================== 平台检测测试 ====================

class TestPlatformDetection:
    """平台检测测试"""
    
    def test_linux_platform_detection(self):
        """
        测试Linux平台检测
        
        验证需求：
        - 需求 1.4: 系统命令执行（仅Linux）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: Linux平台检测")
        logger.info("=" * 60)
        
        # 在Linux环境下，sys.platform应该是'linux'或'linux2'
        current_platform = sys.platform
        logger.info(f"当前平台: {current_platform}")
        
        # 验证平台检测逻辑
        is_linux = current_platform in ['linux', 'linux2']
        
        if is_linux:
            logger.info("✅ 检测到Linux平台，CAN接口配置功能可用")
        else:
            logger.warning(f"⚠️ 非Linux平台（{current_platform}），CAN接口配置功能不可用")
        
        # 在Linux环境下运行时，这个测试应该通过
        # 在其他环境下，这个测试会显示警告但不会失败
        assert isinstance(is_linux, bool), "平台检测应该返回布尔值"


# ==================== 权限检测测试 ====================

class TestPermissionHandling:
    """权限处理测试"""
    
    def test_root_detection(self):
        """
        测试root用户检测
        
        验证需求：
        - 需求 1.5: sudo权限处理
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: root用户检测")
        logger.info("=" * 60)
        
        # 检查当前用户权限
        is_root = _is_root()
        current_user = os.getenv('USER', 'unknown')
        
        logger.info(f"当前用户: {current_user}")
        logger.info(f"是否为root: {is_root}")
        
        # 验证权限检测逻辑
        if hasattr(os, 'geteuid'):
            expected_root = os.geteuid() == 0
            assert is_root == expected_root, f"root检测结果应该与os.geteuid()一致"
        else:
            # 在没有geteuid的系统上，应该返回False
            assert is_root is False, "在没有geteuid的系统上应该返回False"
        
        logger.info("✅ root用户检测测试通过")
    
    @patch('oak_vision_system.modules.can_communication.can_interface_config._is_root')
    @patch('subprocess.run')
    def test_sudo_command_construction_for_regular_user(self, mock_subprocess, mock_is_root):
        """
        测试普通用户的sudo命令构造
        
        验证需求：
        - 需求 1.5: sudo权限处理（普通用户使用sudo）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 普通用户sudo命令构造")
        logger.info("=" * 60)
        
        # 模拟普通用户
        mock_is_root.return_value = False
        mock_subprocess.return_value = create_mock_subprocess_result(0, "success", "")
        
        # 测试带密码的sudo命令
        success, stdout, stderr = _execute_command(
            ['ip', 'link', 'set', 'can0', 'down'],
            sudo_password='test_password',
            use_sudo=True
        )
        
        # 验证命令构造
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        
        # 验证命令参数
        expected_cmd = ['sudo', '-S', 'ip', 'link', 'set', 'can0', 'down']
        actual_cmd = call_args[0][0]  # 第一个位置参数
        assert actual_cmd == expected_cmd, f"sudo命令构造错误: {actual_cmd}"
        
        # 验证输入数据（密码）
        expected_input = b'test_password\n'
        actual_input = call_args[1]['input']  # input关键字参数
        assert actual_input == expected_input, f"sudo密码输入错误: {actual_input}"
        
        # 验证其他参数
        assert call_args[1]['capture_output'] is True, "应该捕获输出"
        assert call_args[1]['timeout'] == 10, "应该设置10秒超时"
        assert call_args[1]['check'] is False, "不应该自动检查返回码"
        
        assert success is True, "命令应该执行成功"
        logger.info("✅ 普通用户sudo命令构造测试通过")
    
    @patch('oak_vision_system.modules.can_communication.can_interface_config._is_root')
    @patch('subprocess.run')
    def test_sudo_command_construction_for_root_user(self, mock_subprocess, mock_is_root):
        """
        测试root用户的命令构造（不使用sudo）
        
        验证需求：
        - 需求 1.5: sudo权限处理（root用户直接执行）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: root用户命令构造")
        logger.info("=" * 60)
        
        # 模拟root用户
        mock_is_root.return_value = True
        mock_subprocess.return_value = create_mock_subprocess_result(0, "success", "")
        
        # 测试root用户执行命令
        success, stdout, stderr = _execute_command(
            ['ip', 'link', 'set', 'can0', 'down'],
            sudo_password='ignored_password',  # root用户会忽略密码
            use_sudo=True
        )
        
        # 验证命令构造
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        
        # 验证命令参数（root用户不应该添加sudo前缀）
        expected_cmd = ['ip', 'link', 'set', 'can0', 'down']
        actual_cmd = call_args[0][0]
        assert actual_cmd == expected_cmd, f"root用户命令构造错误: {actual_cmd}"
        
        # 验证输入数据（root用户不需要密码）
        actual_input = call_args[1]['input']
        assert actual_input is None, f"root用户不应该有输入数据: {actual_input}"
        
        assert success is True, "命令应该执行成功"
        logger.info("✅ root用户命令构造测试通过")


# ==================== 命令执行测试 ====================

class TestCommandExecution:
    """命令执行测试"""
    
    @patch('subprocess.run')
    def test_successful_command_execution(self, mock_subprocess):
        """
        测试成功的命令执行
        
        验证需求：
        - 需求 1.4: 系统命令执行（成功情况）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 成功的命令执行")
        logger.info("=" * 60)
        
        # 模拟成功的命令执行
        mock_subprocess.return_value = create_mock_subprocess_result(
            returncode=0,
            stdout="Interface can0 is UP",
            stderr=""
        )
        
        # 执行命令
        success, stdout, stderr = _execute_command(
            ['ip', 'link', 'show', 'can0'],
            use_sudo=False
        )
        
        # 验证结果
        assert success is True, "命令应该执行成功"
        assert stdout == "Interface can0 is UP", f"stdout应该正确解码: {stdout}"
        assert stderr == "", f"stderr应该为空: {stderr}"
        
        # 验证subprocess调用
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        assert call_args[0][0] == ['ip', 'link', 'show', 'can0'], "命令参数应该正确"
        
        logger.info("✅ 成功命令执行测试通过")
    
    @patch('subprocess.run')
    def test_failed_command_execution(self, mock_subprocess):
        """
        测试失败的命令执行
        
        验证需求：
        - 需求 1.4: 系统命令执行（失败情况）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 失败的命令执行")
        logger.info("=" * 60)
        
        # 模拟失败的命令执行
        mock_subprocess.return_value = create_mock_subprocess_result(
            returncode=1,
            stdout="",
            stderr="Cannot find device can0"
        )
        
        # 执行命令
        success, stdout, stderr = _execute_command(
            ['ip', 'link', 'show', 'can0'],
            use_sudo=False
        )
        
        # 验证结果
        assert success is False, "命令应该执行失败"
        assert stdout == "", f"stdout应该为空: {stdout}"
        assert stderr == "Cannot find device can0", f"stderr应该包含错误信息: {stderr}"
        
        logger.info("✅ 失败命令执行测试通过")
    
    @patch('subprocess.run')
    def test_command_timeout_handling(self, mock_subprocess):
        """
        测试命令超时处理
        
        验证需求：
        - 需求 1.4: 系统命令执行（超时处理）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 命令超时处理")
        logger.info("=" * 60)
        
        # 模拟命令超时
        mock_subprocess.side_effect = subprocess.TimeoutExpired(
            cmd=['ip', 'link', 'show', 'can0'],
            timeout=10
        )
        
        # 执行命令
        success, stdout, stderr = _execute_command(
            ['ip', 'link', 'show', 'can0'],
            use_sudo=False
        )
        
        # 验证结果
        assert success is False, "超时命令应该执行失败"
        assert stdout == "", "超时时stdout应该为空"
        assert stderr == "命令执行超时", f"stderr应该包含超时信息: {stderr}"
        
        logger.info("✅ 命令超时处理测试通过")
    
    @patch('subprocess.run')
    def test_command_exception_handling(self, mock_subprocess):
        """
        测试命令异常处理
        
        验证需求：
        - 需求 1.4: 系统命令执行（异常处理）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 命令异常处理")
        logger.info("=" * 60)
        
        # 模拟命令执行异常
        mock_subprocess.side_effect = OSError("No such file or directory")
        
        # 执行命令
        success, stdout, stderr = _execute_command(
            ['nonexistent_command'],
            use_sudo=False
        )
        
        # 验证结果
        assert success is False, "异常命令应该执行失败"
        assert stdout == "", "异常时stdout应该为空"
        assert "No such file or directory" in stderr, f"stderr应该包含异常信息: {stderr}"
        
        logger.info("✅ 命令异常处理测试通过")


# ==================== CAN接口配置测试 ====================

class TestCANInterfaceConfiguration:
    """CAN接口配置测试"""
    
    @patch('sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config._execute_command')
    def test_successful_can_interface_configuration(self, mock_execute):
        """
        测试成功的CAN接口配置
        
        验证需求：
        - 需求 1.2: CAN接口自动配置
        - 需求 1.3: 波特率设置
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 成功的CAN接口配置")
        logger.info("=" * 60)
        
        # 模拟所有命令都成功执行
        mock_execute.side_effect = [
            (True, "", ""),  # ip link set can0 down
            (True, "", ""),  # modprobe can
            (True, "", ""),  # modprobe can_raw
            (True, "", ""),  # modprobe vcan
            (True, "", ""),  # ip link set can0 type can bitrate 250000
            (True, "", ""),  # ip link set can0 up
            (True, "can0: <NOARP,UP,LOWER_UP> mtu 16", ""),  # ip link show can0
        ]
        
        # 执行配置
        result = configure_can_interface(
            channel='can0',
            bitrate=250000,
            sudo_password='test_password'
        )
        
        # 验证结果
        assert result is True, "CAN接口配置应该成功"
        
        # 验证命令调用顺序和参数
        expected_calls = [
            call(['ip', 'link', 'set', 'can0', 'down'], sudo_password='test_password'),
            call(['modprobe', 'can'], sudo_password='test_password'),
            call(['modprobe', 'can_raw'], sudo_password='test_password'),
            call(['modprobe', 'vcan'], sudo_password='test_password'),
            call(['ip', 'link', 'set', 'can0', 'type', 'can', 'bitrate', '250000'], sudo_password='test_password'),
            call(['ip', 'link', 'set', 'can0', 'up'], sudo_password='test_password'),
            call(['ip', 'link', 'show', 'can0'], sudo_password='test_password', use_sudo=False),
        ]
        
        mock_execute.assert_has_calls(expected_calls)
        assert mock_execute.call_count == 7, f"应该调用7次命令，实际调用{mock_execute.call_count}次"
        
        logger.info("✅ 成功CAN接口配置测试通过")
    
    @patch('sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config._execute_command')
    def test_can_interface_configuration_bitrate_failure(self, mock_execute):
        """
        测试CAN接口配置中波特率设置失败
        
        验证需求：
        - 需求 1.3: 波特率设置（失败处理）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: CAN接口配置波特率设置失败")
        logger.info("=" * 60)
        
        # 模拟波特率设置失败
        mock_execute.side_effect = [
            (True, "", ""),   # ip link set can0 down
            (True, "", ""),   # modprobe can
            (True, "", ""),   # modprobe can_raw
            (True, "", ""),   # modprobe vcan
            (False, "", "RTNETLINK answers: Invalid argument"),  # 波特率设置失败
        ]
        
        # 执行配置
        result = configure_can_interface(
            channel='can0',
            bitrate=999999,  # 无效波特率
            sudo_password='test_password'
        )
        
        # 验证结果
        assert result is False, "波特率设置失败时，配置应该失败"
        
        # 验证只调用了前5个命令（波特率设置失败后停止）
        assert mock_execute.call_count == 5, f"波特率失败后应该停止，实际调用{mock_execute.call_count}次"
        
        logger.info("✅ CAN接口配置波特率失败测试通过")
    
    @patch('sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config._execute_command')
    def test_can_interface_configuration_interface_up_failure(self, mock_execute):
        """
        测试CAN接口配置中接口启用失败
        
        验证需求：
        - 需求 1.2: CAN接口自动配置（启用失败处理）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: CAN接口配置接口启用失败")
        logger.info("=" * 60)
        
        # 模拟接口启用失败
        mock_execute.side_effect = [
            (True, "", ""),   # ip link set can0 down
            (True, "", ""),   # modprobe can
            (True, "", ""),   # modprobe can_raw
            (True, "", ""),   # modprobe vcan
            (True, "", ""),   # ip link set can0 type can bitrate 250000
            (False, "", "RTNETLINK answers: Operation not supported"),  # 接口启用失败
        ]
        
        # 执行配置
        result = configure_can_interface(
            channel='can0',
            bitrate=250000,
            sudo_password='test_password'
        )
        
        # 验证结果
        assert result is False, "接口启用失败时，配置应该失败"
        
        # 验证调用了6个命令（接口启用失败后停止）
        assert mock_execute.call_count == 6, f"接口启用失败后应该停止，实际调用{mock_execute.call_count}次"
        
        logger.info("✅ CAN接口配置接口启用失败测试通过")
    
    @patch('sys.platform', 'win32')
    def test_can_interface_configuration_non_linux_platform(self):
        """
        测试非Linux平台的CAN接口配置
        
        验证需求：
        - 需求 1.4: 系统命令执行（平台检查）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 非Linux平台CAN接口配置")
        logger.info("=" * 60)
        
        # 在非Linux平台执行配置
        result = configure_can_interface(
            channel='can0',
            bitrate=250000
        )
        
        # 验证结果
        assert result is False, "非Linux平台应该返回False"
        
        logger.info("✅ 非Linux平台CAN接口配置测试通过")


# ==================== CAN接口重置测试 ====================

class TestCANInterfaceReset:
    """CAN接口重置测试"""
    
    @patch('sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config._execute_command')
    def test_successful_can_interface_reset(self, mock_execute):
        """
        测试成功的CAN接口重置
        
        验证需求：
        - 需求 1.8: 接口重置
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 成功的CAN接口重置")
        logger.info("=" * 60)
        
        # 模拟成功的接口关闭
        mock_execute.return_value = (True, "", "")
        
        # 执行重置
        result = reset_can_interface(
            channel='can0',
            sudo_password='test_password'
        )
        
        # 验证结果
        assert result is True, "CAN接口重置应该成功"
        
        # 验证命令调用
        mock_execute.assert_called_once_with(
            ['ip', 'link', 'set', 'can0', 'down'],
            sudo_password='test_password'
        )
        
        logger.info("✅ 成功CAN接口重置测试通过")
    
    @patch('sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config._execute_command')
    def test_failed_can_interface_reset(self, mock_execute):
        """
        测试失败的CAN接口重置
        
        验证需求：
        - 需求 1.8: 接口重置（失败处理）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 失败的CAN接口重置")
        logger.info("=" * 60)
        
        # 模拟接口关闭失败
        mock_execute.return_value = (False, "", "Cannot find device can0")
        
        # 执行重置
        result = reset_can_interface(
            channel='can0',
            sudo_password='test_password'
        )
        
        # 验证结果
        assert result is False, "CAN接口重置失败时应该返回False"
        
        logger.info("✅ 失败CAN接口重置测试通过")
    
    @patch('sys.platform', 'darwin')
    def test_can_interface_reset_non_linux_platform(self):
        """
        测试非Linux平台的CAN接口重置
        
        验证需求：
        - 需求 1.8: 接口重置（平台检查）
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 非Linux平台CAN接口重置")
        logger.info("=" * 60)
        
        # 在非Linux平台执行重置
        result = reset_can_interface(channel='can0')
        
        # 验证结果
        assert result is False, "非Linux平台应该返回False"
        
        logger.info("✅ 非Linux平台CAN接口重置测试通过")


# ==================== 集成测试 ====================

class TestIntegrationScenarios:
    """集成场景测试"""
    
    @patch('sys.platform', 'linux')
    @patch('oak_vision_system.modules.can_communication.can_interface_config._execute_command')
    def test_complete_configuration_and_reset_cycle(self, mock_execute):
        """
        测试完整的配置和重置周期
        
        验证需求：
        - 需求 1.2: CAN接口自动配置
        - 需求 1.8: 接口重置
        """
        logger.info("\n" + "=" * 60)
        logger.info("测试: 完整配置和重置周期")
        logger.info("=" * 60)
        
        # 模拟配置阶段的命令执行
        configure_responses = [
            (True, "", ""),  # ip link set can0 down
            (True, "", ""),  # modprobe can
            (True, "", ""),  # modprobe can_raw
            (True, "", ""),  # modprobe vcan
            (True, "", ""),  # ip link set can0 type can bitrate 500000
            (True, "", ""),  # ip link set can0 up
            (True, "can0: <NOARP,UP,LOWER_UP> mtu 16", ""),  # ip link show can0
        ]
        
        # 模拟重置阶段的命令执行
        reset_responses = [
            (True, "", ""),  # ip link set can0 down
        ]
        
        mock_execute.side_effect = configure_responses + reset_responses
        
        # 执行配置
        config_result = configure_can_interface(
            channel='can0',
            bitrate=500000,
            sudo_password='admin123'
        )
        
        # 验证配置成功
        assert config_result is True, "CAN接口配置应该成功"
        
        # 执行重置
        reset_result = reset_can_interface(
            channel='can0',
            sudo_password='admin123'
        )
        
        # 验证重置成功
        assert reset_result is True, "CAN接口重置应该成功"
        
        # 验证总共调用了8次命令（7次配置 + 1次重置）
        assert mock_execute.call_count == 8, f"应该调用8次命令，实际调用{mock_execute.call_count}次"
        
        logger.info("✅ 完整配置和重置周期测试通过")


# ==================== 主测试函数 ====================

def run_can_interface_config_linux_tests():
    """运行CAN接口配置Linux环境测试（用于手动执行）"""
    logger.info("\n" + "=" * 80)
    logger.info("CAN接口配置工具Linux环境测试")
    logger.info("=" * 80)
    
    logger.info("注意：此测试专为Linux环境设计")
    logger.info("请在Linux系统（如香橙派）上运行此测试")
    logger.info("")
    logger.info("运行命令:")
    logger.info("pytest oak_vision_system/tests/integration/can_communication/test_can_interface_config_linux.py -v")


if __name__ == "__main__":
    run_can_interface_config_linux_tests()