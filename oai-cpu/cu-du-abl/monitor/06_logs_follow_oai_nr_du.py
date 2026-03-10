#!/usr/bin/env python3
"""06_logs_follow_oai_nr_du.py

Follow `docker logs -f` for the DU container and prefix each line with an
epoch timestamp for time alignment.

Example:
  python3 06_logs_follow_oai_nr_du.py --out du_docker_logs.tsv

TSV Output Columns:
  ts_epoch_ms  container  log_line
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO

CONTAINER = "oai-nr-du"


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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=str, default="-", help="Output TSV path (or '-' for stdout).")
    p.add_argument(
        "--since",
        type=str,
        default="0s",
        help="Pass-through to `docker logs --since`. Default '0s' means start from now.",
    )
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
    out_f.write(f"# start_epoch_ms={epoch_ms()} container={CONTAINER} since={args.since}\n")
    out_f.write("ts_epoch_ms\tcontainer\tlog_line\n")

    cmd = ["docker", "logs", "--since", args.since, "-f", CONTAINER]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        sys.stderr.write("ERROR: docker not found on PATH.\n")
        return 2

    assert proc.stdout is not None

    try:
        for line in proc.stdout:
            ts = epoch_ms()
            out_f.write(f"{ts}\t{CONTAINER}\t{line.rstrip()}\n")
    except KeyboardInterrupt:
        pass
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        if out_f is not sys.stdout:
            out_f.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
