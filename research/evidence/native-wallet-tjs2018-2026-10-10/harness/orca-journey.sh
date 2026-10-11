#!/usr/bin/env bash
# One real Orca journey on the owned Xephyr display, in a private D-Bus session
# with its own AT-SPI bus, a temporary HOME and runtime directory, and no audio
# sink (so nothing is spoken on the user's live desktop). Orca's debug log
# records every utterance it generates; the SPEECH OUTPUT lines are the result.
#
# usage: orca-journey.sh <wallet-ui-build-dir> <evidence-dir> [display-number]
set -euo pipefail
BUILD=$(cd "$1" && pwd)
OUT=$(cd "$2" && pwd)
NUM=${3:-47}
HERE=$(cd "$(dirname "$0")" && pwd)
export MEOWNERO_TOOLCHAIN="${MEOWNERO_TOOLCHAIN:-$HOME/.local/share/meownero/toolchain}"
SANDBOX=$(mktemp -d /tmp/tjs2018-orca.XXXXXX)
mkdir -p "$SANDBOX/home" "$SANDBOX/run" "$OUT/raw"
chmod 700 "$SANDBOX/run"
# Silent but working audio: speech-dispatcher plays into ALSA's null device, so
# Orca keeps speaking (and logging) without sound reaching the user's desktop.
mkdir -p "$SANDBOX/home/.config/speech-dispatcher"
printf 'pcm.!default { type null }\nctl.!default { type hw card 0 }\n' > "$SANDBOX/home/.asoundrc"
sed -E 's/^#? *AudioOutputMethod.*/AudioOutputMethod "alsa"/' /etc/speech-dispatcher/speechd.conf \
    > "$SANDBOX/home/.config/speech-dispatcher/speechd.conf"

inner() {
    set -euo pipefail
    export DISPLAY=":$NUM" HOME="$SANDBOX/home" XDG_RUNTIME_DIR="$SANDBOX/run" \
        XDG_CONFIG_HOME="$SANDBOX/home/.config" XDG_DATA_HOME="$SANDBOX/home/.local/share" \
        XDG_CURRENT_DESKTOP=GNOME QT_QPA_PLATFORMTHEME=gtk3 \
        PULSE_SERVER=unix:/nonexistent PIPEWIRE_REMOTE=/nonexistent ALSA_CONFIG_PATH=/usr/share/alsa/alsa.conf
    /usr/libexec/at-spi-bus-launcher --launch-immediately &
    sleep 1
    /usr/bin/python3 -I "$HERE/portal_stub.py" "$SANDBOX/portal.txt" &
    sleep 0.5
    orca --replace --debug-file "$SANDBOX/orca-debug.log" > "$SANDBOX/orca-stdout.log" 2>&1 &
    ORCA=$!
    sleep 4
    source "$BUILD/../env.sh"
    "$BUILD/meownero-wallet" --start "$1" > "$SANDBOX/app.log" 2>&1 &
    APP=$!
    sleep 3
    WIN=$(xdotool search --name "^Meownero Wallet —" | head -1)
    xdotool windowfocus --sync "$WIN"
    xdotool mousemove --window "$WIN" 420 14 click 1
    sleep 1.5
    k() { xdotool key --clearmodifiers "$@"; sleep "${PAUSE:-1.2}"; }
    t() { xdotool type --delay 40 "$1"; sleep 0.8; }
    if [ "$1" = welcome ]; then
        k Tab; k Tab; k Return                   # Create a new wallet -> heading
        k Tab; k ctrl+a; t "Orca QA"; k Tab; t "passw0rd!"; k Tab; t "different"; k Return
        k ctrl+a; t "passw0rd!"; k Return       # recovery words heading
        k Tab; k Return                          # Show words
        k Tab; k space                           # acknowledgement check box
        k Tab; k Tab; k Return                   # Continue -> word check
        k Tab; k Tab; k Tab
    else
        k ctrl+3
        k Tab; k space                           # Test wallet B (pressed)
        k Tab; k Tab; k Tab; t "0,5"; k Return   # refused amount; focus stays, error read
        k ctrl+a; t "2.5"; PAUSE=2.5 k Return    # preparing, then review on its Send button
        k Tab                                    # Edit
        k Tab                                    # Send 2.5 MEOW
        PAUSE=3 k Return                         # submit; outcome announced
        k ctrl+5; k Tab
    fi
    kill $APP 2>/dev/null || true
    sleep 1
    kill $ORCA 2>/dev/null || true
    sleep 1
}
export -f inner
export NUM BUILD OUT HERE SANDBOX
for start in welcome overview; do
    rm -f "$SANDBOX/orca-debug.log"
    dbus-run-session -- bash -c "inner $start" > "$SANDBOX/session-$start.log" 2>&1 || true
    grep -E "SPEECH OUTPUT" "$SANDBOX/orca-debug.log" > "$OUT/raw/orca-speech-$start.txt" || true
    cp "$SANDBOX/orca-debug.log" "$SANDBOX/orca-debug-$start.log" 2>/dev/null || true
    echo "$start: $(wc -l < "$OUT/raw/orca-speech-$start.txt") speech lines"
done
orca --version > "$OUT/raw/orca-version.txt"
echo "sandbox: $SANDBOX"
