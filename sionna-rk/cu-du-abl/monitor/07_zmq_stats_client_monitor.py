#!/usr/bin/env python3
"""07_zmq_stats_client_monitor.py

Run the RIC ZMQ stats client from the SRK source tree and prefix each line
with an epoch timestamp for time alignment.

Per requirement, this wrapper runs:
  python3 ../../plugins/ric_xapps/src/zmq_stats_client.py
from the SRK root context, using the SRK `venv/` interpreter when available.

Example (from anywhere):
  python3 07_zmq_stats_client_monitor.py --out zmq_stats.tsv

Pass-through args to the underlying client:
  python3 07_zmq_stats_client_monitor.py -- --host 127.0.0.1 --port 5555

TSV Output Columns:
  ts_epoch_ms  stream  line
"""

from __future__ import annotations

import argparse
import os
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


def guess_srk_root() -> Path:
    # Expected location: <SRK_ROOT>/cu-du-abl/monitor/this_script.py
    here = Path(__file__).resolve()
    # parents: [monitor, cu-du-abl, SRK_ROOT, ...]
    if len(here.parents) >= 3:
        return here.parents[2]
    return Path.cwd().resolve()


def pick_python(srk_root: Path, python_override: str | None) -> str:
    if python_override:
        return python_override
    venv_py = srk_root / "venv" / "bin" / "python"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def main() -> int:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--out", type=str, default="-", help="Output TSV path (or '-' for stdout).")
    p.add_argument(
        "--srk-root",
        type=str,
        default="",
        help="Override SRK root path. Default: inferred from script location.",
    )
    p.add_argument(
        "--python",
        type=str,
        default="",
        help="Override Python interpreter (otherwise uses <srk_root>/venv/bin/python if it exists).",
    )
    p.add_argument(
        "--wait-until-epoch-ms",
        type=int,
        default=0,
        help="If set, sleep until this epoch-ms before starting collection.",
    )
    p.add_argument(
        "client_args",
        nargs=argparse.REMAINDER,
        help="Args after `--` are passed to zmq_stats_client.py.",
    )
    args = p.parse_args()

    if args.wait_until_epoch_ms and args.wait_until_epoch_ms > 0:
        wait_until(args.wait_until_epoch_ms)

    srk_root = Path(args.srk_root).resolve() if args.srk_root else guess_srk_root()
    py = pick_python(srk_root, args.python or None)

    client_path = srk_root / "plugins" / "ric_xapps" / "src" / "zmq_stats_client.py"
    if not client_path.exists():
        sys.stderr.write(f"ERROR: Could not find zmq_stats_client.py at: {client_path}\n")
        sys.stderr.write("Hint: pass --srk-root /path/to/SRK\n")
        return 2

    # Strip leading '--' if present
    client_args: List[str] = list(args.client_args)
    if client_args and client_args[0] == "--":
        client_args = client_args[1:]

    out_f = open_out(args.out)
    out_f.write(f"# start_epoch_ms={epoch_ms()} srk_root={srk_root} python={py}\n")
    out_f.write("ts_epoch_ms\tstream\tline\n")

    cmd = [py, str(client_path)] + client_args

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(srk_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        sys.stderr.write(f"ERROR: Python interpreter not found: {py}\n")
        return 3

    assert proc.stdout is not None

    try:
        for line in proc.stdout:
            ts = epoch_ms()
            out_f.write(f"{ts}\tzmq_stats_client\t{line.rstrip()}\n")
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
