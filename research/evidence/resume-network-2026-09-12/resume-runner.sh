#!/usr/bin/env bash
set -uo pipefail
export MEOW_BUILDER_IMAGE=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
export MEOW_REPRO_BUILD_RUNNER=/tmp/meow-swarm-network-20260912-run/frozen-inputs-15/chain/network-build-guard.sh
timeout --signal=TERM --kill-after=60 10800 bash /tmp/meow-swarm-network-20260912-run/frozen-inputs-15/chain/test-reproducibility.sh /tmp/meow-swarm-network-20260912-run/reproduction
status=$?
printf '%s\n' "$status" > /tmp/meow-swarm-network-20260912-run/resume-once/reproduction.exit
exit "$status"
