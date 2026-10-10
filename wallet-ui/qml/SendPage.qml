import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// Send: form -> preparing (exact transaction built, nothing sent) -> review of
// the exact prepared values -> submitting -> result. The review dialog shows
// only what the controller prepared and confirms it by its token.
PageBase {
    id: page
    readonly property var s: Wallet.send
    readonly property var r: Wallet.sendResult
    readonly property string step: s.step
    title: step === "result" ? (r.kind === "refused" ? "Payment not sent" : r.kind === "unknown" ? "Submission status unknown" : "Sent") : "Send"

    Connections {
        target: Wallet
        function onReviewReady() { review.returnFocusTo = reviewButton; review.open() }
        function onReviewClosed() { if (review.visible) review.close() }
        function onFocusField(name) {
            if (name === "to") toField.forceActiveFocus()
            else if (name === "amount") amountField.forceActiveFocus()
        }
    }

    // ---- Preparing / submitting ----
    Rectangle {
        visible: page.step === "preparing" || page.step === "submitting"
        Layout.fillWidth: true
        implicitHeight: busy.implicitHeight + 36
        radius: Theme.cardRadius; color: Theme.surface; border.width: 1; border.color: Theme.border
        ColumnLayout {
            id: busy
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            spacing: 8
            RowLayout {
                spacing: 10
                Spinner { size: 14 }
                AText { text: page.step === "submitting" ? "Submitting to your node…" : "Preparing the payment…"; font.pointSize: Theme.pt(14); font.weight: Font.DemiBold; color: Theme.fg }
            }
            AText {
                Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
                text: page.step === "submitting" ? "Keep the wallet open. Don't close it until this finishes." : "Building the private transaction so you can review its exact fee. Nothing is sent yet."
            }
        }
    }

    // ---- Results ----
    Banner {
        visible: page.step === "result" && page.r.kind === "refused"
        tone: "bad"
        title: "Your node refused this payment. Nothing was sent."
        body: "The node said: “" + (page.r.reason || "") + ".” This usually means another copy of this wallet spent it, or a recent payment is still settling. Your balance hasn't changed."
        AppButton { text: "Back to the form"; onClicked: { Wallet.sendAnother(); page.heading.forceActiveFocus() } }
        AppButton { text: "View activity"; kind: "quiet"; onClicked: Wallet.navigate("activity") }
    }
    Banner {
        visible: page.step === "result" && page.r.kind === "unknown"
        tone: "warn"
        title: "Submission status unknown. Check this payment before trying again."
        body: "The connection dropped while it was being submitted, so the wallet can't yet tell whether your node received it. It's in Activity as “Status unknown”, and new payments wait until it's resolved."
        AppButton { id: checkPayment; text: "Check payment"; onClicked: page.shell.openDetail(page.r.rowId, checkPayment) }
        AppButton { text: "Overview"; kind: "quiet"; onClicked: Wallet.navigate("overview") }
    }
    Rectangle {
        visible: page.step === "result" && page.r.kind === "sent"
        Layout.fillWidth: true
        implicitHeight: sent.implicitHeight + 36
        radius: Theme.cardRadius; color: Theme.surface; border.width: 1; border.color: Theme.border
        ColumnLayout {
            id: sent
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            spacing: 16
            RowLayout {
                spacing: 12
                Rectangle { Layout.alignment: Qt.AlignTop; width: 32; height: 32; radius: 8; color: Theme.netSoft; Icon { anchors.centerIn: parent; name: "check"; color: Theme.net } }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    RowLayout {
                        spacing: 8
                        AText { text: "Submitted " + page.r.amount + " to your node."; font.pointSize: Theme.pt(14); font.weight: Font.DemiBold; color: Theme.fg; wrapMode: Text.Wrap; Layout.fillWidth: true; Accessible.name: text + " Test coins." }
                        NetTag {}
                    }
                    AText {
                        Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
                        text: "Waiting for the first confirmation. The recipient can spend it after 10 confirmations."
                              + (page.r.change ? " Your change, " + page.r.change + ", returns to your spendable balance after 10 confirmations, so spendable dropped by more than you sent." : "")
                    }
                }
            }
            ColumnLayout {
                spacing: 10
                DefRow { label: "Fee paid"; value: page.r.fee || "" }
                DefRow { label: "To"; accessibleValue: page.r.to || ""; AddressText { Layout.fillWidth: true; text: page.r.to || ""; presentational: true } }
                DefRow {
                    label: "Transaction ID"; accessibleValue: page.r.txid || ""
                    AddressText { Layout.fillWidth: true; text: page.r.txid || ""; grouped: false; onCopy: () => Wallet.copyTransactionId(page.r.rowId) }
                }
            }
            Flow {
                Layout.fillWidth: true; spacing: 10
                AppButton { text: "Copy ID"; iconName: "copy"; onClicked: Wallet.copyTransactionId(page.r.rowId) }
                AppButton { text: "Send another"; onClicked: { Wallet.sendAnother(); page.heading.forceActiveFocus() } }
                AppButton { text: "Done"; kind: "quiet"; onClicked: Wallet.navigate("overview") }
            }
        }
    }

    // ---- Form ----
    ColumnLayout {
        visible: page.step === "form"
        Layout.fillWidth: true
        spacing: 0

        ConditionBanners { Layout.bottomMargin: 18 }
        Banner {
            visible: page.s.hasUnknown
            Layout.bottomMargin: 18
            tone: "warn"
            title: "One payment's submission status is unknown."
            body: "Check it before sending another, so the same payment isn't made twice."
            AppButton { id: checkUnknown; text: "Check payment"; onClicked: page.shell.openDetail(page.s.unknownRowId, checkUnknown) }
        }

        ColumnLayout {
            visible: Wallet.networkKey === "regtest"
            Layout.fillWidth: true
            Layout.bottomMargin: 16
            spacing: 6
            AText { text: "Pay one of your test wallets"; font.pointSize: Theme.pt(13.5); font.weight: Font.DemiBold; color: Theme.fg }
            Flow {
                Layout.fillWidth: true; spacing: 10
                Repeater {
                    // A fixed count keeps the buttons (and focus) alive when the selection changes.
                    model: 2
                    AppButton {
                        required property int index
                        readonly property var modelData: Wallet.kitWallets[index]
                        text: modelData.label + "  " + modelData.short
                        checkable: true
                        checked: modelData.selected
                        Accessible.name: modelData.label
                        Accessible.checkable: true
                        Accessible.checked: modelData.selected
                        onClicked: Wallet.pickKitWallet(modelData.key) // focus stays on the control
                    }
                }
            }
        }

        AText { text: "To"; font.pointSize: Theme.pt(13.5); font.weight: Font.DemiBold; color: Theme.fg; Accessible.ignored: true }
        TextArea {
            id: toField
            Layout.fillWidth: true
            textFormat: TextEdit.PlainText
            Layout.topMargin: 6
            text: page.s.to
            placeholderText: page.s.placeholder
            placeholderTextColor: Theme.faint
            wrapMode: TextEdit.WrapAnywhere
            font.family: Theme.mono
            font.pointSize: Theme.pt(13)
            color: Theme.fg
            selectByMouse: true
            inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
            padding: 9; leftPadding: 11
            implicitHeight: Math.max(64, contentHeight + 20)
            Accessible.name: "To"
            Accessible.ignored: !visible
            Accessible.description: page.s.toError !== "" ? page.s.toError : page.s.toHint
            KeyNavigation.priority: KeyNavigation.BeforeItem
            KeyNavigation.tab: amountField
            Keys.onReturnPressed: (e) => { e.accepted = true; Wallet.requestReview() }
            onTextChanged: if (activeFocus) Wallet.setSendField("to", text)
            background: Rectangle {
                radius: Theme.controlRadius; color: Theme.surface
                border.width: toField.activeFocus ? 2 : 1
                border.color: toField.activeFocus ? Theme.net : page.s.toError !== "" ? Theme.danger : Theme.borderStrong
            }
        }
        FieldError { error: page.s.toError; hint: page.s.toHint }

        AText { Layout.topMargin: 16; text: "Amount"; font.pointSize: Theme.pt(13.5); font.weight: Font.DemiBold; color: Theme.fg; Accessible.ignored: true }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            spacing: 8
            TextField {
                id: amountField
                Layout.fillWidth: true
                text: page.s.amount
                placeholderText: "0" + page.s.decimalPoint + "0"
                placeholderTextColor: Theme.faint
                font.pointSize: Theme.pt(14)
                font.features: { "tnum": 1 }
                color: Theme.fg
                selectByMouse: true
                inputMethodHints: Qt.ImhFormattedNumbersOnly | Qt.ImhNoPredictiveText
                padding: 9; leftPadding: 11; rightPadding: 70
                Accessible.name: "Amount in MEOW"
                Accessible.ignored: !visible
                Accessible.description: page.s.amountError !== "" ? page.s.amountError : "Spendable now: " + page.s.spendableHint + "."
                onTextEdited: Wallet.setSendField("amount", text)
                onAccepted: Wallet.requestReview()
                background: Rectangle {
                    radius: Theme.controlRadius; color: Theme.surface
                    border.width: amountField.activeFocus ? 2 : 1
                    border.color: amountField.activeFocus ? Theme.net : page.s.amountError !== "" ? Theme.danger : Theme.borderStrong
                }
                AText {
                    anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                    text: "MEOW"; font.pointSize: Theme.pt(12.5); font.weight: Font.DemiBold; color: Theme.muted
                    Accessible.ignored: true
                }
            }
            AppButton {
                text: "Max"
                accessibleDescription: "Send everything spendable, minus the fee"
                ToolTip.visible: hovered
                ToolTip.text: "Send everything spendable, minus the fee"
                onClicked: Wallet.useMax()
            }
        }
        FieldError { error: page.s.amountError; hint: "Spendable now: " + page.s.spendableHint + "." }

        Field {
            id: noteField
            Layout.topMargin: 16
            label: "Note (optional)"
            hint: "Saved on this computer only. It isn't sent, and it doesn't come back if you restore from your recovery words."
            text: page.s.note
            input.maximumLength: 80
            onEdited: (t) => Wallet.setSendField("note", t)
            onSubmitted: Wallet.requestReview()
        }

        Flow {
            Layout.fillWidth: true
            spacing: 10
            AppButton {
                id: reviewButton
                text: "Review payment"
                kind: "primary"
                large: true
                enabled: page.s.canReview
                accessibleDescription: page.s.disabledReason
                onClicked: Wallet.requestReview()
            }
            AText {
                visible: page.s.disabledReason !== ""
                width: Math.min(implicitWidth, page.width - reviewButton.width - 10)
                height: reviewButton.height
                verticalAlignment: Text.AlignVCenter
                text: page.s.disabledReason
                wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
            }
        }
    }

    // ---- Review of the exact prepared payment ----
    AppDialog {
        id: review
        readonly property var v: Wallet.review
        title: "Review payment"
        description: "Check the address against what the recipient gave you. Payments can't be reversed."
        initialFocus: confirmButton
        // Edit, Escape or clicking outside discards the prepared payment.
        onClosed: if (Wallet.review.open) Wallet.cancelReview()
        contentItem: ColumnLayout {
            spacing: 10
            AText { Layout.fillWidth: true; wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted; text: review.description; Accessible.ignored: true }
            DefRow {
                Layout.topMargin: 6
                label: "You send"; accessibleValue: (review.v.amount || "") + ", test coins"
                RowLayout { spacing: 8; AText { text: review.v.amount || ""; font.pointSize: Theme.pt(13.5); color: Theme.fg; Accessible.ignored: true } NetTag {} }
            }
            DefRow { label: "Network fee"; value: review.v.fee || "" }
            DefRow {
                label: "Total"; accessibleValue: (review.v.total || "") + ", test coins"
                RowLayout { spacing: 8; AText { text: review.v.total || ""; font.pointSize: Theme.pt(13.5); font.weight: Font.Bold; color: Theme.fg; Accessible.ignored: true } NetTag {} }
            }
            DefRow { label: "To"; accessibleValue: review.v.to || ""; AddressText { Layout.fillWidth: true; text: review.v.to || ""; presentational: true } }
            DefRow { label: "Network"; value: review.v.network || "" }
            DefRow { visible: !!review.v.note; label: "Note"; value: (review.v.note || "") + " (this computer only)" }
            AText {
                Layout.fillWidth: true; Layout.topMargin: 6; wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
                text: "This is the exact payment that will be submitted. If you edit anything, it's prepared again and you review it again."
            }
        }
        footer: DialogButtonBox {
            padding: 22; topPadding: 8; spacing: 10
            background: null
            AppButton {
                text: "Edit"
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
                onClicked: review.reject()
            }
            AppButton {
                id: confirmButton
                text: review.v.confirmLabel || "Send"
                accessibleDescription: "Total " + (review.v.total || "") + ", test coins, including the network fee " + (review.v.fee || "") + ", to " + (review.v.to || "")
                kind: "primary"
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                onClicked: {
                    const token = review.v.token
                    review.closeWithoutRestoring()
                    Wallet.confirmSend(token)
                }
            }
        }
    }
}
