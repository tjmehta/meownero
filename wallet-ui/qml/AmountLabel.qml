import QtQuick

// An exact amount already formatted by the controller. Hidden digits show a
// muted "…"; assistive technology always gets the lossless value.
Row {
    id: root
    property var view: ({})        // {text, more, accessible}
    property real px: 14
    property bool bold: false
    property bool unit: true
    property bool tag: false
    property color color: Theme.fg
    readonly property bool big: px > 24
    spacing: 0
    Accessible.role: Accessible.StaticText
    Accessible.name: (view.accessible || "") + (tag ? ", test coins" : "")

    AText {
        id: digits
        text: root.view.text || ""
        font.pointSize: Theme.pt(root.px)
        font.weight: root.bold ? Font.DemiBold : Font.Normal
        font.letterSpacing: root.big ? -0.8 : 0
        font.features: { "tnum": 1 }
        color: root.color
        Accessible.ignored: true
    }
    AText {
        visible: !!root.view.more
        anchors.baseline: digits.baseline
        text: "…"
        font.pointSize: Theme.pt(root.px)
        font.weight: Font.Normal
        color: Theme.muted
        Accessible.ignored: true
    }
    AText {
        visible: root.unit
        anchors.baseline: digits.baseline
        text: root.big ? "  MEOW" : " MEOW"
        font.pointSize: Theme.pt(root.px * (root.big ? 0.42 : 0.86))
        font.weight: Font.DemiBold
        color: Theme.muted
        Accessible.ignored: true
    }
    Item { width: root.tag ? 8 : 0; height: 1 }
    NetTag {
        visible: root.tag
        fontPx: root.big ? 11 : 10.5
        y: root.big ? digits.height * 0.22 : (digits.height - height) / 2
    }
}
