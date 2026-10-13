#!/usr/bin/env bash
# step_lo resumes with 1 job after an out-of-memory kill, and only then
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh
eval "$(sed -n '/^step_lo() {/,/^}/p' build.sh)"
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: expected '$2', got '$3'"; fails=$((fails + 1)); fi; }
usable_ram_gb() { echo 8; }
MAX_JOBS=6
CALLS=""
run_step() { CALLS="$CALLS $1:$3"; [ "$1" = lo ] && return "$FIRST_RC"; return 0; }
FIRST_RC=137; CALLS=""; step_lo >/dev/null; check "OOM then retry ok" 0 "$?"; check "retry with 1 job" " lo:4 lo-retry:1" "$CALLS"
FIRST_RC=2; CALLS=""; step_lo >/dev/null; check "other failure not retried" 2 "$?"; check "single call" " lo:4" "$CALLS"
FIRST_RC=75; CALLS=""; step_lo >/dev/null; check "disk stop not retried" 75 "$?"; check "single call on disk stop" " lo:4" "$CALLS"
FIRST_RC=0; CALLS=""; step_lo >/dev/null; check "success" 0 "$?"; check "single call on success" " lo:4" "$CALLS"
[ "$fails" -eq 0 ]
