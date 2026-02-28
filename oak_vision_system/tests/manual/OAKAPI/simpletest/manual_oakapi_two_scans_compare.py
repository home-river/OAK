"""最小化验证脚本：同一进程内连续两次设备发现并对比差异。

目的：
- 复现 binding 工具场景：短时间内连续两次调用同一套发现逻辑
- 对比两次扫描到的 MXID 集合、连接状态（connection_status）、notes 等字段差异
- 将结果保存到 JSON 文件，便于事后分析

运行方式：
    python oak_vision_system/tests/manual/OAKAPI/manual_oakapi_two_scans_compare.py

说明：
- 使用项目内的 OAKDeviceDiscovery（与 binding/config_manager 同源）
- 该脚本只做“发现 + 对比”，不做绑定、不保存配置
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    for p in (current, *current.parents):
        if (p / "pyproject.toml").exists():
            return p
    return start.resolve()


project_root = _find_project_root(Path(__file__).parent)
sys.path.insert(0, str(project_root))


from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery  # noqa: E402


def _to_map(devices) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for d in devices:
        # DeviceMetadataDTO 是 dataclass 风格 DTO，这里用 asdict 更稳；如果失败就退回到 __dict__
        try:
            payload = asdict(d)
        except Exception:
            payload = dict(getattr(d, "__dict__", {}))
        # json.dumps 默认无法处理 Enum 等对象，这里统一做一次字符串化兜底
        for k, v in list(payload.items()):
            if isinstance(v, (str, int, float, bool)) or v is None:
                continue
            payload[k] = str(v)
        mxid = payload.get("mxid") or getattr(d, "mxid", None) or "<unknown>"
        out[str(mxid)] = payload
    return out


def _diff(mx_map1: Dict[str, dict], mx_map2: Dict[str, dict]) -> Tuple[List[str], List[str], Dict[str, Dict[str, Tuple[object, object]]]]:
    s1 = set(mx_map1.keys())
    s2 = set(mx_map2.keys())
    missing = sorted(s1 - s2)
    extra = sorted(s2 - s1)

    changed: Dict[str, Dict[str, Tuple[object, object]]] = {}
    for mx in sorted(s1 & s2):
        a = mx_map1[mx]
        b = mx_map2[mx]
        fields = [
            "product_name",
            "connection_status",
            "notes",
            "first_seen",
            "last_seen",
        ]
        for f in fields:
            va = a.get(f)
            vb = b.get(f)
            if va != vb:
                changed.setdefault(mx, {})[f] = (va, vb)

    return missing, extra, changed


def main(argv: Optional[Sequence[str]] = None) -> int:
    # 硬编码参数：尽量贴近 binding 场景（连续两次）
    interval_sec = 0.0  # 两次扫描间隔（秒）。如怀疑状态抖动，可改为 0.2/1.0
    output_path = Path("./testlogs/manual/OAKAPI/two_scans_compare.json")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("OAKAPI Two-Scans Compare")
    print(f"interval_sec={interval_sec}")
    print("=" * 80)

    t1 = time.time()
    devices1 = OAKDeviceDiscovery.discover_devices(verbose=False)
    t2 = time.time()

    if interval_sec > 0:
        time.sleep(interval_sec)

    t3 = time.time()
    devices2 = OAKDeviceDiscovery.discover_devices(verbose=False)
    t4 = time.time()

    m1 = _to_map(devices1)
    m2 = _to_map(devices2)

    missing, extra, changed = _diff(m1, m2)

    print(f"scan#1 count={len(m1)} dt={(t2 - t1):.3f}s mxids={sorted(m1.keys())}")
    print(f"scan#2 count={len(m2)} dt={(t4 - t3):.3f}s mxids={sorted(m2.keys())}")

    if not missing and not extra and not changed:
        print("DIFF: 两次扫描完全一致")
    else:
        print("DIFF: 检测到差异")
        if missing:
            print(f"- missing(second scan not found): {missing}")
        if extra:
            print(f"- extra(only in second scan): {extra}")
        if changed:
            print("- changed(common mxids field changes):")
            for mx, fields in changed.items():
                print(f"  - {mx}:")
                for f, (va, vb) in fields.items():
                    print(f"    - {f}: {va} -> {vb}")

    payload = {
        "params": {
            "interval_sec": interval_sec,
        },
        "scan1": {
            "ts": t1,
            "ts_end": t2,
            "devices": m1,
        },
        "scan2": {
            "ts": t3,
            "ts_end": t4,
            "devices": m2,
        },
        "diff": {
            "missing": missing,
            "extra": extra,
            "changed": {
                mx: {f: [va, vb] for f, (va, vb) in fields.items()} for mx, fields in changed.items()
            },
        },
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n已保存结果: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
