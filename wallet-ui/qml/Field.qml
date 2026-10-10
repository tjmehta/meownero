import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Labelled text field. Its error (or hint) is its accessible description.
ColumnLayout {
    id: root
    property string label: ""
    property string error: ""
    property string hint: ""
    property alias text: input.text
    property alias input: input
    property bool password: false
    property bool mono: false
    signal edited(string text)
    signal submitted()
    Layout.fillWidth: true
    Layout.bottomMargin: 16
    spacing: 6

    AText {
        id: fieldLabel
        text: root.label
        font.pointSize: Theme.pt(13.5)
        font.weight: Font.DemiBold
        color: Theme.fg
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    TextField {
        id: input
        Layout.fillWidth: true
        echoMode: root.password ? TextInput.Password : TextInput.Normal
        font.pointSize: Theme.pt(root.mono ? 13 : 14)
        font.family: root.mono ? Theme.mono : Qt.application.font.family
        color: Theme.fg
        placeholderTextColor: Theme.faint
        selectByMouse: true
        inputMethodHints: root.password ? (Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhHiddenText) : Qt.ImhNone
        padding: 9
        leftPadding: 11
        // Qt drops an explicit name on password fields, so the visible label is also related.
        Accessible.name: root.label
        Accessible.labelledBy: fieldLabel
        Accessible.description: root.error !== "" ? root.error : root.hint
        onTextEdited: root.edited(text)
        onAccepted: root.submitted()
        background: Rectangle {
            radius: Theme.controlRadius
            color: Theme.surface
            border.width: input.activeFocus ? 2 : 1
            border.color: input.activeFocus ? Theme.net : root.error !== "" ? Theme.danger : Theme.borderStrong
        }
    }
    FieldError { error: root.error; hint: root.hint; Layout.topMargin: 0 }
}
