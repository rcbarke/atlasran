#!/usr/bin/env bash
# uplink_test.sh
#
# CU/DU ablation throughput driver (UPLINK-focused)
#
# Primary objective:
#   Stress the uplink channel to load the O-DU LDPC decoder.
#
# This script:
#   - Launches iperf3 servers in UE container(s)
#   - Launches iperf3 client(s) in the traffic generator container using -R (reverse) for UL
#   - Always launches run_all_monitors.sh in parallel (same directory as this script)
#   - Writes iperf3 JSON outputs into the same run directory used by run_all_monitors.sh
#
# UE container naming:
#   UE1  -> oai-nr-ue
#   UE2+ -> oai-nr-ue2, oai-nr-ue3, ...
#
# UE IP inference:
#   --ue-ip is treated as UE1 IP.
#   If --num_ues N, script infers UE IPs by incrementing the base IPv4 address.
#   Example: --num_ues 12 --ue-ip 12.1.1.2 => 12.1.1.2 ... 12.1.1.13
#
# Protocol:
#   Default TCP. Optional -udp flag runs UDP saturated (-b 0).
#
# Notes:
#   - CN/DN bind IP is assumed fixed by default (override via --cn-ip if needed).
#   - This script is intended to be run from the SRK host (not inside a container).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_ALL_MONITORS="${SCRIPT_DIR}/run_all_monitors.sh"

# ---------------- Defaults ----------------
CN_IP="192.168.72.135"         # bind IP used by iperf3 client (inside DN container)
DN_CONTAINER="oai-ext-dn"      # traffic generator container
UE_BASE_CONTAINER="oai-nr-ue"  # UE1 container name
UE1_IP=""                      # required if --num_ues >= 1
NUM_UES=1
DURATION_S=60
INTERVAL_S=1
UDP=0
NO_GPU=0

# Extra args forwarded to run_all_monitors.sh after `--`
MONITOR_EXTRA_ARGS=()

usage() {
  cat <<USAGE_EOF
Usage:
  $(basename "$0") [options] [-- MONITOR_EXTRA_ARGS...]

Options:
  --num_ues N            Number of UE containers to test (default: 1). If 0, bypass iperf3.
  --ue-ip IPv4           UE1 IP address (required if --num_ues >= 1), e.g. 12.1.1.2
  --duration-s SEC       Test duration seconds (default: 60). Used for iperf3 + monitors.
  --interval-s SEC       iperf3 reporting interval (default: 1)
  --cn-ip IPv4           Bind IP for iperf3 client inside DN container (default: ${CN_IP})
  --dn-container NAME    DN / traffic generator container (default: ${DN_CONTAINER})
  -udp                   Use UDP (saturated) instead of TCP (default: TCP)
  --no-gpu               Pass through to run_all_monitors.sh to disable GPU monitors
  -h, --help             Show this help

Examples:
  # 1 UE TCP uplink stress
  $(basename "$0") --num_ues 1 --ue-ip 12.1.1.2 --duration-s 60

  # 12 UE UDP uplink stress (UE1=12.1.1.2 -> UE12=12.1.1.13)
  $(basename "$0") --num_ues 12 --ue-ip 12.1.1.2 -udp --duration-s 60

  # Baseline monitoring (no UE traffic)
  $(basename "$0") --num_ues 0 --duration-s 60 --no-gpu

Notes:
  - Starts iperf3 servers inside UE container(s) and clients inside ${DN_CONTAINER} using -R (uplink).
  - Outputs are written into the run directory created by run_all_monitors.sh.
USAGE_EOF
}

# ---------------- Helpers ----------------
require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found on PATH: $cmd" >&2
    exit 2
  fi
}

ip_to_int() {
  local ip="$1"
  local a b c d
  IFS=. read -r a b c d <<<"$ip"
  if [[ -z "${a:-}" || -z "${b:-}" || -z "${c:-}" || -z "${d:-}" ]]; then
    echo "ERROR: invalid IPv4 address: $ip" >&2
    return 2
  fi
  echo $(( (a << 24) + (b << 16) + (c << 8) + d ))
}

int_to_ip() {
  local x="$1"
  echo "$(( (x >> 24) & 255 )).$(( (x >> 16) & 255 )).$(( (x >> 8) & 255 )).$(( x & 255 ))"
}

ue_container_name() {
  local idx="$1"
  if [[ "$idx" -eq 1 ]]; then
    echo "${UE_BASE_CONTAINER}"
  else
    echo "${UE_BASE_CONTAINER}${idx}"
  fi
}

# Busy-wait until epoch_ms (uses python for portability)
wait_until_epoch_ms() {
  local target_ms="$1"
  python3 - "$target_ms" <<'PY'
import sys, time
target = int(sys.argv[1])
while True:
    now = int(time.time()*1000)
    if now >= target:
        break
    time.sleep(min(0.05, (target-now)/1000.0))
PY
}

