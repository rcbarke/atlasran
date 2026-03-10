# CU–DU Load-Study Harness (AtlasRAN Artifact)

This repository contains the **measurement harness + post-processing** used in the *AtlasRAN* CU–DU scaling ablation (RFSim host-OS emulation), designed to **separate compute saturation from harness/time-scale artifacts** by aligning multiple telemetry streams to a common test window. 

At a high level, the paper’s core diagnostic is:

> **Throughput collapses under UE concurrency while fairness stays ~1 and CU/DU CPU + GPU utilization *decrease*** → the pipeline is increasingly **under-fed** due to host-OS emulation timing/I/O behavior (time-scale dilation), not LDPC saturation. 

This harness is the artifact that makes that claim reproducible: it records CU/DU container CPU, host-wide CPU, DU LDPC timing, slot-progress rate (RTF), ZMQ KPI stream health, GPU utilization/power (when applicable), and per-UE iperf3 throughput—then summarizes everything in a single report.

---

## What this repo is (and is not)

### ✅ What it is
A **synchronized multi-monitor** runner plus a **window-aligned post-processor** for CU–DU load tests, intended for controlled ablations in **RFSim host-OS emulation** (and similar emulation regimes). 

### ❌ What it is not
A claim of real fronthaul timing fidelity or cyber-physical twin behavior. In the paper’s taxonomy, this is an **emulation harness** that can run faster or slower than real time depending on OS scheduling and available compute; the harness therefore must be treated as part of the experimental system. 

---

## Reference experiment (paper alignment)

The AtlasRAN draft runs a split CU–DU uplink load test on a **common NVIDIA DGX Spark harness** (Grace CPU + Blackwell GPU, 128GB NVLink-C2C coherent memory), using the same platform for both baselines to avoid CPU↔GPU confounds. 

- **UE counts:** N ∈ {0, 1, 3, 6, 12}
- **Traffic:** 60s saturated uplink TCP (iperf3), one flow per UE   
- **Pinning (paper):** CU pinned to cores 6–7; DU pinned to cores 8–11   
- **Sampling:** 0.5s monitors; post-processing reports mean/p95 over the steady-state window 
- **Baselines compared (paper):**
  - OAI RFSim with CPU LDPC (MIMD×SIMD threaded decode region) 
  - SRK with CUDA LDPC offload (single GPU-side timing per TB) 

---

## Repository layout

Key scripts:

- **Monitor orchestration**
  - `run_all_monitors.sh` — starts all monitors with a shared `START_MS` and writes run artifacts. 
- **Load generation**
  - `uplink_test.sh` — runs per-UE iperf3 UL tests and writes JSON outputs used to infer the test window. 
- **Post-processing**
  - `post_process_cu_du_ablation.py` — window inference + metric parsing + summary CSV + markdown report. 

Monitors (all emit epoch timestamps in `ts_epoch_ms` so streams can be aligned):

- `01_gpu_util_monitor.py` — GPU utilization via `nvidia-smi`. 
- `02_gpu_power_monitor.py` — GPU power/temp via `nvidia-smi`.
- `03_cpu_monitor_oai_nr_cu.py` — CU container CPU via `docker stats`.
- `04_cpu_monitor_oai_nr_du.py` — DU container CPU via `docker stats`. 
- `05_logs_follow_oai_nr_cu.py` — CU docker logs with timestamps. 
- `06_logs_follow_oai_nr_du.py` — DU docker logs with timestamps (LDPC + Frame.Slot parsing).
- `07_zmq_stats_client_monitor.py` — wraps SRK’s ZMQ stats client with timestamps.
- `08_cpu_monitor_system.py` — **system-wide CPU** from `/proc/stat` (host baseline).

---

## Core metric semantics (paper-consistent)

### CPU “core-equivalent” normalization
All CPU percentages should be read as **core-equivalents**:

- **100% ≡ one fully utilized logical core**
- pinned maxima: DU pinned to 4 cores → 400%; CU pinned to 2 cores → 200%

This repository also records **SYS CPU** (host-wide) on the *same scale* so you can tell the difference between “DU is busy on its pinned cores” vs “the whole machine is saturated.”

### LDPC timing interpretation
DU logs are parsed for LDPC timing lines, but **LDPC prints are treated as samples**, not per-slot/per-TB event counts. The post-processor reports:

- `LDPC wall` — as-logged wall-clock decode duration samples
- `LDPC core-time proxy` — an estimated cumulative “core-µs” proxy (CPU) or equals the single CUDA call (GPU)
- `LDPC samples/s` — log print rate, not decode event rate 

