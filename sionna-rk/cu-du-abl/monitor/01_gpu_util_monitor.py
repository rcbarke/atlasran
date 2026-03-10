#!/usr/bin/env python3
"""01_gpu_util_monitor.py

Collect GPU utilization metrics via `nvidia-smi` at a fixed interval.

Outputs CSV rows with an epoch timestamp so this stream can be aligned
with other monitors (docker stats, logs, ZMQ client, etc.).

Example:
  python3 01_gpu_util_monitor.py --interval 0.5 --out gpu_util.csv

CSV Columns:
  ts_epoch_ms,gpu_index,util_gpu_pct,util_mem_pct
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO, List


def epoch_ms() -> int:
    return int(time.time() * 1000)


def wait_until(epoch_ms_target: int) -> None:
    while True:
        now = epoch_ms()
        if now >= epoch_ms_target:
            return
        time.sleep(min(0.05, (epoch_ms_target - now) / 1000.0))


def open_out(path: str | None) -> TextIO:
    if path is None or path == "-":
        return sys.stdout
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return open(path, "w", buffering=1)


def run_nvidia_smi_query() -> List[str]:
    cmd = [
        "nvidia-smi",
        "--query-gpu=index,utilization.gpu,utilization.memory",
        "--format=csv,noheader,nounits",
    ]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=float, default=0.5, help="Sampling interval (seconds).")
    p.add_argument("--out", type=str, default="-", help="Output CSV path (or '-' for stdout).")
    p.add_argument(
        "--wait-until-epoch-ms",
        type=int,
        default=0,
        help="If set, sleep until this epoch-ms before starting collection.",
    )
    args = p.parse_args()

    if args.wait_until_epoch_ms and args.wait_until_epoch_ms > 0:
        wait_until(args.wait_until_epoch_ms)

    out_f = open_out(args.out)

    out_f.write(f"# start_epoch_ms={epoch_ms()} interval_s={args.interval}\n")
    out_f.write("ts_epoch_ms,gpu_index,util_gpu_pct,util_mem_pct\n")

    try:
        while True:
            ts = epoch_ms()
            try:
                for row in run_nvidia_smi_query():
                    parts = [x.strip() for x in row.split(",")]
                    if len(parts) < 3:
                        continue
                    gpu_index, util_gpu, util_mem = parts[0], parts[1], parts[2]
                    out_f.write(f"{ts},{gpu_index},{util_gpu},{util_mem}\n")
            except FileNotFoundError:
                sys.stderr.write("ERROR: nvidia-smi not found. Are NVIDIA drivers/tools installed?\n")
                return 2
            except subprocess.CalledProcessError as e:
                sys.stderr.write(f"ERROR: nvidia-smi failed: {e.output}\n")
                return 3

            time.sleep(max(0.0, args.interval))
    except KeyboardInterrupt:
        return 0
    finally:
        if out_f is not sys.stdout:
            out_f.close()


if __name__ == "__main__":
    raise SystemExit(main())
