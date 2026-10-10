import QtQuick

// "Test coins" tag on every money figure that matters, so a cropped screenshot still says test (R1).
Rectangle {
    property real fontPx: 10.5
    implicitWidth: tag.implicitWidth + 10
    implicitHeight: tag.implicitHeight + 6
    radius: 4
    color: "transparent"
    border.width: 1
    border.color: Theme.net
    Accessible.ignored: true
    AText {
        id: tag
        anchors.centerIn: parent
        text: "TEST COINS"
        font.pointSize: Theme.pt(parent.fontPx)
        font.weight: Font.DemiBold
        font.letterSpacing: 0.6
        color: Theme.net
    }
}
