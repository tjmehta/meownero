#!/usr/bin/env bash
# Two independent source compilations in one immutable builder image, with no ccache reuse.
# This does not prove independent reconstruction of the builder's apt packages.
# Usage: bash chain/test-reproducibility.sh [new-output-directory]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(realpath -m "${1:-$(mktemp -d /tmp/meownero-repro-XXXXXX)}")
if [ -e "$WORK/first" ] || [ -e "$WORK/second" ]; then
  printf 'Refusing to reuse build trees in %s\n' "$WORK" >&2
  exit 1
fi
mkdir -p "$WORK"
IMG=${MEOW_BUILDER_IMAGE:-meownero-chain-builder}
if [ -z "${MEOW_BUILDER_IMAGE:-}" ]; then
  docker build -q -t "$IMG" -f "$HERE/Dockerfile" "$HERE" >/dev/null
fi
export MEOW_BUILDER_IMAGE
MEOW_BUILDER_IMAGE=$(docker image inspect "$IMG" --format '{{.Id}}')
export CCACHE_DISABLE=1
printf 'Reproducibility output: %s\nBuilder: %s\n' "$WORK" "$MEOW_BUILDER_IMAGE"
for run in first second; do
  "$HERE/build.sh" "$WORK/$run" 2>&1 | tee "$WORK/$run.log"
done
diff -u "$WORK/first/BUILDER_IMAGE_ID" "$WORK/second/BUILDER_IMAGE_ID"
diff -u "$WORK/first/packages.txt" "$WORK/second/packages.txt"
diff -u "$WORK/first/SHA256SUMS" "$WORK/second/SHA256SUMS"
printf 'PASS: independent source builds match in the recorded builder image.\n'
