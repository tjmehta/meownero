import QtQuick

// Page heading. Navigation moves focus here so readers start at the new page.
AText {
    id: root
    property int level: 1
    font.pointSize: Theme.pt(level === 1 ? 20 : 18)
    font.weight: Font.DemiBold
    font.letterSpacing: -0.2
    color: Theme.fg
    wrapMode: Text.Wrap
    Accessible.role: Accessible.Heading
    Accessible.name: text
    Accessible.focusable: true
    // In the Tab chain only while focused, so Tab continues into the page, not the window start.
    activeFocusOnTab: activeFocus
}
