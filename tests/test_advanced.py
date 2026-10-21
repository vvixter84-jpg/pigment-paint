from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtTest import QTest

from app.models import DrawObject
from app.renderer import render_to_image


def _screen(canvas, x: float, y: float) -> QPoint:
    point = canvas.doc_to_screen(QPointF(x, y))
    return QPoint(round(point.x()), round(point.y()))


def test_editing_brush_width_scales_pressure_profile(canvas):
    canvas.settings.tool = "brush"
    canvas.settings.size = 40
    canvas.set_tool("brush")
    p1, p2 = _screen(canvas, 180, 180), _screen(canvas, 520, 340)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p1)
    QTest.mouseMove(canvas, p2, 12)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p2)
    stroke = canvas.document.objects[0]
    assert stroke.width_profile
    before = list(stroke.width_profile)
    canvas.select(stroke.id)
    canvas.update_selected(stroke_width=20.0)
    assert stroke.width_profile
    assert max(stroke.width_profile) < max(before)
    canvas.undo()
    restored = [obj for obj in canvas.document.objects if obj.kind == "stroke"][0]
    assert max(restored.width_profile) > max(stroke.width_profile)


def test_gradient_rendering_is_not_flat(canvas):
    canvas.document.objects.append(
        DrawObject(
            kind="rect",
            x=100,
            y=100,
            w=400,
            h=300,
            fill_mode="linear",
            fill="#FF0000",
            fill2="#0000FF",
            gradient_angle=0,
            stroke_width=0,
        )
    )
    image = render_to_image(canvas.document)
    left = image.pixelColor(120, 250)
    right = image.pixelColor(480, 250)
    assert left.red() > right.red()
    assert right.blue() > left.blue()


def test_insert_image_object_and_roundtrip(canvas, tmp_path: Path):
    image = QImage(240, 160, QImage.Format.Format_ARGB32)
    image.fill(QColor("#A8D7C4"))
    path = tmp_path / "insert.png"
    assert image.save(str(path))
    obj = canvas.insert_image(path)
    assert obj is not None
    assert obj.kind == "image"
    assert obj.image_data
    assert len(canvas.document.objects) == 1
    restored = canvas.document.clone()
    assert restored.objects[0].kind == "image"
    assert restored.objects[0].image_data == obj.image_data
    assert restored.objects[0].w > 100


def test_document_render_hides_invisible_objects(canvas):
    canvas.document.objects.append(
        DrawObject(
            kind="rect",
            x=0,
            y=0,
            w=300,
            h=300,
            fill="#FF00FF",
            fill_mode="solid",
            stroke_width=0,
        )
    )
    visible = render_to_image(canvas.document)
    assert visible.pixelColor(100, 100).name() == "#ff00ff"
    canvas.document.objects[0].visible = False
    hidden = render_to_image(canvas.document)
    assert hidden.pixelColor(100, 100).name() != "#ff00ff"
