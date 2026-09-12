#!/usr/bin/env bash
# Local observers only; sequential wallets inside a 512 MiB isolated container.
# Usage: bash chain/privacy-test.sh <verified-built-source> <new-output-directory>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?verified source required}")
WORK=$(realpath -m "${2:?new output directory required}")
mkdir -m 700 "$WORK" # Refuse reuse, including preserved evidence directories.
mkdir -m 700 "$WORK/home"
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
NAME="meow-swarm-privacy-$$"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
git -C "$SRC" rev-parse HEAD 'HEAD^{tree}' > "$WORK/SOURCE_REVISIONS"
sha256sum "$SRC/build/release/bin/monero-wallet-rpc" > "$WORK/BINARY_SHA256"
docker run --rm --name "$NAME" --network none --memory 512m --memory-swap 512m \
  --cpus 1 --pids-limit 128 --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=32m \
  -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$WORK:/work" \
  -v "$WORK/home:/home/ubuntu" \
  "$IMG" timeout 240 python3 -B -u /harness/privacy-test.py | tee "$WORK/harness.stdout.log"
