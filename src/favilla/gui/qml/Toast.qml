import QtQuick
import QtQuick.Controls

// A message that appears at the bottom of the window for a few seconds.
Rectangle {
    id: toast

    property bool error: false

    function show(message, isError) {
        text.text = message
        error = isError
        opacity = 1
        hideTimer.restart()
    }

    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 28
    width: Math.min(text.implicitWidth + 44, parent.width - 120)
    height: text.implicitHeight + 26
    radius: 12
    color: error ? "#3a161a" : "#1f2a22"
    border.color: error ? theme.bad : theme.good
    border.width: 1
    opacity: 0
    visible: opacity > 0

    Behavior on opacity { NumberAnimation { duration: 180 } }

    Label {
        id: text
        anchors.centerIn: parent
        width: Math.min(implicitWidth, toast.parent.width - 164)
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        color: theme.text
    }

    Timer {
        id: hideTimer
        interval: 4500
        onTriggered: toast.opacity = 0
    }

    TapHandler { onTapped: toast.opacity = 0 }
}
