"""设备匹配管理器模块

职责：
- 设备匹配算法（将在线设备匹配到配置的角色）
- 匹配结果分析和验证
- 自动重匹配功能

设计理念：
- 单一职责：只负责匹配逻辑，不负责配置持久化
- 依赖注入：依赖配置管理器获取绑定信息
- 策略模式：支持不同的匹配策略
"""

import logging
from typing import Optional, Dict, List, Set, Tuple
from dataclasses import dataclass, field, replace
from enum import Enum

from oak_vision_system.core.dto.config_dto import (
    DeviceMetadataDTO,
    DeviceRoleBindingDTO,
    DeviceRole,
    SystemConfigDTO,
)


class MatchResultType(Enum):
    """设备匹配结果类型"""
    FULL_MATCH = "full_match"           # 所有角色都匹配到设备
    PARTIAL_MATCH = "partial_match"     # 部分角色匹配到设备
    NO_MATCH = "no_match"               # 没有任何角色匹配到设备
    INVALID_CONFIG = "invalid_config"   # 配置错误

    def priority(self) -> int:
        """
        获取匹配结果优先级
        
        Returns:
            int: 优先级，数字越大优先级越高
            0: 无效配置
            1: 没有任何角色匹配到设备
            2: 部分角色匹配到设备
            3: 所有角色都匹配到设备
        """

        priority_map = {
            MatchResultType.FULL_MATCH: 3,
            MatchResultType.PARTIAL_MATCH: 2,
            MatchResultType.NO_MATCH: 1,
            MatchResultType.INVALID_CONFIG: 0
        }

        return priority_map.get(self, 0)


    def can_start(self) -> bool:
        """
        判断匹配结果是否满足启动条件
        
        Returns:
            bool: 是否满足启动条件
        """
        return self.priority() >= MatchResultType.PARTIAL_MATCH.priority()


@dataclass
class DeviceMatchResult:
    """设备匹配结果"""
    result_type: MatchResultType
    matched_bindings: List[DeviceRoleBindingDTO] = field(default_factory=list)  # 成功匹配的角色 -> 已激活的绑定对象
    unmatched_bindings: List[DeviceRoleBindingDTO] = field(default_factory=list)                      # 未匹配的角色
    
    # 空闲设备列表
    available_devices: List[DeviceMetadataDTO] = field(default_factory=list)
    
    # 错误信息（仅在配置错误时使用）
    errors: List[str] = field(default_factory=list)
    


