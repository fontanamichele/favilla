import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label
    property string hint
    property real from: 0
    property real to: 1
    property real stepSize: 0
    property real value
    property var format: (v) => v.toFixed(1)
    signal moved(real value)

    Layout.fillWidth: true
    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            text: root.label
            color: theme.text
        }
        Label {
            text: root.format(slider.value)
            color: theme.accent
            font.weight: Font.DemiBold
        }
    }

    Slider {
        id: slider
        Layout.fillWidth: true
        Layout.leftMargin: -6
        Layout.rightMargin: -6
        from: root.from
        to: root.to
        stepSize: root.stepSize
        value: root.value
        onMoved: root.moved(value)
    }

    Label {
        Layout.fillWidth: true
        visible: root.hint !== ""
        text: root.hint
        wrapMode: Text.WordWrap
        font.pixelSize: 11
        color: theme.textFaint
    }
}
