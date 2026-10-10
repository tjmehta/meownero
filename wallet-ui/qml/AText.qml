import QtQuick

// Text that assistive technology can read. Plain Text items are not exposed
// to AT-SPI here, so content text uses this; hidden text stays out of the tree.
Text {
    // Controller strings (notes, wallet names, node reasons) are never markup.
    // Opt in to StyledText only for app-authored formatting.
    textFormat: Text.PlainText
    Accessible.role: Accessible.StaticText
    Accessible.name: textFormat === Text.StyledText ? Accessible.stripHtml(text) : text
    Accessible.ignored: !visible || text === ""
}
