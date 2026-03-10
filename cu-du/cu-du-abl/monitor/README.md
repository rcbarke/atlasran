# CU–DU Load Testing & Telemetry Pipeline (Window-Aligned, Multi-Monitor)

This repository implements a **synchronized, multi-stream monitoring harness** for CU–DU load testing in RAN emulation stacks (e.g., OAI, Sionna-RK), with post-processing designed to:

* Align all telemetry to the inferred **iperf test window**
* Distinguish **pinned container CPU** from **system-wide CPU**
* Interpret LDPC logs correctly under CPU and CUDA execution models
* Quantify **slot-rate degradation (RTF)** as a harness fidelity KPI
* Detect under-fed pipelines and backpressure symptoms

The system is built around:

* `run_all_monitors.sh`
* 8 synchronized monitor scripts
* `uplink_test.sh`
* `post_process_cu_du_ablation.py`

---

# Architecture Overview

```
iperf3 (UL traffic)
        │
        ▼
   CU container ───► DU container ───► RFSim / PHY
        │                  │
        │                  │
        ▼                  ▼
 docker stats        LDPC timing logs
        │                  │
        ├──────────┐       │
        │          │       │
        ▼          ▼       ▼
  System CPU   GPU telemetry   ZMQ/KPM stream
 (/proc/stat)  (nvidia-smi)     (RIC client)

        ▼
 Window-aligned post-processing
        ▼
  Summary CSV + Markdown report
```

---

# Monitors

All monitors share:

* `--interval`
* `--wait-until-epoch-ms`
* `--out`

Each writes timestamped rows using `ts_epoch_ms`.

---

## 01 — GPU Utilization Monitor



Uses `nvidia-smi` to collect:

```
ts_epoch_ms,gpu_index,util_gpu_pct,util_mem_pct
```

Purpose:

* Detect GPU saturation vs under-utilization
* Compare against DU CPU trends

---

## 02 — GPU Power Monitor



Collects:

```
ts_epoch_ms,gpu_index,power_draw_w,power_limit_w,temp_gpu_c
```

Purpose:

* Identify compute-bound vs under-fed behavior
* Validate scaling consistency

---

## 03 — CU Container CPU Monitor



Uses `docker stats` for `oai-nr-cu`:

```
ts_epoch_ms,container,cpu_percent,mem_percent,...
```

Represents **pinned CU utilization only**.

---

## 04 — DU Container CPU Monitor



Same as above but for `oai-nr-du`.

Represents **pinned DU utilization only**.

---

## 05 — CU Docker Log Follower



Streams:

```
ts_epoch_ms    container    log_line
```

Used for:

* Error detection
* Contextual debugging

---

## 06 — DU Docker Log Follower



Critical for:

* LDPC decode timing extraction
* Frame.Slot parsing
* Slot-rate derivation

---

## 07 — ZMQ/KPM Stats Monitor



Wraps SRK RIC client:

```
ts_epoch_ms    zmq_stats_client    line
```

Used to measure:

* Published counter rate
* KPI emission rate
* UE stats presence
* Client usage errors

---

## 08 — System-Wide CPU Monitor (NEW)



Reads `/proc/stat`:

```
ts_epoch_ms,
cpu_total_pct,
cpu_user_pct,
cpu_system_pct,
cpu_iowait_pct,
cpu_idle_pct,
load1,load5,load15,
procs_running,procs_total
```

This is intentionally **not pinned to CU or DU**.

It provides:

* True host-level CPU utilization
* Baseline for comparison with container CPU
* Detection of background load
* Identification of mismatches between pinned vs system CPU

Expected behavior:

* System CPU should increase with UE count
* If DU CPU drops but system CPU remains low → under-fed pipeline
* If system CPU saturates while DU CPU drops → scheduler interference

---

# Monitor Orchestration

## run_all_monitors.sh



* Launches all monitors
* Synchronizes them using a shared `START_MS`
* Writes:

  * `cu_cpu.csv`
  * `du_cpu.csv`
  * `system_cpu.csv`
  * `gpu_util.csv`
  * `gpu_power.csv`
  * `cu_logs.tsv`
  * `du_logs.tsv`
  * `zmq_stats.tsv`
  * `run_manifest.json`
  * `pids.tsv`

All monitors align to the same epoch reference.

---

# Load Generation

## uplink_test.sh

* Runs per-UE iperf3 UL tests
* Produces:

  * `iperf3/*.json`
  * `*.stderr.log`

