#!/bin/bash
#
# Quickstart: build CPU-only OAI NR-UE Docker image (non-CUDA) on x86.
# Minimal, organized workflow: clone OAI, init submodules, build UE-only.
#
# Usage:
#   ./quickstart-cpu-ue.sh --dest <openairinterface5g_dir> [--oai-version <tag>] [--tag <tag>] [--ue-dockerfile <path>] [--clean] [--no-build]
#
set -euo pipefail

usage() {
  echo "Usage: $0 [--dest <openairinterface5g_dir>] [--oai-version <oai-version>] [--tag <tag>] [--ue-dockerfile <path>] [--clean] [--no-build]"
  exit 1
}

TAG="latest"
OAI_VERSION="2025.w34"
dest_dir="./ext/openairinterface5g"
ue_dockerfile=""
clean_dest=0
no_build=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      ;;
    --dest)
      [[ $# -ge 2 ]] || usage
      dest_dir="$2"
      shift 2
      ;;
    --oai-version)
      [[ $# -ge 2 ]] || usage
      OAI_VERSION="$2"
      shift 2
      ;;
    --tag)
      [[ $# -ge 2 ]] || usage
      TAG="$2"
      shift 2
      ;;
    --ue-dockerfile)
      [[ $# -ge 2 ]] || usage
      ue_dockerfile="$2"
      shift 2
      ;;
    --clean)
      clean_dest=1
      shift
      ;;
    --no-build)
      no_build=1
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      ;;
  esac
done

[[ -n "$dest_dir" ]] || usage

dest_dir=$(realpath -sm "$dest_dir")

if [[ "$clean_dest" == "1" && -d "$dest_dir" ]]; then
  echo "Removing existing directory: $dest_dir"
  rm -rf "$dest_dir"
fi

if [[ -d "$dest_dir" ]]; then
  echo "Destination directory already exists: $dest_dir"
  echo "Use --clean or choose a different --dest"
  exit 1
fi

mkdir -p "$(dirname "$dest_dir")"

echo "== Cloning OpenAirInterface ($OAI_VERSION) =="
git clone --branch "$OAI_VERSION" https://gitlab.eurecom.fr/oai/openairinterface5g.git "$dest_dir"

echo "== Initializing submodules =="
pushd "$dest_dir" >/dev/null
git submodule update --init --recursive
popd >/dev/null

if [[ "$no_build" == "0" ]]; then
  script_dir=$(realpath -sm "$(dirname "${BASH_SOURCE[0]}")")
  build_script="${script_dir}/build-cpu-ue.sh"
  if [[ ! -x "$build_script" ]]; then
    echo "Error: build script not found or not executable: $build_script"
    exit 1
  fi

  extra=""
  if [[ -n "$ue_dockerfile" ]]; then
    extra="--ue-dockerfile $(realpath -sm "$ue_dockerfile")"
  fi

  echo "== Building CPU UE image only =="
  "$build_script" --tag "$TAG" $extra "$dest_dir"
fi

echo "Done. OAI repo at: $dest_dir"
