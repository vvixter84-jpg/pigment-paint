from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QTest

from app.canvas import Canvas


def _screen(canvas: Canvas, x: float, y: float) -> QPoint:
    point = canvas.doc_to_screen(QPointF(x, y))
    return QPoint(round(point.x()), round(point.y()))


def _drag(canvas: Canvas, start: tuple[float, float], end: tuple[float, float]) -> None:
    p1, p2 = _screen(canvas, *start), _screen(canvas, *end)
    QTest.mousePress(
        canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p1
    )
    QTest.mouseMove(canvas, p2, 12)
    QTest.mouseRelease(
        canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p2
    )


def test_brush_stroke_undo_redo(canvas):
    canvas.settings.tool = "brush"
    canvas.settings.color = "#6C4AB6"
    canvas.settings.size = 28
    canvas.set_tool("brush")
    p1, p2 = _screen(canvas, 200, 200), _screen(canvas, 500, 350)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p1)
    QTest.mouseMove(canvas, QPoint((p1.x() + p2.x()) // 2, (p1.y() + p2.y()) // 2), 12)
    QTest.mouseMove(canvas, p2, 12)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p2)
    assert len(canvas.document.objects) == 1
    stroke = canvas.document.objects[0]
    assert stroke.kind == "stroke"
    assert stroke.tool == "brush"
    assert len(stroke.points) >= 3
    assert canvas.can_undo()

    canvas.undo()
    assert len(canvas.document.objects) == 0
    assert canvas.can_redo()
    canvas.redo()
    assert len(canvas.document.objects) == 1
    assert canvas.document.objects[0].kind == "stroke"


def test_pencil_spray_and_eraser_create_objects(canvas):
    for tool in ("pencil", "spray", "eraser"):
        canvas.settings.tool = tool
        canvas.settings.size = 30
        canvas.set_tool(tool)
        _drag(canvas, (100, 100), (220, 180))
    assert len(canvas.document.objects) == 3
    tools = {obj.tool for obj in canvas.document.objects}
    assert tools == {"pencil", "spray", "eraser"}
    spray = next(obj for obj in canvas.document.objects if obj.tool == "spray")
    assert len(spray.spray_dots) > 10


def test_create_shape_select_move_and_resize(canvas):
    canvas.settings.tool = "shape"
    canvas.settings.shape_kind = "rect"
    canvas.settings.fill_mode = "linear"
    canvas.settings.color = "#FFD8A8"
    canvas.settings.fill2 = "#EFB8C8"
    canvas.set_tool("shape")
    _drag(canvas, (250, 200), (550, 400))
    assert len(canvas.document.objects) == 1
    obj = canvas.document.objects[0]
    assert obj.kind == "rect"
    assert obj.fill_mode == "linear"
    assert obj.fill == "#FFD8A8"
    start_x, start_y = obj.x, obj.y

    canvas.set_tool("select")
    canvas.select(obj.id)
    _drag(canvas, (400, 300), (440, 330))
    moved = canvas.selected_object()
    assert moved is not None
    assert moved.x > start_x + 20
    assert moved.y > start_y + 15

    handles = canvas._handle_positions()
    se = handles["se"]
    start_w, start_h = moved.w, moved.h
    QTest.mousePress(
        canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(round(se.x()), round(se.y())),
    )
    QTest.mouseMove(
        canvas,
        QPoint(round(se.x() + 42), round(se.y() + 28)),
        10,
    )
    QTest.mouseRelease(
        canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(round(se.x() + 42), round(se.y() + 28)),
    )
    assert moved.w > start_w
    assert moved.h > start_h


def test_star_and_polygon_creation(canvas):
    canvas.settings.tool = "shape"
    canvas.settings.shape_kind = "star"
    canvas.set_tool("shape")
    _drag(canvas, (100, 100), (400, 400))
    assert canvas.document.objects[0].kind == "star"
    assert canvas.document.objects[0].star_points == 5

    canvas.set_shape_kind("polygon")
    for x, y in ((500, 500), (620, 460), (700, 580)):
        QTest.mouseClick(
            canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            _screen(canvas, x, y),
        )
    assert canvas._polygon_points
    canvas._finish_polygon()
    polygons = [obj for obj in canvas.document.objects if obj.kind == "polygon"]
    assert len(polygons) == 1
    assert len(polygons[0].points) == 3


def test_text_creation_and_font_properties(canvas):
    canvas.settings.tool = "text"
    canvas.settings.font_family = "Caveat"
    canvas.settings.font_size = 64
    canvas.set_tool("text")
    canvas._open_text_editor(None, QPointF(160, 200))
    canvas._text_editor.setPlainText("Привет, Pigment")
    canvas._commit_text_editor()
    texts = [obj for obj in canvas.document.objects if obj.kind == "text"]
    assert len(texts) == 1
    text = texts[0]
    assert text.text == "Привет, Pigment"
    assert text.font_family == "Caveat"
    assert text.font_size == 64
    assert text.h >= 64
    assert text.w > 100
    canvas.undo()
    assert not [obj for obj in canvas.document.objects if obj.kind == "text"]


def test_update_selected_properties(canvas):
    canvas.settings.tool = "shape"
    canvas.settings.shape_kind = "ellipse"
    canvas.set_tool("shape")
    _drag(canvas, (200, 200), (500, 400))
    obj = canvas.document.objects[0]
    canvas.select(obj.id)
    canvas.update_selected(fill="#123456", fill_mode="radial", stroke_width=9)
    changed = canvas.selected_object()
    assert changed is not None
    assert changed.fill == "#123456"
    assert changed.fill_mode == "radial"
    assert changed.stroke_width == 9
    canvas.set_selected_bounds(x=100, y=120, w=300, h=250)
    assert changed.bounds() == (100, 120, 300, 250)
    canvas.undo()
    restored = canvas.selected_object()
    assert restored is not None
    assert round(restored.w) == round(obj.w)


def test_zoom_and_fit(canvas):
    initial = canvas.zoom
    canvas.zoom_in()
    assert canvas.zoom > initial
    canvas.zoom_out()
    assert abs(canvas.zoom - initial) < 1e-6
    canvas.fit_to_view()
    assert 0.05 <= canvas.zoom <= 2.5
