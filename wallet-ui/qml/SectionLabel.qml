import QtQuick
import QtQuick.Layouts

Text {
    Layout.fillWidth: true
    Layout.topMargin: 26
    Layout.bottomMargin: 8
    font.pointSize: Theme.pt(13)
    font.weight: Font.DemiBold
    color: Theme.muted
    wrapMode: Text.Wrap
    Accessible.role: Accessible.Heading
    Accessible.name: text
}
