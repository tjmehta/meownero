import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Meownero.Core

// First run, create, restore and unlock. One step exists at a time.
Item {
    id: root
    readonly property var o: Wallet.onb
    readonly property bool wide: Wallet.route === "create-2" || Wallet.route === "restore-1"

    ScrollView {
        id: scroller
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true
        Item {
            width: scroller.availableWidth
            implicitHeight: stepLoader.implicitHeight + 80
            Loader {
                id: stepLoader
                y: 40
                width: Math.min(root.wide ? 740 : 560, parent.width - 48)
                anchors.horizontalCenter: parent.horizontalCenter
                sourceComponent: ({ "welcome": welcome, "create-1": create1, "create-2": create2, "create-3": create3,
                                    "create-4": create4, "restore-1": restore1, "restore-2": restore2, "restore-3": restore3,
                                    "unlock": unlock })[Wallet.route] || null
                onLoaded: scroller.ScrollBar.vertical.position = 0
            }
        }
    }

    Connections {
        target: Wallet
        function onFocusHeading() { if (stepLoader.item && stepLoader.item.heading) stepLoader.item.heading.forceActiveFocus() }
        function onFocusField(name) { if (stepLoader.item && stepLoader.item.focusField) stepLoader.item.focusField(name) }
    }

    component Step: ColumnLayout {
        id: step
        property alias heading: h
        property alias title: h.text
        property int stepNo: 0
        property int stepOf: 0
        property bool hero: false
        property string lead: ""
        default property alias body: content.data
        spacing: 0
        opacity: 0
        Component.onCompleted: fadeIn.start()
        NumberAnimation { id: fadeIn; target: step; property: "opacity"; to: 1; duration: Theme.pageMs; easing.type: Easing.OutQuint }

        Row {
            visible: step.stepOf > 0
            Layout.fillWidth: true
            Layout.bottomMargin: 18
            spacing: 6
            Accessible.role: Accessible.StaticText
            Accessible.name: "Step " + step.stepNo + " of " + step.stepOf
            Accessible.ignored: !visible
            Repeater {
                model: step.stepOf
                Rectangle { required property int index; width: (step.width - 6 * (step.stepOf - 1)) / step.stepOf; height: 4; radius: 4; color: index < step.stepNo ? Theme.net : Theme.borderStrong }
            }
        }
        CoinMark { visible: step.hero; size: 56 }
        PageHeading {
            id: h
            Layout.fillWidth: true
            Layout.topMargin: step.hero ? 14 : 0
            Layout.bottomMargin: 6
            font.pointSize: Theme.pt(26)
        }
        AText {
            visible: step.lead !== ""
            Layout.fillWidth: true
            Layout.bottomMargin: 16
            text: step.lead
            wrapMode: Text.Wrap
            font.pointSize: Theme.pt(14)
            color: Theme.muted
        }
        ColumnLayout { id: content; Layout.fillWidth: true; spacing: 0 }
    }

    component Buttons: Flow { Layout.fillWidth: true; Layout.topMargin: 4; spacing: 10 }

    Component {
        id: welcome
        Step {
            hero: true
            title: "Meownero Wallet"
            lead: "A private wallet for trying Meownero. This build only works with test networks, and test coins have no value."
            AText { text: "Network"; font.pointSize: Theme.pt(13.5); font.weight: Font.DemiBold; color: Theme.fg; Layout.topMargin: 2; Layout.bottomMargin: 6 }
            ChoiceItem {
                focusPolicy: Qt.NoFocus
                hoverEnabled: false
                selectedLook: true
                iconName: "flask"
                title: Wallet.networkName + " · Test coins only"
                subtitle: Wallet.networkSay
                Accessible.role: Accessible.StaticText
                Accessible.name: "Network: " + Wallet.networkName + ", test coins only. " + Wallet.networkSay
            }
            AText {
                Layout.fillWidth: true; Layout.bottomMargin: 18; wrapMode: Text.Wrap
                text: Wallet.networkKey === "regtest" ? "A shared Meownero testnet and mainnet don't exist yet, so this wallet can't hold real coins." : "Design preview only: this network isn't live."
                font.pointSize: Theme.pt(12.5); color: Theme.muted
            }
            AText { text: "Get started"; font.pointSize: Theme.pt(13.5); font.weight: Font.DemiBold; color: Theme.fg; Layout.bottomMargin: 6 }
            ChoiceItem { iconName: "key"; title: "Create a new wallet"; subtitle: "You'll write down 25 recovery words"; onClicked: Wallet.navigate("create-1") }
            ChoiceItem { iconName: "refresh"; title: "Restore from recovery words"; subtitle: "Bring back a wallet you backed up"; onClicked: Wallet.navigate("restore-1") }
            ChoiceItem { iconName: "lock"; title: "Open a wallet file"; subtitle: "A simulated wallet already on this computer"; onClicked: Wallet.navigate("unlock") }
        }
    }

    Component {
        id: create1
        Step {
            id: s
            stepNo: 1; stepOf: 4
            title: "Name and protect this wallet"
            lead: "The password locks the wallet file on this computer. It can't recover your wallet. Only your recovery words can do that."
            function focusField(n) { ({ name: nameF, pw: pwF, pw2: pw2F })[n].input.forceActiveFocus() }
            function submit() { Wallet.submitCreateDetails(nameF.text, pwF.text, pw2F.text) }
            Field { id: nameF; label: "Wallet name"; text: root.o.name; error: root.o.errors.name || ""; onSubmitted: s.submit() }
            Field { id: pwF; label: "Password"; password: true; error: root.o.errors.pw || ""; hint: "At least 8 characters."; onSubmitted: s.submit() }
            Field { id: pw2F; label: "Repeat password"; password: true; error: root.o.errors.pw2 || ""; onSubmitted: s.submit() }
            Buttons {
                AppButton { text: "Back"; onClicked: Wallet.navigate("welcome") }
                AppButton { text: "Continue"; kind: "primary"; onClicked: s.submit() }
            }
        }
    }

    Component {
        id: create2
        Step {
            stepNo: 2; stepOf: 4
            title: "Write down your recovery words"
            lead: "These 25 words are the only way to get this wallet back if this computer is lost. Write them on paper, in order, with the block number."
            AText { visible: !root.o.revealed; Layout.fillWidth: true; Layout.bottomMargin: 10; wrapMode: Text.Wrap; text: "Before you show them, stop any screen recording or sharing."; font.pointSize: Theme.pt(12.5); color: Theme.muted }
            WordsGrid { Layout.fillWidth: true; veiled: !root.o.revealed; onRevealRequested: Wallet.revealWords() }
            Banner { Layout.topMargin: 14; Layout.bottomMargin: 10; title: "Also write down: created at block " + root.o.createdAt; body: "Restoring is faster when you know where the wallet starts." }
            AText {
                Layout.fillWidth: true; Layout.bottomMargin: 14; wrapMode: Text.Wrap; textFormat: Text.StyledText
                text: "• Anyone with these words can spend your coins.<br>• Don't screenshot, photograph or paste them into a website or chat.<br>• Meownero will never ask you for them."
                font.pointSize: Theme.pt(12.5); color: Theme.muted
            }
            CheckBox {
                id: ack
                Layout.bottomMargin: 16
                enabled: root.o.revealed
                checked: root.o.ack
                text: "I've written down all 25 words and the block number."
                font.pointSize: Theme.pt(12.5)
                onToggled: Wallet.setAcknowledged(checked)
                contentItem: AText { leftPadding: ack.indicator.width + 8; text: ack.text; font: ack.font; color: Theme.fg; wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter; opacity: ack.enabled ? 1 : 0.45 }
            }
            Buttons {
                AppButton { text: "Back"; onClicked: Wallet.navigate("create-1") }
                AppButton { text: "Continue"; kind: "primary"; enabled: root.o.ack; onClicked: Wallet.navigate("create-3") }
            }
        }
    }

    Component {
        id: create3
        Step {
            stepNo: 3; stepOf: 4
            title: "Check your paper"
            lead: "Pick the right word for each position. This makes sure your copy is readable."
            Repeater {
                model: root.o.quiz
                ColumnLayout {
                    id: q
                    required property int modelData
                    readonly property string key: "" + modelData
                    Layout.fillWidth: true
                    Layout.bottomMargin: 14
                    spacing: 6
                    AText { text: "Word " + q.modelData; font.pointSize: Theme.pt(14); font.weight: Font.DemiBold; color: Theme.fg }
                    Flow {
                        Layout.fillWidth: true; spacing: 8
                        Accessible.role: Accessible.Grouping
                        Accessible.name: "Word " + q.modelData
                        Repeater {
                            model: Wallet.quizOptions(q.modelData)
                            AppButton {
                                required property string modelData
                                readonly property bool wrong: root.o.wrong[q.key] === modelData
                                text: modelData
                                font.family: Theme.mono
                                checkable: true
                                checked: root.o.picks[q.key] === modelData
                                Accessible.checkable: true
                                Accessible.checked: checked
                                Accessible.description: wrong ? "Wrong word" : ""
                                onClicked: Wallet.pickQuizWord(q.modelData, modelData)
                                background: Rectangle {
                                    radius: 7
                                    color: Theme.surface
                                    border.width: parent.visualFocus || parent.checked || parent.wrong ? 2 : 1
                                    border.color: parent.wrong ? Theme.danger : (parent.visualFocus || parent.checked) ? Theme.net : Theme.borderStrong
                                }
                            }
                        }
                    }
                    FieldError { visible: !!root.o.wrong[q.key]; error: "That isn't word " + q.modelData + ". Check your paper. If it's unclear, go back and write it again." }
                }
            }
            Buttons {
                AppButton { text: "Back to words"; onClicked: Wallet.navigate("create-2") }
                AppButton { text: "Finish"; kind: "primary"; enabled: root.o.quizOk; onClicked: Wallet.navigate("create-4") }
            }
        }
    }

    Component {
        id: create4
        Step {
            stepNo: 4; stepOf: 4
            title: "Your test wallet is ready"
            lead: root.o.name + " is on the " + Wallet.networkProse + ". It's empty for now."
            Rectangle {
                Layout.fillWidth: true; Layout.bottomMargin: 16
                implicitHeight: addrCol.implicitHeight + 36
                radius: Theme.cardRadius; color: Theme.surface; border.width: 1; border.color: Theme.border
                ColumnLayout {
                    id: addrCol
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
                    spacing: 6
                    AText { text: "Your address"; font.pointSize: Theme.pt(12.5); color: Theme.muted }
                    AddressText { Layout.fillWidth: true; text: Wallet.receiveAddress }
                }
            }
            Buttons { AppButton { text: "Open wallet"; kind: "primary"; large: true; onClicked: Wallet.openNewWallet() } }
        }
    }

    Component {
        id: restore1
        Step {
            id: s
            stepNo: 1; stepOf: 3
            title: "Enter your recovery words"
            lead: "Type or paste all 25 words in order. Pasting the whole phrase into the first box fills the rest."
            function focusField(n) {
                const i = parseInt(n.split(":")[1])
                if (!isNaN(i)) words.itemAt(i).forceActiveFocus()
            }
            Banner {
                Layout.bottomMargin: 14
                tone: "warn"
                title: "Simulated build: never type real recovery words here."
                body: "Only the sample words shown when creating a wallet can be restored. Nothing you type is saved."
            }
            GridLayout {
                Layout.fillWidth: true
                columns: Math.max(2, Math.floor((width + 8) / (138 + 8)))
                columnSpacing: 8; rowSpacing: 8
                Accessible.role: Accessible.Grouping
                Accessible.name: "Recovery words"
                Repeater {
                    id: words
                    model: 25
                    TextField {
                        required property int index
                        readonly property bool bad: root.o.badWords.indexOf(index) >= 0
                        Layout.fillWidth: true
                        Layout.minimumWidth: 138
                        text: Wallet.restoreWords[index] || ""
                        font.family: Theme.mono
                        font.pointSize: Theme.pt(12.5)
                        color: Theme.fg
                        leftPadding: 30; padding: 6
                        selectByMouse: true
                        inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase | Qt.ImhSensitiveData | Qt.ImhLowercaseOnly
                        Accessible.name: "Word " + (index + 1)
                        Accessible.description: root.o.errors.words || ""
                        onTextEdited: Wallet.setRestoreWord(index, text)
                        onAccepted: Wallet.submitRestoreWords()
                        background: Rectangle {
                            radius: 7; color: Theme.surface
                            border.width: parent.activeFocus || parent.bad ? 2 : 1
                            border.color: parent.activeFocus ? Theme.net : parent.bad ? Theme.danger : Theme.border
                            AText { x: 8; anchors.verticalCenter: parent.verticalCenter; text: index + 1; font.family: Theme.mono; font.pointSize: Theme.pt(11); color: Theme.faint }
                        }
                    }
                }
            }
            FieldError { Layout.topMargin: 8; error: root.o.errors.words || "" }
            Buttons {
                Layout.topMargin: 16
                AppButton { text: "Back"; onClicked: Wallet.navigate("welcome") }
                AppButton { text: "Continue"; kind: "primary"; onClicked: Wallet.submitRestoreWords() }
            }
        }
    }

    Component {
        id: restore2
        Step {
            id: s
            stepNo: 2; stepOf: 3
            title: "Where should the wallet start?"
            lead: "If you wrote down a block number, enter it. Otherwise the wallet scans the whole chain, which takes longer."
            function focusField(n) { ({ height: heightF, name: nameF, pw: pwF })[n].input.forceActiveFocus() }
            function submit() { Wallet.submitRestoreDetails(heightF.text, nameF.text, pwF.text) }
            Field {
                id: heightF
                label: "Created at block (optional)"
                error: root.o.errors.height || ""
                hint: "This chain is at block " + root.o.chainTip + ". Use a block before your first payment. If unsure, leave it empty to scan from the start."
                input.placeholderText: "for example 1,203"
                input.inputMethodHints: Qt.ImhDigitsOnly
                onSubmitted: s.submit()
            }
            Field { id: nameF; label: "Wallet name"; text: root.o.name; error: root.o.errors.name || ""; onSubmitted: s.submit() }
            Field { id: pwF; label: "New password for this computer"; password: true; error: root.o.errors.pw || ""; hint: "At least 8 characters. It doesn't need to match your old password."; onSubmitted: s.submit() }
            Buttons {
                AppButton { text: "Back"; onClicked: Wallet.navigate("restore-1") }
                AppButton { text: "Restore wallet"; kind: "primary"; onClicked: s.submit() }
            }
        }
    }

    Component {
        id: restore3
        Step {
            readonly property bool done: root.o.scan >= 100
            stepNo: 3; stepOf: 3
            title: done ? "Wallet restored" : "Finding your payments…"
            AText {
                Layout.fillWidth: true; Layout.bottomMargin: 10; wrapMode: Text.Wrap
                text: parent.parent.done ? root.o.restoredSummary : "Scanning block " + root.o.scanBlock + " of " + root.o.chainTip + ". You can leave this open; it continues in the background."
                font.pointSize: Theme.pt(14); color: Theme.muted
            }
            Rectangle {
                visible: !parent.parent.done
                Layout.fillWidth: true; height: 6; radius: 3; color: Theme.borderStrong
                Accessible.role: Accessible.ProgressBar
                Accessible.name: "Scanned " + root.o.scan + "%"
                Rectangle { width: parent.width * root.o.scan / 100; height: parent.height; radius: 3; color: Theme.net }
            }
            Banner {
                visible: parent.parent.done
                Layout.topMargin: 10
                title: "Your seed recovers on-chain funds and spending access after scanning."
                body: "It does not recover local notes, labels or contacts. Those stayed with the old wallet file."
            }
            Buttons {
                visible: parent.parent.done
                Layout.topMargin: 16
                AppButton { text: "Open wallet"; kind: "primary"; large: true; onClicked: Wallet.openRestoredWallet() }
            }
        }
    }

    Component {
        id: unlock
        Step {
            id: s
            hero: true
            title: Wallet.walletName + " is locked"
            lead: "Enter the password for this wallet file."
            function focusField(n) { if (n === "unlock") pw.input.forceActiveFocus() }
            function submit() { const t = pw.text; pw.text = ""; Wallet.unlock(t) }
            Field { id: pw; label: "Password"; password: true; error: root.o.unlockError || ""; hint: Wallet.passwordHint; onSubmitted: s.submit() }
            Buttons {
                AppButton { text: "Unlock"; kind: "primary"; onClicked: s.submit() }
                AppButton { text: "Use a different wallet"; kind: "quiet"; onClicked: Wallet.navigate("welcome") }
            }
        }
    }
}
