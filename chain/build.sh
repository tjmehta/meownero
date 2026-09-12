#!/usr/bin/env bash
# Meownero chain build: pinned upstream + reviewable patch series, built in an Ubuntu container.
#
#   chain/build.sh [workdir]        # default workdir: ./build/chain
#
# Steps: (1) clone monero at the pinned tag with submodules and verify every commit hash against
# chain/upstream.lock; (2) apply chain/patches/*.patch with `git am` (fails on drift); (3) build
# monerod, monero-wallet-cli, monero-wallet-rpc and unit_tests inside the builder image from
# chain/Dockerfile; (4) run the Meownero consensus tests; (5) print SHA-256 of the binaries.
# No sudo needed; Docker is the only host dependency. Nothing here touches any network except the
# git clone and the base-image pull.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(realpath -m "${1:-$HERE/../build/chain}")
SRC="$WORK/monero"
IMG=${MEOW_BUILDER_IMAGE:-meownero-chain-builder}
mkdir -p "$WORK"

# shellcheck disable=SC1091
source "$HERE/upstream.lock"   # UPSTREAM_URL, UPSTREAM_TAG, UPSTREAM_COMMIT, SUBMODULE_<name>=<commit>

echo "==> 1. upstream $UPSTREAM_TAG ($UPSTREAM_COMMIT)"
if [ ! -d "$SRC/.git" ]; then
  git clone --quiet --depth 1 --branch "$UPSTREAM_TAG" --recurse-submodules --shallow-submodules "$UPSTREAM_URL" "$SRC"
fi
actual=$(git -C "$SRC" rev-parse HEAD)
[ "$actual" = "$UPSTREAM_COMMIT" ] || { echo "upstream commit mismatch: $actual != $UPSTREAM_COMMIT"; exit 1; }
while IFS='=' read -r k v; do
  case "$k" in SUBMODULE_*) name=${k#SUBMODULE_}; path="external/${name//_/-}"; got=$(git -C "$SRC" -C "$path" rev-parse HEAD)
    [ "$got" = "$v" ] || { echo "submodule $path mismatch: $got != $v"; exit 1; };; esac
done < "$HERE/upstream.lock"
echo "    pins verified"

echo "==> 2. patch series"
if git -C "$SRC" rev-parse --verify -q meownero >/dev/null; then
  git -C "$SRC" checkout -q meownero
else
  git -C "$SRC" checkout -q -b meownero "$UPSTREAM_COMMIT"
  git -C "$SRC" -c user.name=meownero-build -c user.email=build@meownero.invalid am --quiet --committer-date-is-author-date "$HERE"/patches/*.patch
fi
n=$(git -C "$SRC" rev-list --count "$UPSTREAM_COMMIT"..HEAD); echo "    $n patches applied; $(git -C "$SRC" diff "$UPSTREAM_COMMIT" --shortstat)"

echo "==> 3. build in $IMG"
if [ -z "${MEOW_BUILDER_IMAGE:-}" ]; then
  docker build -q -t "$IMG" -f "$HERE/Dockerfile" "$HERE" >/dev/null
fi
IMG=$(docker image inspect "$IMG" --format '{{.Id}}')
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"
docker run --rm --network none "$IMG" dpkg-query -W -f='${binary:Package}=${Version}\n' > "$WORK/packages.txt"
cache_args=()
if [ "${CCACHE_DISABLE:-0}" != 1 ]; then
  cache_args=(-v meownero-chain-ccache:/root/.ccache -e CCACHE_DIR=/root/.ccache)
fi
docker run --rm --network none -v "$SRC:/src" "${cache_args[@]}" -e CCACHE_DISABLE -e MEOW_JOBS="${MEOW_JOBS:-2}" -w /src "$IMG" bash -ec '
  git config --global --add safe.directory "*"
  mkdir -p build/release && cd build/release
  cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D CMAKE_C_COMPILER_LAUNCHER=ccache -D CMAKE_CXX_COMPILER_LAUNCHER=ccache ../.. > cmake.log 2>&1
  make -j"$MEOW_JOBS" daemon simplewallet wallet_rpc_server unit_tests meow_difficulty_floor_tests > make.log 2>&1 || { tail -30 make.log; exit 1; }'

echo "==> 4. Meownero consensus tests"
docker run --rm --network none -v "$SRC:/src:ro" -w /src/build/release "$IMG" timeout 180 ./tests/unit_tests/unit_tests --gtest_filter='meow_*:cryptonote_protocol_handler.race_condition' 2>&1 | tail -2

MEOW_BUILDER_IMAGE="$IMG" bash "$HERE/test-difficulty.sh" "$SRC"
MEOW_BUILDER_IMAGE="$IMG" bash "$HERE/test-authorities.sh" "$SRC"

echo "==> 5. artifacts"
for b in monerod monero-wallet-cli monero-wallet-rpc; do printf '%s  %s\n' "$(sha256sum "$SRC/build/release/bin/$b" | cut -d' ' -f1)" "$b"; done | tee "$WORK/SHA256SUMS"

# Exact local source inputs and binary versions accompany every hash set.
git -C "$SRC" rev-parse HEAD 'HEAD^{tree}' > "$WORK/SOURCE_REVISIONS"
git -C "$SRC" submodule status --recursive > "$WORK/SUBMODULES"
(cd "$HERE" && sha256sum upstream.lock patches/*.patch) > "$WORK/INPUT_SHA256SUMS"
docker run --rm --network none -v "$SRC:/src:ro" "$IMG" bash -ec '
  c++ --version
  cmake --version
  for b in monerod monero-wallet-cli monero-wallet-rpc; do /src/build/release/bin/$b --version; done
' > "$WORK/VERSIONS"
