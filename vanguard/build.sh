#!/usr/bin/env bash
# Vanguard V1 (TJS-356): build and run the pinned upstream FCMP++ / CARROT primitives
# in an isolated, network-less container. Valueless harness only: no daemon, no
# network, no keys of value, nothing touches the accepted testnet v0 recipes.
#
# Usage: vanguard/build.sh prepare|build|run|receipts|all
#   VANGUARD_SRC   scratch root (default: build/vanguard-src, gitignored)
#   VANGUARD_OUT   evidence dir (default: research/evidence/vanguard-tjs356-2026-09-23)
#   VANGUARD_JOBS  make -j (default 3)
#   RUST_TOOLCHAIN_DIR  host rustup toolchain mounted read-only (must report PIN_RUSTC)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LOCK_FILE="$ROOT/vanguard/source-lock.json"
SRC_ROOT=${VANGUARD_SRC:-$ROOT/build/vanguard-src}
UP="$SRC_ROOT/monero-fcmp"
CARGO_HOME_DIR="$SRC_ROOT/cargo-home"
OUT=${VANGUARD_OUT:-$ROOT/research/evidence/vanguard-tjs356-2026-09-23}
JOBS=${VANGUARD_JOBS:-3}
RUST_TOOLCHAIN_DIR=${RUST_TOOLCHAIN_DIR:-$HOME/.rustup/toolchains/stable-x86_64-unknown-linux-gnu}
HEAVY_LOCK=/tmp/meownero-swarm-20260912-heavy.lock

pin() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval("d"+sys.argv[2]))' "$LOCK_FILE" "$1"; }
UP_URL=$(pin '["upstream"]["url"]')
UP_REV=$(pin '["upstream"]["commit"]')
IMAGE=$(pin '["builder"]["image_id"]')
PIN_RUSTC=$(pin '["builder"]["rustc"]')

die() { echo "vanguard: $*" >&2; exit 1; }

# Heavy work never steals the shared lock; it waits at most VANGUARD_LOCK_WAIT seconds.
with_heavy_lock() {
  exec 9>"$HEAVY_LOCK"
  flock -w "${VANGUARD_LOCK_WAIT:-5}" 9 || die "heavy lock $HEAVY_LOCK is held; not stealing it"
  "$@"
  flock -u 9
}

container() {
  docker run --rm --pull=never --network=none \
    -u "$(id -u):$(id -g)" \
    -v "$UP:/src" \
    -v "$CARGO_HOME_DIR:/cargo-home" \
    -v "$RUST_TOOLCHAIN_DIR:/opt/rust:ro" \
    -v "$OUT:/out" \
    -e CARGO_HOME=/cargo-home -e CARGO_NET_OFFLINE=true -e HOME=/tmp \
    -e PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    -w /src "$IMAGE" bash -ec "$1"
}

prepare() {
  mkdir -p "$SRC_ROOT" "$CARGO_HOME_DIR" "$OUT"
  if [ ! -d "$UP/.git" ]; then
    git clone --filter=blob:none --no-checkout "$UP_URL" "$UP"
  fi
  git -C "$UP" cat-file -e "$UP_REV^{commit}" 2>/dev/null || git -C "$UP" fetch origin "$UP_REV"
  [ "$(git -C "$UP" rev-parse HEAD 2>/dev/null)" = "$UP_REV" ] || git -C "$UP" checkout --detach "$UP_REV"
  git -C "$UP" submodule update --init
  python3 - "$LOCK_FILE" "$UP" <<'EOF'
import json, subprocess, sys
lock = json.load(open(sys.argv[1])); up = sys.argv[2]
head = subprocess.check_output(["git", "-C", up, "rev-parse", "HEAD"], text=True).strip()
assert head == lock["upstream"]["commit"], f"upstream HEAD {head} != pin"
for path, sha in lock["upstream"]["submodules"].items():
    got = subprocess.check_output(["git", "-C", f"{up}/{path}", "rev-parse", "HEAD"], text=True).strip()
    assert got == sha, f"submodule {path} {got} != pin {sha}"
import hashlib
cl = open(f"{up}/src/fcmp_pp/fcmp_pp_rust/Cargo.lock", "rb").read()
assert hashlib.sha256(cl).hexdigest() == lock["rust"]["cargo_lock_sha256"], "Cargo.lock hash != pin"
text = cl.decode()
for rev in (lock["rust"]["monero_oxide_rev"], lock["rust"]["crypto_bigint_rev"]):
    assert rev in text, f"Cargo.lock does not reference pinned rev {rev}"
print("pins verified: upstream, submodules, Cargo.lock, monero-oxide, crypto-bigint")
EOF
  [ "$("$RUST_TOOLCHAIN_DIR/bin/rustc" -V)" = "$PIN_RUSTC" ] || die "rustc is not $PIN_RUSTC"
  (cd "$UP/src/fcmp_pp/fcmp_pp_rust" && CARGO_HOME="$CARGO_HOME_DIR" "$RUST_TOOLCHAIN_DIR/bin/cargo" fetch --locked)
  # Inject the harness: one new directory plus one appended add_subdirectory line.
  rm -rf "$UP/tests/vanguard"
  cp -r "$ROOT/vanguard/harness" "$UP/tests/vanguard"
  grep -qx 'add_subdirectory(vanguard)' "$UP/tests/CMakeLists.txt" || echo 'add_subdirectory(vanguard)' >> "$UP/tests/CMakeLists.txt"
  git -C "$UP" status --porcelain=v1 --untracked-files=all > "$OUT/upstream-injection-status.txt"
  git -C "$UP" diff > "$OUT/upstream-injection.diff"
}

