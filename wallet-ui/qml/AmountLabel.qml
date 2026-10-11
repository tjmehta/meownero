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
    // Inside a definition row that already names the value, stay out of the tree.
    property bool presentational: false
    // When set, the digits wrap anywhere to stay within this width (minimum window).
    property real maxWidth: 0
    readonly property bool big: px > 24
    spacing: 0
    Accessible.role: Accessible.StaticText
    Accessible.name: (view.accessible || "") + (tag ? ", test coins" : "")
    Accessible.ignored: !visible || presentational

    AText {
        id: digits
        readonly property real room: root.maxWidth - (moreText.visible ? moreText.implicitWidth : 0) - (unitText.visible ? unitText.implicitWidth : 0)
        width: root.maxWidth > 0 ? Math.max(1, Math.min(implicitWidth, room)) : implicitWidth
        wrapMode: root.maxWidth > 0 ? Text.WrapAnywhere : Text.NoWrap
        text: root.view.text || ""
        font.pointSize: Theme.pt(root.px)
        font.weight: root.bold ? Font.DemiBold : Font.Normal
        font.letterSpacing: root.big ? -0.8 : 0
        font.features: { "tnum": 1 }
        color: root.color
        Accessible.ignored: true
    }
    AText {
        id: moreText
        visible: !!root.view.more
        anchors.baseline: digits.baseline
        text: "…"
        font.pointSize: Theme.pt(root.px)
        font.weight: Font.Normal
        color: Theme.muted
        Accessible.ignored: true
    }
    AText {
        id: unitText
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
