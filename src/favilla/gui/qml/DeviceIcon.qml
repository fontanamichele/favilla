import QtQuick

// Small line icons drawn with rectangles, so they need no icon font.
Item {
    id: icon

    property string kind
    property color tint: theme.textDim

    implicitWidth: 22
    implicitHeight: 22

    Rectangle {
        visible: icon.kind === "keyboard"
        anchors.centerIn: parent
        width: 21
        height: 13
        radius: 3
        color: "transparent"
        border.color: icon.tint
        border.width: 1.5

        Grid {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -1
            columns: 5
            spacing: 2
            Repeater {
                model: 10
                Rectangle { width: 2; height: 2; color: icon.tint }
            }
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2.5
            width: 9
            height: 1.5
            color: icon.tint
        }
    }

    Rectangle {
        visible: icon.kind === "mouse"
        anchors.centerIn: parent
        width: 13
        height: 20
        radius: 6.5
        color: "transparent"
        border.color: icon.tint
        border.width: 1.5

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 3.5
            width: 1.5
            height: 5
            radius: 1
            color: icon.tint
        }
    }

    Rectangle {
        visible: icon.kind !== "keyboard" && icon.kind !== "mouse"
        anchors.centerIn: parent
        width: 15
        height: 15
        radius: 4
        color: "transparent"
        border.color: icon.tint
        border.width: 1.5
    }
}
