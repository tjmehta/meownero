import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// Payment rows. Each row opens its details; amounts are exact or compact by the controller's rule.
Rectangle {
    id: root
    property var model
    property var shell
    Layout.fillWidth: true
    implicitHeight: col.implicitHeight + 2
    radius: 10
    color: Theme.surface
    border.width: 1
    border.color: Theme.border
    Accessible.role: Accessible.List
    Accessible.name: "Payments"
    Accessible.ignored: !visible

    Column {
        id: col
        x: 1; y: 1
        width: parent.width - 2
        Repeater {
            model: root.model
            AbstractButton {
                id: row
                required property string rowId
                required property string title
                required property string subtitle
                required property string amountText
                required property bool moreDigits
                required property string amountAccessible
                required property string statusText
                required property string statusKind
                required property string iconKey
                required property int index
                width: col.width
                implicitHeight: 58
                focusPolicy: Qt.StrongFocus
                Accessible.role: Accessible.Button
                Accessible.name: title + ", " + subtitle + ", " + amountAccessible + ", " + statusText
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                onClicked: root.shell.openDetail(rowId, row)

                background: Rectangle {
                    color: row.hovered ? Theme.surface2 : "transparent"
                    radius: row.index === 0 || row.index === root.model.count - 1 ? 9 : 0
                    border.width: row.visualFocus ? 2 : 0
                    border.color: Theme.net
                    Rectangle { visible: row.index < root.model.count - 1; anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
                }
                contentItem: RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14; anchors.rightMargin: 14
                    spacing: 12
                    Rectangle {
                        Layout.preferredWidth: 32; Layout.preferredHeight: 32; radius: 8; color: Theme.surface2
                        Icon { anchors.centerIn: parent; name: row.iconKey; size: 16; color: Theme.muted }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        AText { Layout.fillWidth: true; text: row.title; elide: Text.ElideRight; font.pointSize: Theme.pt(14); font.weight: Font.Medium; color: Theme.fg; Accessible.ignored: true }
                        AText { Layout.fillWidth: true; text: row.subtitle; elide: Text.ElideRight; font.pointSize: Theme.pt(12.5); color: Theme.muted; Accessible.ignored: true }
                    }
                    ColumnLayout {
                        spacing: 1
                        AmountLabel {
                            Layout.alignment: Qt.AlignRight
                            view: ({ text: row.amountText, more: row.moreDigits, accessible: row.amountAccessible })
                            unit: false
                            bold: true
                            Accessible.ignored: true
                        }
                        RowLayout {
                            Layout.alignment: Qt.AlignRight
                            spacing: 5
                            Icon {
                                visible: row.statusKind === "failed" || row.statusKind === "unknown" || row.statusText === "Waiting to confirm"
                                name: row.statusKind === "failed" ? "x" : row.statusKind === "unknown" ? "alert" : "clock"
                                size: 13
                                color: statusLabel.color
                            }
                            AText {
                                id: statusLabel
                                text: row.statusText
                                font.pointSize: Theme.pt(12)
                                font.weight: row.statusKind === "done" ? Font.Medium : Font.DemiBold
                                color: row.statusKind === "failed" ? Theme.danger : row.statusKind === "done" ? Theme.muted : Theme.warn
                                Accessible.ignored: true
                            }
                        }
                    }
                }
            }
        }
    }
}
