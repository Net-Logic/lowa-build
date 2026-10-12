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

step_image() {
	docker build -t "$IMAGE" \
		--build-arg BASE_IMAGE="$BASE_IMAGE" --build-arg EMSDK_VERSION="$EMSDK_VERSION" --build-arg EMSDK_COMMIT="$EMSDK_COMMIT" \
		--build-arg UID="$(id -u)" --build-arg GID="$(id -g)" \
		"$ROOT/docker"
}

# Apply the patches of $2 (*.patch, in name order) to the tree $1, once. A stamp records the applied set.
apply_patches() {
	local src="$1" dir="$2" stamp="$1/.lowa-patches" want p
	want=$(cd "$dir" && sha256sum -- *.patch 2>/dev/null || true)
	if [ -f "$stamp" ]; then
		if [ "$(cat "$stamp")" = "$want" ]; then
			return 0
		fi
		echo "The patches changed since $src was patched: delete $src and run ./build.sh fetch again" >&2
		return 1
	fi
	for p in "$dir"/*.patch; do
		[ -e "$p" ] || continue
		patch -d "$src" -p1 --dry-run -s < "$p" || { echo "Patch does not apply: $p" >&2; return 1; }
		patch -d "$src" -p1 -s < "$p"
		echo "Applied $(basename "$p")"
	done
	echo "$want" > "$stamp"
}

step_fetch() {
	local t f src="$WORK/src/libreoffice-$LO_VERSION"
	for t in $LO_TARBALLS; do
		for f in "$t" "$t.asc"; do
			if [ ! -f "$WORK/dl/$f" ]; then
				curl -fL --retry 3 -o "$WORK/dl/$f.part" "$LO_SRC_URL/$f"
				mv "$WORK/dl/$f.part" "$WORK/dl/$f"
			fi
		done
		gpg --batch --status-fd 1 --verify "$WORK/dl/$t.asc" "$WORK/dl/$t" 2>/dev/null | grep -q "VALIDSIG $LO_SIGNING_KEY" \
			|| { echo "Bad or missing signature for $t (key $LO_SIGNING_KEY)" >&2; return 1; }
	done
	(cd "$WORK/dl" && sha256sum -c --quiet "$ROOT/checksums.sha256")
	if [ ! -d "$src" ]; then
		for t in $LO_TARBALLS; do
			tar -C "$WORK/src" -xf "$WORK/dl/$t"
		done
	fi
	apply_patches "$src" "$ROOT/patches/core"
}

# Bash reads a script while it runs: everything is parsed before the first step (build.sh is edited
# while long steps run in the background)
main() {
	case "${1:-all}" in
		preflight) step_preflight ;;
		status) step_status ;;
		image) step_image ;;
		fetch) step_fetch ;;
		*) echo "Usage: $0 [all|preflight|image|fetch|qt|lo|collect|status]" >&2; exit 2 ;;
	esac
}

main "$@"; exit
