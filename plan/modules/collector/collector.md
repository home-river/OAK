# OAK 数据采集模块（Collector）功能与架构说明

## 模块目标
- **统一采集**：基于 DepthAI 管线统一采集 RGB 预览帧、空间检测结果，按需输出深度帧。
- **事件分发**：将原始视频帧与检测数据以事件形式发布到系统总线，供后续处理链消费。
- **多设备角色**：按设备“角色”并行驱动多个 OAK 设备，独立管理运行状态与线程。

## 架构总览
- **核心类**：
  - `OAKDataCollector`：采集编排与事件发布。
  - `PipelineManager`：DepthAI `Pipeline` 的创建与配置。
- **主要数据模型（DTO）**：
  - `VideoFrameDTO`：包含 `device_id`、`frame_id`、`rgb_frame`（OpenCV 图像）、可选 `depth_frame`（毫米单位）。
  - `DeviceDetectionDataDTO`：包含 `device_id`、`frame_id`、`device_alias`、`detections`（`DetectionDTO` 列表，含 `BoundingBoxDTO` 与 `SpatialCoordinatesDTO`）。
- **事件通道**：
  - `EventType.RAW_FRAME_DATA`：发布 `VideoFrameDTO`。
  - `EventType.RAW_DETECTION_DATA`：发布 `DeviceDetectionDataDTO`。

## 关键类与职责
- **OAKDataCollector**（采集编排）
  - 接收 `OAKModuleConfigDTO`（已绑定设备角色），内部持有 `PipelineManager` 与 `EventBus`。
  - 基于 `role_bindings` 初始化设备运行态与帧号计数器（按 `role.value` 维度）。
  - 按设备角色开启工作线程，创建 DepthAI 设备，获取输出队列并进行采集循环。
  - 将 `dai.ImgFrame`、`dai.SpatialImgDetections` 组装为相应 DTO 后发布事件。
  - 提供 `start()` 返回结构化结果（已启动角色、跳过原因），`stop()` 停止并回收线程。

- **PipelineManager**（管线管理）
  - 根据 `OAKConfigDTO` 与 `enable_depth_output` 创建两类管线：
    - 启用深度输出：输出流包含 `rgb`、`detections`、`depth`。
    - 关闭深度输出：输出流仅 `rgb`、`detections`（仍保留深度用于空间检测，但不单独输出深度帧）。
  - 负责节点创建与连接：`ColorCamera`、`YoloSpatialDetectionNetwork`、`MonoCamera`(L/R)、`StereoDepth`、`XLinkOut`（按需）。
  - 将配置转换为 DepthAI 枚举（RGB/Mono 分辨率、中值滤波核大小等），并在不支持时回退默认值并记录告警。

## 配置与依赖
- `OAKModuleConfigDTO`
  - `hardware_config`：被 `PipelineManager` 使用（如 `enable_depth_output`、`rgb_resolution`、`depth_resolution`、`median_filter`、`subpixel`、`left_right_check`、`extended_disparity`、`model_path`、`confidence_threshold`、深度阈值、`queue_max_size`、`queue_blocking`、`usb2_mode`、`preview_resolution` 等）。
  - `role_bindings`：`DeviceRoleBindingDTO` 映射，含 `role` 与 `active_mxid`。
- 事件总线：通过 `EventBus.get_instance()` 获取，发布原始帧与检测事件。

## 运行流程（时序）
1. 初始化阶段
   - `OAKDataCollector` 构造：创建 `PipelineManager`，建立运行状态字典与帧号计数器。
   - `PipelineManager` 在初始化内解析 `enable_depth_output` 并立即创建管线。
2. 启动阶段
   - `start()` 遍历 `role_bindings`：
     - 无 `active_mxid` 的角色被标记为跳过（原因 `no_active_mxid`）。
     - 其余角色各自启动一个守护线程执行设备采集。
