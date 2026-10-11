import QtQuick
import QtQuick.Layouts
import Meownero.Core

// Reorg and node/engine banners shown on money screens. Every paused reason
// names the part at fault: node or wallet engine.
ColumnLayout {
    Layout.fillWidth: true
    spacing: 18
    visible: Wallet.reorg.visible || Wallet.condition.visible

    Banner {
        visible: Wallet.reorg.visible
        tone: "warn"
        iconName: "refresh"
        title: Wallet.reorg.title || ""
        body: Wallet.reorg.body || ""
        AppButton { text: "View activity"; onClicked: Wallet.navigate("activity") }
        AppButton { text: "Dismiss"; kind: "quiet"; onClicked: Wallet.dismissReorg() }
    }
    Banner {
        visible: Wallet.condition.visible
        tone: Wallet.condition.tone || "info"
        iconName: tone === "net" ? "clock" : tone === "bad" ? "alert" : "info"
        title: Wallet.condition.title || ""
        body: Wallet.condition.body || ""
        progress: Wallet.condition.progress !== undefined ? Wallet.condition.progress : -1
        AppButton {
            visible: !!Wallet.condition.action
            text: Wallet.condition.actionLabel || ""
            onClicked: Wallet.condition.action === "retry" ? Wallet.retryNode() : Wallet.navigate("node")
        }
        AppButton {
            visible: !!Wallet.condition.secondary
            text: Wallet.condition.secondaryLabel || ""
            kind: "quiet"
            onClicked: Wallet.navigate("node")
        }
    }
}
