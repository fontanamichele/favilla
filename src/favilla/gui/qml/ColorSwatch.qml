import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// Current color, a few quick picks and a button for the full color dialog.
RowLayout {
    id: swatch

    property color color
    property string label: qsTr("Color")
    signal picked(string color)

    readonly property var presets: ["#ff4400", "#ff8a00", "#ffd000", "#ffffff",
                                    "#00c8ff", "#3d5afe", "#b04dff", "#ff2d6f", "#2dff8a"]

    Layout.fillWidth: true
    spacing: 12

    Label {
        text: swatch.label
        color: theme.text
        Layout.preferredWidth: 90
    }

    Rectangle {
        implicitWidth: 46
        implicitHeight: 30
        radius: 8
        color: swatch.color
        border.color: Qt.lighter(swatch.color, 1.5)
        border.width: 1

        HoverHandler { cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: dialog.open() }

        ToolTip.visible: hoverTip.hovered
        ToolTip.text: qsTr("Pick any color")
        HoverHandler { id: hoverTip }
    }

    Label {
        text: swatch.color.toString().toUpperCase()
        font.family: "monospace"
        color: theme.textDim
        Layout.preferredWidth: 72
    }

    Row {
        spacing: 7
        Repeater {
            model: swatch.presets
            delegate: Rectangle {
                required property string modelData
                width: 20
                height: 20
                radius: 10
                color: modelData
                border.width: Qt.colorEqual(modelData, swatch.color) ? 2 : 1
                border.color: Qt.colorEqual(modelData, swatch.color) ? theme.text : Qt.rgba(1, 1, 1, 0.15)

                HoverHandler { cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: swatch.picked(parent.modelData) }
            }
        }
    }

    Item { Layout.fillWidth: true }

    ColorDialog {
        id: dialog
        title: swatch.label
        selectedColor: swatch.color
        onAccepted: swatch.picked(selectedColor.toString())
    }
}
