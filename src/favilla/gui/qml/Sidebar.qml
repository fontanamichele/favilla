import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: sidebar

    property string current
    signal selected(string page)

    color: theme.sidebar

    function deviceDetail(device) {
        if (device.state === "unsupported")
            return qsTr("Not supported yet")
        if (device.state === "no_permission")
            return qsTr("Permission needed")
        if (device.state !== "connected")
            return qsTr("Cannot be opened")
        const parts = [device.connection === "wireless" ? qsTr("Wireless") : qsTr("Wired")]
        const battery = device.status ? device.status.battery : undefined
        if (battery)
            parts.push(battery.charging ? qsTr("%1% charging").arg(battery.level) : qsTr("%1%").arg(battery.level))
        return parts.join(" · ")
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 4

        RowLayout {
            Layout.leftMargin: 8
            Layout.topMargin: 10
            Layout.bottomMargin: 22
            spacing: 12

            Ember {
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30
            }
            Label {
                text: "favilla"
                font.pixelSize: 24
                font.weight: Font.Bold
                font.letterSpacing: 0.4
                color: theme.text
            }
        }

        SectionLabel { text: qsTr("Effects") }

        NavItem {
            text: qsTr("Lighting")
            detail: qsTr("Keyboard and mouse together")
            icon: "lighting"
            active: sidebar.current === "lighting"
            onClicked: sidebar.selected("lighting")
        }

        SectionLabel {
            text: qsTr("Devices")
            Layout.topMargin: 18
        }

        Repeater {
            model: backend.devices
            delegate: NavItem {
                required property var modelData
                text: modelData.name
                detail: sidebar.deviceDetail(modelData)
                icon: modelData.kind ?? "other"
                dim: modelData.state !== "connected"
                status: modelData.state === "connected" ? "good" : (modelData.state === "unsupported" ? "" : "warn")
                active: sidebar.current === modelData.id
                onClicked: sidebar.selected(modelData.id)
            }
        }

        Label {
            visible: backend.devices.length === 0
            Layout.leftMargin: 12
            text: qsTr("No SteelSeries device found")
            color: theme.textFaint
        }

        Item { Layout.fillHeight: true }

        ProfileSelector {
            Layout.fillWidth: true
        }
    }
}