# Start an iperf3 server inside a UE container (one-off: exits after one test)
start_iperf_server() {
  local ue_container="$1"
  local port="$2"
  docker exec -d "$ue_container" sh -lc "iperf3 -s -1 -p ${port} >/tmp/iperf3_server_${port}.log 2>&1"
}

# Kill any lingering iperf3 servers in a UE container (best effort)
kill_iperf_servers() {
  local ue_container="$1"
  docker exec "$ue_container" sh -lc "pkill -f 'iperf3 -s' >/dev/null 2>&1 || true" || true
}

# Parse start_epoch_ms from run_all_monitors manifest
read_start_epoch_ms() {
  local manifest_path="$1"
  python3 - "$manifest_path" <<'PY'
import json, sys
p = sys.argv[1]
with open(p, "r") as f:
    j = json.load(f)
print(int(j["start_epoch_ms"]))
PY
}

# ---------------- Arg parsing ----------------
if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --num_ues)
      NUM_UES="$2"; shift 2;;
    --ue-ip|--ue_ip)
      UE1_IP="$2"; shift 2;;
    --duration-s|--duration)
      DURATION_S="$2"; shift 2;;
    --interval-s|--interval)
      INTERVAL_S="$2"; shift 2;;
    --cn-ip)
      CN_IP="$2"; shift 2;;
    --dn-container)
      DN_CONTAINER="$2"; shift 2;;
    --no-gpu)
      NO_GPU=1; shift;;
    -udp)
      UDP=1; shift;;
    -h|--help)
      usage; exit 0;;
    --)
      shift
      MONITOR_EXTRA_ARGS=("$@")
      break;;
    -*)
      echo "ERROR: unknown option: $1" >&2
      usage
      exit 2;;
    *)
      echo "ERROR: unexpected arg: $1" >&2
      usage
      exit 2;;
  esac
done

