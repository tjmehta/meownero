import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// Reviewer fixtures: a separate window that stages simulated backend states.
// It is not part of the app's interaction model and never ships enabled.
Window {
    id: fx
    visible: true
    width: 380
    height: 760
    x: Screen.desktopAvailableWidth - width - 8
    y: 8
    title: "Reviewer fixtures — simulated backend (not part of the app)"
    color: Theme.dark ? "#2a2410" : "#fff8e1"
    readonly property var f: Wallet.fixtures

    component Group: ColumnLayout {
        property string label: ""
        default property alias items: flow.data
        Layout.fillWidth: true
        Layout.bottomMargin: 12
        spacing: 4
        Text { text: parent.label; font.pointSize: 8.5; font.weight: Font.DemiBold; font.capitalization: Font.AllUppercase; color: Theme.muted }
        Flow { id: flow; Layout.fillWidth: true; spacing: 6 }
    }
    component Opt: Button {
        property bool on: false
        font.pointSize: 9
        padding: 5
        checkable: true
        checked: on
        Accessible.checkable: true
        Accessible.checked: on
    }

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        ColumnLayout {
            width: fx.width - 28
            x: 14; y: 12
            spacing: 0
            Text { Layout.fillWidth: true; Layout.bottomMargin: 4; text: "Reviewer fixtures"; font.pointSize: 13; font.weight: Font.Bold; color: Theme.fg }
            Text { Layout.fillWidth: true; Layout.bottomMargin: 12; wrapMode: Text.Wrap; font.pointSize: 9; color: Theme.muted
                   text: "Stages simulated states for review and QA. No wallet, node or network exists behind any of these." }

            Group { label: "Network the node reports"
                Opt { text: "Local regtest"; on: fx.f.network === "regtest"; onClicked: Wallet.fixtureSetNetwork("regtest") }
                Opt { text: "Testnet (design preview)"; on: fx.f.network === "testnet"; onClicked: Wallet.fixtureSetNetwork("testnet") }
            }
            Group { label: "Node and wallet engine"
                Repeater {
                    model: [["synced", "Synced"], ["remote", "Synced via someone else's node"], ["connecting", "Connecting"], ["node-sync", "Node catching up"],
                            ["scanning", "Wallet scanning"], ["offline", "Node unreachable"], ["wrong-net", "Wrong network"], ["node-old", "Incompatible node"],
                            ["engine-down", "Engine stopped"], ["auth-failed", "Engine refused credentials"]]
                    Opt { required property var modelData; text: modelData[1]; on: fx.f.node === modelData[0]
                          enabled: modelData[0] !== "remote" || fx.f.network === "testnet"; onClicked: Wallet.fixtureSetNodeState(modelData[0]) }
                }
            }
            Group { label: "Wallet contents (reloads history)"
                Opt { text: "Normal"; onClicked: Wallet.fixtureSetStory("normal") }
                Opt { text: "Empty"; onClicked: Wallet.fixtureSetStory("empty") }
                Opt { text: "1 atomic unit"; onClicked: Wallet.fixtureSetStory("dust") }
                Opt { text: "Large balance"; onClicked: Wallet.fixtureSetStory("large") }
            }
            Group { label: "Chain"
                Opt { text: "Add 1 block"; checkable: false; onClicked: Wallet.fixtureAddBlocks(1) }
                Opt { text: "Add 10 blocks"; checkable: false; onClicked: Wallet.fixtureAddBlocks(10) }
                Opt { text: "Reorganize"; checkable: false; onClicked: Wallet.fixtureReorg() }
            }
            Group { label: "Next send result"
                Opt { text: "Accepted"; on: fx.f.sendOutcome === "accepted"; onClicked: Wallet.fixtureSetSendOutcome("accepted") }
                Opt { text: "Node refuses"; on: fx.f.sendOutcome === "refused"; onClicked: Wallet.fixtureSetSendOutcome("refused") }
                Opt { text: "Connection drops"; on: fx.f.sendOutcome === "drops"; onClicked: Wallet.fixtureSetSendOutcome("drops") }
            }
            Group { label: "Unknown payment resolves as"
                Opt { text: "Reached the node"; on: fx.f.unknownResolves === "reached"; onClicked: Wallet.fixtureSetUnknownResolves("reached") }
                Opt { text: "Not sent"; on: fx.f.unknownResolves === "notsent"; onClicked: Wallet.fixtureSetUnknownResolves("notsent") }
            }
            Group { label: "Fill send form"
                Repeater {
                    model: [["valid", "Valid kit wallet"], ["typo", "Typo"], ["wrongnet", "Other network"], ["mainnet", "Mainnet"], ["short", "Incomplete"], ["13dp", "13 decimals"], ["locked", "Above spendable"]]
                    Opt { required property var modelData; text: modelData[1]; checkable: false; onClicked: Wallet.fixtureFillSend(modelData[0]) }
                }
            }
            Group { label: "Fill restore words"
                Repeater {
                    model: [["sample", "Sample words"], ["badword", "Misspelled"], ["checksum", "Don't add up"], ["count", "Missing words"]]
                    Opt { required property var modelData; text: modelData[1]; checkable: false; onClicked: Wallet.fixtureFillRestore(modelData[0]) }
                }
            }
            Group { label: "Evidence counters"
                Text { text: "Session " + fx.f.epoch + " · stale replies dropped " + fx.f.staleDropped + " · stale actions refused " + fx.f.staleRefused; font.pointSize: 9; color: Theme.fg; wrapMode: Text.Wrap; width: parent.width }
            }
            Group { label: "Diagnostics (allowlisted fields only)"
                Opt { text: "Refresh"; checkable: false; onClicked: diag.text = Wallet.diagnostics() }
            }
            TextArea { id: diag; Layout.fillWidth: true; readOnly: true; wrapMode: TextEdit.Wrap; font.family: Theme.mono; font.pointSize: 8.5; text: Wallet.diagnostics() }
        }
    }
}
