import QtQuick
import QtQuick.Layouts

// A wallet page: heading row plus content, with the 180 ms entry motion
// (none under reduced motion).
ColumnLayout {
    id: page
    property var shell
    property alias heading: headingText
    property alias title: headingText.text
    default property alias content: body.data
    property alias headerRight: right.data
    spacing: 0

    opacity: 0
    transform: Translate { id: shift; y: Theme.reducedMotion ? 0 : 4 }
    Component.onCompleted: { entry.start() }
    ParallelAnimation {
        id: entry
        NumberAnimation { target: page; property: "opacity"; to: 1; duration: Theme.pageMs; easing.type: Easing.OutQuint }
        NumberAnimation { target: shift; property: "y"; to: 0; duration: Theme.pageMs; easing.type: Easing.OutQuint }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.bottomMargin: 18
        spacing: 12
        PageHeading { id: headingText; Layout.fillWidth: true }
        Row { id: right; spacing: 8 }
    }
    ColumnLayout {
        id: body
        Layout.fillWidth: true
        spacing: 0
    }
}
