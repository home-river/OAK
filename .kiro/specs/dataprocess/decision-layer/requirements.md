# 需求文档：决策层模块

## 简介

决策层模块是数据处理流水线的核心决策组件，**嵌入在 DataProcessor 中**，位于**滤波处理之后、数据组装之前**。该模块通过维护**设备级别的状态**，对每个设备的滤波数据进行增量更新和决策，无需等待所有设备数据到齐。决策层通过**事件机制**发布人员警告和目标坐标信息，是连接数据处理和渲染/通信模块的关键桥梁。

**架构特点**：
- **嵌入式设计**：作为 DataProcessor 的组件，同步调用，无独立线程
- **全局单例**：决策层在系统中全局唯一，确保状态一致性和资源管理
- **增量更新**：每个设备独立维护状态，无需等待其他设备
- **状态管理**：维护设备级别的人员距离状态和最近可抓取物体状态
- **全局决策**：基于所有设备的状态进行全局比较，选择待抓取目标
- **事件驱动**：通过事件总线发布警告事件
- **同步访问接口**：提供线程安全的同步方法供 CAN 通信模块零延迟访问目标坐标
- **向量化计算**：使用整数 ndarray 进行状态计算，最后转换为枚举列表

**数据流说明**：
```
原始检测数据 → 坐标变换 → 滤波处理 → [决策层] → 数据组装 → 输出
                                      ↓
                                  事件发布 → 通信模块
```

**单设备处理流程**：
```
设备A滤波数据 → decide(A) → 分流 → _process_person(A) + _process_object(A) → 合并 → 状态标签A
设备B滤波数据 → decide(B) → 分流 → _process_person(B) + _process_object(B) → 合并 → 状态标签B
```

**决策层方法架构**：
```python
class DecisionLayer:
    def decide(device_id, filtered_coords, filtered_labels):
        """主方法：分流、调用处理方法、合并输出"""
        # 1. 基于 labels_map 创建掩码分流
        # 2. 调用 _process_person() 和 _process_object()
        # 3. 合并状态数组并转换为枚举列表
        
    def _process_person(device_id, person_coords):
        """人员处理方法：距离计算、状态机更新、事件发布"""
        # 返回人员状态数组（HUMAN_SAFE/HUMAN_DANGEROUS）
        
    def _process_object(device_id, object_coords):
        """物体处理方法：区域判断、最近物体更新、全局目标选择"""
        # 返回物体状态数组（OBJECT_GRASPABLE/DANGEROUS/OUT_OF_RANGE/PENDING_GRASP）
```

**决策层输入**（单设备，每次调用）：
- `device_id`：设备ID（字符串）
- `filtered_coords`：滤波后的坐标矩阵，形状 (N, 3)，dtype=float32
- `filtered_labels`：滤波后的标签数组，形状 (N,)，dtype=int32

**决策层输出**（单设备，每次调用）：
- `state_labels`：状态标签列表，长度 N，类型 List[DetectionStatusLabel]

**决策层维护的状态**（跨设备）：
- 每个设备的人员最近距离和危险区域持续时间
- 每个设备的最近可抓取物体坐标和距离
- 全局待抓取目标坐标（使用线程锁保护）

**决策层发布的事件**：
- `PERSON_WARNING`：人员警告事件（包含状态标志：TRIGGERED/CLEARED，由 _process_person() 发布）

**决策层提供的同步接口**：
- `get_target_coords_snapshot()`：线程安全地获取待抓取目标坐标副本（供 CAN 通信模块使用）
- `get_instance()`：获取决策层全局单例实例

## 术语表

