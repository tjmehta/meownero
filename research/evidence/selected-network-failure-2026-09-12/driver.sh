#!/usr/bin/env bash
set -euo pipefail
BASE=/tmp/meownero-selected-network-20260912
INPUTS="$BASE/runner-inputs"
export MEOW_BUILDER_IMAGE=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
finish() { result=$?; printf '%s\n' "$result" > "$BASE/driver.exit"; }
trap finish EXIT
for profile in selected-9-90 fallback-12-120; do
  printf '%s build %s\n' "$(date -u +%FT%TZ)" "$profile" | tee "$BASE/phase.txt"
  bash "$INPUTS/spikes/network-benchmark/build-profile.sh" \
    /tmp/meow-swarm-network-20260912-run/reproduction/first \
    "$INPUTS/spikes/selected-issuance" "$profile" \
    "$INPUTS/spikes/selected-issuance/selected-unit-fixtures.patch" "$BASE/$profile"
  printf '%s p2p %s\n' "$(date -u +%FT%TZ)" "$profile" | tee "$BASE/phase.txt"
  bash "$INPUTS/chain/test-network-p2p.sh" "$BASE/$profile/source" "$BASE/$profile/p2p" "$profile"
done
printf '%s completed both profiles\n' "$(date -u +%FT%TZ)" | tee "$BASE/phase.txt"
