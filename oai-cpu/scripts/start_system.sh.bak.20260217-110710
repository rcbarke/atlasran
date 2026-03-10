#!/bin/bash
#
# SPDX-FileCopyrightText: Copyright (c) 2024-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

set -e  # Stop script on any error

# supress outputs from pushd and popd
function pushd() {
  command pushd "$@" > /dev/null
}

function popd() {
  command popd "$@" > /dev/null
}

function usage() {
  echo "Usage: $0 <config_name> [--num-ues <N>] [-h|--help]"
  echo
  echo "Options:"
  echo "  --num-ues <N>   Number of UE containers to start sequentially (default: 12)"
  echo "  -h, --help      Show this help"
  echo
  echo "Examples:"
  echo "  $0 rfsim"
  echo "  $0 rfsim --num-ues 12"
  echo "  $0 rfsim-fast --num-ues 12"
}

# defaults
CONFIG_NAME="rfsim"
NUM_UES=12

# Parse args (backward compatible: first non-flag token is config name)
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --num-ues|--num_ues)
      if [[ $# -lt 2 ]]; then
        echo "Error: missing value after $1"
        usage
        exit 1
      fi
      NUM_UES="$2"
      shift 2
      ;;
    *)
      # Treat the first non-flag token as CONFIG_NAME (allows custom config dirs like rfsim-12ue, rfsim-fast, etc.)
      if [[ "$1" != -* && "$CONFIG_NAME" == "rfsim" ]]; then
        CONFIG_NAME="$1"
        shift
      else
        echo "Error: unknown argument: $1"
        usage
        exit 1
      fi
      ;;
  esac
done

# Compute paths
configs_dir=$(realpath $(dirname "${BASH_SOURCE[0]}")/../config)
env_file="${configs_dir}/${CONFIG_NAME}/.env"

# Validate config
if [[ ! -f "$env_file" ]]; then
    echo "Error: .env file not found at $env_file"
    echo "Usage: $0 <config_name> [--num-ues <N>]"
    exit 1
fi

# Validate NUM_UES is a positive integer
if ! [[ "$NUM_UES" =~ ^[0-9]+$ ]] || [[ "$NUM_UES" -lt 1 ]]; then
  echo "Error: --num-ues must be a positive integer (got: $NUM_UES)"
  exit 1
fi

# change into common config directory
pushd "${configs_dir}/common"

echo "Using config: $CONFIG_NAME (env: $env_file)"
echo "Deploying $NUM_UES UE(s)..."

echo "Starting 5G Core network"
docker compose --env-file "$env_file" up -d mysql oai-amf oai-smf oai-upf oai-ext-dn nearRT-RIC

# Function to wait until a container is healthy
wait_for_container() {
    container_name=$1
    timeout=60  # Set timeout in seconds
    start_time=$(date +%s)
    echo "Waiting for $container_name to be healthy (Timeout: ${timeout}s)..."
    while true; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "not_found")

        if [[ "$status" == "healthy" ]]; then
            echo "$container_name is ready!"
            return 0
        elif [[ "$status" == "unhealthy" ]]; then
            echo "Error: $container_name became unhealthy! Exiting..."
            exit 1
        elif [[ "$status" == "not_found" ]]; then
            echo "Error: Container $container_name not found! Exiting..."
            exit 1
        fi

        # Check if timeout is reached
        current_time=$(date +%s)
        elapsed_time=$((current_time - start_time))
        if [[ $elapsed_time -ge $timeout ]]; then
            echo "Error: Timeout reached while waiting for $container_name! Exiting..."
            exit 1
        fi

        sleep 2
    done
}

# Wait for each service to be healthy
wait_for_container "oai-mysql"
wait_for_container "oai-amf"
wait_for_container "oai-smf"
wait_for_container "oai-upf"
wait_for_container "oai-ext-dn"

echo "All services are up and healthy!"

echo "Starting OAI CU (oai-nr-cu)"
docker compose --env-file "$env_file" up -d oai-nr-cu
wait_for_container "oai-nr-cu"

echo "Starting OAI DU (oai-nr-du)"
docker compose --env-file "$env_file" up -d oai-nr-du
wait_for_container "oai-nr-du"

# Start UEs only for rfsim configs
if [[ "$CONFIG_NAME" == *"rfsim"* ]]; then
  echo "gNB ready to connect"
  echo "Starting ${NUM_UES} nr-ue container(s) sequentially"

  # UE1 service name is "oai-nr-ue" (container_name: oai-nr-ue)
  echo "Starting nr-ue: oai-nr-ue (UE1)"
  docker compose --env-file "$env_file" up -d oai-nr-ue
  wait_for_container "oai-nr-ue"

  # UE2..UEN are "oai-nr-ue2"..."oai-nr-ueN"
  if [[ "$NUM_UES" -gt 1 ]]; then
    for (( i=2; i<=NUM_UES; i++ )); do
      svc="oai-nr-ue${i}"
      echo "Starting nr-ue: ${svc} (UE${i})"
      docker compose --env-file "$env_file" up -d "${svc}"
      wait_for_container "${svc}"
    done
  fi
fi

# Start xApp
docker compose --env-file "$env_file" up -d monitor_xapp

echo "5G network is ready to connect!"

# back to original directory
popd
