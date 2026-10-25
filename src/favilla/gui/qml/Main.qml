import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

ApplicationWindow {
    id: window

    property string page: "lighting"   // "lighting" or the id of a device

    width: 1240
    height: 800
    minimumWidth: 980
    minimumHeight: 640
    visible: true
    title: "Favilla"
    color: theme.bg

    Material.theme: Material.Dark
    Material.accent: theme.accent
    Material.background: theme.surfaceHi
    Material.foreground: theme.text
    Material.roundedScale: Material.SmallScale

    function deviceById(id) {
        for (const device of backend.devices)
            if (device.id === id)
                return device
        return null
    }

    // The live preview polls the daemon only while somebody can see it.
    Binding {
        target: backend
        property: "previewEnabled"
        value: window.visible && window.visibility !== Window.Minimized && window.page === "lighting"
    }

    // A device page whose device went away falls back to the lighting page.
    Connections {
        target: backend
        function onDevicesChanged() {
            if (window.page !== "lighting" && window.deviceById(window.page) === null)
                window.page = "lighting"
        }
        function onNotify(message, isError) {
            toast.show(message, isError)
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Sidebar {
            Layout.fillHeight: true
            Layout.preferredWidth: 264
            current: window.page
            onSelected: (page) => window.page = page
        }

        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            color: theme.border
        }

        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: window.page === "lighting" ? lightingPage : devicePage
        }
    }

    Component {
        id: lightingPage
        LightingPage {}
    }

    Component {
        id: devicePage
        DevicePage {
            device: window.deviceById(window.page)
        }
    }

    // Shown while the daemon cannot be reached.
    Rectangle {
        anchors.fill: parent
        visible: !backend.online
        color: Qt.rgba(0.05, 0.05, 0.07, 0.92)

        TapHandler {}   // swallow clicks

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 12

            Ember {
                Layout.alignment: Qt.AlignHCenter
                width: 56
                height: 56
                dim: true
            }
            Label {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("The Favilla service is not running")
                font.pixelSize: 20
                font.weight: Font.DemiBold
                color: theme.text
            }
            Label {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Start it from a terminal, the window will connect by itself:")
                color: theme.textDim
            }
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: command.implicitWidth + 32
                implicitHeight: command.implicitHeight + 18
                radius: 8
                color: theme.surface
                border.color: theme.border
                Label {
                    id: command
                    anchors.centerIn: parent
                    text: "systemctl --user start favilla"
                    font.family: "monospace"
                    color: theme.accent
                }
            }
        }
    }

    Toast {
        id: toast
    }
}
