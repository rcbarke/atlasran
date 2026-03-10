# Sionna-RK CU–DU Uplink Scaling Ablation (No UE CPU Pinning)

**Generated:** 2026-02-23T20:34:28Z  
**Host/kernel:** `spark-ecf8` · `Linux spark-ecf8 6.14.0-1015-nvidia #15-Ubuntu SMP PREEMPT_DYNAMIC Tue Nov 25 18:02:16 UTC 2025 aarch64 aarch64 aarch64 GNU/Linux`

This document is the **final analysis** for the CU–DU ablation in which **UE CPU pinning was removed** (i.e., UEs were *not* constrained to a fixed core set). The goal is to characterize **multi-UE uplink scaling** of the **Sionna-RK CU–DU stack** while being explicit about **system-level limitations** of the test harness (notably **OAI RFsim**).

> **Regeneration note (apples-to-apples):** This file was regenerated using the updated post-processing logic that reports both **per-thread** and **cumulative** LDPC KPIs. For **CUDA LDPC**, the DU emits a **single parallelized kernel timing** per decode event, so **per-thread ≡ cumulative** (threads_assumed=1 across all runs).

---

## Executive summary

**What the numbers say**
- With **1 UE**, uplink throughput reached **~101.2 Mbps**.
- As UE count increased, **aggregate UL throughput fell sharply**:
  - **3 UEs:** ~64.8 Mbps total (**−36%** vs 1 UE)
  - **6 UEs:** ~32.8 Mbps total (**−68%** vs 1 UE)
  - **12 UEs:** ~16.8 Mbps total (**−83%** vs 1 UE)
- **Per-UE throughput collapses** from **~101.2 Mbps/UE (1 UE)** to **~1.40 Mbps/UE (12 UEs)** (~**72×** drop per UE).

**What the resource telemetry says**
- DU/CU CPU usage and GPU utilization/power **decrease** as UE count increases.  
  This is the opposite of what we would expect if the system were compute-limited and instead indicates the stack is being **throttled upstream** of PHY compute.
- LDPC decoding timing remains in the **~319–343 μs** mean range across multi-UE runs, while LDPC events/s drops in proportion to throughput, indicating the decoder pipeline is **not saturated**.
- Because CUDA LDPC is a **single parallelized kernel**, the LDPC timing printed in DU logs corresponds to the **total GPU-time per decode event** (i.e., cumulative work does not scale with thread count in the way CPU decode does).

**Interpretation**
- The results are consistent with a **shared multi-UE bottleneck** in **OAI RFsim** (or the RFsim-adjacent sample-forwarding path), not with a GPU LDPC bottleneck or UE-side CPU scheduling.
- **Jain’s fairness** remains essentially **1.0**, consistent with a shared clamp. In this study, Jain’s is computed from the **ZMQ-based KPM xApp monitor** (not srsRAN’s ZMQ deployment mode).
- This aligns with upstream OAI documentation stating that RFsim **forwards IQ samples via TCP** and is **not designed for performance nor real-time operation**; it can run faster/slower than real time depending on system conditions [1,2].  
  As a result, RFsim should be treated as a **loose channel emulator**, *not* a cyber-physical twin for multi-UE performance scaling.

---

## Experimental setup (as exercised in this ablation)

### Core architecture
- **OAI gNB split into CU + DU over F1** (CU hosts higher layers; DU hosts MAC/PHY).  
  The CU/DU split over F1 is the canonical OAI disaggregation model for gNB deployments.  
- **RFSim enabled on the DU**; UEs connect via RFsim client mode.
- **DU loads the CUDA LDPC plugin** (`--loader.ldpc.shlibversion _cuda`) to exercise the Sionna-RK GPU-accelerated decode path.

### Radio configuration (key items)
- **Band n78**, **106 PRBs**, numerology **μ=1 (30 kHz SCS)**.
- TDD pattern configured for mixed DL/UL; the experiment stresses **uplink**.

