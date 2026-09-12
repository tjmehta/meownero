#!/usr/bin/env bash
# Source slice compilation + real daemon checks, never a P2Pool service.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SOURCE=$(realpath "$1")
DAEMON_SOURCE=$(realpath "$2")
WORK=$(realpath -m "$3")
mkdir -p "$WORK"
[[ -z $(ls -A "$WORK") ]] || { echo 'output directory must be empty' >&2; exit 1; }
IMAGE=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
NAME=meow-swarm-mining-probe-$$
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
echo 'Waiting for shared heavy lock (one small compiler process, then one daemon).'
flock 9
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker image inspect "$IMAGE" --format '{{.Id}}' > "$WORK/BUILDER_IMAGE_ID"
free -m > "$WORK/memory-before.txt"
df -k "$WORK" > "$WORK/disk-before.txt"
# This is a tiny two-routine compilation, not a large/source P2Pool build.
# Heavy lock also serializes the 1 GiB daemon/RandomX test with other tracks.
docker run --rm --name "$NAME" --network none --memory 1g --memory-swap 1g --cpus 2 \
  --pids-limit 128 --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" \
  -v "$SOURCE:/p2pool:ro" -v "$DAEMON_SOURCE:/src:ro" \
  -v "$HERE:/harness:ro" -v "$WORK:/work" "$IMAGE" \
  timeout 240 sh -c 'python3 /harness/source_probe.py /p2pool /work && python3 /harness/devnet_probe.py'
