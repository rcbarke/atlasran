# System Interaction Guide (Top-Level)

This repository provides a **dockerized continuous deployment (CD) workflow** for running **OpenAirInterface (OAI)** in multiple modes, including **CPU-only** and **GPU-accelerated (Sionna Research Kit / SRK-backed)** execution paths. The workflow is **extended from NVIDIA’s Sionna-RK deployment automation** and preserves SRK’s documented operational model wherever possible.

**Primary references (upstream SRK):**
- NVlabs Sionna-RK repository: https://github.com/NVlabs/sionna-rk  
- SRK documentation: https://nvlabs.github.io/sionna/rk/index.html  

**BibTeX citation:**
```bibtex
@software{sionna-rk,
    title = {Sionna Research Kit},
    author = {Cammerer, Sebastian, and Marcus, Guillermo and Zirr, Tobias and Hoydis, Jakob and {Ait Aoudia}, Fayçal and Wiesmayr, Reinhard and Maggi, Lorenzo and Nimier-David, Merlin and Keller, Alexander},
    note = {https://nvlabs.github.io/sionna/rk/index.html},
    year = {2025},
    version = {1.1.0}
}
```

---

## Repository Layout

This deployment pipeline has **two top-level directories**:

1. **`sionna-rk/`**

   * GPU-first deployment mode based on NVIDIA SRK.
   * **Must be built on**:

     * **NVIDIA DGX Spark**, or
     * **NVIDIA Jetson Orin**
   * (In general: SRK expects a compliant NVIDIA software stack and compatible GPU runtime.)

2. **`oai-cpu/`**

   * CPU-only deployment mode.
   * Can be built/run on **any COTS PC**.

The top-level directory also includes:

* **`cu-du/`**

  * Modified Dockerfile deployment for **CU–DU F1 split** (recommended for load testing).
  * Contains documentation and staging scripts.

* **`srk-modified-configs/`**

  * Organized record of repository extensions and useful features.
  * Includes staging scripts and documentation for changes introduced beyond upstream SRK.

---

## One-Time Host Preparation

### SRK (`sionna-rk/`) — required once per *new* compliant device

On **DGX Spark** or **Jetson Orin**, run exactly once on new hardware:

```bash
cd sionna-rk
make prepare-system
```

Notes:

* This is **not required** on typical COTS PCs.
* This is also **not required** on compliant devices that already have SRK dependencies installed (e.g., an already-prepared DGX Spark host).

### OAI-CPU (`oai-cpu/`)

* Dependencies are handled as part of the build process (not a separate prerequisite step).

---

## Build Workflows

### Build OAI Docker Images (CPU workflow)

```bash
oai-cpu/scripts/quickstart-oai.sh
```

### Build SRK (GPU workflow)

```bash
cd sionna-rk
make sionna-rk
```

After the first successful SRK build, you may also use:

```bash
sionna-rk/scripts/quickstart-oai.sh
```

---

## Compilation & Redeployment After Source Changes

In either deployment mode, when you modify source code and need fresh containers, rebuild images with:

```bash
./scripts/build-oai-images.sh
```

Verify images exist:

```bash
docker image ls
```

You should see either:

* **`oai`** images (CPU mode), or
* **`oai-cuda`** images (GPU/SRK mode)

---

## Start / Stop the End-to-End System

### Start

```bash
./scripts/start_system.sh [rfsim | b200 | x410 | custom_config ] --num_ues N
```

* `N` is in **[1, 12]**
* Default is **12 UEs**

### Stop

```bash
./scripts/stop_system.sh
```

---

## `nr-UE/` Utility (External SDR SoftUE)

A useful extension available in **both deployment modes** is:

* `./nr-UE/`

This directory contains scripts and documentation to run an **SDR-based softUE on a separate host** (e.g., a Linux PC). It also includes lightweight example test scripts and example logs.

### SDR tuning and attenuation guidance

If you are working with SDRs:

* Tune your O-DU configuration to match the **maximum radio power** and your link budget.
* Both OAI and SRK commonly use `tx_attenuation` / `rx_attenuation` values that are **subtracted from dynamically detected maximum power**.
* For **cabled SDR deployments**, always use **inline attenuation** between TX and RX.
* We have **diplexers** available for building a **single-line TDD** link.

For deeper SDR cabling and deployment references (especially for NVIDIA-supported workflows), consult the upstream SRK documentation:

