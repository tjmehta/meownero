#!/usr/bin/env bash
# Resolve the actual, unchanged workspace without compiling or using the network.
set -euo pipefail
SRC=$(realpath "${1:?usage: check-locked.sh full-source new-output-directory}")
OUT=$(realpath -m "${2:?new output directory required}")
test -f "$SRC/Cargo.toml" && test -f "$SRC/Cargo.lock"
if [ -e "$OUT" ]; then echo 'output directory must not exist' >&2; exit 2; fi
TOOLCHAIN=$(dirname "$(dirname "$(rustup which cargo)")")
CACHE=${CARGO_HOME:-$HOME/.cargo}
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
mkdir -p "$OUT/cargo"
cat /proc/meminfo > "$OUT/host-memory-before.txt"
docker image inspect "$IMG" --format '{{.Id}}' > "$OUT/builder-image.txt"
set +e
docker run --rm --network none --memory 512m --memory-swap 512m --cpus 1 \
  --pids-limit 64 --read-only --tmpfs /tmp:rw,size=32m \
  -u "$(id -u):$(id -g)" \
  -v "$SRC:/src:ro" -v "$OUT:/out" -v "$TOOLCHAIN:/rust:ro" \
  -v "$CACHE/registry:/out/cargo/registry:ro" \
  -v "$CACHE/git:/out/cargo/git:ro" \
  -e CARGO_HOME=/out/cargo -e CARGO_TARGET_DIR=/out/target \
  -e PATH=/rust/bin:/usr/bin:/bin -w /src "$IMG" bash -c '
    cargo -vV > /out/cargo-version.txt
    rustc -vV > /out/rust-version.txt
    sha256sum Cargo.toml Cargo.lock > /out/inputs-before.sha256
    timeout 45 cargo metadata --frozen --format-version 1 \
      > /out/metadata.json 2> /out/cargo.stderr
    result=$?
    printf "%s\n" "$result" > /out/cargo.exit
    sha256sum Cargo.toml Cargo.lock > /out/inputs-after.sha256
    cat /sys/fs/cgroup/memory.peak > /out/container-memory-peak.txt
    cat /sys/fs/cgroup/memory.events > /out/container-memory-events.txt
    exit "$result"
  ' > "$OUT/container.log" 2>&1
result=$?
set -e
printf '%s\n' "$result" > "$OUT/container.exit"
cat "$OUT/container.log"
if [ -f "$OUT/cargo.stderr" ]; then cat "$OUT/cargo.stderr"; fi
exit "$result"
