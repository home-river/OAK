"""轮询测试：触发一次 `probe_get_eeprom_datav2` 后，轮询观察设备何时恢复可用。

用途：验证你提出的“非 with 打开方式（dai.Device(DeviceInfo)）”是否仍会触发
短暂掉线/不可枚举/不可再次打开的问题。

流程：
1) baseline：触发前枚举快照（normal + bootloader）
2) trigger：执行一次 `probe_get_eeprom_datav2`（会 open device + readCalibration + getEepromData）
3) poll：按固定间隔轮询
   - `with dai.Device(...)`（结构 only）何时第一次恢复可用

运行：
    python oak_vision_system/tests/manual/OAKAPI/manual_oakapi_eeprom_datav2_recovery_window_probe.py

输出：
    ./testlogs/manual/OAKAPI/eeprom_datav2_recovery_window_<timestamp>_mxid-..._poll-..._max-....log
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from oak_vision_system.tests.manual.OAKAPI.oakapi_probe_utils import (
    probe_get_eeprom_datav2,
    probe_with_device_structure_only,
)


def _mxid_present(rec: object, mxid: str) -> bool:
    try:
        result = getattr(rec, "result", None)
        if isinstance(result, dict):
            mxids = result.get("mxids", [])
            return str(mxid) in set(map(str, mxids))

        if isinstance(rec, dict):
            mxids = rec.get("result", {}).get("mxids", [])
            return str(mxid) in set(map(str, mxids))

        return False
    except Exception:
        return False


def main() -> int:
    mxid = "19443010F1221E1300"

    # 轮询参数
    poll_interval_sec = 0.1
    max_wait_sec = 30.0

    # with 恢复测试参数
    usb2_mode_for_with = True

    # baseline 是否记录一次枚举快照（只做一次，不参与轮询；便于复现实验环境）
    record_baseline_enum = True

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(
        f"./testlogs/manual/OAKAPI/eeprom_datav2_recovery_window_{run_ts}_mxid-{mxid}_poll-{poll_interval_sec}_max-{max_wait_sec}.log"
    )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "meta": {
                        "run_ts": run_ts,
                        "mxid": mxid,
                        "poll_interval_sec": poll_interval_sec,
                        "max_wait_sec": max_wait_sec,
                        "usb2_mode_for_with": usb2_mode_for_with,
                        "record_baseline_enum": record_baseline_enum,
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        fp.write("\n\n")

    print("\n\n", end="")
    print("=" * 80)
    print("OAKAPI EEPROM Data v2 Recovery Window Probe")
    print(f"mxid={mxid}")
    print(f"poll_interval_sec={poll_interval_sec} max_wait_sec={max_wait_sec}")
    print(f"usb2_mode_for_with={usb2_mode_for_with}")
    print(f"log_path={log_path}")
    print("=" * 80)

    # baseline
    if record_baseline_enum:
        from oak_vision_system.tests.manual.OAKAPI.oakapi_probe_utils import probe_get_all_available_devices

        probe_get_all_available_devices(log_path=log_path, continuous=False, n_calls=1, internal_gap_sec=0.0, use_bootloader=False)
        probe_get_all_available_devices(log_path=log_path, continuous=False, n_calls=1, internal_gap_sec=0.0, use_bootloader=True)

    # trigger
    t_trigger_start = time.perf_counter()
    trigger_recs = probe_get_eeprom_datav2(
        log_path=log_path,
        mxid=mxid,
        continuous=False,
        n_calls=1,
        internal_gap_sec=0.0,
        usb2_mode=True,
    )
    t_trigger_end = time.perf_counter()

    trigger_ok = bool(trigger_recs and trigger_recs[-1].ok)
    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "trigger": {
                        "name": "probe_get_eeprom_datav2",
                        "ok": trigger_ok,
                        "duration_sec": float(t_trigger_end - t_trigger_start),
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        fp.write("\n" + ("=" * 80) + "\n")

    # poll
    t0 = time.perf_counter()

    with_recovered = False
    with_recovered_start_elapsed_sec: float | None = None
    with_recovered_finish_elapsed_sec: float | None = None

    attempt = 0
    while True:
        elapsed = time.perf_counter() - t0
        if elapsed >= max_wait_sec:
            break

        time.sleep(poll_interval_sec)
        attempt += 1

        if not with_recovered:
            with_attempt_start = float(elapsed)
            with_recs = probe_with_device_structure_only(
                log_path=log_path,
                mxid=mxid,
                continuous=False,
                n_calls=1,
                internal_gap_sec=0.0,
                usb2_mode=usb2_mode_for_with,
            )
            with_ok = bool(with_recs and with_recs[-1].ok)
            with_attempt_finish = float(time.perf_counter() - t0)

            with log_path.open("a", encoding="utf-8") as fp:
                fp.write(
                    json.dumps(
                        {
                            "with_poll": {
                                "attempt": attempt,
                                "start_elapsed_sec": with_attempt_start,
                                "finish_elapsed_sec": with_attempt_finish,
                                "ok": with_ok,
                                "error": (with_recs[-1].error if with_recs else None),
                            }
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                fp.write("\n" + ("=" * 80) + "\n")

            if with_ok:
                with_recovered = True
                with_recovered_start_elapsed_sec = with_attempt_start
                with_recovered_finish_elapsed_sec = with_attempt_finish

        if with_recovered:
            break

    summary = {
        "summary": {
            "trigger_ok": trigger_ok,
            "with_recovered": with_recovered,
            "with_recovered_start_elapsed_sec": with_recovered_start_elapsed_sec,
            "with_recovered_finish_elapsed_sec": with_recovered_finish_elapsed_sec,
            "attempts": attempt,
            "max_wait_sec": max_wait_sec,
        }
    }

    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(summary, ensure_ascii=False, indent=2))
        fp.write("\n")

    print("=" * 80)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("=" * 80)

    if with_recovered:
        print(
            "with 恢复："
            f"start_elapsed={with_recovered_start_elapsed_sec:.3f}s "
            f"finish_elapsed={with_recovered_finish_elapsed_sec:.3f}s"
        )
    else:
        print("with 未恢复")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