- **Decision_Layer**：决策层模块，嵌入在 DataProcessor 中，负责状态管理和决策逻辑
- **Device_State**：设备状态，包含该设备的人员距离状态和最近可抓取物体状态
- **Filtered_Coords**：滤波后的坐标矩阵，形状 (N, 3)，dtype=float32
- **Filtered_Labels**：滤波后的标签数组，形状 (N,)，dtype=int32
- **Detection_Object**：检测对象，由滤波后的坐标和标签表示
- **Status_Label**：状态标签，表示检测对象的当前状态（可抓取、危险等）
- **State_Array**：状态数组，整数类型的 ndarray，形状 (N,)，用于向量化计算状态标签
- **DetectionStatusLabel**：状态标签枚举类型（IntEnum），可直接与整数值互转
- **labels_map**：标签映射配置，定义哪些 YOLO 标签值对应人员（例如 [0] 表示人员）
- **Graspable_Object**：可抓取物体，指非人类的检测对象
- **Person_Object**：人员对象，指检测为人类的对象
- **Target_Object**：待抓取目标物体，全局选择的最近可抓取物体
- **Danger_Zone**：危险区域，基于 y 坐标绝对值判断（|y| < danger_y_threshold），表示过于靠近车体。danger_y_threshold 是一个绝对值阈值，默认 1500.0 mm
- **Grasp_Zone**：抓取区域，定义为机器人可以成功抓取物体的范围
  - 矩形模式：x ∈ (x_min, x_max)，|y| ∈ (y_min, y_max)，z 无限制
  - 半径模式：r ∈ (r_min, r_max)，其中 r = sqrt(x² + y² + z²)
- **Out_Of_Range_Zone**：无法抓取区域，不在危险区和抓取区内的其他区域
- **Person_Warning_State**：人员警告状态，包括 SAFE（安全）、PENDING（潜在危险）、ALARM（危险告警）
- **d_in**：进入危险区距离阈值，人员距离小于此值进入危险区，默认 3.0 米
- **d_out**：离开危险区距离阈值，人员距离大于等于此值离开危险区（d_out > d_in，用于防抖动），默认 3.2 米
- **T_warn**：警告触发时间阈值，危险持续时间达到此值触发警告，默认 3.0 秒
- **T_clear**：警告清除时间阈值，离开危险区持续时间达到此值清除警告，默认 3.0 秒
- **grace_time**：目标消失宽限期，人员未检测到但不超过此时间不清空状态，默认 0.5 秒
- **Warning_Event**：人员警告事件，包含警告状态（TRIGGERED/CLEARED）、设备ID、距离和持续时间
- **PersonWarningStatus**：警告状态枚举，包括 TRIGGERED（警告触发）和 CLEARED（警告清除）
- **Communication_Module**：通信模块，通过事件机制与决策层交互
- **Vectorized_Operation**：向量化操作，使用 NumPy 批量处理数组以提高性能
- **Incremental_Update**：增量更新，每个设备独立更新状态，无需等待其他设备
- **State_Expiration**：设备状态过期，当设备的最后更新时间超过阈值（默认 1 秒）时，该设备的最近可抓取物体状态将被清空

## 需求

### 需求组 A：主方法与数据分流

#### 需求 1：主方法 decide() - 单设备滤波数据处理

**用户故事**：作为系统架构师，我希望决策层的主方法能够接收单个设备的滤波数据，协调分流和处理流程，并输出状态标签列表。

**验收标准**：

1. THE Decision_Layer SHALL 提供 `decide(device_id, filtered_coords, filtered_labels)` 方法作为主入口
2. WHEN decide() 接收到单个设备的 Filtered_Coords 和 Filtered_Labels THEN THE 方法 SHALL 处理该设备的所有检测对象
3. WHEN 输入数据为空（零个检测对象）THEN THE decide() SHALL 返回空的状态标签列表
4. THE decide() SHALL 调用数据分流逻辑创建 person_mask 和 object_mask
5. THE decide() SHALL 调用 _process_person() 处理人员类数据
6. THE decide() SHALL 调用 _process_object() 处理物体类数据
7. THE decide() SHALL 使用掩码合并两个处理方法返回的状态数组
8. THE decide() SHALL 调用 states_to_labels() 将整数状态数组转换为枚举列表
9. WHEN decide() 完成处理 THEN THE 方法 SHALL 返回与输入长度一致的状态标签列表

**处理流程**：

```
输入: device_id, Filtered_Coords, Filtered_Labels
  ↓
创建标签掩码 (person_mask, object_mask) [基于 labels_map]
  ↓
数据分流
  ├─→ person_coords = Filtered_Coords[person_mask]
  │   ↓
  │   _process_person(device_id, person_coords)
  │   ↓
  │   person_state_array (整数 ndarray)
  │
  └─→ object_coords = Filtered_Coords[object_mask]
      ↓
      _process_object(device_id, object_coords)
      ↓
      object_state_array (整数 ndarray)
  ↓
使用掩码合并状态数组
  all_states = np.empty(len(labels), dtype=np.int32)
  all_states[person_mask] = person_state_array
  all_states[object_mask] = object_state_array
  ↓
转换为枚举标签列表
  status_labels = states_to_labels(all_states)
  ↓
输出: List[DetectionStatusLabel] (按原始索引顺序)
```

