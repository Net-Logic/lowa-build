#!/usr/bin/env bash
# build.sh is edited while long steps run in the background. Bash reads a script as it runs, so text read
# after a step would come from the edited file at the old offset. Everything must be parsed before the
# first step starts: the only top-level command is the last line, `main "$@"; exit`.
set -uo pipefail
cd "$(dirname "$0")/.."
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: expected '$2', got '$3'"; fails=$((fails + 1)); fi; }
check "last line" 'main "$@"; exit' "$(grep -v '^[[:space:]]*$' build.sh | tail -n 1)"
check "single call of main" 1 "$(grep -c '^main ' build.sh)"
# Behaviour: a copy whose step sleeps, edited while it sleeps, must not run the appended text
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/scripts" && cp build.sh versions.env "$T/" && cp scripts/lib.sh "$T/scripts/"
sed -i 's/^\([[:space:]]*\)status) step_status ;;/\1sleepy) sleep 2 ;;\n&/' "$T/build.sh"
bash "$T/build.sh" sleepy > "$T/out.txt" 2>&1 &
pid=$!
sleep 1
printf '\necho APPENDED-RAN\n' >> "$T/build.sh"
sed -i '1i # shifted' "$T/build.sh"
wait $pid
check "edited script: exit status" 0 "$?"
check "edited script: appended text not run" 0 "$(grep -c 'APPENDED-RAN\|not found\|introuvable' "$T/out.txt")"
[ "$fails" -eq 0 ]
