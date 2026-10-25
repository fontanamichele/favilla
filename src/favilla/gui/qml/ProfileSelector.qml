import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: selector

    spacing: 6

    SectionLabel { text: qsTr("Profile") }

    RowLayout {
        Layout.fillWidth: true
        spacing: 4

        ComboBox {
            id: combo
            Layout.fillWidth: true
            model: backend.profileNames
            currentIndex: backend.profileNames.indexOf(backend.activeProfile)
            onActivated: (index) => backend.switchProfile(backend.profileNames[index])
        }

        ToolButton {
            text: "⋯"
            font.pixelSize: 18
            onClicked: menu.popup()

            ToolTip.visible: hovered
            ToolTip.text: qsTr("Manage profiles")

            Menu {
                id: menu
                MenuItem {
                    text: qsTr("New profile…")
                    onTriggered: nameDialog.ask("create")
                }
                MenuItem {
                    text: qsTr("Rename…")
                    onTriggered: nameDialog.ask("rename")
                }
                MenuSeparator {}
                MenuItem {
                    text: qsTr("Delete “%1”").arg(backend.activeProfile)
                    enabled: backend.profileNames.length > 1
                    onTriggered: deleteDialog.open()
                }
            }
        }
    }

    Dialog {
        id: nameDialog

        property string mode: "create"
        property string error

        function ask(newMode) {
            mode = newMode
            error = ""
            field.text = mode === "rename" ? backend.activeProfile : ""
            open()
            field.forceActiveFocus()
            field.selectAll()
        }

        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 380
        modal: true
        title: mode === "create" ? qsTr("New profile") : qsTr("Rename profile")
        standardButtons: Dialog.Ok | Dialog.Cancel

        onAccepted: {
            const result = mode === "create"
                ? backend.createProfile(field.text)
                : backend.renameProfile(backend.activeProfile, field.text)
            if (result !== "") {
                error = result
                open()
            }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 8

            Label {
                Layout.fillWidth: true
                visible: nameDialog.mode === "create"
                text: qsTr("The new profile starts as a copy of “%1”.").arg(backend.activeProfile)
                wrapMode: Text.WordWrap
                color: theme.textDim
            }
            TextField {
                id: field
                Layout.fillWidth: true
                placeholderText: qsTr("Profile name")
                maximumLength: 40
                onAccepted: nameDialog.accept()
            }
            Label {
                visible: nameDialog.error !== ""
                text: nameDialog.error
                color: theme.bad
            }
        }
    }

    Dialog {
        id: deleteDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: qsTr("Delete profile")
        standardButtons: Dialog.Yes | Dialog.No

        onAccepted: {
            const result = backend.deleteProfile(backend.activeProfile)
            if (result !== "")
                backend.notify(result, true)
        }

        Label {
            text: qsTr("Delete “%1”? This cannot be undone.").arg(backend.activeProfile)
            color: theme.text
        }
    }
}
