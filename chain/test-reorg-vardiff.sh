#!/usr/bin/env bash
# Variable-difficulty (non-floor) reorg economics on the real selected daemon — closes F2.
# Two isolated --offline mainnet-mode daemons, real RandomX PoW via submit_block nonce
# search, explicit RPC block delivery, empty blocks, disposable fixture address, no
# networking. Difficulty is driven above the floor by controlled timestamps (a hashpower
# model on the real DAA) — not a live hashrate race; see the harness docstring.
# Usage: bash chain/test-reorg-vardiff.sh <built-source> <new-output-directory>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?verified built source required}")
WORK=$(realpath -m "${2:?new output directory required}")
mkdir -m 700 "$WORK"   # refuse reuse, including preserved evidence directories
IMG=$(docker image inspect "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" --format '{{.Id}}')
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
git -C "$SRC" rev-parse HEAD 'HEAD^{tree}' > "$WORK/SOURCE_REVISIONS"
# Bind staged and unstaged tracked overlays, not just the clean historical tree.
# Untracked files/build products are not covered; the executable is hashed separately.
git -C "$SRC" diff --no-ext-diff --no-textconv --binary HEAD > "$WORK/SOURCE_OVERLAY.patch"
(cd "$WORK" && sha256sum SOURCE_OVERLAY.patch) >> "$WORK/SOURCE_REVISIONS"
sha256sum "$SRC/build/release/bin/monerod" > "$WORK/BINARY_SHA256"
sha256sum "$HERE/test-reorg-vardiff.py" "$HERE/test-reorg-vardiff.sh" > "$WORK/INPUT_SHA256"

# Preserve full daemon witnesses on success or failure, without deleting originals.
# Copy n{0,1}.log.gz and DAEMON_LOG_SHA256 into durable evidence before cleanup;
# copy SOURCE_OVERLAY.patch with SOURCE_REVISIONS into its freeze directory.
preserve_daemon_logs() {
  local status=$? node
  trap - EXIT
  : > "$WORK/DAEMON_LOG_SHA256"
  for node in n0 n1; do
    if [[ -f "$WORK/$node.log" ]]; then
      gzip -n -c "$WORK/$node.log" > "$WORK/$node.log.gz" || exit 1
      (cd "$WORK" && sha256sum "$node.log.gz") >> "$WORK/DAEMON_LOG_SHA256" || exit 1
    fi
  done
  exit "$status"
}
trap preserve_daemon_logs EXIT

docker run --rm --name "meow-reorg-vardiff-$$" --network none --memory 3g --memory-swap 3g \
  --cpus 2 --pids-limit 512 --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" \
  -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$WORK:/work" \
  "$IMG" timeout 1800 python3 -B -u /harness/test-reorg-vardiff.py \
  | tee "$WORK/harness.stdout.log"
exit 0
