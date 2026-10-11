pragma Singleton
import QtQuick
import Meownero.Core

// Accepted design tokens (prototype revision 5), converted from OKLCH to sRGB.
// One accent bound to the network the node reports; appearance follows the system.
QtObject {
    readonly property bool dark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property bool testnet: Wallet.networkKey === "testnet"
    readonly property bool reducedMotion: Wallet.reducedMotion

    readonly property color bg: dark ? "#12100e" : "#fbfaf8"
    readonly property color side: dark ? "#0d0b09" : "#f3f2ee"
    readonly property color surface: dark ? "#1a1815" : "#ffffff"
    readonly property color surface2: dark ? "#23201c" : "#f2f0ec"
    readonly property color chrome: dark ? "#181613" : "#edebe7"
    readonly property color fg: dark ? "#f1eee9" : "#1e1a16"
    readonly property color muted: dark ? "#a5a199" : "#5f5a54"
    readonly property color faint: dark ? "#78746e" : "#8a8580"
    readonly property color border: dark ? "#17ffffff" : "#17000000"
    readonly property color borderStrong: dark ? "#2bffffff" : "#2b000000"
    readonly property color warn: dark ? "#ff9c6b" : "#ab4400"
    readonly property color warnSoft: dark ? "#21ff9c6b" : "#24e97c48"
    readonly property color danger: dark ? "#fd736d" : "#c92324"
    readonly property color dangerSoft: dark ? "#24fd736d" : "#1ade3c37"
    readonly property color ok: dark ? "#6ecc8a" : "#168b49"
    readonly property color net: testnet ? (dark ? "#54d1cd" : "#007478") : (dark ? "#ad9bf6" : "#6949ba")
    readonly property color netSoft: testnet ? (dark ? "#2454d1cd" : "#17007478") : (dark ? "#26ad9bf6" : "#176949ba")
    readonly property color netInk: testnet ? (dark ? "#011615" : "#fcfcfc") : (dark ? "#100d1b" : "#fcfcfc")

    // Point sizes so the system text-scaling setting applies (px * 0.75).
    function pt(px) { return px * 0.75 }
    readonly property string mono: "monospace"

    readonly property int controlRadius: 8
    readonly property int cardRadius: 12
    // 180 ms page entry, 200 ms sheets; nothing moves under reduced motion.
    readonly property int pageMs: reducedMotion ? 0 : 180
    readonly property int sheetMs: reducedMotion ? 0 : 200
}
