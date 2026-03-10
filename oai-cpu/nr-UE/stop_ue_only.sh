#!/usr/bin/env bash
#
# UE-only stop script for SRK-derived deployments.
# Stops only the UE container on this host (other components may be running elsewhere).
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
configs_dir="$(realpath "${SCRIPT_DIR}/../config")"

usage() {
  cat <<USAGE
Usage: $(basename "$0") <CONFIG_NAME>

Arguments:
  CONFIG_NAME   Name of config directory under ${configs_dir} (e.g., b200, rfsim)

Notes:
  - Uses ${configs_dir}/<CONFIG_NAME>/.env as the compose env file.
  - Runs docker compose from ${configs_dir}/common.
  - Stops/removes only the UE service/container.
USAGE
  exit 1
}

wait_for_container() {
  # Wait until the UE container is no longer running.
  # If the container does not exist, return success.
  local cname="$1"
  local timeout_s="${2:-30}"

  local start_ts now_ts
  start_ts="$(date +%s)"

  while true; do
    # If container doesn't exist, we're done
    if ! docker inspect "$cname" >/dev/null 2>&1; then
      return 0
    fi

    local state
    state="$(docker inspect -f '{{.State.Status}}' "$cname" 2>/dev/null || true)"

    if [[ "$state" != "running" && "$state" != "restarting" ]]; then
      return 0
    fi

    now_ts="$(date +%s)"
    if (( now_ts - start_ts > timeout_s )); then
      echo "Timed out waiting for container '$cname' to stop (status=$state)." >&2
      return 1
    fi

    sleep 1
  done
}

CONFIG_NAME="${1:-}"
if [[ -z "$CONFIG_NAME" ]]; then
  usage
fi

env_file="${configs_dir}/${CONFIG_NAME}/.env"
if [[ ! -f "$env_file" ]]; then
  echo "Env file not found: $env_file" >&2
  usage
fi

echo "Shutting down UE on this host (config: ${CONFIG_NAME})"

cd "${configs_dir}/common"

# Stop UE service (ignore if not running)
docker compose --env-file "$env_file" stop -t 10 oai-nr-ue || true

# Remove container to leave a clean slate (ignore if missing)
docker compose --env-file "$env_file" rm -f oai-nr-ue || true

# Wait until container is fully stopped/removed
wait_for_container "oai-nr-ue" 30 || true

echo "UE stopped: oai-nr-ue"
