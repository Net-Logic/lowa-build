#!/usr/bin/env bash
# Run all tests of the recipe (shell and Python)
set -uo pipefail
cd "$(dirname "$0")/.."
status=0
for t in tests/test_*.sh; do echo "== $t"; bash "$t" || status=1; done
for t in tests/test_*.py; do [ -e "$t" ] || continue; echo "== $t"; python3 -I "$t" || status=1; done
exit $status
