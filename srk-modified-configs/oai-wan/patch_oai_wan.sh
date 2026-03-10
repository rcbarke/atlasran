#!/usr/bin/env bash
#
# patch_oai_wan.sh
#
# Purpose:
#   Patches NVIDIA Sionna-RK’s OpenAirInterface (OAI) Dockerfiles to enable
#   WAN connectivity tools (e.g., curl, wget) inside the runtime gNB and UE
#   containers. This is required for research workflows involving external
#   downloads, telemetry, and load-testing utilities.
#
# Design:
#   - Keeps all modifications in a parallel repository (srk-modified-configs)
#     to avoid direct edits to NVIDIA-managed infrastructure.
#   - Copies pre-modified Dockerfiles into the Sionna-RK OAI docker directory.
#   - Fails fast if required files or target paths are missing.
#
# Assumptions:
#   - This script is executed from srk-modified-configs/oai-docker/
#   - The Sionna-RK repository exists at:
#       ../../sionna-rk/ext/openairinterface5g/docker/
#
# Usage:
#   ./patch_oai_wan.sh
#
# Follow-up:
#   After patching, rebuild the OAI images using build-oai-images.sh
#

#!/usr/bin/env bash
set -euo pipefail

# Files we expect locally
FILES=(
  "Dockerfile.gNB.ubuntu.cuda"
  "Dockerfile.nrUE.ubuntu.cuda"
)
COMPOSE=(
  "docker-compose.yaml"
)

# Target directory relative to this script
TARGET_DIR="../../sionna-rk/ext/openairinterface5g/docker"
TARGET_COMPOSE_DIR="../../sionna-rk/config/common"

echo "[INFO] Patching OAI Dockerfiles for WAN tools (curl/wget)..."

# Necessary at systems-level on 5GC host
sudo sysctl -w net.ipv4.conf.all.forwarding=1
sudo iptables -P FORWARD ACCEPT

# Ensure we are running from the directory containing the Dockerfiles
for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "[ERROR] Required file not found in current directory: $f"
    exit 1
  fi
done

# Ensure target directory exists
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "[ERROR] Target directory does not exist: $TARGET_DIR"
  exit 1
fi

# Copy files
for f in "${FILES[@]}"; do
  echo "[INFO] Copying $f -> $TARGET_DIR"
  cp "$f" "$TARGET_DIR/"
done

for c in "${COMPOSE[@]}"; do
  echo "[INFO] Copying $c -> $TARGET_COMPOSE_DIR"
  cp "$c" "$TARGET_COMPOSE_DIR/"
done

echo "[SUCCESS] OAI Dockerfiles patched successfully."
echo "[NEXT] Rebuild images using build-oai-images.sh"

