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

# Container variables: every pin of versions.env
ENV_ARGS=()
for v in $(sed -n 's/^\([A-Z0-9_]*\)=.*/\1/p' "$ROOT/versions.env"); do ENV_ARGS+=(-e "$v"); done

# Every 30 s: record the memory peaks of container $1 into work/stats/$2.peak, stop it if the disk is nearly full
watch_container() {
	local name="$1" step="$2" dir
	while sleep 30; do
		docker inspect "$name" >/dev/null 2>&1 || return 0
		dir=$(lowa_cgroup_dir "$name")
		echo "$(cat "$dir/memory.peak" 2>/dev/null || echo 0) $(cat "$dir/memory.swap.peak" 2>/dev/null || echo 0)" > "$WORK/stats/$step.peak"
		if lowa_disk_low "$WORK" "$STOP_BELOW_DISK_GB"; then
			echo "STOPPING $name: less than $STOP_BELOW_DISK_GB GB free on $WORK"
			echo disk > "$WORK/stats/$step.stopped"
			docker stop -t 30 "$name" >/dev/null
			return 0
		fi
	done
}

# Run /scripts/$2 in a memory-capped container lowa-$1 with $3 jobs; returns the container exit code
# (75 when the disk guard stopped it)
run_step() {
	local step="$1" script="$2" jobs="$3" name="lowa-$1" swap start rc watcher peak swappeak
	swap=$(lowa_container_swap_gb "$(lowa_meminfo_gb SwapFree)")
	rm -f "$WORK/stats/$step.peak" "$WORK/stats/$step.stopped"
	docker rm -f "$name" >/dev/null 2>&1 || true
	start=$(date +%s)
	echo "[$(date -Is)] $step: $jobs jobs, $MAX_CPUS CPUs, memory ${MEM_LIMIT_GB} GB + swap ${swap} GB"
	docker run -d --name "$name" --memory="${MEM_LIMIT_GB}g" --memory-swap="$((MEM_LIMIT_GB + swap))g" --cpus="$MAX_CPUS" \
		--user "$(id -u):$(id -g)" -v "$WORK:/work" -v "$ROOT/scripts:/scripts:ro" -v "$ROOT/patches:/patches:ro" \
		"${ENV_ARGS[@]}" -e JOBS="$jobs" "$IMAGE" bash "/scripts/$script" >/dev/null
	watch_container "$name" "$step" &
	watcher=$!
	docker logs -f "$name" 2>&1 || true
	rc=$(docker wait "$name" 2>/dev/null || echo 1)
	kill "$watcher" 2>/dev/null || true
	docker rm "$name" >/dev/null 2>&1 || true
	read -r peak swappeak < "$WORK/stats/$step.peak" 2>/dev/null || { peak=0; swappeak=0; }
	printf '{"start": %d, "end": %d, "exit": %d, "jobs": %d, "peak_bytes": %d, "swap_peak_bytes": %d, "stopped": "%s"}\n' \
		"$start" "$(date +%s)" "$rc" "$jobs" "${peak:-0}" "${swappeak:-0}" "$(cat "$WORK/stats/$step.stopped" 2>/dev/null || true)" \
		> "$WORK/stats/$step.json"
	echo "[$(date -Is)] $step: exit $rc"
	# Stopped by the disk guard: a distinct code, so that the SIGKILL of docker stop is not taken for an out-of-memory kill
	if [ -f "$WORK/stats/$step.stopped" ]; then
		echo "$step was stopped: $(cat "$WORK/stats/$step.stopped")"
		return 75
	fi
	return "$rc"
}

# RAM a step may use: what the host has available, at most the container cap
usable_ram_gb() {
	local avail
	avail=$(lowa_meminfo_gb MemAvailable)
	[ "$avail" -lt "$MEM_LIMIT_GB" ] && echo "$avail" || echo "$MEM_LIMIT_GB"
}

step_qt() {
	run_step qt build-qt.sh "$(lowa_jobs "$(usable_ram_gb)" "$MAX_JOBS")"
}

# LibreOffice; after an out-of-memory kill, resume once with a single job (the link alone)
step_lo() {
	local jobs rc=0
	jobs=$(lowa_jobs "$(usable_ram_gb)" "$MAX_JOBS")
	run_step lo build-lo.sh "$jobs" || rc=$?
	if [ "$rc" -ne 0 ] && lowa_is_oom_exit "$rc"; then
		echo "Out of memory with $jobs jobs: resuming with 1 job"
		run_step lo-retry build-lo.sh 1
		return
	fi
	return "$rc"
}

step_collect() {
	python3 -I "$ROOT/scripts/collect.py" "$ROOT" "$WORK" "$OUT"
	echo "Engine collected in $OUT"
}

# Every step in order (runs in the background, see step_all)
step_run_all() {
	echo "[$(date -Is)] build $LABEL started"
	step_image
	step_fetch
	step_qt
	step_lo
	step_collect
	echo "[$(date -Is)] build $LABEL finished"
}

step_all() {
	step_preflight
	nohup "$ROOT/build.sh" _all > "$OUT/build.log" 2>&1 &
	echo "Build started in the background (pid $!). Log: $OUT/build.log  Progress: ./build.sh status"
}

# Bash reads a script while it runs: everything is parsed before the first step (build.sh is edited
# while long steps run in the background)
main() {
	case "${1:-all}" in
		preflight) step_preflight ;;
		status) step_status ;;
		image) step_image ;;
		fetch) step_fetch ;;
		qt) step_qt ;;
		lo) step_lo ;;
		collect) step_collect ;;
		all) step_all ;;
		_all) step_run_all ;;
		*) echo "Usage: $0 [all|preflight|image|fetch|qt|lo|collect|status]" >&2; exit 2 ;;
	esac
}

main "$@"; exit
