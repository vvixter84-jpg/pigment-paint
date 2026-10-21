from __future__ import annotations

from pathlib import Path


from app.main_window import MainWindow
from app.renderer import render_to_image


def test_main_window_loads_demo_and_inspector_is_sized(qapp):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qapp.processEvents()
    window.load_demo()
    qapp.processEvents()
    assert len(window.document.objects) == 20
    star = next(o for o in window.document.objects if o.name == "Градиентная звезда")
    window.settings.tool = "select"
    window._sync_tool_buttons()
    window.canvas.select(star.id)
    qapp.processEvents()
    content = window.inspector.props_scroll.widget()
    viewport = window.inspector.props_scroll.viewport()
    assert content is not None
    assert content.width() <= viewport.width()
    assert content.height() > viewport.height()
    assert window.inspector.object_list.count() == 20
    window.inspector.show_objects()
    qapp.processEvents()
    assert window.inspector.object_list.currentItem() is not None
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_save_and_reopen_project(qapp, tmp_path: Path):
    window = MainWindow()
    window.resize(1400, 880)
    window.show()
    qapp.processEvents()
    window.load_demo()
    qapp.processEvents()
    target = tmp_path / "demo.pigment"
    assert window._write_project(target)
    assert target.exists()
    assert window.dirty is False
    assert window.current_path == target

    window._load_new_document(
        window.document.__class__(width=800, height=600, name="Пусто")
    )
    assert len(window.document.objects) == 0
    window._open_path(target)
    qapp.processEvents()
    assert len(window.document.objects) == 20
    assert window.current_path == target
    assert window.dirty is False
    assert window.document.name == "demo"
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_export_image_renders_artwork(qapp, tmp_path: Path):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qapp.processEvents()
    window.load_demo()
    qapp.processEvents()
    image = render_to_image(window.document)
    assert image.width() == 1600
    assert image.height() == 1000
    path = tmp_path / "demo.png"
    assert image.save(str(path), "PNG")
    assert path.stat().st_size > 20_000
    # The demo has colour in many pixels, not just the background.
    colors = set()
    for x in range(0, 1600, 80):
        for y in range(0, 1000, 80):
            colors.add(image.pixelColor(x, y).name())
    assert len(colors) > 5
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_tool_selection_and_tool_shortcut(qapp):
    window = MainWindow()
    window.resize(1400, 880)
    window.show()
    qapp.processEvents()
    window.canvas.setFocus()
    qapp.processEvents()
    window._select_tool("pencil")
    assert window.settings.tool == "pencil"
    assert window.tool_buttons["pencil"].isChecked()
    window._select_tool("shape")
    window._choose_shape("star")
    assert window.settings.tool == "shape"
    assert window.settings.shape_kind == "star"
    assert window.tool_buttons["shape"].isChecked()
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_project_json_is_human_readable(qapp):
    window = MainWindow()
    qapp.processEvents()
    raw = window.document.to_json()
    assert '"format": "pigment-document"' in raw
    assert '"objects": []' in raw
    window.deleteLater()
    qapp.processEvents()
