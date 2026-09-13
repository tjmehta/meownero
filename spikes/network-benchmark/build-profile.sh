#!/usr/bin/env bash
# No selected build until the coordinator supplies a reviewed profile fixture patch.
# Usage: build-profile.sh historical-run issuance-dir profile fixture.patch NEW-output
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
if [[ ${1:-} != --locked ]]; then
  [[ $# == 5 ]] || { echo 'usage: build-profile.sh historical-run issuance-dir profile fixture.patch NEW-output' >&2; exit 2; }
  [[ -s $4 ]] || { echo 'explicit coordinator fixture patch is required; no build started' >&2; exit 2; }
  exec bash "$ROOT/chain/network-build-guard.sh" bash "$0" --locked "$@"
fi
shift
declare -F docker >/dev/null || { echo "guard Docker wrapper missing" >&2; exit 2; }
[[ ${MEOW_JOBS:-} == 1 ]] || { echo "guard compiler-job setting missing" >&2; exit 2; }
[[ $(readlink /proc/$$/fd/9) == /tmp/meownero-swarm-20260912-heavy.lock ]] || { echo 'guard lock missing' >&2; exit 2; }
flock -n 9 || { echo 'guard lock not held' >&2; exit 75; }
HISTORICAL=$(realpath "$1")
ISSUANCE=$(realpath "$2")
PROFILE=$3
FIXTURE=$(realpath "$4")
OUT=$(realpath -m "$5")
case "$PROFILE" in selected-9-90|fallback-12-120) ;; *) echo 'unknown selected profile' >&2; exit 2;; esac
for input in "$HISTORICAL" "$ISSUANCE" "$(dirname "$FIXTURE")"; do
  case "$OUT/" in "$input/"*) echo 'output overlaps inputs' >&2; exit 2;; esac
done
[[ ! -e $OUT ]] || { echo 'output must not exist' >&2; exit 2; }
mkdir -p "$OUT/source"
disk_kib=$(df -Pk "$OUT" | awk 'END {print $4}')
(( disk_kib >= 5 * 1024 * 1024 )) || { echo 'need >=5 GiB output disk' >&2; exit 75; }
IMG=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
[[ $(docker image inspect "$IMG" --format '{{.Id}}') == "$IMG" ]]
printf '%s\n' "$IMG" > "$OUT/BUILDER_IMAGE_ID"
# Stop only this owned container on interruption; the container's own timeout also
# bounds compilation and tests without leaving a detached compiler behind.
# shellcheck disable=SC2317 # Invoked indirectly by the EXIT trap.
cleanup() {
  for cid in "$OUT/container.cid" "$OUT/dns-container.cid"; do
    if [[ -s $cid ]]; then docker rm -f "$(cat "$cid")" >/dev/null 2>&1 || true; fi
  done
}
# shellcheck disable=SC2317 # Invoked indirectly by the EXIT trap.
finish_run() {
  result=$?
  printf '%s\n' "$result" > "$OUT/build.exit"
  cleanup
}
trap finish_run EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
set +e
docker run --rm -i --cidfile "$OUT/container.cid" --network none \
  -e CCACHE_DISABLE=1 -e MEOW_JOBS=1 -e PYTHONDONTWRITEBYTECODE=1 -e GIT_OPTIONAL_LOCKS=0 \
  -e MEOW_PROFILE_SOURCE_ONLY="${MEOW_PROFILE_SOURCE_ONLY:-0}" -e PROFILE="$PROFILE" -v "$HISTORICAL:/historical:ro" -v "$ISSUANCE:/issuance:ro" \
  -v "$FIXTURE:/fixture.patch:ro" -v "$ROOT/research/evidence/clean15-2026-09-12/first:/receipts:ro" \
  -v "$HERE:/harness:ro" -v "$OUT/source:/src" -v "$OUT:/out" \
  "$IMG" timeout --signal=TERM --kill-after=60 7200 bash -se <<'BUILD' 2>&1 | tee "$OUT/run.log"
set -euo pipefail
git config --global --add safe.directory '*'
finish() {
  result=$?
  for field in memory.peak memory.events memory.max memory.swap.max cpu.max; do
    cat "/sys/fs/cgroup/$field" > "/out/cgroup-$field"
  done
  printf '%s\n' "$result" > /out/container.exit
}
trap finish EXIT
python3 /harness/stage-profile-build.py --historical /historical --receipts /receipts \
  --issuance /issuance --fixture /fixture.patch --profile "$PROFILE" --source /src --output /out
mkdir -p /src/build/release
cd /src/build/release
cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON \
  -D CMAKE_C_COMPILER_LAUNCHER=ccache -D CMAKE_CXX_COMPILER_LAUNCHER=ccache ../.. > /out/cmake.log 2>&1
make -j1 daemon simplewallet wallet_rpc_server unit_tests meow_difficulty_floor_tests > /out/make.log 2>&1
# Full executables are rebuilt; retain the existing three documented CI exclusions.
cd /tmp
timeout 300 /src/build/release/tests/unit_tests/unit_tests \
  --gtest_filter='meow_*:cryptonote_protocol_handler.race_condition' --gtest_output=xml:/out/consensus.xml > /out/consensus.log 2>&1