class DeviceMatchManager:
    """
    设备匹配管理器
    
    职责：
    1. 设备匹配算法（核心）
    2. 匹配结果分析
    
    使用示例：
        config_manager = DeviceConfigManager("config.json")
        config_manager.load_config()
        
        matcher = DeviceMatchManager(config_manager)
        online_devices = OAKDeviceDiscovery.discover_devices()
        
        result = matcher.match_devices(online_devices)
        
        if result.result_type == MatchResultType.FULL_MATCH:
            start_detection(result.matched_bindings)
    """
    
    # ==================== 1. 初始化 ====================
    
    def __init__(self, bindings: List[DeviceRoleBindingDTO],
                auto_bind_new_devices: bool = True ,
                online_devices: List[DeviceMetadataDTO] = None,
                system_config: SystemConfigDTO = None):
        """
        初始化设备匹配管理器

        Args:
            bindings: 设备角色绑定配置列表，为空时自动创建默认配置
            auto_bind_new_devices: 是否自动绑定历史未记录的新设备，默认 True
            online_devices: 当前在线设备列表（可选）
        """
        
        self.logger = logging.getLogger(__name__)
        self.system_config = system_config
        if  online_devices is None:
            online_devices = []
        self.online_devices = online_devices
        if bindings is None:
            bindings = DeviceRoleBindingDTO.create_default_bingdings()


        ok, errors = DeviceMatchManager.check_bindings_roles(bindings)
        if not ok:
            raise ValueError(f"Invalid bindings: {', '.join(errors)}")
        self.bindings = bindings
        self.match_result: DeviceMatchResult = DeviceMatchResult(
            result_type=MatchResultType.NO_MATCH,
            matched_bindings=[],
            unmatched_bindings=[],
            available_devices=online_devices.copy()
        )
        self.enable_auto_bind_new_devices = auto_bind_new_devices
        self.__post_init__()
    
    def __post_init__(self):
        # 进行日志配置
        pass

    
    # ==================== 2. 配置接口 (Setters) ====================
    
    def set_online_devices(self, online_devices: List[DeviceMetadataDTO]):
        """设置在线设备列表"""
        self.online_devices = online_devices

    def set_bindings(self, bindings: List[DeviceRoleBindingDTO]):
        """
        设置绑定配置
        
        Args:
            bindings: 设备角色绑定配置列表
            
        Raises:
            ValueError: 如果绑定配置不合法
        """
        ok, errors = DeviceMatchManager.check_bindings_roles(bindings)
        if not ok:
            self.logger.error("Invalid bindings: %s", ", ".join(errors))
            raise ValueError(f"Invalid bindings: {', '.join(errors)}")
        self.bindings = bindings
        
    def set_auto_bind_new_devices(self, enable: bool) -> None:
        """
        设置是否自动绑定新设备的开关
        
        Args:
            enable: True 启用自动绑定； False 禁用
        """
        self.enable_auto_bind_new_devices = enable
    
    # ==================== 3. 核心匹配功能 ====================
    
    def default_match_devices(
        self,
        online_devices: List[DeviceMetadataDTO],
        bindings: List[DeviceRoleBindingDTO] = None
        ) -> DeviceMatchResult:
        """
        将在线设备匹配到角色绑定配置
        
        匹配策略：优先匹配 last_active_mxid，其次匹配 historical_mxids，都没有则自动绑定
        
        Args:
            online_devices: 在线设备列表
            bindings: 角色绑定配置（可选），未传入时使用内部 bindings
        
        Returns:
            DeviceMatchResult: 包含 matched_bindings、unmatched_bindings、available_devices 等信息
        """
        # 1. 更新在线设备列表
        if online_devices is not None:
            self.online_devices = online_devices

        # 2. 验证并准备 bindings
        if bindings is not None:
            # 检查绑定配置是否合法
            is_valid, errors = self.check_bindings_roles(bindings)
            if not is_valid:
                self.logger.error("Invalid bindings: %s", ", ".join(errors))
                # 配置不合法，设置错误状态并返回
                self.match_result.result_type = MatchResultType.INVALID_CONFIG
                self.match_result.errors = errors
                self.match_result.matched_bindings = []
                self.match_result.unmatched_bindings = []
                self.match_result.available_devices = []
                return self.match_result
            # 使用传入的 bindings
            self.bindings = bindings
        else:
            # 使用内部 bindings
            if not self.bindings:
                self.bindings = DeviceRoleBindingDTO.create_default_bingdings()
            
            # 验证内部 bindings
            is_valid, errors = self._check_bindings_roles()
            if not is_valid:
                self.logger.error("Invalid default bindings: %s", ", ".join(errors))
                # 配置不合法，设置错误状态并返回
                self.match_result.result_type = MatchResultType.INVALID_CONFIG
                self.match_result.errors = errors
                self.match_result.matched_bindings = []
                self.match_result.unmatched_bindings = []
                self.match_result.available_devices = []
                return self.match_result
        
        # 3. 使用历史记录进行匹配（更新 self.bindings 中的 active_mxid）
        self._bind_devices_to_roles()
        
        # 4. 自动绑定新设备（更新 self.bindings 中的 active_mxid）
        self._auto_bind_new_devices()
        
        # 5. 统一同步到 match_result（一次性完成所有更新）
        self._sync_result_from_bindings()
        # 日志记录
        if self.logger.isEnabledFor(logging.INFO):
            self.logger.info(
                "设备匹配完成: result=%s, matched=%d/%d, available=%d",
                self.match_result.result_type.value,
                len(self.match_result.matched_bindings),
                len(self.bindings),
                len(self.match_result.available_devices)
            )
        return self.match_result
    


    def auto_rematch_devices(
        self,
        online_devices: List[DeviceMetadataDTO]
    ) -> bool:
        """
        自动重新匹配设备并更新配置
        
        使用场景：
        - 设备更换后自动更新绑定
        - 按顺序重新分配设备
        
        Args:
            online_devices: 当前在线的设备列表
        
        Returns:
            是否成功重新匹配并更新配置
        """

        result = self.default_match_devices(online_devices=online_devices)
        return result.result_type.can_start()
    




    def unbind_role(self, role: DeviceRole) -> Tuple[bool, str]:
        """
        解除指定角色的设备绑定
        
        
        Args:
            role: 要解除绑定的角色
        
        Returns:
            Tuple[bool, str]: (成功/失败, 消息)
        """
        binding  = self.get_binding_by_role(role)
        if not binding:
            self.logger.warning("角色 %s 不存在于配置中", role.value)
            return (False, f"角色 {role.value} 不存在于配置中")
        
        new_binding = replace(binding, active_mxid=None)
        self._update_binding(new_binding)
        self._sync_result_from_bindings()
        self.logger.info("成功解除角色 %s 的设备绑定", role.value)
        return (True, f"成功解除角色 {role.value} 的设备绑定")

    


    def unbind_all_devices(self) -> Tuple[bool, str]:
        """解除所有设备与角色的绑定"""
        
        unbound_count = 0
        for i ,binding in enumerate(self.bindings):
            if binding.active_mxid:
                new_binding = replace(binding, active_mxid=None)
                self.bindings[i] = new_binding
                unbound_count += 1
        self._sync_result_from_bindings()
        # ✅ 合并为一条有意义的聚合日志
        if unbound_count > 0:
            self.logger.info("已解除 %d 个角色的设备绑定", unbound_count)
        return (True, "成功解除所有设备与角色的绑定")
        


    def manual_bind_device(self, role: DeviceRole, mxid: str) -> Tuple[bool, str]:
        """手动将指定设备绑定到角色"""
        
        # 1. 验证角色和设备
        binding = self.get_binding_by_role(role)
        if not binding:
            self.logger.warning("角色%s不存在于配置中", role.value)
            return (False, f"角色 {role.value} 不存在于配置中")
        
        device = self.get_device_by_mxid(mxid)
        if not device:
            self.logger.warning("设备%s不在线", mxid)
            return (False, f"设备 {mxid} 不在线")
        
        old_binding = self.get_binding_by_mxid(mxid)

        if old_binding:
            self.unbind_role(old_binding.role)
        
        new_binding = binding.set_active_Mxid_by_device(device)
        self._update_binding(new_binding)
        self._sync_result_from_bindings()
        self.logger.info("成功将设备 %s 绑定到 %s", mxid, role.value)
        return (True, f"成功将设备 {mxid} 绑定到 {role.value}")


    def swap_devices(self, role1: DeviceRole, role2: DeviceRole) -> Tuple[bool, str]:
        """
        交换两个角色的设备绑定
        
        功能说明：
        - 快速交换两个角色的 active_mxid 和 active_device_info
        - 适用于设备接反、快速测试等场景
        - 自动更新匹配结果状态
        
        使用场景：
        - 相机位置接反：左右相机设备接反了，一键交换
        - 快速调试：测试不同相机角度，无需重新插拔
        - GUI 操作：拖拽交换设备绑定
        
        Args:
            role1: 第一个角色
            role2: 第二个角色
        
        Returns:
            Tuple[bool, str]: (成功/失败, 消息)
        
        Example:
            >>> success, msg = matcher.swap_devices(DeviceRole.LEFT_CAMERA, DeviceRole.RIGHT_CAMERA)
            >>> if success:
            ...     print(msg)  # "成功交换 left_camera 和 right_camera 的设备绑定"
        """
        # 1. 查找两个角色的绑定
        binding1 = self.get_binding_by_role(role1)
        binding2 = self.get_binding_by_role(role2)
        
        if not binding1:
            self.logger.warning("角色 %s 不存在于配置中", role1.value)
            return (False, f"角色 {role1.value} 不存在于配置中，无法交换")
        if not binding2:
            self.logger.warning("角色 %s 不存在于配置中", role2.value)
            return (False, f"角色 {role2.value} 不存在于配置中，无法交换")
        
        # 2. 检查是否都有设备绑定
        if not binding1.active_mxid:
            self.logger.warning("角色 %s 当前未绑定设备，无法交换", role1.value)
            return (False, f"角色 {role1.value} 当前未绑定设备，无法交换")
        if not binding2.active_mxid:
            self.logger.warning("角色 %s 当前未绑定设备，无法交换", role2.value)
            return (False, f"角色 {role2.value} 当前未绑定设备，无法交换")
        
        # 3. 获取两个设备的元数据对象
        device1 = self.get_device_by_mxid(binding1.active_mxid)
        device2 = self.get_device_by_mxid(binding2.active_mxid)
        
        if not device1:
            self.logger.warning("设备 %s 不在线，无法交换", binding1.active_mxid)
            return (False, f"设备 {binding1.active_mxid} 不在线，无法交换")
        if not device2:
            self.logger.warning("设备 %s 不在线，无法交换", binding2.active_mxid)
            return (False, f"设备 {binding2.active_mxid} 不在线，无法交换")
        
        # 4. 交换设备绑定（自动更新历史记录）
        new_binding1 = binding1.set_active_Mxid_by_device(device2)
        new_binding2 = binding2.set_active_Mxid_by_device(device1)
        
        # 5. 更新 self.bindings（批量修改）
        self._update_binding(new_binding1)
        self._update_binding(new_binding2)
        
        # 6. 统一同步到 match_result（遵循单向数据流）
        self._sync_result_from_bindings()
        
        # 7. 返回成功消息
        self.logger.info("成功交换 %s 和 %s 的设备绑定", role1.value, role2.value)
        return (True, f"成功交换 {role1.value} 和 {role2.value} 的设备绑定")


    # ==================== 4. 配置管理 ====================
    
    @staticmethod
    def check_bindings_roles(bindings:List[DeviceRoleBindingDTO]) -> tuple[bool, List[str]]:
        """
        检查绑定结果是否合法的对外接口
        
        Args:
            bindings: DeviceRoleBindingDTO列表
        
        Returns:
            tuple[bool, List[str]]: (是否合法, 错误信息列表)
        
        Example:
            >>> result, errors = matcher.check_bindings_roles()
            >>> if result:
            >>>     print(f"配置合法")
            >>> else:
            >>>     print(f"配置不合法，错误信息：{errors}")
        """

        errors = []
        # 检查是否为空
        if not bindings:
            return (False,["绑定结果为空,请先填入默认DeviceRoleBindingDTO"])
        
        roles = [binding.role for binding in bindings]
        # 先根据role的长度判断是否有重复
        if len(roles) != len(set(roles)):
            seen = set()
            duplicates = set()  
            for role in roles:
                if role in seen:
                    duplicates.add(role)
                seen.add(role)
            if duplicates:
                errors.append(f"检测到重复角色：{[r.value for r in duplicates]}")

        # 检查是不是左右相机
        excepted_roles = DeviceRole.get_expected_roles()
        actual_roles = set(roles)

        invalid_role = actual_roles - excepted_roles
        if invalid_role:
            errors.append(f"包含非左右相机的角色：{[r.value for r in invalid_role]}")

        # 检查是否有缺失role
        missed_roles = excepted_roles - actual_roles
        if missed_roles:
            errors.append(f"缺失角色：{[r.value for r in missed_roles]}")
            
        return (len(errors) == 0,errors)
    
    def reset_to_default_bindingsResult(self):
        """
        重置匹配结果
        
        使用场景：
        - 清除当前匹配状态
        - 重新开始匹配流程
        
        Returns:
            None
            
        Example:
            >>> matcher.reset_to_default_bindingsResult()
            >>> result = matcher.default_match_devices(online_devices)
        """
        self.match_result.matched_bindings = []
        self.match_result.unmatched_bindings = []
        self.match_result.available_devices = []
        self.match_result.result_type = MatchResultType.NO_MATCH
        self.match_result.errors = []
        self.logger.info("重置匹配结果为默认值")
    
    # ==================== 5. 结果分析和验证 ====================
    
    def validate_match_result(self, result: DeviceMatchResult = None) -> Tuple[bool, List[str]]:
        """
        验证匹配结果是否满足启动条件,如果传入 None 则使用当前匹配器的匹配结果
        
        Args:
            result: 匹配结果对象
        
        Returns:
            (是否可以启动, 阻塞问题列表)
        """
        if result is None:
            result = self.match_result
        
        issues = []
        can_start = result.result_type.can_start()

        if not can_start:
            # 不能启动的情况
            if result.result_type == MatchResultType.INVALID_CONFIG:
                self.logger.error("验证过程中发现配置错误，无法启动")
                issues.append("配置错误，无法启动")
                issues.extend(result.errors)
            elif result.result_type == MatchResultType.NO_MATCH:
                self.logger.error("验证过程中发现没有任何设备匹配到角色")
                issues.append("没有任何设备匹配到角色")
        else:
            # 可以启动，但如果是部分匹配需要添加警告
            if result.result_type == MatchResultType.PARTIAL_MATCH:
                self.logger.warning("验证过程中发现部分角色未匹配 (%d 个)", len(result.unmatched_bindings))
                issues.append(f"警告：部分角色未匹配 ({len(result.unmatched_bindings)} 个)")
                for binding in result.unmatched_bindings:
                    issues.append(f"  - 缺失角色: {binding.role.value}")
        
        return (can_start, issues)
    
    def get_match_summary(self, result: DeviceMatchResult) -> str:
        """
        生成匹配结果的人类可读摘要
        
        Args:
            result: 匹配结果对象
        
        Returns:
            格式化的摘要字符串
        """

        self.logger.info("生成匹配结果的人类可读摘要")
        lines = []
        
        # 1. 匹配类型标题
        type_messages = {
            MatchResultType.FULL_MATCH: "✓ 完全匹配 - 所有角色已成功匹配设备",
            MatchResultType.PARTIAL_MATCH: "⚠ 部分匹配 - 部分角色未匹配到设备",
            MatchResultType.NO_MATCH: "✗ 无匹配 - 所有角色均未匹配到设备",
            MatchResultType.INVALID_CONFIG: "✗ 配置错误 - 绑定配置不合法"
        }
        lines.append(f"【匹配结果】{type_messages.get(result.result_type, '未知状态')}")
        lines.append("")
        
        # 2. 配置错误信息（如果有）
        if result.errors:
            lines.append("【错误信息】")
            for error in result.errors:
                lines.append(f"  - {error}")
            lines.append("")
        
        # 3. 已匹配的绑定
        if result.matched_bindings:
            lines.append(f"【已匹配角色】({len(result.matched_bindings)})")
            for binding in result.matched_bindings:
                lines.append(f"  - {binding.role.value}: {binding.active_mxid}")
            lines.append("")
        
        # 4. 未匹配的绑定
        if result.unmatched_bindings:
            lines.append(f"【未匹配角色】({len(result.unmatched_bindings)})")
            for binding in result.unmatched_bindings:
                hint = ""
                if binding.last_active_mxid:
                    hint = f" (上次: {binding.last_active_mxid})"
                elif binding.historical_mxids:
                    hint = f" (历史: {', '.join(binding.historical_mxids[:2])}...)"
                lines.append(f"  - {binding.role.value}{hint}")
            lines.append("")
        
        # 5. 空闲设备
        if result.available_devices:
            lines.append(f"【空闲设备】({len(result.available_devices)})")
            for device in result.available_devices:
                lines.append(f"  - {device.mxid}")
            lines.append("")
        
        # 6. 统计摘要
        total_roles = len(result.matched_bindings) + len(result.unmatched_bindings)
        if total_roles > 0:
            match_rate = len(result.matched_bindings) / total_roles * 100
            lines.append(f"【统计】匹配率: {match_rate:.1f}% ({len(result.matched_bindings)}/{total_roles})")
        
        return "\n".join(lines)
    
    



    
        
        
        
    
    

        
    def get_device_by_mxid(self, mxid: str) -> Optional[DeviceMetadataDTO]:
        """
        根据 MXID 查找在线设备（私有辅助方法）
        
        Args:
            mxid: 设备的唯一标识符
        
        Returns:
            DeviceMetadataDTO: 找到的设备对象，不存在返回 None
        """
        for device in self.online_devices:
            if device.mxid == mxid:
                return device
        return None


    def get_binding_by_mxid(self, mxid: str) -> Optional[DeviceRoleBindingDTO]:
        """
        根据 MXID 查找绑定信息
        
        Args:
            mxid: 设备的唯一标识符
        
        Returns:
            DeviceRoleBindingDTO: 找到的绑定对象，不存在返回 None
        """
        for binding in self.bindings:
            if binding.active_mxid == mxid:
                return binding
        return None

    def get_matched_binding_by_mxid(self, mxid: str) -> Optional[DeviceRoleBindingDTO]:
        """
        根据 MXID 查找已匹配的绑定信息
        
        Args:
            mxid: 设备的唯一标识符
        
        Returns:
            DeviceRoleBindingDTO: 找到的绑定对象，不存在返回 None
        """
        for binding in self.match_result.matched_bindings:
            if binding.active_mxid == mxid:
                return binding
        return None
    
    def get_binding_by_role(self, role: DeviceRole) -> Optional[DeviceRoleBindingDTO]:
        """
        获取指定角色的绑定信息
        
        使用场景：
        - 系统启动时验证配置
        - CLI查询特定角色状态
        - 其他模块需要获取设备信息
        
        Args:
            role: 要查询的角色
        
        Returns:
            DeviceRoleBindingDTO: 绑定信息，如果角色不存在返回 None
            
        Example:
            >>> binding = matcher.get_binding_by_role(DeviceRole.LEFT_CAMERA)
            >>> if binding and binding.active_mxid:
            ...     print(f"左相机当前绑定: {binding.active_mxid}")
            >>> else:
            ...     print("左相机未绑定设备")
        """
        for binding in self.bindings:
            if binding.role == role:
                return binding
        return None

    def get_matched_binding_by_role(self,role: DeviceRole) -> Optional[DeviceRoleBindingDTO]:
        """
        获取指定角色的已匹配绑定信息
        
        Args:
            role: 要查询的角色
        
        Returns:
            DeviceRoleBindingDTO: 绑定信息，如果角色不存在返回 None
            
        Example:
            >>> binding = matcher.get_matched_binding_by_role(DeviceRole.LEFT_CAMERA)
            >>> if binding and binding.active_mxid:
            ...     print(f"左相机当前绑定: {binding.active_mxid}")
            >>> else:
            ...     print("左相机未绑定设备")
        """

        for binding in self.match_result.matched_bindings:
            if binding.role == role:
                return binding
        return None


    def get_unmatched_roles(self) -> List[DeviceRole]:
        """
        获取所有未匹配的角色
        
        Returns:
            List[DeviceRole]: 未匹配的角色列表
            
        Example:
            >>> unmatched = matcher.get_unmatched_roles()
            >>> for role in unmatched:
            ...     print(role.value)
        """
        return [b.role for b in self.match_result.unmatched_bindings] 

    def list_matched_devices(self) -> List[Tuple[DeviceRole, str]]:
        """
        列出所有已匹配设备的绑定信息
        
        Returns:
            List[Tuple[DeviceRole, str]]: 已匹配的 (角色, MXID) 元组列表
            
        Example:
            >>> matched = matcher.list_matched_devices()
            >>> for role, mxid in matched:
            ...     print(f"{role.value}: {mxid}")
        """
        return [(device.role, device.active_mxid) for device in self.match_result.matched_bindings if device.active_mxid]

    def list_available_devices(self) -> List[DeviceMetadataDTO]:
        """
        列出所有未匹配设备的绑定信息
        
        Returns:
            List[DeviceMetadataDTO]: 未匹配的设备列表
            
        Example:
            >>> available = matcher.list_available_devices()
            >>> for device in available:
            ...     print(f"{device.role.value}: {device.mxid}")
        """
        return self.match_result.available_devices

    def get_all_bindings(self) -> List[DeviceRoleBindingDTO]:
        """
        获取所有绑定信息
        
        Returns:
            List[DeviceRoleBindingDTO]: 所有绑定信息列表
            
        Example:
            >>> bindings = matcher.get_all_bindings()
            >>> for binding in bindings:
            ...     print(f"{binding.role.value}: {binding.active_mxid}")
        """
        return self.bindings.copy()

    def is_role_matched(self, role: DeviceRole) -> bool:
        """
        检查指定角色是否已匹配设备
        
        注意：此方法检查的是当前匹配状态，而不是配置中的 active_mxid。
        只有在线设备且成功匹配的角色才会返回 True。
        
        Args:
            role: 要检查的角色
        
        Returns:
            bool: 如果角色已匹配设备返回 True，否则返回 False
        """
        binding = self.get_matched_binding_by_role(role)
        return binding is not None and binding.active_mxid is not None
        
    def is_device_bound(self, mxid: str) -> bool:
        """
        检查指定设备是否已经被绑定到角色
        
        Args:
            mxid: 设备的唯一标识符
        
        Returns:
            bool: 如果设备已经被绑定到角色返回 True，否则返回 False
        """
        for binding in self.match_result.matched_bindings:
            if binding.active_mxid == mxid:
                return True
        return False


    def get_available_device_by_mxid(self, mxid: str) -> Optional[DeviceMetadataDTO]:

        """
        根据 MXID 查找绑定信息
        
        Args:
            mxid: 设备的唯一标识符
        
        Returns:
            DeviceMetadataDTO: 找到的设备信息，不存在返回 None
        """
        for device in self.match_result.available_devices:
            if device.mxid == mxid:
                return device
        return None

    


    

        
    def get_current_status(self) -> Dict:
        """
        获取当前匹配状态（可序列化版本，用于 CLI 和监控）
        
        返回示例：
            {
                "result_type": "full_match",
                "can_start": True,
                "matched_devices": {"LEFT_CAMERA": "mxid1", ...},
                "unmatched_roles": ["MIDDLE_CAMERA"],
                "available_devices": ["mxid3"],
                "errors": []
            }
        """
        return {
            # 状态判断
            "result_type": self.match_result.result_type.value,
            "can_start": self.match_result.result_type.can_start(),
            
            # 匹配详情（可序列化为 JSON）
            "matched_devices": {
                b.role.value: b.active_mxid 
                for b in self.match_result.matched_bindings
            },
            "unmatched_roles": [
                b.role.value 
                for b in self.match_result.unmatched_bindings
            ],
            "available_devices": [
                d.mxid 
                for d in self.match_result.available_devices
            ],
            
            # 错误信息
            "errors": self.match_result.errors or []
        }
    
    
    

    
    def export_bindings(self) -> List[DeviceRoleBindingDTO]:
        """
        根据当前绑定的结果，更新绑定配置并导出
        """
        export_bindings = []
        matched_roles = {b.role for b in self.match_result.matched_bindings}

        for binding in self.bindings:
            if binding.role in matched_roles:
                export_bindings.append(self.get_matched_binding_by_role(binding.role))
            else:
                export_bindings.append(binding)

        return export_bindings

    def _update_result_type(self) -> None:
        """
        根据匹配情况更新 result_type
        
        判断逻辑：
        - FULL_MATCH: 所有角色都匹配到设备
        - PARTIAL_MATCH: 部分角色匹配到设备
        - NO_MATCH: 没有任何角色匹配到设备
        """
        matched_count = len(self.match_result.matched_bindings)
        unmatched_count = len(self.match_result.unmatched_bindings)
        total_count = matched_count + unmatched_count
        
        if matched_count == total_count and total_count > 0:
            self.match_result.result_type = MatchResultType.FULL_MATCH
        elif matched_count > 0:
            self.match_result.result_type = MatchResultType.PARTIAL_MATCH
        else:
            self.match_result.result_type = MatchResultType.NO_MATCH
        self.logger.info("update result_type to %s", self.match_result.result_type.value)

    def _auto_bind_new_devices(self):
        """
        自动将未匹配的角色按顺序绑定到可用设备（私有方法）
        
        功能说明：
        - 当历史绑定记录无法匹配到设备时，自动将空闲设备绑定到未匹配的角色
        - 按照 unmatched_bindings 和 available_devices 的顺序进行一对一绑定
        - 更新 self.bindings 中的 active_mxid（不直接修改 match_result）
        
        使用场景：
        - 新设备首次连接，历史记录中没有该设备
        - 设备更换后，旧设备不在线，需要使用新设备
        - 快速启动系统，自动分配可用设备
        
        注意事项：
        - 需要 enable_auto_bind_new_devices 开关启用
        - 会自动更新历史记录：新设备会通过 set_active_Mxid_by_device 添加到 historical_mxids
        - 同时设置 active_mxid 和 last_active_mxid 为当前设备
        - 如果可用设备数量不足，部分角色仍会保持未匹配状态
        - 调用者需要手动调用 _sync_result_from_bindings() 同步到 match_result
        
        执行逻辑：
        1. 检查自动绑定开关是否启用
        2. 从 self.bindings 计算未匹配的角色和空闲设备
        3. 按索引顺序将可用设备分配给未匹配的角色（调用 set_active_Mxid_by_device）
        4. 通过 _update_binding 更新 self.bindings 中的 active_mxid
        """
        # 1. 检查自动绑定开关
        if not self.enable_auto_bind_new_devices:
            return

        # 2. 获取当前未匹配的角色和可用设备列表
        unmatched_bindings = [b for b  in self.bindings if not b.active_mxid]
        used_mxids = {b.active_mxid for b in self.bindings if b.active_mxid}
        available_devices = [d for d in self.online_devices if d.mxid not in used_mxids]
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("自动绑定候选: unmatched=%d, available=%d", len(unmatched_bindings), len(available_devices))

        

        # 3. 按顺序将可用设备分配给未匹配的角色
        for i , binding in enumerate(unmatched_bindings):
            if i < len(available_devices):
                # 有可用设备，进行绑定
                device = available_devices[i]
                update_binding = binding.set_active_Mxid_by_device(device)
                self.logger.info("自动绑定 %s 到设备 %s", binding.role.value, device.mxid)
                self._update_binding(update_binding)
 

        
    
    def _check_bindings_roles(self, 
            bindings: List[DeviceRoleBindingDTO] | None = None) -> tuple[bool, List[str]]:
        """
        检查绑定结果是否合法（内部方法）
        
        Args:
            bindings: 要检查的绑定列表，默认为 self.bindings
        
        Returns:
            tuple[bool, List[str]]: (是否合法, 错误信息列表)
        
        Example:
            >>> result, errors = matcher.check_bindings_roles()
            >>> if result:
            >>>     print(f"配置合法")
            >>> else:
            >>>     print(f"配置不合法，错误信息：{errors}")
        """

        candidate = bindings
        if candidate is None:
            candidate = self.bindings  # 默认检查 self.bindings，而不是 matched_bindings
        result, errors = DeviceMatchManager.check_bindings_roles(candidate)
        if not result:
            self.logger.error("配置不合法，错误信息：%s", errors)
        else:
            self.logger.debug("校验通过")
        return result, errors

        
    def _sync_result_from_bindings(self):
        """
        从 self.bindings 同步到 match_result（私有方法）
        
        职责：
        - 根据 self.bindings 中的 active_mxid 重新计算 match_result
        - 更新 matched_bindings, unmatched_bindings, available_devices
        - 更新 result_type
        
        使用场景：
        - 任何修改 self.bindings 后都应该调用此方法
        
        注意：
        - self.bindings 是唯一数据源
        - match_result 是计算结果，不应该直接修改
        - 这是唯一可以修改 match_result 的方法
        """
        # 1. 根据 active_mxid 分类
        matched_bindings = []
        unmatched_bindings = []
        
        for b in self.bindings:
            if b.active_mxid:
                matched_bindings.append(b)
            else:
                unmatched_bindings.append(b)
        
        # 2. 计算已使用的设备 ID（注意：是 mxid 字符串，不是 binding 对象）
        used_mxids = {b.active_mxid for b in matched_bindings if b.active_mxid}
        
        # 3. 计算空闲设备
        available_devices = [d for d in self.online_devices if d.mxid not in used_mxids]

        # 4. 更新 match_result
        self.match_result.matched_bindings = matched_bindings
        self.match_result.unmatched_bindings = unmatched_bindings
        self.match_result.available_devices = available_devices
        self.logger.info("update match_result")
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "match_result 统计: matched=%d, unmatched=%d, available=%d",
                len(matched_bindings), len(unmatched_bindings), len(available_devices)
            )
        # 5. 更新 result_type
        self._update_result_type()


    def _update_binding(self, binding: DeviceRoleBindingDTO) -> Tuple[bool, str]:
        """
        更新 self.bindings 中指定角色的 binding（私有方法）
        
        职责：
        - 只负责替换 self.bindings 中对应角色的 binding
        - 不修改 match_result（需要调用者手动调用 _sync_result_from_bindings）
        
        设计原则：
        - self.bindings 是唯一数据源
        - match_result 是计算结果，不在此方法中修改
        - 遵循单向数据流：bindings → match_result
        
        Args:
            binding: 新的 binding 对象（会完全替换旧的）
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        
        Example:
            >>> # 绑定设备
            >>> updated = binding.set_active_Mxid_by_device(device)
            >>> success, msg = self._update_binding(updated)
            >>> self._sync_result_from_bindings()  # 同步到 match_result
            
            >>> # 解绑设备
            >>> unbound = replace(binding, active_mxid=None)
            >>> success, msg = self._update_binding(unbound)
            >>> self._sync_result_from_bindings()  # 同步到 match_result
        """
        # 查找并替换 self.bindings 中对应角色的 binding
        for i, b in enumerate(self.bindings):
            if b.role == binding.role:
                self.bindings[i] = binding
                self.logger.info("成功更新 %s 的绑定配置", binding.role.value)
                return (True, f"成功更新 {binding.role.value} 的绑定配置")
        
        # 角色不存在
        self.logger.warning("角色 %s 不存在于配置中", binding.role.value)
        return (False, f"角色 {binding.role.value} 不存在于配置中")


    # ==================== 6. 私有辅助方法 ====================
    
    def _bind_devices_to_roles(self):
        """
        批量为所有角色绑定在线设备（私有辅助方法）
        
        功能说明：
        - 使用内部维护的 self.bindings 和 self.online_devices 进行批量匹配
        - 根据历史记录为每个角色设置 active_mxid
        - 更新 self.bindings，然后通过 _sync_result_from_bindings 同步到 match_result
        
        匹配策略（两阶段匹配）：
        1. 第一阶段：优先匹配所有 binding 的 last_active_mxid
        2. 第二阶段：剩余 binding 从 historical_mxids 匹配
        
        Args:
            None
        
        Returns:
            bool: 是否执行成功（False 表示缺少必要数据）
        """
        if self.bindings is None:
            self.logger.warning("Bind devices to roles failed: bindings is None.")
            return False
        if self.online_devices is None:
            self.logger.warning("Bind devices to roles failed: online_devices is None.")
            return False
        self.logger.info("Start binding devices to roles.")
        # 1. 创建设备索引字典（mxid -> DeviceMetadataDTO），提高查找效率
        online_mxids = {device.mxid: device for device in self.online_devices}
        used_mxids = set()
        
        # 标记哪些 binding 已经匹配
        matched = [False] * len(self.bindings)
        
        # 【第一阶段】：优先匹配所有 last_active_mxid
        for i, binding in enumerate(self.bindings):
            if binding.last_active_mxid:
                if binding.last_active_mxid in online_mxids and binding.last_active_mxid not in used_mxids:
                    matched[i] = True
                    used_mxids.add(binding.last_active_mxid)
                    new_binding = binding.set_active_Mxid_by_device(online_mxids[binding.last_active_mxid])
                    self._update_binding(new_binding)
                    self.logger.info("成功绑定 %s 到设备 %s", binding.role.value, binding.last_active_mxid)
        
        # 【第二阶段】：剩余 binding 从 historical_mxids 匹配
        for i, binding in enumerate(self.bindings):
            if not matched[i] and binding.historical_mxids:
                for mxid in binding.historical_mxids:
                    if mxid in online_mxids and mxid not in used_mxids:
                        matched[i] = True
                        used_mxids.add(mxid)
                        new_binding = binding.set_active_Mxid_by_device(online_mxids[mxid])
                        self._update_binding(new_binding)
                        self.logger.info("成功绑定 %s 到设备 %s（历史记录）", binding.role.value, mxid)
                        break  # 找到一个就跳出本层循环
        
        return True
            