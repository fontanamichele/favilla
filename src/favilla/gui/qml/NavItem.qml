import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: item

    property string text
    property string detail
    property string icon            // "lighting", "keyboard", "mouse" or "other"
    property string status          // "", "good" or "warn"
    property bool active: false
    property bool dim: false
    signal clicked()

    Layout.fillWidth: true
    implicitHeight: 54
    radius: 10
    color: active ? theme.accentSoft : (hover.hovered ? theme.surfaceHi : "transparent")

    Behavior on color { ColorAnimation { duration: 120 } }

    Rectangle {
        visible: item.active
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 3
        height: 22
        radius: 2
        color: theme.accent
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 12
        spacing: 12

        Item {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22

            Ember {
                visible: item.icon === "lighting"
                anchors.fill: parent
                dim: !item.active
            }
            DeviceIcon {
                visible: item.icon !== "lighting"
                anchors.fill: parent
                kind: item.icon
                tint: item.active ? theme.accent : (item.dim ? theme.textFaint : theme.textDim)
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            Label {
                Layout.fillWidth: true
                text: item.text
                elide: Text.ElideRight
                color: item.dim ? theme.textDim : theme.text
                font.weight: item.active ? Font.DemiBold : Font.Medium
            }
            Label {
                Layout.fillWidth: true
                visible: item.detail !== ""
                text: item.detail
                elide: Text.ElideRight
                color: theme.textFaint
                font.pixelSize: 11
            }
        }

        Rectangle {
            visible: item.status !== ""
            Layout.preferredWidth: 8
            Layout.preferredHeight: 8
            radius: 4
            color: item.status === "good" ? theme.good : theme.warn
        }
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
    }
    TapHandler {
        onTapped: item.clicked()
    }
}
