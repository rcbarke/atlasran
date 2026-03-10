#!/usr/bin/env python3
"""03_cpu_monitor_oai_nr_cu.py

Collect container-level CPU utilization for `oai-nr-cu` using `docker stats`.

Why `docker stats` (vs htop):
- Script-friendly and easy to timestamp.
- Separates CU and DU containers cleanly.

Example:
  python3 03_cpu_monitor_oai_nr_cu.py --interval 0.5 --out cu_cpu.csv

CSV Columns:
  ts_epoch_ms,container,cpu_percent,mem_percent,mem_usage,net_io,block_io,pids
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO

CONTAINER = "oai-nr-cu"


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


def parse_percent(s: str) -> float:
    s = s.strip()
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s)
    except Exception:
        return float("nan")


def docker_stats_once(container: str) -> str:
    # format: name,cpu%,memUsage,mem%,netIO,blockIO,pids
    fmt = "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}"
    cmd = ["docker", "stats", "--no-stream", "--format", fmt, container]
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()


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
    out_f.write(f"# start_epoch_ms={epoch_ms()} interval_s={args.interval} container={CONTAINER}\n")
    out_f.write("ts_epoch_ms,container,cpu_percent,mem_percent,mem_usage,net_io,block_io,pids\n")

    try:
        while True:
            ts = epoch_ms()
            try:
                line = docker_stats_once(CONTAINER)
            except FileNotFoundError:
                sys.stderr.write("ERROR: docker not found on PATH.\n")
                return 2
            except subprocess.CalledProcessError as e:
                sys.stderr.write(f"ERROR: docker stats failed: {e.output}\n")
                return 3

            # Split the docker stats line
            # name,cpu%,memUsage,mem%,netIO,blockIO,pids
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                name, cpu_s, mem_usage, mem_s, net_io, block_io, pids = parts[:7]
                cpu = parse_percent(cpu_s)
                mem = parse_percent(mem_s)
                out_f.write(f"{ts},{name},{cpu},{mem},{mem_usage},{net_io},{block_io},{pids}\n")
            else:
                # Write raw line for debugging
                out_f.write(f"{ts},{CONTAINER},nan,nan,NA,NA,NA,NA\n")

            time.sleep(max(0.0, args.interval))
    except KeyboardInterrupt:
        return 0
    finally:
        if out_f is not sys.stdout:
            out_f.close()


if __name__ == "__main__":
    raise SystemExit(main())