---

#### 需求 2：数据分流逻辑

**用户故事**：作为系统开发者，我希望决策层能够基于标签映射将检测对象分流为人员和物体两类，以便应用不同的决策逻辑。

**验收标准**：

1. THE Decision_Layer SHALL 接受标签映射配置（labels_map），定义哪些 YOLO 标签值对应人员
2. WHEN 执行分流时 THEN THE Decision_Layer SHALL 使用 `np.isin(filtered_labels, person_label_ids)` 创建 person_mask
3. WHEN person_mask 创建完成 THEN THE Decision_Layer SHALL 创建 object_mask = ~person_mask
4. THE Decision_Layer SHALL 使用 NumPy 布尔索引进行分流，而非 Python 循环
5. THE Decision_Layer SHALL 提供默认的标签映射配置（如 label=0 表示人员）
6. WHEN 检测对象的标签在人员标签列表中 THEN THE 对象 SHALL 被识别为 Person_Object
7. WHEN 检测对象的标签不在人员标签列表中 THEN THE 对象 SHALL 被识别为 Graspable_Object


---

#### 需求 3：向量化状态计算

**用户故事**：作为系统开发者，我希望决策层使用向量化的整数数组进行状态计算，以便提升性能并简化掩码合并操作。

**验收标准**：

1. THE Decision_Layer SHALL 在内部使用整数类型的 ndarray（State_Array）进行状态计算
2. THE _process_person() SHALL 返回整数状态数组，使用 DetectionStatusLabel 的整数值（100, 101）
3. THE _process_object() SHALL 返回整数状态数组，使用 DetectionStatusLabel 的整数值（0, 1, 2, 3）
4. THE Decision_Layer SHALL 使用 NumPy 向量化操作（如 `np.where`、布尔索引）计算状态数组
5. WHEN 合并 person 类和物体类状态时 THEN THE decide() SHALL 使用掩码索引直接赋值整数数组
6. THE decide() SHALL 调用 `states_to_labels()` 函数将整数数组转换为 DetectionStatusLabel 枚举列表
7. THE Decision_Layer SHALL 避免在状态计算过程中创建枚举对象，仅在最终输出时转换
8. THE Decision_Layer SHALL 确保转换后的枚举列表长度与输入检测对象数量一致

**实现示例**：

```python
# 伪代码示例
def decide(device_id, filtered_coords, filtered_labels):
    # 1. 创建掩码
    person_mask = np.isin(filtered_labels, [0])  # 假设 0 是人员标签
    object_mask = ~person_mask
    
    # 2. 分流并处理
    person_states = self._process_person(device_id, filtered_coords[person_mask])
    object_states = self._process_object(device_id, filtered_coords[object_mask])
    
    # 3. 合并状态数组
    all_states = np.empty(len(filtered_labels), dtype=np.int32)
    all_states[person_mask] = person_states
    all_states[object_mask] = object_states
    
    # 4. 转换为枚举列表
    return states_to_labels(all_states)
```

---

### 需求组 B：人员处理方法 _process_person()

#### 需求 4：人员危险距离判断

**用户故事**：作为安全管理员，我希望人员处理方法能够基于滤波后的坐标计算距离并判断危险状态，以便及时发出警告。

**验收标准**：

1. THE _process_person() SHALL 接受 device_id 和 person_coords 作为输入参数
2. THE _process_person() SHALL 使用欧几里得距离公式计算每个人员到原点的距离：`distances = np.sqrt(np.sum(person_coords**2, axis=1))`
3. WHEN 人员距离 >= d_out THEN THE _process_person() SHALL 为该人员分配状态值 DetectionStatusLabel.HUMAN_SAFE (100)
4. WHEN 人员距离 < d_in THEN THE _process_person() SHALL 为该人员分配状态值 DetectionStatusLabel.HUMAN_DANGEROUS (101)
5. WHEN 人员距离在 d_in 和 d_out 之间 THEN THE _process_person() SHALL 根据当前设备的警告状态机决定状态值
6. THE _process_person() SHALL 返回整数状态数组，形状 (M,)，其中 M 是人员数量
7. WHEN person_coords 为空数组 THEN THE _process_person() SHALL 返回空的整数数组

