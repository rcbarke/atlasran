#!/usr/bin/env python3
"""post_process_cu_du_ablation.py (optimized)

Post-process CU/DU ablation runs produced by:
  - cu-du-abl/monitor/run_all_monitors.sh
  - cu-du-abl/monitor/uplink_test.sh

It scans one or more run directories under ./runs/ and produces:
  - analysis/ablation_summary.csv
  - analysis/ablation_report.md
  - analysis/iperf_per_ue.csv
  - analysis/ablation_details.json

Design goals:
  - Robust to missing/partial files (common in large UE runs / buffer overflows).
  - Metrics are aligned to the *test window* (inferred from iperf JSON timestamps when possible).
  - LDPC interpretation reflects OAI's MIMD×SIMD CPU implementation:
      * DU log LDPC prints are typically rate-limited samples, not per-decode events.
      * Report wall-clock latency as-logged, plus a CPU core-time proxy that accounts for
        (a) configured thread-pool width and (b) estimated number of code-block segments.
      * When logs appear to provide per-thread/per-task timings (multiple samples in a small time bucket),
        compute core-time proxy by summing within that bucket.
  - Adds a direct harness fidelity KPI: slot-processing rate (slots/sec) derived from DU logs
    ("Frame.Slot F.S"), plus a derived real-time-factor (RTF) against nominal slots/sec.

Typical usage:
  python3 post_process_cu_du_ablation.py

Or explicitly:
  python3 post_process_cu_du_ablation.py \
    --runs-root ./runs \
    --ues-values 0,1,3,6,12 \
    --out-dir ./runs/analysis

CPU-only (skip GPU expectations):
  python3 post_process_cu_du_ablation.py --no-gpu
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_UES_VALUES = [0, 1, 3, 6, 12]
DEFAULT_FALLBACK_TEST_DURATION_S = 60.0

# Files expected within each run directory.
RUN_FILES = [
    "cu_cpu.csv",
    "cu_logs.tsv",
    "du_cpu.csv",
    "du_logs.tsv",
    "system_cpu.csv", 
    "gpu_power.csv",
    "gpu_util.csv",
    "pids.tsv",
    "run_all_monitors.launch.log",
    "run_manifest.json",
    "zmq_stats.tsv",
]
IPERF_DIRNAME = "iperf3"

# DU LDPC timing print pattern.
LDPC_RE = re.compile(
    r"(?:CPU|CUDA)?\s*LDPC\s*decoder:\s*([0-9]+(?:\.[0-9]+)?)\s*us\s*\(\s*([0-9]+(?:\.[0-9]+)?)\s*us\s*/\s*seg\s*\)",
    re.IGNORECASE,
)

# DU slot progress print pattern (example: "Frame.Slot 384.0").
FRAME_SLOT_RE = re.compile(r"\bFrame\.Slot\s+(\d+)\.(\d+)\b")

UE_RNTI_RE = re.compile(r"UE\s+RNTI\s+([0-9a-fA-F]+)\s+CU-UE-ID\s+(\d+)")
ZMQ_PUBLISHED_RE = re.compile(r"Published\s+#(\d+):")
ZMQ_UE_LINE_RE = re.compile(r"\bRNTI:([0-9]+)\b")

ERROR_PATTERNS = {
    "error": re.compile(r"\bERROR\b", re.IGNORECASE),
    "assert": re.compile(r"\bAssertion\b|\bassert\b", re.IGNORECASE),
    "segfault": re.compile(r"Segmentation fault|SIGSEGV", re.IGNORECASE),
    "aborted": re.compile(r"\bAborted\b|\babort\b", re.IGNORECASE),
    "buffer_overflow": re.compile(r"buffer overflow", re.IGNORECASE),
    "failed": re.compile(r"\bfailed\b", re.IGNORECASE),
    "timeout": re.compile(r"timeout", re.IGNORECASE),
}


def epoch_ms_to_iso(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return dt.isoformat()


def safe_float(x: str) -> Optional[float]:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def quantile(values: Sequence[float], q: float) -> Optional[float]:
    """Linear-interpolated quantile in [0, 1]."""
    if not values:
        return None
    if q <= 0:
        return float(min(values))
    if q >= 1:
        return float(max(values))
    xs = sorted(values)
    n = len(xs)
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(xs[lo])
    w = pos - lo
    return float(xs[lo] * (1 - w) + xs[hi] * w)


@dataclass
class NumSummary:
    n: int
    mean: Optional[float]
    p50: Optional[float]
    p95: Optional[float]
    min: Optional[float]
    max: Optional[float]

    def as_dict(self, prefix: str = "") -> Dict[str, Any]:
        p = prefix
        return {
            f"{p}n": self.n,
            f"{p}mean": self.mean,
            f"{p}p50": self.p50,
            f"{p}p95": self.p95,
            f"{p}min": self.min,
            f"{p}max": self.max,
        }


def summarize(values: Sequence[Optional[float]]) -> NumSummary:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return NumSummary(n=0, mean=None, p50=None, p95=None, min=None, max=None)
    return NumSummary(
        n=len(vals),
        mean=float(statistics.fmean(vals)),
        p50=quantile(vals, 0.50),
        p95=quantile(vals, 0.95),
        min=float(min(vals)),
        max=float(max(vals)),
    )


def read_text(path: Path) -> str:
    return path.read_text(errors="replace")


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    """Read CSV while skipping comment lines starting with '#'."""
    lines = read_text(path).splitlines()
    data_lines = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    if not data_lines:
        return []
    reader = csv.DictReader(data_lines)
    return [dict(row) for row in reader]


def read_tsv_rows(path: Path) -> Iterable[Tuple[int, str, str]]:
    """Yield (ts_epoch_ms, stream/container, line) from TSV logs."""
    with path.open("r", errors="replace") as f:
        for ln in f:
            if not ln.strip():
                continue
            if ln.lstrip().startswith("#"):
                continue
            if ln.startswith("ts_epoch_ms"):
                continue
            parts = ln.rstrip("\n").split("\t", 2)
            if len(parts) < 3:
                continue
            ts = safe_float(parts[0])
            if ts is None:
                continue
            yield (int(ts), parts[1], parts[2])


def parse_run_manifest(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(read_text(path))
    except Exception as e:
        return {"_error": f"failed_to_parse_manifest: {e}"}


def parse_pids(path: Path) -> Dict[str, int]:
    res: Dict[str, int] = {}
    if not path.exists():
        return res
    with path.open("r", errors="replace") as f:
        for i, ln in enumerate(f):
            if i == 0 and "name" in ln and "pid" in ln:
                continue
            parts = ln.strip().split("\t")
            if len(parts) != 2:
                continue
            name, pid_s = parts
            pid = safe_float(pid_s)
            if pid is None:
                continue
            res[name] = int(pid)
    return res

def _apply_window_to_rows(
    rows: List[Dict[str, str]],
    start_ms: Optional[int],
    end_ms: Optional[int],
    trim_s: float = 0.0,
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """Filter CSV rows by ts_epoch_ms window; returns (filtered_rows, window_meta)."""
    ts_vals = []
    for r in rows:
        t = safe_float(r.get("ts_epoch_ms", ""))
        if t is not None:
            ts_vals.append(int(t))
    total_duration_s = None
    if ts_vals:
        total_duration_s = (max(ts_vals) - min(ts_vals)) / 1000.0

    if start_ms is None or end_ms is None or start_ms >= end_ms:
        # No usable window; return all rows.
        return rows, {
            "window_used": False,
            "window_start_ms": None,
            "window_end_ms": None,
            "trim_s": trim_s,
            "rows_total": len(rows),
            "rows_used": len(rows),
            "duration_s_total": total_duration_s,
            "duration_s_used": total_duration_s,
        }

    # Apply trim.
    start_eff = int(start_ms + trim_s * 1000.0)
    end_eff = int(end_ms - trim_s * 1000.0)
    if start_eff >= end_eff:
        # Trimming collapsed window; fall back to original window.
        start_eff = int(start_ms)
        end_eff = int(end_ms)

    filtered: List[Dict[str, str]] = []
    used_ts: List[int] = []
    for r in rows:
        t = safe_float(r.get("ts_epoch_ms", ""))
        if t is None:
            continue
        t_i = int(t)
        if start_eff <= t_i <= end_eff:
            filtered.append(r)
            used_ts.append(t_i)

    used_duration_s = None
    if used_ts:
        used_duration_s = (max(used_ts) - min(used_ts)) / 1000.0

    return filtered, {
        "window_used": True,
        "window_start_ms": int(start_ms),
        "window_end_ms": int(end_ms),
        "window_start_eff_ms": int(start_eff),
        "window_end_eff_ms": int(end_eff),
        "trim_s": float(trim_s),
        "rows_total": len(rows),
        "rows_used": len(filtered),
        "duration_s_total": total_duration_s,
        "duration_s_used": used_duration_s,
    }


def parse_cpu_csv(path: Path, window: Optional[Tuple[int, int]] = None, trim_s: float = 0.0) -> Dict[str, Any]:
    rows = read_csv_rows(path)
    start_ms, end_ms = window if window else (None, None)
    rows_used, meta = _apply_window_to_rows(rows, start_ms, end_ms, trim_s=trim_s)

    cpu = []
    mem = []
    ts = []
    pids = []
    for r in rows_used:
        ts_v = safe_float(r.get("ts_epoch_ms", ""))
        if ts_v is not None:
            ts.append(ts_v)
        cpu_v = safe_float(r.get("cpu_percent", ""))
        mem_v = safe_float(r.get("mem_percent", ""))
        if cpu_v is not None:
            cpu.append(cpu_v)
        if mem_v is not None:
            mem.append(mem_v)
        p = safe_float(r.get("pids", ""))
        if p is not None:
            pids.append(p)

    duration_s = None
    if ts:
        duration_s = (max(ts) - min(ts)) / 1000.0

    return {
        "path": str(path),
        **meta,
        "duration_s": duration_s,
        "cpu": summarize(cpu).as_dict("cpu_"),
        "mem": summarize(mem).as_dict("mem_"),
        "pids": summarize(pids).as_dict("pids_"),
    }

def parse_system_cpu_csv(path: Path, window: Optional[Tuple[int, int]] = None, trim_s: float = 0.0) -> Dict[str, Any]:
    """
    Parse system_cpu.csv emitted by 08_cpu_monitor_system.py.

    Expected columns:
      ts_epoch_ms,cpu_total_pct,cpu_user_pct,cpu_system_pct,cpu_iowait_pct,cpu_idle_pct,...

    Returns summaries for total/user/system/iowait/idle CPU percentages.
    """
    rows = read_csv_rows(path)
    start_ms, end_ms = window if window else (None, None)
    rows_used, meta = _apply_window_to_rows(rows, start_ms, end_ms, trim_s=trim_s)

    ts = []
    total = []
    user = []
    system = []
    iowait = []
    idle = []

    for r in rows_used:
        ts_v = safe_float(r.get("ts_epoch_ms", ""))
        if ts_v is not None:
            ts.append(ts_v)

        v = safe_float(r.get("cpu_total_pct", ""))
        if v is not None:
            total.append(v)

        v = safe_float(r.get("cpu_user_pct", ""))
        if v is not None:
            user.append(v)

        v = safe_float(r.get("cpu_system_pct", ""))
        if v is not None:
            system.append(v)

        v = safe_float(r.get("cpu_iowait_pct", ""))
        if v is not None:
            iowait.append(v)

        v = safe_float(r.get("cpu_idle_pct", ""))
        if v is not None:
            idle.append(v)

    duration_s = None
    if ts:
        duration_s = (max(ts) - min(ts)) / 1000.0

    return {
        "path": str(path),
        **meta,
        "duration_s": duration_s,
        "cpu_total": summarize(total).as_dict("cpu_total_"),
        "cpu_user": summarize(user).as_dict("cpu_user_"),
        "cpu_system": summarize(system).as_dict("cpu_system_"),
        "cpu_iowait": summarize(iowait).as_dict("cpu_iowait_"),
        "cpu_idle": summarize(idle).as_dict("cpu_idle_"),
    }

def parse_gpu_util_csv(path: Path, window: Optional[Tuple[int, int]] = None, trim_s: float = 0.0) -> Dict[str, Any]:
    rows = read_csv_rows(path)
    start_ms, end_ms = window if window else (None, None)
    rows_used, meta = _apply_window_to_rows(rows, start_ms, end_ms, trim_s=trim_s)

    util_gpu = []
    util_mem = []
    ts = []
    by_gpu: Dict[str, Dict[str, List[float]]] = {}
    for r in rows_used:
        ts_v = safe_float(r.get("ts_epoch_ms", ""))
        if ts_v is not None:
            ts.append(ts_v)
        idx = (r.get("gpu_index", "") or "0").strip()
        ug = safe_float(r.get("util_gpu_pct", ""))
        um = safe_float(r.get("util_mem_pct", ""))
        if ug is not None:
            util_gpu.append(ug)
        if um is not None:
            util_mem.append(um)
        if idx not in by_gpu:
            by_gpu[idx] = {"util_gpu": [], "util_mem": []}
        if ug is not None:
            by_gpu[idx]["util_gpu"].append(ug)
        if um is not None:
            by_gpu[idx]["util_mem"].append(um)

    duration_s = None
    if ts:
        duration_s = (max(ts) - min(ts)) / 1000.0

    by_gpu_stats = {
        idx: {
            **summarize(v["util_gpu"]).as_dict("util_gpu_"),
            **summarize(v["util_mem"]).as_dict("util_mem_"),
        }
        for idx, v in by_gpu.items()
    }

    return {
        "path": str(path),
        **meta,
        "duration_s": duration_s,
        "all": {
            **summarize(util_gpu).as_dict("util_gpu_"),
            **summarize(util_mem).as_dict("util_mem_"),
        },
        "by_gpu": by_gpu_stats,
    }


def parse_gpu_power_csv(path: Path, window: Optional[Tuple[int, int]] = None, trim_s: float = 0.0) -> Dict[str, Any]:
    rows = read_csv_rows(path)
    start_ms, end_ms = window if window else (None, None)
    rows_used, meta = _apply_window_to_rows(rows, start_ms, end_ms, trim_s=trim_s)

    pwr = []
    temp = []
    ts = []
    by_gpu: Dict[str, Dict[str, List[float]]] = {}
    for r in rows_used:
        ts_v = safe_float(r.get("ts_epoch_ms", ""))
        if ts_v is not None:
            ts.append(ts_v)
        idx = (r.get("gpu_index", "") or "0").strip()
        pd = safe_float(r.get("power_draw_w", ""))
        tg = safe_float(r.get("temp_gpu_c", ""))
        if pd is not None:
            pwr.append(pd)
        if tg is not None:
            temp.append(tg)
        if idx not in by_gpu:
            by_gpu[idx] = {"power_draw": [], "temp": []}
        if pd is not None:
            by_gpu[idx]["power_draw"].append(pd)
        if tg is not None:
            by_gpu[idx]["temp"].append(tg)

    duration_s = None
    if ts:
        duration_s = (max(ts) - min(ts)) / 1000.0

    by_gpu_stats = {
        idx: {
            **summarize(v["power_draw"]).as_dict("power_w_"),
            **summarize(v["temp"]).as_dict("temp_c_"),
        }
        for idx, v in by_gpu.items()
    }

    return {
        "path": str(path),
        **meta,
        "duration_s": duration_s,
        "all": {
            **summarize(pwr).as_dict("power_w_"),
            **summarize(temp).as_dict("temp_c_"),
        },
        "by_gpu": by_gpu_stats,
    }


def parse_text_log_for_errors(text: str, max_examples: int = 10) -> Dict[str, Any]:
    counts = {k: 0 for k in ERROR_PATTERNS}
    examples: Dict[str, List[str]] = {k: [] for k in ERROR_PATTERNS}

    for ln in text.splitlines():
        for k, rx in ERROR_PATTERNS.items():
            if rx.search(ln):
                counts[k] += 1
                if len(examples[k]) < max_examples:
                    examples[k].append(ln[:500])

    return {"counts": counts, "examples": examples}


def _guess_slots_per_frame(max_slot_seen: int) -> int:
    """
    Guess slots_per_frame from observed slot indices.
    In NR: slots_per_frame = 10 * 2^mu, so values are 10, 20, 40, 80, 160, ...
    """
    if max_slot_seen < 0:
        return 10
    need = max_slot_seen + 1
    candidates = [10 * (2**mu) for mu in range(0, 8)]  # up to 1280
    for c in candidates:
        if c >= need:
            return c
    return candidates[-1]


def _compute_slot_rate(
    frame_slot_samples: List[Tuple[int, int, int]],
    frame_wrap: int,
    slots_per_frame: int,
) -> Dict[str, Any]:
    """
    Compute slots/sec from a list of (ts_ms, frame, slot) samples.
    Handles SFN wrap by enforcing a non-decreasing unwrapped slot index.
    """
    if len(frame_slot_samples) < 2:
        return {
            "samples_n": len(frame_slot_samples),
            "slots_per_frame": slots_per_frame,
            "frame_wrap": frame_wrap,
            "slot_rate_sps": summarize([]).as_dict("sps_"),
            "real_time_factor": None,
        }

    samples = sorted(frame_slot_samples, key=lambda x: x[0])
    cycle = frame_wrap * slots_per_frame

    unwrapped_idxs: List[int] = []
    prev_idx: Optional[int] = None
    for ts, frame, slot in samples:
        idx = int(frame) * int(slots_per_frame) + int(slot)
        # unwrap: ensure strictly non-decreasing, adding cycles as needed
        if prev_idx is not None and idx <= prev_idx:
            # add enough cycles to get above prev_idx
            delta = prev_idx - idx + 1
            k = int(math.ceil(delta / cycle))
            idx += k * cycle
        unwrapped_idxs.append(idx)
        prev_idx = idx

    t0, t1 = samples[0][0], samples[-1][0]
    dur_s = (t1 - t0) / 1000.0 if t1 > t0 else None
    slot_delta = unwrapped_idxs[-1] - unwrapped_idxs[0]

    # Per-interval rates for distribution.
    rates: List[float] = []
    for i in range(1, len(samples)):
        dt_s = (samples[i][0] - samples[i - 1][0]) / 1000.0
        if dt_s <= 0:
            continue
        ds = unwrapped_idxs[i] - unwrapped_idxs[i - 1]
        if ds < 0:
            continue
        rates.append(ds / dt_s)

    nominal_slots_per_s = 100.0 * float(slots_per_frame)  # 100 frames/sec (10ms frames)
    mean_rate = (slot_delta / dur_s) if (dur_s and dur_s > 0) else None
    rtf = (mean_rate / nominal_slots_per_s) if (mean_rate is not None and nominal_slots_per_s > 0) else None

    return {
        "samples_n": len(samples),
        "slots_per_frame": slots_per_frame,
        "frame_wrap": frame_wrap,
        "t0_ms": t0,
        "t1_ms": t1,
        "duration_s": dur_s,
        "slot_delta": slot_delta,
        "slot_rate_sps": summarize(rates).as_dict("sps_"),
        "slot_rate_mean_sps": mean_rate,
        "nominal_slots_per_s": nominal_slots_per_s,
        "real_time_factor": rtf,
    }


def parse_du_logs(
    path: Path,
    *,
    window: Optional[Tuple[int, int]] = None,
    ldpc_bucket_ms: int = 5,
    cpu_ldpc_threads: int = 4,
    cuda_ldpc_threads: int = 1,
    slots_per_frame_override: Optional[int] = None,
    frame_wrap: int = 1024,
) -> Dict[str, Any]:
    """
    Parse DU logs: LDPC decode timing + UE IDs + error patterns + slot-rate estimate.

    Important semantics:
      - LDPC prints are typically *rate-limited samples* (e.g., ~1 Hz), not per-slot or per-TB events.
        We therefore expose LDPC sample rate as `ldpc_samples_per_s` (not “events/s”).
      - `ldpc_wall_*` is the distribution of as-logged LDPC wall time (per printed sample).
      - `ldpc_core_time_proxy_*` is a CPU core-time proxy for the decode region:
          * If multiple LDPC samples appear in the same small time bucket, we sum within each bucket.
          * Otherwise, we scale by an effective parallelism estimate:
                eff_par = min(configured_threads, estimated_segments)
            where estimated_segments ≈ (wall_us / us_per_seg) when available.
    """
    # Window bounds
    w0, w1 = window if window else (None, None)

    ldpc_samples: List[Dict[str, Any]] = []
    frame_slot_samples: List[Tuple[int, int, int]] = []  # (ts_ms, frame, slot)

    ts_first: Optional[int] = None
    ts_last: Optional[int] = None
    n_lines = 0

    ue_ids: set[int] = set()
    rntis: set[str] = set()
    error_counts = {k: 0 for k in ERROR_PATTERNS}

    with path.open("r", errors="replace") as f:
        for ln in f:
            if not ln.strip():
                continue
            if ln.lstrip().startswith("#"):
                continue
            if ln.startswith("ts_epoch_ms"):
                continue
            parts = ln.rstrip("\n").split("\t", 2)
            if len(parts) < 3:
                continue
            ts = safe_float(parts[0])
            if ts is None:
                continue
            ts_i = int(ts)

            # Apply test window filter if provided.
            if w0 is not None and w1 is not None and not (w0 <= ts_i <= w1):
                continue

            n_lines += 1

            if ts_first is None or ts_i < ts_first:
                ts_first = ts_i
            if ts_last is None or ts_i > ts_last:
                ts_last = ts_i

            msg = parts[2]

            # LDPC timing
            m = LDPC_RE.search(msg)
            if m:
                wall_us = safe_float(m.group(1))
                us_per_seg = safe_float(m.group(2))
                if wall_us is not None:
                    msg_l = msg.lower()
                    if "cuda ldpc" in msg_l:
                        impl = "cuda"
                    elif "cpu ldpc" in msg_l:
                        impl = "cpu"
                    else:
                        impl = "unknown"

                    seg_est = None
                    if us_per_seg is not None and us_per_seg > 0:
                        seg_est = float(wall_us) / float(us_per_seg)
                        # Guard against nonsense from partial logs.
                        if not (0.0 < seg_est < 1e6):
                            seg_est = None

                    ldpc_samples.append(
                        {
                            "ts_ms": ts_i,
                            "impl": impl,
                            "wall_us": float(wall_us),
                            "us_per_seg": float(us_per_seg) if us_per_seg is not None else None,
                            "segments_est": seg_est,
                        }
                    )

            # Slot rate samples
            mfs = FRAME_SLOT_RE.search(msg)
            if mfs:
                try:
                    frame = int(mfs.group(1))
                    slot = int(mfs.group(2))
                    frame_slot_samples.append((ts_i, frame, slot))
                except Exception:
                    pass

            # UE info
            m2 = UE_RNTI_RE.search(msg)
            if m2:
                rntis.add(m2.group(1))
                ue_id = safe_float(m2.group(2))
                if ue_id is not None:
                    ue_ids.add(int(ue_id))

            # Error patterns
            for k, rx in ERROR_PATTERNS.items():
                if rx.search(msg):
                    error_counts[k] += 1

    duration_s = None
    if ts_first is not None and ts_last is not None:
        duration_s = (ts_last - ts_first) / 1000.0

    # Implementation classification
    impl = "unknown"
    if ldpc_samples:
        cpu_n = sum(1 for s in ldpc_samples if s["impl"] == "cpu")
        cuda_n = sum(1 for s in ldpc_samples if s["impl"] == "cuda")
        if cpu_n > 0 and cuda_n == 0:
            impl = "cpu"
        elif cuda_n > 0 and cpu_n == 0:
            impl = "cuda"
        elif cpu_n > 0 and cuda_n > 0:
            impl = "mixed"

    # Thread parallelism used for scaling when needed
    threads_cfg: Optional[int] = None
    if impl == "cpu":
        threads_cfg = max(1, int(cpu_ldpc_threads))
    elif impl == "cuda":
        threads_cfg = max(1, int(cuda_ldpc_threads))

    # LDPC wall distributions
    wall_us_list = [s["wall_us"] for s in ldpc_samples]
    us_per_seg_list = [s["us_per_seg"] for s in ldpc_samples if s.get("us_per_seg") is not None]
    segments_est_list = [s["segments_est"] for s in ldpc_samples if s.get("segments_est") is not None]

    ldpc_samples_per_s = None
    if duration_s and duration_s > 0:
        ldpc_samples_per_s = len(ldpc_samples) / duration_s

    # Group LDPC samples into small time buckets to detect per-thread/per-task logging
    bucket_ms = max(1, int(ldpc_bucket_ms))
    by_bucket: Dict[int, List[Dict[str, Any]]] = {}
    for s in ldpc_samples:
        b = int(s["ts_ms"]) // bucket_ms
        by_bucket.setdefault(b, []).append(s)
    group_sizes = [len(v) for v in by_bucket.values()]
    has_multi_in_bucket = any(sz > 1 for sz in group_sizes)

    # Core-time proxy computation
    core_proxy_us: List[float] = []
    core_proxy_method = "none"

    if has_multi_in_bucket:
        # Sum within bucket: treat each LDPC line as a work-item on a worker.
        core_proxy_method = f"bucket_sum_{bucket_ms}ms"
        core_proxy_us = [float(sum(s["wall_us"] for s in group)) for group in by_bucket.values()]
    else:
        # Scale wall time by effective parallelism estimate
        core_proxy_method = "eff_parallelism_scaling"
        if threads_cfg is not None:
            for s in ldpc_samples:
                seg_est = s.get("segments_est")
                if isinstance(seg_est, (int, float)) and seg_est > 0:
                    eff_par = min(float(threads_cfg), float(seg_est))
                    eff_par = max(1.0, eff_par)
                else:
                    eff_par = float(threads_cfg)
                core_proxy_us.append(float(s["wall_us"]) * eff_par)

    # Also expose effective parallelism estimates (for CPU mostly)
    eff_par_list: List[float] = []
    if threads_cfg is not None:
        for s in ldpc_samples:
            seg_est = s.get("segments_est")
            if isinstance(seg_est, (int, float)) and seg_est > 0:
                eff_par = min(float(threads_cfg), float(seg_est))
                eff_par = max(1.0, eff_par)
            else:
                eff_par = float(threads_cfg)
            eff_par_list.append(eff_par)

    # Slot rate / time dilation
    slots_per_frame = int(slots_per_frame_override) if isinstance(slots_per_frame_override, int) and slots_per_frame_override > 0 else None
    if slots_per_frame is None:
        max_slot = max((slot for _, _, slot in frame_slot_samples), default=-1)
        slots_per_frame = _guess_slots_per_frame(max_slot)

    slot_rate = _compute_slot_rate(frame_slot_samples, frame_wrap=frame_wrap, slots_per_frame=slots_per_frame)

    return {
        "path": str(path),
        "window_start_ms": w0,
        "window_end_ms": w1,
        "duration_s": duration_s,
        "lines": n_lines,
        "ue_ids_count": len(ue_ids),
        "ue_ids": sorted(ue_ids)[:50],  # cap for readability
        "rnti_count": len(rntis),
        "ldpc_impl": impl,
        "ldpc_threads_cfg": threads_cfg,
        "ldpc_bucket_ms": bucket_ms,
        "ldpc_group_sizes": summarize(group_sizes).as_dict("threads_") if group_sizes else None,
        "ldpc_wall_decode_us": summarize(wall_us_list).as_dict("wall_"),
        "ldpc_us_per_seg": summarize(us_per_seg_list).as_dict("perseg_"),
        "ldpc_segments_est": summarize(segments_est_list).as_dict("segs_"),
        "ldpc_eff_parallelism_est": summarize(eff_par_list).as_dict("effpar_"),
        "ldpc_samples_per_s": ldpc_samples_per_s,
        "ldpc_core_time_proxy_us": summarize(core_proxy_us).as_dict("core_"),
        "ldpc_core_time_proxy_method": core_proxy_method,
        "error_counts": error_counts,
        "slot_rate": slot_rate,
    }


def parse_generic_tsv_log(path: Path, window: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
    """Parse TSV logs for line counts + error pattern summary, optionally windowed."""
    w0, w1 = window if window else (None, None)

    n_lines = 0
    ts_first: Optional[int] = None
    ts_last: Optional[int] = None
    error_counts = {k: 0 for k in ERROR_PATTERNS}
    examples: Dict[str, List[str]] = {k: [] for k in ERROR_PATTERNS}

    for ts, _, msg in read_tsv_rows(path):
        if w0 is not None and w1 is not None and not (w0 <= ts <= w1):
            continue
        n_lines += 1
        if ts_first is None or ts < ts_first:
            ts_first = ts
        if ts_last is None or ts > ts_last:
            ts_last = ts

        for k, rx in ERROR_PATTERNS.items():
            if rx.search(msg):
                error_counts[k] += 1
                if len(examples[k]) < 5:
                    examples[k].append(msg[:500])

    duration_s = None
    if ts_first is not None and ts_last is not None:
        duration_s = (ts_last - ts_first) / 1000.0

    return {
        "path": str(path),
        "window_start_ms": w0,
        "window_end_ms": w1,
        "lines": n_lines,
        "duration_s": duration_s,
        "error_counts": error_counts,
        "error_examples": examples,
    }


def parse_zmq_stats(path: Path, window: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
    """Lightweight ZMQ stats parsing (may be partial/blank), optionally windowed."""
    w0, w1 = window if window else (None, None)

    n_lines = 0
    published_lines = 0
    ue_lines = 0
    unique_rnti: set[str] = set()
    parse_errors = 0

    ts_first: Optional[int] = None
    ts_last: Optional[int] = None

    pub_first: Optional[int] = None
    pub_last: Optional[int] = None
    pub_min: Optional[int] = None
    pub_max: Optional[int] = None

    # We avoid reading the whole file unless needed.
    usage_err = False

    with path.open("r", errors="replace") as f:
        for ln in f:
            if not ln.strip():
                continue
            if ln.lstrip().startswith("#"):
                continue
            if ln.startswith("ts_epoch_ms"):
                continue
            parts = ln.rstrip("\n").split("\t", 2)
            if len(parts) < 3:
                continue
            ts = safe_float(parts[0])
            if ts is None:
                continue
            ts_i = int(ts)

            if w0 is not None and w1 is not None and not (w0 <= ts_i <= w1):
                continue

            n_lines += 1
            if ts_first is None or ts_i < ts_first:
                ts_first = ts_i
            if ts_last is None or ts_i > ts_last:
                ts_last = ts_i

            msg = parts[2]
            if "unrecognized arguments" in msg or "usage:" in msg.lower():
                usage_err = True

            m = ZMQ_PUBLISHED_RE.search(msg)
            if m:
                published_lines += 1
                try:
                    c = int(m.group(1))
                    pub_min = c if pub_min is None else min(pub_min, c)
                    pub_max = c if pub_max is None else max(pub_max, c)
                    if pub_first is None:
                        pub_first = c
                    pub_last = c
                except Exception:
                    parse_errors += 1

            if "RNTI:" in msg:
                ue_lines += 1
                m2 = ZMQ_UE_LINE_RE.search(msg)
                if m2:
                    unique_rnti.add(m2.group(1))

    duration_s = None
    if ts_first is not None and ts_last is not None and ts_last > ts_first:
        duration_s = (ts_last - ts_first) / 1000.0

    pub_counter_delta = None
    pub_counter_rate = None
    if pub_first is not None and pub_last is not None:
        pub_counter_delta = pub_last - pub_first
        if duration_s and duration_s > 0:
            pub_counter_rate = pub_counter_delta / duration_s

    pub_line_rate = None
    if duration_s and duration_s > 0:
        pub_line_rate = published_lines / duration_s

    return {
        "path": str(path),
        "window_start_ms": w0,
        "window_end_ms": w1,
        "lines": n_lines,
        "duration_s": duration_s,
        "published_lines": published_lines,
        "published_line_rate_sps": pub_line_rate,
        "published_counter_first": pub_first,
        "published_counter_last": pub_last,
        "published_counter_min": pub_min,
        "published_counter_max": pub_max,
        "published_counter_delta": pub_counter_delta,
        "published_counter_rate_sps": pub_counter_rate,
        "ue_lines": ue_lines,
        "unique_rnti_count": len(unique_rnti),
        "usage_error": usage_err,
        "parse_errors": parse_errors,
    }


def parse_iperf_json(path: Path) -> Dict[str, Any]:
    """Parse iperf3 JSON, handling 'WARNING:' prefix and missing end blocks."""
    txt = read_text(path)
    idx = txt.find("{")
    warning_prefix = None
    if idx > 0:
        prefix = txt[:idx].strip()
        if prefix:
            warning_prefix = prefix[:300]

    if idx < 0:
        return {"path": str(path), "parse_ok": False, "error": "no_json_object_found"}

    dec = json.JSONDecoder()
    try:
        obj, _ = dec.raw_decode(txt[idx:])
    except Exception as e:
        return {
            "path": str(path),
            "parse_ok": False,
            "error": f"json_decode_failed: {e}",
            "warning_prefix": warning_prefix,
        }

    start = obj.get("start", {}) or {}
    end = obj.get("end", {}) or {}
    intervals = obj.get("intervals", []) or []

    # Extract protocol and flags
    test_start = start.get("test_start", {}) or {}
    protocol = test_start.get("protocol")
    reverse = test_start.get("reverse")
    duration = test_start.get("duration")

    # Timestamp
    ts_secs = None
    try:
        ts_secs = int(start.get("timestamp", {}).get("timesecs"))
    except Exception:
        ts_secs = None

    # Per-interval throughput (bits/sec)
    bps_series: List[float] = []
    for it in intervals:
        if not isinstance(it, dict):
            continue
        if "sum" in it and isinstance(it["sum"], dict) and "bits_per_second" in it["sum"]:
            v = it["sum"].get("bits_per_second")
            if isinstance(v, (int, float)):
                bps_series.append(float(v))
            continue
        if "streams" in it and isinstance(it["streams"], list):
            s = 0.0
            ok = False
            for st in it["streams"]:
                if isinstance(st, dict) and isinstance(st.get("bits_per_second"), (int, float)):
                    s += float(st["bits_per_second"])
                    ok = True
            if ok:
                bps_series.append(s)

    bps_summary = summarize(bps_series)

    end_present = bool(end) and isinstance(end, dict) and ("sum_received" in end or "sum_sent" in end)

    end_sum_received = (end.get("sum_received") or {}) if isinstance(end, dict) else {}
    end_sum_sent = (end.get("sum_sent") or {}) if isinstance(end, dict) else {}

    end_bps_received = None
    end_bps_sent = None
    end_bytes_received = None
    end_bytes_sent = None
    end_retrans = None

    if isinstance(end_sum_received, dict):
        v = end_sum_received.get("bits_per_second")
        if isinstance(v, (int, float)):
            end_bps_received = float(v)
        b = end_sum_received.get("bytes")
        if isinstance(b, (int, float)):
            end_bytes_received = float(b)

    if isinstance(end_sum_sent, dict):
        v = end_sum_sent.get("bits_per_second")
        if isinstance(v, (int, float)):
            end_bps_sent = float(v)
        b = end_sum_sent.get("bytes")
        if isinstance(b, (int, float)):
            end_bytes_sent = float(b)
        r = end_sum_sent.get("retransmits")
        if isinstance(r, (int, float)):
            end_retrans = int(r)

    # Choose throughput metric:
    # Prefer an end-of-test metric when present. To be robust against "client vs server JSON"
    # and reverse-mode confusion, choose the max of (sum_received, sum_sent) if available.
    candidates = [x for x in (end_bps_received, end_bps_sent) if isinstance(x, (int, float))]
    end_bps = max(candidates) if candidates else None
    chosen_bps = end_bps if end_bps is not None else bps_summary.mean

    # iperf stderr (if present)
    stderr_path = path.with_suffix(path.suffix + ".stderr.log")
    stderr_text = None
    if stderr_path.exists():
        stderr_text = read_text(stderr_path).strip()[:5000]

    stderr_has_error = False
    if stderr_text:
        stderr_has_error = "error" in stderr_text.lower()

    return {
        "path": str(path),
        "parse_ok": True,
        "warning_prefix": warning_prefix,
        "has_warning_prefix": bool(warning_prefix),
        "protocol": protocol,
        "reverse": bool(reverse) if isinstance(reverse, bool) else reverse,
        "duration_s": duration,
        "start_timesecs": ts_secs,
        "intervals_n": len(bps_series),
        "end_present": end_present,
        "end_bps_received": end_bps_received,
        "end_bps_sent": end_bps_sent,
        "end_bps": end_bps,
        "chosen_bps": chosen_bps,
        "bps": bps_summary.as_dict("bps_"),
        "end_bytes_received": end_bytes_received,
        "end_bytes_sent": end_bytes_sent,
        "retransmits": end_retrans,
        "stderr_path": str(stderr_path) if stderr_path.exists() else None,
        "stderr_has_error": stderr_has_error,
        "stderr_excerpt": stderr_text,
    }


def jains_fairness(xs: Sequence[Optional[float]]) -> Optional[float]:
    """Jain's fairness index over a fixed set of UEs; zeros are included, None is treated as missing."""
    vals = [float(x) for x in xs if x is not None]
    if not vals:
        return None
    s1 = sum(vals)
    s2 = sum(v * v for v in vals)
    n = len(vals)
    if s2 == 0:
        return None
    return (s1 * s1) / (n * s2)


