#!/usr/bin/env bash
set -euo pipefail

# run_all_monitors.sh
#
# Launch all CU/DU load-test monitoring streams in parallel with a shared start epoch.
# Designed for: <SRK_ROOT>/cu-du-abl/monitor/run_all_monitors.sh
#
# Streams:
#  01) GPU util          (nvidia-smi)
#  02) GPU power         (nvidia-smi)
#  03) oai-nr-cu CPU     (docker stats)
#  04) oai-nr-du CPU     (docker stats)
#  05) oai-nr-cu logs    (docker logs -f)
#  06) oai-nr-du logs    (docker logs -f)
#  07) ZMQ stats client  (SRK venv python wrapper)
#
# Usage (from SRK root or anywhere):
#   bash cu-du-abl/monitor/run_all_monitors.sh --ues 12
#
# Forward extra args to the ZMQ client (after --):
#   bash cu-du-abl/monitor/run_all_monitors.sh --ues 12 -- --host 127.0.0.1 --port 5555

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SRK_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# -------- defaults --------
SRK_ROOT="$DEFAULT_SRK_ROOT"
UES="NA"
INTERVAL="0.5"
SINCE="0s"
ZMQ_HOST="127.0.0.1"
ZMQ_PORT="5555"
START_DELAY_MS="100"
RUN_DIR=""
DURATION_S=""
NO_GPU=0

# Anything after `--` is forwarded to the ZMQ client wrapper.
ZMQ_EXTRA_ARGS=()

# -------- helpers --------
now_ms() {
  # GNU date supports %3N (milliseconds). If unavailable, fall back to python.
  if date +%s%3N >/dev/null 2>&1; then
    date +%s%3N
  else
    python3 - <<'PY'
import time
print(int(time.time()*1000))
PY
  fi
}

usage() {
  cat <<EOF
Usage:
  $0 [options] [-- ZMQ_CLIENT_ARGS...]

Options:
  --srk-root PATH         SRK root folder (default: inferred from script location)
  --ues N                 UE count label for run directory naming (default: NA)
  --run-dir PATH          Output directory (default: <srk-root>/runs/<timestamp>_ues<N>)
  --interval SEC          Sampling interval for GPU+CPU monitors (default: 0.5)
  --since DUR             docker logs --since value (default: 0s; starts from now)
  --zmq-host HOST         ZMQ host for zmq_stats_client.py (default: 127.0.0.1)
  --zmq-port PORT         ZMQ port (default: 5555)
  --start-delay-ms MS     Delay before shared start epoch (default: 100 ms)
  --duration-s SEC        Optional: stop all monitors after SEC seconds (default: run until Ctrl-C)
  --no-gpu                Disable GPU monitors (01/02) even if nvidia-smi exists
  -h, --help              Show this help

Examples:
  $0 --ues 12
  $0 --ues 6 --interval 1.0 --since 0s
  $0 --ues 12 -- --host 127.0.0.1 --port 5555
EOF
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found on PATH: $cmd" >&2
    exit 2
  fi
}

# -------- parse args --------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --srk-root)
      SRK_ROOT="$2"; shift 2;;
    --ues)
      UES="$2"; shift 2;;
    --run-dir)
      RUN_DIR="$2"; shift 2;;
    --interval)
      INTERVAL="$2"; shift 2;;
    --since)
      SINCE="$2"; shift 2;;
    --zmq-host)
      ZMQ_HOST="$2"; shift 2;;
    --zmq-port)
      ZMQ_PORT="$2"; shift 2;;
    --start-delay-ms)
      START_DELAY_MS="$2"; shift 2;;
    --duration-s)
      DURATION_S="$2"; shift 2;;
    --no-gpu)
      NO_GPU=1; shift;;
    -h|--help)
      usage; exit 0;;
    --)
      shift
      ZMQ_EXTRA_ARGS=("$@")
      break;;
    *)
      echo "ERROR: unknown arg: $1" >&2
      usage
      exit 2;;
  esac
done

SRK_ROOT="$(cd "$SRK_ROOT" && pwd)"

if [[ -z "$RUN_DIR" ]]; then
  TS="$(date +%Y%m%d_%H%M%S)"
  RUN_DIR="$SCRIPT_DIR/runs/${TS}_ues${UES}"
fi

mkdir -p "$RUN_DIR"

require_cmd docker

HAS_NVIDIA_SMI=0
if [[ "$NO_GPU" -eq 1 ]]; then
  HAS_NVIDIA_SMI=0
else
  if command -v nvidia-smi >/dev/null 2>&1; then
    HAS_NVIDIA_SMI=1
  fi
fi


START_MS="$(( $(now_ms) + START_DELAY_MS ))"

echo "Run directory: $RUN_DIR"
echo "SRK root:      $SRK_ROOT"
echo "UE label:      $UES"
echo "Start epoch:   $START_MS (epoch ms)"
echo "Interval:      $INTERVAL s"
echo "docker --since $SINCE"
echo "ZMQ:           ${ZMQ_HOST}:${ZMQ_PORT}"
if [[ -n "$DURATION_S" ]]; then
  echo "Duration:      $DURATION_S s"
