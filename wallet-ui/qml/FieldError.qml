import QtQuick
import QtQuick.Layouts

// Error or hint text under a field. The field itself carries it as its
// accessible description, so this text is linked rather than separate.
RowLayout {
    id: root
    property string error: ""
    property string hint: ""
    Layout.fillWidth: true
    Layout.topMargin: 6
    spacing: 6
    visible: error !== "" || hint !== ""
    Icon { visible: root.error !== ""; name: "alert"; size: 14; color: Theme.danger; Layout.alignment: Qt.AlignTop; Layout.topMargin: 2 }
    Text {
        Layout.fillWidth: true
        text: root.error !== "" ? root.error : root.hint
        wrapMode: Text.Wrap
        font.pointSize: Theme.pt(12.5)
        color: root.error !== "" ? Theme.danger : Theme.muted
        Accessible.ignored: true
    }
}
