import QtQuick
import QtQuick.Layouts

// Condition banner: icon, bold title, body and optional actions (children).
Rectangle {
    id: root
    property string tone: "info" // info | warn | bad | net
    property string title: ""
    property string body: ""
    property string iconName: tone === "warn" || tone === "bad" ? "alert" : tone === "net" ? "clock" : "info"
    property int progress: -1
    default property alias actions: actionRow.data

    Layout.fillWidth: true
    implicitHeight: content.implicitHeight + 24
    radius: 10
    color: tone === "warn" ? Theme.warnSoft : tone === "bad" ? Theme.dangerSoft : tone === "net" ? Theme.netSoft : Theme.surface2
    border.width: tone === "info" ? 1 : 0
    border.color: Theme.border
    Accessible.role: Accessible.Grouping
    Accessible.name: title

    RowLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12; leftMargin: 14; rightMargin: 14 }
        spacing: 12
        Icon {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 1
            name: root.iconName
            size: 18
            color: root.tone === "warn" ? Theme.warn : root.tone === "bad" ? Theme.danger : root.tone === "net" ? Theme.net : Theme.muted
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text {
                Layout.fillWidth: true
                text: root.title
                wrapMode: Text.Wrap
                font.pointSize: Theme.pt(14)
                font.weight: Font.DemiBold
                color: Theme.fg
            }
            Text {
                Layout.fillWidth: true
                visible: text !== ""
                text: root.body
                wrapMode: Text.Wrap
                font.pointSize: Theme.pt(14)
                color: Theme.fg
            }
            Rectangle {
                visible: root.progress >= 0
                Layout.fillWidth: true
                Layout.topMargin: 8
                height: 4
                radius: 2
                color: Theme.borderStrong
                Accessible.role: Accessible.ProgressBar
                Accessible.name: root.progress + "%"
                Rectangle { width: parent.width * Math.max(0, root.progress) / 100; height: parent.height; radius: 2; color: Theme.net }
            }
            Flow {
                id: actionRow
                Layout.fillWidth: true
                Layout.topMargin: children.length ? 8 : 0
                spacing: 10
            }
        }
    }
}
