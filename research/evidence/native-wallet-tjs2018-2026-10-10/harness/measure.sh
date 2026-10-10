#!/usr/bin/env bash
# Host, toolchain and executable facts plus single-host startup/idle/RSS
# observations for the native wallet. Runs on the owned Xephyr display without
# an accessibility bus. Writes raw/measure.txt and raw/qt-libraries-loaded.txt.
#
# usage: measure.sh <wallet-ui-dir> <evidence-dir> [display-number]
set -eu  # no pipefail: "| head -1" would SIGPIPE
UI=$(cd "$1" && pwd)
OUT=$(cd "$2" && pwd)
NUM=${3:-47}
source "$UI/env.sh"
BIN="$UI/build/meownero-wallet"
R="$OUT/raw/measure.txt"
{
echo "## Host"
uname -srvmo
grep PRETTY_NAME /etc/os-release
ldd --version | head -1
echo "display: Xephyr :$NUM (nested in the host's GNOME/Xorg session), no window manager"
echo
echo "## Toolchain"
gcc --version | head -1
cmake --version | head -1
echo "ninja $(ninja --version)"
"$MEOWNERO_TOOLCHAIN/venv/bin/aqt" version 2>&1 | head -1
echo "Qt: $(cat "$QTDIR/mkspecs/qconfig.pri" | grep -E '^QT_VERSION *=' | head -1)"
for l in libQt6Core.so.6 libQt6Gui.so.6 libQt6Qml.so.6 libQt6Quick.so.6 libQt6QuickControls2.so.6 libQt6QuickTemplates2.so.6 libQt6XcbQpa.so.6; do
    sha256sum "$(readlink -f "$QTDIR/lib/$l")"
done
sha256sum "$MEOWNERO_TOOLCHAIN"/debs/*.deb
echo "toolchain installed bytes: $(du -sb "$MEOWNERO_TOOLCHAIN/qt" | cut -f1) (Qt) $(du -sb "$MEOWNERO_TOOLCHAIN/sysroot" | cut -f1) (sysroot) $(du -sb "$MEOWNERO_TOOLCHAIN/venv" | cut -f1) (aqt venv)"
echo
echo "## Executable"
sha256sum "$BIN"
stat -c 'bytes %s' "$BIN"
file "$BIN"
echo "linked Qt modules:"; ldd "$BIN" | grep -o 'libQt6[A-Za-z0-9]*' | sort -u | tr '\n' ' '; echo
echo
echo "## Reproducibility: clean rebuild in a second directory"
rm -rf /tmp/tjs2018-rebuild && cmake -S "$UI" -B /tmp/tjs2018-rebuild -G Ninja -DCMAKE_BUILD_TYPE=Release >/dev/null && cmake --build /tmp/tjs2018-rebuild --target meownero-wallet >/dev/null
sha256sum /tmp/tjs2018-rebuild/meownero-wallet
if cmp -s /tmp/tjs2018-rebuild/meownero-wallet "$BIN"; then echo "byte-identical to the candidate build"; else echo "DIFFERS from the candidate build"; fi
rm -rf /tmp/tjs2018-rebuild
echo
echo "## Startup: process launch to mapped window (5 cold-ish runs; page cache not dropped)"
export DISPLAY=":$NUM"
for i in 1 2 3 4 5; do
    t0=$(date +%s.%N)
    "$BIN" --start overview >/dev/null 2>&1 &
    pid=$!
    while ! xdotool search --name '^Meownero Wallet —' >/dev/null 2>&1; do sleep 0.01; done
    t1=$(date +%s.%N)
    echo "run $i: $(echo "$t1 - $t0" | bc) s"
    if [ $i -eq 5 ]; then
        sleep 3
        a=$(awk '{print $14+$15}' /proc/$pid/stat); sleep 10; b=$(awk '{print $14+$15}' /proc/$pid/stat)
        echo "idle CPU over 10 s after 3 s settle: $((b - a)) ticks (CLK_TCK $(getconf CLK_TCK))"
        grep -E 'VmRSS|VmHWM' /proc/$pid/status
        awk '$6 ~ /\.so/ {print $6}' /proc/$pid/maps | sort -u > "$OUT/raw/libraries-loaded.txt"
        echo "shared objects mapped: $(wc -l < "$OUT/raw/libraries-loaded.txt"), of which from the Qt toolchain: $(grep -c "$MEOWNERO_TOOLCHAIN" "$OUT/raw/libraries-loaded.txt")"
        echo "bytes of Qt toolchain libraries/plugins mapped: $(grep "$MEOWNERO_TOOLCHAIN" "$OUT/raw/libraries-loaded.txt" | xargs stat -L -c %s | paste -sd+ | bc)"
    fi
    kill $pid; wait $pid 2>/dev/null || true
done
echo
echo "## Limits"
echo "Single host and display; nested X server; no window manager; caches warm after the first run; ticks are 10 ms resolution;"
echo "mapped-window time is not first-frame time; mapped library bytes are not an installer size; no package was built."
} > "$R" 2>&1
cat "$R"
