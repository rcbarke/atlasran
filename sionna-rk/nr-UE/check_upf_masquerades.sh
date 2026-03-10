#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Configuration
# -----------------------------
EXT_DN_CONTAINER="${EXT_DN_CONTAINER:-oai-ext-dn}"

# -----------------------------
# Helpers
# -----------------------------
die() {
  echo "[ERROR] $*" >&2
  exit 1
}

log() {
  echo "[INFO] $*"
}

# -----------------------------
# Pre-flight
# -----------------------------
docker ps --format '{{.Names}}' | grep -qx "${EXT_DN_CONTAINER}" \
  || die "Container '${EXT_DN_CONTAINER}' is not running"

# -----------------------------
# MASQUERADE check
# -----------------------------
log "Checking NAT MASQUERADE counters in ${EXT_DN_CONTAINER}"

MASQ_OUTPUT="$(docker exec -it "${EXT_DN_CONTAINER}" bash -lc \
  'iptables-legacy -t nat -L POSTROUTING -n -v | grep MASQUERADE || true')"

if [[ -z "${MASQ_OUTPUT}" ]]; then
  die "No MASQUERADE rule found in POSTROUTING table"
fi

echo "${MASQ_OUTPUT}"

# -----------------------------
# Optional: extract counters
# -----------------------------
PKTS="$(echo "${MASQ_OUTPUT}" | awk '{print $1}')"
BYTES="$(echo "${MASQ_OUTPUT}" | awk '{print $2}')"

log "MASQUERADE packets=${PKTS}, bytes=${BYTES}"

exit 0

