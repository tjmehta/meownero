import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// 25 recovery-word cells sized for "verification". Veiled words never reach
// QML: the controller sends bullets until they are revealed. No copy control.
ColumnLayout {
    id: root
    property bool veiled: true
    property bool showReveal: veiled
    signal revealRequested()
    spacing: 6

    Item {
        Layout.fillWidth: true
        implicitHeight: grid.implicitHeight
        GridLayout {
            id: grid
            width: parent.width
            columns: Math.max(2, Math.floor((width + 8) / (138 + 8)))
            columnSpacing: 8; rowSpacing: 8
            Accessible.role: Accessible.List
            Accessible.name: root.veiled ? "Recovery words, hidden" : "Recovery words"
            Repeater {
                model: Wallet.displayedWords
                Rectangle {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.minimumWidth: 138
                    implicitHeight: cell.implicitHeight + 12
                    radius: 7
                    color: Theme.surface
                    border.width: 1; border.color: Theme.border
                    Accessible.role: Accessible.ListItem
                    Accessible.name: root.veiled ? "Word " + (index + 1) + " hidden" : "Word " + (index + 1) + ": " + modelData
                    RowLayout {
                        id: cell
                        anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8
                        spacing: 6
                        AText { text: index + 1; font.family: Theme.mono; font.pointSize: Theme.pt(11); color: Theme.faint; Layout.minimumWidth: 18; Accessible.ignored: true }
                        AText { text: modelData; font.family: Theme.mono; font.pointSize: Theme.pt(12.5); color: Theme.fg; Layout.fillWidth: true; Accessible.ignored: true }
                    }
                }
            }
        }
        AText {
            anchors.centerIn: parent
            text: "SAMPLE"
            rotation: -6
            font.family: Theme.mono; font.pointSize: Theme.pt(40); font.weight: Font.ExtraBold; font.letterSpacing: 12
            color: Theme.danger; opacity: 0.28
            Accessible.ignored: true
        }
        AppButton {
            visible: root.showReveal
            anchors.centerIn: parent
            kind: "primary"
            iconName: "eye"
            text: "Show words"
            onClicked: root.revealRequested()
        }
    }
    AText {
        Layout.fillWidth: true
        text: "Simulated: sample words that can't form a valid recovery phrase."
        wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
    }
}