build_targets() {
  mkdir -p "$OUT"
  container '
    mkdir -p build/vanguard && cd build/vanguard
    start=$(date +%s)
    cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF \
      -D MANUAL_SUBMODULES=ON ../.. > /out/cmake.log 2>&1
    make -j'"$JOBS"' '"${*:-vanguard_tests}"' > /out/make.log 2>&1 || { tail -40 /out/make.log; exit 1; }
    end=$(date +%s)
    printf "{\"build_wall_seconds\": %s, \"container_memory_peak_bytes\": %s, \"jobs\": %s}\n" \
      "$((end-start))" "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo null)" '"$JOBS"' > /out/build-metrics.json'
}

run_vectors() {
  mkdir -p "$OUT/run1" "$OUT/run2"
  for r in run1 run2; do
    container '
      /src/build/vanguard/tests/vanguard/vanguard_tests \
        --data-dir=/src/tests/data --results=/out/'"$r"'/results.json --metrics=/out/'"$r"'/metrics.json \
        > /out/'"$r"'/stdout.log 2>&1
      echo "{\"container_memory_peak_bytes\": $(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo null)}" > /out/'"$r"'/container.json'
  done
  cmp "$OUT/run1/results.json" "$OUT/run2/results.json" || die "results.json differs between runs"
  echo "results.json byte-identical across run1/run2"
}

receipts() {
  container '
    B=build/vanguard
    {
      echo "image_id='"$IMAGE"'"
      echo "rustc: $(rustc -vV | tr "\n" ";")"
      echo "cargo: $(cargo -V)"
      echo "gxx: $(g++ --version | head -1)"
      echo "cmake: $(cmake --version | head -1)"
      echo "packages_sha256: $(dpkg-query -W -f="\${binary:Package}=\${Version}\n" | sort | sha256sum | cut -d" " -f1)"
    } > /out/toolchain.txt
    for f in $B/src/fcmp_pp/fcmp_pp_rust/libfcmp_pp_rust.a $B/src/fcmp_pp/libfcmp_pp.a \
             $B/src/carrot_core/libcarrot_core.a $B/src/carrot_impl/libcarrot_impl.a \
             $B/tests/vanguard/vanguard_tests; do
      printf "%s %s %s\n" "$(sha256sum "$f" | cut -d" " -f1)" "$(stat -c %s "$f")" "${f#$B/}"
    done > /out/artifacts.txt'
  git -C "$UP" rev-parse HEAD > "$OUT/upstream-head.txt"
  git -C "$UP" submodule status > "$OUT/upstream-submodules.txt"
  sha256sum "$UP/src/fcmp_pp/fcmp_pp_rust/Cargo.lock" | sed "s#$UP/##" > "$OUT/cargo-lock.sha256"
  (cd "$UP/tests/data" && sha256sum fcmp_pp_verify_inputs_*in.bin) > "$OUT/upstream-vectors.sha256"
  (cd "$UP/tests/vanguard" && sha256sum CMakeLists.txt vanguard_tests.cpp) > "$OUT/harness-source.sha256"
  cp "$LOCK_FILE" "$OUT/source-lock.json"
  (cd "$OUT" && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256)
}

case "${1:-all}" in
  prepare) prepare ;;
  build) shift; with_heavy_lock build_targets "$@" ;;
  run) with_heavy_lock run_vectors ;;
  receipts) receipts ;;
  all) prepare; with_heavy_lock build_targets; with_heavy_lock run_vectors; receipts ;;
  *) die "unknown stage $1" ;;
esac
