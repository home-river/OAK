"""
决策层模块核心实现

DecisionLayer 类是决策层的核心，采用全局单例模式，负责：
- 接收滤波后的检测数据，进行状态判断和全局决策
- 维护设备级别的状态信息
- 发布人员警告事件
- 提供线程安全的目标坐标访问接口
"""

import logging
import threading
import time
from typing import Dict, List, Optional

import numpy as np

from oak_vision_system.core.event_bus import EventBus
from oak_vision_system.core.event_bus.event_types import EventType
from oak_vision_system.core.dto.config_dto import DecisionLayerConfigDTO

from .types import (
    DetectionStatusLabel,
    DeviceState,
    GlobalTargetObject,
    PersonWarningState,
    PersonWarningStatus,
)

logger = logging.getLogger(__name__)


def states_to_labels(state_array: np.ndarray) -> List[DetectionStatusLabel]:
    """
    将整数状态数组转换为 DetectionStatusLabel 枚举列表
    
    这是一个辅助函数，用于将向量化计算得到的整数状态数组转换为
    枚举列表，以便返回给调用者。
    
    Args:
        state_array: 整数状态数组，形状 (N,)，dtype=int32
                    值应该是 DetectionStatusLabel 的有效整数值
    
    Returns:
        DetectionStatusLabel 枚举列表，长度 N
    
    Example:
        >>> states = np.array([0, 1, 100, 101], dtype=np.int32)
        >>> labels = states_to_labels(states)
        >>> labels
        [<DetectionStatusLabel.OBJECT_GRASPABLE: 0>,
         <DetectionStatusLabel.OBJECT_DANGEROUS: 1>,
         <DetectionStatusLabel.HUMAN_SAFE: 100>,
         <DetectionStatusLabel.HUMAN_DANGEROUS: 101>]
    """
    return [DetectionStatusLabel(int(state)) for state in state_array]


