#!/usr/bin/env bash
set -euo pipefail
cd <repo>
printf '%s\n' "$$" > <repo>/build/recovery-network-20260913/selected-9-90-launch-01/driver.pid
trap 'result=$?; printf "%s\n" "$result" > <repo>/build/recovery-network-20260913/selected-9-90-launch-01/driver.exit' EXIT
export MEOW_PROFILE_SOURCE_ONLY=1 MEOW_NETWORK_WAIT_SECONDS=60
bash <repo>/build/recovery-network-20260913/selected-9-90-launch-01/inputs/spikes/network-benchmark/build-profile.sh <repo>/build/recovery-network-20260913/source <repo>/build/recovery-network-20260913/selected-9-90-launch-01/inputs/spikes/selected-issuance selected-9-90 <repo>/build/recovery-network-20260913/selected-9-90-launch-01/inputs/spikes/selected-issuance/selected-unit-fixtures.patch <repo>/build/recovery-network-20260913/selected-9-90-launch-01/output
