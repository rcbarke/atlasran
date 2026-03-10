# Open Air Interface CU–DU Uplink Scaling Ablation (CPU-Only LDPC)

**Generated:** 2026-02-23T20:02:23Z
**Host/kernel:** `spark-ecf8` · `Linux spark-ecf8 6.14.0-1015-nvidia #15-Ubuntu SMP PREEMPT_DYNAMIC Tue Nov 25 18:02:16 UTC 2025 aarch64 aarch64 aarch64 GNU/Linux`

This document is the **final analysis** for the CU–DU ablation characterizing **multi-UE uplink scaling** of the **Open Air Interface (OAI) CU–DU stack** using **CPU-only LDPC** (i.e., no CUDA LDPC acceleration). The goal is to quantify end-to-end UL behavior across UE concurrency while being explicit about **system-level limitations** of the test harness (notably **RFsim**).

---

## Executive summary

**What the numbers say**

* With **1 UE**, uplink throughput reached **~113.84 Mbps**.
* As UE count increased, **aggregate UL throughput fell sharply**:

  * **3 UEs:** ~64.27 Mbps total (**−43.5%** vs 1 UE)
  * **6 UEs:** ~32.40 Mbps total (**−71.5%** vs 1 UE)
  * **12 UEs:** ~15.79 Mbps total (**−86.1%** vs 1 UE) *(see data-quality note below)*
* **Per-UE throughput collapses** from **~113.84 Mbps/UE (1 UE)** to **~1.32 Mbps/UE (12 UEs)** (~**87×** drop per UE).

**What the resource telemetry says**

* DU and CU CPU usage does **not** increase monotonically with UE count. After 1 UE, both CU and DU CPU **trend downward** as UE count rises—matching a regime where the system is **throttled upstream** (i.e., it is doing *less useful work* because it cannot sustain throughput under multi-UE load).
* LDPC decode timing (as logged) rises sharply from **0 UE → 1 UE**, then **plateaus** in the **~256–277 µs** mean range for multi-UE runs, suggesting LDPC is **not the scaling limiter** once activated.
* When accounting for **multi-threaded CPU decode**, the **cumulative** LDPC CPU-time per decode group is **~1.03–1.11 ms** (≈4× the per-thread timing), which is important when comparing CPU vs GPU-offloaded PHY pipelines.

**Interpretation**

* The ablation indicates a **shared multi-UE bottleneck** in the end-to-end CU/DU + RFsim forwarding path rather than an LDPC saturation event.
* This is consistent with the pattern: **throughput collapses** while **CPU demand does not ramp** with UE count.

---

## Experimental setup (as exercised in this ablation)

### Core architecture

* **OAI gNB split into CU + DU over F1** (CU hosts higher layers; DU hosts MAC/PHY).
* **RFSim enabled** to connect UEs in simulated RF mode.
* **LDPC decode runs on CPU** (DU logs report `CPU LDPC decoder: ... us` timing lines).

### Radio configuration (key items)

* Same fixed carrier + numerology configuration used across runs (constant PRBs/carrier settings per your harness).
* Ablation stressor is **uplink TCP**.

### Traffic method (uplink)

* Each UE runs an **iperf3 server**.
* A traffic-generator runs **iperf3 clients in reverse mode (`-R`)**, which in your topology produces **uplink load (UE → host/5GC)**.

### Monitoring

* CPU utilization: container sampling (CU and DU).
* PHY telemetry: **LDPC decode timing** extracted from DU logs.
* Data quality: iperf parsing checks (missing end blocks, warning prefixes).

---

## Runs included

* `20260219_172332_ues0` (UEs=0)
* `20260219_172441_ues1` (UEs=1)
* `20260219_172959_ues3` (UEs=3)
* `20260219_173535_ues6` (UEs=6)
* `20260219_174039_ues12` (UEs=12)

---

## Primary results

### Aggregate summary table

| UEs | UL total (Mbps) | UL/UE (Mbps) | Jain fairness | DU CPU mean/p95 (%) | CU CPU mean/p95 (%) | LDPC mean/p95 (us) | LDPC events/s |
| --: | :-------------- | :----------- | :------------ | :------------------ | :------------------ | :----------------- | ------------: |
|   0 | NA             | NA          | NA           | 213.53/216.88       | 1.70/2.60           | 79.85/94.46      |        0.988 |
|   1 | 113.84         | 113.84      | 1.000000     | 329.26/332.28       | 22.68/25.37         | 256.27/262.18    |        1.011 |
|   3 | 64.27          | 21.42       | 1.000000     | 288.06/296.97       | 16.41/17.83         | 260.15/268.52    |        1.016 |
|   6 | 32.40          | 5.40        | 0.999905     | 202.29/209.68       | 8.62/9.37           | 275.29/287.92    |        1.015 |
|  12 | 15.79          | 1.32        | 0.999994     | 152.78/158.90       | 5.54/6.10           | 276.66/296.23    |        1.014 |

