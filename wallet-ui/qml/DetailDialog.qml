import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// Payment details, including "Submission status unknown" and Check with node.
AppDialog {
    id: dlg
    property string rowId: ""
    readonly property var d: { Wallet.balance; Wallet.tip; return rowId ? Wallet.detail(rowId) : ({}) }
    title: d.title || ""
    initialFocus: doneButton

    Connections {
        target: Wallet
        function onReconciled(id) {
            if (dlg.visible && id === dlg.rowId) {
                dlg.closeWithoutRestoring()
                UiState.focus(dlg.returnTarget()) // Check payment may be gone once resolved
            }
        }
    }

    contentItem: ColumnLayout {
        spacing: 12
        Banner {
            visible: !!dlg.d.failed
            title: "Not sent."
            body: "Your node never received this payment, so the coins are back in your balance. You can send it again."
        }
        Banner {
            visible: !!dlg.d.unknown
            tone: "warn"
            title: "Submission status unknown. Check this payment before trying again."
            body: "The connection dropped while it was being submitted, so the wallet can't yet tell whether your node received it. New payments wait until the wallet and node agree on what happened."
            AppButton {
                id: checkButton
                text: dlg.d.checking ? "Checking…" : "Check with node"
                iconName: "refresh"
                enabled: !dlg.d.checking
                onClicked: Wallet.reconcile(dlg.rowId)
            }
        }
        DefRow {
            label: "Amount"
            AmountLabel { view: dlg.d.amount || ({}); tag: true; presentational: true }
            accessibleValue: (dlg.d.amount ? dlg.d.amount.accessible : "") + ", test coins"
        }
        DefRow { visible: !!dlg.d.isOut; label: "Network fee"; value: dlg.d.fee || "" }
        DefRow {
            visible: !!dlg.d.isOut
            label: "To"
            AddressText { Layout.fillWidth: true; text: dlg.d.to || ""; presentational: true }
            accessibleValue: dlg.d.to || ""
        }
        DefRow { visible: !!dlg.d.isIn; label: "From"; value: "Not shown in this wallet"; valueColor: Theme.muted }
        DefRow {
            label: "Status"; value: dlg.d.status || ""
            valueColor: dlg.d.statusKind === "failed" ? Theme.danger : (dlg.d.statusKind === "pending" || dlg.d.statusKind === "unknown") ? Theme.warn : Theme.muted
        }
        DefRow { label: "Block"; value: dlg.d.block || "" }
        DefRow {
            visible: !!dlg.d.txid
            label: "Transaction ID"
            AddressText { Layout.fillWidth: true; text: dlg.d.txid || ""; grouped: false; onCopy: () => Wallet.copyTransactionId(dlg.rowId) }
            accessibleValue: dlg.d.txid || ""
        }
        DefRow { label: "Note"; value: dlg.d.note ? dlg.d.note + " (this computer only)" : "None"; valueColor: dlg.d.note ? Theme.fg : Theme.muted }
    }

    footer: DialogButtonBox {
        padding: 22
        topPadding: 8
        spacing: 10
        background: null
        AppButton {
            visible: !!dlg.d.txid
            text: "Copy ID"
            iconName: "copy"
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: Wallet.copyTransactionId(dlg.rowId)
        }
        AppButton {
            id: doneButton
            text: "Done"
            kind: "primary"
            DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            onClicked: dlg.close()
        }
    }
}
