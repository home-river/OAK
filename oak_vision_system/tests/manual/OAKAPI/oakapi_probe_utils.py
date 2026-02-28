"""OAKAPI 调用探针工具集（面向手工/探索性测试）。

目标：将可能影响 OAK 设备枚举稳定性/耗时的关键 DepthAI API 调用拆成可组合的 probe。

设计要点：
- 每个 `probe_*` 函数都支持内部连续调用（`continuous=True` + `n_calls`）
- 支持内部两次调用之间的间隔（`internal_gap_sec`）
- 每次调用结果追加写入日志文件（`log_path`），便于离线分析“哪一步开始引入副作用/卡顿”

典型用法：在一个 main 脚本中按你想要的排列组合调用这些 probe（可在外部自行 sleep 控制间隔）。

"""

from __future__ import annotations

import gc
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import depthai as dai


@dataclass
class ProbeResult:
    """单次 probe 调用的记录结构（用于写入日志文件）。"""

    ts: float
    name: str
    ok: bool
    duration_sec: float
    params: Dict[str, Any]
    result: Dict[str, Any]
    error: Optional[str]


def _append_jsonl(path: Path, obj: object) -> None:
    """将对象追加写入到 `path`。

    约定：
    - 当后缀为 `.jsonl` 时，使用 JSON Lines（单行）格式写入
    - 否则使用 pretty JSON（多行缩进）并用分隔线隔开，便于肉眼观察
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        if path.suffix.lower() == ".jsonl":
            fp.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        else:
            fp.write(json.dumps(obj, ensure_ascii=False, default=str, indent=2) + "\n")
            fp.write("-" * 80 + "\n")
        fp.flush()


def _mxids_from_infos(infos: Sequence[object]) -> List[str]:
    """从 depthai 的 DeviceInfo 列表中提取 mxid 字符串列表（去重、排序）。"""

    mxids: List[str] = []
    for info in infos:
        get_mxid = getattr(info, "getMxId", None)
        if callable(get_mxid):
            try:
                mxids.append(str(get_mxid()))
                continue
            except Exception:
                continue
        mxid_attr = getattr(info, "mxid", None)
        if mxid_attr is not None:
            mxids.append(str(mxid_attr))
    return sorted(set(mxids))


def _run_probe(
    *,
    name: str,
    log_path: Path,
    params: Dict[str, Any],
    fn: Callable[[], Dict[str, Any]],
) -> ProbeResult:
    """统一封装 probe 的计时、异常捕获与日志记录。

    Args:
        name: probe 名称（写入日志）。
        log_path: 日志追加写入路径。
        params: 本次调用参数（原样写入日志，便于复现）。
        fn: 实际执行函数，返回一个 dict 作为 result 字段。

    Returns:
        ProbeResult: 单次调用记录。
    """

    t0 = time.perf_counter()
    ok = True
    err: Optional[str] = None
    result: Dict[str, Any] = {}
    try:
        result = fn() or {}
    except Exception as e:
        ok = False
        err = f"{type(e).__name__}: {e}"
    dt = time.perf_counter() - t0

    rec = ProbeResult(
        ts=time.time(),
        name=name,
        ok=ok,
        duration_sec=float(dt),
        params=params,
        result=result,
        error=err,
    )
    _append_jsonl(log_path, asdict(rec))
    return rec


def probe_get_all_available_devices(
    *,
    log_path: Path,
    internal_gap_sec: float = 0.0,
    continuous: bool = True,
    n_calls: int = 2,
    use_bootloader: bool = False,
) -> List[ProbeResult]:
    """测试行为：仅调用“源头枚举 API”是否会导致设备列表抖动。

    对应 API：
    - `dai.Device.getAllAvailableDevices()`
    - （可选）`dai.DeviceBootloader.getAllAvailableDevices()`

    关注点：
    - 连续调用时 mxid 列表是否稳定（是否出现 missing/extra）
    - 单次调用耗时是否异常

    Args:
        log_path: 日志追加写入路径（支持 `.jsonl` 单行与 `.log` 多行 pretty JSON）。
        internal_gap_sec: 内部连续调用之间的 sleep 间隔。
        continuous: True 表示内部循环调用 n_calls 次；False 表示只调用一次。
        n_calls: 连续调用次数（仅 continuous=True 时生效）。
        use_bootloader: True 表示调用 `dai.DeviceBootloader.getAllAvailableDevices()`。

    Returns:
        List[ProbeResult]: 每次调用一条记录。
    """

    results: List[ProbeResult] = []

    calls = n_calls if continuous else 1
    for i in range(calls):
        params = {
            "call_index": i,
            "internal_gap_sec": float(internal_gap_sec),
            "continuous": bool(continuous),
            "n_calls": int(n_calls),
            "use_bootloader": bool(use_bootloader),
        }

        def _fn() -> Dict[str, Any]:
            infos = (
                dai.DeviceBootloader.getAllAvailableDevices()
                if use_bootloader
                else dai.Device.getAllAvailableDevices()
            )
            mxids = _mxids_from_infos(infos)
            return {"mxids": mxids, "count": len(mxids)}

        results.append(_run_probe(name="getAllAvailableDevices", log_path=log_path, params=params, fn=_fn))

        if internal_gap_sec > 0 and i != calls - 1:
            time.sleep(internal_gap_sec)

    return results


def probe_with_device_structure_only(
    *,
    log_path: Path,
    mxid: str,
    internal_gap_sec: float = 0.0,
    continuous: bool = True,
    n_calls: int = 2,
    usb2_mode: bool = True,
) -> List[ProbeResult]:
    """测试行为：仅测试 `with dai.Device(...):` 结构（进入/退出上下文）的影响。

    对应 API：
    - `with dai.Device(dai.Pipeline(), DeviceInfo(mxid), usb2Mode=...) as device:`

    关注点：
    - 不做 `getMxId/readCalibration/getEepromData` 等操作时，单纯 open/close 是否仍会引起耗时/异常
    - 连续执行 open/close 是否会影响后续枚举稳定性

    Args:
        log_path: 日志追加写入路径（支持 `.jsonl` 单行与 `.log` 多行 pretty JSON）。
        mxid: 目标设备 mxid。
        internal_gap_sec: 内部连续调用之间的 sleep 间隔。
        continuous: True 表示内部循环调用 n_calls 次；False 表示只调用一次。
        n_calls: 连续调用次数（仅 continuous=True 时生效）。
        usb2_mode: 传递给 DepthAI 的 usb2Mode 参数。

    Returns:
        List[ProbeResult]: 每次调用一条记录。
    """

    results: List[ProbeResult] = []

    calls = n_calls if continuous else 1
    for i in range(calls):
        params = {
            "call_index": i,
            "mxid": str(mxid),
            "internal_gap_sec": float(internal_gap_sec),
            "continuous": bool(continuous),
            "n_calls": int(n_calls),
            "usb2_mode": bool(usb2_mode),
        }

        def _fn() -> Dict[str, Any]:
            info = dai.DeviceInfo(str(mxid))
            with dai.Device(dai.Pipeline(), info, usb2Mode=usb2_mode) as device:
                _ = id(device)
                return {"entered": True}

        results.append(_run_probe(name="with Device structure only", log_path=log_path, params=params, fn=_fn))

        if internal_gap_sec > 0 and i != calls - 1:
            time.sleep(internal_gap_sec)

    return results


def probe_device_info_from_mxid(
    *,
    log_path: Path,
    mxid: str,
    internal_gap_sec: float = 0.0,
    continuous: bool = True,
    n_calls: int = 2,
) -> List[ProbeResult]:
    """测试行为：构造 `DeviceInfo` 是否存在副作用/异常或显著耗时。

    对应 API：
    - `dai.DeviceInfo(mxid)`

    关注点：
    - 仅构造对象是否会触发底层访问（理论上不应）
    - 连续构造是否会引入异常/耗时飙升

    Args:
        log_path: 日志追加写入路径（支持 `.jsonl` 单行与 `.log` 多行 pretty JSON）。
        mxid: 目标设备 mxid。
        internal_gap_sec: 内部连续调用之间的 sleep 间隔。
        continuous: True 表示内部循环调用 n_calls 次；False 表示只调用一次。
        n_calls: 连续调用次数（仅 continuous=True 时生效）。

    Returns:
        List[ProbeResult]: 每次调用一条记录。
    """

    results: List[ProbeResult] = []

    calls = n_calls if continuous else 1
    for i in range(calls):
        params = {
            "call_index": i,
            "mxid": str(mxid),
            "internal_gap_sec": float(internal_gap_sec),
            "continuous": bool(continuous),
            "n_calls": int(n_calls),
        }

        def _fn() -> Dict[str, Any]:
            info = dai.DeviceInfo(str(mxid))
            get_mxid = getattr(info, "getMxId", None)
            mx_out = None
            if callable(get_mxid):
                try:
                    mx_out = str(get_mxid())
                except Exception:
                    mx_out = None
            return {"mxid": mx_out}

        results.append(_run_probe(name="DeviceInfo(mxid)", log_path=log_path, params=params, fn=_fn))

        if internal_gap_sec > 0 and i != calls - 1:
            time.sleep(internal_gap_sec)

    return results


def probe_open_device(
    *,
    log_path: Path,
    mxid: str,
    internal_gap_sec: float = 0.0,
    continuous: bool = True,
    n_calls: int = 2,
    usb2_mode: bool = True,
) -> List[ProbeResult]:
    """测试行为：仅“打开设备/关闭设备”是否会引入副作用（不读标定/EEPROM）。

    对应 API：
    - `with dai.Device(dai.Pipeline(), DeviceInfo(mxid), usb2Mode=...) as device:`

    关注点：
    - 单纯建立连接是否就会导致后续枚举不稳定/设备状态变化
    - 连续 open/close 是否会造成耗时飙升或偶发失败

    Args:
        log_path: 日志追加写入路径（支持 `.jsonl` 单行与 `.log` 多行 pretty JSON）。
        mxid: 目标设备 mxid。
        internal_gap_sec: 内部连续调用之间的 sleep 间隔。
        continuous: True 表示内部循环调用 n_calls 次；False 表示只调用一次。
        n_calls: 连续调用次数（仅 continuous=True 时生效）。
        usb2_mode: 传递给 DepthAI 的 usb2Mode 参数。

    Returns:
        List[ProbeResult]: 每次调用一条记录。
    """

    results: List[ProbeResult] = []

    calls = n_calls if continuous else 1
    for i in range(calls):
        params = {
            "call_index": i,
            "mxid": str(mxid),
            "internal_gap_sec": float(internal_gap_sec),
            "continuous": bool(continuous),
            "n_calls": int(n_calls),
            "usb2_mode": bool(usb2_mode),
        }

        def _fn() -> Dict[str, Any]:
            info = dai.DeviceInfo(str(mxid))
            with dai.Device(dai.Pipeline(), info, usb2Mode=usb2_mode) as device:
                _ = device.getMxId()
                return {"opened": True}

        results.append(_run_probe(name="with Device(...)", log_path=log_path, params=params, fn=_fn))

        if internal_gap_sec > 0 and i != calls - 1:
            time.sleep(internal_gap_sec)

    return results


def probe_read_calibration(
    *,
    log_path: Path,
    mxid: str,
    internal_gap_sec: float = 0.0,
    continuous: bool = True,
    n_calls: int = 2,
    usb2_mode: bool = True,
) -> List[ProbeResult]:
    """测试行为：`device.readCalibration()` 是否是卡顿点/副作用源头。

    对应 API：
    - `device.readCalibration()`

    关注点：
    - 调用耗时是否明显高于“仅 open device”
    - 是否出现阻塞/卡死（你之前的 KeyboardInterrupt 堆栈指向此处）
    - 连续调用是否会导致后续枚举结果出现 missing/extra

    Args:
        log_path: 日志追加写入路径（支持 `.jsonl` 单行与 `.log` 多行 pretty JSON）。
        mxid: 目标设备 mxid。
        internal_gap_sec: 内部连续调用之间的 sleep 间隔。
        continuous: True 表示内部循环调用 n_calls 次；False 表示只调用一次。
        n_calls: 连续调用次数（仅 continuous=True 时生效）。
        usb2_mode: 传递给 DepthAI 的 usb2Mode 参数。

    Returns:
        List[ProbeResult]: 每次调用一条记录。
    """

    results: List[ProbeResult] = []

    calls = n_calls if continuous else 1
    for i in range(calls):
        params = {
            "call_index": i,
            "mxid": str(mxid),
            "internal_gap_sec": float(internal_gap_sec),
            "continuous": bool(continuous),
            "n_calls": int(n_calls),
            "usb2_mode": bool(usb2_mode),
        }

        def _fn() -> Dict[str, Any]:
            info = dai.DeviceInfo(str(mxid))
            with dai.Device(dai.Pipeline(), info, usb2Mode=usb2_mode) as device:
                calib = device.readCalibration()
                return {"calib_type": type(calib).__name__}

        results.append(_run_probe(name="readCalibration", log_path=log_path, params=params, fn=_fn))

        if internal_gap_sec > 0 and i != calls - 1:
            time.sleep(internal_gap_sec)

    return results


def probe_get_eeprom_data(
    *,
    log_path: Path,
    mxid: str,
    internal_gap_sec: float = 0.0,
    continuous: bool = True,
    n_calls: int = 2,
    usb2_mode: bool = True,
) -> List[ProbeResult]:
    """测试行为：`calib.getEepromData()` 是否带来额外耗时/异常/副作用。

    执行路径：
    - `with dai.Device(...) as device`
    - `calib = device.readCalibration()`
    - `eeprom = calib.getEepromData()`

    关注点：
    - 相比仅 `readCalibration()` 是否出现额外耗时
    - `getEepromData()` 是否偶发异常
    - 连续调用是否会进一步恶化后续枚举稳定性

    Args:
        log_path: 日志追加写入路径（支持 `.jsonl` 单行与 `.log` 多行 pretty JSON）。
        mxid: 目标设备 mxid。
        internal_gap_sec: 内部连续调用之间的 sleep 间隔。
        continuous: True 表示内部循环调用 n_calls 次；False 表示只调用一次。
        n_calls: 连续调用次数（仅 continuous=True 时生效）。
        usb2_mode: 传递给 DepthAI 的 usb2Mode 参数。

    Returns:
        List[ProbeResult]: 每次调用一条记录。
    """

    results: List[ProbeResult] = []

    calls = n_calls if continuous else 1
    for i in range(calls):
        params = {
            "call_index": i,
            "mxid": str(mxid),
            "internal_gap_sec": float(internal_gap_sec),
            "continuous": bool(continuous),
            "n_calls": int(n_calls),
            "usb2_mode": bool(usb2_mode),
        }

        def _fn() -> Dict[str, Any]:
            info = dai.DeviceInfo(str(mxid))
            with dai.Device(dai.Pipeline(), info, usb2Mode=usb2_mode) as device:
                calib = device.readCalibration()
                eeprom = calib.getEepromData()
                product = getattr(eeprom, "productName", None)
                return {"product_name": product}

        results.append(_run_probe(name="readCalibration+getEepromData", log_path=log_path, params=params, fn=_fn))

        if internal_gap_sec > 0 and i != calls - 1:
            time.sleep(internal_gap_sec)

    return results


def probe_get_eeprom_datav2(
    *,
    log_path: Path,
    mxid: str,
    internal_gap_sec: float = 0.0,
    continuous: bool = True,
    n_calls: int = 2,
    usb2_mode: bool = True,
) -> List[ProbeResult]:
    """测试行为：`calib.getEepromData()` 是否带来额外耗时/异常/副作用。

    执行路径：
    - `with dai.Device(...) as device`
    - `calib = device.readCalibration()`
    - `eeprom = calib.getEepromData()`

    关注点：
    - 相比仅 `readCalibration()` 是否出现额外耗时
    - `getEepromData()` 是否偶发异常
    - 连续调用是否会进一步恶化后续枚举稳定性

    Args:
        log_path: 日志追加写入路径（支持 `.jsonl` 单行与 `.log` 多行 pretty JSON）。
        mxid: 目标设备 mxid。
        internal_gap_sec: 内部连续调用之间的 sleep 间隔。
        continuous: True 表示内部循环调用 n_calls 次；False 表示只调用一次。
        n_calls: 连续调用次数（仅 continuous=True 时生效）。
        usb2_mode: 传递给 DepthAI 的 usb2Mode 参数。

    Returns:
        List[ProbeResult]: 每次调用一条记录。
    """

    results: List[ProbeResult] = []

    calls = n_calls if continuous else 1
    for i in range(calls):
        params = {
            "call_index": i,
            "mxid": str(mxid),
            "internal_gap_sec": float(internal_gap_sec),
            "continuous": bool(continuous),
            "n_calls": int(n_calls),
            "usb2_mode": bool(usb2_mode),
        }

        def _fn() -> Dict[str, Any]:
            info = dai.DeviceInfo(str(mxid))
            device = dai.Device(info)
            try:
                calib = device.readCalibration()
                eeprom = calib.getEepromData()
                product = getattr(eeprom, "productName", None)
                return {"product_name": product}
            finally:
                try:
                    del eeprom  # type: ignore[name-defined]
                except Exception:
                    pass
                try:
                    del calib  # type: ignore[name-defined]
                except Exception:
                    pass
                try:
                    del device
                except Exception:
                    pass
                gc.collect()

        results.append(_run_probe(name="readCalibration+getEepromData", log_path=log_path, params=params, fn=_fn))

        if internal_gap_sec > 0 and i != calls - 1:
            time.sleep(internal_gap_sec)

    return results