import QtQuick
import QtQuick.Layouts
import Meownero.Core

PageBase {
    id: page
    title: "Activity"
    headerRight: AppButton {
        text: "Show every digit"; kind: "quiet"; checkable: true; checked: Wallet.exactDigits
        Accessible.checkable: true; Accessible.checked: Wallet.exactDigits
        onClicked: Wallet.toggleExact()
    }
    ConditionBanners { Layout.bottomMargin: 18 }
    ActivityList { visible: Wallet.activity.count > 0; model: Wallet.activity; shell: page.shell }
    AText {
        visible: Wallet.activity.count === 0
        Layout.fillWidth: true
        text: "No payments yet."
        font.pointSize: Theme.pt(14); color: Theme.muted
    }
    AText {
        Layout.fillWidth: true; Layout.topMargin: 12
        text: "Incoming payments don't show who sent them. Notes you add stay on this computer and don't come back when you restore from your recovery words."
        wrapMode: Text.Wrap; font.pointSize: Theme.pt(12.5); color: Theme.muted
    }
}
