#!/usr/bin/env bash
# No daemon, service, network, key access, or large build.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
P2POOL=$(realpath "${1:?pinned P2Pool source required}")
MEOW=$(realpath "${2:?preserved current15 source required}")
OVERLAYS=$(realpath "${3:?selected-issuance overlay directory required}")
OUT=$(realpath -m "${4:?new empty output directory required}")
mkdir -p "$OUT"
[[ -z $(ls -A "$OUT") ]] || { echo 'output directory must be empty' >&2; exit 2; }
# Explicit lightweight allowance: <=512 MiB. No heavy lock is taken away from
# network reproduction. Half a CPU and low CPU shares prioritize that build.
IMAGE=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
cat /proc/meminfo > "$OUT/host-memory-before.txt"
docker image inspect "$IMAGE" --format '{{.Id}}' > "$OUT/BUILDER_IMAGE_ID"
docker run --rm --network none --memory 512m --memory-swap 512m --cpus 0.5 --cpu-shares 128 \
  --pids-limit 64 --ulimit core=0 --read-only --tmpfs /tmp:rw,size=32m \
  --cap-drop ALL --security-opt no-new-privileges --user "$(id -u):$(id -g)" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$HERE/../../research/evidence/swarm-2026-09-12/mining/devnet-results.json:/genesis-receipt:ro" \
  -v "$P2POOL:/p2pool:ro" -v "$MEOW:/meow:ro" -v "$OVERLAYS:/overlays:ro" \
  -v "$HERE:/harness:ro" -v "$OUT:/out" -w /out "$IMAGE" \
  timeout 180 python3 /harness/selected_probe.py /p2pool /meow /overlays /out
