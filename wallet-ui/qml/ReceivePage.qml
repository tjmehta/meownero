import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

PageBase {
    id: page
    title: "Receive"
    readonly property bool regtest: Wallet.networkKey === "regtest"

    ConditionBanners { Layout.bottomMargin: 18 }
    Banner {
        visible: page.regtest
        Layout.bottomMargin: 18
        tone: "warn"
        title: "Test address only. It uses Monero's address format. Do not send real Monero here."
        body: "On the local regtest, only other test wallets in your Meownero test kit can pay this address."
    }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: card.implicitHeight + 36
        radius: Theme.cardRadius
        color: Theme.surface
        border.width: 1; border.color: Theme.border
        ColumnLayout {
            id: card
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            spacing: 6
            AText { text: "Your address · " + Wallet.networkName + " · test coins only"; font.pointSize: Theme.pt(12.5); color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
            AddressText { id: addr; Layout.fillWidth: true; text: Wallet.receiveAddress; onCopy: () => Wallet.copyAddress() }
            Flow {
                Layout.fillWidth: true; Layout.topMargin: 8
                spacing: 10
                AppButton { text: "Copy address"; iconName: "copy"; kind: "primary"; onClicked: Wallet.copyAddress() }
                AppButton {
                    text: "New address for each payer"
                    enabled: false
                    accessibleDescription: "Not in this test build"
                    ToolTip.visible: hovered
                    ToolTip.text: "Not in this test build"
                }
            }
        }
    }
    AText {
        Layout.fillWidth: true; Layout.topMargin: 12
        text: "When comparing, check the coloured groups at the start and end."
        wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
    }
    SectionLabel { text: "Get test coins" }
    Rectangle {
        visible: page.regtest
        Layout.fillWidth: true
        implicitHeight: mine.implicitHeight + 36
        radius: Theme.cardRadius
        color: Theme.surface
        border.width: 1; border.color: Theme.border
        ColumnLayout {
            id: mine
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            spacing: 10
            AText { Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: Theme.pt(14); color: Theme.fg; text: "Your local regtest only makes blocks when asked. Mining 10 blocks pays their test rewards to this wallet." }
            AText { Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted; text: "Mined coins can be spent after 60 more blocks. This chain uses upstream test rewards, not Meownero's planned 9 MEOW per 90 seconds." }
            AText { visible: !Wallet.canTransact; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted; text: "Needs " + Wallet.node.pausedNeeds + "." }
            AppButton { text: "Mine 10 test blocks"; iconName: "block"; enabled: Wallet.canTransact; onClicked: Wallet.mineTestCoins() }
        }
    }
    AText {
        visible: !page.regtest
        Layout.fillWidth: true
        text: "On the testnet, test coins come from mining. A faucet is not planned yet."
        wrapMode: Text.Wrap; font.pointSize: Theme.pt(14); color: Theme.muted
    }
}
