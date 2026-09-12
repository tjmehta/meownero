#!/usr/bin/env bash
# Disposable private-chain seed recovery. No external networking or host ports.
# Usage: bash chain/test-seed-recovery.sh <built-source> <new-output-directory>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "$1")
WORK=$(realpath -m "$2")
mkdir -p "$WORK"
[ -z "$(ls -A "$WORK")" ] || { echo 'workdir must be empty' >&2; exit 1; }
IMG=$(docker image inspect "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" --format '{{.Id}}')
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
docker run --rm --network none -v "$SRC:/src:ro" -v "$HERE:/harness:ro" \
  -v "$WORK:/work" "$IMG" timeout 600 python3 -u /harness/test-seed-recovery.py
