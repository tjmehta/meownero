#!/usr/bin/env bash
# Actual daemon validation/reorganization in an isolated regtest container.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "$1")
WORK=$(realpath -m "$2")
MODE=${3:-regtest}
case "$MODE" in regtest|mainnet-window) ;; *) echo 'mode must be regtest or mainnet-window' >&2; exit 1;; esac
mkdir -p "$WORK"
[ -z "$(ls -A "$WORK")" ] || { echo 'workdir must be empty' >&2; exit 1; }
IMG=$(docker image inspect "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" --format '{{.Id}}')
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
docker run --rm --network none -v "$SRC:/src:ro" -v "$HERE:/harness:ro" \
  -v "$WORK:/work" "$IMG" timeout 600 python3 -u /harness/test-reorg.py "$MODE"
