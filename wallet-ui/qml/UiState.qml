pragma Singleton
import QtQuick

// Window-level UI facts the controller does not own.
QtObject {
    property int openDialogs: 0
    // Dialogs between aboutToHide and closed (their exit transition).
    property int closingDialogs: 0
    property Item deferredFocus: null

    // Move focus to a named, actionable item. When a dialog finishes closing, Qt
    // hands focus back to the window's content item, so a target chosen during
    // the exit transition is applied again once the dialog has closed.
    function focus(item) {
        if (!item)
            return
        item.forceActiveFocus()
        if (closingDialogs > 0 || openDialogs > 0)
            deferredFocus = item
    }
    function dialogClosed() {
        closingDialogs = Math.max(0, closingDialogs - 1)
        const target = deferredFocus
        if (closingDialogs === 0)
            deferredFocus = null
        if (target && target.visible && target.enabled) {
            target.forceActiveFocus()
            return true
        }
        return false
    }
}
