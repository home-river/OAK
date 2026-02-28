"""测量：退出 `with dai.Device(...) as device:` 后，目标设备多久能重新出现在枚举中。

运行：
    python oak_vision_system/tests/manual/OAKAPI/manual_oakapi_recovery_window_probe.py

说明：
- 本脚本会先进行一次“触发动作”（with-device 结构 only，尽量不做额外 API 调用）
- 然后按固定间隔轮询枚举：
  - normal: `dai.Device.getAllAvailableDevices()`
  - bootloader: `dai.DeviceBootloader.getAllAvailableDevices()`
- 一旦目标 mxid 在任一枚举中出现，就记录“恢复耗时”并停止。
- 结果写入独立 `.log` 文件，文件开头包含本次配置参数，后续为 pretty JSON 分块记录。
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from oak_vision_system.tests.manual.OAKAPI.oakapi_probe_utils import (
    probe_get_all_available_devices,
    probe_with_device_structure_only,
)


def _mxid_present(rec: dict, mxid: str) -> bool:
    try:
        mxids = rec.get("result", {}).get("mxids", [])
        return str(mxid) in set(map(str, mxids))
    except Exception:
        return False


def main() -> int:
    mxid = "19443010F1221E1300"

    # 触发动作参数（建议先最小化）
    usb2_mode = True

    # 轮询参数
    poll_interval_sec = 0.1
    max_wait_sec = 30.0

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(f"./testlogs/manual/OAKAPI/recovery_window_{run_ts}_mxid-{mxid}_poll-{poll_interval_sec}_max-{max_wait_sec}.log")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "meta": {
                        "run_ts": run_ts,
                        "mxid": mxid,
                        "usb2_mode": usb2_mode,
                        "poll_interval_sec": poll_interval_sec,
                        "max_wait_sec": max_wait_sec,
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        fp.write("=" * 80 + "\n")
        fp.flush()

    print("\n\n", end="")
    print("=" * 80)
    print("OAKAPI Recovery Window Probe")
    print(f"mxid={mxid}")
    print(f"poll_interval_sec={poll_interval_sec} max_wait_sec={max_wait_sec}")
    print(f"usb2_mode={usb2_mode}")
    print(f"log_path={log_path}")
    print("=" * 80)

    # baseline：触发前的枚举快照
    probe_get_all_available_devices(
        log_path=log_path,
        continuous=False,
        n_calls=1,
        internal_gap_sec=0.0,
        use_bootloader=False,
    )
    probe_get_all_available_devices(
        log_path=log_path,
        continuous=False,
        n_calls=1,
        internal_gap_sec=0.0,
        use_bootloader=True,
    )

    # trigger：执行一次 with-device（结构 only）
    t_trigger_start = time.perf_counter()
    trigger_recs = probe_with_device_structure_only(
        log_path=log_path,
        mxid=mxid,
        continuous=False,
        n_calls=1,
        internal_gap_sec=0.0,
        usb2_mode=usb2_mode,
    )
    t_trigger_end = time.perf_counter()

    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "trigger": {
                        "duration_sec": float(t_trigger_end - t_trigger_start),
                        "ok": bool(trigger_recs and getattr(trigger_recs[0], "ok", False)),
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        fp.write("=" * 80 + "\n")
        fp.flush()

    # poll：轮询直到恢复或超时
    t0 = time.perf_counter()
    deadline = t0 + max_wait_sec

    recovered = False
    recovered_in = None
    recovered_elapsed = None

    attempt = 0
    while time.perf_counter() < deadline:
        attempt += 1
        now = time.perf_counter()
        elapsed = now - t0

        normal_recs = probe_get_all_available_devices(
            log_path=log_path,
            continuous=False,
            n_calls=1,
            internal_gap_sec=0.0,
            use_bootloader=False,
        )
        boot_recs = probe_get_all_available_devices(
            log_path=log_path,
            continuous=False,
            n_calls=1,
            internal_gap_sec=0.0,
            use_bootloader=True,
        )

        normal_present = False
        boot_present = False
        if normal_recs:
            normal_present = _mxid_present(normal_recs[0].__dict__, mxid)
        if boot_recs:
            boot_present = _mxid_present(boot_recs[0].__dict__, mxid)

        with log_path.open("a", encoding="utf-8") as fp:
            fp.write(
                json.dumps(
                    {
                        "poll": {
                            "attempt": attempt,
                            "elapsed_sec": float(elapsed),
                            "present": {"normal": normal_present, "bootloader": boot_present},
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            fp.write("=" * 80 + "\n")
            fp.flush()

        if normal_present:
            recovered = True
            recovered_in = "normal"
            recovered_elapsed = elapsed
            break
        if boot_present:
            recovered = True
            recovered_in = "bootloader"
            recovered_elapsed = elapsed
            break

        time.sleep(poll_interval_sec)

    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "summary": {
                        "recovered": recovered,
                        "recovered_in": recovered_in,
                        "recovered_elapsed_sec": recovered_elapsed,
                        "max_wait_sec": max_wait_sec,
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        fp.flush()

    if recovered:
        print(f"恢复成功：elapsed={recovered_elapsed:.3f}s in={recovered_in}")
    else:
        print(f"恢复失败：在 {max_wait_sec:.1f}s 内未观察到 mxid={mxid} 回到枚举")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
