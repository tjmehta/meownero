import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// A large choice row. As a radio it is one Tab stop in its group; the group
// moves the choice with the arrow keys (D14). Picking never applies anything.
AbstractButton {
    id: control
    property string title: ""
    property string subtitle: ""
    property string iconName: "node"
    property bool radio: false
    property bool selectedLook: radio && checked
    Layout.fillWidth: true
    Layout.bottomMargin: 10
    checkable: radio
    focusPolicy: radio ? (checked ? Qt.StrongFocus : Qt.NoFocus) : Qt.StrongFocus
    // Inert behind a modal is not "unavailable": keep the normal look under the scrim.
    property bool inBackground: false
    Component.onCompleted: {
        for (let p = parent; p; p = p.parent)
            if (p.objectName === "appContent") { inBackground = true; break }
    }
    opacity: enabled || (inBackground && UiState.openDialogs > 0) ? 1 : 0.55
    padding: 14
    implicitHeight: row.implicitHeight + 28
    Accessible.role: radio ? Accessible.RadioButton : Accessible.Button
    // Any keyboard or programmatic focus (dialog initial focus, focus return) shows the ring.
    readonly property bool focusRing: activeFocus && focusReason !== Qt.MouseFocusReason
    Accessible.name: title
    Accessible.ignored: !visible
    Accessible.description: subtitle
    Accessible.checkable: radio
    Accessible.checked: radio && checked
    Keys.onReturnPressed: if (!radio && enabled) clicked()
    Keys.onEnterPressed: if (!radio && enabled) clicked()

    contentItem: RowLayout {
        id: row
        spacing: 12
        Rectangle {
            Layout.preferredWidth: 36; Layout.preferredHeight: 36
            radius: 8
            color: Theme.netSoft
            Icon { anchors.centerIn: parent; name: control.iconName; size: 16; color: Theme.net }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            AText { Layout.fillWidth: true; text: control.title; font.pointSize: Theme.pt(14); font.weight: Font.DemiBold; color: Theme.fg; wrapMode: Text.Wrap; Accessible.ignored: true }
            AText { Layout.fillWidth: true; visible: text !== ""; text: control.subtitle; font.pointSize: Theme.pt(12.5); color: Theme.muted; wrapMode: Text.Wrap; Accessible.ignored: true }
        }
        Icon { visible: control.selectedLook; name: "check"; size: 18; color: Theme.net }
    }
    background: Rectangle {
        radius: Theme.cardRadius
        color: control.hovered && control.enabled ? Theme.surface2 : Theme.surface
        border.width: control.focusRing ? 2 : (control.selectedLook ? 2 : 1)
        border.color: control.focusRing || control.selectedLook ? Theme.net : Theme.borderStrong
    }
}
