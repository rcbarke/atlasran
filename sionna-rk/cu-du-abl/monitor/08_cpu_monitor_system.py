#!/usr/bin/env python3
"""08_cpu_monitor_system.py

Collect *system-wide* CPU utilization (all processes, all cores) from /proc/stat.

This is intentionally *not* pinned to any specific processes/containers, so it
acts as a cumulative host CPU reference to compare against pinned CU/DU numbers.

Example:
  python3 08_cpu_monitor_system.py --interval 0.5 --out system_cpu.csv

CSV Columns:
  ts_epoch_ms,
  cpu_total_pct,cpu_user_pct,cpu_system_pct,cpu_iowait_pct,cpu_idle_pct,
  load1,load5,load15,procs_running,procs_total
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, TextIO, Tuple


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


def read_proc_stat_cpu() -> Dict[str, int]:
    """
    Parse the aggregate 'cpu' line in /proc/stat.

    Fields (Linux): user nice system idle iowait irq softirq steal guest guest_nice
    We use the first 8 (user..steal) for utilization math.
    """
    with open("/proc/stat", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("cpu "):
                parts = line.split()
                # parts[0] == "cpu"
                vals = [int(x) for x in parts[1:]]
                # Pad defensively (older kernels may expose fewer fields)
                while len(vals) < 8:
                    vals.append(0)
                keys = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"]
                return {k: vals[i] for i, k in enumerate(keys)}
    raise RuntimeError("Could not find aggregate 'cpu' line in /proc/stat")


def read_loadavg() -> Tuple[float, float, float, int, int]:
    """
    /proc/loadavg format:
      1min 5min 15min running/total last_pid
    """
    with open("/proc/loadavg", "r", encoding="utf-8") as f:
        s = f.read().strip().split()
    load1, load5, load15 = float(s[0]), float(s[1]), float(s[2])
    running_s, total_s = s[3].split("/")
    return load1, load5, load15, int(running_s), int(total_s)


def pct(numer: int, denom: int) -> float:
    if denom <= 0:
        return float("nan")
    return 100.0 * (numer / denom)


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
    out_f.write(f"# start_epoch_ms={epoch_ms()} interval_s={args.interval} source=/proc/stat\n")
    out_f.write(
        "ts_epoch_ms,"
        "cpu_total_pct,cpu_user_pct,cpu_system_pct,cpu_iowait_pct,cpu_idle_pct,"
        "load1,load5,load15,procs_running,procs_total\n"
    )

    prev = None

    try:
        while True:
            ts = epoch_ms()

            try:
                cur = read_proc_stat_cpu()
                load1, load5, load15, pr, pt = read_loadavg()
            except FileNotFoundError:
                sys.stderr.write("ERROR: /proc not available (are you on Linux?).\n")
                return 2
            except Exception as e:
                sys.stderr.write(f"ERROR: failed reading /proc stats: {e}\n")
                return 3

            if prev is None:
                # Need a previous sample to compute deltas.
                out_f.write(
                    f"{ts},nan,nan,nan,nan,nan,{load1},{load5},{load15},{pr},{pt}\n"
                )
                prev = cur
                time.sleep(max(0.0, args.interval))
                continue

            # Compute deltas
            d = {k: max(0, cur[k] - prev.get(k, 0)) for k in cur.keys()}
            prev = cur

            idle_all = d["idle"] + d["iowait"]
            non_idle = d["user"] + d["nice"] + d["system"] + d["irq"] + d["softirq"] + d["steal"]
            total = idle_all + non_idle

            total_pct = pct(non_idle, total)
            user_pct = pct(d["user"] + d["nice"], total)
            system_pct = pct(d["system"] + d["irq"] + d["softirq"], total)
            iowait_pct = pct(d["iowait"], total)
            idle_pct = pct(d["idle"], total)

            out_f.write(
                f"{ts},"
                f"{total_pct:.6f},{user_pct:.6f},{system_pct:.6f},{iowait_pct:.6f},{idle_pct:.6f},"
                f"{load1},{load5},{load15},{pr},{pt}\n"
            )

            time.sleep(max(0.0, args.interval))

    except KeyboardInterrupt:
        return 0
    finally:
        if out_f is not sys.stdout:
            out_f.close()


if __name__ == "__main__":
    raise SystemExit(main())
