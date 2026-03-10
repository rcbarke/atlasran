#!/bin/bash
#
# Build CPU-only OAI NR-UE Docker image (non-CUDA) for x86 hosts.
# Minimal, purpose-built wrapper for SRK-style workflows.
#
# Usage:
#   ./build-cpu-ue.sh [--tag <tag>] [--no-cache] [--ue-dockerfile <path>] <openairinterface5g_dir>
#
set -euo pipefail

# Directory where the script was invoked from
SCRIPT_CWD="$(pwd)"

# Local modified Dockerfile we want to inject
LOCAL_UE_DOCKERFILE="${SCRIPT_CWD}/Dockerfile.nrUE.ubuntu"

usage() {
  echo "Usage: $0 [--tag <tag>] [--no-cache] [--ue-dockerfile <path>] <openairinterface5g_dir>"
  exit 1
}

check_docker_group() {
  if id -nG "$USER" | grep -qw docker; then
    return 0
  fi
  echo "Error: $USER is not in the docker group."
  echo "Run: sudo usermod -aG docker $USER  (then log out/in)"
  exit 1
}

tag="latest"
cache_opts=""
ue_dockerfile=""

oai_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      ;;
    --tag)
      [[ $# -ge 2 ]] || usage
      tag="$2"
      shift 2
      ;;
    --no-cache)
      cache_opts="--no-cache"
      shift
      ;;
    --ue-dockerfile)
      [[ $# -ge 2 ]] || usage
      ue_dockerfile="$2"
      shift 2
      ;;
    *)
      oai_path="$1"
      shift
      ;;
  esac
done

[[ -n "$oai_path" ]] || usage

oai_path=$(realpath -sm "$oai_path")
[[ -d "$oai_path" ]] || { echo "Error: $oai_path does not exist"; exit 1; }

check_docker_group

# Default UE Dockerfile:
# 1) If a sibling Dockerfile (from SRK repo) is provided via --ue-dockerfile, use it.
# 2) Otherwise, prefer ../Dockerfile.nrUE.ubuntu relative to this script (SRK-style).
# 3) Finally, fall back to OAI's docker/Dockerfile.nrUE.ubuntu.
if [[ -z "$ue_dockerfile" ]]; then
  script_dir=$(realpath -sm "$(dirname "${BASH_SOURCE[0]}")")
  if [[ -f "${script_dir}/../Dockerfile.nrUE.ubuntu" ]]; then
    ue_dockerfile="${script_dir}/../Dockerfile.nrUE.ubuntu"
  else
    ue_dockerfile="${oai_path}/docker/Dockerfile.nrUE.ubuntu"
  fi
fi
ue_dockerfile=$(realpath -sm "$ue_dockerfile")
if [[ -f "${LOCAL_UE_DOCKERFILE}" ]]; then
    echo "[INFO] Injecting modified Dockerfile.nrUE.ubuntu into OAI repo"
    echo "       Source: ${LOCAL_UE_DOCKERFILE}"
    echo "       Target: ${ue_dockerfile}"
    cp -f "${LOCAL_UE_DOCKERFILE}" "${ue_dockerfile}"
else
    echo "[WARN] Local Dockerfile.nrUE.ubuntu not found at ${LOCAL_UE_DOCKERFILE}"
    echo "       Using existing Dockerfile in OAI repo"
fi
[[ -f "$ue_dockerfile" ]] || { echo "Error: UE Dockerfile not found at $ue_dockerfile"; exit 1; }

echo "OAI Path       : $oai_path"
echo "Tag            : $tag"
echo "UE Dockerfile  : $ue_dockerfile"

# NOTE: Dockerfile.nrUE.ubuntu expects these base images to exist:
#   ran-base:latest and ran-build:latest
# We'll tag both :$tag and :latest for convenience/compat.

pushd "$oai_path" >/dev/null

echo "== Building ran-base (CPU) =="
docker build --progress plain \
  $cache_opts --build-arg DOCKER_CUSTOM_IMAGE_TAG="${tag}" \
  --target ran-base --tag "ran-base:${tag}" --tag "ran-base:latest" \
  --file docker/Dockerfile.base.ubuntu .

echo "== Building ran-build (CPU) =="
docker build --progress plain \
  $cache_opts --build-arg DOCKER_CUSTOM_IMAGE_TAG="${tag}" \
  --target ran-build --tag "ran-build:${tag}" --tag "ran-build:latest" \
  --file docker/Dockerfile.build.ubuntu .

echo "== Building oai-nr-ue (CPU) =="
docker build --progress plain \
  $cache_opts --build-arg DOCKER_CUSTOM_IMAGE_TAG="${tag}" \
  --target oai-nr-ue --tag "oai-nr-ue:${tag}" \
  --file "$ue_dockerfile" .

popd >/dev/null

echo "Done. Built: oai-nr-ue:${tag} (plus ran-base/ran-build)"
