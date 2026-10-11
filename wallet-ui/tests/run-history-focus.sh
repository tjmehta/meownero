#!/usr/bin/env bash
set -euo pipefail
BUILD=$(cd "$1" && pwd)
OUT=$(cd "$2" && pwd)
NUM=$3
HERE=$(cd "$(dirname "$0")" && pwd)
HELPERS="$HERE/../../research/evidence/native-wallet-tjs2018-2026-10-10/harness"
mkdir -p "$OUT/screens" "$OUT/raw"
test -S "/tmp/.X11-unix/X$NUM"
inner() {
    export DISPLAY=":$NUM" XDG_CURRENT_DESKTOP=GNOME QT_QPA_PLATFORMTHEME=gtk3
    /usr/libexec/at-spi-bus-launcher --launch-immediately &
    sleep 1
    /usr/bin/python3 -I "$HELPERS/portal_stub.py" "$OUT/raw/portal-status.txt" &
    PORTAL=$!
    trap 'kill "$PORTAL" 2>/dev/null || true' EXIT
    sleep 0.8
    source "$BUILD/../env.sh"
    /usr/bin/python3 -I "$HERE/history-focus-journey.py" "$BUILD/meownero-wallet" "$OUT" "$OUT/raw/portal-status.txt" "$PORTAL"
}
export -f inner
export NUM BUILD OUT HERE HELPERS
dbus-run-session -- bash -c inner 2>&1 | tee "$OUT/raw/history-focus.log"
