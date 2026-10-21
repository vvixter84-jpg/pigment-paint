"""Regenerate screenshots and the openable demo project.

Run from the repository root:
    .venv\\Scripts\\python.exe scripts\\make_assets.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.demo import build_demo_document  # noqa: E402
from app.dialogs import NewDocumentDialog  # noqa: E402
from app.main_window import MainWindow  # noqa: E402
from app.renderer import render_to_image  # noqa: E402
from app.theme import apply_app_theme  # noqa: E402


def main() -> None:
    screenshots = ROOT / "assets" / "screenshots"
    examples = ROOT / "assets" / "examples"
    screenshots.mkdir(parents=True, exist_ok=True)
    examples.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    app.setApplicationName("Pigment")
    apply_app_theme(app)

    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    app.processEvents()
    window.load_demo()
    app.processEvents()
    if hasattr(window, "toast"):
        window.toast.hide()

    artwork = render_to_image(window.document)
    artwork.save(str(screenshots / "demo-artwork.png"), "PNG")

    star = next(obj for obj in window.document.objects if obj.name == "Градиентная звезда")
    window.settings.tool = "select"
    window._sync_tool_buttons()
    window.canvas.select(star.id)
    window.inspector.props_scroll.verticalScrollBar().setValue(0)
    app.processEvents()
    window.grab().save(str(screenshots / "app.png"), "PNG")

    window.inspector.show_objects()
    app.processEvents()
    window.grab().save(str(screenshots / "objects.png"), "PNG")

    window.inspector._show_tab(0)
    dialog = NewDocumentDialog(window)
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(screenshots / "new-document.png"), "PNG")
    dialog.close()

    demo = build_demo_document()
    demo.name = "pigment-demo"
    (examples / "pigment-demo.pigment").write_text(demo.to_json(), encoding="utf-8")

    print(f"Screenshots: {screenshots}")
    print(f"Demo: {examples / 'pigment-demo.pigment'}")


if __name__ == "__main__":
    main()
