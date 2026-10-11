#!/usr/bin/env bash
# Runs the author journey checks on an owned, isolated Xephyr display inside a
# private D-Bus session with its own AT-SPI bus and a stub settings portal.
# Nothing here talks to the user's live desktop session bus or settings.
#
# usage: run-journeys.sh <wallet-ui-build-dir> <evidence-dir> [display-number]
set -euo pipefail
BUILD=$(cd "$1" && pwd)
OUT=$(cd "$2" && pwd)
NUM=${3:-47}
JOURNEY=${JOURNEY:-ABCD}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT/screens" "$OUT/raw"

if [ ! -S "/tmp/.X11-unix/X$NUM" ]; then
    echo "Start the isolated display first, for example:" >&2
    echo "  DISPLAY=:0 Xephyr :$NUM -screen 1500x800 -nolisten tcp &" >&2
    exit 2
fi

inner() {
    set -euo pipefail
    export DISPLAY=":$NUM" XDG_CURRENT_DESKTOP=GNOME QT_QPA_PLATFORMTHEME=gtk3
    /usr/libexec/at-spi-bus-launcher --launch-immediately &
    sleep 1
    /usr/bin/python3 -I "$HERE/portal_stub.py" "$OUT/raw/portal-status.txt" &
    PORTAL=$!
    sleep 0.8
    source "$BUILD/../env.sh"
    /usr/bin/python3 -I "$HERE/journey.py" "$BUILD/meownero-wallet" "$OUT" "$OUT/raw/portal-status.txt" "$PORTAL"
    kill "$PORTAL" 2>/dev/null || true
}
export -f inner
export NUM BUILD OUT HERE JOURNEY
dbus-run-session -- bash -c inner 2>&1 | tee "$OUT/raw/journey-run.log"
