#!/usr/bin/env bash
# Funded private-devnet wallet integration: send/receive, restore-then-spend,
# fee/atomic-unit correctness, real-daemon aggregate cross-check. No external
# networking or host ports; all keys are disposable test keys.
# Usage: bash chain/test-wallet-funded.sh <built-source> <new-output-directory>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?verified built source required}")
WORK=$(realpath -m "${2:?new output directory required}")
mkdir -m 700 "$WORK"   # refuse reuse, including preserved evidence directories
IMG=$(docker image inspect "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" --format '{{.Id}}')
NAME="meow-wallet-funded-$$"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
git -C "$SRC" rev-parse HEAD 'HEAD^{tree}' > "$WORK/SOURCE_REVISIONS"
sha256sum "$SRC/build/release/bin/monerod" "$SRC/build/release/bin/monero-wallet-rpc" \
  > "$WORK/BINARY_SHA256"
sha256sum "$HERE/test-wallet-funded.py" "$HERE/test-wallet-funded.sh" \
  "$SRC/src/cryptonote_config.h" > "$WORK/INPUT_SHA256"

# 4 GiB / 2 CPU: a daemon (RandomX miner needs its ~2 GiB dataset) plus four
# wallet-rpc processes and short mining bursts. Single job under the shared heavy
# lock; the >=5 GiB available preflight still holds with margin.
docker run --rm --name "$NAME" --network none --memory 4g --memory-swap 4g \
  --cpus 2 --pids-limit 256 --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" \
  -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$WORK:/work" \
  "$IMG" timeout 1200 python3 -B -u /harness/test-wallet-funded.py \
  | tee "$WORK/harness.stdout.log"
