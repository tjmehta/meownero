#!/usr/bin/env bash
# Usage: bash demos/private-payment/run.sh <current15-built-source> <NEW-output-dir>
set -euo pipefail
[[ $# == 2 ]] || { echo 'expected built-source and NEW output directory' >&2; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "$1")
WORK=$(realpath -m "$2")
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
case "$WORK" in /tmp/meownero-swarm-demo-*) ;; *) echo 'output must start /tmp/meownero-swarm-demo-' >&2; exit 2;; esac
# mkdir without -p refuses existing directories, including preserved evidence.
umask 077
mkdir "$WORK"
NAME="meow-swarm-demo-$(date +%s)-$$"
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
echo 'Waiting for shared heavy-job lock'
flock 9
docker image inspect "$IMG" --format '{{.Id}}' > "$WORK/BUILDER_IMAGE_ID"
cleanup() {
  docker inspect "$NAME" --format '{{json .State}}' > "$WORK/container-state.json" 2>/dev/null || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# All traffic stays inside this container. The image, binaries and harness are read-only.
docker run --name "$NAME" --network none --memory 512m --memory-swap 512m \
  --cpus 2 --pids-limit 128 --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" -e HOME=/work -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$WORK:/work" \
  "$IMG" timeout 600 python3 -u /harness/demo.py 2>&1 | tee "$WORK/run.log"