### Traffic method
- Each UE runs an **iperf3 server**; a traffic-generator container runs **iperf3 clients in reverse mode (`-R`)** to create **uplink** load (TCP by default).  
- Runs are 60 s and are designed to **stress uplink LDPC decode**.

### Monitoring
- CPU utilization: `docker stats` for CU and DU containers.
- GPU utilization/power: `nvidia-smi` sampling.
- PHY telemetry: LDPC decode timing extracted from DU logs.
- KPI stream: **ZMQ-based KPM xApp monitor** collecting L1/L2 KPIs (used to compute Jain’s fairness).  
  *Note:* “ZMQ” here refers to the **KPM xApp transport**, not srsRAN’s ZMQ RF mode.
- Data quality: DU log error counters and iperf parsing checks.

---

## Runs included

- `20260218_191943_ues0` (UEs=0)
- `20260218_192448_ues1` (UEs=1)
- `20260218_192836_ues3` (UEs=3)
- `20260218_193305_ues6` (UEs=6)
- `20260218_193808_ues12` (UEs=12)

---

## Primary results

### Aggregate summary table

| UEs | UL total (Mbps) | UL/UE (Mbps) | Jain fairness | DU CPU mean/p95 (%) | CU CPU mean/p95 (%) | LDPC thread mean/p95 (us) | LDPC cum mean/p95 (us) | LDPC thr/cum events/s | GPU util mean/p95 (%) | GPU power mean/p95 (W) |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| 0 | NA | NA | NA | 208.90/211.02 | 1.92/2.20 | 208.65/222.09 | 208.65/222.09 | 0.571/0.571 | 1.32/2.30 | 11.83/12.23 |
| 1 | 101.20 | 101.20 | 1.000000 | 346.57/348.92 | 20.51/21.84 | 322.55/360.40 | 322.55/360.40 | 1.287/1.287 | 45.43/50.00 | 37.54/39.10 |
| 3 | 64.82 | 21.61 | 1.000000 | 326.69/347.02 | 16.63/18.17 | 319.22/344.05 | 319.22/344.05 | 0.827/0.827 | 28.33/33.90 | 28.91/30.40 |
| 6 | 32.78 | 5.46 | 0.999935 | 224.35/235.22 | 9.22/11.08 | 342.61/386.26 | 342.61/386.26 | 0.445/0.445 | 15.70/20.00 | 20.89/22.04 |
| 12 | 16.76 | 1.40 | 0.999995 | 175.38/182.50 | 5.98/7.16 | 337.65/377.38 | 337.65/377.38 | 0.245/0.245 | 8.71/13.30 | 16.58/17.55 |

### Derived scaling indicators (UL)

| UEs | UL total (Mbps) | UL/UE (Mbps) | Jain fairness | DU CPU mean (%) | GPU util mean (%) | GPU power mean (W) | UL total / 1UE | UL total loss vs 1UE (%) | Energy per Mbps (GPU W/Mbps) |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1.000 | 101.199 | 101.199 | 1.000 | 346.574 | 45.435 | 37.541 | 1.000 | 0.000 | 0.371 |
| 3.000 | 64.820 | 21.607 | 1.000 | 326.685 | 28.330 | 28.905 | 0.641 | 35.948 | 0.446 |
| 6.000 | 32.784 | 5.464 | 1.000 | 224.345 | 15.696 | 20.890 | 0.324 | 67.604 | 0.637 |
| 12.000 | 16.756 | 1.396 | 1.000 | 175.376 | 8.713 | 16.577 | 0.166 | 83.443 | 0.989 |

**Observed scaling:** Fitting a simple power law `T_total ≈ 115.7 · N^(-0.73)` over N∈{1,3,6,12} yields an exponent of -0.73 (i.e., total UL throughput decays approximately as N^-0.73).

### LDPC threading analysis (per-thread vs cumulative GPU-time)

In the updated post-processing, we compute both:
- **per-thread LDPC timing/events** (as directly emitted by DU log timing lines), and
- **cumulative LDPC timing/events** (total work per decode event, summing across parallel threads when applicable).

