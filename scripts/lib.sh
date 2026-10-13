# Host-side helpers of build.sh. Sourced; defines functions only.
# Test hooks: LOWA_MEMINFO (meminfo file to read), LOWA_DF_AVAIL_GB (forced free disk in GB).

# Value of a /proc/meminfo field in GB, rounded down. $1 = field name
lowa_meminfo_gb() {
	awk -v k="$1:" '$1 == k { printf "%d\n", $2 / 1048576 }' "${LOWA_MEMINFO:-/proc/meminfo}"
}

# Free disk space in GB on the file system of $1
lowa_free_disk_gb() {
	if [ -n "${LOWA_DF_AVAIL_GB:-}" ]; then
		echo "$LOWA_DF_AVAIL_GB"
		return
	fi
	df -BG --output=avail "$1" | tail -n 1 | tr -dc '0-9'
	echo
}

# Compile jobs: one per 2 GB of usable RAM, between 1 and $2. $1 = usable RAM in GB
lowa_jobs() {
	local j=$(( $1 / 2 ))
	[ "$j" -gt "$2" ] && j=$2
	[ "$j" -lt 1 ] && j=1
	echo "$j"
}

# Swap a build container may use, keeping 4 GB for the host. $1 = free swap in GB
lowa_container_swap_gb() {
	local s=$(( $1 - 4 ))
	[ "$s" -lt 0 ] && s=0
	echo "$s"
}

# Checks before a build. $1 = work directory. Prints each problem; returns 1 if any.
lowa_preflight() {
	local status=0 disk swap
	disk=$(lowa_free_disk_gb "$1")
	swap=$(lowa_meminfo_gb SwapTotal)
	if [ "$disk" -lt "$MIN_FREE_DISK_GB" ]; then
		echo "Free disk on $1: ${disk} GB, at least ${MIN_FREE_DISK_GB} GB needed."
		status=1
	fi
	if [ "$swap" -lt "$MIN_SWAP_GB" ]; then
		echo "Swap: ${swap} GB, at least ${MIN_SWAP_GB} GB needed. Add a swapfile (run it yourself):"
		echo "  sudo fallocate -l $(( MIN_SWAP_GB - swap ))G /home/swapfile-lowa && sudo chmod 600 /home/swapfile-lowa && sudo mkswap /home/swapfile-lowa && sudo swapon /home/swapfile-lowa"
		status=1
	fi
	return $status
}

# Status 0 when the free disk on $1 is below $2 GB
lowa_disk_low() {
	[ "$(lowa_free_disk_gb "$1")" -lt "$2" ]
}

# Status 0 when a container exit code means it was killed for lack of memory
lowa_is_oom_exit() {
	[ "$1" -eq 137 ]
}

# cgroup v2 directory of a running container (systemd cgroup driver)
lowa_cgroup_dir() {
	echo "/sys/fs/cgroup/system.slice/docker-$(docker inspect -f '{{.Id}}' "$1").scope"
}
