import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One device setting, edited according to the type the daemon reports.
Card {
    id: card

    property var setting
    property var value
    property bool isSet: false
    property bool changed: false
    signal edited(var value)

    // Friendlier names for the settings rivalcfg knows; others keep its label.
    readonly property var known: ({
        "sensitivity": [qsTr("Sensitivity (DPI)"), qsTr("The presets you cycle through with the DPI button")],
        "polling_rate": [qsTr("Polling rate"), qsTr("How many times per second the mouse reports its movement")],
        "sleep_timer": [qsTr("Sleep after"), qsTr("Minutes without use before the mouse goes to sleep")],
        "dim_timer": [qsTr("Dim the LEDs after"), qsTr("Seconds without use before the LEDs dim")],
        "reactive_color": [qsTr("Flash on click"), qsTr("The mouse flashes this color by itself on every click, even when Favilla is not running")],
        "default_lighting": [qsTr("Lighting at power on"), qsTr("Effect the mouse shows by itself before Favilla takes over")]
    })
    readonly property var info: known[setting.name] ?? [setting.label, setting.description]
    // lists coming from Python are array-like objects, not real JS arrays
    readonly property var presets: setting.type === "dpi" && value ? Array.from(value) : []

    title: info[0]
    subtitle: info[1]
    badge: changed ? qsTr("Changed") : (isSet ? "" : qsTr("Not set"))

    function unitFor(v) {
        if (setting.name === "sleep_timer")
            return v === 0 ? qsTr("Never") : qsTr("%1 min").arg(v)
        if (setting.name === "dim_timer")
            return v === 0 ? qsTr("Never") : qsTr("%1 s").arg(v)
        return String(v)
    }
    function choiceLabel(choice) {
        if (setting.name === "polling_rate")
            return qsTr("%1 Hz").arg(choice)
        const words = String(choice).replace(/[-_]/g, " ")
        return words.charAt(0).toUpperCase() + words.slice(1)
    }

    // ---- choice ----
    ChipRow {
        visible: card.setting.type === "choice"
        value: card.isSet ? String(card.value) : ""   // the device value is unknown until set
        options: card.setting.type === "choice"
            ? card.setting.choices.map((c) => ({ value: c, label: card.choiceLabel(c) })) : []
        onPicked: (value) => card.edited(value)
    }

    // ---- range ----
    LabeledSlider {
        visible: card.setting.type === "range"
        label: card.isSet ? "" : qsTr("Default")
        from: card.setting.min ?? 0
        to: card.setting.max ?? 1
        stepSize: card.setting.step ?? 1
        value: Number(card.value ?? 0)
        format: (v) => card.unitFor(Math.round(v))
        onMoved: (v) => card.edited(Math.round(v))
    }

    // ---- dpi presets ----
    Flow {
        visible: card.setting.type === "dpi"
        Layout.fillWidth: true
        spacing: 10

        Repeater {
            model: card.presets.length

            delegate: ColumnLayout {
                required property int index
                spacing: 2

                Label {
                    text: qsTr("Preset %1").arg(parent.index + 1)
                    font.pixelSize: 11
                    color: theme.textFaint
                }
                SpinBox {
                    from: card.setting.min
                    to: card.setting.max
                    stepSize: card.setting.step
                    editable: true
                    value: card.presets[parent.index]
                    onValueModified: {
                        const presets = card.presets.slice()
                        presets[parent.index] = value
                        card.edited(presets)
                    }
                }
            }
        }
    }

    RowLayout {
        visible: card.setting.type === "dpi"
        spacing: 6

        Button {
            text: qsTr("Add preset")
            flat: true
            enabled: card.presets.length > 0 && card.presets.length < (card.setting.max_count ?? 1)
            onClicked: {
                const presets = card.presets.slice()
                presets.push(Math.min(card.setting.max, presets[presets.length - 1] * 2))
                card.edited(presets)
            }
        }
        Button {
            text: qsTr("Remove the last one")
            flat: true
            enabled: card.presets.length > 1
            onClicked: card.edited(card.presets.slice(0, -1))
        }
    }

    // ---- color or off ----
    RowLayout {
        visible: card.setting.type === "color_or_off"
        Layout.fillWidth: true
        spacing: 14

        Switch {
            id: enabled
            checked: card.value !== undefined && card.value !== null && String(card.value).toLowerCase() !== "off"
            text: checked ? qsTr("On") : qsTr("Off")
            onToggled: card.edited(checked ? "#ffffff" : "off")
        }
        ColorSwatch {
            visible: enabled.checked
            label: ""
            color: enabled.checked ? String(card.value) : "#ffffff"
            onPicked: (color) => card.edited(color)
        }
    }
}
