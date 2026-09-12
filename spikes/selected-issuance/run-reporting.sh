#!/usr/bin/env bash
# Bounded reporting probe; synthetic storage, no daemon or selected-profile build.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?usage: run-reporting.sh preserved-current15-source empty-output-dir}")
OUT=$(realpath -m "${2:?empty output directory required}")
mkdir -p "$OUT"
if [ -n "$(ls -A "$OUT")" ]; then echo 'output must be empty' >&2; exit 2; fi
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
cat /proc/meminfo > "$OUT/host-memory-before.txt"
# Lightweight work is permitted alongside the priority build at <=512 MiB.
docker run --rm --network none --memory 512m --memory-swap 512m --cpus 1 \
  --pids-limit 64 --ulimit core=0 --read-only --tmpfs /tmp:rw,size=32m \
  -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$OUT:/out" -w /out \
  "$IMG" python3 /harness/verify-reporting.py /src /out
