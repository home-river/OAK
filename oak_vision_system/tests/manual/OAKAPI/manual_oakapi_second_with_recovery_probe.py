"""A 方案：测量“第二次 with dai.Device(...) 何时恢复可用”的恢复时间窗。

思路：
1) 记录触发前枚举（normal + bootloader 可选）。
2) 触发一次 open/close：仅执行 `with dai.Device(dai.Pipeline(), DeviceInfo(mxid), usb2Mode=...) as device:`
   不做 readCalibration / EEPROM 等额外操作。
3) 从触发结束开始计时，以固定轮询间隔不断尝试“第二次 with（同一 mxid）”，直到成功或超时。
4) 全流程写入独立 .log 文件（文件头是 meta 配置），后续每个 probe 会追加 pretty JSON。

运行：
    python oak_vision_system/tests/manual/OAKAPI/manual_oakapi_second_with_recovery_probe.py

输出：
    ./testlogs/manual/OAKAPI/second_with_recovery_<timestamp>_mxid-..._poll-..._max-... .log
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

    # 触发动作参数（建议先最小化）
    usb2_mode = True

    # 轮询参数
    poll_interval_sec = 0.1
    max_wait_sec = 30.0

    # 轮询时是否采样枚举（注意：枚举本身约 0.5s，会显著拉长“尝试频率”）
    # - 0: 不在轮询中做枚举（推荐，用于更精确测“第二次 with 最短恢复时间”）
    # - N>0: 每 N 次 with 重试采样一次（normal + bootloader）
    enum_every_n_polls = 0

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(
        f"./testlogs/manual/OAKAPI/second_with_recovery_{run_ts}_mxid-{mxid}_poll-{poll_interval_sec}_max-{max_wait_sec}_usb2-{usb2_mode}.log"
    )

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
                        "enum_every_n_polls": enum_every_n_polls,
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        fp.write("\n\n")

    print("\n\n", end="")
    print("=" * 80)
    print("OAKAPI Second With Recovery Probe (方案A)")
    print(f"mxid={mxid} usb2_mode={usb2_mode} poll_interval_sec={poll_interval_sec} max_wait_sec={max_wait_sec}")
    print(f"log_path={log_path}")
    print("=" * 80)

    # 1) 触发前枚举（基线）
    probe_get_all_available_devices(log_path=log_path, continuous=False, use_bootloader=False)
    probe_get_all_available_devices(log_path=log_path, continuous=False, use_bootloader=True)

    # 2) 触发一次 open/close
    print("[trigger] with Device structure only ...")
    trigger_results = probe_with_device_structure_only(
        log_path=log_path,
        mxid=mxid,
        usb2_mode=usb2_mode,
        continuous=False,
        n_calls=1,
    )
    trigger_ok = bool(trigger_results and trigger_results[-1].ok)
    print(f"[trigger] ok={trigger_ok}")

    # 3) 轮询重试第二次 with，直到成功
    t0 = time.perf_counter()
    recovered = False
    recovered_elapsed_sec: float | None = None
    attempt = 0

    while True:
        time.sleep(poll_interval_sec)
        attempt += 1

        elapsed = time.perf_counter() - t0
        if elapsed >= max_wait_sec:
            break

        normal_present: bool | None
        boot_present: bool | None
        if enum_every_n_polls > 0 and (attempt % enum_every_n_polls == 0):
            normal_results = probe_get_all_available_devices(log_path=log_path, continuous=False, use_bootloader=False)
            boot_results = probe_get_all_available_devices(log_path=log_path, continuous=False, use_bootloader=True)
            normal_present = _mxid_present(normal_results[-1], mxid) if normal_results else False
            boot_present = _mxid_present(boot_results[-1], mxid) if boot_results else False
        else:
            normal_present = None
            boot_present = None

        print(
            f"[poll] attempt={attempt} elapsed_sec={elapsed:.3f} "
            f"present.normal={normal_present} present.bootloader={boot_present}"
        )

        results = probe_with_device_structure_only(
            log_path=log_path,
            mxid=mxid,
            usb2_mode=usb2_mode,
            continuous=False,
            n_calls=1,
        )
        ok = bool(results and results[-1].ok)
        print(f"[poll] attempt={attempt} with_ok={ok}")

        if ok:
            recovered = True
            recovered_elapsed_sec = time.perf_counter() - t0
            break

    # 4) 收尾枚举
    probe_get_all_available_devices(log_path=log_path, continuous=False, use_bootloader=False)
    probe_get_all_available_devices(log_path=log_path, continuous=False, use_bootloader=True)

    summary = {
        "summary": {
            "mxid": mxid,
            "usb2_mode": usb2_mode,
            "poll_interval_sec": poll_interval_sec,
            "max_wait_sec": max_wait_sec,
            "enum_every_n_polls": enum_every_n_polls,
            "recovered": recovered,
            "recovered_elapsed_sec": recovered_elapsed_sec,
            "trigger_ok": trigger_ok,
            "attempts": attempt,
        }
    }

    with log_path.open("a", encoding="utf-8") as fp:
        fp.write("\n")
        fp.write(json.dumps(summary, ensure_ascii=False, indent=2))
        fp.write("\n")

    print("=" * 80)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