else
  echo "Duration:      (until Ctrl-C)"
fi
echo

# Write a lightweight manifest for reproducibility
MANIFEST="$RUN_DIR/run_manifest.json"
HOSTNAME="$(hostname || true)"
UNAME="$(uname -a || true)"
DATE_ISO="$(date -Iseconds || true)"

cat > "$MANIFEST" <<EOF
{
  "created_at": "$DATE_ISO",
  "host": "$HOSTNAME",
  "uname": "$(echo "$UNAME" | sed 's/"/\\"/g')",
  "srk_root": "$SRK_ROOT",
  "run_dir": "$RUN_DIR",
  "ue_label": "$UES",
  "start_epoch_ms": $START_MS,
  "start_delay_ms": $START_DELAY_MS,
  "interval_s": $INTERVAL,
  "docker_logs_since": "$SINCE",
  "zmq_host": "$ZMQ_HOST",
  "zmq_port": $ZMQ_PORT,
  "zmq_extra_args": "$(printf '%q ' "${ZMQ_EXTRA_ARGS[@]}")"
}
EOF

# PID tracking / cleanup
PIDS=()
NAMES=()
PID_FILE="$RUN_DIR/pids.tsv"
echo -e "name\tpid" > "$PID_FILE"

start_bg() {
  local name="$1"; shift
  local stderr_file="$RUN_DIR/${name}.stderr.log"
  # shellcheck disable=SC2091
  ("$@" 2> >(tee -a "$stderr_file" >&2)) &
  local pid=$!
  PIDS+=("$pid")
  NAMES+=("$name")
  echo -e "${name}\t${pid}" >> "$PID_FILE"
  echo "Started: $name (pid=$pid)"
}

cleanup() {
  echo
  echo "Stopping monitors..."
  for i in "${!PIDS[@]}"; do
    pid="${PIDS[$i]}"
    name="${NAMES[$i]}"
    if kill -0 "$pid" >/dev/null 2>&1; then
      echo "  Killing $name (pid=$pid)"
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  # Give them a moment, then hard kill if needed
  sleep 0.5
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  done
  echo "Done. Outputs in: $RUN_DIR"
}

trap cleanup INT TERM EXIT

# -------- launch monitors --------

# GPU Utilization + Power
if [[ "$HAS_NVIDIA_SMI" -eq 1 ]]; then
  start_bg "01_gpu_util"  python3 "$SCRIPT_DIR/01_gpu_util_monitor.py"  --interval "$INTERVAL" --wait-until-epoch-ms "$START_MS" --out "$RUN_DIR/gpu_util.csv"
  start_bg "02_gpu_power" python3 "$SCRIPT_DIR/02_gpu_power_monitor.py" --interval "$INTERVAL" --wait-until-epoch-ms "$START_MS" --out "$RUN_DIR/gpu_power.csv"
else
  echo "WARN: nvidia-smi not found; skipping GPU monitors (01/02)."
fi

# CU/DU CPU Utilization
start_bg "03_cu_cpu" python3 "$SCRIPT_DIR/03_cpu_monitor_oai_nr_cu.py" --interval "$INTERVAL" --wait-until-epoch-ms "$START_MS" --out "$RUN_DIR/cu_cpu.csv"
start_bg "04_du_cpu" python3 "$SCRIPT_DIR/04_cpu_monitor_oai_nr_du.py" --interval "$INTERVAL" --wait-until-epoch-ms "$START_MS" --out "$RUN_DIR/du_cpu.csv"

# CU/DU Logs
start_bg "05_cu_logs" python3 "$SCRIPT_DIR/05_logs_follow_oai_nr_cu.py" --since "$SINCE" --wait-until-epoch-ms "$START_MS" --out "$RUN_DIR/cu_logs.tsv"
start_bg "06_du_logs" python3 "$SCRIPT_DIR/06_logs_follow_oai_nr_du.py" --since "$SINCE" --wait-until-epoch-ms "$START_MS" --out "$RUN_DIR/du_logs.tsv"

# ZMQ client wrapper (runs SRK venv python if present)
start_bg "07_zmq_client" python3 "$SCRIPT_DIR/07_zmq_stats_client_monitor.py" --srk-root "$SRK_ROOT" --wait-until-epoch-ms "$START_MS" --out "$RUN_DIR/zmq_stats.tsv" -- --host "$ZMQ_HOST" --port "$ZMQ_PORT" "${ZMQ_EXTRA_ARGS[@]}"

# Cumulative CPU utilization
start_bg "08_system_cpu" python3 "$SCRIPT_DIR/08_cpu_monitor_system.py" --interval "$INTERVAL" --wait-until-epoch-ms "$START_MS" --out "$RUN_DIR/system_cpu.csv"

echo
echo "All monitors started. PID list: $PID_FILE"
echo "Manifest: $MANIFEST"
echo

if [[ -n "$DURATION_S" ]]; then
  # Run for fixed duration, then exit (trap will cleanup).
  sleep "$DURATION_S"
  exit 0
fi

# Otherwise wait forever until Ctrl-C.
wait
