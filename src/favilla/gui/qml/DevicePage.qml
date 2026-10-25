import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: page

    property var device
    readonly property string deviceId: device ? device.id : ""
    readonly property bool connected: device !== null && device.state === "connected"
    readonly property bool isKeyboard: connected && device.kind === "keyboard"
    readonly property var settings: connected ? device.settings : []
    readonly property var saved: connected ? (backend.deviceSettings[device.model] ?? {}) : ({})
    readonly property var battery: connected && device.status ? device.status.battery : undefined
    readonly property int margin: 32

    // Edits not applied yet: {setting: value}
    property var draft: ({})
    readonly property int changes: Object.keys(draft).length

    function valueOf(setting) {
        if (draft[setting.name] !== undefined)
            return draft[setting.name]
        if (saved[setting.name] !== undefined)
            return saved[setting.name]
        return setting.default
    }
    function edit(name, value) {
        const next = Object.assign({}, draft)
        next[name] = value
        draft = next
    }

    onDeviceIdChanged: draft = ({})
    contentWidth: availableWidth
    clip: true

    ColumnLayout {
        width: page.availableWidth
        spacing: 18

        PageHeader {
            Layout.fillWidth: true
            Layout.topMargin: 30
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            title: page.device ? page.device.name : ""
            subtitle: !page.connected ? ""
                : page.isKeyboard ? qsTr("Keyboard · %1").arg(page.device.connection === "wireless" ? qsTr("2.4 GHz wireless") : qsTr("USB cable"))
                : qsTr("Mouse · %1").arg(page.device.connection === "wireless" ? qsTr("2.4 GHz wireless") : qsTr("USB cable"))
        }

        // Battery and identity
        RowLayout {
            visible: page.connected
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            spacing: 10

            Rectangle {
                visible: page.battery !== undefined
                implicitWidth: batteryRow.implicitWidth + 24
                implicitHeight: 36
                radius: 18
                color: theme.surface
                border.color: theme.border

                RowLayout {
                    id: batteryRow
                    anchors.centerIn: parent
                    spacing: 8

                    Rectangle {   // battery gauge
                        implicitWidth: 26
                        implicitHeight: 12
                        radius: 3
                        color: "transparent"
                        border.color: theme.textDim
                        Rectangle {
                            x: 2; y: 2
                            height: parent.height - 4
                            width: (parent.width - 4) * Math.max(0.05, (page.battery ? page.battery.level : 0) / 100)
                            radius: 1.5
                            color: page.battery && page.battery.level <= 20 ? theme.bad : theme.good
                        }
                    }
                    Label {
                        text: page.battery ? (page.battery.charging ? qsTr("%1% · charging").arg(page.battery.level)
                                                                    : qsTr("%1% battery").arg(page.battery.level)) : ""
                        color: theme.text
                    }
                }
            }

            Rectangle {
                implicitWidth: idLabel.implicitWidth + 24
                implicitHeight: 36
                radius: 18
                color: theme.surface
                border.color: theme.border
                Label {
                    id: idLabel
                    anchors.centerIn: parent
                    text: page.device ? "USB " + page.device.usb_id : ""
                    font.family: "monospace"
                    color: theme.textDim
                }
            }
        }

        // Unsupported device or device that could not be opened
        Card {
            visible: page.device !== null && !page.connected
            Layout.fillWidth: true
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            title: page.device && page.device.state === "unsupported" ? qsTr("Not supported yet")
                                                                       : qsTr("Favilla cannot open this device")
            subtitle: page.device && page.device.state === "unsupported"
                ? qsTr("Favilla sees this device but does not know how to talk to it yet. Support can be added with a USB capture: see docs/adding-a-device.md in the project.")
                : (page.device && page.device.message ? page.device.message : "")

            Label {
                visible: page.device !== null && page.device.state === "no_permission"
                Layout.fillWidth: true
                text: qsTr("Install the udev rules from the project folder, then reconnect the device:")
                color: theme.textDim
                wrapMode: Text.WordWrap
            }
            TextArea {
                visible: page.device !== null && page.device.state === "no_permission"
                Layout.fillWidth: true
                readOnly: true
                selectByMouse: true
                font.family: "monospace"
                text: "sudo install -m644 data/udev/60-favilla.rules /etc/udev/rules.d/\nsudo udevadm control --reload && sudo udevadm trigger"
            }
        }

        // ---- keyboard -------------------------------------------------------

        Card {
            visible: page.isKeyboard
            Layout.fillWidth: true
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            title: qsTr("Physical layout")
            subtitle: qsTr("Used to draw the keyboard and to place each key for the effects")

            ChipRow {
                value: backend.desk.keyboard_layout ?? ""
                options: page.isKeyboard ? page.device.layouts.map((l) => ({ value: l.id, label: l.name })) : []
                onPicked: (value) => backend.setDesk("keyboard_layout", value)
            }
        }

        Card {
            visible: page.isKeyboard && page.device.tested === false
            Layout.fillWidth: true
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            title: qsTr("Untested connection mode")
            subtitle: qsTr("Lighting in this mode follows the published protocol but has not been tried on real hardware yet. Please report whether it works.")
        }

        Card {
            visible: page.isKeyboard
            Layout.fillWidth: true
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            title: qsTr("Coming next")
            subtitle: qsTr("These settings need parts of the keyboard protocol that are still being reverse engineered.")
            badge: qsTr("Roadmap")

            Repeater {
                model: [qsTr("Actuation point for every key"), qsTr("Rapid Trigger"),
                        qsTr("Key remapping and Fn layer"), qsTr("Onboard profiles")]
                delegate: RowLayout {
                    required property string modelData
                    spacing: 12
                    Rectangle { implicitWidth: 6; implicitHeight: 6; radius: 3; color: theme.accent }
                    Label { text: parent.modelData; color: theme.text }
                }
            }
        }

        // ---- mouse settings -------------------------------------------------

        Repeater {
            model: page.settings

            delegate: SettingCard {
                required property var modelData
                Layout.fillWidth: true
                Layout.leftMargin: page.margin
                Layout.rightMargin: page.margin
                setting: modelData
                value: page.valueOf(modelData)
                isSet: page.draft[modelData.name] !== undefined || page.saved[modelData.name] !== undefined
                changed: page.draft[modelData.name] !== undefined
                onEdited: (value) => page.edit(modelData.name, value)
            }
        }

        RowLayout {
            visible: page.settings.length > 0
            Layout.fillWidth: true
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            spacing: 10

            Label {
                Layout.fillWidth: true
                text: page.changes > 0 ? qsTr("%n change(s) not applied yet", "", page.changes)
                                       : qsTr("Settings marked “Not set” are left as they are on the device.")
                color: page.changes > 0 ? theme.text : theme.textFaint
                wrapMode: Text.WordWrap
            }
            Button {
                text: qsTr("Discard")
                flat: true
                enabled: page.changes > 0
                onClicked: page.draft = ({})
            }
            Button {
                text: qsTr("Apply to the mouse")
                highlighted: true
                enabled: page.changes > 0
                onClicked: {
                    backend.applyDeviceSettings(page.device.id, page.device.model, page.draft)
                    page.draft = ({})
                }
            }
        }

        Item { Layout.preferredHeight: 20 }
    }
}
