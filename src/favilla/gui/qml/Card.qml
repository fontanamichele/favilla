import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// A rounded panel with an optional title; children go into a column.
Rectangle {
    id: card

    property string title
    property string subtitle
    property string badge          // small grey tag next to the title
    default property alias content: body.data

    implicitHeight: column.implicitHeight + 44
    color: theme.surface
    radius: theme.radius
    border.color: theme.border
    border.width: 1

    ColumnLayout {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 22
        spacing: 16

        RowLayout {
            visible: card.title !== ""
            Layout.fillWidth: true
            spacing: 10

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Label {
                    text: card.title
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: theme.text
                }
                Label {
                    Layout.fillWidth: true
                    visible: card.subtitle !== ""
                    text: card.subtitle
                    wrapMode: Text.WordWrap
                    font.pixelSize: 12
                    color: theme.textDim
                }
            }

            Rectangle {
                visible: card.badge !== ""
                Layout.alignment: Qt.AlignTop
                implicitWidth: badgeLabel.implicitWidth + 16
                implicitHeight: badgeLabel.implicitHeight + 8
                radius: height / 2
                color: theme.surfaceHi
                Label {
                    id: badgeLabel
                    anchors.centerIn: parent
                    text: card.badge
                    font.pixelSize: 11
                    color: theme.textDim
                }
            }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 16
        }
    }
}
