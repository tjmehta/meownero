import QtQuick
import QtQuick.Controls.Basic

// Standard Button with the accepted styling: 8 px radius, network accent for
// primary, no pill shapes. Toggles keep a constant label and report "pressed".
Button {
    id: control
    property string kind: "default" // default | primary | quiet
    property bool large: false
    property string iconName: ""
    property string accessibleDescription: ""

    font.pointSize: Theme.pt(large ? 14 : 13.5)
    font.weight: Font.Medium
    leftPadding: kind === "quiet" ? 6 : (large ? 18 : 14)
    rightPadding: leftPadding
    topPadding: large ? 11 : 8
    bottomPadding: topPadding
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : 0.45

    Accessible.name: text
    Accessible.description: accessibleDescription
    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onEnterPressed: if (enabled) clicked()

    contentItem: Row {
        spacing: 8
        Icon {
            visible: control.iconName !== ""
            name: control.iconName
            size: 16
            color: label.color
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            text: control.text
            font: control.font
            color: control.kind === "primary" ? Theme.netInk : control.kind === "quiet" ? Theme.net : Theme.fg
            anchors.verticalCenter: parent.verticalCenter
            Accessible.ignored: true
        }
    }

    background: Rectangle {
        radius: Theme.controlRadius
        color: control.kind === "primary" ? (control.hovered && control.enabled ? Qt.tint(Theme.net, Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.12)) : Theme.net)
             : control.kind === "quiet" ? ((control.checked || (control.hovered && control.enabled)) ? Theme.netSoft : "transparent")
             : (control.hovered && control.enabled ? Theme.surface2 : Theme.surface)
        border.width: control.visualFocus ? 2 : (control.kind === "default" ? 1 : 0)
        border.color: control.visualFocus ? Theme.net : Theme.borderStrong
        scale: control.pressed && !Theme.reducedMotion ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: Theme.reducedMotion ? 0 : 140; easing.type: Easing.OutQuint } }
    }
}
