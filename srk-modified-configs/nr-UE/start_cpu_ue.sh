#!/bin/bash
#
# Minimal container start script for OAI CPU NR-UE on a remote host

set -e  # Stop script on any error

# suppress outputs from pushd and popd
function pushd() {
  command pushd "$@" > /dev/null
}

function popd() {
  command popd "$@" > /dev/null
}

# defaults
CONFIG_NAME=${1:-b200}
configs_dir=$(realpath $(dirname "${BASH_SOURCE[0]}")/../config)
env_file="${configs_dir}/${CONFIG_NAME}/.env"

# Validate config
if [[ ! -f "$env_file" ]]; then
    echo "Error: .env file not found at $env_file"
    echo "Usage: $0 [rfsim|b200|<custom>]"
    exit 1
fi

# change into common config directory
pushd "${configs_dir}/common"

echo "Using config: $CONFIG_NAME (env: $env_file)"

echo "Starting CPU UE only (this host does not start core/gNB/RIC containers)"

# Function to wait until a container is healthy (or running if no healthcheck)
wait_for_container() {
    container_name=$1
    timeout=60  # seconds
    start_time=$(date +%s)
    echo "Waiting for $container_name to be ready (Timeout: ${timeout}s)..."
    while true; do
        # Health status if present, else "no_healthcheck".
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no_healthcheck{{end}}' "$container_name" 2>/dev/null || echo "not_found")

        if [[ "$health" == "healthy" ]]; then
            echo "$container_name is healthy!"
            return 0
        elif [[ "$health" == "unhealthy" ]]; then
            echo "Error: $container_name became unhealthy! Exiting..."
            exit 1
        elif [[ "$health" == "not_found" ]]; then
            echo "Error: Container $container_name not found! Exiting..."
            exit 1
        elif [[ "$health" == "no_healthcheck" ]]; then
            # No healthcheck defined. Consider the container ready when it's running.
            state=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "not_found")
            if [[ "$state" == "running" ]]; then
                echo "$container_name is running (no healthcheck defined)."
                return 0
            elif [[ "$state" == "exited" ]]; then
                echo "Error: $container_name exited. Exiting..."
                docker logs --tail 200 "$container_name" || true
                exit 1
            elif [[ "$state" == "not_found" ]]; then
                echo "Error: Container $container_name not found! Exiting..."
                exit 1
            fi
        fi

        current_time=$(date +%s)
        elapsed_time=$((current_time - start_time))
        if [[ $elapsed_time -ge $timeout ]]; then
            echo "Error: Timeout reached while waiting for $container_name! Exiting..."
            docker logs --tail 200 "$container_name" || true
            exit 1
        fi

        sleep 2
    done
}

# Start only the UE service. The compose file is expected to reference the locally built
# CPU UE image (oai-nr-ue:latest) or an equivalent tag.
docker compose --env-file "$env_file" up -d oai-nr-ue

wait_for_container "oai-nr-ue"

echo "UE container is up. Next: configure RF/networking and bring up the remote core+gNB on the other host."

# back to original directory
popd
