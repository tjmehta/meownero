import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// Sidebar plus the current page. Only the current page exists, so inactive
// pages are absent from the accessibility tree rather than merely hidden.
Item {
    id: shell

    function openDetail(rowId, opener) {
        detail.rowId = rowId
        detail.returnFocusTo = opener
        detail.open()
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Sidebar { Layout.fillHeight: true; Layout.preferredWidth: 228 }
        ScrollView {
            id: scroller
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            Item {
                width: scroller.availableWidth
                implicitHeight: pageLoader.implicitHeight + 62
                Loader {
                    id: pageLoader
                    x: 32; y: 22
                    width: Math.min(860 - 64, parent.width - 64)
                    sourceComponent: ({ overview: overview, activity: activity, send: send, receive: receive, node: node, wallet: wallet })[Wallet.route] || null
                    onLoaded: {
                        item.shell = shell
                        scroller.ScrollBar.vertical.position = 0
                    }
                }
            }
        }
    }

    Component { id: overview; OverviewPage {} }
    Component { id: activity; ActivityPage {} }
    Component { id: send; SendPage {} }
    Component { id: receive; ReceivePage {} }
    Component { id: node; NodePage {} }
    Component { id: wallet; WalletPage {} }

    DetailDialog { id: detail }

    Connections {
        target: Wallet
        function onFocusHeading() {
            if (pageLoader.item && pageLoader.item.heading)
                pageLoader.item.heading.forceActiveFocus()
        }
    }
}