3. 采集循环
   - 为每个设备创建 `rgb`、`detections` 队列，按配置决定是否创建 `depth` 队列。
   - 采用非阻塞 `tryGet()` 拉取：若暂时无数据，短暂休眠（10ms）避免空转。
   - 对获取到的帧：
     - 组装 `VideoFrameDTO` 并发布。
     - 组装 `DeviceDetectionDataDTO` 并发布。
   - 帧号来源优先使用 DepthAI 序列号（可用则取 `getSequenceNum()`），否则回退到计数器。
4. 停止阶段
   - `stop()` 将所有角色运行标记置为 `False`，并 `join()` 工作线程。

## DepthAI 管线要点
- 相机与网络
  - RGB 预览输出接入 `YoloSpatialDetectionNetwork`，同时通过 `passthrough` 输出 `rgb` 流。
  - `StereoDepth` 输出接入 `YoloSpatialDetectionNetwork.inputDepth`，提供空间坐标。
  - 启用深度输出时，通过 `passthroughDepth` 输出 `depth` 流。
- 网络与阈值
  - 支持设置置信度阈值、IoU 阈值、检测类别数、深度上下阈值、边界框缩放因子等。

## 数据与事件
- 视频帧事件（`RAW_FRAME_DATA`）
  - `device_id`：来自绑定的设备 MXID。
  - `frame_id`：DepthAI 序列号优先；不可用时使用内部计数。
  - `rgb_frame`：OpenCV BGR 图像。
  - `depth_frame`：可选，`uint16` 毫米单位（启用深度输出且获取成功时）。
- 检测数据事件（`RAW_DETECTION_DATA`）
  - `device_alias`：设备角色的 `value`。
  - `detections`：包含边界框与空间坐标（毫米）。若单个检测转换失败，不影响其他检测。

## 线程模型与并发控制
- 每个设备角色对应一个工作线程，线程名形如 `OAKWorker-<role>`。
- 通过内部锁保护的运行状态字典，支持线程安全的启动/停止判断。
- 非阻塞队列 + 短暂休眠的循环方式，避免在停止时阻塞在阻塞式获取上。

## 错误处理与日志
- 管线创建与设备启动失败会记录异常并抛出 `RuntimeError`（含阶段/角色信息）。
- 帧与检测数据组装失败会记录详细告警/异常，并安全跳过返回 `None`。
- 对异常配置值进行回退并记录警告，保证运行健壮性。

## 可扩展点
- 模型/阈值：通过 `OAKConfigDTO` 的 `model_path`、阈值参数进行替换与调优。
- 输出策略：可在事件消费端增加缓存、对齐与持久化策略。
- 采集策略：可扩展为按需切换 `enable_depth_output`、调整 `queue_max_size`、`queue_blocking` 等以平衡时延与稳定性。
- 多设备：在 `role_bindings` 中增加角色即可横向扩展。

## 已知约束与注意事项
- 未绑定 `active_mxid` 的角色不会启动采集（会在 `start()` 的返回结果中标明）。
- 启用深度输出时，若深度帧获取失败，当前帧的视频 DTO 会被丢弃以确保数据一致性。
- `create_pipeline_with_no_depth_output` 仍使用深度参与空间检测，但不对外输出独立的 `depth` 流。
- `frame_id` 的一致性依赖 DepthAI 序列号；个别设备/队列不可用时将回退到内部计数。

## 与系统的边界
- 上游：配置管理器提供已绑定好的 `OAKModuleConfigDTO`（含 `role_bindings`）。
- 下游：事件总线的订阅方（可视化、记录、融合、抓取策略等）消费原始帧与检测事件。

## 典型使用方式（描述性）
- 准备 `OAKModuleConfigDTO`（含设备角色与 MXID 绑定、硬件/模型配置）。
- 构造 `OAKDataCollector`，调用 `start()` 获取启动/跳过结果。
- 订阅事件总线中的 `RAW_FRAME_DATA` 与 `RAW_DETECTION_DATA` 进行处理。
- 结束时调用 `stop()` 停止所有采集线程。

