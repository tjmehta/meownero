#!/usr/bin/env bash
# Opt-in swarm-only resource policy. General build.sh keeps its portable defaults.
# MEOW_REPRO_BUILD_RUNNER=$PWD/chain/network-build-guard.sh chain/test-reproducibility.sh ...
set -euo pipefail
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
resources_ready() {
  local available_kib disk_kib
  available_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
  disk_kib=$(df -Pk /tmp | awk 'END {print $4}')
  printf '%s resource gate RAM=%s KiB disk=%s KiB\n' "$(date -u +%FT%TZ)" "$available_kib" "$disk_kib"
  (( available_kib >= 5 * 1024 * 1024 && disk_kib >= 5 * 1024 * 1024 ))
}
while true; do
  if resources_ready; then
    flock 9
    if resources_ready; then break; fi
    flock -u 9
  fi
  sleep 30
done
# This function deliberately applies only within this opt-in runner and its
# existing build/test child scripts. All names/resources belong to this track.
docker() {
  if [ "${1:-}" = run ]; then
    shift
    command docker run --name "meow-swarm-network-${BASHPID}-${RANDOM}" --memory=4g --memory-swap=4g --cpus=2 "$@"
  else
    command docker "$@"
  fi
}
export -f docker
export MEOW_JOBS=1
"$@"
