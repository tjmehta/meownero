import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

PageBase {
    id: page
    title: "Wallet"

    Connections {
        target: Wallet
        function onSeedRequested() {
            if (Wallet.seedDialog === "password") { seedPassword.returnFocusTo = showSeed; seedPassword.open() }
            else if (Wallet.seedDialog === "words") { seedPassword.closeWithoutRestoring(); seedWords.returnFocusTo = showSeed; seedWords.open() }
        }
        function onSeedClosed() {
            if (seedPassword.visible) seedPassword.close()
            if (seedWords.visible) seedWords.close()
        }
        function onFocusField(name) { if (name === "seed-password") seedField.input.forceActiveFocus() }
    }

    SectionLabel { text: "Backup"; Layout.topMargin: 0 }
    Card {
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                AText { text: "Recovery words"; font.pointSize: Theme.pt(14); font.weight: Font.DemiBold; color: Theme.fg }
                AText { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "Show your 25 words and starting block again. Asks for your password first."; font.pointSize: Theme.pt(12.5); color: Theme.muted }
            }
            AppButton { id: showSeed; text: "Show recovery words"; iconName: "eye"; onClicked: Wallet.requestSeed() }
        }
    }
    SectionLabel { text: "This computer" }
    Card {
        DefRow { label: "Wallet file"; value: "Simulated: no wallet file is written"; valueColor: Theme.muted }
        DefRow {
            label: "Password"; accessibleValue: "Change password, not in this test build"
            RowLayout { spacing: 8; AppButton { text: "Change password"; enabled: false } AText { text: "Not in this test build"; font.pointSize: Theme.pt(12.5); color: Theme.muted } }
        }
        DefRow {
            label: "Lock"; accessibleValue: "Lock wallet now"
            AppButton { text: "Lock wallet now"; iconName: "lock"; accessibleDescription: "Shortcut: Control L"; onClicked: Wallet.lock() }
        }
    }
    SectionLabel { text: "About this test build" }
    Card {
        AText { Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.StyledText; text: "<b>Meownero Wallet</b> · native build with a simulated wallet engine, no release yet"; font.pointSize: Theme.pt(14); color: Theme.fg }
        DefRow { label: "Engine today"; value: "In the current test kit, the wallet engine can create and restore a wallet, receive, send a payment, report balances and incoming history, and mine test coins on the local regtest. This desktop app is connected to none of it: every wallet action here is simulated." }
        DefRow { label: "Designed, not yet tested with the kit"; value: "Wallet password and lock, opening a wallet file, reviewing the exact fee before submitting, address checks, send-max." }
        DefRow { label: "Not yet"; value: "Changing the password, separate addresses per payer, a full payment history, other people's nodes, Tor or I2P, hardware wallets, a shared testnet, mainnet." }
        DefRow { label: "Engine"; value: "Upstream wallet and node programs from the FCMP++/CARROT test branch, pinned for the Vanguard kit. Meownero's own reward schedule isn't applied yet." }
        DefRow { label: "Computers"; value: "Builds for macOS, Windows and Linux are planned. None has been tested or signed yet." }
    }
    AppButton { Layout.topMargin: 18; text: "Create or restore another wallet"; onClicked: Wallet.startOver() }

    component Card: Rectangle {
        default property alias body: inner.data
        Layout.fillWidth: true
        implicitHeight: inner.implicitHeight + 36
        radius: Theme.cardRadius; color: Theme.surface; border.width: 1; border.color: Theme.border
        ColumnLayout { id: inner; anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 } spacing: 10 }
    }

    AppDialog {
        id: seedPassword
        title: "Enter your password"
        description: "Your recovery words give full control of this wallet."
        initialFocus: seedField.input
        onClosed: if (Wallet.seedDialog === "password") Wallet.hideRecoveryWords()
        contentItem: ColumnLayout {
            spacing: 8
            AText { Layout.fillWidth: true; wrapMode: Text.Wrap; text: seedPassword.description; font.pointSize: Theme.pt(12.5); color: Theme.muted; Accessible.ignored: true }
            Field {
                id: seedField
                Layout.topMargin: 8
                label: "Password"
                password: true
                error: Wallet.seedError
                hint: Wallet.passwordHint
                onSubmitted: { Wallet.submitSeedPassword(text); text = "" }
            }
        }
        footer: DialogButtonBox {
            padding: 22; topPadding: 0; spacing: 10; background: null
            AppButton { text: "Cancel"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole; onClicked: seedPassword.close() }
            AppButton {
                text: "Show words"; kind: "primary"; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                onClicked: { Wallet.submitSeedPassword(seedField.text); seedField.text = "" }
            }
        }
    }
    AppDialog {
        id: seedWords
        wide: true
        title: "Recovery words"
        description: "Make sure no one can see your screen. Created at block " + Wallet.createdBlock.toLocaleString(Qt.locale(), "f", 0) + "."
        initialFocus: hideButton
        onClosed: Wallet.hideRecoveryWords()
        contentItem: ColumnLayout {
            spacing: 10
            AText { Layout.fillWidth: true; wrapMode: Text.Wrap; text: seedWords.description; font.pointSize: Theme.pt(12.5); color: Theme.muted; Accessible.ignored: true }
            WordsGrid { Layout.fillWidth: true; veiled: Wallet.seedDialog !== "words"; showReveal: false }
        }
        footer: DialogButtonBox {
            padding: 22; topPadding: 0; background: null
            AppButton { id: hideButton; text: "Hide words"; kind: "primary"; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole; onClicked: seedWords.close() }
        }
    }
}
