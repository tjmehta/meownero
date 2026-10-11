import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// Node status and choice. A pick changes nothing until an explicit Connect;
// someone else's node needs the confirmation dialog with the approved
// exposure sentence, and is never offered on the local regtest.
PageBase {
    id: page
    title: "Node"
    readonly property var n: Wallet.node
    readonly property bool remote: n.remote
    readonly property bool far: (Wallet.nodePick !== "" ? Wallet.nodePick : (remote ? "remote" : "local")) === "remote"

    function focusChecked() { UiState.focus(page.far ? remoteChoice : localChoice) }

    Connections {
        target: Wallet
        function onConsentRequested() { consent.returnFocusTo = connectButton; consent.open() }
        function onConsentClosed() { if (consent.visible) consent.closeWithoutRestoring() }
    }

    ConditionBanners { Layout.bottomMargin: 18 }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: dl.implicitHeight + 36
        radius: Theme.cardRadius; color: Theme.surface; border.width: 1; border.color: Theme.border
        ColumnLayout {
            id: dl
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            spacing: 10
            DefRow { label: "Status"; value: page.n.status || "" }
            DefRow { label: "Node"; value: (page.n.address || "") + "  " + (page.n.addressNote || "") }
            DefRow { label: "Network"; value: page.n.networkText || ""; valueColor: page.n.networkWrong ? Theme.danger : Theme.fg }
            DefRow { label: "Node height"; value: page.n.height || "" }
            DefRow { label: "Wallet scanned to"; value: page.n.scanned || "" }
            DefRow { label: "Peers"; value: (page.n.peers || "") + (page.n.peersNote ? "  " + page.n.peersNote : "") }
            DefRow { label: "Trust"; value: page.n.trust || "" }
        }
    }

    SectionLabel { text: "Connect through" }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        Accessible.role: Accessible.Grouping
        Accessible.name: "Node choice"
        ChoiceItem {
            id: localChoice
            radio: true
            checked: !page.far
            title: "My own node on this computer"
            subtitle: page.n.ownNodeNote || ""
            onClicked: Wallet.pickNode("local")
            Keys.onPressed: (e) => page.arrow(e, remoteChoice, "remote")
        }
        ChoiceItem {
            id: remoteChoice
            radio: true
            checked: page.far
            enabled: page.n.remoteAllowed
            title: "Someone else's node"
            subtitle: page.n.remoteAllowed ? "Faster to start, but it can observe your activity" : "Not available on the local regtest"
            onClicked: Wallet.pickNode("remote")
            Keys.onPressed: (e) => page.arrow(e, localChoice, "local")
        }
    }
    function arrow(e, other, value) {
        if ([Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right].indexOf(e.key) < 0)
            return
        e.accepted = true
        if (!other.enabled)
            return
        Wallet.pickNode(value)
        other.forceActiveFocus()
    }

    // While connected to someone else's node, the explanation stays above any Connect control.
    Banner {
        visible: page.remote
        Layout.bottomMargin: 10
        tone: "warn"
        title: "What someone else's node can observe"
        body: Wallet.remoteExposure
    }
    Flow {
        visible: page.far !== page.remote
        Layout.fillWidth: true
        Layout.bottomMargin: 10
        spacing: 10
        AppButton {
            id: connectButton
            kind: "primary"
            text: page.far ? "Connect to someone else's node…" : "Connect to my own node"
            onClicked: {
                const wasFar = page.far
                Wallet.applyNodePick()
                if (!wasFar) page.focusChecked()
            }
        }
        AppButton { text: "Keep current node"; kind: "quiet"; onClicked: { Wallet.keepCurrentNode(); page.focusChecked() } }
        AText { height: connectButton.height; verticalAlignment: Text.AlignVCenter; text: "Nothing changes until you connect."; font.pointSize: Theme.pt(12.5); color: Theme.muted }
    }
    ChoiceItem {
        enabled: false
        iconName: "lock"
        title: "Through Tor or I2P"
        subtitle: "Not available in this test build"
    }

    AppDialog {
        id: consent
        title: "Connect to someone else's node?"
        description: Wallet.remoteExposure
        initialFocus: keepButton
        // Keep, Escape and clicking outside change nothing; Escape returns focus to Connect.
        onClosed: if (Wallet.consentOpen) Wallet.dismissConsent()
        contentItem: ColumnLayout {
            spacing: 12
            AText {
                objectName: "consentExplanation"
                Layout.fillWidth: true
                text: Wallet.remoteExposure
                wrapMode: Text.Wrap
                font.pointSize: Theme.pt(14)
                color: Theme.fg
            }
            DefRow { label: "Node"; value: "node.example-test.org:29081" }
            DefRow { label: "Trust"; value: "Untrusted, by your choice" }
        }
        footer: DialogButtonBox {
            padding: 22; topPadding: 8; spacing: 10
            background: null
            AppButton {
                id: keepButton
                text: "Keep current node"
                // Initial focus: the reader hears the exposure explanation with the choice that changes nothing.
                accessibleDescription: Wallet.remoteExposure
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
                onClicked: {
                    consent.closeWithoutRestoring()
                    Wallet.keepCurrentNode()
                    page.focusChecked()
                }
            }
            AppButton {
                text: "Connect to someone else's node"
                kind: "primary"
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                onClicked: {
                    const token = Wallet.consentToken
                    consent.closeWithoutRestoring()
                    Wallet.confirmRemoteNode(token)
                    // Connected: the chosen radio. Refused as stale: the pick is cleared, so the checked radio too.
                    page.focusChecked()
                }
            }
        }
    }
}
