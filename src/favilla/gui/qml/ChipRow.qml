import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// A row of pill buttons to pick one value.
Flow {
    id: chips

    property var options: []      // [{value, label}]
    property string value
    signal picked(string value)

    Layout.fillWidth: true
    spacing: 8

    Repeater {
        model: chips.options

        delegate: Rectangle {
            id: chip

            required property var modelData
            readonly property bool selected: modelData.value === chips.value

            implicitWidth: label.implicitWidth + 30
            implicitHeight: 34
            radius: height / 2
            color: selected ? theme.accent : (hover.hovered ? theme.surfaceHi : "transparent")
            border.color: selected ? theme.accent : theme.border
            border.width: 1

            Behavior on color { ColorAnimation { duration: 120 } }

            Label {
                id: label
                anchors.centerIn: parent
                text: chip.modelData.label
                color: chip.selected ? "#1a0b04" : theme.text
                font.weight: chip.selected ? Font.DemiBold : Font.Normal
            }

            HoverHandler {
                id: hover
                cursorShape: Qt.PointingHandCursor
            }
            TapHandler {
                onTapped: chips.picked(chip.modelData.value)
            }
        }
    }
}
