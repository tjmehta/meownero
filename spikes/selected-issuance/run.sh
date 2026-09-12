#!/usr/bin/env bash
# Isolated source probe only; does not modify chain/patches or frozen builds.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?usage: run.sh preserved-current15-source empty-output-dir}")
OUT=$(realpath -m "${2:?empty output directory required}")
mkdir -p "$OUT"
if [ -n "$(ls -A "$OUT")" ]; then echo 'output must be empty' >&2; exit 2; fi
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
if ! flock -n 9; then echo 'priority compiler busy; retry later' >&2; exit 75; fi
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
cat /proc/meminfo > "$OUT/host-memory-before.txt"
docker run --rm --network none --memory 512m --memory-swap 512m --cpus 1 \
  --pids-limit 64 --ulimit core=0 --read-only --tmpfs /tmp:rw,size=32m \
  -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$OUT:/out" -w /out \
  "$IMG" python3 /harness/verify.py /src /out
