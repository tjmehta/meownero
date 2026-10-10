import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

ApplicationWindow {
    id: win
    property bool showFixtures: false
    visible: true
    width: 1040
    height: 720
    minimumWidth: 880
    minimumHeight: 600
    title: "Meownero Wallet — " + Wallet.networkTitle + " (simulated)"
    color: Theme.bg

    palette.window: Theme.bg
    palette.windowText: Theme.fg
    palette.base: Theme.surface
    palette.text: Theme.fg
    palette.button: Theme.surface
    palette.buttonText: Theme.fg
    palette.highlight: Theme.net
    palette.highlightedText: Theme.netInk
    palette.placeholderText: Theme.faint
    palette.toolTipBase: Theme.fg
    palette.toolTipText: Theme.bg
    palette.mid: Theme.borderStrong
    palette.dark: Theme.muted

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // The network is always named and can't be dismissed (TJS-1994 #1).
        Rectangle {
            id: ribbon
            Layout.fillWidth: true
            implicitHeight: ribbonRow.implicitHeight + 10
            color: Theme.netSoft
            Accessible.role: Accessible.StaticText
            Accessible.name: Wallet.networkName + " · Test coins only. " + Wallet.networkSay + " Simulated build: wallet actions are simulated."
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
            RowLayout {
                id: ribbonRow
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 14; rightMargin: 14 }
                spacing: 10
                Icon { name: "flask"; size: 14; color: Theme.net }
                Text { text: Wallet.networkName + " · Test coins only"; font.pointSize: Theme.pt(12.5); font.weight: Font.DemiBold; color: Theme.net; Accessible.ignored: true }
                Text {
                    Layout.fillWidth: true
                    text: Wallet.networkSay + "  Simulated build · Wallet actions are simulated."
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    font.pointSize: Theme.pt(12.5)
                    color: Theme.fg
                    opacity: 0.86
                    Accessible.ignored: true
                }
                AppButton {
                    id: aboutNetButton
                    text: "What does this mean?"
                    kind: "quiet"
                    font.pointSize: Theme.pt(12.5)
                    topPadding: 2; bottomPadding: 2
                    onClicked: { about.returnFocusTo = aboutNetButton; about.open() }
                }
            }
        }

        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: Wallet.onboarding ? onboarding : shell
        }
    }
    Component { id: onboarding; OnboardingPage {} }
    Component { id: shell; ShellPage {} }

    // One polite announcement channel; the toast is visual only (N9).
    Connections {
        target: Wallet
        function onAnnounce(message) { ribbon.Accessible.announce(message) }
        function onToastChanged() { toast.show(Wallet.toastText) }
    }

    Rectangle {
        id: toast
        property string message: ""
        function show(m) { message = m; opacity = 1; hideTimer.restart() }
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height - height - 18 - (Theme.reducedMotion ? 0 : (opacity > 0 ? 4 : 0))
        width: toastText.implicitWidth + 28
        height: toastText.implicitHeight + 16
        radius: 8
        color: Theme.fg
        opacity: 0
        visible: opacity > 0
        Accessible.ignored: true
        Behavior on opacity { NumberAnimation { duration: 160 } }
        Behavior on y { enabled: !Theme.reducedMotion; NumberAnimation { duration: 200; easing.type: Easing.OutQuint } }
        Text { id: toastText; anchors.centerIn: parent; text: toast.message; color: Theme.bg; font.pointSize: Theme.pt(13); font.weight: Font.Medium; Accessible.ignored: true }
        Timer { id: hideTimer; interval: 1600; onTriggered: toast.opacity = 0 }
    }

    // Platform shortcuts: Ctrl/⌘+1–6 sections, Ctrl/⌘+L lock, ⌘, settings on macOS.
    Repeater {
        model: ["overview", "activity", "send", "receive", "node", "wallet"]
        Item {
            required property string modelData
            required property int index
            Shortcut {
                sequence: "Ctrl+" + (index + 1)
                enabled: !Wallet.onboarding && UiState.openDialogs === 0
                onActivated: Wallet.navigate(modelData)
            }
        }
    }
    Shortcut { sequence: StandardKey.Preferences; enabled: !Wallet.onboarding && UiState.openDialogs === 0; onActivated: Wallet.navigate("wallet") }
    Shortcut { sequence: "Ctrl+L"; enabled: !Wallet.onboarding; onActivated: Wallet.lock() }

    AppDialog {
        id: about
        title: Wallet.networkKey === "regtest" ? "About the local regtest" : "About the Meownero testnet"
        initialFocus: gotIt
        contentItem: ColumnLayout {
            spacing: 10
            Repeater {
                model: Wallet.networkKey === "regtest" ? [
                    "An isolated, accelerated FCMP++/CARROT test chain. Coins have no value. It runs only inside the Meownero test kit on this computer.",
                    "This local test uses FCMP++ and CARROT for transaction privacy. It does not establish anonymity or Internet privacy.",
                    "Its addresses use Monero's format (they start with 4), so never send real Monero to them. Meownero's planned reward of 9 MEOW every 90 seconds isn't applied yet.",
                    "A shared Meownero testnet and mainnet don't exist yet. Nothing here launches or joins a public network.",
                    "This build is simulated: it is not connected to the test kit, a node or any network."
                ] : [
                    "A future shared test network for trying Meownero with other people. Its coins would have no value.",
                    "Design preview: this network isn't live. The T… addresses come from a provisional spec and are placeholders, not what the current kit produces.",
                    "This build is simulated: it is not connected to the test kit, a node or any network."
                ]
                Text { required property string modelData; required property int index; Layout.fillWidth: true; text: modelData; wrapMode: Text.Wrap; font.pointSize: Theme.pt(index >= 3 ? 12.5 : 14); color: index >= 3 ? Theme.muted : Theme.fg }
            }
        }
        footer: DialogButtonBox {
            padding: 22; topPadding: 4; background: null
            AppButton { id: gotIt; text: "Got it"; kind: "primary"; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole; onClicked: about.close() }
        }
    }

    Loader {
        active: win.showFixtures
        sourceComponent: ReviewerFixtures {}
    }
}