---

#### 需求 5：人员警告状态机管理

**用户故事**：作为系统开发者，我希望人员处理方法能够通过状态机管理人员警告逻辑，以便实现防抖动和防漏报功能。

**验收标准**：

1. THE Decision_Layer SHALL 为每个设备维护人员警告状态机，包含 SAFE、PENDING、ALARM 三种状态
2. WHEN 当前状态为 SAFE 且检测到人员距离 < d_in THEN THE _process_person() SHALL 转换状态为 PENDING 并开始累计 t_in
3. WHEN 当前状态为 PENDING 且 t_in >= T_warn THEN THE _process_person() SHALL 转换状态为 ALARM
4. WHEN 当前状态为 PENDING 且人员距离 >= d_out THEN THE _process_person() SHALL 转换状态为 SAFE 并重置 t_in 和 t_out
5. WHEN 当前状态为 ALARM 且人员距离 >= d_out THEN THE _process_person() SHALL 开始累计 t_out
6. WHEN 当前状态为 ALARM 且 t_out >= T_clear THEN THE _process_person() SHALL 转换状态为 SAFE 并重置 t_in 和 t_out
7. WHEN 未检测到人员但距离最后看到时间 <= grace_time THEN THE _process_person() SHALL 保持当前状态（宽限期）
8. WHEN 未检测到人员且距离最后看到时间 > grace_time THEN THE _process_person() SHALL 根据当前状态执行相应的清除逻辑
9. THE _process_person() SHALL 使用回差机制（d_in < d_out）防止距离阈值附近的抖动
10. THE _process_person() SHALL 更新设备状态中的人员最近距离、最后看到时间、t_in 和 t_out


---

#### 需求 6：人员警告事件发布

**用户故事**：作为安全管理员，我希望当人员警告状态发生关键转换时，人员处理方法能够发布统一的警告事件，以便通信模块触发或停止警报。

**验收标准**：

1. WHEN 人员警告状态从 PENDING 转为 ALARM THEN THE _process_person() SHALL 发布 PERSON_WARNING 事件，状态为 TRIGGERED
2. WHEN 人员警告状态从 ALARM 转为 SAFE THEN THE _process_person() SHALL 发布 PERSON_WARNING 事件，状态为 CLEARED
3. WHEN PERSON_WARNING 事件被发布 THEN THE 事件 SHALL 包含以下字段：
   - status：PersonWarningStatus（枚举值，TRIGGERED 或 CLEARED）
   - timestamp：事件时间戳（float，Unix 时间戳）
4. THE _process_person() SHALL 通过事件总线发布警告事件
5. THE _process_person() SHALL 确保每次状态转换只发布一次对应事件
6. THE PERSON_WARNING 事件 SHALL 使用统一的数据结构，通过 status 字段区分触发和清除

**事件数据结构**：

```python
# PersonWarningStatus 枚举定义
class PersonWarningStatus(Enum):
    TRIGGERED = "triggered"  # 警告触发
    CLEARED = "cleared"      # 警告清除

# PERSON_WARNING 事件数据
{
    "status": PersonWarningStatus,         # 警告状态（TRIGGERED/CLEARED）
    "timestamp": float                     # 事件时间戳
}
```

---

### 需求组 C：物体处理方法 _process_object()

#### 需求 7：物体抓取区域判断

**用户故事**：作为机器人操作员，我希望物体处理方法能够根据物体的滤波后坐标判断其所在区域，以便分配正确的抓取状态。

**验收标准**：

