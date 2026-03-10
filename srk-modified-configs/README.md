# Sionna-RK Modified Configurations

This repository contains **out-of-tree, research-oriented configuration extensions** for NVIDIA’s **Sionna Research Kit (Sionna-RK)** and its OpenAirInterface (OAI) integration.

The intent is to:
- extend Sionna-RK beyond its default examples,
- keep **all changes outside NVIDIA-managed repositories**,
- and enable **reproducible, auditable experimentation** across multi-UE, GPU-accelerated, and future slicing workflows.

Nothing in this directory is required for baseline Sionna-RK operation; everything here is **opt-in**.

Due to the number of developed features, please refer to the individual READMEs within the below subdirectories. Noteable subsets are summarized below, though this file does not encompass all functionalities.

---

## Directory Overview

```

srk-modified-configs/
├── cuda-ldpc/
├── oai-ldpc/
├── rfsim/
├── nr-ue/
├── multi-ue/
│   ├── rfsim-1ue/
│   └── rfsim-12ue/
├── oai-wan/
├── sionna-rt/
├── sliced_5gc/
└── x410/

```

---

## `cuda-ldpc/` — CUDA LDPC Decoding Acceleration

Enables **GPU-accelerated LDPC decoding** in OAI via environment overrides.

- Provides `rfsim.env` and `b200.env` variants.
- Includes `accelerate_ldpc.sh` to stage the correct `.env` files into:
  - `sionna-rk/config/rfsim/.env`
  - `sionna-rk/config/b200/.env`

**Status:** ✅ Working
**Recommendation:** **Strongly recommended** for dense UE configurations (e.g., 12 UEs). 
Without CUDA LDPC, CPU-based decoding becomes a bottleneck and destabilizes multi-UE experiments.

---

## `multi-ue/` — RFSim Multi-UE Profiles

Contains **self-contained RFSim experiment profiles** that scale UE count while preserving NVIDIA’s startup workflow.

### `multi-ue/rfsim-1ue/`
- Backup of NVIDIA’s **known-good single-UE RFSim configuration**.
- Serves as the **golden baseline** for debugging and regression testing.

**Status:** ✅ Stable (baseline)

### `multi-ue/rfsim-12ue/`
- Fully validated **12-UE RFSim deployment**:
  - 12 UE containers
  - sequential UE startup to avoid PRACH/attach storms
  - per-UE UL channel models
  - matching subscriber DB entries
- Includes an enhanced `start_system.sh` with `--num-ues`.

**Status:** 
- ✅ All 12 UEs attach and remain stable 
- ⚠️ RIC monitoring xApp exhibits buffer overflow (documented)

This profile represents the **current scaling limit** of SRK + OAI RFSim with full end-to-end registration.

---

## `oai-docker/` — OAI Docker Image Patches

Minimal Dockerfile patches for OAI images used by Sionna-RK.

- Adds WAN tooling (e.g., `curl`, `wget`) to runtime containers.
- Keeps NVIDIA’s build flow intact (`build-oai-images.sh`).
- Uses patch scripts instead of forking OAI repos.

**Status:** ✅ Stable utility layer 
**Purpose:** Research ergonomics and instrumentation

---

## `sliced_5gc/` — Sliced 5GC (TO-DO)

Design notes and placeholder for **future sliced 5GC integration**.

- OAI upstream supports slicing (Mode 3 with NSSF).
- Sionna-RK v1.1.0 deploys **only the minimalist 5GC**.
- As a result:
  - only single-slice eMBB experiments are currently supported,
  - URLLC and multi-slice studies are **not reliable** in SRK today.

This directory documents:
- the architectural gap,
- why slicing is intentionally deferred,
- and potential future integration paths.

**Status:** 🚧 TO-DO (documented, not implemented)

---

## Design Principles

Across all subdirectories:

- **No direct edits** to NVIDIA-managed repositories
- **Explicit staging scripts** for every change
- **Version-controlled configs** instead of ad-hoc edits
- **Honest documentation of limitations**
- Prefer **architectural correctness** over fragile demos

---

## Recommended Starting Point

For new users or collaborators:

1. Start with `multi-ue/rfsim-1ue/` to validate the environment.
2. Enable GPU offload via `cuda-ldpc/`.
3. Progress to `multi-ue/rfsim-12ue/` for scaling experiments.
4. Treat `sliced_5gc/` as forward-looking documentation only.

---

## Final Note

This directory reflects **what actually works today**, what **scales**, and what is **intentionally deferred**. 

It is meant to support serious systems research, not marketing demos.

If something is here, it has been tested, documented, and justified.`

