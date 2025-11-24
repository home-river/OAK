"""
设备配置管理器模块

职责：
- 配置文件的加载、保存、验证
- 设备角色绑定管理
- 设备匹配算法（启动时自动识别）
- OAK硬件参数配置管理
- 配置查询与统计

设计理念：
- 配置与运行分离：配置通过CLI工具修改，运行时通过此模块读取
- 设备热插拔支持：基于 historical_mxids 自动识别设备
- 类型安全：所有配置使用强类型DTO
"""

from _typeshed import Self
import json
import logging
from oak_vision_system.core.dto.config_dto.device_binding_dto import DeviceRoleBindingDTO
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import time

from oak_vision_system.core.dto.config_dto import (
    DeviceManagerConfigDTO,
    DeviceMetadataDTO,
    DeviceRoleBindingDTO,
    DeviceType,
    DeviceRole,
    OAKModuleConfigDTO,
    OAKConfigDTO,
    DisplayConfigDTO,
    CANConfigDTO,
    DataProcessingConfigDTO,
    SystemConfigDTO,
)
from oak_vision_system.utils import template_DeviceManagerConfigDTO
from .device_discovery import OAKDeviceDiscovery
from .validators import validate_dto_structure, run_all_validations,validate_against_online_devices
from .device_match import DeviceMatchManager
from oak_vision_system.utils.logging_utils import configure_logging

class MatchResultType(Enum):
    """设备匹配结果类型"""
    FULL_MATCH = "full_match"           # 所有角色都匹配到设备
    PARTIAL_MATCH = "partial_match"     # 部分角色匹配到设备
    NO_MATCH = "no_match"               # 没有任何角色匹配到设备
    DEVICE_SWAPPED = "device_swapped"   # 设备已更换（匹配到的不是 last_active_mxid）


@dataclass
class DeviceMatchResult:
    """设备匹配结果"""
    result_type: MatchResultType
    matched_roles: Dict[DeviceRole, str]    # 成功匹配的角色 -> mxid
    unmatched_roles: List[DeviceRole]       # 未匹配的角色
    swapped_roles: List[DeviceRole]         # 设备已更换的角色
    warnings: List[str]                     # 警告信息
    errors: List[str]                       # 错误信息


class ConfigNotFoundError(Exception):
    """配置文件不存在异常"""
    pass


class ConfigValidationError(Exception):
    """配置验证失败异常"""
    pass


