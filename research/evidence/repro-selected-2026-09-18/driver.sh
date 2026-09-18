#!/usr/bin/env bash
# TJS-40: two clean cache-disabled source-only builds per profile, sequential, under the existing guard.
set -uo pipefail
RUN=<repo>/build/repro-selected-20260918
cd <repo>
printf '%s\n' "$$" > "$RUN/driver.pid"
trap 'r=$?; printf "%s\n" "$r" > "$RUN/driver.exit"' EXIT
export MEOW_PROFILE_SOURCE_ONLY=1 MEOW_NETWORK_WAIT_SECONDS=60
for cell in selected-9-90/first selected-9-90/second fallback-12-120/first fallback-12-120/second; do
  profile=${cell%/*}
  printf '%s start %s MemAvailable=%s KiB\n' "$(date -u +%FT%TZ)" "$cell" "$(awk '/MemAvailable/ {print $2}' /proc/meminfo)"
  bash "$RUN/inputs/spikes/network-benchmark/build-profile.sh" \
    "$PWD/build/recovery-network-20260913/source" "$RUN/inputs/spikes/selected-issuance" "$profile" \
    "$RUN/inputs/spikes/selected-issuance/selected-unit-fixtures.patch" "$RUN/$cell" > "$RUN/$cell.launch.log" 2>&1
  rc=$?
  printf '%s end %s exit=%s\n' "$(date -u +%FT%TZ)" "$cell" "$rc"
  if (( rc == 75 )); then printf 'RESOURCE BLOCKER: guard refused (%s) - heavy lock busy or <5 GiB RAM/disk; stopping, no competing heavy work\n' "$cell"; exit 75; fi
  if (( rc != 0 )); then printf 'BUILD FAILURE %s exit=%s; stopping\n' "$cell" "$rc"; exit "$rc"; fi
done
printf 'all four builds completed\n'
