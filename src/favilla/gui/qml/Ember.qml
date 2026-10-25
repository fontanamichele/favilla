import QtQuick
import QtQuick.Shapes

// The Favilla logo: a four-pointed spark.
Item {
    id: ember

    property bool dim: false

    implicitWidth: 32
    implicitHeight: 32
    opacity: dim ? 0.55 : 1.0

    Shape {
        width: 32
        height: 32
        anchors.centerIn: parent
        scale: Math.min(ember.width, ember.height) / 32
        antialiasing: true
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeWidth: -1
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: 16; centerY: 16; centerRadius: 16
                focalX: 16; focalY: 16
                GradientStop { position: 0.0; color: "#fff4d6" }
                GradientStop { position: 0.28; color: "#ffb347" }
                GradientStop { position: 0.75; color: "#ff5a1f" }
                GradientStop { position: 1.0; color: "#e8380d" }
            }
            PathSvg {
                path: "M16 0 C17.1 9.6 22.4 14.9 32 16 C22.4 17.1 17.1 22.4 16 32 "
                    + "C14.9 22.4 9.6 17.1 0 16 C9.6 14.9 14.9 9.6 16 0 Z"
            }
        }
    }
}
