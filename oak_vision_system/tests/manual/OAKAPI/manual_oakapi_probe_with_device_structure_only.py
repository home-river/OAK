"""验证仅 `with dai.Device(...) as device:` 上下文 open/close 是否会引起设备短暂掉线/枚举抖动。

运行：
    python oak_vision_system/tests/manual/OAKAPI/manual_oakapi_probe_with_device_structure_only.py

说明：
- 本脚本硬编码一个 mxid
- 每轮执行：枚举 -> with-device(仅结构) -> 枚举
- 结果写入独立的 .log 文件（pretty JSON 分块），便于离线分析每一步的耗时/异常与枚举变化
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


def main() -> int:
    # 硬编码：你可以改成要重点观察的那台设备
    mxid = "19443010F1221E1300"

    # 每轮测试的间隔（外部控制）
    outer_gap_sec = 5.0

    # with-device 内部连续调用参数
    internal_gap_sec = 10.0
    n_calls = 2

    # 总轮数：每轮都会做 枚举->with-device(仅结构) -> 枚举
    rounds = 1

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(
        f"./testlogs/manual/OAKAPI/probe_with_device_structure_only_{run_ts}_mxid-{mxid}_outer-{outer_gap_sec}_internal-{internal_gap_sec}_calls-{n_calls}_rounds-{rounds}.log"
    )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "meta": {
                        "run_ts": run_ts,
                        "mxid": mxid,
                        "outer_gap_sec": outer_gap_sec,
                        "internal_gap_sec": internal_gap_sec,
                        "n_calls": n_calls,
                        "rounds": rounds,
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
    print("OAKAPI Probe: with Device structure only")
    print(f"mxid={mxid}")
    print(f"rounds={rounds} outer_gap_sec={outer_gap_sec}")
    print(f"with-device: n_calls={n_calls} internal_gap_sec={internal_gap_sec}")
    print(f"log_path={log_path}")
    print("=" * 80)

    for r in range(1, rounds + 1):
        print(f"\n--- round {r}/{rounds} ---")

        probe_get_all_available_devices(
            log_path=log_path,
            continuous=False,
            n_calls=1,
            internal_gap_sec=0.0,
            use_bootloader=False,
        )

        probe_with_device_structure_only(
            log_path=log_path,
            mxid=mxid,
            continuous=True,
            n_calls=n_calls,
            internal_gap_sec=internal_gap_sec,
            usb2_mode=True,
        )

        probe_get_all_available_devices(
            log_path=log_path,
            continuous=False,
            n_calls=1,
            internal_gap_sec=0.0,
            use_bootloader=False,
        )

        

        if outer_gap_sec > 0 and r != rounds:
            time.sleep(outer_gap_sec)

    print("\n完成。请查看 jsonl 并重点对比每轮 with-device 前后两次枚举的 mxids 是否变化。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
