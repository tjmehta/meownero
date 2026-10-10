import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

PageBase {
    id: page
    title: "Overview"
    readonly property var b: Wallet.balance

    headerRight: AppButton {
        text: "Show every digit"
        kind: "quiet"
        checkable: true
        checked: Wallet.exactDigits
        Accessible.checkable: true
        Accessible.checked: Wallet.exactDigits
        onClicked: Wallet.toggleExact()
    }

    ConditionBanners { Layout.bottomMargin: 18 }

    // Spendable balance: priority one, with the network tag beside it.
    Text { text: "Spendable now"; font.pointSize: Theme.pt(12.5); font.weight: Font.Medium; color: Theme.muted; Accessible.ignored: true }
    AbstractButton {
        id: bigAmount
        Layout.topMargin: 4
        Layout.bottomMargin: 6
        Layout.fillWidth: true
        implicitHeight: amt.implicitHeight
        focusPolicy: Qt.StrongFocus
        checkable: true
        checked: Wallet.exactDigits
        Accessible.role: Accessible.Button
        Accessible.name: page.b.accessibleName
        Accessible.checkable: true
        Accessible.checked: Wallet.exactDigits
        onClicked: Wallet.toggleExact() // focus stays on the balance (N5)
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        background: Rectangle { color: "transparent"; radius: 6; border.width: bigAmount.visualFocus ? 2 : 0; border.color: Theme.net; anchors.margins: -4 }
        contentItem: Item {
            implicitHeight: amt.implicitHeight
            AmountLabel { id: amt; view: page.b.spendable; px: 44; bold: true; tag: true; Accessible.ignored: true }
        }
    }
    Flow {
        Layout.fillWidth: true
        spacing: 18
        Text {
            visible: page.b.hasLocked
            textFormat: Text.StyledText
            text: "Unlocking <b>" + page.b.unlocking.text + (page.b.unlocking.more ? "…" : "") + " MEOW</b>" + (page.b.nextUnlock ? " · next in " + page.b.nextUnlock : "")
            font.pointSize: Theme.pt(13); color: Theme.muted
            Accessible.name: "Unlocking " + page.b.unlocking.accessible + (page.b.nextUnlock ? ", next in " + page.b.nextUnlock : "")
        }
        Text {
            textFormat: Text.StyledText
            text: "Total <b>" + page.b.total.text + (page.b.total.more ? "…" : "") + " MEOW</b>"
            font.pointSize: Theme.pt(13); color: Theme.muted
            Accessible.name: "Total " + page.b.total.accessible
        }
        Text { visible: page.b.lastSynced !== ""; text: page.b.lastSynced; font.pointSize: Theme.pt(13); color: Theme.muted }
    }
    Flow {
        Layout.fillWidth: true
        Layout.topMargin: 18
        Layout.bottomMargin: 4
        spacing: 10
        AppButton { text: "Receive"; iconName: "down"; kind: "primary"; large: true; onClicked: Wallet.navigate("receive") }
        AppButton { text: "Send"; iconName: "up"; large: true; enabled: page.b.canSend; onClicked: Wallet.navigate("send") }
        AppButton {
            visible: Wallet.networkKey === "regtest"
            text: "Get test coins"; iconName: "block"; kind: "quiet"
            enabled: Wallet.canTransact
            onClicked: Wallet.mineTestCoins()
        }
    }
    Text {
        visible: page.b.belowFee
        Layout.fillWidth: true; Layout.topMargin: 8
        text: "Your spendable balance is smaller than a network fee, so it can't be sent yet."
        wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
    }
    Text {
        visible: Wallet.networkKey === "regtest" && !Wallet.canTransact
        Layout.fillWidth: true; Layout.topMargin: 8
        text: "Getting test coins needs " + Wallet.node.pausedNeeds + "."
        wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
    }
    Text {
        visible: page.b.hasLocked
        Layout.fillWidth: true; Layout.topMargin: 12
        text: "New coins wait before they can be spent: mined coins for 60 blocks, payments and change for 10."
        wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
    }

    SectionLabel { text: "Recent activity" }
    ActivityList { visible: Wallet.recentActivity.count > 0; model: Wallet.recentActivity; shell: page.shell }
    AppButton { visible: Wallet.recentActivity.count > 0; Layout.topMargin: 8; text: "See all activity"; kind: "quiet"; onClicked: Wallet.navigate("activity") }
    EmptyActivity { visible: Wallet.recentActivity.count === 0 }

    component EmptyActivity: Rectangle {
        Layout.fillWidth: true
        implicitHeight: emptyCol.implicitHeight + 56
        radius: 10
        color: "transparent"
        border.width: 1
        border.color: Theme.borderStrong
        ColumnLayout {
            id: emptyCol
            anchors.centerIn: parent
            width: parent.width - 56
            spacing: 4
            Icon { Layout.alignment: Qt.AlignHCenter; name: "coin"; size: 40; color: Theme.faint }
            Text { Layout.alignment: Qt.AlignHCenter; text: "No payments yet"; font.pointSize: Theme.pt(14); font.weight: Font.DemiBold; color: Theme.fg }
            Text {
                Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
                text: Wallet.networkKey === "regtest" ? "Mine some test coins, or pay this wallet from another test wallet in your kit." : "Share your address to receive test coins."
                font.pointSize: Theme.pt(13.5); color: Theme.muted
            }
            Row {
                Layout.alignment: Qt.AlignHCenter; Layout.topMargin: 12; spacing: 10
                AppButton { text: "Show my address"; onClicked: Wallet.navigate("receive") }
                AppButton { visible: Wallet.networkKey === "regtest"; text: "Get test coins"; kind: "quiet"; enabled: Wallet.canTransact; onClicked: Wallet.mineTestCoins() }
            }
        }
    }
}