1. THE _process_object() SHALL 接受 device_id 和 object_coords 作为输入参数
2. THE _process_object() SHALL 基于物体坐标判断其所在区域（危险区/抓取区/超出范围区）
3. WHEN 物体的 y 坐标绝对值小于 danger_y_threshold（即 |y| < danger_y_threshold）THEN THE _process_object() SHALL 分配状态值 DetectionStatusLabel.OBJECT_DANGEROUS (1)
4. WHEN 物体在抓取区域内（Grasp_Zone）THEN THE _process_object() SHALL 分配状态值 DetectionStatusLabel.OBJECT_GRASPABLE (0)
5. WHEN 物体在无法抓取区域内（Out_Of_Range_Zone）THEN THE _process_object() SHALL 分配状态值 DetectionStatusLabel.OBJECT_OUT_OF_RANGE (2)
6. THE _process_object() SHALL 支持矩形抓取区域配置（x_min, x_max, y_min, y_max）
   - 矩形判断：`(x_min < x < x_max) & (y_min < |y| < y_max)`
7. THE _process_object() SHALL 支持半径抓取区域配置（r_min, r_max）作为替代方案
   - 半径判断：`r_min < sqrt(x² + y² + z²) < r_max`
8. THE _process_object() SHALL 使用 NumPy 向量化操作进行区域判断
9. THE _process_object() SHALL 返回整数状态数组，形状 (K,)，其中 K 是物体数量
10. WHEN object_coords 为空数组 THEN THE _process_object() SHALL 返回空的整数数组

---

#### 需求 8：设备级别最近可抓取物体更新

**用户故事**：作为系统开发者，我希望物体处理方法能够维护该设备的最近可抓取物体信息，以便支持全局目标选择。

**验收标准**：

1. THE _process_object() SHALL 筛选出该设备的抓取区域内的物体（状态为 OBJECT_GRASPABLE）
2. WHEN 存在可抓取物体时 THEN THE _process_object() SHALL 计算每个物体到原点的欧几里得距离
3. WHEN 存在可抓取物体时 THEN THE _process_object() SHALL 选择距离最近的物体更新该设备的 Device_State
4. WHEN 不存在可抓取物体时 THEN THE _process_object() SHALL 将该设备的最近可抓取物体信息设置为 None
5. THE _process_object() SHALL 在 Device_State 中记录最近可抓取物体的坐标和距离
6. THE _process_object() SHALL 在 Device_State 中记录最后更新时间戳
7. THE _process_object() SHALL 使用 NumPy 向量化操作筛选和查找最近物体
8. THE _process_object() SHALL 使用欧几里得距离公式：`distances = np.sqrt(np.sum(object_coords**2, axis=1))`


---

#### 需求 9：全局待抓取目标选择与状态标记

**用户故事**：作为机器人操作员，我希望物体处理方法能够参与全局目标选择，并为待抓取目标分配特殊状态。

**验收标准**：

1. WHEN _process_object() 更新完当前设备的最近可抓取物体后 THEN THE 方法 SHALL 从所有设备的最近可抓取物体中选择全局 Target_Object
2. WHEN 选择全局 Target_Object 时 THEN THE _process_object() SHALL 只考虑未过期的设备状态（更新时间在 1 秒内）
3. WHEN 存在多个候选物体时 THEN THE _process_object() SHALL 选择距离最近的物体作为 Target_Object
4. WHEN 没有候选物体时 THEN THE _process_object() SHALL 清除全局 Target_Object 信息
5. THE _process_object() SHALL 保存全局 Target_Object 的坐标信息
6. WHEN 物体是当前的全局 Target_Object THEN THE _process_object() SHALL 将其状态值修改为 DetectionStatusLabel.OBJECT_PENDING_GRASP (3)
7. THE _process_object() SHALL 通过比较物体坐标与全局 Target_Object 坐标来判断是否为待抓取目标
8. THE _process_object() SHALL 使用线程锁（RLock）保护全局 Target_Object 的更新操作
9. THE _process_object() SHALL 调用内部方法 `_update_global_target()` 更新全局目标，确保线程安全

---

### 需求组 D：设备状态管理与配置

#### 需求 10：设备级别状态管理

**用户故事**：作为系统开发者，我希望决策层能够维护每个设备的状态信息，以便支持增量更新、状态机管理和全局决策。

**验收标准**：

1. THE Decision_Layer SHALL 为每个设备维护独立的 Device_State
2. WHEN 处理设备数据时 THEN THE _process_person() 和 _process_object() SHALL 更新该设备的 Device_State
3. THE Device_State SHALL 包含人员警告状态机的当前状态（SAFE/PENDING/ALARM）
4. THE Device_State SHALL 包含人员最近距离和最后看到时间
5. THE Device_State SHALL 包含危险持续时间（t_in）和清空时间（t_out）
6. THE Device_State SHALL 包含最近可抓取物体的坐标和距离
7. THE Device_State SHALL 包含最后更新时间戳
8. THE Decision_Layer SHALL 使用字典结构存储设备状态，以 device_id 为键

