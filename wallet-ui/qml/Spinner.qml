import QtQuick
import QtQuick.Shapes

// Busy indicator. Under reduced motion it only pulses in opacity (D10).
Item {
    id: root
    property real size: 14
    property color color: Theme.net
    implicitWidth: size
    implicitHeight: size
    Accessible.ignored: true

    Shape {
        id: ring
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.color
            strokeWidth: 2
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.size / 2; centerY: root.size / 2
                radiusX: root.size / 2 - 1.5; radiusY: root.size / 2 - 1.5
                startAngle: 0; sweepAngle: 270
            }
        }
        RotationAnimator on rotation {
            running: root.visible && !Theme.reducedMotion
            from: 0; to: 360; duration: 900; loops: Animation.Infinite
        }
    }
    SequentialAnimation on opacity {
        running: root.visible && Theme.reducedMotion
        loops: Animation.Infinite
        NumberAnimation { to: 0.35; duration: 600 }
        NumberAnimation { to: 1; duration: 600 }
    }
}
