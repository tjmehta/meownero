import QtQuick
import Meownero.Core

// An address or ID in monospace, grouped by four for comparison; the first and
// last two groups use the network colour. Assistive technology reads the exact
// string. When copyable, the standard copy shortcut copies it while focused.
FocusScope {
    id: root
    property string text: ""
    property bool grouped: true
    property var onCopy: null
    property real px: 13
    implicitHeight: flow.implicitHeight
    implicitWidth: 300
    activeFocusOnTab: onCopy !== null
    Accessible.role: Accessible.StaticText
    Accessible.name: text
    Accessible.ignored: !visible
    Accessible.focusable: activeFocusOnTab
    Accessible.description: onCopy !== null ? "Press the copy shortcut to copy" : ""

    Keys.onPressed: (e) => {
        if (root.onCopy !== null && e.matches(StandardKey.Copy)) {
            root.onCopy()
            e.accepted = true
        }
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        radius: 6
        color: "transparent"
        border.width: root.activeFocus ? 2 : 0
        border.color: Theme.net
    }
    Flow {
        id: flow
        width: root.width
        spacing: root.grouped ? root.px * 0.45 : 0
        Repeater {
            model: root.grouped ? (root.text.match(/.{1,4}/g) || []) : [root.text]
            AText {
                required property string modelData
                required property int index
                readonly property int groups: Math.ceil(root.text.length / 4)
                text: modelData
                width: root.grouped ? implicitWidth : flow.width
                wrapMode: root.grouped ? Text.NoWrap : Text.WrapAnywhere
                font.family: Theme.mono
                font.pointSize: Theme.pt(root.px)
                font.letterSpacing: 0.3
                font.weight: root.grouped && (index < 2 || index >= groups - 2) ? Font.DemiBold : Font.Normal
                color: root.grouped && (index < 2 || index >= groups - 2) ? Theme.net : Theme.fg
                lineHeight: 1.35
                Accessible.ignored: true
            }
        }
    }
}
