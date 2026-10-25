import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    property string title
    property string subtitle

    spacing: 6

    Label {
        text: parent.title
        font.pixelSize: 28
        font.weight: Font.DemiBold
        color: theme.text
    }
    Label {
        Layout.fillWidth: true
        visible: parent.subtitle !== ""
        text: parent.subtitle
        wrapMode: Text.WordWrap
        font.pixelSize: 13
        color: theme.textDim
    }
}
