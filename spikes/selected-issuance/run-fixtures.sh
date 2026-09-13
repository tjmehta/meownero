#!/usr/bin/env bash
# Fixture smoke test; native headers require the shared guarded compile budget.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?usage: run-fixtures.sh preserved-current15-source empty-output-dir}")
OUT=$(realpath -m "${2:?empty output directory required}")
mkdir -p "$OUT"
if [ -n "$(ls -A "$OUT")" ]; then echo 'output must be empty' >&2; exit 2; fi
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
bash "$HERE/../../chain/network-build-guard.sh" docker run --rm --network none --cpus 1 \
  --pids-limit 64 --ulimit core=0 --read-only --tmpfs /tmp:rw,size=32m \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$SRC:/src:ro" -v "$HERE:/harness:ro" \
  -v "$OUT:/out" -w /out "$IMG" python3 /harness/verify-fixtures.py /src /out
