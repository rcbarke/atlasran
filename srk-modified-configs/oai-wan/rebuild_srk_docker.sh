#!/usr/bin/env bash
#
# rebuild_srk_docker.sh
#
# Purpose:
#   Rebuilds NVIDIA Sionna-RK OpenAirInterface (OAI) Docker images after local
#   Dockerfile modifications (e.g., WAN tooling, research instrumentation).
#
# Design:
#   - Invokes NVIDIA’s official build-oai-images.sh script to preserve
#     upstream behavior and compatibility.
#   - Uses the default Sionna-RK image tag ("latest") to align with the
#     standard docker-compose configuration.
#   - Executes from a parallel configuration repository to avoid modifying
#     NVIDIA-managed infrastructure code.
#
# Assumptions:
#   - This script is executed from srk-modified-configs/oai-docker/
#   - The Sionna-RK repository exists at:
#       ../../sionna-rk
#   - The OpenAirInterface source is located at:
#       ./ext/openairinterface5g (relative to Sionna-RK root)
#
# Usage:
#   ./rebuild_srk_docker.sh
#
# Notes:
#   - Safe to run repeatedly during iterative Dockerfile development.
#   - Restart running containers after rebuild to apply updated images.
#

set -euo pipefail

echo "[INFO] Rebuilding Sionna-RK OAI Docker images (tag: latest)"

# Relative path to Sionna-RK root
SRK_ROOT="../../sionna-rk"

# Sanity checks
if [[ ! -d "$SRK_ROOT" ]]; then
  echo "[ERROR] Sionna-RK directory not found at: $SRK_ROOT"
  exit 1
fi

if [[ ! -x "$SRK_ROOT/scripts/build-oai-images.sh" ]]; then
  echo "[ERROR] build-oai-images.sh not found or not executable"
  exit 1
fi

# Move into Sionna-RK root to match NVIDIA's expected invocation context
pushd "$SRK_ROOT" > /dev/null

echo "[INFO] Invoking NVIDIA build script"
echo "[INFO] Command: ./scripts/build-oai-images.sh --tag latest ./ext/openairinterface5g"

./scripts/build-oai-images.sh --tag latest ./ext/openairinterface5g

popd > /dev/null

echo "[SUCCESS] OAI Docker images rebuilt successfully."
echo "[NEXT] Restart services or redeploy via docker compose as needed."

