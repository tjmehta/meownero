import QtQuick

// Text that assistive technology can read. Plain Text items are not exposed
// to AT-SPI here, so content text uses this; hidden text stays out of the tree.
Text {
    Accessible.role: Accessible.StaticText
    Accessible.name: textFormat === Text.StyledText ? Accessible.stripHtml(text) : text
    Accessible.ignored: !visible || text === ""
}
