#!/usr/bin/env bash
# Real daemon P2P bytes through interruptible TCP proxies, in a network-less container.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?built source required}")
WORK=$(realpath -m "${2:?new output directory required}")
PROFILE=${3:-historical-0.9-120}
mkdir -p "$WORK"
[ -z "$(ls -A "$WORK")" ] || { echo 'workdir must be empty' >&2; exit 1; }
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
flock -w 60 9 || { echo 'priority build busy; retry after reproduction' >&2; exit 75; }
available_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
(( available_kib >= 5 * 1024 * 1024 )) || { echo 'need >=5 GiB available RAM' >&2; exit 75; }
IMG=$(docker image inspect "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" --format '{{.Id}}')
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
sha256sum "$SRC/build/release/bin/monerod" > "$WORK/BINARY_SHA256"
name="meow-swarm-network-p2p-$$"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
# No outbound networking or published ports. Loopback connects only these two daemons/proxies.
docker run --rm --name "$name" --network none --memory=1536m --memory-swap=1536m --cpus=2 \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$HERE/../spikes/network-benchmark:/profiles:ro" -v "$WORK:/work" \
  "$IMG" timeout 420 python3 -u /harness/test-network-p2p.py --profile "$PROFILE" 2>&1 | tee "$WORK/run.log"