---

#### 需求 11：状态过期检查

**用户故事**：作为系统开发者，我希望决策层能够检查设备状态是否过期并自动清空，以便避免使用陈旧数据进行全局决策。

**验收标准**：

1. THE Decision_Layer SHALL 在每个 Device_State 中记录最后更新时间戳
2. WHEN _process_object() 选择全局 Target_Object 时 THEN THE 方法 SHALL 检查每个设备状态的更新时间
3. WHEN 设备状态的更新时间超过 1 秒 THEN THE _process_object() SHALL 认为该状态已过期
4. WHEN 设备状态已过期 THEN THE _process_object() SHALL 清空该设备的最近可抓取物体状态（设置为 None）
5. THE Decision_Layer SHALL 使用当前系统时间与最后更新时间的差值判断是否过期
6. THE Decision_Layer SHALL 使用 `time.time()` 或等效方法获取当前时间戳


---

#### 需求 12：距离阈值与区域配置

**用户故事**：作为系统配置员，我希望能够配置各种距离阈值、时间阈值和区域参数，以便适应不同的应用场景。

**验收标准**：

1. THE Decision_Layer SHALL 从 DataProcessingConfigDTO.decision_layer_config 读取配置参数
2. THE DecisionLayerConfigDTO SHALL 包含人员警告配置（PersonWarningConfigDTO）
3. THE PersonWarningConfigDTO SHALL 包含以下参数：
   - d_in：进入危险区距离阈值（默认 3.0 米）
   - d_out：离开危险区距离阈值（默认 3.2 米，且 d_out > d_in）
   - T_warn：警告触发时间阈值（默认 3.0 秒）
   - T_clear：警告清除时间阈值（默认 3.0 秒）
   - grace_time：目标消失宽限期（默认 0.5 秒）
4. THE DecisionLayerConfigDTO SHALL 包含物体区域配置（ObjectZonesConfigDTO）
5. THE ObjectZonesConfigDTO SHALL 包含危险区 y 坐标绝对值阈值（danger_y_threshold，默认 1500.0 mm）
6. THE ObjectZonesConfigDTO SHALL 包含抓取区域配置（GraspZoneConfigDTO）
7. THE GraspZoneConfigDTO SHALL 支持矩形模式（mode="rect"），包含参数：
   - x_min, x_max：定义 x 轴方向的抓取范围
   - y_min, y_max：定义 y 轴方向的绝对值范围
   - z 轴无限制
8. THE GraspZoneConfigDTO SHALL 支持半径模式（mode="radius"），包含参数：
   - r_min, r_max：定义半径范围
9. THE DecisionLayerConfigDTO SHALL 包含标签映射配置（person_label_ids），定义哪些 YOLO 标签值对应人员
10. WHEN 配置参数无效（如负数、d_out <= d_in、最小值大于最大值）THEN THE 配置 DTO SHALL 在验证时返回错误信息
11. THE DecisionLayerConfigDTO SHALL 提供默认的距离阈值、时间阈值、区域配置和标签映射
12. THE DecisionLayerConfigDTO SHALL 在初始化时通过 _validate_data() 验证所有配置参数的有效性

**配置结构**：

```python
# 配置层次结构
DataProcessingConfigDTO
├── coordinate_transforms: Dict[DeviceRole, CoordinateTransformConfigDTO]
├── filter_config: FilterConfigDTO
└── decision_layer_config: DecisionLayerConfigDTO
    ├── person_label_ids: List[int]
    ├── person_warning: PersonWarningConfigDTO
    │   ├── d_in: float
    │   ├── d_out: float
    │   ├── T_warn: float
    │   ├── T_clear: float
    │   └── grace_time: float
    ├── object_zones: ObjectZonesConfigDTO
    │   ├── danger_y_threshold: float
    │   └── grasp_zone: GraspZoneConfigDTO
    │       ├── mode: str ("rect" | "radius")
    │       ├── x_min, x_max, y_min, y_max: float (矩形模式)
    │       └── r_min, r_max: Optional[float] (半径模式)
    └── state_expiration_time: float
```

