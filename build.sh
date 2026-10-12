#!/usr/bin/env bash
# One-command LibreOffice WebAssembly build for the Office Editor module.
# Usage: ./build.sh [all|preflight|image|fetch|qt|lo|collect|status]
#   all (default): preflight, then every step in the background; log in out/<label>/build.log
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
. "$ROOT/versions.env"
set +a
. "$ROOT/scripts/lib.sh"
WORK="$ROOT/work"
LABEL="${LO_VERSION}-nl${BUILD_NUMBER}"
OUT="$ROOT/out/$LABEL"
IMAGE="lowa-build:emsdk-${EMSDK_VERSION}"
mkdir -p "$WORK/dl" "$WORK/src" "$WORK/tarballs" "$WORK/ccache" "$WORK/stats" "$OUT"

step_preflight() {
	lowa_preflight "$WORK" || return 1
	echo "Preflight ok: $(lowa_free_disk_gb "$WORK") GB free, swap $(lowa_meminfo_gb SwapTotal) GB, RAM available $(lowa_meminfo_gb MemAvailable) GB"
}

step_status() {
	tail -n 15 "$OUT/build.log" 2>/dev/null || echo "No build log yet: $OUT/build.log"
	docker ps --filter name=lowa- --format '{{.Names}} {{.Status}}'
	docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' $(docker ps -q --filter name=lowa-) 2>/dev/null || true
	echo "Free disk: $(lowa_free_disk_gb "$WORK") GB"
}

case "${1:-all}" in
	preflight) step_preflight ;;
	status) step_status ;;
	*) echo "Usage: $0 [all|preflight|image|fetch|qt|lo|collect|status]" >&2; exit 2 ;;
esac