class DeviceConfigManager:
    """
    设备配置管理器
    
    核心功能：
    1. 配置文件的加载、保存、验证
    2. 设备角色绑定管理
    3. 设备匹配算法（启动时根据 historical_mxids 自动识别设备）
    4. OAK硬件参数配置
    
    典型使用流程：
    
    ### 初次配置（通过CLI工具）
    manager = DeviceConfigManager(config_path, auto_create=True)
    devices = OAKDeviceDiscovery.discover_devices()
    config = DeviceConfigManager.get_default_config(devices)
    manager.save_config()
    
    ### 运行时加载（检测流启动）
    manager = DeviceConfigManager(config_path, auto_create=False)
    manager.load_config()  # 配置不存在会抛出异常
    
    ### 设备匹配
    online_devices = OAKDeviceDiscovery.discover_devices()
    match_result = manager.match_devices(online_devices)
    
    if match_result.result_type == MatchResultType.FULL_MATCH:
        # 启动检测流
        pass
    elif match_result.result_type == MatchResultType.PARTIAL_MATCH:
        # 警告后继续（单设备模式）
        pass
    else:
        # 提示用户重新绑定
        pass
    """
    
    # 配置文件默认路径
    DEFAULT_CONFIG_DIR = Path(__file__).parent.parent / "config"
    DEFAULT_CONFIG_FILE = "device_config.json"
    
    # historical_mxids 最大长度
    MAX_HISTORICAL_MXIDS = 5
    
    def __init__(
    self,
    config_path: Optional[str] = None,
    auto_create: bool = True,
    eager_load: bool = False,
    include_runtime_checks: bool = False,
    ) -> None:
        """
        初始化设备配置管理器

        Args:
            config_path: 配置文件路径；None 则使用默认路径 DEFAULT_CONFIG_DIR/DEFAULT_CONFIG_FILE
            auto_create: 找不到配置文件时是否自动创建默认配置
            eager_load: 是否在构造期间立即加载并校验配置（可能抛出异常）
            include_runtime_checks: 构造期校验是否包含运行态检查（通常 False）
        """
        # 规范化路径（不做实际 I/O）
        path = Path(config_path) if config_path else (self.DEFAULT_CONFIG_DIR / self.DEFAULT_CONFIG_FILE)

        # 内部状态
        self._config_path: str = str(path)
        self._auto_create: bool = auto_create
        self._config: Optional[DeviceManagerConfigDTO] = None
        self._last_modified: Optional[float] = None
        # 可运行配置及状态
        self._runnable_config: Optional[DeviceManagerConfigDTO] = None
        self._last_match_result: Optional[DeviceMatchResult] = None
        self._dirty: bool = False   # 是否需要保存到磁盘

        self.logger = logging.getLogger(__name__)

        # 可选：构造期间加载与校验
        if eager_load:
            # 加载阶段一般不开启运行态校验
            self.load_config(
                validate=True,
                auto_create=auto_create,
            )
    
    # ==================== 一、配置加载与保存 ====================
    
    def load_config(self,
                    *,
                    validate: bool = True,
                    config_path: Optional[str] = None,
                    auto_create: Optional[bool] = None
                    ) -> bool:
        """
        从JSON文件加载配置到内存
        
        工作流程：
        1. 检查配置文件是否存在
        2. 读取JSON文件
        3. 反序列化为 DeviceManagerConfigDTO
        4. 验证配置完整性
        5. 加载到内存（self._config）
        
        Returns:
            bool: 加载成功返回 True，失败返回 False
        
        Raises:
            ConfigNotFoundError: 当配置文件不存在且初始化时 auto_create=False
            ConfigValidationError: 当配置文件格式错误或验证失败
        
        
        """
        # 1) 解析路径与策略
        path = Path(config_path) if config_path else Path(self._config_path)
        if auto_create is None:
            auto_create = self._auto_create

        # 2) 不存在时处理
        if not path.exists():
            if not auto_create:
                self.logger.error("配置文件不存在且未启用自动创建: %s", path)
                raise ConfigNotFoundError(f"配置文件不存在: {path}")
            self.logger.info("配置文件不存在，将自动创建默认配置: %s", path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise ConfigValidationError(f"创建配置目录失败: {e}")
            # 2.1 生成默认配置（按项目需要构造）
            devices = OAKDeviceDiscovery.discover_devices()
            dto = DeviceConfigManager.get_default_config(devices)
            if dto is None:
                raise ConfigValidationError("默认配置创建失败：get_default_config 未实现或返回 None")
            # 2.2 可选校验（不含运行态）
            if validate:
                ok, errors = validate_dto_structure(dto)
                if not ok:
                    raise ConfigValidationError("; ".join(errors))
            # 2.3 写盘并入内存
            try:
                path.write_text(dto.to_json(indent=2), encoding="utf-8")
            except OSError as e:
                raise ConfigValidationError(f"写入配置文件失败: {e}")
            self._config = dto
            self._runnable_config = dto  # 自动创建时同时作为可运行基线
            self._dirty = False
            self._config_path = str(path)
            try:
                self._last_modified = path.stat().st_mtime
            except OSError:
                self._last_modified = None
            try:
                configure_logging(dto.system_config)
            except Exception as e:
                self.logger.error("初始化日志失败: %s", e, exc_info=True)
            self.logger.info("配置已创建: path=%s", path)
            return True

        # 3) 读取 + 反序列化
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            dto = DeviceManagerConfigDTO.from_dict(data)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            self.logger.error("配置读取/解析失败: %s, path=%s", e, path, exc_info=True)
            raise ConfigValidationError(f"配置读取/解析失败: {e}")

        # 4) 可选校验
        if validate:
            ok, errors = validate_dto_structure(dto)
            if not ok:
                raise ConfigValidationError("; ".join(errors))

        # 5) 入内存并记录元信息
        self._config = dto
        self._runnable_config = dto  # 加载后将配置作为可运行基线
        self._dirty = False  # 加载后草稿与可运行配置对齐
        self._config_path = str(path)
        try:
            self._last_modified = path.stat().st_mtime
        except OSError:
            self._last_modified = None
        try:
            configure_logging(dto.system_config)
        except Exception as e:
            self.logger.error("根据系统配置初始化日志失败: %s", e, exc_info=True)
        self.logger.info("配置已加载: path=%s", path)
        return True

    
    def save_config(self) -> bool:
        """
        将内存中的可运行配置保存到JSON文件
        
        工作流程：
        1. 验证当前配置有效性
        2. 序列化为JSON格式
        3. 原子写入（先写临时文件，再重命名）
        4. 更新配置的 last_modified 时间戳
        
        Returns:
            bool: 保存成功返回 True，失败返回 False
        
        Raises:
            ConfigValidationError: 当配置对象不存在、无效或写入失败时
        
        Example:
            manager = DeviceConfigManager()
            
            # 修改配置并晋升
            manager.promote_runnable_if_valid()
            
            # 保存
            if manager.save_config():
                print("配置已保存")
        """
        # 1. 确保有可运行配置
        if self._runnable_config is None:
            self.logger.error("当前无可运行配置可保存，请先调用 promote_runnable_if_valid() 晋升")
            raise ConfigValidationError("当前无可运行配置可保存，请先调用 promote_runnable_if_valid() 晋升")
        
        # 2. 确定路径
        if self._config_path is None:
            self._config_path = str(self.DEFAULT_CONFIG_DIR / self.DEFAULT_CONFIG_FILE)
        
        output_path = Path(self._config_path)
        
        # 3. 确保目录存在
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.logger.error("创建配置目录失败: %s, path=%s", e, output_path.parent, exc_info=True)
            raise ConfigValidationError(f"创建配置目录失败: {e}")
        
        # 4. 原子写入
        json_text = self._runnable_config.to_json(indent=2)
        temp_path = output_path.with_suffix('.tmp')
        try:
            temp_path.write_text(json_text, encoding='utf-8')
            temp_path.replace(output_path)
        except OSError as e:
            if temp_path.exists():
                temp_path.unlink()
            self.logger.error("保存配置文件失败: %s, path=%s", e, output_path, exc_info=True)
            raise ConfigValidationError(f"保存配置文件失败: {e}")
        
        # 5. 更新时间戳
        try:
            self._last_modified = output_path.stat().st_mtime
        except OSError:
            self._last_modified = None
        self.logger.info("配置已保存: path=%s", output_path)
        
        return True
            

    
    def get_config(self) -> DeviceManagerConfigDTO:
        """
        获取当前配置对象（只读）
        
        Returns:
            DeviceManagerConfigDTO: 当前配置对象
        
        Raises:
            ConfigValidationError: 当配置未加载时
        
        Example:
            config = manager.get_config()
            print(f"已配置角色数: {len(config.role_bindings)}")

        """
        if self._config is None:
            raise ConfigValidationError("当前无草稿配置，请先创建或加载配置")
        return self._config

    def get_runnable_config(self) -> DeviceManagerConfigDTO:
        """
        获取当前可运行配置对象（只读）
        
        Returns:
            DeviceManagerConfigDTO: 当前可运行配置对象

        Raises:
            ConfigValidationError: 当无可运行配置时
        """
        if self._runnable_config is None:
            raise ConfigValidationError("当前无可运行配置，请先创建或加载配置")
        return self._runnable_config

    def get_last_match_result(self) -> Optional[DeviceMatchResult]:
        """
        获取最近一次匹配结果（只读）
        
        Returns:
            Optional[DeviceMatchResult]: 最近一次匹配结果，未匹配过返回 None
        
        Example:
            result = manager.get_last_match_result()
            if result:
                print(f"匹配类型: {result.result_type.value}")
        """
        return self._last_match_result
    
    def is_dirty(self) -> bool:
        """
        检查当前草稿是否领先于可运行配置
        
        Returns:
            bool: 草稿已修改返回 True，否则返回 False
        
        Example:
            if manager.is_dirty():
                print("⚠️ 配置已修改但未晋升")
        """
        return self._dirty
    
    def has_runnable_config(self) -> bool:
        """
        检查是否存在可运行配置
        
        Returns:
            bool: 存在可运行配置返回 True，否则返回 False
        
        Example:
            if not manager.has_runnable_config():
                print("请先晋升配置")
        """
        return self._runnable_config is not None
    def create_and_set_default_config(self) -> bool:
        """
        自动检查设备在线情况，并进行默认创建和绑定，更新内部配置状态
        
        Returns:
            bool: 创建成功返回 True，失败返回 False
        """
        online_devices = OAKDeviceDiscovery.discover_devices()
        default_config = DeviceConfigManager.get_default_config(online_devices)
        default_config, match_result = DeviceConfigManager._match_config_internal(default_config, online_devices)

        # 写入实例状态：草稿与可运行配置对齐，并记录匹配结果
        self._config = default_config
        self._runnable_config = default_config
        self._last_match_result = match_result
        self._dirty = False
        self._last_modified = time.time()
        try:
            configure_logging(default_config.system_config)
        except Exception as e:
            self.logger.error("初始化日志失败: %s", e, exc_info=True)
        self.logger.info("默认配置已创建")
        return True

    # ==================== 一.1 可运行配置管理（晋升与回滚） ====================

    def promote_runnable_if_valid(
        self,
        *,
        include_runtime_checks: bool = True,
        persist: bool = False,
    ) -> DeviceManagerConfigDTO:
        """
        验证当前草稿配置的完整性和有效性，并在验证通过后将其设置为“可运行配置”。

        Args:
            include_runtime_checks (bool): 是否包含运行时校验（如active_mxid在设备列表中唯一），默认True。
            persist (bool): 验证成功后是否立即将可运行配置保存到磁盘，默认False。

        Returns:
            DeviceManagerConfigDTO: 可运行的配置对象。

        Raises:
            ConfigValidationError: 当配置未加载或验证失败时抛出异常。

        Note:
            - 该方法不会进行设备发现与自动匹配；
            - 仅对当前self._config进行一致性与完整性校验，如通过则晋升为self._runnable_config。
        """
        if self._config is None:
            raise ConfigValidationError("当前无草稿配置，请先创建或加载配置")

        ok, errors = run_all_validations(self._config, include_runtime_checks=include_runtime_checks)
        if not ok:
            raise ConfigValidationError("; ".join(errors))

        # 验证通过：更新可运行快照
        self._runnable_config = self._config
        self._dirty = False
        self.logger.info("已晋升当前草稿为可运行配置")

        if persist:
            path = Path(self._config_path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                text = self._runnable_config.to_json(indent=2)
                path.write_text(text, encoding="utf-8")
                try:
                    self._last_modified = path.stat().st_mtime
                except OSError:
                    self._last_modified = None
                self.logger.info("已保存可运行配置: path=%s", path)
            except OSError as e:
                self.logger.error("保存可运行配置失败: %s, path=%s", e, path, exc_info=True)
                raise ConfigValidationError(f"保存可运行配置失败: {e}")

        return self._runnable_config

    def restore_runnable_config(self) -> DeviceManagerConfigDTO:
        """
        回档：将当前草稿恢复为最近一次“可运行配置”快照。
        """
        if self._runnable_config is None:
            raise ConfigValidationError("不存在可运行配置快照，无法回档")

        self._config = self._runnable_config
        self._dirty = False
        self.logger.info("已回档到最近的可运行配置快照")
        return self._config
    
    # ==================== 二、配置验证 ====================
    
    def validate_config(self, *, include_runtime_checks: bool = False) -> Tuple[bool, List[str]]:
        """
        验证配置的完整性和有效性
        
        验证内容：
        1. 必需字段是否存在（config_version、role_bindings、device_metadata）
        2. 角色绑定是否合法（historical_mxids 不为空）
        3. 设备元数据是否完整（mxid、device_type）
        4. 硬件参数是否合法（模型路径、阈值范围等）
        5. 数据一致性（role_bindings 中的 mxid 在 device_metadata 中存在）
        
        Args:
            include_runtime_checks: 是否包含运行态校验（默认 False）
        
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
                - (True, []): 配置有效，无错误
                - (False, [errors]): 配置无效，包含错误列表
        
        Example:
            is_valid, errors = manager.validate_config()
            
            if is_valid:
                print("配置验证通过")
            else:
                print("配置验证失败:")
                for error in errors:
                    print(f"  - {error}")
        """
        if self._config is None:
            return False, ["配置未加载"]
        
        return run_all_validations(self._config, include_runtime_checks=include_runtime_checks)
    
    # ==================== 三、配置创建（工厂方法） ====================
    
    @staticmethod
    def get_default_config(
        devices: Optional[List[DeviceMetadataDTO]] = None,
    ) -> DeviceManagerConfigDTO:
        """
        创建并返回的默认配置（工厂方法）：根据设备列表创建未绑定的原生配置，后续需进行绑定
        
        Args:
            devices: 设备元数据列表；未提供时自动发现
        Returns:
            DeviceManagerConfigDTO: 创建的配置对象
        
        Example:
                # 生成未绑定的默认配置
                config = DeviceConfigManager.get_default_config()
        """
        # 1) 设备发现
        discovered_devices = devices if devices is not None else OAKDeviceDiscovery.discover_devices()
        if not discovered_devices:
            raise ConfigValidationError("未发现任何可用设备，无法创建默认配置")
        # 2) 创建默认配置
        default_config = template_DeviceManagerConfigDTO(discovered_devices)
        # 3) 字段内部验证
        ok ,errors = validate_dto_structure(default_config)
        if not ok:
            raise ConfigValidationError(f"创建默认配置失败: {'; '.join(errors)}")
        # 进行设备绑定
        return default_config


    @staticmethod
    def _match_config_internal(
        config: DeviceManagerConfigDTO,
        online_devices: Optional[List[DeviceMetadataDTO]] = None,
        *,
        auto_bind_new_devices: bool = True,
        validate: bool = True,
        include_runtime_checks: bool = True,
        require_at_least_one_binding: bool = True,
    ) -> Tuple[DeviceManagerConfigDTO, DeviceMatchResult]:
        """
        内部匹配配置（供设备配置流程内部调用），支持字段内部验证、自动绑定与一致性校验。

        此方法适合高级流程或自动化流程内部使用，实现逻辑包括：
          1. 结构/角色绑定预验证；2. 调用 DeviceMatchManager 进行匹配/自动绑定；
          3. 匹配结果聚合与配置 DTO 更新；4. 最终一致性校验、运行时校验可选。

        参数说明:
            config : DeviceManagerConfigDTO
                配置对象，须为设备配置管理全量数据 DTO。
            online_devices : Optional[List[DeviceMetadataDTO]]
                当前在线设备元数据列表，必须以列表形式传入，若为 None 则报错。
            auto_bind_new_devices : bool, default=True
                是否自动绑定历史中未记录的新设备（针对新插入或首次上线设备）。
            validate : bool, default=True
                匹配后是否立即做全量一致性校验 (run_all_validations)，推荐上线时保持 True。
            include_runtime_checks : bool, default=True
                校验阶段是否启用运行态一致性比对（如 mxid 是否在线等）。
            require_at_least_one_binding : bool, default=True
                匹配后是否强制至少有一个角色绑定成功，否则 raise 异常。

        返回:
            Tuple[DeviceManagerConfigDTO, DeviceMatchResult]
                匹配结果与更新后的配置对象。
                - new_config : 新配置（角色绑定经过自动映射与修正、DTO已变更，不自动保存）
                - result : 匹配详细结果 DeviceMatchResult

        异常:
            - ConfigValidationError: 绑定/设备列表不合法或规则不满足时抛出，异常文本可直接用于 CLI/日志显示。


        补充说明:
            - 本方法充分复用 DeviceMatchManager 的逻辑，并在内部实现配置对象不可变更新（with_updates）
            - 本方法不会自动保存，需调用方决定是否写入磁盘等
        """
        # 1. 拆解出所有角色绑定，预做角色集合和内部逻辑合法性校验
        bindings = list(config.oak_module.role_bindings.values())
        ok, errors = DeviceMatchManager.check_bindings_roles(bindings)
        if not ok:
            # 角色绑定结构不合法（如无角色/重复/非法），直接异常
            raise ConfigValidationError(f"非法 bindings: {', '.join(errors)}")
        if online_devices is None:
            # 匹配必须有在线设备清单
            raise ConfigValidationError("online_devices 不能为空")

        # 2. 创建匹配管理器，传递绑定关系和在线设备，支持自动绑定新设备
        matcher = DeviceMatchManager(
            bindings,
            auto_bind_new_devices=auto_bind_new_devices,
            online_devices=online_devices,
        )
        # 3. 执行一次标准匹配，自动更新绑定内容
        result = matcher.default_match_devices()

        # 4. 若要求必须有至少一个角色完成绑定，否则认为配置失败
        if require_at_least_one_binding and result.result_type == MatchResultType.NO_MATCH:
            raise ConfigValidationError("匹配失败：至少需要一个角色完成绑定")

        # 5. 导出并整理出新的 role_bindings，生成新的配置对象
        match_bindings = matcher.export_bindings()
        # 以 role 作为字典 key，重组绑定结构，保持类型强一致
        role_bindings = {binding.role: binding for binding in match_bindings}
        # 用 DTO 的 with_updates 方法生成新的 OAKModuleConfigDTO 和 DeviceManagerConfigDTO
        new_oak_module = config.oak_module.with_updates(role_bindings=role_bindings)
        new_config = config.with_updates(oak_module=new_oak_module)

        # 6. 可选：最终一致性校验（含字段/跨字段/运行时校验，便于运维/开发查错）
        if validate:
            ok_all, errs_all = run_all_validations(new_config, include_runtime_checks=include_runtime_checks)
            if not ok_all:
                raise ConfigValidationError("; ".join(errs_all))

        # 返回新配置和匹配结果
        return new_config, result


        

    


    # =========配置导出================

    def get_oak_module_config(self) -> OAKModuleConfigDTO:
        """获取 OAK 模块配置"""
        if self.get_runnable_config() is None:
            raise ConfigValidationError("当前无可运行配置，请先创建或加载配置")
        return self.get_runnable_config().oak_module

    def get_data_processing_config(self) -> DataProcessingConfigDTO:
        """获取数据处理模块配置"""
        if self.get_runnable_config() is None:
            raise ConfigValidationError("当前无可运行配置，请先创建或加载配置")
        return self.get_runnable_config().data_processing_config

    def get_can_config(self) -> CANConfigDTO:
        """获取 CAN 模块配置"""
        if self.get_runnable_config() is None:
            raise ConfigValidationError("当前无可运行配置，请先创建或加载配置")
        return self.get_runnable_config().can_config

    def get_display_config(self) -> DisplayConfigDTO:
        """获取显示模块配置"""
        if self.get_runnable_config() is None:
            raise ConfigValidationError("当前无可运行配置，请先创建或加载配置")
        return self.get_runnable_config().display_config

    def get_system_config(self) -> SystemConfigDTO:
        """获取系统模块配置"""
        if self.get_runnable_config() is None:
            raise ConfigValidationError("当前无可运行配置，请先创建或加载配置")
        return self.get_runnable_config().system_config
    

