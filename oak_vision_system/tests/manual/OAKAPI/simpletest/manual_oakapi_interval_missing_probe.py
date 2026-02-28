"""按不同时间间隔执行“两连扫”，记录出现缺失时的时间间隔。

目标：
- 使用与 manual_oakapi_two_scans_compare.py 相同的发现方式：
  scan1 -> sleep(interval) -> scan2
- 对一组 interval 逐个测试，每次测试重复多轮
- 一旦发现 scan2 相对 scan1 出现 missing/extra，立刻记录并可选择停止

运行：
    python oak_vision_system/tests/manual/OAKAPI/manual_oakapi_interval_missing_probe.py
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set


def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    for p in (current, *current.parents):
        if (p / "pyproject.toml").exists():
            return p
    return start.resolve()


project_root = _find_project_root(Path(__file__).parent)
sys.path.insert(0, str(project_root))


from oak_vision_system.modules.config_manager.device_discovery import OAKDeviceDiscovery  # noqa: E402


@dataclass
class TrialRecord:
    ts: float
    interval_target_sec: float
    interval_actual_sec: float
    scan1_dt_sec: float
    scan2_dt_sec: float
    mxids_1: List[str]
    mxids_2: List[str]
    missing: List[str]
    extra: List[str]


def _mxids_from_devices(devices) -> List[str]:
    mxids: List[str] = []
    for d in devices:
        mx = getattr(d, "mxid", None)
        if mx is None:
            continue
        mxids.append(str(mx))
    return sorted(set(mxids))


def _dump_jsonl(fp, obj: object) -> None:
    fp.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
    fp.flush()


def main(argv: Optional[Sequence[str]] = None) -> int:
    # 硬编码参数（按你的需求：不是统计汇总，而是记录“缺失出现时的间隔”）
    # 待扫描的时间间隔（秒），注意：这里的时间间隔是相对于两次扫描间隔的时间间隔
    # 如设置为[0.0, 0.01, 0.02, ...]，即在每次扫描后睡眠0秒、0.01秒、0.02秒等，
    # 然后再进行下一次扫描，这样的话，即使扫描本身的时间很短，也能反映出缺失的时间间隔
    # 如设置为[1.0, 2.0, 5.0, ...]，即在每次扫描后睡眠1秒、2秒、5秒等，
    # 然后再进行下一次扫描，这样的话，如果扫描本身的时间很长，也能反映出缺失的时间间隔
    interval_start = 0.5
    interval_end = 0.0
    interval_step = -0.01
    n_steps = int((interval_end - interval_start) / interval_step) + 1
    intervals_sec = [round(interval_start + i * interval_step, 6) for i in range(max(0, n_steps))]
    extra_head = [1.0]
    extra_tail: List[float] = []
    ordered = extra_head + intervals_sec + extra_tail
    seen: Set[float] = set()
    intervals_sec = [x for x in ordered if not (x in seen or seen.add(x))]
    # 每个时间间隔内的扫描次数
    trials_per_interval = 30
    # 是否在检测到缺失后停止整个扫描过程
    stop_on_first_missing = False

    log_path = Path("./testlogs/manual/OAKAPI/interval_missing_probe.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("OAKAPI Interval Missing Probe")
    print(f"intervals_sec={intervals_sec}")
    print(f"trials_per_interval={trials_per_interval} stop_on_first_missing={stop_on_first_missing}")
    print(f"log_path={log_path}")
    print("=" * 80)

    with log_path.open("w", encoding="utf-8") as fp:
        _dump_jsonl(
            fp,
            {
                "meta": {
                    "ts": time.time(),
                    "intervals_sec": intervals_sec,
                    "trials_per_interval": trials_per_interval,
                    "stop_on_first_missing": stop_on_first_missing,
                }
            },
        )

        for interval in intervals_sec:
            print(f"\n--- interval={interval:.3f}s ---")
            for trial_idx in range(1, trials_per_interval + 1):
                t1 = time.perf_counter()
                d1 = OAKDeviceDiscovery.discover_devices(verbose=False)
                t2 = time.perf_counter()

                if interval > 0:
                    time.sleep(interval)

                t3 = time.perf_counter()
                d2 = OAKDeviceDiscovery.discover_devices(verbose=False)
                t4 = time.perf_counter()

                mx1 = _mxids_from_devices(d1)
                mx2 = _mxids_from_devices(d2)

                s1 = set(mx1)
                s2 = set(mx2)
                missing = sorted(s1 - s2)
                extra = sorted(s2 - s1)

                rec = TrialRecord(
                    ts=time.time(),
                    interval_target_sec=float(interval),
                    interval_actual_sec=float(t3 - t2),
                    scan1_dt_sec=float(t2 - t1),
                    scan2_dt_sec=float(t4 - t3),
                    mxids_1=mx1,
                    mxids_2=mx2,
                    missing=missing,
                    extra=extra,
                )
                _dump_jsonl(fp, asdict(rec))

                line = (
                    f"[{trial_idx:02d}/{trials_per_interval}] "
                    f"gap_target={interval:.3f}s gap_actual={rec.interval_actual_sec:.3f}s "
                    f"scan1={len(mx1)} scan2={len(mx2)}"
                )
                if missing or extra:
                    line += f"  MISMATCH missing={missing} extra={extra}"
                print(line)

                if (missing or extra) and stop_on_first_missing:
                    print("\n发现缺失/差异，已停止。")
                    print(f"interval_target_sec={rec.interval_target_sec}")
                    print(f"interval_actual_sec={rec.interval_actual_sec}")
                    return 0

    print("\n未发现缺失/差异，已完成全部测试。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