def infer_ue_count_from_dirname(run_dir: Path) -> Optional[int]:
    m = re.search(r"_ues(\d+)$", run_dir.name)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def _extract_ue_idx_from_filename(p: Path) -> Optional[int]:
    """
    Extract UE index from iperf JSON filename.

    Supports:
      - ..._ue3_....json
      - ..._ue3.json
      - ...ue3....json
    """
    # Prefer explicit "_ue{d}" token, allowing end-of-string or non-digit delimiter.
    m = re.search(r"(?:^|[_\-])ue(\d+)(?:$|[_\-\.])", p.stem)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None

    # Fallback: any "ue{d}" token in the stem.
    m = re.search(r"\bue(\d+)\b", p.stem)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def infer_test_window_ms(
    *,
    run_manifest: Optional[Dict[str, Any]],
    iperf_records: Sequence[Dict[str, Any]],
    expected_duration_s: float,
) -> Dict[str, Any]:
    """
    Infer test window [start_ms, end_ms] using best available signals:
      1) iperf per-UE start timestamps + durations
      2) run_manifest start_epoch_ms + expected_duration_s
    """
    starts_ms: List[int] = []
    ends_ms: List[int] = []

    durations_s: List[float] = []
    for r in iperf_records:
        if not r.get("parse_ok"):
            continue
        ts_secs = r.get("start_timesecs")
        if not isinstance(ts_secs, int):
            continue
        starts_ms.append(int(ts_secs) * 1000)
        dur = r.get("duration_s")
        if isinstance(dur, (int, float)) and dur > 0:
            durations_s.append(float(dur))
            ends_ms.append(int((ts_secs + float(dur)) * 1000))

    if starts_ms:
        start = min(starts_ms)
        # If we have any end estimates, use them; otherwise use expected_duration_s.
        if ends_ms:
            end = max(ends_ms)
        else:
            # Use median duration if present; else fallback to expected.
            dur_use = statistics.median(durations_s) if durations_s else float(expected_duration_s)
            end = int(start + dur_use * 1000)
        return {"start_ms": start, "end_ms": end, "source": "iperf"}

    # Manifest fallback
    if run_manifest and isinstance(run_manifest, dict):
        s = run_manifest.get("start_epoch_ms")
        if isinstance(s, (int, float)):
            start = int(s)
            end = int(start + float(expected_duration_s) * 1000)
            return {"start_ms": start, "end_ms": end, "source": "manifest_start+fallback_duration"}

    return {"start_ms": None, "end_ms": None, "source": "none"}


