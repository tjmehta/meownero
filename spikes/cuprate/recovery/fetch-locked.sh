#!/usr/bin/env bash
# One bounded online fetch into a new task cache; no compilation or pin changes.
set -euo pipefail
SRC=$(realpath "${1:?usage: fetch-locked.sh full-source new-cache new-output-directory}")
CACHE=$(realpath -m "${2:?new isolated cache required}")
OUT=$(realpath -m "${3:?new output directory required}")
test -f "$SRC/Cargo.toml" && test -f "$SRC/Cargo.lock"
if [ -e "$CACHE" ] || [ -e "$OUT" ] || [ "$CACHE" = "$OUT" ]; then
  echo 'cache and output must be distinct new directories' >&2; exit 2
fi
TOOLCHAIN=$(dirname "$(dirname "$(rustup which cargo)")")
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
mkdir -p "$CACHE" "$OUT"
set +e
docker run --rm --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
  --read-only --tmpfs /tmp:rw,size=32m -u "$(id -u):$(id -g)" \
  -v "$SRC:/src:ro" -v "$CACHE:/cargo" -v "$OUT:/out" \
  -v "$TOOLCHAIN:/rust:ro" -e PATH=/rust/bin:/usr/bin:/bin \
  -e CARGO_HOME=/cargo -e CARGO_NET_RETRY=0 -e CARGO_HTTP_TIMEOUT=20 \
  -e CARGO_NET_GIT_FETCH_WITH_CLI=true -e GIT_TERMINAL_PROMPT=0 \
  -e GIT_CONFIG_NOSYSTEM=1 -e GIT_CONFIG_GLOBAL=/dev/null \
  -w /src "$IMG" bash -c '
    sha256sum Cargo.toml Cargo.lock > /out/inputs-before.sha256
    date -u +%FT%TZ > /out/start.txt
    timeout --signal=TERM --kill-after=5 90 cargo fetch --locked \
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
if [ "$result" -ne 0 ] && [ -f "$OUT/stderr.log" ]; then tail -40 "$OUT/stderr.log"; fi
exit "$result"
