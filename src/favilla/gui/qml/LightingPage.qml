import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: page

    readonly property var lighting: backend.lighting
    readonly property var bgSettings: lighting.background ?? ({})
    readonly property var rxSettings: lighting.reactive ?? ({})
    readonly property int margin: 32

    contentWidth: availableWidth
    clip: true

    ColumnLayout {
        width: page.availableWidth
        spacing: 18

        PageHeader {
            Layout.fillWidth: true
            Layout.topMargin: 30
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            title: qsTr("Lighting")
            subtitle: qsTr("One effect across your keyboard and mouse. Click a key to preview it.")
        }

        Card {
            Layout.fillWidth: true
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin

            DeskPreview {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(220, Math.min(330, width * 0.3))
            }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            columns: page.availableWidth > 1050 ? 2 : 1
            columnSpacing: 18
            rowSpacing: 18

            Card {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                title: qsTr("Background")
                subtitle: qsTr("What the LEDs show when nothing is happening")

                ChipRow {
                    value: page.bgSettings.effect ?? ""
                    options: [
                        { value: "static", label: qsTr("Static") },
                        { value: "breathing", label: qsTr("Breathing") },
                        { value: "spectrum", label: qsTr("Spectrum") },
                        { value: "off", label: qsTr("Off") }
                    ]
                    onPicked: (value) => backend.setLighting("background.effect", value)
                }

                ColorSwatch {
                    visible: page.bgSettings.effect === "static" || page.bgSettings.effect === "breathing"
                    color: page.bgSettings.color ?? "#000000"
                    onPicked: (color) => backend.setLighting("background.color", color)
                }

                LabeledSlider {
                    visible: page.bgSettings.effect === "breathing"
                    label: qsTr("Breath length")
                    from: 0.5; to: 12; stepSize: 0.1
                    value: page.bgSettings.period ?? 4
                    format: (v) => qsTr("%1 s").arg(v.toFixed(1))
                    onMoved: (v) => backend.setLighting("background.period", v)
                }

                LabeledSlider {
                    visible: page.bgSettings.effect === "spectrum"
                    label: qsTr("Speed")
                    from: 0.02; to: 1.5; stepSize: 0.01
                    value: page.bgSettings.speed ?? 0.2
                    format: (v) => qsTr("%1 cycles/s").arg(v.toFixed(2))
                    onMoved: (v) => backend.setLighting("background.speed", v)
                }

                LabeledSlider {
                    visible: page.bgSettings.effect === "spectrum"
                    label: qsTr("Rainbow width")
                    hint: qsTr("How much the color changes from one key to the next")
                    from: 0.0; to: 0.15; stepSize: 0.005
                    value: page.bgSettings.spread ?? 0.03
                    format: (v) => (v * 100).toFixed(1) + "%"
                    onMoved: (v) => backend.setLighting("background.spread", v)
                }
            }

            Card {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                title: qsTr("On key press")
                subtitle: qsTr("How the LEDs react to keys and mouse clicks")

                ChipRow {
                    value: page.rxSettings.effect ?? ""
                    options: [
                        { value: "ripple", label: qsTr("Wave") },
                        { value: "keyfade", label: qsTr("Key glow") },
                        { value: "none", label: qsTr("Nothing") }
                    ]
                    onPicked: (value) => backend.setLighting("reactive.effect", value)
                }

                ColorSwatch {
                    visible: page.rxSettings.effect !== "none"
                    color: page.rxSettings.color ?? "#ffffff"
                    onPicked: (color) => backend.setLighting("reactive.color", color)
                }

                LabeledSlider {
                    visible: page.rxSettings.effect === "ripple"
                    label: qsTr("Speed")
                    from: 4; to: 40; stepSize: 0.5
                    value: page.rxSettings.speed ?? 14
                    format: (v) => qsTr("%1 keys/s").arg(v.toFixed(1))
                    onMoved: (v) => backend.setLighting("reactive.speed", v)
                }

                LabeledSlider {
                    visible: page.rxSettings.effect === "ripple"
                    label: qsTr("Thickness")
                    from: 0.4; to: 3; stepSize: 0.05
                    value: page.rxSettings.width ?? 1.1
                    format: (v) => qsTr("%1 keys").arg(v.toFixed(2))
                    onMoved: (v) => backend.setLighting("reactive.width", v)
                }

                LabeledSlider {
                    visible: page.rxSettings.effect !== "none"
                    label: qsTr("Duration")
                    from: 0.2; to: 3; stepSize: 0.05
                    value: page.rxSettings.life ?? 0.9
                    format: (v) => qsTr("%1 s").arg(v.toFixed(2))
                    onMoved: (v) => backend.setLighting("reactive.life", v)
                }

                LabeledSlider {
                    visible: page.rxSettings.effect === "ripple"
                    label: qsTr("Duration on the other device")
                    hint: qsTr("The wave fades more slowly when it travels from the keyboard to the mouse and back, otherwise it would vanish before arriving")
                    from: 0.2; to: 5; stepSize: 0.05
                    value: page.rxSettings.life_cross ?? 1.8
                    format: (v) => qsTr("%1 s").arg(v.toFixed(2))
                    onMoved: (v) => backend.setLighting("reactive.life_cross", v)
                }
            }
        }

        Card {
            Layout.fillWidth: true
            Layout.leftMargin: page.margin
            Layout.rightMargin: page.margin
            title: qsTr("Desk")

            LabeledSlider {
                label: qsTr("Brightness")
                from: 0; to: 1; stepSize: 0.01
                value: page.lighting.brightness ?? 1
                format: (v) => Math.round(v * 100) + "%"
                onMoved: (v) => backend.setLighting("brightness", v)
            }

            LabeledSlider {
                label: qsTr("Gap between keyboard and mouse")
                hint: qsTr("Tells the effects where your mouse is, so a wave reaches it at the right moment")
                from: 17; to: 32; stepSize: 0.25
                value: backend.desk.mouse_x ?? 19
                format: (v) => qsTr("%1 cm").arg(((v - 16.8) * 1.905).toFixed(0))
                onMoved: (v) => backend.setDesk("mouse_x", v)
            }
        }

        Item { Layout.preferredHeight: 20 }
    }
}
