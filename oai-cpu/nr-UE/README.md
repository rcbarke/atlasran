# nr-UE — x86 OAI NR UE Utilities for Sionna Research Kit

This directory contains **x86 CPU-only NR UE utilities** designed to run **independently from the main Sionna Research Kit (SRK) tree**, which typically targets **DGX Spark or Jetson** platforms.

The scripts in `nr-UE/` enable building and running an **OpenAirInterface (OAI) NR UE Docker container** on a **separate x86 host**, which then communicates with SRK running on DGX/Jetson via **USRP B200/B210 (or compatible) radios**.

This split-host design avoids CUDA/Jetson dependencies on the UE side and simplifies debugging, USB stability, and host resource allocation.

---

## Overview

**Intended architecture**

```
x86 UE Host                          DGX / Jetson Host
------------                        ------------------
nr-UE utilities                     Sionna Research Kit
OAI NR UE (CPU)      <---RF--->      OAI gNB + 5GC
USRP B200/B210                       USRP B200/B210 / X410
```

* **UE host**: x86 Linux, CPU-only, runs `oai-nr-ue` container
* **gNB host**: DGX Spark or Jetson, runs full SRK stack
* **RF**: direct cable or OTA via USRP radios
* **Transport**: standard SRK networking (NGAP/F1/E2/etc.)

---

## Directory Contents

```
nr-UE/
├── README.md                # This file
├── quickstart-cpu-ue.sh     # Clone OAI + build CPU-only NR UE image
├── build-cpu-ue.sh          # Build UE-only Docker images
├── start-cpu-ue.sh          # Start only the UE container
├── stop-cpu-ue.sh           # Stop only the UE container
```

All scripts are intended to be run **from the UE host**, not from the DGX/Jetson system.

---

## Prerequisites (UE Host)

* x86_64 Linux (Ubuntu 22.04 / 24.04 recommended)
* Docker + Docker Compose
* Git
* USRP B200/B210 (or compatible)
* **USB 3.x connection required** (USB-C SS2.0 preferred)
* External power to the USRP strongly recommended

---

## Configuration

The UE uses the same SRK configuration layout:

```
../config/
└── b200/
    └── .env
```

The `.env` file is **shared logically** with SRK but interpreted locally by the UE scripts.
Key variables (excerpt):

```bash
# UE PHY config
UE_EXTRA_OPTIONS="-C 3309480000 -r 51 --numerology 1 --ssb 238 --thread-pool 3,4"

# UE radio
USRP_SERIAL_UE=30AD2B6
UE_RF_OPTIONS="--usrp-args serial=${USRP_SERIAL_UE},num_recv_frames=256,num_send_frames=256 --ue-fo-compensation --band 78"
```

### PRB profiles

* **51 PRBs** (default): aligns with SRK gNB configuration
* **24 PRBs**: fallback mode for marginal USB links or weaker hosts

If the UE enumerates as **USB-2**, downshift to **24 PRBs** per NVIDIA’s SRK guidance.

---

## Workflow

### 1. Build the CPU-only NR UE image

```bash
./quickstart-cpu-ue.sh
```

This script:

* Clones the OAI repository
* Builds the required base images
* Builds `oai-nr-ue:latest` (CPU-only)

> ⚠️ **Known issue**
> The upstream OAI Docker build can intermittently fail on the **first run** due to a circular dependency where UHD is referenced before installation completes.
> **If this happens, simply re-run the script** — UHD will already be present and the build will succeed.

This is an upstream OAI issue, not an SRK or script bug.

---

### 2. Verify USB 3.x connectivity (critical)

Before starting the UE, confirm the USRP is on USB-3:

```bash
lsusb -t
uhd_find_devices
uhd_usrp_probe
```

You must see:

```
[B200] Operating over USB 3.
```

If the device enumerates at **USB-2 (480M)**:

* Swap cables
* Change ports (USB-C SS2.0 preferred)
* Try a different host
* Or temporarily switch to **24 PRBs** in `../config/b200/.env`

---

### 3. Start the UE

```bash
./start-cpu-ue.sh b200
```

This:

* Loads the appropriate `.env`
* Starts **only** the `oai-nr-ue` container
* Uses existing `wait_for_container` logic
* Does **not** touch gNB, core, or RIC containers (which run on the other host)

Successful startup will show:

* UE synchronization
* RNTI assignment
* HARQ counters incrementing without overflow

---

### 4. Stop / clean up

```bash
./stop-cpu-ue.sh b200
```

Stops and removes **only** the UE container.

---

## USB Stability Notes (Important)

* The USRP B210 **cannot sustain 30.72 MSps over USB-2**
* If you see:

  ```
  Operating over USB 2.
  ERROR_CODE_OVERFLOW (Overflow)
  ```

  the UE will crash regardless of buffering

Mitigations:

* Ensure USB-3 enumeration
* Use `num_recv_frames=256,num_send_frames=256`
* Disable USB autosuspend
* Set CPU governor to `performance`
* Downshift to 24 PRBs if necessary

---

## Summary

These utilities provide a **clean, reproducible way to run an OAI NR UE on x86**, decoupled from DGX/Jetson constraints, while remaining fully compatible with SRK.

They are intended to:

* Reduce platform friction
* Improve USB stability
* Simplify debugging
* Enable multi-host SRK deployments

This directory is deliberately **self-contained** and does not modify the main SRK workflow.
