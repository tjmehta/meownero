import QtQuick
import QtQuick.Shapes

// Stroke icons from the prototype (24 px grid). Decorative: hidden from assistive technology.
Item {
    id: root
    property string name: ""
    property color color: Theme.fg
    property real size: 16
    property real viewBox: name === "coin" ? 32 : 24
    implicitWidth: size
    implicitHeight: size
    Accessible.ignored: true

    readonly property var paths: ({
        home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
        list: "M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01",
        up: "M12 19V5M5 12l7-7 7 7",
        down: "M12 5v14M19 12l-7 7-7-7",
        block: "M12 2 3 7v10l9 5 9-5V7zM3 7l9 5 9-5M12 12v10",
        node: "M4.5 4h15a1.5 1.5 0 0 1 1.5 1.5v4a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 9.5v-4A1.5 1.5 0 0 1 4.5 4zM4.5 13h15a1.5 1.5 0 0 1 1.5 1.5v4a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5v-4A1.5 1.5 0 0 1 4.5 13zM7 7.5h.01M7 16.5h.01",
        key: "M4 15a4 4 0 1 0 8 0a4 4 0 1 0-8 0zM11 12l9-9M17 6l3 3M15 8l2 2",
        copy: "M11 9h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2zM5 15V5a2 2 0 0 1 2-2h8",
        check: "M20 6 9 17l-5-5",
        alert: "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
        info: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0zM12 16v-4M12 8h.01",
        clock: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0zM12 7v5l3 2",
        lock: "M6 11h12a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2zM8 11V7a4 4 0 0 1 8 0v4",
        flask: "M9 3h6M10 3v6L4.5 18.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3M7 15h10",
        x: "M18 6 6 18M6 6l12 12",
        gear: "M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
        eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0z",
        refresh: "M21 12a9 9 0 1 1-2.6-6.4L21 8M21 3v5h-5",
        coin: "M1.8 16a14.2 14.2 0 1 0 28.4 0a14.2 14.2 0 1 0-28.4 0zM9.6 21.8V10.6l4.1 3.3h4.6l4.1-3.3v11.2M12.6 18.1h2M17.4 18.1h2M15.2 20.6h1.6"
    })

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        transform: Scale { xScale: root.width / root.viewBox; yScale: root.height / root.viewBox }
        ShapePath {
            strokeColor: root.color
            strokeWidth: root.name === "coin" ? 1.6 : 1.8
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.paths[root.name] || "" }
        }
    }
}
