#!/usr/bin/env bash
# Tiny source-only build/test, capped at 512 MiB total; no network or host install.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "${1:?usage: run.sh pinned-cpp-source empty-output-dir}")
OUT=$(realpath -m "${2:?empty output directory required}")
mkdir -p "$OUT"
if [ -n "$(ls -A "$OUT")" ]; then echo 'output must be empty' >&2; exit 2; fi
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
RUSTC=$(rustup which rustc)
TOOLCHAIN=$(dirname "$(dirname "$RUSTC")")
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
if ! flock -n 9; then echo 'shared compiler lock busy; retry after priority workload' >&2; exit 75; fi
# This is deliberately a small build, not a >=5 GiB full-node build.
cat /proc/meminfo > "$OUT/host-memory-before.txt"
git -C "$SRC" rev-parse HEAD 'HEAD^{tree}' > "$OUT/cpp-git.txt"
docker image inspect "$IMG" --format '{{.Id}}' > "$OUT/builder-image.txt"
sha256sum "$RUSTC" "$TOOLCHAIN"/lib/libLLVM* > "$OUT/host-rust-toolchain.sha256"
NAME="meow-swarm-rust-daa-$$"
docker run --rm --name "$NAME" --network none --memory 512m --memory-swap 512m --cpus 1 \
  --ulimit core=0 --pids-limit 64 --read-only --tmpfs /tmp:rw,size=32m \
  -v "$SRC:/src:ro" -v "$HERE:/harness:ro" -v "$OUT:/out" \
  -v "$TOOLCHAIN:/rust:ro" -w /out "$IMG" bash -ec '
    export LC_ALL=C
    python3 /harness/extract.py /src /out/extracted.rs
    g++ --version > /out/cpp-toolchain.txt
    /rust/bin/rustc -vV > /out/rust-toolchain.txt
    sha256sum /rust/lib/rustlib/x86_64-unknown-linux-gnu/lib/* > /out/rust-sysroot.sha256
    g++ -std=c++14 -O2 -I /src/src -I /src/contrib/epee/include \
      /harness/driver.cpp /src/src/cryptonote_basic/difficulty.cpp -o /out/cpp
    /rust/bin/rustc --edition=2021 -C opt-level=3 -C codegen-units=1 -C panic=abort \
      -C overflow-checks=off /out/extracted.rs -o /out/rust-release
    /rust/bin/rustc --edition=2021 -C opt-level=3 -C codegen-units=1 -C panic=abort \
      -C overflow-checks=on /out/extracted.rs -o /out/rust-checked
    python3 /harness/compare.py /out
    sha256sum /out/cpp /out/rust-release /out/rust-checked /out/extracted.rs > /out/build.sha256
    cat /sys/fs/cgroup/memory.peak > /out/container-memory-peak.txt
    cat /sys/fs/cgroup/memory.events > /out/container-memory-events.txt
  ' 2>&1 | tee "$OUT/run.log"
