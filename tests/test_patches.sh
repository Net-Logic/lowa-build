#!/usr/bin/env bash
# Tests of apply_patches (build.sh): applies once, refuses a changed patch set, fails loudly on a bad patch
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh
eval "$(sed -n '/^apply_patches() {/,/^}/p' build.sh)"
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: expected '$2', got '$3'"; fails=$((fails + 1)); fi; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/src" "$T/p"
printf 'a\nb\n' > "$T/src/f.txt"
printf -- '--- a/f.txt\n+++ b/f.txt\n@@ -1,2 +1,2 @@\n a\n-b\n+c\n' > "$T/p/0001-x.patch"
apply_patches "$T/src" "$T/p" >/dev/null; check "applies" 0 "$?"
check "content patched" "c" "$(sed -n 2p "$T/src/f.txt")"
apply_patches "$T/src" "$T/p" >/dev/null; check "second run is a no-op" 0 "$?"
check "not patched twice" "c" "$(sed -n 2p "$T/src/f.txt")"
echo '# changed' >> "$T/p/0001-x.patch"
apply_patches "$T/src" "$T/p" >/dev/null 2>&1; check "changed patch set refused" 1 "$?"
rm -f "$T/src/.lowa-patches"; printf 'z\ny\n' > "$T/src/f.txt"
apply_patches "$T/src" "$T/p" >/dev/null 2>&1; check "non-applying patch fails" 1 "$?"
check "tree left as is" "y" "$(sed -n 2p "$T/src/f.txt")"
[ "$fails" -eq 0 ]