This matches the paper’s explanation: CPU decode is parallel across segments (MIMD) with SIMD kernels per worker, so the DU log line reports the wall-clock duration of the parallel region plus a per-segment normalization. 

### Slot-rate and Real-Time Factor (RTF)
The post-processor extracts `Frame.Slot` progress from DU logs and computes:

- **slot-processing rate (slots/s)**
- **RTF = measured_slots_per_s / nominal_slots_per_s**

RTF < 1 is a direct “time dilation” signature (harness is running slower than nominal slot timing). The paper uses this as a primary fidelity KPI.

### ZMQ KPI stream health
The harness monitors the ZMQ KPI stream rate and detects “usage errors” / collapse; the paper highlights telemetry stalling at high UE counts as an additional harness-level symptom.

---

## Running the pipeline

### 1) Start monitors (synchronized)
```bash
./run_all_monitors.sh
```

This launches all monitors using a shared `START_MS` and writes (per run):

* `cu_cpu.csv`, `du_cpu.csv` (container CPU)
* `system_cpu.csv` (host CPU baseline)
* `gpu_util.csv`, `gpu_power.csv` (if GPU available)
* `cu_logs.tsv`, `du_logs.tsv` (timestamped docker logs)
* `zmq_stats.tsv` (timestamped ZMQ client output)
* `run_manifest.json`, `pids.tsv`, launch logs 

### 2) Generate load

```bash
./uplink_test.sh
```

This produces per-UE iperf3 JSON outputs under `iperf3/`, which the post-processor uses as the **anchor for window inference**. 

### 3) Post-process (window-aligned)

```bash
python3 post_process_cu_du_ablation.py
```

Common options:

* CPU-only stack (skip GPU expectations):

```bash
python3 post_process_cu_du_ablation.py --no-gpu
```

* Override LDPC thread parallelism for the core-time proxy:

```bash
python3 post_process_cu_du_ablation.py --cpu-ldpc-threads 4
```

---

## Outputs

Written to:

```
runs/analysis/
```

Artifacts:

* `ablation_summary.csv` — one row per run (UE count) with all core KPIs
* `ablation_report.md` — human-readable report with tables + deltas
* `iperf_per_ue.csv` — per-UE throughput + parse quality stats
* `ablation_details.json` — full parsed structure (for custom analysis) 

---

## How to read results (the AtlasRAN “compute vs harness” test)

This harness is built to answer:

> **Is multi-UE goodput collapse due to PHY compute saturation or to harness/time-scale/I/O limits upstream of the decoder?** 

Interpretation patterns (aligned with the draft):

* **Compute-bound:** throughput ↓ while DU CPU and/or GPU util ↑
* **Under-fed / time-dilated:** throughput ↓ while DU CPU, SYS CPU, and GPU util/power ↓, often with **RTF ↓** and ZMQ instability 
* **Scheduler unfairness:** Jain fairness ↓ meaningfully (not observed in the paper’s collapse regime) 

---

## Notes for paper parity

* This repo assumes the CU/DU container names used in the study:

  * `oai-nr-cu` and `oai-nr-du` 
* If you change container names, update `03_cpu_monitor_oai_nr_cu.py`, `04_cpu_monitor_oai_nr_du.py`, `05_logs_follow_oai_nr_cu.py`, and `06_logs_follow_oai_nr_du.py`. 
* The post-processor is intentionally robust to partial/missing logs at high UE counts (common when the emulation harness destabilizes). 

---

## Outlook (paper draft continuity)

The AtlasRAN draft explicitly motivates a follow-on that “hardens the substrate” (engineered I/O + timing discipline), and notes an in-progress repeat of this ablation against a CUDA channel emulator being rearchitected to address the precise under-fed failure mode surfaced here. 

This repository should be treated as the **baseline measurement substrate** for that next step: when the transport/timing contracts change, the same monitors + windowing + RTF and fairness diagnostics should make the improvement (or lack thereof) unambiguous.

---

## Citation

If you use this codebase (scripts, measurement methodology, or post-processing) in your research, please cite the associated paper:

> Ryan Barker, Tolunay Seyfi, Alireza Ebrahimi Dorcheh, Julia Boone, Fatemeh Afghah, and Joseph Boccuzzi, “**AtlasRAN: The O-RAN and AI-RAN Compass**,” 2026.

**BibTeX**
```bibtex
@unpublished{barker_atlasran_2026,
  title  = {AtlasRAN: The O-RAN and AI-RAN Compass},
  author = {Barker, Ryan and Seyfi, Tolunay and Ebrahimi Dorcheh, Alireza and Boone, Julia and Afghah, Fatemeh and Boccuzzi, Joseph},
  year   = {2026},
  note   = {Manuscript. Code and measurement harness: this repository}
}
