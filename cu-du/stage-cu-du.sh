#!/usr/bin/env bash
set -euo pipefail

# stage-cu-du.sh
# Copies CU/DU split config artifacts from the current directory into the sionna-rk repo tree.

# Paths relative to *this script's* directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC_COMPOSE="${SCRIPT_DIR}/docker-compose.yaml"
SRC_COMPOSE_OVERRIDE="${SCRIPT_DIR}/docker-compose.override.yaml"
SRC_ENV="${SCRIPT_DIR}/.env"
SRC_CU_CONF="${SCRIPT_DIR}/gnb-cu.sa.f1.band78.106prbs.conf"
SRC_DU_CONF="${SCRIPT_DIR}/gnb-du.sa.f1.band78.106prbs.rfsim.e2.conf"
SRC_START="${SCRIPT_DIR}/start_system.sh"

DST_BASE="${SCRIPT_DIR}/../../sionna-rk"
DST_COMMON="${DST_BASE}/config/common"
DST_RFSIM="${DST_BASE}/config/rfsim"
DST_SCRIPTS="${DST_BASE}/scripts"

# If 1, make timestamped backups of destination files before overwriting.
BACKUP="${BACKUP:-1}"

ts() { date +"%Y%m%d-%H%M%S"; }

die() {
  echo "ERROR: $*" >&2
  exit 1
}

need_file() {
  local f="$1"
  [[ -f "$f" ]] || die "Missing source file: $f"
}

mkdirs() {
  mkdir -p "$DST_COMMON" "$DST_RFSIM" "$DST_SCRIPTS"
}

backup_if_exists() {
  local dst="$1"
  [[ "$BACKUP" == "1" ]] || return 0
  if [[ -f "$dst" ]]; then
    local bkp="${dst}.bak.$(ts)"
    cp -a "$dst" "$bkp"
    echo "Backup: $dst -> $bkp"
  fi
}

copy_one() {
  local src="$1"
  local dst="$2"
  backup_if_exists "$dst"
  cp -a "$src" "$dst"
  echo "Copied: $src -> $dst"
}

main() {
  # Validate sources exist
  need_file "$SRC_COMPOSE"
  need_file "$SRC_COMPOSE_OVERRIDE"
  need_file "$SRC_ENV"
  need_file "$SRC_CU_CONF"
  need_file "$SRC_DU_CONF"
  need_file "$SRC_START"

  # Validate destination root exists
  [[ -d "$DST_BASE" ]] || die "Destination repo not found at: $DST_BASE (expected ../../sionna-rk from this script)"

  mkdirs

  # 1) docker-compose.yaml -> ../../sionna-rk/config/common/
  copy_one "$SRC_COMPOSE" "${DST_COMMON}/docker-compose.yaml"
  copy_one "$SRC_COMPOSE_OVERRIDE" "${DST_COMMON}/docker-compose.override.yaml"

  # 2) .env -> ../../sionna-rk/config/rfsim
  copy_one "$SRC_ENV" "${DST_RFSIM}/.env"

  # 3) gnb-cu... -> ../../sionna-rk/config/common/
  copy_one "$SRC_CU_CONF" "${DST_COMMON}/$(basename "$SRC_CU_CONF")"

  # 4) gnb-du... -> ../../sionna-rk/config/common/
  copy_one "$SRC_DU_CONF" "${DST_COMMON}/$(basename "$SRC_DU_CONF")"

  # 5) start_system.sh -> ../../sionna-rk/scripts/
  copy_one "$SRC_START" "${DST_SCRIPTS}/start_system.sh"


# 6) mcs_cu-du_xapp/ -> ../../sionna-rk/plugins/ric_xapps/src/
SRC_XAPP_DIR="${SCRIPT_DIR}/mcs_cu-du_xapp"
DST_XAPP_SRC="${DST_BASE}/plugins/ric_xapps/src"

[[ -d "$SRC_XAPP_DIR" ]] || die "Missing source directory: $SRC_XAPP_DIR"
mkdir -p "$DST_XAPP_SRC"

# Copy all files (recursively), preserving relative paths under mcs_cu-du_xapp/
while IFS= read -r -d '' f; do
  rel="${f#${SRC_XAPP_DIR}/}"
  dst="${DST_XAPP_SRC}/${rel}"
  mkdir -p "$(dirname "$dst")"
  copy_one "$f" "$dst"
done < <(find "$SRC_XAPP_DIR" -type f -print0)

  echo
  echo "Done."
  echo "Tip: set BACKUP=0 to disable backups (e.g., BACKUP=0 ./stage-cu-du.sh)"
}

main "$@"
