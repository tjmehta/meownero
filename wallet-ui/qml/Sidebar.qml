import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// Wallet sections, the wallet's name and network, and the connection chip.
Rectangle {
    id: root
    color: Theme.side
    Accessible.role: Accessible.Grouping
    Accessible.name: "Wallet sections"
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.border }

    readonly property var sections: [
        ["overview", "Overview", "home"], ["activity", "Activity", "list"], ["send", "Send", "up"],
        ["receive", "Receive", "down"], ["node", "Node", "node"], ["wallet", "Wallet", "gear"]]

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 14; anchors.leftMargin: 10; anchors.rightMargin: 11; anchors.bottomMargin: 12
        spacing: 2

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 8; Layout.topMargin: 4; Layout.bottomMargin: 14
            spacing: 10
            CoinMark { size: 30 }
            ColumnLayout {
                spacing: 0
                AText { text: Wallet.walletName; font.pointSize: Theme.pt(13.5); font.weight: Font.DemiBold; color: Theme.fg; elide: Text.ElideRight; Layout.fillWidth: true }
                AText { text: Wallet.networkName; font.pointSize: Theme.pt(11.5); color: Theme.muted }
            }
        }

        Repeater {
            model: root.sections
            AbstractButton {
                id: nav
                required property var modelData
                required property int index
                readonly property bool current: Wallet.route === modelData[0]
                readonly property int pending: modelData[0] === "activity" ? Wallet.pendingCount : 0
                Layout.fillWidth: true
                implicitHeight: 34
                focusPolicy: Qt.StrongFocus
                Accessible.role: Accessible.Button
                Accessible.name: modelData[1]
                Accessible.description: (current ? "Current page" : "") + (pending > 0 ? (current ? ". " : "") + pending + " pending" : "")
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                onClicked: Wallet.navigate(modelData[0])
                background: Rectangle {
                    radius: 7
                    color: nav.current || nav.hovered ? Theme.surface2 : "transparent"
                    border.width: (nav.activeFocus && nav.focusReason !== Qt.MouseFocusReason) ? 2 : 0
                    border.color: Theme.net
                }
                contentItem: RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10; anchors.rightMargin: 10
                    spacing: 10
                    Icon { name: nav.modelData[2]; size: 16; color: nav.current ? Theme.net : Theme.muted }
                    AText {
                        Layout.fillWidth: true
                        text: nav.modelData[1]
                        font.pointSize: Theme.pt(13.5)
                        font.weight: nav.current ? Font.DemiBold : Font.Normal
                        color: Theme.fg
                        Accessible.ignored: true
                    }
                    AText {
                        visible: nav.pending > 0
                        text: nav.pending + " pending"
                        font.pointSize: Theme.pt(11)
                        font.weight: Font.DemiBold
                        color: Theme.warn
                        Accessible.ignored: true
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        AbstractButton {
            id: chip
            Layout.fillWidth: true
            implicitHeight: chipRow.implicitHeight + 16
            focusPolicy: Qt.StrongFocus
            Accessible.role: Accessible.Button
            Accessible.name: Wallet.node.chipAccessible
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            onClicked: Wallet.navigate("node")
            background: Rectangle {
                radius: 8
                color: chip.hovered ? Theme.surface2 : "transparent"
                border.width: (chip.activeFocus && chip.focusReason !== Qt.MouseFocusReason) ? 2 : 1
                border.color: (chip.activeFocus && chip.focusReason !== Qt.MouseFocusReason) ? Theme.net : Theme.border
            }
            contentItem: RowLayout {
                id: chipRow
                anchors.fill: parent
                anchors.leftMargin: 10; anchors.rightMargin: 10
                spacing: 8
                Spinner { visible: Wallet.node.chipKind === "spin"; size: 12 }
                Rectangle {
                    visible: Wallet.node.chipKind !== "spin"
                    width: 8; height: 8; radius: 4
                    color: Wallet.node.chipKind === "ok" ? Theme.ok : Wallet.node.chipKind === "warn" ? Theme.warn : Theme.danger
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    AText { Layout.fillWidth: true; text: Wallet.node.chipTitle; font.pointSize: Theme.pt(12); font.weight: Font.DemiBold; color: Theme.fg; elide: Text.ElideRight; Accessible.ignored: true }
                    AText { Layout.fillWidth: true; text: Wallet.node.chipSub; font.pointSize: Theme.pt(11.5); color: Theme.muted; elide: Text.ElideRight; Accessible.ignored: true }
                }
            }
        }
    }
}