class DecisionLayer:
    """
    决策层模块（全局单例）
    
    职责：
    - 接收滤波后的检测数据，进行状态判断和全局决策
    - 维护设备级别的状态信息
    - 发布人员警告事件
    - 提供线程安全的目标坐标访问接口
    
    设计特点：
    - 全局单例模式，确保系统中只有一个实例
    - 线程安全，使用 RLock 保护全局状态
    - 向量化计算，使用 NumPy 提升性能
    - 事件驱动，通过事件总线发布警告
    """
    
    # 类变量（单例模式）
    _instance: Optional['DecisionLayer'] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """
        确保全局唯一实例（线程安全）
        
        使用双重检查锁定模式：
        1. 第一次检查：避免不必要的锁获取
        2. 加锁
        3. 第二次检查：确保只创建一个实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        event_bus: EventBus,
        config: DecisionLayerConfigDTO
    ):
        """
        初始化决策层
        
        防止重复初始化：如果实例已经初始化，直接返回。
        
        Args:
            event_bus: 事件总线实例
            config: 决策层配置对象
        """
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return
        
        # 初始化事件总线引用
        self._event_bus = event_bus
        
        # 初始化配置对象
        self._config = config
        
        # 初始化设备状态字典
        self._device_states: Dict[str, DeviceState] = {}
        
        # 初始化全局目标对象和线程锁
        self._target_lock = threading.RLock()
        self._global_target_object: Optional[GlobalTargetObject] = None
        
        # 标记已初始化
        self._initialized = True
        
        logger.info(
            "决策层初始化完成: person_labels=%s, d_in=%.2f, d_out=%.2f, "
            "T_warn=%.2f, T_clear=%.2f",
            self._config.person_label_ids,
            self._config.person_warning.d_in,
            self._config.person_warning.d_out,
            self._config.person_warning.T_warn,
            self._config.person_warning.T_clear
        )
    
    @classmethod
    def get_instance(cls) -> 'DecisionLayer':
        """
        获取决策层单例实例
        
        Returns:
            DecisionLayer 实例
        
        Raises:
            RuntimeError: 实例尚未初始化
        """
        if cls._instance is None:
            raise RuntimeError("DecisionLayer 尚未初始化，请先调用构造函数")
        return cls._instance
    
    def _validate_input(
        self,
        filtered_coords: np.ndarray,
        filtered_labels: np.ndarray
    ) -> None:
        """
        验证输入数据格式（仅用于测试）
        
        此方法保留用于测试目的，在正式使用的 decide() 方法中不调用。
        采用性能优先策略，信任滤波模块的输出质量。
        
        Args:
            filtered_coords: 坐标矩阵
            filtered_labels: 标签数组
        
        Raises:
            ValueError: 输入数据格式错误
        """
        # 验证坐标数组
        if not isinstance(filtered_coords, np.ndarray):
            raise ValueError("filtered_coords 必须是 np.ndarray 类型")
        
        if filtered_coords.ndim != 2 or filtered_coords.shape[1] != 3:
            raise ValueError(
                f"filtered_coords 形状必须为 (N, 3)，当前形状: {filtered_coords.shape}"
            )
        
        # 验证标签数组
        if not isinstance(filtered_labels, np.ndarray):
            raise ValueError("filtered_labels 必须是 np.ndarray 类型")
        
        if filtered_labels.ndim != 1:
            raise ValueError(
                f"filtered_labels 形状必须为 (N,)，当前形状: {filtered_labels.shape}"
            )
        
        # 验证长度一致性
        if len(filtered_coords) != len(filtered_labels):
            raise ValueError(
                f"坐标数组长度 ({len(filtered_coords)}) 与标签数组长度 "
                f"({len(filtered_labels)}) 不一致"
            )
    
    def decide(
        self,
        device_id: str,
        filtered_coords: np.ndarray,
        filtered_labels: np.ndarray
    ) -> List[DetectionStatusLabel]:
        """
        主方法：处理单个设备的滤波数据
        
        这是决策层的核心入口方法，负责协调整个决策流程：
        1. 处理空输入情况
        2. 基于标签映射创建掩码分流
        3. 调用 _process_person() 和 _process_object() 处理不同类型的对象
        4. 合并状态数组
        5. 转换为枚举列表并返回
        
        注意：此方法不进行输入验证，信任滤波模块的输出质量。
        _validate_input() 方法保留用于测试目的。
        
        Args:
            device_id: 设备ID（字符串）
            filtered_coords: 滤波后的坐标矩阵，形状 (N, 3)，dtype=float32，单位：毫米（mm）
            filtered_labels: 滤波后的标签数组，形状 (N,)，dtype=int32
        
        Returns:
            状态标签列表，长度 N，类型 List[DetectionStatusLabel]
            每个状态标签对应一个检测对象，按原始索引顺序排列
        
        Example:
            >>> coords = np.array([[1000.0, 500.0, 0.0], [2000.0, 300.0, 0.0]], dtype=np.float32)
            >>> labels = np.array([0, 1], dtype=np.int32)  # 0=人员, 1=物体
            >>> decision_layer.decide("device_1", coords, labels)
            [<DetectionStatusLabel.HUMAN_SAFE: 100>,
             <DetectionStatusLabel.OBJECT_GRASPABLE: 0>]
        """
        # 1. 处理空输入
        if len(filtered_coords) == 0:
            return []
        
        # 2. 创建掩码分流
        # 使用 np.isin() 判断哪些标签是人员标签
        person_mask = np.isin(filtered_labels, self._config.person_label_ids)
        object_mask = ~person_mask
        
        # 3. 分流并处理
        # 使用布尔索引提取对应的坐标
        person_states = self._process_person(device_id, filtered_coords[person_mask])
        object_states = self._process_object(device_id, filtered_coords[object_mask])
        
        # 4. 合并状态数组
        # 预分配数组以提高性能
        all_states = np.empty(len(filtered_labels), dtype=np.int32)
        all_states[person_mask] = person_states
        all_states[object_mask] = object_states
        
        # 5. 转换为枚举列表
        return states_to_labels(all_states)
    
    def _update_person_state_machine(
        self,
        device_state: DeviceState,
        min_distance: float,
        current_time: float,
        device_id: str
    ) -> PersonWarningState:
        """
        更新人员警告状态机
        
        实现状态机转换逻辑：
        - SAFE -> PENDING: 人员距离 < d_in
        - PENDING -> ALARM: 危险持续时间 >= T_warn（发布 TRIGGERED 事件）
        - PENDING -> SAFE: 人员距离 >= d_out
        - ALARM -> SAFE: 离开危险区持续时间 >= T_clear（发布 CLEARED 事件）
        
        同时处理宽限期逻辑：当人员未检测到但距离最后看到时间 <= grace_time 时，
        保持当前状态。
        
        Args:
            device_state: 设备状态对象
            min_distance: 最近人员距离（毫米）
            current_time: 当前时间戳（秒）
            device_id: 设备ID（用于事件发布）
        
        Returns:
            更新后的人员警告状态
        """
        old_state = device_state.person_warning_state
        config = self._config.person_warning
        
        # 计算时间增量（使用实际时间差）
        if device_state.person_last_seen_time is not None:
            time_delta = current_time - device_state.person_last_seen_time
        else:
            time_delta = 0.0
        
        # 更新最后看到时间和距离
        device_state.person_last_seen_time = current_time
        device_state.person_distance = min_distance
        
        # 状态机转换逻辑
        if old_state == PersonWarningState.SAFE:
            # SAFE -> PENDING: 距离 < d_in
            if min_distance < config.d_in:
                device_state.person_warning_state = PersonWarningState.PENDING
                device_state.t_in = 0.0  # 重置危险持续时间
                device_state.t_out = 0.0
        
        elif old_state == PersonWarningState.PENDING:
            if min_distance >= config.d_out:
                # PENDING -> SAFE: 距离 >= d_out
                device_state.person_warning_state = PersonWarningState.SAFE
                device_state.t_in = 0.0
                device_state.t_out = 0.0
            elif min_distance < config.d_in:
                # 继续累计危险持续时间（使用实际时间差）
                device_state.t_in += time_delta
                
                # PENDING -> ALARM: t_in >= T_warn
                if device_state.t_in >= config.T_warn:
                    device_state.person_warning_state = PersonWarningState.ALARM
                    device_state.t_out = 0.0
                    # 发布警告触发事件
                    self._publish_warning_event(PersonWarningStatus.TRIGGERED, device_id)
        
        elif old_state == PersonWarningState.ALARM:
            if min_distance >= config.d_out:
                # 开始累计离开危险区时间（使用实际时间差）
                device_state.t_out += time_delta
                
                # ALARM -> SAFE: t_out >= T_clear
                if device_state.t_out >= config.T_clear:
                    device_state.person_warning_state = PersonWarningState.SAFE
                    device_state.t_in = 0.0
                    device_state.t_out = 0.0
                    # 发布警告清除事件
                    self._publish_warning_event(PersonWarningStatus.CLEARED, device_id)
            else:
                # 距离 < d_out，重置 t_out
                device_state.t_out = 0.0
        
        return device_state.person_warning_state
    
    def _publish_warning_event(
        self,
        status: PersonWarningStatus,
        device_id: str
    ) -> None:
        """
        发布人员警告事件
        
        通过事件总线发布 PERSON_WARNING 事件，通知其他模块（如通信模块）
        人员警告状态的变化。
        
        事件数据结构：
        {
            "status": PersonWarningStatus,  # TRIGGERED 或 CLEARED
            "timestamp": float              # Unix 时间戳
        }
        
        Args:
            status: 警告状态（TRIGGERED 或 CLEARED）
            device_id: 设备ID
        """
        # 构造事件数据
        event_data = {
            "status": status,
            "timestamp": time.time()
        }
        
        # 通过事件总线发布警告事件
        self._event_bus.publish(
            EventType.PERSON_WARNING,
            event_data,
            wait_all=False  # 异步发布，不等待所有订阅者处理完成
        )
        
    
    def _process_person(
        self,
        device_id: str,
        person_coords: np.ndarray
    ) -> np.ndarray:
        """
        处理人员类数据
        
        实现人员处理逻辑：
        1. 处理空输入
        2. 使用向量化操作计算欧几里得距离
        3. 获取或创建设备状态
        4. 找到最近人员距离
        5. 调用 _update_person_state_machine() 更新状态（内部会发布事件）
        6. 使用 np.where 向量化分配状态值
        7. 返回整数状态数组
        
        Args:
            device_id: 设备ID
            person_coords: 人员坐标矩阵，形状 (M, 3)，单位：毫米（mm）
        
        Returns:
            人员状态数组，形状 (M,)，dtype=int32
            值为 DetectionStatusLabel.HUMAN_SAFE (100) 或 
            DetectionStatusLabel.HUMAN_DANGEROUS (101)
        """
        # 1. 处理空输入
        if len(person_coords) == 0:
            return np.array([], dtype=np.int32)
        
        # 2. 计算距离（向量化）
        # 欧几里得距离：sqrt(x² + y² + z²)
        # 注意：输入坐标单位是毫米，直接计算即可
        distances = np.sqrt(np.sum(person_coords**2, axis=1))
        
        # 3. 获取或创建设备状态
        if device_id not in self._device_states:
            self._device_states[device_id] = DeviceState()
        
        device_state = self._device_states[device_id]
        current_time = time.time()
        
        # 4. 找到最近的人员
        min_distance = np.min(distances)
        
        # 5. 更新状态机（内部会在状态转换时发布事件）
        new_state = self._update_person_state_machine(
            device_state, min_distance, current_time, device_id
        )
        
        # 6. 分配状态值（向量化）
        # 根据距离和状态机状态分配状态标签
        config = self._config.person_warning
        
        # 使用 np.where 进行向量化状态分配
        # 逻辑：
        # - 距离 >= d_out: HUMAN_SAFE
        # - 距离 < d_in: HUMAN_DANGEROUS
        # - d_in <= 距离 < d_out: 根据状态机决定
        #   - 如果状态机为 ALARM: HUMAN_DANGEROUS
        #   - 否则: HUMAN_SAFE
        states = np.where(
            distances >= config.d_out,
            DetectionStatusLabel.HUMAN_SAFE,
            np.where(
                distances < config.d_in,
                DetectionStatusLabel.HUMAN_DANGEROUS,
                # 中间区域根据状态机决定
                DetectionStatusLabel.HUMAN_DANGEROUS if new_state == PersonWarningState.ALARM
                else DetectionStatusLabel.HUMAN_SAFE
            )
        )
        
        # 7. 返回整数状态数组
        return states.astype(np.int32)
    
    def _update_global_target(self) -> None:
        """
        更新全局待抓取目标（线程安全）
        
        从所有未过期的设备状态中选择距离最近的可抓取物体作为全局目标。
        
        实现逻辑：
        1. 收集所有未过期设备的最近可抓取物体
        2. 检查设备状态过期（超过 state_expiration_time）
        3. 清空过期设备的最近物体状态
        4. 使用线程锁保护全局目标对象
        5. 选择距离最近的物体作为全局目标
        
        线程安全：使用 _target_lock 保护全局目标对象的更新
        """
        current_time = time.time()
        candidates = []
        
        # 1. 收集所有未过期的候选物体
        for device_id, state in self._device_states.items():
            # 2. 检查状态是否过期
            if current_time - state.last_update_time > self._config.state_expiration_time:
                # 3. 清空过期状态
                state.nearest_object_coords = None
                state.nearest_object_distance = None
                continue
            
            # 收集有效候选
            if state.nearest_object_coords is not None:
                candidates.append(GlobalTargetObject(
                    coords=state.nearest_object_coords,
                    distance=state.nearest_object_distance,
                    device_id=device_id
                ))
        
        # 4 & 5. 选择距离最近的候选（线程安全）
        with self._target_lock:
            if len(candidates) == 0:
                self._global_target_object = None
            else:
                # 选择距离最小的候选作为全局目标
                self._global_target_object = min(candidates, key=lambda obj: obj.distance)
    
    def _process_object(
        self,
        device_id: str,
        object_coords: np.ndarray
    ) -> np.ndarray:
        """
        处理物体类数据
        
        实现物体处理逻辑：
        1. 处理空输入
        2. 使用向量化操作判断危险区（|y| < danger_y_threshold）
        3. 实现矩形抓取区域判断
        4. 实现半径抓取区域判断（可选）
        5. 使用 np.where 分配初始状态值
        6. 筛选可抓取物体并计算距离
        7. 更新设备最近可抓取物体状态
        8. 调用 _update_global_target() 更新全局目标
        9. 使用线程锁标记待抓取目标状态
        10. 返回整数状态数组
        
        Args:
            device_id: 设备ID
            object_coords: 物体坐标矩阵，形状 (K, 3)，单位：毫米（mm）
        
        Returns:
            物体状态数组，形状 (K,)，dtype=int32
            值为 DetectionStatusLabel.OBJECT_GRASPABLE (0)、
            DetectionStatusLabel.OBJECT_DANGEROUS (1)、
            DetectionStatusLabel.OBJECT_OUT_OF_RANGE (2) 或
            DetectionStatusLabel.OBJECT_PENDING_GRASP (3)
        """
        # 1. 处理空输入
        if len(object_coords) == 0:
            return np.array([], dtype=np.int32)
        
        # 2. 判断区域（向量化）
        x = object_coords[:, 0]
        y = object_coords[:, 1]
        z = object_coords[:, 2]
        
        # 危险区判断（使用绝对值）
        # 注意：danger_y_threshold 是绝对值阈值，判断条件为 |y| < danger_y_threshold
        is_dangerous = np.abs(y) < self._config.object_zones.danger_y_threshold
        
        # 3 & 4. 抓取区判断（根据配置模式）
        grasp_config = self._config.object_zones.grasp_zone
        
        if grasp_config.mode == "rect":
            # 矩形模式：x ∈ (x_min, x_max)，|y| ∈ (y_min, y_max)，z 无限制
            # 注意：y 使用绝对值判断
            is_graspable = (
                (x > grasp_config.x_min) & (x < grasp_config.x_max) &
                (np.abs(y) > grasp_config.y_min) & (np.abs(y) < grasp_config.y_max) &
                ~is_dangerous  # 排除危险区
            )
        else:  # radius mode
            # 半径模式：r ∈ (r_min, r_max)，其中 r = sqrt(x² + y² + z²)
            distances = np.sqrt(x**2 + y**2 + z**2)
            is_graspable = (
                (distances > grasp_config.r_min) &
                (distances < grasp_config.r_max) &
                ~is_dangerous  # 排除危险区
            )
        
        # 5. 分配初始状态（向量化）
        # 优先级：危险区 > 抓取区 > 超出范围
        states = np.where(
            is_dangerous,
            DetectionStatusLabel.OBJECT_DANGEROUS,
            np.where(
                is_graspable,
                DetectionStatusLabel.OBJECT_GRASPABLE,
                DetectionStatusLabel.OBJECT_OUT_OF_RANGE
            )
        )
        
        # 6 & 7. 更新设备最近可抓取物体
        graspable_indices = np.where(is_graspable)[0]
        nearest_idx = None  # 保存最近物体的索引（相对于 graspable_indices）
        
        if len(graspable_indices) > 0:
            # 筛选可抓取物体并计算距离
            graspable_coords = object_coords[graspable_indices]
            graspable_distances = np.sqrt(np.sum(graspable_coords**2, axis=1))
            
            # 找到距离最近的物体
            nearest_idx = np.argmin(graspable_distances)
            
            # 更新设备状态
            if device_id not in self._device_states:
                self._device_states[device_id] = DeviceState()
            
            device_state = self._device_states[device_id]
            device_state.nearest_object_coords = graspable_coords[nearest_idx].copy()
            device_state.nearest_object_distance = graspable_distances[nearest_idx]
            device_state.last_update_time = time.time()
        else:
            # 没有可抓取物体，清空状态
            if device_id in self._device_states:
                self._device_states[device_id].nearest_object_coords = None
                self._device_states[device_id].nearest_object_distance = None
        
        # 8. 更新全局目标
        self._update_global_target()
        
        # 9. 标记待抓取目标（优化版本：直接使用 device_id 和 nearest_idx）
        with self._target_lock:
            if self._global_target_object is not None:
                # 检查全局目标是否来自当前设备
                if self._global_target_object.device_id == device_id and nearest_idx is not None:
                    # 全局目标就在当前设备，直接使用 nearest_idx 标记
                    # nearest_idx 是相对于 graspable_indices 的索引
                    # graspable_indices[nearest_idx] 是相对于 object_coords 的索引
                    states[graspable_indices[nearest_idx]] = DetectionStatusLabel.OBJECT_PENDING_GRASP
        
        # 10. 返回整数状态数组
        return states.astype(np.int32)
    
    def get_target_coords_snapshot(self) -> Optional[np.ndarray]:
        """
        线程安全地获取待抓取目标坐标副本
        
        这是一个同步访问接口，供 CAN 通信模块等外部模块使用。
        使用线程锁保护全局目标对象的访问，确保线程安全。
        
        性能要求：< 0.1ms（锁获取 + 内存复制）
        
        Returns:
            目标坐标的副本（形状 (3,)），如果不存在则返回 None
            
        Example:
            >>> decision_layer = DecisionLayer.get_instance()
            >>> target_coords = decision_layer.get_target_coords_snapshot()
            >>> if target_coords is not None:
            ...     print(f"目标坐标: {target_coords}")
        """
        with self._target_lock:
            if self._global_target_object is None:
                return None
            # 返回坐标的副本，避免外部修改影响内部状态
            return self._global_target_object.coords.copy()

