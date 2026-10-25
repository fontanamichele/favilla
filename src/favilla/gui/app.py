"""Entry point of the Favilla interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .. import APP_ID, __version__

HERE = Path(__file__).resolve().parent

THEME = {
    "bg": "#0e0f12",
    "sidebar": "#131418",
    "surface": "#17181d",
    "surfaceHi": "#1f2027",
    "border": "#26272f",
    "text": "#ececf1",
    "textDim": "#9a9ba6",
    "textFaint": "#62636d",
    "accent": "#ff5a1f",
    "accentSoft": "#2c1810",
    "good": "#3ddc84",
    "warn": "#ffb020",
    "bad": "#ff4d5e",
    "radius": 14,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="favilla", description="Favilla: lighting and settings "
                                     "for SteelSeries devices.")
    parser.add_argument("--version", action="version", version=f"favilla {__version__}")
    parser.add_argument("--page", default="lighting", help=argparse.SUPPRESS)       # for screenshots
    parser.add_argument("--screenshot", metavar="PNG", help=argparse.SUPPRESS)
    parser.add_argument("--size", metavar="WxH", help=argparse.SUPPRESS)
    args, qt_args = parser.parse_known_args(argv)

    from PySide6.QtCore import QLocale, QTimer, QTranslator, QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    from .backend import Backend

    QQuickStyle.setStyle("Material")
    app = QGuiApplication([sys.argv[0], *qt_args])
    app.setApplicationName("Favilla")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon(str(HERE / "favilla.svg")))

    translator = QTranslator(app)
    if translator.load(QLocale(), "favilla", "_", str(HERE / "i18n")):
        app.installTranslator(translator)

    backend = Backend(app)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("theme", THEME)
    engine.setInitialProperties({"page": args.page})
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1

    window = engine.rootObjects()[0]
    if args.size:
        width, height = (int(v) for v in args.size.lower().split("x"))
        window.resize(width, height)
    if args.screenshot:
        def grab():
            window.grabWindow().save(args.screenshot)
            app.quit()
        QTimer.singleShot(2500, grab)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
