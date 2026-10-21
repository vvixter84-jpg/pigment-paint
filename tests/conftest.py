import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

import pytest
from PyQt6.QtWidgets import QApplication

from app.theme import apply_app_theme


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Pigment Tests")
    apply_app_theme(app)
    yield app
    app.processEvents()


@pytest.fixture
def canvas(qapp):
    from app.canvas import Canvas
    from app.models import Document, ToolSettings

    document = Document(width=900, height=650, background="#FFFFFF", name="Test")
    settings = ToolSettings(tool="brush", color="#6C4AB6", size=24)
    widget = Canvas(document, settings)
    widget.resize(1000, 760)
    widget.show()
    qapp.processEvents()
    widget.fit_to_view()
    qapp.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    qapp.processEvents()