if ! [[ "$NUM_UES" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --num_ues must be a non-negative integer." >&2
  exit 2
fi

if ! [[ "$DURATION_S" =~ ^[0-9]+$ ]] || [[ "$DURATION_S" -le 0 ]]; then
  echo "ERROR: --duration-s must be a positive integer." >&2
  exit 2
fi

if ! [[ "$INTERVAL_S" =~ ^[0-9]+$ ]] || [[ "$INTERVAL_S" -le 0 ]]; then
  echo "ERROR: --interval-s must be a positive integer." >&2
  exit 2
fi

if [[ "$NUM_UES" -ge 1 ]]; then
  if [[ -z "$UE1_IP" ]]; then
    echo "ERROR: --ue-ip is required when --num_ues >= 1" >&2
    exit 2
  fi
fi

if [[ ! -x "$RUN_ALL_MONITORS" ]]; then
  echo "ERROR: run_all_monitors.sh not found or not executable at: $RUN_ALL_MONITORS" >&2
  exit 2
fi

require_cmd docker
require_cmd python3

# ---------------- Derived config ----------------
TS="$(date +%Y%m%d_%H%M%S)"
PROTO="tcp"
if [[ "$UDP" -eq 1 ]]; then
  PROTO="udp"
fi

RUN_DIR="${SCRIPT_DIR}/runs/${TS}_ues${NUM_UES}"
mkdir -p "$RUN_DIR"

IPERF_DIR="${RUN_DIR}/iperf3"
mkdir -p "$IPERF_DIR"

IPERF_PORT=5201

UE_CONTAINERS=()
UE_IPS=()

if [[ "$NUM_UES" -ge 1 ]]; then
  base_int="$(ip_to_int "$UE1_IP")"
  for i in $(seq 1 "$NUM_UES"); do
    UE_CONTAINERS+=("$(ue_container_name "$i")")
    UE_IPS+=("$(int_to_ip $((base_int + (i - 1))) )")
  done
fi

# ---------------- Run header ----------------
echo "========================================================================"
echo "UL Throughput + Monitoring (protocol=${PROTO^^})"
echo "  num_ues     : ${NUM_UES}"
if [[ "$NUM_UES" -ge 1 ]]; then
  echo "  ue_ip (UE1) : ${UE1_IP}  (inferred up to UE${NUM_UES}: ${UE_IPS[-1]})"
fi
echo "  cn bind ip  : ${CN_IP}"
echo "  dn container: ${DN_CONTAINER}"
echo "  duration    : ${DURATION_S}s"
echo "  interval    : ${INTERVAL_S}s"
echo "  run dir     : ${RUN_DIR}"
if [[ "$NO_GPU" -eq 1 ]]; then
  echo "  gpu monitors: disabled (--no-gpu)"
fi
echo "========================================================================"
echo

MONITOR_PID=""
CLIENT_PIDS=()

cleanup() {
  set +e
  echo
  echo "[cleanup] stopping iperf3 clients (best effort)..."
  for pid in "${CLIENT_PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done

  if [[ -n "${MONITOR_PID:-}" ]]; then
    if kill -0 "$MONITOR_PID" >/dev/null 2>&1; then
      echo "[cleanup] stopping run_all_monitors.sh (pid=${MONITOR_PID})..."
      kill "$MONITOR_PID" >/dev/null 2>&1 || true
    fi
  fi

  echo "[cleanup] stopping iperf3 servers in UE containers (best effort)..."
  for c in "${UE_CONTAINERS[@]:-}"; do
    kill_iperf_servers "$c"
  done
}
trap cleanup INT TERM EXIT

# ---------------- Start UE iperf3 servers ----------------
if [[ "$NUM_UES" -ge 1 ]]; then
  echo "[step] Starting iperf3 server(s) in UE container(s)..."
  for idx in "${!UE_CONTAINERS[@]}"; do
    c="${UE_CONTAINERS[$idx]}"
    ip="${UE_IPS[$idx]}"
    echo "  - UE$((idx+1)): container=${c} ip=${ip} port=${IPERF_PORT}"
    kill_iperf_servers "$c"
    start_iperf_server "$c" "$IPERF_PORT"
  done
  echo
else
  echo "[step] num_ues=0 -> skipping iperf3 traffic generation."
  echo
fi

# ---------------- Start monitors ----------------
MONITOR_ARGS=(--ues "$NUM_UES" --duration-s "$DURATION_S" --run-dir "$RUN_DIR")
if [[ "$NO_GPU" -eq 1 ]]; then
  MONITOR_ARGS+=(--no-gpu)
fi

echo "[step] Starting run_all_monitors.sh..."
echo "+ $RUN_ALL_MONITORS ${MONITOR_ARGS[*]} -- ${MONITOR_EXTRA_ARGS[*]:-}"
"$RUN_ALL_MONITORS" "${MONITOR_ARGS[@]}" -- "${MONITOR_EXTRA_ARGS[@]}" >"$RUN_DIR/run_all_monitors.launch.log" 2>&1 &
MONITOR_PID=$!
echo "  run_all_monitors.sh pid=${MONITOR_PID}"
echo

MANIFEST_PATH="$RUN_DIR/run_manifest.json"
echo "[step] Waiting for monitor manifest: $MANIFEST_PATH"
for _ in $(seq 1 300); do
  if [[ -f "$MANIFEST_PATH" ]]; then
    break
  fi
  sleep 0.01
done
if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "ERROR: monitor manifest not found after waiting. Check $RUN_DIR/run_all_monitors.launch.log" >&2
  exit 3
fi

START_EPOCH_MS="$(read_start_epoch_ms "$MANIFEST_PATH")"
echo "  monitor start_epoch_ms=${START_EPOCH_MS}"
echo

# ---------------- Start iperf3 clients (UL reverse mode) ----------------
if [[ "$NUM_UES" -ge 1 ]]; then
  echo "[step] Synchronizing: launching iperf3 client(s) at start_epoch_ms..."
  wait_until_epoch_ms "$START_EPOCH_MS"

  BASE_ARGS=(-t "$DURATION_S" -i "$INTERVAL_S" -B "$CN_IP" -J -p "$IPERF_PORT")
  UDP_ARGS=()
  if [[ "$UDP" -eq 1 ]]; then
    UDP_ARGS=(-u -b 0)
  fi

  for idx in "${!UE_IPS[@]}"; do
    ip="${UE_IPS[$idx]}"
    ue_container="${UE_CONTAINERS[$idx]}"

    OUT_JSON="${IPERF_DIR}/uplink_${PROTO}_ue$((idx+1))_${ip}_${TS}.json"
    OUT_ERR="${IPERF_DIR}/uplink_${PROTO}_ue$((idx+1))_${ip}_${TS}.stderr.log"

    echo "  - UL UE$((idx+1)) ${ue_container} (${ip}) -> ${OUT_JSON}"
    docker exec "$DN_CONTAINER" iperf3 "${UDP_ARGS[@]}" "${BASE_ARGS[@]}" -c "$ip" -R >"$OUT_JSON" 2>"$OUT_ERR" &
    CLIENT_PIDS+=("$!")
  done
  echo
fi

# ---------------- Wait for completion ----------------
echo "[step] Waiting for completion..."
EXIT_CODE=0

if [[ "$NUM_UES" -ge 1 ]]; then
  for pid in "${CLIENT_PIDS[@]}"; do
    if ! wait "$pid"; then
      EXIT_CODE=4
    fi
  done
fi

if [[ -n "${MONITOR_PID:-}" ]]; then
  if ! wait "$MONITOR_PID"; then
    EXIT_CODE=5
  fi
fi

echo
echo "========================================================================"
echo "Done."
echo "  run_dir       : $RUN_DIR"
echo "  iperf outputs : $IPERF_DIR"
echo "  monitors log  : $RUN_DIR/run_all_monitors.launch.log"
if [[ "$EXIT_CODE" -ne 0 ]]; then
  echo "  status        : FAILED (exit_code=$EXIT_CODE)"
else
  echo "  status        : OK"
fi
echo "========================================================================"

exit "$EXIT_CODE"
