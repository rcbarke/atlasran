# OAI Docker WAN Patch (Sionna-RK)

This directory contains **non-intrusive configuration overrides** for NVIDIA’s
Sionna-RK OpenAirInterface (OAI) Docker images.
The goal is to enable **WAN connectivity utilities** (e.g., `curl`, `wget`)
inside the runtime **gNB** and **UE** containers, without modifying or forking
NVIDIA-managed infrastructure code.

All changes are applied via controlled file replacement and can be reapplied
after upstream updates.

---

## Directory Contents

```

oai-docker/
├── Dockerfile.gNB.ubuntu.cuda
├── Dockerfile.nrUE.ubuntu.cuda
├── patch_oai_wan.sh
└── rebuild_srk_docker.sh

```

---

## File Descriptions

### 1. `Dockerfile.gNB.ubuntu.cuda`

**Purpose**
Modified runtime Dockerfile for the OAI **gNB** container.

**Changes vs upstream**
- Adds WAN-related userland tools:
  - `curl`
  - `wget`
  - `ca-certificates`
- Packages are installed in the **final runtime stage** (`oai-gnb-cuda`),
  ensuring availability inside the running container.

**Why this matters**
- Enables:
  - External artifact downloads
  - Telemetry uploads
  - Load-testing integrations
- Required for research workflows that interact with resources outside the
  Docker network.

---

### 2. `Dockerfile.nrUE.ubuntu.cuda`

**Purpose** 
Modified runtime Dockerfile for the OAI **NR UE** container.

**Changes vs upstream**
- Mirrors the gNB changes for symmetry and dependency safety:
  - `curl`
  - `wget`
  - `ca-certificates`
- Ensures UE containers can:
  - Pull test vectors
  - Interact with WAN-hosted services
  - Support multi-UE load testing scenarios

**Design note** 
Both gNB and UE images are patched to avoid subtle runtime inconsistencies when
conducting distributed or scaled experiments.

---

### 3. `patch_oai_wan.sh`

**Purpose** 
Applies the modified Dockerfiles to the Sionna-RK repository **without editing
NVIDIA code directly**.

**What it does**
- Verifies the modified Dockerfiles exist locally
- Verifies the target Sionna-RK OAI Docker directory exists
- Copies the Dockerfiles into:

```

../../sionna-rk/ext/openairinterface5g/docker/

```

**Key properties**
- Fail-fast and idempotent
- No assumptions about git state or branches
- Safe to re-run after upstream updates

**Usage**
```bash
cd srk-modified-configs/oai-docker
./patch_oai_wan.sh
```

---

### 4. `rebuild_srk_docker.sh`

**Purpose**
Rebuilds the Sionna-RK OpenAirInterface Docker images after Dockerfile changes,
while preserving NVIDIA’s default build behavior.

**What it does**

* Invokes NVIDIA’s `build-oai-images.sh` script
* Uses the default `latest` tag to match the standard docker-compose config
* Targets the canonical OAI source directory:

  ```
  ./ext/openairinterface5g
  ```

**Usage**

```bash
cd srk-modified-configs/oai-docker
./rebuild_srk_docker.sh
```

This script is intended to be run repeatedly during iterative Dockerfile
development.

---

## End-to-End Workflow (Patch → Rebuild → Deploy → Test)

### 1. Patch NVIDIA’s OAI Dockerfiles

```bash
cd srk-modified-configs/oai-docker
./patch_oai_wan.sh
```

---

### 2. Rebuild OAI Docker Images

```bash
./rebuild_srk_docker.sh
```

This executes:

```bash
./scripts/build-oai-images.sh --tag latest ./ext/openairinterface5g
```

from the Sionna-RK root, mirroring NVIDIA’s default configuration.

---

### 3. Start the Sionna-RK System (RFSim)

From the Sionna-RK repository:

```bash
cd ../../sionna-rk
./scripts/start_system.sh rfsim
```

This deploys:

* 5G Core Network
* gNB (`oai-gnb`)
* NR UE (`oai-nr-ue`)
* Supporting services (RIC, monitoring, etc.)

---

### 4. Verify Running Containers

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | egrep 'oai-gnb|oai-nr-ue'
```

**Sample output**

```
oai-nr-ue   oai-nr-ue-cuda:latest   Up 40 seconds (healthy)
oai-gnb     oai-gnb-cuda:latest     Up 51 seconds (healthy)
```

---

### 5. Smoke Test: Tool Availability Inside Running Containers

Because OAI containers require mounted configuration files, testing must be
performed **inside the deployed containers** (not via `docker run`).

```bash
docker exec -it oai-gnb   bash -lc 'which curl wget && curl --version | head -n1 && wget --version | head -n1'
docker exec -it oai-nr-ue bash -lc 'which curl wget && curl --version | head -n1 && wget --version | head -n1'
```

**Sample output**

```
/usr/bin/curl
/usr/bin/wget
curl 8.5.0 (aarch64-unknown-linux-gnu) ...
GNU Wget 1.21.4 built on linux-gnu.
```

---

### 6. Smoke Test: WAN Connectivity (DNS + TLS + Egress)

```bash
docker exec -it oai-nr-ue bash -lc 'curl -I https://example.com | head -n 1'
docker exec -it oai-gnb   bash -lc 'curl -I https://example.com | head -n 1'
```

**Sample output**

```
HTTP/2 200
```

This confirms:

* WAN egress is functional
* DNS resolution works
* TLS negotiation succeeds
* The added tools operate correctly in the deployed environment

---

## Design Philosophy

* **Separation of concerns**
  All local research customizations live outside NVIDIA-managed repositories.

* **Upstream-friendly**
  No forks, no direct edits, no merge conflicts.

* **Reproducible & auditable**
  Changes are explicit, scriptable, and easy to reapply after updates.

This structure is intended to scale cleanly as additional research-driven
Docker or runtime patches are introduced.

---

## Notes

* These patches only affect **runtime images**; build stages are intentionally
  left untouched.
* If the Sionna-RK directory structure changes upstream, update the target paths
  in `patch_oai_wan.sh` and `rebuild_srk_docker.sh` accordingly.
