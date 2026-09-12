#!/usr/bin/env bash
# Baseline kernel measurement, not a proposed optimization or a chain speedup.
set -euo pipefail
[[ $# == 2 ]] || { echo 'expected current15 built-source and NEW output directory' >&2; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "$1")
WORK=$(realpath -m "$2")
case "$WORK" in /tmp/meownero-swarm-demo-*) ;; *) echo 'output must start /tmp/meownero-swarm-demo-' >&2; exit 2;; esac
umask 077
mkdir "$WORK"
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
NAME="meow-swarm-demo-hash-$(date +%s)-$$"
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
echo 'Waiting for shared heavy-job lock'
flock 9
cleanup() {
  docker inspect "$NAME" --format '{{json .State}}' > "$WORK/container-state.json" 2>/dev/null || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# One tiny harness compilation, linking already-built objects; no chain rebuild.
docker run --name "$NAME" --network none --memory 128m --memory-swap 128m \
  --cpus 1 --cpuset-cpus 0 --pids-limit 32 --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$WORK:/work" \
  "$IMG" bash -euc '
    cc --version > /work/compiler.txt
    uname -a > /work/kernel.txt
    cat /proc/cpuinfo > /work/cpuinfo.txt
    OBJ=/src/build/release/src/crypto/CMakeFiles/obj_cncrypto.dir
    sha256sum "$OBJ/hash.c.o" "$OBJ/keccak.c.o" /src/tests/hash/tests-fast.txt \
      /harness/hash-measure.c > /work/inputs.sha256
    cc -std=c11 -O3 -DNDEBUG -fno-lto -Wall -Wextra -Werror /harness/hash-measure.c \
      "$OBJ/hash.c.o" "$OBJ/keccak.c.o" -o /work/hash-measure
    sha256sum /work/hash-measure > /work/binary.sha256
    timeout 60 /work/hash-measure /src/tests/hash/tests-fast.txt > /work/measurement.json
  '
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
