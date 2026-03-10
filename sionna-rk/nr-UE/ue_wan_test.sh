#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Configuration
# -----------------------------
UE_CONTAINER="${UE_CONTAINER:-oai-nr-ue}"
UE_IFACE="${UE_IFACE:-oaitun_ue1}"
PING_IP="${PING_IP:-8.8.8.8}"
DNS_TEST_HOST="${DNS_TEST_HOST:-google.com}"
CURL_IFCONFIG_URL="${CURL_IFCONFIG_URL:-ifconfig.me}"

# -----------------------------
# Helpers
# -----------------------------
log() {
  echo -e "\n[$(date '+%H:%M:%S')] $*"
}

die() {
  echo -e "\n[ERROR] $*" >&2
  exit 1
}

docker_exec() {
  docker exec -it "${UE_CONTAINER}" bash -lc "$*"
}

# -----------------------------
# Pre-flight checks
# -----------------------------
log "Checking UE container: ${UE_CONTAINER}"
docker ps --format '{{.Names}}' | grep -qx "${UE_CONTAINER}" \
  || die "UE container '${UE_CONTAINER}' is not running"

log "Checking UE tunnel interface: ${UE_IFACE}"
docker_exec "ip link show ${UE_IFACE} >/dev/null 2>&1" \
  || die "Interface ${UE_IFACE} not found in UE container"

# -----------------------------
# Test 1: Raw IP reachability
# -----------------------------
log "Test 1: ICMP reachability to ${PING_IP} via ${UE_IFACE}"
docker_exec "ping -c 3 -I ${UE_IFACE} ${PING_IP}"

# -----------------------------
# Test 2: DNS resolution
# -----------------------------
log "Test 2: DNS resolution + ICMP to ${DNS_TEST_HOST} via ${UE_IFACE}"
docker_exec "ping -c 2 -I ${UE_IFACE} ${DNS_TEST_HOST}"

# -----------------------------
# Test 3: Public WAN + NAT
# -----------------------------
log "Test 3: Public WAN egress (curl via ${UE_IFACE})"
PUBLIC_IP="$(docker_exec "curl -4 --interface ${UE_IFACE} ${CURL_IFCONFIG_URL}")"

log "UE public egress IP: ${PUBLIC_IP}"

# -----------------------------
# Test 4: Post-egress stability check
# -----------------------------
log "Test 4: Post-egress ICMP stability check"
docker_exec "ping -c 3 -I ${UE_IFACE} ${PING_IP}"

# -----------------------------
# Success
# -----------------------------
log "WAN TEST PASSED ✔"
exit 0