* [https://nvlabs.github.io/sionna/rk/index.html](https://nvlabs.github.io/sionna/rk/index.html)

---

## Where to Look Next

* If you are doing **CU–DU load testing**, start with:

  * `cu-du/`
* If you want a curated index of repository extensions and “what we changed,” see:

  * `srk-modified-configs/`
* For SRK-native utilities and deeper explanations that are not modified here, refer to:

  * SRK docs: [https://nvlabs.github.io/sionna/rk/index.html](https://nvlabs.github.io/sionna/rk/index.html)
  * SRK repo:  [https://github.com/NVlabs/sionna-rk](https://github.com/NVlabs/sionna-rk)

---

# CU–DU Load Study Dataset

**Host-OS Emulation (RFSim) — OAI CPU LDPC vs SRK CUDA LDPC**

This repository contains a fully post-processed dataset from a CU–DU load evaluation conducted under a controlled host-OS emulation harness. The study compares:

* **OpenAirInterface (OAI)** with vectorized **CPU LDPC**
* **Sionna Research Kit (SRK)** with **CUDA-accelerated LDPC**

The dataset includes windowed KPI aggregation, LDPC timing extraction, per-UE throughput series, and system-level resource metrics suitable for reproducible analysis.

---

## Study Overview

The CU–DU architecture consists of:

* OAI DU (RFSim mode, UE/RU abstraction)
* OAI CU exchanging F1 traffic
* Uplink traffic generated via `iperf3`
* ZMQ-based monitoring export
* Centralized post-processing pipeline

The harness is a **host-OS emulation environment**, enabling controlled compute ablations while preserving identical traffic generation and orchestration across both stacks.

The dataset captures steady-state behavior over 60 s runs across multiple UE concurrency levels.

---

## Measurement Methodology

### 1. Windowed KPI Aggregation

All KPIs are computed over the inferred `iperf3` active interval with trimmed edges to remove startup and teardown transients. Reported statistics include:

* Mean
* p95
* Run duration
* Valid interval rate

This ensures consistent steady-state comparison across UE counts.

---

### 2. LDPC Timing Interpretation

#### OAI (CPU Backend)

OAI logs report vectorized CPU decode timing per invocation:

* `LDPC/thread`
  Wall-clock duration of the parallel decode region per printed sample (µs)

* `LDPC cum`
  A cumulative core-time proxy accounting for effective 4-thread parallelism
  (≈4× per-thread timing under light load; slightly below 4× at high UE concurrency)

This reflects total decoder compute work rather than just wall-clock latency.

#### SRK (CUDA Backend)

SRK reports:

* CUDA workload timing per decode
* GPU utilization
* GPU memory usage
* CUDA engine activity

For SRK, `LDPC cum` equals the reported CUDA kernel workload timing.

---

### 3. CPU Metrics

Both stacks include:

* CU container CPU utilization (mean/p95)
* DU container CPU utilization (mean/p95)
* **System-wide CPU utilization** (mean/p95)

This separation allows evaluation of:

* Per-process compute saturation
* Host headroom
* Cross-component resource coupling

---

### 4. Throughput Metrics

The dataset includes:

* Aggregate UL throughput per run
* Per-UE throughput time series
* Scaling behavior across UE counts
* iperf interval diagnostics

Throughput collapse at high UE concurrency correlates strongly with:

* Slot progression rate (`slot_rate_mean_sps`)
* Real-time factor (`real_time_factor`)

This reinforces the interpretation of RFSim here as a **host scheduling harness**, not a fronthaul-faithful real-time twin.

---

## Repository Structure

### OAI (CPU LDPC)

* `oai_ablation_summary.csv`
  Windowed steady-state KPIs (one row per UE count)

* `oai_ablation_details.json`
  File inventory, parsing diagnostics, metadata

* `oai_ablation_report.md`
  Human-readable run summary and KPI interpretation

* `oai_iperf_per_ue.csv`
  Per-UE throughput time series

---

### SRK (CUDA LDPC)

* `srk_ablation_summary.csv`
  Windowed steady-state KPIs (includes GPU metrics)

* `srk_ablation_details.json`
  File inventory, parsing diagnostics, metadata

* `srk_ablation_report.md`
  Human-readable run summary and KPI interpretation

* `srk_iperf_per_ue.csv`
  Per-UE throughput time series

---

## Data Quality Notes

* Certain high-UE runs may exhibit missing iperf end summaries.
  Aggregate throughput is derived from interval rates and remains usable for scaling analysis.

* RFSim timing progression affects aggregate throughput under load.
  Reported results should therefore be interpreted in the context of host-OS emulation rather than RF-accurate fronthaul timing.

* All statistics are computed from steady-state trimmed intervals.

---

## Reproducing the UL Throughput Scaling Plot

```bash
python plot_ul_throughput_scaling.py \
  --oai oai_ablation_summary.csv \
  --srk srk_ablation_summary.csv \
  --out fig_ul_throughput_scaling.png
```

---

## Intended Use

This dataset supports:

* CU–DU compute ablation analysis
* CPU vs GPU LDPC performance comparison
* Multi-UE scaling characterization
* Host-OS emulation artifact study
* Cross-stack benchmarking methodology research

The data is suitable for:

* Reproducible systems papers
* Open RAN benchmarking studies
* AI-RAN compute acceleration analysis
* Scheduler and scaling-law modeling

---

## Citation

If this dataset contributes to published work, please cite the associated CU–DU load study and LDPC acceleration analysis as referenced in the accompanying manuscript.