**配置文件位置**：

决策层配置存储在 `config/data_processing.yaml` 中，与坐标变换、滤波配置统一管理。

---

#### 需求 13：待抓取目标坐标同步访问接口

**用户故事**：作为 CAN 通信模块开发者，我希望能够以零延迟的方式同步获取待抓取目标坐标，以满足实时通信要求。

**验收标准**：

1. THE Decision_Layer SHALL 提供线程安全的同步方法 `get_target_coords_snapshot()` 供外部模块调用
2. THE `get_target_coords_snapshot()` SHALL 使用线程锁（RLock）保护全局目标对象的访问
3. WHEN 方法被调用且存在全局 Target_Object THEN THE 方法 SHALL 返回目标坐标的副本（numpy array copy）
4. WHEN 方法被调用且不存在 Target_Object THEN THE 方法 SHALL 返回 None
5. THE 方法 SHALL 在 < 0.1ms 内完成（锁获取 + 内存复制）
6. THE 返回的坐标副本 SHALL 不影响内部状态（外部修改不影响决策层）
7. THE Decision_Layer SHALL 确保所有对全局 Target_Object 的更新操作都使用相同的线程锁保护
8. THE Decision_Layer SHALL 提供内部方法 `_update_global_target()` 用于线程安全地更新全局目标

**线程安全保证**：

- 所有读取全局 Target_Object 的操作必须在锁保护下进行
- 所有更新全局 Target_Object 的操作（在 `_process_object()` 中）必须在锁保护下进行
- 使用 `RLock`（可重入锁）避免死锁

**接口设计**：

```python
# CAN 通信模块使用示例
decision_layer = DecisionLayer.get_instance()
target_coords = decision_layer.get_target_coords_snapshot()

if target_coords is not None:
    # 发送坐标到 CAN 总线
    can_module.send_coords(target_coords)
```

**性能要求**：

- 响应时间：< 0.1ms（典型场景）
- 锁竞争：可忽略（写入 90 次/秒，读取 10-50 次/秒）
- CPU 占用：< 0.5%

---

#### 需求 14：全局单例模式

**用户故事**：作为系统架构师，我希望决策层在系统中全局唯一，以确保状态一致性和资源管理。

**验收标准**：

1. THE Decision_Layer SHALL 实现单例模式，确保全局只有一个实例
2. THE Decision_Layer SHALL 使用线程安全的单例实现（双重检查锁定）
3. THE Decision_Layer SHALL 提供 `get_instance()` 类方法获取单例实例
4. WHEN 多次调用构造函数或 `get_instance()` THEN THE 方法 SHALL 返回同一个实例
5. THE Decision_Layer SHALL 在首次实例化时初始化所有内部状态
6. THE Decision_Layer SHALL 防止通过 `__init__` 重复初始化已存在的实例
7. WHEN `get_instance()` 被调用但实例尚未创建 THEN THE 方法 SHALL 抛出 RuntimeError

**实现要求**：

```python
class DecisionLayer:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """确保全局唯一实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, ...):
        """防止重复初始化"""
        if hasattr(self, '_initialized'):
            return
        
        # 初始化内部状态
        self._target_lock = threading.RLock()
        self._global_target_object = None
        # ... 其他初始化
        
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'DecisionLayer':
        """获取决策层单例实例"""
        if cls._instance is None:
            raise RuntimeError("DecisionLayer 尚未初始化")
        return cls._instance
```

---

### 需求组 E：性能与错误处理

#### 需求 15：高效计算性能

**用户故事**：作为系统架构师，我希望决策层能够高效处理单设备数据，以便满足实时处理要求并不影响整体系统性能。

**验收标准**：

1. WHEN 处理单设备数据 THEN THE decide() SHALL 在 5ms 内完成处理（典型场景：10-20 个检测对象）
2. WHEN 处理大量检测对象（50+ 个）THEN THE decide() SHALL 在 20ms 内完成处理
3. THE _process_person() 和 _process_object() SHALL 使用 NumPy 向量化操作批量计算所有对象的距离
4. THE _process_person() 和 _process_object() SHALL 使用 NumPy 布尔索引批量筛选不同状态的对象
5. THE Decision_Layer SHALL 避免 Python 循环进行距离计算，优先使用向量化操作
6. THE Decision_Layer SHALL 避免不必要的内存分配和数组复制操作
7. THE decide() SHALL 预分配状态数组以避免动态扩展
8. THE decide() SHALL 在分流处理时使用 NumPy 布尔索引而非 Python 循环
9. THE Decision_Layer SHALL 避免在热路径中进行字符串操作或日志记录
10. THE Decision_Layer SHALL 重用已分配的数组空间，减少垃圾回收压力


