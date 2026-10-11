import QtQuick
import QtQuick.Layouts

// One label/value row of a definition list (140 px label column).
RowLayout {
    id: root
    property string label: ""
    property string value: ""
    property color valueColor: Theme.fg
    property bool mono: false
    property string accessibleValue: ""
    default property alias extra: valueBox.data
    Layout.fillWidth: true
    spacing: 16
    Accessible.role: Accessible.StaticText
    Accessible.name: label + ": " + (value !== "" ? value : accessibleValue)
    Accessible.ignored: !visible

    AText {
        Layout.preferredWidth: 140
        Layout.alignment: Qt.AlignTop
        text: root.label
        color: Theme.muted
        font.pointSize: Theme.pt(13.5)
        wrapMode: Text.Wrap
        Accessible.ignored: true
    }
    ColumnLayout {
        id: valueBox
        Layout.fillWidth: true
        spacing: 4
        AText {
            visible: root.value !== ""
            Layout.fillWidth: true
            text: root.value
            color: root.valueColor
            font.pointSize: Theme.pt(root.mono ? 13 : 13.5)
            font.family: root.mono ? Theme.mono : Qt.application.font.family
            font.features: { "tnum": 1 }
            wrapMode: Text.WrapAnywhere
            Accessible.ignored: true
        }
    }
}
