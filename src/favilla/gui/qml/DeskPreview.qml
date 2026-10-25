import QtQuick
import QtQuick.Controls
import QtQuick.Shapes

// Live picture of the desk: every connected device drawn where the lighting
// engine thinks it is, with the colors its LEDs are showing right now.
Item {
    id: desk

    readonly property var connected: backend.devices.filter((d) => d.state === "connected")
    readonly property bool hasMouse: connected.some((d) => d.kind === "mouse")
    readonly property real mouseX: backend.desk.mouse_x ?? 19
    readonly property real x0: -0.7
    readonly property real x1: hasMouse ? mouseX + 2.5 : 15.7
    readonly property real y0: -0.9
    readonly property real y1: 6.9
    readonly property real unit: Math.min(width / (x1 - x0), height / (y1 - y0))
    readonly property real originX: (width - unit * (x1 - x0)) / 2 - x0 * unit
    readonly property real originY: (height - unit * (y1 - y0)) / 2 - y0 * unit

    function ledColor(deviceId, ledId) {
        const frame = backend.frame[deviceId]
        return frame && frame[ledId] ? frame[ledId] : "#303139"
    }
    function withAlpha(c, a) {
        return Qt.rgba(c.r, c.g, c.b, a)
    }

    implicitHeight: 300

    Label {
        anchors.centerIn: parent
        visible: desk.connected.length === 0
        text: qsTr("Connect a supported device to see it here")
        color: theme.textDim
    }

    Repeater {
        model: desk.connected

        delegate: Item {
            id: device

            required property var modelData
            readonly property real dx: modelData.kind === "mouse" ? desk.mouseX : 0
            readonly property real dy: modelData.kind === "mouse" ? 3.0 : 0

            anchors.fill: parent

            // keyboard case
            Rectangle {
                visible: device.modelData.kind === "keyboard"
                x: desk.originX + (device.dx - 0.32) * desk.unit
                y: desk.originY + (device.dy - 0.32) * desk.unit
                width: 15.64 * desk.unit
                height: 5.64 * desk.unit
                radius: 0.42 * desk.unit
                color: "#111216"
                border.color: "#23242b"
            }

            // mouse shell
            Rectangle {
                id: shell
                readonly property var body: device.modelData.body ?? [0, 0, 0, 0]
                visible: device.modelData.body !== null && device.modelData.body !== undefined
                x: desk.originX + (device.dx + body[0]) * desk.unit
                y: desk.originY + (device.dy + body[1]) * desk.unit
                width: body[2] * desk.unit
                height: body[3] * desk.unit
                radius: width / 2
                color: "#14151a"
                border.color: "#25262d"

                Rectangle {   // split between the two buttons
                    x: parent.width / 2
                    width: 1
                    height: parent.height * 0.34
                    color: "#2b2c34"
                }
                Rectangle {   // wheel
                    x: (parent.width - width) / 2
                    y: parent.height * 0.1
                    width: parent.width * 0.15
                    height: parent.height * 0.12
                    radius: width / 2
                    color: "#23242b"
                }
            }

            Repeater {
                model: device.modelData.leds.filter((led) => led.visible)

                delegate: Item {
                    id: led

                    required property var modelData
                    readonly property color lit: desk.ledColor(device.modelData.id, modelData.id)
                    readonly property color fill: Qt.tint("#1c1d23", desk.withAlpha(lit, 0.36))
                    readonly property color edge: desk.withAlpha(lit, 0.95)
                    readonly property bool shaped: (modelData.outline ?? "") !== ""
                    readonly property bool strip: device.modelData.kind === "mouse"

                    anchors.fill: parent

                    // keys that are not rectangles (ISO Enter) are drawn from their outline
                    Shape {
                        visible: led.shaped
                        x: desk.originX + device.dx * desk.unit
                        y: desk.originY + device.dy * desk.unit
                        transform: Scale { xScale: desk.unit; yScale: desk.unit }
                        preferredRendererType: Shape.CurveRenderer

                        ShapePath {
                            fillColor: led.fill
                            strokeColor: led.edge
                            strokeWidth: Math.max(1 / desk.unit, 0.05)
                            PathSvg { path: led.modelData.outline ?? "" }
                        }
                    }

                    Repeater {
                        model: led.modelData.rects

                        delegate: Rectangle {
                            id: cap

                            required property var modelData   // [x, y, width, height]
                            required property int index
                            readonly property real gap: 0.07

                            x: desk.originX + (device.dx + modelData[0] + gap) * desk.unit
                            y: desk.originY + (device.dy + modelData[1] + gap) * desk.unit
                            width: (modelData[2] - 2 * gap) * desk.unit
                            height: (modelData[3] - 2 * gap) * desk.unit
                            radius: led.strip ? width / 2 : 0.17 * desk.unit
                            color: led.shaped ? "transparent" : led.fill
                            border.color: led.edge
                            border.width: led.shaped ? 0 : Math.max(1, desk.unit * 0.05)

                            // soft glow
                            Rectangle {
                                visible: !led.shaped
                                z: -1
                                anchors.fill: parent
                                anchors.margins: -desk.unit * 0.09
                                radius: parent.radius + desk.unit * 0.09
                                color: "transparent"
                                border.color: desk.withAlpha(led.lit, 0.22)
                                border.width: desk.unit * 0.09
                            }

                            Label {
                                anchors.centerIn: parent
                                visible: cap.index === 0 && led.modelData.label !== "" && !led.strip
                                text: led.modelData.label
                                color: led.lit.hslLightness < 0.12 ? theme.textFaint : Qt.lighter(led.lit, 1.3)
                                font.pixelSize: Math.max(8, desk.unit * 0.3)
                            }

                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                            TapHandler {
                                onTapped: backend.simulatePress(device.modelData.id, led.modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }
}