timeout 180 /src/build/release/tests/unit_tests/unit_tests \
  --gtest_filter='meow_difficulty.*:difficulty.*' --gtest_output=xml:/out/difficulty.xml > /out/difficulty.log 2>&1
timeout 180 /src/build/release/tests/unit_tests/meow_difficulty_floor_tests \
  --gtest_filter='meow_difficulty.*:difficulty.*' --gtest_output=xml:/out/floor.xml > /out/floor.log 2>&1
/src/build/release/tests/unit_tests/unit_tests --gtest_list_tests \
  --gtest_filter='-ban.subnet:http_server.response_soft_limit:notify.works' > /out/native-expected.txt
cp -a /src/tests/data /tmp/test-data
timeout 600 /src/build/release/tests/unit_tests/unit_tests --data-dir /tmp/test-data \
  --gtest_filter='-ban.subnet:http_server.response_soft_limit:notify.works:AddressFromURL.*:DNSResolver.*' \
  --gtest_output=xml:/out/full-native-offline.xml > /out/full-native-offline.log 2>&1

BUILD
pipeline_results=("${PIPESTATUS[@]}")
build_result=${pipeline_results[0]}
if (( build_result == 0 && pipeline_results[1] != 0 )); then build_result=${pipeline_results[1]}; fi
set -e
printf '%s\n' "$build_result" > "$OUT/offline.exit"

if (( build_result != 0 )); then exit "$build_result"; fi
set +e
docker run --rm -i --cidfile "$OUT/dns-container.cid" --network bridge \
  -e PYTHONDONTWRITEBYTECODE=1 -e GIT_OPTIONAL_LOCKS=0 -e MEOW_PROFILE_SOURCE_ONLY="${MEOW_PROFILE_SOURCE_ONLY:-0}" \
  -v "$HISTORICAL:/historical:ro" -v "$OUT/source:/src:ro" -v "$OUT:/out" -v "$HERE:/harness:ro" \
  -v "$ROOT/research/evidence/clean15-2026-09-12/first:/receipts:ro" \
  "$IMG" timeout --signal=TERM --kill-after=30 600 bash -se <<'DNS' 2>&1 | tee "$OUT/dns-run.log"
set -euo pipefail
git config --global --add safe.directory '*'
cd /tmp
cp -a /src/tests/data /tmp/test-data
printf 'bridge; no published ports; public DNS unit fixtures only\n' > /out/dns-network-scope.txt
timeout 300 /src/build/release/tests/unit_tests/unit_tests --data-dir /tmp/test-data \
  --gtest_filter='AddressFromURL.*:DNSResolver.*' --gtest_output=xml:/out/dns.xml > /out/dns.log 2>&1
python3 - <<'PY'
import json,pathlib,runpy,subprocess,xml.etree.ElementTree as ET
out=pathlib.Path('/out'); src=pathlib.Path('/src')
m=runpy.run_path('/harness/clean15-provenance.py')
runpy.run_path('/harness/stage-profile-build.py')['original_source'](pathlib.Path('/historical'),pathlib.Path('/receipts'))
runpy.run_path('/harness/merge-native-results.py')['merge'](out)
results={}
for name in ('consensus','difficulty','floor','full-native-offline','dns','full-native'):
 root=ET.parse(out/(name+'.xml')).getroot()
 assert int(root.attrib['tests'])>0 and int(root.attrib['failures'])==0 and int(root.attrib.get('errors',0))==0
 results[name]=dict(root.attrib)
artifacts={str(p.relative_to(src)):m['digest'](p) for p in [
 src/'build/release/bin'/b for b in ('monerod','monero-wallet-cli','monero-wallet-rpc')]}
artifacts.update({str(p.relative_to(src)):m['digest'](p) for p in [
 src/'build/release/tests/unit_tests'/b for b in ('unit_tests','meow_difficulty_floor_tests')]})
(out/'SHA256SUMS').write_text(''.join(f'{h}  {p}\n' for p,h in artifacts.items()))
versions=subprocess.check_output(['c++','--version'],text=True)+subprocess.check_output(['cmake','--version'],text=True)
for binary in ('monerod','monero-wallet-cli','monero-wallet-rpc'):
 versions+=subprocess.check_output([str(src/'build/release/bin'/binary),'--version'],text=True)
(out/'VERSIONS').write_text(versions)
(out/'packages.txt').write_bytes(subprocess.check_output(['dpkg-query','-W','-f=${binary:Package}=${Version}\n']))
receipt=json.loads((out/'profile-inputs.json').read_text())
receipt.update(build_completed=True,tests=results,historical_source_preserved=True,
               historical_build_preserved=(None if receipt['source_only'] else True),
               limits=[receipt['scope'],'native CI selection excludes only ban.subnet, http_server.response_soft_limit, notify.works; DNS-only phase uses normal networking',
                       'no runtime wallet/RPC/authority/P2P/FCMP readiness claim'])
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
PY
DNS
pipeline_results=("${PIPESTATUS[@]}")
build_result=${pipeline_results[0]}
if (( build_result == 0 && pipeline_results[1] != 0 )); then build_result=${pipeline_results[1]}; fi
set -e
printf '%s\n' "$build_result" > "$OUT/dns.exit"
exit "$build_result"
