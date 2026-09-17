#!/usr/bin/env bash
# Loaded matched-profile P2P run: two daemons, one wallet-rpc, shaped proxies, one network-less container.
# Usage: chain/test-network-loaded.sh <built-source> <new-output-directory> <profile> [harness args...]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?built source required}")
WORK=$(realpath -m "${2:?new output directory required}")
PROFILE=${3:?profile required}
shift 3
mkdir -p "$WORK"
[ -z "$(ls -A "$WORK")" ] || { echo 'workdir must be empty' >&2; exit 1; }
# Same heavy lock and >=5 GiB available-RAM preflight as chain/test-network-p2p.sh; this
# waits (bounded) for RAM instead of failing at once because availability fluctuates.
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
flock -w "${MEOW_NETWORK_WAIT_SECONDS:-60}" 9 || { echo 'priority build busy; retry later' >&2; exit 75; }
deadline=$((SECONDS + ${MEOW_NETWORK_WAIT_SECONDS:-60}))
while :; do
  available_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
  printf '%s resource gate RAM=%s KiB\n' "$(date -u +%FT%TZ)" "$available_kib"
  (( available_kib >= 5 * 1024 * 1024 )) && break
  (( SECONDS < deadline )) || { echo 'need >=5 GiB available RAM' >&2; exit 75; }
  sleep 10
done
IMG=$(docker image inspect "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" --format '{{.Id}}')
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
sha256sum "$SRC/build/release/bin/monerod" "$SRC/build/release/bin/monero-wallet-rpc" > "$WORK/BINARY_SHA256"
sha256sum "$HERE/test-network-loaded.py" "$HERE/../spikes/network-benchmark/check-readiness.py" > "$WORK/HARNESS_SHA256"
printf '%s\n' "$PROFILE" "$@" > "$WORK/ARGS"
name="meow-swarm-network-loaded-$$"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
# No outbound networking or published ports. Loopback connects only these daemons, wallet-rpc and proxies.
docker run --rm --name "$name" --network none --memory=1536m --memory-swap=1536m --cpus=2 \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$HERE/../spikes/network-benchmark:/profiles:ro" -v "$WORK:/work" \
  "$IMG" timeout "${MEOW_LOADED_TIMEOUT:-1800}" python3 -u /harness/test-network-loaded.py --profile "$PROFILE" "$@" 2>&1 | tee "$WORK/run.log"
echo "${PIPESTATUS[0]}" > "$WORK/exit"
exit "$(cat "$WORK/exit")"