These JSON files are the anchor for window inference.

---

# Post-Processing

## post_process_cu_du_ablation.py



This script performs:

### 1️⃣ Window Inference

Test window derived from:

* iperf3 start timestamps + duration
* or manifest fallback

All telemetry (CPU, GPU, logs, ZMQ) is filtered to:

```
[start_ms + trim, end_ms - trim]
```

This prevents:

* Warm-up bias
* Cool-down bias

---

## 2️⃣ CPU Analysis

Produces:

| Metric           | Meaning                   |
| ---------------- | ------------------------- |
| DU CPU mean/p95  | Container-level pinned DU |
| CU CPU mean/p95  | Container-level pinned CU |
| SYS CPU mean/p95 | System-wide aggregate CPU |

Key interpretation rule:

* If DU CPU drops as UE increases → not compute-bound
* If GPU util drops → not compute-bound
* If SYS CPU low while throughput collapses → pipeline under-fed
* If SYS CPU high but DU CPU low → scheduler contention

---

## 3️⃣ LDPC Interpretation (Thread-Aware)

LDPC lines parsed from DU logs:

```
CPU LDPC decoder: 276.66 us ( 81.53 us / seg )
```

The script computes:

* Wall decode time distribution
* Estimated segment count
* Effective parallelism estimate
* Core-time proxy (bucket-summed or scaled)
* LDPC sample rate (prints/sec)

Important:

LDPC prints are treated as **samples**, not per-TTI events.

---

## 4️⃣ Slot-Rate & Real-Time Factor (RTF)

From `Frame.Slot F.S` logs:

* Computes slots/sec
* Derives:

```
RTF = measured_slots_per_s / nominal_slots_per_s
```

Nominal:

```
100 frames/sec × slots_per_frame
```

RTF < 1 → time dilation / harness slowdown.

This is the **strongest fidelity KPI**.

---

## 5️⃣ iperf3 Robust Parsing

Handles:

* WARNING prefixes
* Missing end blocks
* Partial JSON
* Reverse mode

Outputs:

* Per-UE throughput
* Jain fairness
* End-present rate
* Parse-success rate

---

# Outputs

Written to:

```
runs/analysis/
```

Files:

* `ablation_summary.csv`
* `ablation_report.md`
* `iperf_per_ue.csv`
* `ablation_details.json`

---

# Scaling Interpretation Framework

The pipeline is designed to distinguish:

| Signature                         | Likely Cause                    |
| --------------------------------- | ------------------------------- |
| Throughput collapse + high DU CPU | Compute-bound                   |
| Throughput collapse + low DU CPU  | Under-fed                       |
| GPU util drops with UE            | Upstream bottleneck             |
| RTF < 1                           | Emulation time-scale distortion |
| ZMQ telemetry collapse            | KPI backpressure                |
| Fairness ≈ 1                      | Uniform clamping                |

---

# Recommended Usage

### Standard run:

```bash
./run_all_monitors.sh
./uplink_test.sh
python3 post_process_cu_du_ablation.py
```

### CPU-only stack:

```bash
python3 post_process_cu_du_ablation.py --no-gpu
```

### Override LDPC threads:

```bash
python3 post_process_cu_du_ablation.py --cpu-ldpc-threads 8
```

---

# Design Philosophy

This pipeline is built to answer one question:

> Is multi-UE throughput collapse caused by PHY compute saturation or by harness/emulation limitations?

By aligning:

* Pinned CPU
* System CPU
* GPU utilization
* LDPC decode work
* Slot-rate fidelity
* ZMQ KPI stream
* iperf throughput

…we eliminate single-metric ambiguity.

---

# What Changed in This Version

Compared to previous revisions:

✔ Added **system-wide CPU monitor (08_cpu_monitor_system.py)**
✔ Window-aligned parsing for system CPU
✔ SYS CPU deltas vs UE=0 baseline
✔ Corrected markdown delta alignment
✔ Slot-rate/RTF included in summary table
✔ Robust iperf fallback logic

---

# Final Note

This is not just a logging harness.

It is a **causal analysis framework** for CU–DU scaling behavior.

If throughput collapses while compute utilization falls, the problem is not the decoder.

If RTF drops below 1, the emulator is distorting time.

If ZMQ telemetry disappears at scale, the control plane is overloaded.

This README reflects the current, validated logic across all scripts.