For **CUDA LDPC**, DU logs correspond to a **single parallelized GPU kernel**, so **per-thread ≡ cumulative** (threads_assumed=1). This makes SRK directly comparable to CPU LDPC pipelines where per-thread timing can hide higher total CPU-time due to parallel thread fan-out.

| UEs | LDPC thread mean/p95 (us) | LDPC cumulative mean/p95 (us) | LDPC events/s (thr/cum) | Cum ÷ thread (mean) |
| ---: | :--- | :--- | :--- | :--- |
| 0 | 208.65/222.09 | 208.65/222.09 | 0.571/0.571 | 1.000 |
| 1 | 322.55/360.40 | 322.55/360.40 | 1.287/1.287 | 1.000 |
| 3 | 319.22/344.05 | 319.22/344.05 | 0.827/0.827 | 1.000 |
| 6 | 342.61/386.26 | 342.61/386.26 | 0.445/0.445 | 1.000 |
| 12 | 337.65/377.38 | 337.65/377.38 | 0.245/0.245 | 1.000 |

---

## Analysis & academic justification

### 1) Multi-UE throughput collapse is **not** explained by PHY compute saturation

A common failure mode in accelerated PHY pipelines is that, as offered load increases, the accelerator becomes the bottleneck and we observe:
- increasing GPU utilization and power,
- stable or rising throughput until saturation,
- then flattening throughput with rising latency.

**We observe the opposite**:
- GPU utilization falls from **~45% (1 UE)** → **~8.7% (12 UEs)**.
- GPU power falls from **~37.5 W (1 UE)** → **~16.6 W (12 UEs)**.
- DU and CU CPU usage also falls with UE count.

This indicates the PHY pipeline is being **under-fed** (fewer TBs reach decode per unit time), pointing to an upstream shared bottleneck rather than decoder saturation.

### 2) CUDA LDPC is a single parallelized workload (cumulative GPU-time ≈ per-event timing)

Unlike CPU LDPC decode (which is explicitly multi-threaded in OAI’s implementation), SRK’s CUDA LDPC timing lines reflect a **single parallel kernel duration** per decode event. Therefore:
- cumulative work does **not** scale by thread count in the logs, and
- the SRK LDPC KPI is directly interpretable as total accelerator time per decode event.

This matters for CPU-vs-GPU comparisons: CPU can show “~250–300 μs per thread” while still consuming ~4× the cumulative CPU-time when four threads execute per decode group; SRK does not incur that multiplicative effect.

### 3) Jain fairness ≈ 1.0 implies a shared bottleneck, not UE starvation

For multi-UE runs, **Jain’s fairness index** is essentially **1.0** [4], meaning each UE receives almost the same throughput share. In other words, the system behaves like a **single shared resource** being partitioned evenly rather than a scheduler starving particular UEs.

This pattern is compatible with:
- shared transport contention / backpressure,
- shared lock/critical-section contention,
- a single-server architecture serving multiple clients,
- or a central queue/buffer throttling all UEs uniformly.

It is **less compatible** with random per-UE failures (e.g., one UE crashing, or a single bad channel instance) which would reduce fairness.

### 4) RFSim’s design characteristics match the observed failure mode

OAI’s RFsimulator is explicitly described as [1,2]:
- forwarding IQ samples between endpoints rather than transmitting “over the air”,
- using **TCP** to exchange IQ samples,
- not having a fixed timescale (can run faster or slower than real time),
- and **not designed to be as performant as possible nor close to real-time**.

These properties are important because multi-UE operation inherently increases:
- the number of concurrent sample streams,
- socket/kernel overhead,
- context switching,
- buffer management and backpressure sensitivity.

Additionally, OAI documentation notes RFsim is “limited to one server with multiple clients” [3] in certain multi-endpoint setups, reinforcing the “shared-server” nature of the transport.

**Hypothesis (most consistent with the data):** under multi-UE load, the RFsim TCP sample-forwarding path becomes the dominant bottleneck. The PHY stack is then under-fed, which reduces throughput and simultaneously lowers CPU/GPU utilization.