---

#### 需求 16：错误处理

**用户故事**：作为系统维护员，我希望决策层能够在保证性能的前提下处理异常情况，采用 fail-fast 策略确保数据质量。

**验收标准**：

1. WHEN 输入数据格式错误（坐标数组形状不正确或标签数组长度不一致）THEN THE decide() SHALL 在方法入口处验证并抛出异常
2. THE decide() SHALL 在方法入口处进行一次性验证：
   - 坐标数组形状为 (N, 3)
   - 标签数组长度与坐标数组第一维度一致
3. THE _process_person() 和 _process_object() SHALL 假设输入数据已经过滤波处理且有效，不进行额外的数据有效性检查
4. THE Decision_Layer SHALL 在热路径（向量化计算）中不使用 try-except 或数据验证（如 `np.isfinite()`），以最大化计算性能
5. THE Decision_Layer SHALL 采用 fail-fast 策略，如果数据异常（NaN、Inf 等）则让异常自然抛出，由上层模块处理
6. THE Decision_Layer SHALL 信任滤波模块的输出质量，默认数据是正确的
7. WHEN 发生未预期的异常时 THEN THE 异常 SHALL 向上传播，由 DataProcessor 或更上层模块捕获和处理

---

#### 需求 17：状态标签输出一致性

**用户故事**：作为下游模块开发者，我希望决策层输出的状态标签列表与输入检测对象一一对应，以便正确渲染和处理。

**验收标准**：

1. WHEN decide() 输出状态标签列表 THEN THE 方法 SHALL 确保列表长度与输入检测对象数量一致
2. WHEN decide() 输出状态标签列表 THEN THE 方法 SHALL 确保第 i 个状态标签对应第 i 个检测对象
3. WHEN 输入为空（零个检测对象）THEN THE decide() SHALL 输出空的状态标签列表
4. THE decide() SHALL 使用 DetectionStatusLabel 枚举类型作为状态标签
5. THE decide() SHALL 保持分流前后的对象顺序一致（通过掩码索引实现）
6. THE decide() SHALL 验证输出列表长度与输入长度匹配，不匹配时抛出异常
7. THE decide() SHALL 确保所有状态标签都是有效的 DetectionStatusLabel 枚举值

---

## 需求总结

本需求文档定义了决策层模块的完整功能规范，包括：

**核心架构**（需求组 A）：
- 主方法 `decide()` 协调整个处理流程
- 基于 `labels_map` 的数据分流机制
- 向量化整数数组状态计算

**人员处理**（需求组 B）：
- 距离计算与危险判断
- 状态机管理（SAFE/PENDING/ALARM）
- 警告事件发布

**物体处理**（需求组 C）：
- 抓取区域判断（危险区/抓取区/超出范围）
- 设备级别最近可抓取物体维护
- 全局待抓取目标选择（线程安全）

**状态管理**（需求组 D）：
- 设备状态维护与过期检查
- 灵活的配置参数系统
- 线程安全的同步访问接口（供 CAN 通信模块使用）
- 全局单例模式

**质量保证**（需求组 E）：
- 高性能向量化计算（5-20ms 处理时间）
- 完善的错误处理机制
- 输出一致性保证

**关键设计决策**：
1. **全局单例**：确保系统中只有一个决策层实例，保证状态一致性
2. **线程安全**：使用 RLock 保护全局目标对象，支持多线程访问
3. **零延迟接口**：提供同步方法 `get_target_coords_snapshot()` 供 CAN 通信模块使用（< 0.1ms）
4. **事件驱动**：人员警告通过事件总线发布，解耦模块间依赖
5. **向量化计算**：使用 NumPy 整数数组进行状态计算，最后转换为枚举列表

该设计确保了决策层的高性能、可维护性、线程安全性和实时响应能力。