def pick_runs_by_ues(runs_root: Path, ues_values: List[int]) -> List[Path]:
    """
    For each UE count, pick the run with the latest run_manifest.start_epoch_ms.
    Falls back to lexicographic order if manifest timestamps are missing.
    """
    chosen: List[Path] = []
    for u in ues_values:
        matches = [p for p in runs_root.iterdir() if p.is_dir() and p.name.endswith(f"_ues{u}")]
        if not matches:
            continue

        best: Optional[Path] = None
        best_start: Optional[int] = None

        for p in matches:
            man_path = p / "run_manifest.json"
            start = None
            if man_path.exists():
                man = parse_run_manifest(man_path)
                s = man.get("start_epoch_ms") if isinstance(man, dict) else None
                if isinstance(s, (int, float)):
                    start = int(s)

            if best is None:
                best = p
                best_start = start
                continue

            # Prefer higher start_epoch_ms; if missing, fallback to name ordering.
            if start is not None and (best_start is None or start > best_start):
                best = p
                best_start = start
            elif start is None and best_start is None:
                if p.name > best.name:
                    best = p
                    best_start = best_start

        chosen.append(best if best is not None else matches[-1])
    return chosen


def parse_run(
    run_dir: Path,
    *,
    no_gpu: bool,
    cpu_ldpc_threads: int,
    cuda_ldpc_threads: int,
    ldpc_bucket_ms: int,
    trim_seconds: float,
    expected_test_duration_s: float,
    slots_per_frame_override: Optional[int],
    frame_wrap: int,
) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "run_dir": str(run_dir),
        "run_name": run_dir.name,
        "ue_count": infer_ue_count_from_dirname(run_dir),
        "files_present": {},
        "missing_files": [],
    }

    # File presence map
    for fn in RUN_FILES:
        p = run_dir / fn
        if no_gpu and fn in ("gpu_power.csv", "gpu_util.csv"):
            res["files_present"][fn] = False
            continue
        if p.exists():
            res["files_present"][fn] = True
        else:
            res["files_present"][fn] = False
            res["missing_files"].append(fn)

    # Manifest
    manifest_path = run_dir / "run_manifest.json"
    res["manifest"] = parse_run_manifest(manifest_path) if manifest_path.exists() else None

    # PIDs
    pids_path = run_dir / "pids.tsv"
    res["pids"] = parse_pids(pids_path) if pids_path.exists() else {}

    # iperf3 (parse first to infer test window)
    iperf_dir = run_dir / IPERF_DIRNAME
    iperf_files = sorted(iperf_dir.glob("*.json")) if (iperf_dir.exists() and iperf_dir.is_dir()) else []
    iperf_recs = []
    for p in iperf_files:
        rec = parse_iperf_json(p)
        rec["ue_idx"] = _extract_ue_idx_from_filename(p)
        iperf_recs.append(rec)

    res["iperf"] = {"dir": str(iperf_dir), "files": [r["path"] for r in iperf_recs], "records": iperf_recs}

    # Infer test window
    win = infer_test_window_ms(run_manifest=res["manifest"], iperf_records=iperf_recs, expected_duration_s=expected_test_duration_s)
    start_ms, end_ms = win.get("start_ms"), win.get("end_ms")
    window = (int(start_ms), int(end_ms)) if isinstance(start_ms, int) and isinstance(end_ms, int) and start_ms < end_ms else None
    res["test_window"] = {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "duration_s": ((end_ms - start_ms) / 1000.0) if isinstance(start_ms, int) and isinstance(end_ms, int) else None,
        "source": win.get("source"),
        "trim_s": float(trim_seconds),
    }

    # CPU/GPU metrics aligned to test window (with trim)
    cu_cpu_path = run_dir / "cu_cpu.csv"
    du_cpu_path = run_dir / "du_cpu.csv"
    system_cpu_path = run_dir / "system_cpu.csv" 

    res["cu_cpu"] = parse_cpu_csv(cu_cpu_path, window=window, trim_s=trim_seconds) if cu_cpu_path.exists() else None
    res["du_cpu"] = parse_cpu_csv(du_cpu_path, window=window, trim_s=trim_seconds) if du_cpu_path.exists() else None
    res["system_cpu"] = ( parse_system_cpu_csv(system_cpu_path, window=window, trim_s=trim_seconds) if system_cpu_path.exists() else None )

    if not no_gpu:
        gpu_util_path = run_dir / "gpu_util.csv"
        gpu_power_path = run_dir / "gpu_power.csv"
        res["gpu_util"] = parse_gpu_util_csv(gpu_util_path, window=window, trim_s=trim_seconds) if gpu_util_path.exists() else None
        res["gpu_power"] = parse_gpu_power_csv(gpu_power_path, window=window, trim_s=trim_seconds) if gpu_power_path.exists() else None
    else:
        res["gpu_util"] = None
        res["gpu_power"] = None

    # Logs (also windowed)
    cu_logs_path = run_dir / "cu_logs.tsv"
    du_logs_path = run_dir / "du_logs.tsv"
    res["cu_logs"] = parse_generic_tsv_log(cu_logs_path, window=window) if cu_logs_path.exists() else None
    res["du_logs"] = (
        parse_du_logs(
            du_logs_path,
            window=window,
            ldpc_bucket_ms=ldpc_bucket_ms,
            cpu_ldpc_threads=cpu_ldpc_threads,
            cuda_ldpc_threads=cuda_ldpc_threads,
            slots_per_frame_override=slots_per_frame_override,
            frame_wrap=frame_wrap,
        )
        if du_logs_path.exists()
        else None
    )

    # ZMQ stats (windowed)
    zmq_path = run_dir / "zmq_stats.tsv"
    res["zmq_stats"] = parse_zmq_stats(zmq_path, window=window) if zmq_path.exists() else None

    # Monitor launch log (text; not windowed)
    launch_log_path = run_dir / "run_all_monitors.launch.log"
    if launch_log_path.exists():
        txt = read_text(launch_log_path)
        res["run_all_monitors_log"] = {
            "path": str(launch_log_path),
            "bytes": len(txt.encode("utf-8", errors="ignore")),
            **parse_text_log_for_errors(txt),
        }
    else:
        res["run_all_monitors_log"] = None

    # Aggregate iperf metrics per run (include zeros for missing expected UEs)
    expected_ues = res.get("ue_count")
    if not isinstance(expected_ues, int) or expected_ues < 0:
        expected_ues = None

    # Build per-UE throughput array
    ue_mbps: List[float] = []
    if expected_ues and expected_ues > 0:
        ue_mbps = [0.0 for _ in range(expected_ues)]
        has_any_idx = any(isinstance(r.get("ue_idx"), int) for r in iperf_recs)
        if has_any_idx:
            # Normalize UE indices so all runs align:
            # If indices appear 1-based (1..N) with no 0, shift to 0-based.
            idxs = sorted({int(r["ue_idx"]) for r in iperf_recs if isinstance(r.get("ue_idx"), int)})
            shift = 0
            if idxs:
                # Classic case: filenames are ue1..ueN (1-based)
                if (0 not in idxs) and (min(idxs) == 1) and (max(idxs) == expected_ues):
                    shift = -1
                # Also handle "ue0..ue{N}" (rare off-by-one extra)
                elif (min(idxs) == 0) and (max(idxs) == expected_ues) and (expected_ues not in (0, None)):
                    # If we see N as a valid idx, it's out-of-range for length N -> treat as 1-based mistake
                    # but only if 1 is present and distribution suggests shift.
                    if 1 in idxs and (expected_ues - 1) in idxs:
                        shift = -1
               
            res["iperf_ue_idx_shift"] = shift
            for rec in iperf_recs:
                if isinstance(rec.get("ue_idx"), int):
                    rec["ue_idx_norm"] = int(rec["ue_idx"]) + shift
                else:
                    rec["ue_idx_norm"] = None

            for r in iperf_recs:
                if not r.get("parse_ok"):
                    continue
                ue_idx = r.get("ue_idx")
                if not isinstance(ue_idx, int):
                    continue
                ue_idx = ue_idx + shift

                if ue_idx < 0 or ue_idx >= expected_ues:
                    continue
                bps = r.get("chosen_bps")
                if isinstance(bps, (int, float)):
                    ue_mbps[ue_idx] = float(bps) / 1e6
    else:
        # Unknown/0 expected UE count: use only parsed records
        for r in iperf_recs:
            if not r.get("parse_ok"):
                continue
            bps = r.get("chosen_bps")
            if isinstance(bps, (int, float)):
                ue_mbps.append(float(bps) / 1e6)

    # Quality counts
    parse_fail_n = sum(1 for r in iperf_recs if not r.get("parse_ok"))
    missing_end_n = sum(1 for r in iperf_recs if r.get("parse_ok") and r.get("end_present") is False)
    warning_prefix_n = sum(1 for r in iperf_recs if r.get("parse_ok") and r.get("has_warning_prefix"))
    stderr_error_n = sum(1 for r in iperf_recs if r.get("parse_ok") and r.get("stderr_has_error"))
    end_present_n = sum(1 for r in iperf_recs if r.get("parse_ok") and r.get("end_present") is True)
    reverse_n = sum(1 for r in iperf_recs if r.get("parse_ok") and r.get("reverse") is True)

    total_mbps = sum(ue_mbps) if ue_mbps else None
    per_ue_mean_mbps = (total_mbps / len(ue_mbps)) if (total_mbps is not None and len(ue_mbps) > 0) else None

    iperf_expected = expected_ues if expected_ues is not None else (len(iperf_files) if iperf_files else None)
    iperf_end_rate = (end_present_n / iperf_expected) if (iperf_expected and iperf_expected > 0) else None
    iperf_parse_rate = ((len(iperf_recs) - parse_fail_n) / iperf_expected) if (iperf_expected and iperf_expected > 0) else None

    res["iperf_summary"] = {
        "files_n": len(iperf_files),
        "expected_ues": iperf_expected,
        "parse_fail_n": parse_fail_n,
        "parse_ok_n": len(iperf_recs) - parse_fail_n,
        "parse_ok_rate": iperf_parse_rate,
        "missing_end_n": missing_end_n,
        "end_present_n": end_present_n,
        "end_present_rate": iperf_end_rate,
        "warning_prefix_n": warning_prefix_n,
        "stderr_error_n": stderr_error_n,
        "reverse_n": reverse_n,
        "total_mbps": total_mbps,
        "per_ue_mean_mbps": per_ue_mean_mbps,
        "fairness_jain": jains_fairness(ue_mbps) if ue_mbps else None,
    }

    return res


