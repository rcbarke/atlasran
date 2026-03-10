# OAI-CPU: Baseline OpenAirInterface Deployment for Clean CPU Benchmarking

This directory contains a **CPU-only OpenAirInterface (OAI) workflow** used to establish clean baseline benchmarks against the GPU-accelerated Sionna Research Kit (SRK) path. While the original SRK workflow builds **CUDA-enabled container images** and integrates SRK-specific patches for accelerated execution, this folder contains **augmented scripts that deploy standard OAI containers on CPU without SRK patches**.

The purpose of this directory is straightforward: provide a reproducible, minimally altered OAI deployment path for **apples-to-apples benchmarking** against SRK-accelerated workflows. In other words, where SRK evaluates what changes when GPU-accelerated PHY execution is introduced, this folder preserves a conventional OAI software path so the performance, scaling, and orchestration differences can be measured cleanly.

## What this directory is for

This folder is intended for researchers and engineers who want to:

- deploy **standard OAI network functions on CPU**
- benchmark OAI **without SRK’s accelerator-specific patches**
- compare **CPU-only OAI** against **SRK / GPU-enabled workflows**
- isolate the effect of **accelerated PHY execution** from the rest of the software stack
- build a reproducible baseline for CU-DU, orchestration, and end-to-end goodput studies

## Key distinction from SRK

The SRK workflow is designed around **GPU-accelerated AI-RAN / O-RAN experimentation**, including CUDA-capable Docker images and SRK-specific integration points.

This `OAI-CPU` directory serves a different purpose:

- **SRK path:** builds CUDA-enabled images and uses SRK modifications for accelerated execution
- **OAI-CPU path:** builds standard `oai-*` images and runs OAI on CPU only
- **SRK path:** intended for accelerator-backed experimentation
- **OAI-CPU path:** intended for clean baseline measurement against unpatched OAI behavior

This makes the folder especially useful for studies where the question is not just “how fast is the accelerated path,” but rather **“what changes relative to standard OAI when acceleration is introduced?”**

## What is included here

This directory contains **augmented deployment scripts** adapted for baseline OAI benchmarking. These scripts are derived from the broader SRK-style workflow, but modified so that this path:

- does **not** depend on SRK-specific patches
- does **not** build CUDA-based Docker images
- **does** build standard OAI container images on CPU
- preserves a workflow that is familiar to users comparing against SRK experiments

In short, this folder keeps the deployment process recognizable while removing the accelerator-specific assumptions that would otherwise contaminate baseline measurements.

## Build behavior

Unlike the SRK workflow, which builds CUDA-capable images for GPU-backed execution, this directory builds the standard OAI images, such as:

- `oai-gnb`
- `oai-nr-ue`
- `oai-amf`
- `oai-smf`
- `oai-upf`
- other standard `oai-*` services as required by the experiment configuration

These images are intended to run in a **CPU-only benchmark configuration**.

## Why this matters

For rigorous benchmarking, the baseline must be clean.

If the comparison target already contains SRK-specific modifications, accelerator-aware build logic, or GPU-oriented integration changes, then it becomes harder to determine whether observed gains come from:

- PHY acceleration itself
- container/build differences
- orchestration changes
- patched runtime behavior
- or some combination of the above

This directory helps avoid that ambiguity by providing a **standard OAI reference path** for comparison.

## Recommended use

Use this folder when you want to:

1. build and deploy a **baseline OAI stack**
2. collect CPU-only timing, throughput, and goodput measurements
3. compare those results against an SRK / GPU-enabled run
4. quantify where bottlenecks move when acceleration is introduced

This is particularly useful in studies of:

- CU-DU scaling
- host-side orchestration overhead
- containerized OAI execution
- end-to-end uplink or downlink benchmarking
- accelerator versus non-accelerator execution tradeoffs

## Relationship to the paper

This directory supports the benchmarking methodology used in the accompanying AtlasRAN study by providing a **clean non-SRK OAI baseline**. Its role is to help separate:

- improvements due to lower decoder-side work
- from limitations caused by host-side harness, orchestration, or software-stack overhead

That distinction is central to fair comparison between conventional OAI execution and accelerator-backed AI-RAN workflows.

## Usage notes

Before running experiments from this directory, make sure to:

- verify that your host is configured for standard OAI container builds
- confirm that no SRK-specific patches or CUDA assumptions remain in the local environment
- document software versions, container tags, and host hardware for reproducibility
- keep benchmark settings aligned with the SRK comparison case wherever possible

For credible comparison, differences between the CPU and SRK workflows should be limited to the factors actually under study.

## License and attribution

This folder is part of the broader AtlasRAN research artifact. Users should also be aware that upstream OAI and any third-party components may carry their own licenses and usage terms. It is your responsibility to review and comply with all applicable upstream licenses when using or redistributing derived workflows.

## Summary

`OAI-CPU` is the **clean baseline path** in this repository.

It exists to answer a simple but important question: **how does standard CPU-only OpenAirInterface behave when measured against the SRK GPU-accelerated path under comparable conditions?** To support that goal, this folder replaces SRK’s CUDA-oriented build flow with standard `oai-*` image builds and removes SRK patches so benchmarking against upstream-style OAI remains as clean and defensible as possible.
