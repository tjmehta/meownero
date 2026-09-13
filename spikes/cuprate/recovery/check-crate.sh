#!/usr/bin/env bash
# One guarded, offline actual crate check; network owns the next heavy slot.
set -euo pipefail
SRC=$(realpath "${1:?usage: check-crate.sh full-source populated-cache new-output-directory [existing-target-directory]}")
CACHE=$(realpath "${2:?populated isolated cache required}")
OUT=$(realpath -m "${3:?new output directory required}")
test -f "$SRC/Cargo.toml" && test -f "$SRC/Cargo.lock"
if [ ! -d "$SRC/.git" ]; then
  echo 'crate check requires a genuine standalone Git checkout; an archive lacks build commit metadata' >&2
  exit 2
fi
PIN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["cuprate_commit"])' \
  "$(dirname "$0")/../source-lock.json")
if [ "$(git -C "$SRC" rev-parse HEAD)" != "$PIN" ] || ! git -C "$SRC" diff --quiet HEAD --; then
  echo 'checkout must have the pinned HEAD and unchanged tracked files' >&2; exit 2
fi
if [ -e "$OUT" ]; then echo 'output directory must not exist' >&2; exit 2; fi
TOOLCHAIN=$(dirname "$(dirname "$(rustup which --toolchain 1.96.1 cargo)")")
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
mkdir -p "$OUT/cargo"
cat /proc/meminfo > "$OUT/host-memory-before.txt"
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
if ! flock -n 9; then
  echo 'shared heavy lock busy; yielded without waiting' > "$OUT/guard.log"
  echo 75 > "$OUT/guard.exit"
  cat "$OUT/guard.log"; exit 75
fi
available_kib=$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)
printf '%s\n' "$available_kib" > "$OUT/available-kib-under-lock.txt"
if [ "$available_kib" -lt 5242880 ]; then
  echo 'less than 5 GiB available; yielded without launching a container' > "$OUT/guard.log"
  echo 75 > "$OUT/guard.exit"
  cat "$OUT/guard.log"; exit 75
fi
echo 0 > "$OUT/guard.exit"
TARGET=$(realpath -m "${4:-$OUT/target}")
mkdir -p "$TARGET"
NAME="meownero-rust-crate-check-$$"
printf '%s\n' "$NAME" > "$OUT/container-name.txt"
trap 'docker rm -f "$NAME" > "$OUT/cleanup.log" 2>&1 || true' EXIT
set +e
docker run --rm --name "$NAME" --network none --memory 4g --memory-swap 4g \
  --cpus 2 --pids-limit 256 --read-only --tmpfs /tmp:rw,size=128m \
  -u "$(id -u):$(id -g)" -v "$SRC:/src:ro" -v "$OUT:/out" \
  -v "$TARGET:/out/target" \
  -v "$TOOLCHAIN:/rust:ro" -v "$CACHE/registry:/out/cargo/registry:ro" \
  -v "$CACHE/git:/out/cargo/git:ro" -e PATH=/rust/bin:/usr/bin:/bin \
  -e CARGO_HOME=/out/cargo -e CARGO_TARGET_DIR=/out/target -w /src "$IMG" bash -c '
    cargo -vV > /out/cargo-version.txt
    rustc -vV > /out/rust-version.txt
    sha256sum Cargo.toml Cargo.lock > /out/inputs-before.sha256
    date -u +%FT%TZ > /out/start.txt
    timeout --signal=TERM --kill-after=5 300 \
      cargo check --frozen --package cuprate-consensus-context --jobs 1 \
      > /out/stdout.log 2> /out/stderr.log
    result=$?
    printf "%s\n" "$result" > /out/cargo.exit
    date -u +%FT%TZ > /out/end.txt
    sha256sum Cargo.toml Cargo.lock > /out/inputs-after.sha256
    cat /sys/fs/cgroup/memory.peak > /out/container-memory-peak.txt
    cat /sys/fs/cgroup/memory.events > /out/container-memory-events.txt
    exit "$result"
  ' > "$OUT/container.log" 2>&1
result=$?
set -e
printf '%s\n' "$result" > "$OUT/container.exit"
cat "$OUT/container.log"
if [ -f "$OUT/stderr.log" ]; then tail -30 "$OUT/stderr.log"; fi
exit "$result"