def format_float(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "NA"
    try:
        return f"{x:.{nd}f}"
    except Exception:
        return "NA"


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def build_summary_rows(runs: List[Dict[str, Any]], no_gpu: bool) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for r in runs:
        ue = r.get("ue_count")
        man = r.get("manifest") or {}
        start_ms = man.get("start_epoch_ms")
        start_iso = epoch_ms_to_iso(int(start_ms)) if isinstance(start_ms, (int, float)) else "NA"

        tw = r.get("test_window") or {}
        tw_start = tw.get("start_ms")
        tw_end = tw.get("end_ms")
        tw_dur = tw.get("duration_s")
        tw_src = tw.get("source")

        cu_cpu = r.get("cu_cpu") or {}
        du_cpu = r.get("du_cpu") or {}
        system_cpu = r.get("system_cpu") or {}  # NEW
        gpu_u = r.get("gpu_util") or {}
        gpu_p = r.get("gpu_power") or {}
        du_logs = r.get("du_logs") or {}
        ip = r.get("iperf_summary") or {}
        zmq = r.get("zmq_stats") or {}

        # Slot rate
        slot = (du_logs.get("slot_rate") or {}) if isinstance(du_logs, dict) else {}
        sps_mean = slot.get("slot_rate_mean_sps")
        rtf = slot.get("real_time_factor")
        slots_per_frame = slot.get("slots_per_frame")

        row = {
            "ue_count": ue,
            "run_name": r.get("run_name"),
            "start_epoch_ms": start_ms,
            "start_iso_utc": start_iso,
            "test_window_start_ms": tw_start,
            "test_window_end_ms": tw_end,
            "test_window_duration_s": tw_dur,
            "test_window_source": tw_src,
            "iperf_expected_ues": ip.get("expected_ues"),
            "iperf_total_mbps": ip.get("total_mbps"),
            "iperf_per_ue_mbps": ip.get("per_ue_mean_mbps"),
            "iperf_files": ip.get("files_n"),
            "iperf_parse_ok_rate": ip.get("parse_ok_rate"),
            "iperf_end_present_rate": ip.get("end_present_rate"),
            "iperf_missing_end": ip.get("missing_end_n"),
            "iperf_warn_prefix": ip.get("warning_prefix_n"),
            "iperf_stderr_err": ip.get("stderr_error_n"),
            "iperf_reverse_n": ip.get("reverse_n"),
            "iperf_fairness_jain": ip.get("fairness_jain"),
            "cu_cpu_mean_pct": (cu_cpu.get("cpu", {}) or {}).get("cpu_mean"),
            "cu_cpu_p95_pct": (cu_cpu.get("cpu", {}) or {}).get("cpu_p95"),
            "du_cpu_mean_pct": (du_cpu.get("cpu", {}) or {}).get("cpu_mean"),
            "du_cpu_p95_pct": (du_cpu.get("cpu", {}) or {}).get("cpu_p95"),
            "system_cpu_mean_pct": (system_cpu.get("cpu_total", {}) or {}).get("cpu_total_mean"),
            "system_cpu_p95_pct": (system_cpu.get("cpu_total", {}) or {}).get("cpu_total_p95"),
            "ldpc_impl": du_logs.get("ldpc_impl"),
            "ldpc_threads_cfg": du_logs.get("ldpc_threads_cfg"),
            "ldpc_bucket_ms": du_logs.get("ldpc_bucket_ms"),
            "ldpc_wall_mean_us": ((du_logs.get("ldpc_wall_decode_us", {}) or {}).get("wall_mean")),
            "ldpc_wall_p95_us": ((du_logs.get("ldpc_wall_decode_us", {}) or {}).get("wall_p95")),
            "ldpc_perseg_mean_us": ((du_logs.get("ldpc_us_per_seg", {}) or {}).get("perseg_mean")),
            "ldpc_samples_per_s": du_logs.get("ldpc_samples_per_s"),
            "ldpc_segments_est_mean": ((du_logs.get("ldpc_segments_est", {}) or {}).get("segs_mean")),
            "ldpc_effpar_mean": ((du_logs.get("ldpc_eff_parallelism_est", {}) or {}).get("effpar_mean")),
            "ldpc_core_proxy_mean_us": ((du_logs.get("ldpc_core_time_proxy_us", {}) or {}).get("core_mean")),
            "ldpc_core_proxy_p95_us": ((du_logs.get("ldpc_core_time_proxy_us", {}) or {}).get("core_p95")),
            "ldpc_core_proxy_method": du_logs.get("ldpc_core_time_proxy_method"),
            "slots_per_frame": slots_per_frame,
            "slot_rate_mean_sps": sps_mean,
            "real_time_factor": rtf,
            "zmq_published_counter_rate_sps": zmq.get("published_counter_rate_sps"),
            "zmq_published_line_rate_sps": zmq.get("published_line_rate_sps"),
            "zmq_usage_error": zmq.get("usage_error"),
        }

        if not no_gpu:
            row.update(
                {
                    "gpu_util_mean_pct": ((gpu_u.get("all", {}) or {}).get("util_gpu_mean")),
                    "gpu_util_p95_pct": ((gpu_u.get("all", {}) or {}).get("util_gpu_p95")),
                    "gpu_power_mean_w": ((gpu_p.get("all", {}) or {}).get("power_w_mean")),
                    "gpu_power_p95_w": ((gpu_p.get("all", {}) or {}).get("power_w_p95")),
                    "gpu_temp_mean_c": ((gpu_p.get("all", {}) or {}).get("temp_c_mean")),
                }
            )

        rows.append(row)
    return rows


def write_markdown_report(out_path: Path, runs: List[Dict[str, Any]], summary_rows: List[Dict[str, Any]], no_gpu: bool) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Choose throughput baseline as UE=1 if present, else UE=0 if present.
    baseline_thr = next((r for r in summary_rows if r.get("ue_count") == 1), None)
    baseline_idle = next((r for r in summary_rows if r.get("ue_count") == 0), None)

    def pct_delta(cur: Optional[float], base: Optional[float]) -> str:
        if cur is None or base is None or base == 0:
            return "NA"
        return f"{((cur - base) / base) * 100.0:+.1f}%"

    headers = [
        "UEs",
        "UL total (Mbps)",
        "UL/UE (Mbps)",
        "iperf end-rate",
        "Jain",
        "DU CPU mean/p95 (%)",
        "CU CPU mean/p95 (%)",
        "SYS CPU mean/p95 (%)",  
        "LDPC wall mean/p95 (us)",
        "LDPC core-proxy mean/p95 (us)",
        "LDPC samples/s",
        "Slot rate (slots/s)",
        "RTF",
    ]
    if not no_gpu:
        headers += ["GPU util mean/p95 (%)", "GPU power mean/p95 (W)"]
    headers += ["ZMQ pub-rate (ctr/s)"]

    lines: List[str] = []
    lines.append("# CU/DU Ablation Post-Processing Report (Optimized)")
    lines.append("")
    lines.append(f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Notes on metric semantics")
    lines.append("")
    lines.append("- **CPU/GPU utilization is windowed** to the inferred iperf test interval (with a small trim) when possible.")
    lines.append("- **LDPC prints are treated as samples**, not true per-decode event counts; `LDPC samples/s` reflects log print rate.")
    lines.append("- **LDPC core-proxy** approximates CPU core-time in the LDPC decode region using either (a) per-bucket summation (if multiple samples arrive within a small bucket) or (b) scaling by `min(threads_cfg, segments_est)` from `(us/us_per_seg)`.")
    lines.append("- **Slot rate / RTF** is a direct harness fidelity KPI: if RFSim/host scheduling slows, slots/sec drops and RTF < 1.")
    lines.append("")

    lines.append("## Runs analyzed")
    for r in runs:
        tw = (r.get("test_window") or {})
        lines.append(f"- `{r.get('run_name')}` (ue_count={r.get('ue_count')}, test_window_source={tw.get('source')})")
    lines.append("")

    lines.append("## Summary (windowed)")
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in summary_rows:
        ue = row.get("ue_count")
        ul_total = row.get("iperf_total_mbps")
        ul_per = row.get("iperf_per_ue_mbps")
        end_rate = row.get("iperf_end_present_rate")
        jain = row.get("iperf_fairness_jain")

        du_cpu = f"{format_float(row.get('du_cpu_mean_pct'))}/{format_float(row.get('du_cpu_p95_pct'))}"
        cu_cpu = f"{format_float(row.get('cu_cpu_mean_pct'))}/{format_float(row.get('cu_cpu_p95_pct'))}"
        sys_cpu = f"{format_float(row.get('system_cpu_mean_pct'))}/{format_float(row.get('system_cpu_p95_pct'))}"

        ldpc_wall = f"{format_float(row.get('ldpc_wall_mean_us'))}/{format_float(row.get('ldpc_wall_p95_us'))}"
        ldpc_core = f"{format_float(row.get('ldpc_core_proxy_mean_us'))}/{format_float(row.get('ldpc_core_proxy_p95_us'))}"
        ldpc_sps = format_float(row.get("ldpc_samples_per_s"), 3)

        slot_rate = format_float(row.get("slot_rate_mean_sps"), 1)
        rtf = format_float(row.get("real_time_factor"), 3)

        zmq_rate = format_float(row.get("zmq_published_counter_rate_sps"), 2)

        fields = [
            str(ue),
            format_float(ul_total, 2),
            format_float(ul_per, 2),
            format_float(end_rate, 3),
            format_float(jain, 6),
            du_cpu,
            cu_cpu,
            sys_cpu, 
            ldpc_wall,
            ldpc_core,
            ldpc_sps,
            slot_rate,
            rtf,
        ]
        if not no_gpu:
            gpu_util = f"{format_float(row.get('gpu_util_mean_pct'))}/{format_float(row.get('gpu_util_p95_pct'))}"
            gpu_pwr = f"{format_float(row.get('gpu_power_mean_w'))}/{format_float(row.get('gpu_power_p95_w'))}"
            fields += [gpu_util, gpu_pwr]
        fields += [zmq_rate]

        lines.append("| " + " | ".join(fields) + " |")

    lines.append("")
    lines.append("## Deltas vs baselines")
    lines.append("")
    if baseline_thr is None:
        lines.append("- No UE=1 run found; skipping throughput/RTF deltas vs UE=1.")
    else:
        lines.append("### Relative to UE=1 (scaling reference)")
        lines.append("")
        lines.append("| UEs | UL total Δ | Slot rate Δ | RTF Δ | Notes |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in summary_rows:
            ue = row.get("ue_count")
            if ue is None or ue == 1:
                continue
            ul_d = pct_delta(row.get("iperf_total_mbps"), baseline_thr.get("iperf_total_mbps"))
            sr_d = pct_delta(row.get("slot_rate_mean_sps"), baseline_thr.get("slot_rate_mean_sps"))
            rtf_d = pct_delta(row.get("real_time_factor"), baseline_thr.get("real_time_factor"))
            notes = []
            if (row.get("iperf_missing_end") or 0) > 0:
                notes.append(f"iperf missing_end={row.get('iperf_missing_end')}")
            if (row.get("iperf_reverse_n") or 0) > 0:
                notes.append(f"iperf reverse_n={row.get('iperf_reverse_n')}")
            if row.get("zmq_usage_error"):
                notes.append("ZMQ usage_error")
            lines.append(f"| {ue} | {ul_d} | {sr_d} | {rtf_d} | {', '.join(notes) if notes else ''} |")

    lines.append("")
    if baseline_idle is None:
        lines.append("- No UE=0 run found; skipping resource deltas vs idle baseline.")
    else:
        lines.append("### Relative to UE=0 (idle baseline)")
        lines.append("")
        lines.append("| UEs | DU CPU mean Δ | CU CPU mean Δ | SYS CPU mean Δ | GPU power mean Δ | Notes |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in summary_rows:
            ue = row.get("ue_count")
            if ue is None or ue == 0:
                continue
            du_d = pct_delta(row.get("du_cpu_mean_pct"), baseline_idle.get("du_cpu_mean_pct"))
            cu_d = pct_delta(row.get("cu_cpu_mean_pct"), baseline_idle.get("cu_cpu_mean_pct"))
            sys_d = pct_delta(row.get("system_cpu_mean_pct"), baseline_idle.get("system_cpu_mean_pct"))
            gp_d = pct_delta(row.get("gpu_power_mean_w"), baseline_idle.get("gpu_power_mean_w")) if not no_gpu else "NA"
            notes = []
            if (row.get("iperf_end_present_rate") is not None) and (row.get("iperf_end_present_rate") < 1.0):
                notes.append(f"iperf_end_rate={format_float(row.get('iperf_end_present_rate'),3)}")
            lines.append(f"| {ue} | {du_d} | {cu_d} | {sys_d} | {gp_d} | {', '.join(notes) if notes else ''} |")

    lines.append("")
    lines.append("## Per-run notes (data quality + errors)")
    lines.append("")
    for r in runs:
        rn = r.get("run_name")
        ue = r.get("ue_count")
        tw = r.get("test_window") or {}
        lines.append(f"### {rn} (UEs={ue})")
        lines.append("")
        lines.append(f"- Test window: source={tw.get('source')} start={tw.get('start_ms')} end={tw.get('end_ms')} trim_s={tw.get('trim_s')}")
        missing = r.get("missing_files") or []
        lines.append(f"- Missing files: {', '.join(missing) if missing else 'none'}")

        ip = r.get("iperf_summary") or {}
        lines.append(
            f"- iperf3: expected_ues={ip.get('expected_ues')} files={ip.get('files_n')} "
            f"parse_ok_rate={format_float(ip.get('parse_ok_rate'),3)} end_present_rate={format_float(ip.get('end_present_rate'),3)} "
            f"missing_end={ip.get('missing_end_n')} warn_prefix={ip.get('warning_prefix_n')} stderr_error={ip.get('stderr_error_n')} reverse_n={ip.get('reverse_n')}"
        )

        du = r.get("du_logs") or {}
        if du:
            ec = du.get("error_counts") or {}
            slot = du.get("slot_rate") or {}
            lines.append("- DU log errors: " + ", ".join([f"{k}={ec.get(k,0)}" for k in sorted(ec.keys())]))
            lines.append(
                f"- Slot rate: mean_sps={format_float(slot.get('slot_rate_mean_sps'),1)} "
                f"p50/p95_sps={format_float((slot.get('slot_rate_sps') or {}).get('sps_p50'),1)}/{format_float((slot.get('slot_rate_sps') or {}).get('sps_p95'),1)} "
                f"RTF={format_float(slot.get('real_time_factor'),3)} slots_per_frame={slot.get('slots_per_frame')}"
            )
            lines.append(
                f"- LDPC ({du.get('ldpc_impl','unknown')}): threads_cfg={du.get('ldpc_threads_cfg')} "
                f"wall_mean/p95_us={format_float((du.get('ldpc_wall_decode_us') or {}).get('wall_mean'),2)}/{format_float((du.get('ldpc_wall_decode_us') or {}).get('wall_p95'),2)} "
                f"core_proxy_mean/p95_us={format_float((du.get('ldpc_core_time_proxy_us') or {}).get('core_mean'),2)}/{format_float((du.get('ldpc_core_time_proxy_us') or {}).get('core_p95'),2)} "
                f"method={du.get('ldpc_core_time_proxy_method')} "
                f"samples_per_s={format_float(du.get('ldpc_samples_per_s'),3)} "
                f"segments_est_mean={format_float((du.get('ldpc_segments_est') or {}).get('segs_mean'),2)} effpar_mean={format_float((du.get('ldpc_eff_parallelism_est') or {}).get('effpar_mean'),2)}"
            )

        zmq = r.get("zmq_stats") or {}
        if zmq:
            lines.append(
                f"- ZMQ: lines={zmq.get('lines')} duration_s={format_float(zmq.get('duration_s'),1)} "
                f"ctr_rate_sps={format_float(zmq.get('published_counter_rate_sps'),2)} line_rate_sps={format_float(zmq.get('published_line_rate_sps'),2)} "
                f"unique_rnti={zmq.get('unique_rnti_count')} usage_error={zmq.get('usage_error')}"
            )
        lines.append("")

    out_path.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--runs-root",
        type=str,
        default="",
        help="Root folder containing run directories. Default: ./runs relative to this script.",
    )
    ap.add_argument(
        "--runs",
        nargs="*",
        default=[],
        help="Explicit list of run directories to process. If omitted, uses --ues-values under --runs-root.",
    )
    ap.add_argument(
        "--ues-values",
        type=str,
        default=",".join(str(x) for x in DEFAULT_UES_VALUES),
        help="Comma-separated UE counts to select latest matching runs (default: 0,1,3,6,12).",
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default="",
        help="Output directory for analysis results. Default: <runs-root>/analysis",
    )
    ap.add_argument(
        "--no-gpu",
        action="store_true",
        help="Skip GPU files/metrics (for CPU-only stacks such as OAI).",
    )
    ap.add_argument(
        "--cpu-ldpc-threads",
        type=int,
        default=4,
        help="Configured CPU LDPC worker parallelism for core-time proxy scaling (default: 4).",
    )
    ap.add_argument(
        "--cuda-ldpc-threads",
        type=int,
        default=1,
        help="Configured CUDA LDPC parallelism for core-time proxy scaling (default: 1).",
    )
    ap.add_argument(
        "--ldpc-bucket-ms",
        type=int,
        default=5,
        help="Time bucket (ms) for clustering LDPC prints to detect per-thread/per-task logs (default: 5).",
    )
    ap.add_argument(
        "--trim-seconds",
        type=float,
        default=2.0,
        help="Trim this many seconds off start/end of inferred test window when summarizing CPU/GPU (default: 2.0).",
    )
    ap.add_argument(
        "--test-duration-s",
        type=float,
        default=DEFAULT_FALLBACK_TEST_DURATION_S,
        help="Fallback test duration (seconds) when end timestamps cannot be inferred (default: 60).",
    )
    ap.add_argument(
        "--slots-per-frame",
        type=int,
        default=0,
        help="Override slots per frame for slot-rate computation (0=auto, default).",
    )
    ap.add_argument(
        "--frame-wrap",
        type=int,
        default=1024,
        help="Frame number wrap modulus used for slot unwrapping (default: 1024).",
    )
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    runs_root = Path(args.runs_root).resolve() if args.runs_root else (script_dir / "runs").resolve()

    if not runs_root.exists():
        raise SystemExit(f"Runs root does not exist: {runs_root}")

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (runs_root / "analysis").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    run_dirs: List[Path] = []
    if args.runs:
        run_dirs = [Path(p).resolve() for p in args.runs]
    else:
        ues_values: List[int] = []
        for s in args.ues_values.split(","):
            s = s.strip()
            if not s:
                continue
            try:
                ues_values.append(int(s))
            except Exception:
                continue
        if not ues_values:
            ues_values = DEFAULT_UES_VALUES
        run_dirs = pick_runs_by_ues(runs_root, ues_values)

    if not run_dirs:
        raise SystemExit("No runs found to process. Provide --runs or check --runs-root/--ues-values.")

    slots_per_frame_override = int(args.slots_per_frame) if isinstance(args.slots_per_frame, int) and args.slots_per_frame > 0 else None

    parsed_runs: List[Dict[str, Any]] = []
    for rd in run_dirs:
        if not rd.exists():
            print(f"WARN: run dir missing: {rd}")
            continue
        parsed_runs.append(
            parse_run(
                rd,
                no_gpu=args.no_gpu,
                cpu_ldpc_threads=args.cpu_ldpc_threads,
                cuda_ldpc_threads=args.cuda_ldpc_threads,
                ldpc_bucket_ms=args.ldpc_bucket_ms,
                trim_seconds=args.trim_seconds,
                expected_test_duration_s=float(args.test_duration_s),
                slots_per_frame_override=slots_per_frame_override,
                frame_wrap=int(args.frame_wrap),
            )
        )

    # Sort by UE count if possible
    parsed_runs.sort(key=lambda r: (r.get("ue_count") is None, r.get("ue_count") or 0, r.get("run_name") or ""))

    summary_rows = build_summary_rows(parsed_runs, no_gpu=args.no_gpu)

    # Write outputs
    details_path = out_dir / "ablation_details.json"
    details_path.write_text(json.dumps(parsed_runs, indent=2))

    summary_csv_path = out_dir / "ablation_summary.csv"
    summary_fields = list(summary_rows[0].keys()) if summary_rows else []
    write_csv(summary_csv_path, summary_rows, summary_fields)

    # Per-UE iperf CSV
    iperf_rows: List[Dict[str, Any]] = []
    for run in parsed_runs:
        ue_count = run.get("ue_count")
        run_name = run.get("run_name")
        recs = (run.get("iperf") or {}).get("records") or []
        for rec in recs:
            base = {
                "ue_count": ue_count,
                "run_name": run_name,
                "ue_idx": rec.get("ue_idx_norm"),   
                "ue_idx_raw": rec.get("ue_idx"),    
                "file": rec.get("path"),
            }
            if not rec.get("parse_ok"):
                iperf_rows.append({**base, "parse_ok": False, "error": rec.get("error")})
                continue

            iperf_rows.append(
                {
                    **base,
                    "parse_ok": True,
                    "protocol": rec.get("protocol"),
                    "reverse": rec.get("reverse"),
                    "has_warning_prefix": rec.get("has_warning_prefix"),
                    "end_present": rec.get("end_present"),
                    "intervals_n": rec.get("intervals_n"),
                    "throughput_mbps": (rec.get("chosen_bps") / 1e6) if isinstance(rec.get("chosen_bps"), (int, float)) else None,
                    "end_bps_received_mbps": (rec.get("end_bps_received") / 1e6) if isinstance(rec.get("end_bps_received"), (int, float)) else None,
                    "end_bps_sent_mbps": (rec.get("end_bps_sent") / 1e6) if isinstance(rec.get("end_bps_sent"), (int, float)) else None,
                    "bps_mean_mbps": (rec.get("bps", {}).get("bps_mean") / 1e6) if isinstance((rec.get("bps", {}) or {}).get("bps_mean"), (int, float)) else None,
                    "bps_p95_mbps": (rec.get("bps", {}).get("bps_p95") / 1e6) if isinstance((rec.get("bps", {}) or {}).get("bps_p95"), (int, float)) else None,
                    "retransmits": rec.get("retransmits"),
                    "stderr_has_error": rec.get("stderr_has_error"),
                }
            )

    if iperf_rows:
        iperf_csv_path = out_dir / "iperf_per_ue.csv"
        iperf_fields = sorted({k for row in iperf_rows for k in row.keys()})
        write_csv(iperf_csv_path, iperf_rows, iperf_fields)

    # Markdown report
    md_path = out_dir / "ablation_report.md"
    write_markdown_report(md_path, parsed_runs, summary_rows, no_gpu=args.no_gpu)

    print(f"Wrote: {details_path}")
    print(f"Wrote: {summary_csv_path}")
    if iperf_rows:
        print(f"Wrote: {out_dir / 'iperf_per_ue.csv'}")
    print(f"Wrote: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
