import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// Modal dialog named by its heading and, for consent, described by its
// explanation. Escape closes; focus starts on initialFocus and returns to the
// control that opened it. Navigation or locking closes it.
Dialog {
    id: dlg
    property string description: ""
    property Item returnFocusTo: null
    property Item initialFocus: null
    property bool restoreFocus: true
    property bool wide: false
    property string openedRoute: ""

    parent: Overlay.overlay
    modal: true
    focus: true
    anchors.centerIn: parent
    width: Math.min(wide ? 760 : 520, (parent ? parent.width : 560) - 32)
    height: Math.min(implicitHeight, (parent ? parent.height : 600) - 48)
    padding: 22
    topPadding: 6
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    header: PageHeading {
        text: dlg.title
        level: 2
        leftPadding: 22; rightPadding: 22; topPadding: 22; bottomPadding: 6
        Accessible.focusable: false
    }
    background: Rectangle {
        color: Theme.bg
        radius: 14
        border.width: 1
        border.color: Theme.borderStrong
    }
    Overlay.modal: Rectangle { color: "#6b000000" }

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.sheetMs; easing.type: Easing.OutQuint }
        NumberAnimation { property: "scale"; from: Theme.reducedMotion ? 1 : 0.97; to: 1; duration: Theme.sheetMs; easing.type: Easing.OutQuint }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.reducedMotion ? 0 : 120 }
    }

    onAboutToShow: {
        openedRoute = Wallet.route
        UiState.openDialogs++
    }
    onOpened: (initialFocus ? initialFocus : contentItem).forceActiveFocus()
    onClosed: {
        UiState.openDialogs = Math.max(0, UiState.openDialogs - 1)
        if (restoreFocus && returnFocusTo)
            returnFocusTo.forceActiveFocus()
        restoreFocus = true
    }
    function closeWithoutRestoring() {
        restoreFocus = false
        close()
    }
    Connections {
        target: Wallet
        enabled: dlg.visible
        function onChanged() {
            if (Wallet.route !== dlg.openedRoute)
                dlg.closeWithoutRestoring()
        }
    }
}