> Note: DU logs in these runs did not surface explicit `buffer overflow` strings, but RFsim can still throttle via backpressure or socket-level congestion without surfacing a hard overflow error.

### 5) Why this matters: RFSim is a *loose emulator*, not a cyber-physical twin

A cyber-physical twin (digital twin) is typically expected to preserve the key timing and performance behaviors of the real system. RFsim, by design, can run slower/faster than real time and introduces a TCP-based IQ transport layer that does not exist in an over-the-air RAN. Therefore, when RFsim becomes the bottleneck, it produces **non-physical performance degradation** that can dominate higher-layer KPIs (e.g., throughput/spectral efficiency) under multi-UE load.

**Practical conclusion for this dataset:** the multi-UE throughput collapse is best interpreted as a limitation of the RFsim test harness, not as an intrinsic limitation of the Sionna-RK CU–DU compute pipeline (context: Sionna is designed for GPU-accelerated PHY experimentation) [5].

---

## Data-quality notes

- **No missing files** were reported for the monitored artifacts in any run.
- DU log scans did **not** flag asserts/segfaults/aborts/timeouts/buffer-overflow errors in these runs.
- UE12 run: iperf3 JSON parsed ok for all 12 files, but `missing_end_n=12` and `warning_prefix_n=12` (the sender summary was not fully present in the text logs). Throughput was computed from interval samples.

---

## What I would publish (and how to frame it)

When reporting these numbers, I recommend explicitly stating:

1. **These are end-to-end UL throughput measurements under OAI RFsim**, not over-the-air measurements.
2. **Throughput does not scale with UE count** in this harness; instead it degrades approximately as a power law with exponent ~-0.73.
3. The telemetry (CPU/GPU utilization + LDPC timing) indicates the system is **not compute-limited**, and the most plausible explanation is **RFsim multi-stream contention / backpressure**.
4. Therefore, these numbers should be used for **transparent systems characterization** (what happens in this specific stack + harness), not as a proxy for over-the-air multi-UE spectral efficiency.

---

## Repository artifacts

- `ablation_summary.csv` — aggregate metrics per run (throughput, CPU/GPU, LDPC)
- `iperf_per_ue.csv` — per-UE iperf metrics (throughput, p95, retrans)
- `ablation_details.json` — per-run detail payload used to generate this README
- `ablation_report.md` — original post-processing report
- `post_process_cu_du_ablation.py` — post-processing logic used to compute metrics/tables

---

## References

1. **OAI RFsimulator README** (architecture, TCP server/client options, non-real-time + non-performance design statements):  
   - <https://raw.githubusercontent.com/OPENAIRINTERFACE/openairinterface5g/develop/radio/rfsimulator/README.md>

2. **OAI workshop slides**: *“Realistic Beamforming Simulation in OAI 5G stack”* (explicitly notes RFsim uses TCP to exchange IQ samples and has no fixed time scale):  
   - <https://openairinterface.org/wp-content/uploads/2025/05/OAI-Kista-Workshop-OAI.pdf>

3. **OAI handover tutorial** (RFsim role switching + “one server with multiple clients” limitation statement):  
   - <https://raw.githubusercontent.com/OPENAIRINTERFACE/openairinterface5g/develop/doc/handover-tutorial.md>

4. **Jain’s fairness index** (resource allocation fairness metric):  
   - R. Jain, D.-M. Chiu, W. Hawe, *A Quantitative Measure of Fairness and Discrimination for Resource Allocation in Shared Computer Systems* (arXiv mirror):  
     <https://arxiv.org/abs/cs/9809099>

5. **Sionna** (GPU-accelerated physical-layer research library):  
   - J. Hoydis et al., *Sionna: An Open-Source Library for Next-Generation Physical Layer Research*:  
     <https://arxiv.org/abs/2203.11854>

6. **Digital twin definition context** (real-time virtual representation concept):  
   - IBM, “What is a digital twin?”:  
     <https://www.ibm.com/think/topics/digital-twin>
