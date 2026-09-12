#!/usr/bin/env bash
# Native DAA + paired stochastic scenarios. This is not a full network benchmark.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "$1")
WORK=$(realpath -m "$2")
mkdir -p "$WORK"
[ -z "$(ls -A "$WORK")" ] || { echo 'workdir must be empty' >&2; exit 1; }
IMG=$(docker image inspect "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" --format '{{.Id}}')
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
sha256sum "$SRC/src/cryptonote_basic/difficulty.cpp" "$SRC/src/cryptonote_config.h" > "$WORK/SOURCE_SHA256SUMS"
docker run --rm --network none -v "$SRC:/src:ro" -v "$HERE:/harness:ro" \
  -v "$WORK:/work" -w /work "$IMG" bash -ec '
    g++ -std=c++14 -O2 -fPIC -shared -I /src/src -I /src/contrib/epee/include \
      /harness/daa-benchmark.cpp /src/src/cryptonote_basic/difficulty.cpp -o /work/daa.so
    timeout 600 python3 -u /harness/benchmark-difficulty.py /work/daa.so /work/results.json
  '