### Derived scaling indicators (UL)

| UEs | UL total (Mbps) | UL/UE (Mbps) | Jain fairness | DU CPU mean (%) | CU CPU mean (%) | UL total / 1UE | UL total loss vs 1UE (%) | DU CPU per Mbps |
| --: | --------------: | -----------: | ------------: | --------------: | --------------: | -------------: | -----------------------: | --------------: |
|   1 |         113.84 |     113.84 |     1.000000 |         329.26 |          22.68 |         1.000 |                     0.0 |           2.89 |
|   3 |          64.27 |      21.42 |     1.000000 |         288.06 |          16.41 |         0.565 |                    43.5 |           4.48 |
|   6 |          32.40 |       5.40 |     0.999905 |         202.29 |           8.62 |         0.285 |                    71.5 |           6.24 |
|  12 |          15.79 |       1.32 |     0.999994 |         152.78 |           5.54 |         0.139 |                    86.1 |           9.68 |

### LDPC threading analysis (per-thread vs cumulative CPU-time)

The aggregate table’s **LDPC mean/p95** corresponds to the **per-line timing emitted in DU logs** (per-thread / per-work-item). Since CPU LDPC decode is parallelized, we also compute a **cumulative CPU-time** estimate to reflect total work performed across threads.

| UEs | LDPC thread mean/p95 (us) | LDPC cumulative mean/p95 (us) | LDPC events/s (thr/cum) | Cum ÷ thread (mean) |
| --: | :----------------------- | :---------------------------- | -----------------------: | ------------------: |
|   0 | 79.85/94.46            | 319.41/377.86            |   0.988/3.954   |            4.00 |
|   1 | 256.27/262.18          | 1025.07/1048.71          |   1.011/4.043   |            4.00 |
|   3 | 260.15/268.52          | 1040.61/1074.09          |   1.016/4.065   |            4.00 |
|   6 | 275.29/287.92          | 1101.16/1151.68          |   1.015/4.062   |            4.00 |
|  12 | 276.66/296.23          | 1106.63/1184.91          |   1.014/4.056   |            4.00 |

---

## Analysis & academic justification

### 1) Multi-UE throughput collapse is not explained by LDPC saturation

* LDPC decode timing jumps from **~80 µs (0 UE)** to **~256 µs (1 UE)** as LDPC becomes active under real UL traffic.
* Past that, per-thread LDPC mean timing stays in a narrow band (**~256–277 µs**) even as total throughput collapses from **113.84 Mbps → 15.79 Mbps**.
* The **cumulative** LDPC CPU-time per decode group remains **~1.03–1.11 ms**, consistent with ~4-way parallelism on CPU (and useful for CPU/GPU comparisons where GPU may execute a single parallel kernel).
* This combined pattern suggests multi-UE scaling failure is driven by **shared stack/transport contention**, not by LDPC decode becoming the dominant limiting stage.

### 2) Jain fairness ≈ 1.0 implies a shared bottleneck, not UE starvation

Across multi-UE runs, Jain’s index remains essentially **1.0**, meaning UEs degrade together rather than one UE being starved. That points to a **global bottleneck** (shared resource) throttling all UEs uniformly.

### 3) CPU behavior reinforces “throttled upstream” interpretation

If the system were compute-limited on useful work, you’d expect CPU usage to climb with more UEs / more offered load. Instead:

* **CU CPU:** 22.68% (1 UE) → 5.54% (12 UE)
* **DU CPU:** 329% (1 UE) → 153% (12 UE)

This inversion strongly indicates the pipeline is **processing fewer effective work items** as UE concurrency rises—consistent with congestion/backpressure/coordination overhead preventing the PHY from being fully fed.

---

## Data-quality notes

* **UE12 run:** iperf parsing flagged **missing sender/receiver end blocks** and warning-prefixed outputs (12 / 12 iperf files). Throughput was computed from interval samples and should be treated as “degraded measurement,” but the measurement failure itself is consistent with an overloaded regime.

---

## Repository artifacts

* `ablation_summary.csv` — aggregate metrics per run (throughput, CPU, LDPC)
* `iperf_per_ue.csv` — per-UE iperf metrics (throughput, p95, retrans)
* `ablation_details.json` — per-run detail payload used to generate this README
* `ablation_report.md` — original post-processing report
* `post_process_cu_du_ablation.py` — post-processing logic used to compute metrics/tables
