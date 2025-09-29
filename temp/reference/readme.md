- 实现了1080p无损视野输出
- 实现了线性回归修正逻辑
- 固定了一个参数版本，加入了一个回归修正逻辑，精度预计可达30mm

- 双OAK实现，开启三个线程，两个检测线程，并在主程序处理数据，最后发给can模块进行通信。

# OAK 设备配置管理模块（dual1.0）开发说明

## 配置 JSON 草案（精简，仅设备坐标变换 + 全局滤波）
{
  "config_version": "1.0.0",
  "updated_at": "2025-08-26T10:00:00Z",
  "filter": { "type": "moving_average", "window": 5 },
  "devices": [
    {
      "mxid": "MXID_LEFT_ABCDEFG",
      "alias": "left_oak",
      "kinematics": { "Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Rx": 0.0, "Ry": 22.9, "Rz": -25.2 }
    },
    {
      "mxid": "MXID_RIGHT_HIJKLMN",
      "alias": "right_oak",
      "kinematics": { "Tx": -1600.0, "Ty": -800.0, "Tz": 1250.0, "Rx": 0.0, "Ry": 25.0, "Rz": -30.0 }
    }
  ]
}

说明：
- 仅保留与设备相关的外参（Tx/Ty/Tz: mm；Rx/Ry/Rz: 度），移除修正逻辑。
- `filter` 为全局配置（如需每设备不同，可扩展为放入各自 `devices[i].filter`）。

## 待实现功能（TODO）
1. 设备识别与别名绑定
   - 列出已连接设备（获取 MXid）
   - 将 MXid 与 `alias` 双向绑定；提供冲突检测（重复别名/重复 MXid）
2. 配置保存
   - 将内存中的配置以 JSON 保存至磁盘
   - 原子化写入（临时文件 + 覆盖），保存时间戳 `updated_at`
3. 配置加载
   - 从 JSON 加载，校验结构与字段类型，自动补齐默认值
   - 版本号 `config_version` 识别（为后续迁移预留）
4. 配置读取接口
   - 按 alias/MXid 获取设备配置
   - 读取设备外参（kinematics）与全局滤波参数（filter）
5. 配置修改接口
   - 可更新设备外参（Tx/Ty/Tz/Rx/Ry/Rz）
   - 可更新全局滤波参数（type/window）
   - 提供校验并支持内存更新后重新保存

## 接口规划（简版）
- 设备发现：
  - list_connected() -> List[{mxid, name?, state?}]
- 绑定管理：
  - bind_alias(mxid: str, alias: str) -> None
  - get_mxid(alias: str) -> str | None
  - get_alias(mxid: str) -> str | None
- 配置生命周期：
  - load(path: str) -> Config
  - save(path: str, atomic: bool = True) -> None
- 读取：
  - get_device(alias_or_mxid: str) -> DeviceConfig | None
  - get_kinematics(alias_or_mxid: str) -> dict
  - get_filter() -> dict
- 修改：
  - set_kinematics(alias_or_mxid: str, **fields) -> None
  - set_filter(type: str = None, window: int = None) -> None
  - validate() -> bool / raise

## 校验要求
- MXid：非空字符串，格式长度合规（≥10）
- alias：非空且全局唯一
- kinematics：Tx/Ty/Tz 为 float（mm），Rx/Ry/Rz 为 float（deg）
- filter：
  - type ∈ {"moving_average","median"}（可扩展）
  - window 为正整数且范围合理（建议 1~101）

## 文件约定
- 默认路径：configs/dual_oak.json（可自定义）
- 保存时落盘目录自动创建；失败时不破坏旧文件

## 后续可选扩展（非本阶段）
- 多 profile 支持（dev/test/prod）
- 每设备独立滤波配置
- 运行时热更新/订阅通知
- 设备健康检查与绑定状态报告


# 进度报告

## 8-27
- 当前已完成oak配置模块的设计，支持加载、修改、保存、映射绑定的功能，可以为不同设备绑定不同的参数。

- 下一步是根据detection_corrected.py脚本，构建一个OAK检测流的模块，或者直接构建一个配合oak配置模块使用mxid启动的脚本，同时启动两个相机的检测流，然后拿到两个相机的数据，依次使用并等待can线程使用。
- 或者是同上，但是是依次启动OAK设备，具体而言：通过mxid先启动设备1的检测流，然后等待检测数据，如果有durian（后续可换成任意待抓取物体）的数据，就等待can通信模块的使用；如果没有数据，就通过mxid启动另一侧的OAK设备2，同样的检查方法，有数据则等待can模块来使用数据。

- 当前还缺少通过mxid启动设备的API，下面是补充：
"""
import depthai

pipeline = depthai.Pipeline()
# ... 配置你的pipeline ...

mxid = "你的目标设备MXID"
device_info = depthai.DeviceInfo(mxid)
with depthai.Device(pipeline, device_info) as device:
    # 这里可以与指定设备进行交互
    print('已连接设备MXID:', device.getDeviceInfo().getMxId())

"""


"""
import depthai as dai

mxid = "你的设备MXID"  # 替换为你想连接的设备MXID
device_info = dai.DeviceInfo(mxid)
with dai.Device(device_info) as device:
    # 在这里创建并启动你的 pipeline
    pipeline = dai.Pipeline()
    # ... pipeline 配置 ...
    device.startPipeline(pipeline)
    # ... 后续处理 ...
"""
"""
import depthai as dai

mxid = "1944301091C41B1300"
pipeline = dai.Pipeline()
# ... 配置pipeline ...

# 直接通过MXid连接
with dai.Device(pipeline, mxid) as device:
    print(f'已连接设备: {device.getDeviceInfo().getMxId()}')
    # 处理数据流...
"""

------------------------------------