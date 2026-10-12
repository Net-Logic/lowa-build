#!/usr/bin/env bash
# Tests of scripts/lib.sh (host helpers). Run: bash tests/test_lib.sh
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh
fails=0
check() { # $1 = description, $2 = expected, $3 = actual
	if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: expected '$2', got '$3'"; fails=$((fails + 1)); fi
}
export LOWA_MEMINFO=tests/fixtures/meminfo
check "MemAvailable GB" 6 "$(lowa_meminfo_gb MemAvailable)"
check "SwapTotal GB" 8 "$(lowa_meminfo_gb SwapTotal)"
check "SwapFree GB" 5 "$(lowa_meminfo_gb SwapFree)"
check "jobs from 6 GB" 3 "$(lowa_jobs 6 6)"
check "jobs capped" 6 "$(lowa_jobs 15 6)"
check "jobs at least 1" 1 "$(lowa_jobs 1 6)"
check "container swap keeps 4 GB" 1 "$(lowa_container_swap_gb 5)"
check "container swap never negative" 0 "$(lowa_container_swap_gb 2)"
check "forced free disk" 42 "$(LOWA_DF_AVAIL_GB=42 lowa_free_disk_gb /)"
MIN_FREE_DISK_GB=60 MIN_SWAP_GB=32 LOWA_DF_AVAIL_GB=100 lowa_preflight /tmp >/dev/null; check "preflight fails on small swap" 1 "$?"
out=$(MIN_FREE_DISK_GB=60 MIN_SWAP_GB=32 LOWA_DF_AVAIL_GB=100 lowa_preflight /tmp)
check "preflight prints the swapfile command" 1 "$(grep -c 'sudo fallocate -l 24G' <<<"$out")"
MIN_FREE_DISK_GB=60 MIN_SWAP_GB=8 LOWA_DF_AVAIL_GB=50 lowa_preflight /tmp >/dev/null; check "preflight fails on small disk" 1 "$?"
MIN_FREE_DISK_GB=60 MIN_SWAP_GB=8 LOWA_DF_AVAIL_GB=70 lowa_preflight /tmp >/dev/null; check "preflight passes" 0 "$?"
LOWA_DF_AVAIL_GB=4 lowa_disk_low / 5; check "disk low below 5" 0 "$?"
LOWA_DF_AVAIL_GB=6 lowa_disk_low / 5; check "disk not low at 6" 1 "$?"
lowa_is_oom_exit 137; check "137 is OOM" 0 "$?"
lowa_is_oom_exit 2; check "2 is not OOM" 1 "$?"
[ "$fails" -eq 0 ]
