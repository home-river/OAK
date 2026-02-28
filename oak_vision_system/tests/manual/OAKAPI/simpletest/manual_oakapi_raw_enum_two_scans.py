"""最小化：直接调用 DepthAI 源头枚举 API，仅提取 MXID，连续两次快速扫描对比差异。

运行：
    python oak_vision_system/tests/manual/OAKAPI/manual_oakapi_raw_enum_two_scans.py
"""

from __future__ import annotations

import time
from typing import Iterable, List, Optional, Sequence, Set, Tuple

import depthai as dai


def _mxid_from_device_info(info: object) -> Optional[str]:
    get_mxid = getattr(info, "getMxId", None)
    if callable(get_mxid):
        try:
            return str(get_mxid())
        except Exception:
            return None

    mxid_attr = getattr(info, "mxid", None)
    if mxid_attr is not None:
        return str(mxid_attr)

    return None


def _mxids_from_infos(infos: Iterable[object]) -> List[str]:
    mxids: List[str] = []
    for info in infos:
        mx = _mxid_from_device_info(info)
        if mx:
            mxids.append(mx)
    return sorted(set(mxids))


def _enum_devices(use_bootloader: bool) -> List[str]:
    if use_bootloader:
        infos = dai.DeviceBootloader.getAllAvailableDevices()
    else:
        infos = dai.Device.getAllAvailableDevices()
    return _mxids_from_infos(infos)


def _compare(a: Sequence[str], b: Sequence[str]) -> Tuple[List[str], List[str]]:
    sa: Set[str] = set(a)
    sb: Set[str] = set(b)
    missing = sorted(sa - sb)
    extra = sorted(sb - sa)
    return missing, extra


def main() -> int:
    use_bootloader = False
    gap_sec = 0.0

    print("=" * 80)
    print("OAKAPI Raw Enum Two Scans")
    print(f"use_bootloader={use_bootloader} gap_sec={gap_sec}")
    print("=" * 80)

    t1 = time.perf_counter()
    mx1 = _enum_devices(use_bootloader=use_bootloader)
    t2 = time.perf_counter()

    if gap_sec > 0:
        time.sleep(gap_sec)

    t3 = time.perf_counter()
    mx2 = _enum_devices(use_bootloader=use_bootloader)
    t4 = time.perf_counter()

    missing, extra = _compare(mx1, mx2)

    print(f"scan1: n={len(mx1)} dt={t2 - t1:.3f}s mxids={mx1}")
    print(f"scan2: n={len(mx2)} dt={t4 - t3:.3f}s mxids={mx2}")
    if missing or extra:
        print(f"MISMATCH missing={missing} extra={extra}")
    else:
        print("MATCH")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
