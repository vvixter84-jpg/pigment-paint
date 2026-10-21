"""Entry point for Pigment Paint."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication

from app.icons import app_icon
from app.main_window import MainWindow
from app.theme import apply_app_theme


def _schedule_self_check(app: QApplication, window: MainWindow) -> None:
    """Open the demo, render the real UI and exit — used to verify frozen builds."""

    def capture() -> None:
        window.toast.hide()
        app.processEvents()
        target = Path(
            os.environ.get(
                "PIGMENT_SMOKE_OUT",
                str(Path(tempfile.gettempdir()) / "pigment-smoke.png"),
            )
        )
        saved = window.grab().save(str(target), "PNG")
        app.exit(0 if saved else 2)

    def prepare() -> None:
        window.load_demo()
        window.toast.hide()
        QTimer.singleShot(500, capture)

    QTimer.singleShot(500, prepare)


def main() -> int:
    smoke_test = "--smoke-test" in sys.argv
    open_demo = "--demo" in sys.argv
    qt_args = [
        arg for arg in sys.argv if arg not in {"--smoke-test", "--demo"}
    ]

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(qt_args)
    app.setApplicationName("Pigment")
    app.setApplicationDisplayName("Pigment Paint")
    app.setOrganizationName("Pigment Studio")
    app.setWindowIcon(app_icon())
    apply_app_theme(app)

    window = MainWindow()
    window.show()
    if smoke_test:
        _schedule_self_check(app, window)
    elif open_demo:
        QTimer.singleShot(0, window.load_demo)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
