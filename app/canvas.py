"""Interactive artboard: tools, selection, shape editing, text and history."""

from __future__ import annotations

import base64
import copy
import math
import random
import time
from dataclasses import fields
from pathlib import Path

from PyQt6.QtCore import (
    QBuffer,
    QByteArray,
    QEvent,
    QIODevice,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import QFileDialog, QMenu, QTextEdit, QWidget

from .icons import make_pixmap
from .models import (
    Document,
    DrawObject,
    ToolSettings,
    clamp,
)
from .renderer import paint_object, qcolor, render_document, render_to_image
from .theme import (
    BG,
    OUTLINE,
    OUTLINE_STRONG,
    PRIMARY,
    SURFACE_1,
    TEXT,
    TEXT_MUTED,
    ui_font_family,
)

DRAW_TOOLS = {"pencil", "brush", "pen", "spray", "eraser"}
SHAPE_TOOLS = {"line", "shape"}
SHAPE_KINDS = {
    "line": "Линия",
    "rect": "Прямоугольник",
    "rounded_rect": "Скруглённый прямоугольник",
    "ellipse": "Эллипс",
    "star": "Звезда",
    "polygon": "Многоугольник",
}
TOOL_HINTS = {
    "select": "Выделение · тяните объект, чтобы переместить",
    "hand": "Рука · перетаскивайте холст",
    "pencil": "Карандаш",
    "brush": "Кисть",
    "pen": "Перо",
    "spray": "Баллончик",
    "eraser": "Ластик",
    "fill": "Заливка · клик по фигуре",
    "picker": "Пипетка · возьмите цвет с холста",
    "text": "Текст · кликните на холсте",
    "shape": "Фигура",
}

HANDLE_CURSORS = {
    "nw": Qt.CursorShape.SizeFDiagCursor,
    "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor,
    "sw": Qt.CursorShape.SizeBDiagCursor,
    "n": Qt.CursorShape.SizeVerCursor,
    "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor,
    "w": Qt.CursorShape.SizeHorCursor,
    "p1": Qt.CursorShape.CrossCursor,
    "p2": Qt.CursorShape.CrossCursor,
}


class Canvas(QWidget):
    documentChanged = pyqtSignal()
    selectionChanged = pyqtSignal(object)
    geometryChanged = pyqtSignal()
    historyChanged = pyqtSignal(bool, bool)
    zoomChanged = pyqtSignal(float)
    cursorMoved = pyqtSignal(float, float)
    colorPicked = pyqtSignal(str)
    toolChanged = pyqtSignal(str)
    statusMessage = pyqtSignal(str)

    def __init__(self, document: Document, settings: ToolSettings, parent=None):
        super().__init__(parent)
        self.setObjectName("Canvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMinimumSize(320, 240)
        self.document = document
        self.settings = settings
        self.selected_id: str | None = None
        self.zoom = 0.7
        self.pan = QPointF(0, 0)
        self._initial_view_done = False
        self._mouse = QPointF(-1, -1)
        self._hover_doc = QPointF(-1, -1)
        self._mouse_inside = False
        self._space_down = False

        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self._last_undo_key: object | None = None
        self._last_undo_time = 0.0

        self._drag_mode: str | None = None
        self._drag_handle: str | None = None
        self._drag_start = QPointF()
        self._drag_original: DrawObject | None = None
        self._drag_changed = False
        self._undo_before_drag = 0
        self._panning = False
        self._pan_start = QPointF()
        self._pan_origin = QPointF()

        self._stroke: DrawObject | None = None
        self._last_point = QPointF()
        self._last_stroke_time = 0.0
        self._last_width = 0.0

        self._draft: DrawObject | None = None
        self._draft_start = QPointF()
        self._polygon_points: list[QPointF] = []

        self._text_editor: QTextEdit | None = None
        self._text_target: DrawObject | None = None
        self._text_original_visible = True
        self._text_is_new = False
        self._text_doc_pos = QPointF()
        self._text_closing = False

        self._hud_icon_cache: dict[str, QPixmap] = {}
        self._undo_limit = 80

    # ------------------------------------------------------------------ document
    def set_document(self, document: Document, fit: bool = True) -> None:
        self.cancel_pending_edits()
        self.document = document
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.selected_id = None
        self._draft = None
        self._stroke = None
        self._polygon_points.clear()
        self._last_undo_key = None
        self.historyChanged.emit(False, False)
        self.selectionChanged.emit(None)
        self._initial_view_done = False
        if fit:
            if self.isVisible() and self.width() > 50:
                QTimer.singleShot(0, self.fit_to_view)
            else:
                self.zoom = 0.7
                self.pan = QPointF(0, 0)
        self.update()

    def set_tool(self, tool: str) -> None:
        if tool == self.settings.tool:
            return
        self.cancel_pending_edits()
        if self._polygon_points:
            self._polygon_points.clear()
        self._stroke = None
        self._draft = None
        self.settings.tool = tool
        if self.selected_id is not None:
            self.select(None)
        self.update()
        self._update_cursor(self._mouse)
        self.toolChanged.emit(tool)
        self.statusMessage.emit(self._tool_status())

    def set_shape_kind(self, kind: str) -> None:
        if kind not in SHAPE_KINDS:
            return
        was_shape = self.settings.tool == "shape"
        self.settings.tool = "shape"
        self.settings.shape_kind = kind
        if not was_shape and self.selected_id is not None:
            self.select(None)
        if kind == "polygon":
            self._polygon_points.clear()
        self.update()
        self._update_cursor(self._mouse)
        self.toolChanged.emit("shape")
        self.statusMessage.emit(self._tool_status())

    def selected_object(self) -> DrawObject | None:
        return self.document.object_by_id(self.selected_id)

    def select(self, object_id: str | None, *, emit: bool = True) -> None:
        if self._text_editor is not None and object_id != self.selected_id:
            self._commit_text_editor()
        if object_id == self.selected_id:
            if emit:
                self.selectionChanged.emit(self.selected_object())
            return
        self.selected_id = object_id
        obj = self.selected_object()
        if obj is None:
            self.selected_id = None
        if emit:
            self.selectionChanged.emit(obj)
            self.update()

    def clear_selection(self) -> None:
        self.select(None)

    # ------------------------------------------------------------------- history
    def push_undo(self, coalesce_key: object | None = None) -> bool:
        now = time.perf_counter()
        if (
            coalesce_key is not None
            and self._last_undo_key == coalesce_key
            and now - self._last_undo_time < 0.8
        ):
            self._last_undo_time = now
            return False
        self.undo_stack.append(self.document.as_dict())
        if len(self.undo_stack) > self._undo_limit:
            del self.undo_stack[0]
        self.redo_stack.clear()
        self._last_undo_key = coalesce_key
        self._last_undo_time = now
        self.historyChanged.emit(True, False)
        return True

    def undo(self) -> None:
        self.cancel_pending_edits()
        if not self.undo_stack:
            return
        self.redo_stack.append(self.document.as_dict())
        snapshot = self.undo_stack.pop()
        self._restore_document(snapshot)
        self.historyChanged.emit(bool(self.undo_stack), bool(self.redo_stack))
        self.documentChanged.emit()

    def redo(self) -> None:
        self.cancel_pending_edits()
        if not self.redo_stack:
            return
        self.undo_stack.append(self.document.as_dict())
        snapshot = self.redo_stack.pop()
        self._restore_document(snapshot)
        self.historyChanged.emit(bool(self.undo_stack), bool(self.redo_stack))
        self.documentChanged.emit()

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def _restore_document(self, snapshot: dict) -> None:
        selected = self.selected_id
        self.document = Document.from_dict(snapshot)
        self.selected_id = selected if self.document.object_by_id(selected) else None
        self._last_undo_key = None
        self.selectionChanged.emit(self.selected_object())
        self.geometryChanged.emit()
        self.update()

    # ----------------------------------------------------------------- properties
    def update_selected(self, *, record: bool = True, **values) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        valid = {f.name for f in fields(DrawObject)}
        clean = {key: value for key, value in values.items() if key in valid}
        if not clean:
            return
        if record:
            self.push_undo(coalesce_key=("property", obj.id, tuple(sorted(clean.keys()))))
        old_width = obj.stroke_width
        for key, value in clean.items():
            setattr(obj, key, value)
        if obj.kind == "stroke" and "stroke_width" in clean and old_width > 0:
            factor = obj.stroke_width / old_width
            if obj.width_profile:
                obj.width_profile = [max(0.4, width * factor) for width in obj.width_profile]
            if obj.tool == "spray" and obj.spray_dots:
                for dot in obj.spray_dots:
                    dot[2] = max(0.25, dot[2] * factor)
        if any(key in clean for key in ("text", "font_size", "font_family", "bold", "italic")):
            self._fit_text_height(obj)
        obj.sanitize()
        self.geometryChanged.emit()
        self.documentChanged.emit()
        self.update()

    def set_selected_bounds(
        self,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
    ) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        ox, oy, ow, oh = obj.bounds()
        nx = float(x) if x is not None else ox
        ny = float(y) if y is not None else oy
        nw = float(w) if w is not None else ow
        nh = float(h) if h is not None else oh
        if abs(nx - ox) < 1e-6 and abs(ny - oy) < 1e-6 and abs(nw - ow) < 1e-6 and abs(nh - oh) < 1e-6:
            return
        self.push_undo(coalesce_key=("bounds", obj.id))
        obj.scale_to(nx, ny, max(1.0, nw), max(1.0, nh), (ox, oy, ow, oh))
        obj.sanitize()
        self.geometryChanged.emit()
        self.documentChanged.emit()
        self.update()

    def set_document_background(self, color: str) -> None:
        if QColor(color).isValid() and self.document.background.upper() != color.upper():
            self.push_undo(coalesce_key=("background",))
            self.document.background = color
            self.documentChanged.emit()
            self.update()

    def reorder_selected_step(self, direction: int) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        index = self.document.index_of(obj.id)
        target = index + direction
        if 0 <= target < len(self.document.objects):
            self.push_undo()
            self.document.reorder(obj.id, direction)
            self.documentChanged.emit()
            self.update()

    def toggle_selected_visibility(self) -> None:
        obj = self.selected_object()
        if obj is not None:
            self.update_selected(visible=not obj.visible)

    def delete_selected(self) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        self.push_undo()
        self.document.remove(obj.id)
        self.selected_id = None
        self.selectionChanged.emit(None)
        self.documentChanged.emit()
        self.update()

    def duplicate_selected(self) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        self.push_undo()
        copied = self.document.duplicate(obj.id)
        if copied is not None:
            self.selected_id = copied.id
            self.selectionChanged.emit(copied)
            self.documentChanged.emit()
            self.update()

    def raise_selected(self) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        index = self.document.index_of(obj.id)
        if 0 <= index < len(self.document.objects) - 1:
            self.push_undo()
            self.document.raise_to_top(obj.id)
            self.documentChanged.emit()
            self.update()

    def lower_selected(self) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        index = self.document.index_of(obj.id)
        if index > 0:
            self.push_undo()
            self.document.send_to_back(obj.id)
            self.documentChanged.emit()
            self.update()

    def nudge_selected(self, dx: float, dy: float) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        self.push_undo(coalesce_key=("nudge", obj.id))
        obj.move(dx, dy)
        self.geometryChanged.emit()
        self.documentChanged.emit()
        self.update()

    # -------------------------------------------------------------------- view
    def _page_rect_screen(self) -> QRectF:
        w = self.document.width * self.zoom
        h = self.document.height * self.zoom
        return QRectF(
            (self.width() - w) / 2.0 + self.pan.x(),
            (self.height() - h) / 2.0 + self.pan.y(),
            w,
            h,
        )

    def _origin(self) -> QPointF:
        return self._page_rect_screen().topLeft()

    def screen_to_doc(self, point: QPointF) -> QPointF:
        origin = self._origin()
        return QPointF(
            (point.x() - origin.x()) / self.zoom,
            (point.y() - origin.y()) / self.zoom,
        )

    def doc_to_screen(self, point: QPointF) -> QPointF:
        origin = self._origin()
        return QPointF(origin.x() + point.x() * self.zoom, origin.y() + point.y() * self.zoom)

    def _clamp_doc(self, point: QPointF) -> QPointF:
        return QPointF(
            clamp(point.x(), 0.0, self.document.width),
            clamp(point.y(), 0.0, self.document.height),
        )

    def fit_to_view(self) -> None:
        if self.width() < 20 or self.height() < 20:
            return
        margin_x = 104 if self.width() > 700 else 56
        margin_y = 104 if self.height() > 600 else 56
        available_w = max(80, self.width() - margin_x)
        available_h = max(80, self.height() - margin_y)
        zoom = min(available_w / self.document.width, available_h / self.document.height)
        self.zoom = clamp(zoom, 0.05, 2.5)
        self.pan = QPointF(0, 0)
        self._initial_view_done = True
        self.zoomChanged.emit(self.zoom)
        self._position_text_editor()
        self.update()

    def set_zoom(self, zoom: float, anchor: QPointF | None = None) -> None:
        old_zoom = self.zoom
        new_zoom = clamp(zoom, 0.05, 8.0)
        if abs(new_zoom - old_zoom) < 1e-5:
            return
        if anchor is None:
            anchor = QPointF(self.width() / 2.0, self.height() / 2.0)
        doc_anchor = self.screen_to_doc(anchor)
        self.zoom = new_zoom
        page_w = self.document.width * self.zoom
        page_h = self.document.height * self.zoom
        self.pan = QPointF(
            anchor.x() - doc_anchor.x() * self.zoom - (self.width() - page_w) / 2.0,
            anchor.y() - doc_anchor.y() * self.zoom - (self.height() - page_h) / 2.0,
        )
        self.zoomChanged.emit(self.zoom)
        self._position_text_editor()
        self.update()

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom * 1.2)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom / 1.2)

    def actual_size(self) -> None:
        self.set_zoom(1.0)

    # ------------------------------------------------------------------- rendering
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(BG))
        self._draw_workspace(painter)
        page = self._page_rect_screen()
        self._draw_page_shadow(painter, page)

        painter.save()
        painter.setClipRect(page.adjusted(-1, -1, 1, 1))
        painter.translate(page.topLeft())
        painter.scale(self.zoom, self.zoom)
        painter.fillRect(
            QRectF(0, 0, self.document.width, self.document.height),
            qcolor(self.document.background, "#FFFFFF"),
        )
        render_document(painter, self.document, draw_background=False)
        if self.settings.show_grid:
            self._draw_grid(painter)
        if self._draft is not None:
            paint_object(painter, self._draft, self.document.background)
        if self._polygon_points:
            self._draw_polygon_preview(painter)
        painter.restore()

        painter.setPen(QPen(QColor(OUTLINE_STRONG), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(page.adjusted(0, 0, -1, -1))
        self._draw_selection(painter)
        self._draw_hud(painter)
        self._draw_cursor(painter)
        painter.end()

    def _draw_workspace(self, painter: QPainter) -> None:
        step = 26
        points = [
            QPointF(x, y)
            for y in range(12, self.height(), step)
            for x in range(12, self.width(), step)
        ]
        if points:
            painter.setPen(QPen(QColor(255, 255, 255, 11), 1.2))
            painter.drawPoints(QPolygonF(points))

    def _draw_page_shadow(self, painter: QPainter, page: QRectF) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        for offset, alpha in ((18, 16), (12, 30), (7, 48)):
            rect = page.translated(0, offset * 0.55).adjusted(-offset, -offset, offset, offset)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(rect, 5, 5)
        painter.setBrush(QColor(0, 0, 0, 90))
        painter.drawRect(page.translated(0, 7).adjusted(2, 2, -2, -2))

    def _draw_grid(self, painter: QPainter) -> None:
        step = 50
        minor = QPen(QColor(20, 20, 25, 20), 0.8)
        major = QPen(QColor(20, 20, 25, 42), 1.0)
        painter.setPen(minor)
        for x in range(step, self.document.width, step):
            painter.drawLine(QPointF(x, 0), QPointF(x, self.document.height))
        for y in range(step, self.document.height, step):
            painter.drawLine(QPointF(0, y), QPointF(self.document.width, y))

    def _draw_polygon_preview(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pts = list(self._polygon_points)
        if self._mouse_inside:
            pts.append(self._hover_doc)
        if len(pts) >= 2:
            path = QPainterPath()
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
            if len(self._polygon_points) >= 3:
                path.closeSubpath()
            fill = QColor(self.settings.color)
            fill.setAlpha(34 if len(self._polygon_points) >= 3 else 0)
            painter.setBrush(fill)
            pen = QPen(QColor(PRIMARY), max(1.0, 1.6 / self.zoom))
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawPath(path)
        painter.setPen(QPen(QColor(BG), 2 / self.zoom))
        painter.setBrush(QColor(PRIMARY))
        for p in self._polygon_points:
            painter.drawEllipse(p, 4.5 / self.zoom, 4.5 / self.zoom)
        painter.restore()

    def _selected_screen_rect(self) -> QRectF | None:
        obj = self.selected_object()
        if obj is None or not obj.visible:
            return None
        x, y, w, h = obj.bounds()
        top_left = self.doc_to_screen(QPointF(x, y))
        return QRectF(
            top_left.x(),
            top_left.y(),
            max(1.0, w * self.zoom),
            max(1.0, h * self.zoom),
        )

    def _handle_positions(self) -> dict[str, QPointF]:
        obj = self.selected_object()
        if obj is None:
            return {}
        if obj.kind == "line" and len(obj.points) >= 2:
            return {
                "p1": self.doc_to_screen(QPointF(obj.points[0][0], obj.points[0][1])),
                "p2": self.doc_to_screen(QPointF(obj.points[1][0], obj.points[1][1])),
            }
        rect = self._selected_screen_rect()
        if rect is None:
            return {}
        left, top = rect.left(), rect.top()
        right, bottom = rect.right(), rect.bottom()
        cx, cy = rect.center().x(), rect.center().y()
        return {
            "nw": QPointF(left, top),
            "n": QPointF(cx, top),
            "ne": QPointF(right, top),
            "e": QPointF(right, cy),
            "se": QPointF(right, bottom),
            "s": QPointF(cx, bottom),
            "sw": QPointF(left, bottom),
            "w": QPointF(left, cy),
        }

    def _handle_at(self, screen_pos: QPointF) -> str | None:
        for name, point in self._handle_positions().items():
            if (screen_pos - point).manhattanLength() <= 11:
                return name
        return None

    def _draw_selection(self, painter: QPainter) -> None:
        obj = self.selected_object()
        if obj is None or not obj.visible:
            return
        screen_rect = self._selected_screen_rect()
        if screen_rect is None:
            return
        screen_rect = screen_rect.adjusted(-4, -4, 4, 4)
        pen = QPen(QColor(PRIMARY), 1.4)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([4.0, 3.0])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(screen_rect)
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawRect(screen_rect.adjusted(-2, -2, 2, 2))

        handles = self._handle_positions()
        for name, point in handles.items():
            if name in {"p1", "p2"}:
                radius = 5.0
                painter.setPen(QPen(QColor(BG), 2))
                painter.setBrush(QColor(PRIMARY))
                painter.drawEllipse(point, radius, radius)
            else:
                size = 4.0
                handle_rect = QRectF(point.x() - size, point.y() - size, size * 2, size * 2)
                painter.setPen(QPen(QColor(PRIMARY), 1.3))
                painter.setBrush(QColor(SURFACE_1))
                painter.drawRoundedRect(handle_rect, 2.5, 2.5)

        # Object name and dimensions float above the selection.
        font = QFont(ui_font_family())
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        x, y, w, h = obj.bounds()
        caption = f"{obj.label}   {round(w)} × {round(h)}"
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(caption) + 18
        label_y = max(8.0, screen_rect.top() - 27)
        label_rect = QRectF(max(8.0, screen_rect.left()), label_y, text_width, 21)
        painter.setPen(QPen(QColor(OUTLINE), 1))
        painter.setBrush(QColor(24, 27, 33, 242))
        painter.drawRoundedRect(label_rect, 7, 7)
        painter.setPen(QColor(TEXT))
        painter.drawText(
            label_rect.adjusted(9, 0, -9, 0),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            caption,
        )

    def _hud_text(self) -> tuple[str, str, str]:
        tool = self.settings.tool
        if tool == "shape":
            name = SHAPE_KINDS.get(self.settings.shape_kind, "Фигура")
            hint = TOOL_HINTS["shape"]
            icon = {
                "line": "line",
                "rect": "square",
                "rounded_rect": "rounded-square",
                "ellipse": "circle",
                "star": "star",
                "polygon": "polygon",
            }.get(self.settings.shape_kind, "shapes")
            detail = f"{name} · {self.settings.stroke_width:g} px"
            return icon, hint, detail
        if tool in DRAW_TOOLS:
            return {
                "pencil": "pencil",
                "brush": "brush",
                "pen": "pen",
                "spray": "spray",
                "eraser": "eraser",
            }[tool], TOOL_HINTS.get(tool, ""), f"{self.settings.size} px"
        icon = {
            "select": "cursor",
            "hand": "hand",
            "fill": "fill",
            "picker": "eyedropper",
            "text": "text",
        }.get(tool, "brush")
        return icon, TOOL_HINTS.get(tool, ""), ""

    def _draw_hud(self, painter: QPainter) -> None:
        icon_name, text, detail = self._hud_text()
        font = QFont(ui_font_family())
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        label = text
        if detail:
            label = f"{text}  ·  {detail}"
        width = metrics.horizontalAdvance(label) + 56
        rect = QRectF(16, 16, max(138, width), 34)
        painter.setPen(QPen(QColor(OUTLINE), 1))
        painter.setBrush(QColor(22, 25, 31, 238))
        painter.drawRoundedRect(rect, 10, 10)
        icon = self._hud_icon_cache.get(icon_name)
        if icon is None:
            icon = make_pixmap(icon_name, "#D0BCFF", 17)
            self._hud_icon_cache[icon_name] = icon
        painter.drawPixmap(int(rect.left() + 12), int(rect.top() + 9), icon)
        painter.setPen(QColor(TEXT))
        painter.drawText(
            rect.adjusted(37, 0, -10, 0),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            label,
        )

    def _draw_cursor(self, painter: QPainter) -> None:
        if not self._mouse_inside or self._panning:
            return
        if self.settings.tool not in DRAW_TOOLS:
            return
        page = self._page_rect_screen()
        if not page.contains(self._mouse):
            return
        radius = max(3.0, self.settings.size * self.zoom / 2.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(10, 10, 14, 200), 3))
        painter.drawEllipse(self._mouse, radius, radius)
        painter.setPen(QPen(QColor(PRIMARY), 1.3))
        painter.drawEllipse(self._mouse, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PRIMARY))
        painter.drawEllipse(self._mouse, 1.4, 1.4)

    # ------------------------------------------------------------------- mouse
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if self._text_editor is not None:
            self._commit_text_editor()
            return
        pos = event.position()
        self._mouse = pos
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and (self.settings.tool == "hand" or self._space_down)
        ):
            self._begin_pan(pos)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        page = self._page_rect_screen()
        doc_pos = self.screen_to_doc(pos)
        inside = page.contains(pos)
        if self.settings.tool == "select":
            self._press_select(pos, event)
            return
        if self.settings.tool == "hand":
            return
        if self.settings.tool == "text":
            if inside:
                hit = self.document.hit_test(doc_pos.x(), doc_pos.y(), tolerance=4 / self.zoom)
                if hit is not None and hit.kind == "text":
                    self.select(hit.id)
                    self._open_text_editor(hit, QPointF(hit.x, hit.y))
                else:
                    self._open_text_editor(None, self._clamp_doc(doc_pos))
            return
        if self.settings.tool == "picker":
            if inside:
                self._pick_color(doc_pos)
            return
        if self.settings.tool == "fill":
            if inside:
                self._fill_at(doc_pos)
            return
        if not inside:
            return
        if self.settings.tool in DRAW_TOOLS:
            self._begin_stroke(self._clamp_doc(doc_pos))
            return
        if self.settings.tool == "shape":
            if self.settings.shape_kind == "polygon":
                self._add_polygon_point(self._clamp_doc(doc_pos))
            else:
                self._begin_shape(self._clamp_doc(doc_pos))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        self._mouse = pos
        self._mouse_inside = True
        self._hover_doc = self._clamp_doc(self.screen_to_doc(pos))
        if self._page_rect_screen().contains(pos):
            self.cursorMoved.emit(self._hover_doc.x(), self._hover_doc.y())
        if self._panning:
            delta = pos - self._pan_start
            self.pan = self._pan_origin + delta
            self._position_text_editor()
            self.update()
            return
        if self._drag_mode is not None:
            self._drag_move(pos, event.modifiers())
            return
        if self._stroke is not None:
            self._stroke_move(self._clamp_doc(self.screen_to_doc(pos)))
            return
        if self._draft is not None:
            self._draft_move(self._clamp_doc(self.screen_to_doc(pos)), event.modifiers())
            return
        if self._polygon_points:
            self.update()
        self._update_cursor(pos)
        if self.settings.tool in DRAW_TOOLS:
            self.update()
        elif self.settings.tool == "select":
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            return
        if self._panning:
            self._panning = False
            self._update_cursor(event.position())
            return
        if self._drag_mode is not None:
            self._finish_drag()
            return
        if self._stroke is not None:
            self._finish_stroke()
            return
        if self._draft is not None:
            self._finish_shape()
            return
        self._update_cursor(event.position())

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._text_editor is not None:
            return
        pos = event.position()
        if self.settings.tool == "shape" and self.settings.shape_kind == "polygon":
            if self._polygon_points:
                self._finish_polygon()
            return
        if self.settings.tool != "select":
            return
        self._cancel_drag_undo_if_unchanged()
        self._drag_mode = None
        self._drag_original = None
        obj = self.selected_object()
        if obj is None:
            doc_pos = self.screen_to_doc(pos)
            obj = self.document.hit_test(doc_pos.x(), doc_pos.y(), tolerance=4 / self.zoom)
        if obj is not None and obj.kind == "text":
            self.select(obj.id)
            self._open_text_editor(obj, QPointF(obj.x, obj.y))

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom * (1.0018**delta), event.position())
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.pan += QPointF(delta * 0.6, 0)
        else:
            self.pan += QPointF(0, delta * 0.6)
        self._position_text_editor()
        self.update()
        event.accept()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._mouse_inside = False
        self._update_cursor(QPointF(-100, -100))
        self.update()
        super().leaveEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._mouse_inside = True
        super().enterEvent(event)

    # ------------------------------------------------------------------ panning
    def _begin_pan(self, pos: QPointF) -> None:
        self._panning = True
        self._pan_start = pos
        self._pan_origin = QPointF(self.pan)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    # ------------------------------------------------------------------ select
    def _press_select(self, pos: QPointF, event: QMouseEvent) -> None:
        self.cancel_pending_edits()
        handle = self._handle_at(pos)
        obj = self.selected_object()
        if obj is not None and handle is not None:
            self.push_undo()
            self._undo_before_drag = len(self.undo_stack)
            self._drag_mode = "resize"
            self._drag_handle = handle
            self._drag_start = self.screen_to_doc(pos)
            self._drag_original = obj.copy()
            self._drag_changed = False
            return
        doc_pos = self.screen_to_doc(pos)
        hit = self.document.hit_test(doc_pos.x(), doc_pos.y(), tolerance=5.0 / self.zoom)
        if hit is None:
            self.clear_selection()
            self.update()
            return
        if hit.id != self.selected_id:
            self.select(hit.id)
        self.push_undo()
        self._undo_before_drag = len(self.undo_stack)
        self._drag_mode = "move"
        self._drag_handle = None
        self._drag_start = self.screen_to_doc(pos)
        self._drag_original = hit.copy()
        self._drag_changed = False
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def _drag_move(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        obj = self.selected_object()
        original = self._drag_original
        if obj is None or original is None:
            self._drag_mode = None
            return
        mouse = self.screen_to_doc(pos)
        dx = mouse.x() - self._drag_start.x()
        dy = mouse.y() - self._drag_start.y()
        if abs(dx) + abs(dy) > 0.3:
            self._drag_changed = True
        if self._drag_mode == "move":
            self._apply_copy(original)
            obj.move(dx, dy)
        elif self._drag_mode == "resize":
            self._apply_copy(original)
            self._resize_from_handle(obj, original, self._drag_handle or "", mouse, modifiers)
        self.geometryChanged.emit()
        self.update()

    def _resize_from_handle(
        self,
        obj: DrawObject,
        original: DrawObject,
        handle: str,
        mouse: QPointF,
        modifiers: Qt.KeyboardModifier,
    ) -> None:
        if original.kind == "line" and len(original.points) >= 2:
            pts = [list(p) for p in original.points]
            index = 0 if handle == "p1" else 1
            other = 1 - index
            ox, oy = pts[other]
            nx, ny = self._clamp_doc(mouse).x(), self._clamp_doc(mouse).y()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                angle = math.atan2(ny - oy, nx - ox)
                step = math.pi / 4.0
                angle = round(angle / step) * step
                length = math.hypot(nx - ox, ny - oy)
                nx, ny = ox + math.cos(angle) * length, oy + math.sin(angle) * length
            obj.points[index] = [nx, ny]
            obj.recalc_bounds()
            return

        ox, oy, ow, oh = original.bounds()
        left, top, right, bottom = ox, oy, ox + ow, oy + oh
        mx = clamp(mouse.x(), 0.0, self.document.width)
        my = clamp(mouse.y(), 0.0, self.document.height)
        minimum = 8.0 / self.zoom
        if "w" in handle:
            left = min(mx, right - minimum)
        if "e" in handle:
            right = max(mx, left + minimum)
        if "n" in handle:
            top = min(my, bottom - minimum)
        if "s" in handle:
            bottom = max(my, top + minimum)

        if modifiers & Qt.KeyboardModifier.ShiftModifier and len(handle) == 2:
            aspect = ow / max(1e-6, oh)
            new_w = max(minimum, right - left)
            new_h = max(minimum, bottom - top)
            if new_w / new_h > aspect:
                new_w = new_h * aspect
            else:
                new_h = new_w / aspect
            if "w" in handle:
                left = right - new_w
            else:
                right = left + new_w
            if "n" in handle:
                top = bottom - new_h
            else:
                bottom = top + new_h

        obj.scale_to(left, top, right - left, bottom - top, (ox, oy, ow, oh))

    def _apply_copy(self, original: DrawObject) -> None:
        obj = self.selected_object()
        if obj is None:
            return
        object_id = obj.id
        for field in fields(DrawObject):
            setattr(obj, field.name, copy.deepcopy(getattr(original, field.name)))
        # Drag copies are snapshots, not duplicate objects: keep the identity.
        obj.id = object_id

    def _finish_drag(self) -> None:
        if self._drag_changed:
            self.documentChanged.emit()
        else:
            self._cancel_drag_undo_if_unchanged()
        self._drag_mode = None
        self._drag_original = None
        self._drag_handle = None
        self._drag_changed = False
        self.geometryChanged.emit()
        self._update_cursor(self._mouse)
        self.update()

    def _cancel_drag_undo_if_unchanged(self) -> None:
        if not self._drag_changed and len(self.undo_stack) >= self._undo_before_drag > 0:
            self.undo_stack.pop()
            self.historyChanged.emit(bool(self.undo_stack), bool(self.redo_stack))

    # ------------------------------------------------------------------ strokes
    def _begin_stroke(self, pos: QPointF) -> None:
        self.clear_selection()
        self.push_undo()
        tool = self.settings.tool
        obj = DrawObject(
            kind="stroke",
            tool=tool,
            opacity=self.settings.opacity / 100.0,
            stroke=self.settings.color,
            stroke_width=float(self.settings.size),
            points=[[pos.x(), pos.y()]],
        )
        if tool == "eraser":
            obj.stroke = self.document.background
        self._last_width = float(self.settings.size)
        if tool in {"brush", "pen"}:
            obj.width_profile = [self._last_width]
        self._last_point = pos
        self._last_stroke_time = time.perf_counter()
        if tool == "spray":
            self._spray_at(obj, pos, pos, 7)
        self._stroke = obj
        self.document.objects.append(obj)
        self._update_cursor(self._mouse)
        self.update()

    def _stroke_move(self, pos: QPointF) -> None:
        obj = self._stroke
        if obj is None:
            return
        distance = math.hypot(pos.x() - self._last_point.x(), pos.y() - self._last_point.y())
        if distance < 0.7:
            return
        now = time.perf_counter()
        dt = max(0.001, now - self._last_stroke_time)
        if obj.tool in {"brush", "pen"}:
            speed = distance / dt
            if obj.tool == "pen":
                pressure = 1.0 - clamp(speed / 1800.0, 0.0, 0.76)
                target = float(self.settings.size) * (0.24 + 0.76 * pressure)
            else:
                pressure = 1.0 - clamp(speed / 2300.0, 0.0, 0.55)
                target = float(self.settings.size) * (0.58 + 0.42 * pressure)
            self._last_width = self._last_width * 0.72 + target * 0.28
            obj.width_profile.append(round(self._last_width, 2))
        obj.points.append([pos.x(), pos.y()])
        if obj.tool == "spray":
            self._spray_at(obj, self._last_point, pos, max(3, int(distance * 1.3)))
        self._last_point = pos
        self._last_stroke_time = now
        obj.recalc_bounds()
        self.update()

    def _spray_at(self, obj: DrawObject, start: QPointF, end: QPointF, count: int) -> None:
        radius = max(2.0, self.settings.size / 2.0)
        for i in range(max(1, count)):
            t = (i + 0.5) / max(1, count)
            cx = start.x() + (end.x() - start.x()) * t
            cy = start.y() + (end.y() - start.y()) * t
            # Uniform-ish distribution inside the spray radius.
            r = radius * math.sqrt(random.random())
            theta = random.random() * math.tau
            x = cx + math.cos(theta) * r
            y = cy + math.sin(theta) * r
            dot_radius = random.uniform(max(0.35, self.settings.size * 0.035), max(0.7, self.settings.size * 0.09))
            alpha = random.uniform(0.16, 0.72)
            obj.spray_dots.append([x, y, dot_radius, alpha])
        obj.recalc_bounds()

    def _finish_stroke(self) -> None:
        obj = self._stroke
        self._stroke = None
        if obj is None:
            return
        if not obj.points:
            self.document.remove(obj.id)
        else:
            obj.recalc_bounds()
        self.documentChanged.emit()
        self.update()

    # ------------------------------------------------------------------- shapes
    def _shape_style(self, kind: str) -> dict:
        s = self.settings
        stroke = s.color if kind == "line" else s.secondary
        return {
            "stroke": stroke,
            "stroke_width": float(s.stroke_width),
            "fill_mode": "none" if kind == "line" else s.fill_mode,
            "fill": s.color,
            "fill2": s.fill2,
            "gradient_angle": s.gradient_angle,
            "opacity": s.opacity / 100.0,
            "corner_radius": s.corner_radius,
            "star_points": s.star_points,
            "star_inner": s.star_inner,
        }

    def _begin_shape(self, pos: QPointF) -> None:
        self.clear_selection()
        self._draft_start = pos
        kind = self.settings.shape_kind
        obj = DrawObject(
            kind="line" if kind == "line" else kind,
            x=pos.x(),
            y=pos.y(),
            w=1,
            h=1,
            **self._shape_style(kind),
        )
        if kind == "line":
            obj.points = [[pos.x(), pos.y()], [pos.x(), pos.y()]]
        elif kind == "polygon":
            obj.kind = "polygon"
        self._draft = obj
        self.update()

    def _draft_move(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        self._update_draft(pos, modifiers)
        self.update()

    def _update_draft(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        obj = self._draft
        if obj is None:
            return
        start = self._draft_start
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(modifiers & Qt.KeyboardModifier.AltModifier)
        if obj.kind == "line":
            end = pos
            if shift:
                angle = math.atan2(end.y() - start.y(), end.x() - start.x())
                step = math.pi / 4.0
                angle = round(angle / step) * step
                length = math.hypot(end.x() - start.x(), end.y() - start.y())
                end = QPointF(start.x() + math.cos(angle) * length, start.y() + math.sin(angle) * length)
            obj.points = [[start.x(), start.y()], [end.x(), end.y()]]
            obj.recalc_bounds()
            return
        dx, dy = pos.x() - start.x(), pos.y() - start.y()
        if shift:
            size = max(abs(dx), abs(dy))
            dx = math.copysign(size, dx or 1.0)
            dy = math.copysign(size, dy or 1.0)
        if alt:
            x = start.x() - abs(dx)
            y = start.y() - abs(dy)
            w = abs(dx) * 2
            h = abs(dy) * 2
        else:
            x = min(start.x(), start.x() + dx)
            y = min(start.y(), start.y() + dy)
            w = abs(dx)
            h = abs(dy)
        obj.x, obj.y = x, y
        obj.w, obj.h = max(1.0, w), max(1.0, h)

    def _finish_shape(self) -> None:
        obj = self._draft
        self._draft = None
        if obj is None:
            return
        if obj.kind == "line":
            length = math.hypot(
                obj.points[1][0] - obj.points[0][0], obj.points[1][1] - obj.points[0][1]
            )
            if length < 2:
                self.update()
                return
        elif obj.w < 2 or obj.h < 2:
            self.update()
            return
        self.push_undo()
        self.document.add(obj)
        self.selected_id = obj.id
        self.selectionChanged.emit(obj)
        self.documentChanged.emit()
        self.update()

    # ------------------------------------------------------------------ polygon
    def _add_polygon_point(self, pos: QPointF) -> None:
        if self._polygon_points and (pos - self._polygon_points[-1]).manhattanLength() < 4 / self.zoom:
            self._finish_polygon()
            return
        self._polygon_points.append(pos)
        self.update()

    def _finish_polygon(self) -> None:
        points = list(self._polygon_points)
        self._polygon_points.clear()
        if len(points) < 3:
            self.update()
            return
        obj = DrawObject(kind="polygon", **self._shape_style("polygon"))
        obj.points = [[p.x(), p.y()] for p in points]
        obj.sanitize()
        self.push_undo()
        self.document.add(obj)
        self.selected_id = obj.id
        self.selectionChanged.emit(obj)
        self.documentChanged.emit()
        self.update()

    # ------------------------------------------------------------------- text
    def _open_text_editor(self, obj: DrawObject | None, pos: QPointF) -> None:
        if self._text_editor is not None:
            self._commit_text_editor()
        self._text_is_new = obj is None
        self._text_target = obj
        self._text_doc_pos = pos
        editor = QTextEdit(self)
        editor.setObjectName("TextOverlay")
        editor.setAcceptRichText(False)
        editor.setTabChangesFocus(True)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor.setPlaceholderText("Введите текст…  Ctrl+Enter — применить, Esc — отмена")
        editor.installEventFilter(self)
        if obj is not None:
            editor.setPlainText(obj.text)
            editor.selectAll()
            self._text_original_visible = obj.visible
            obj.visible = False
            family = obj.font_family
            pixel_size = obj.font_size
        else:
            family = self.settings.font_family
            pixel_size = self.settings.font_size
        editor_font = QFont(family)
        editor_font.setPixelSize(int(clamp(pixel_size * self.zoom, 12, 42)))
        editor.setFont(editor_font)
        editor.setStyleSheet(
            f"""
            QTextEdit#TextOverlay {{
                background: #191C22;
                color: #F4F0FA;
                border: 2px solid {PRIMARY};
                border-radius: 12px;
                padding: 9px;
                selection-background-color: #4F378B;
                font-family: "{family}";
            }}
            """
        )
        self._text_editor = editor
        self._position_text_editor()
        editor.show()
        editor.raise_()

        def focus_editor() -> None:
            if self._text_editor is editor:
                editor.setFocus(Qt.FocusReason.OtherFocusReason)

        QTimer.singleShot(0, focus_editor)
        self.update()

    def _text_editor_rect(self) -> QRect:
        obj = self._text_target
        if obj is not None:
            top_left = self.doc_to_screen(QPointF(obj.x, obj.y))
            width = clamp(obj.w * self.zoom, 280, 560)
            height = clamp(obj.h * self.zoom + 40, 110, 260)
        else:
            top_left = self.doc_to_screen(self._text_doc_pos)
            width = clamp(self.document.width * self.zoom * 0.45, 300, 560)
            height = 130
        x = clamp(top_left.x(), 12, max(12, self.width() - width - 12))
        y = clamp(top_left.y(), 12, max(12, self.height() - height - 12))
        return QRect(int(x), int(y), int(width), int(height))

    def _position_text_editor(self) -> None:
        if self._text_editor is not None:
            self._text_editor.setGeometry(self._text_editor_rect())

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._text_editor:
            if event.type() == QEvent.Type.KeyPress:
                key_event = event
                if key_event.key() == Qt.Key.Key_Escape:
                    self._cancel_text_editor()
                    return True
                if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if key_event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        self._commit_text_editor()
                        return True
            elif event.type() == QEvent.Type.FocusOut:
                QTimer.singleShot(0, self._commit_text_editor_if_visible)
        return super().eventFilter(obj, event)

    def _commit_text_editor_if_visible(self) -> None:
        if self._text_editor is not None and self._text_editor.isVisible():
            self._commit_text_editor()

    def _commit_text_editor(self) -> None:
        if self._text_editor is None or self._text_closing:
            return
        self._text_closing = True
        editor = self._text_editor
        text = editor.toPlainText()
        target = self._text_target
        is_new = self._text_is_new
        pos = self._text_doc_pos
        self._teardown_text_editor()
        if target is not None:
            target.visible = True
            if not text.strip():
                if target.text.strip():
                    self.push_undo()
                    self.document.remove(target.id)
                    self.selected_id = None
                    self.selectionChanged.emit(None)
                    self.documentChanged.emit()
            elif text != target.text:
                self.push_undo()
                target.text = text
                self._fit_text_height(target)
                target.sanitize()
                self.selected_id = target.id
                self.selectionChanged.emit(target)
                self.geometryChanged.emit()
                self.documentChanged.emit()
        elif is_new and text.strip():
            self.push_undo()
            obj = DrawObject(
                kind="text",
                x=pos.x(),
                y=pos.y(),
                w=clamp(self.document.width - pos.x() - 12, 120, 640),
                h=max(40, self.settings.font_size * 1.4),
                text=text,
                font_family=self.settings.font_family,
                font_size=self.settings.font_size,
                bold=self.settings.bold,
                italic=self.settings.italic,
                underline=self.settings.underline,
                align=self.settings.align,
                fill=self.settings.color,
                fill2=self.settings.fill2,
                fill_mode="solid",
                stroke=self.settings.secondary,
                opacity=self.settings.opacity / 100.0,
            )
            self._fit_text_height(obj)
            obj.sanitize()
            self.document.add(obj)
            self.selected_id = obj.id
            self.selectionChanged.emit(obj)
            self.documentChanged.emit()
        self._text_closing = False
        self.update()

    def _cancel_text_editor(self) -> None:
        if self._text_editor is None:
            return
        target = self._text_target
        self._teardown_text_editor()
        if target is not None:
            target.visible = self._text_original_visible
        self.update()

    def _teardown_text_editor(self) -> None:
        editor = self._text_editor
        self._text_editor = None
        self._text_target = None
        if editor is not None:
            editor.blockSignals(True)
            editor.hide()
            editor.deleteLater()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _fit_text_height(self, obj: DrawObject) -> None:
        if obj.kind != "text":
            return
        font = QFont(obj.font_family)
        font.setPixelSize(max(6, obj.font_size))
        font.setBold(obj.bold)
        font.setItalic(obj.italic)
        metrics = QFontMetrics(font)
        rect = metrics.boundingRect(
            QRect(0, 0, max(20, int(obj.w)), 10000),
            int(Qt.TextFlag.TextWordWrap),
            obj.text or " ",
        )
        obj.h = max(obj.font_size * 1.25, rect.height() + 6)

    def cancel_pending_edits(self) -> None:
        if self._text_editor is not None:
            self._commit_text_editor()
        if self._polygon_points:
            self._polygon_points.clear()
            self.update()
        if self._draft is not None:
            self._draft = None
            self.update()

    def finish_text_edit(self) -> None:
        if self._text_editor is not None:
            self._commit_text_editor()

    # ---------------------------------------------------------------- fill/picker
    def _fill_at(self, doc_pos: QPointF) -> None:
        obj = self.document.hit_test(doc_pos.x(), doc_pos.y(), tolerance=2 / self.zoom)
        if obj is None:
            if qcolor(self.document.background).name().lower() != qcolor(self.settings.color).name().lower():
                self.push_undo()
                self.document.background = self.settings.color
                self.documentChanged.emit()
                self.update()
            return
        self.push_undo()
        if obj.kind == "stroke":
            obj.stroke = self.settings.color
        else:
            obj.fill_mode = "solid" if self.settings.fill_mode == "none" else self.settings.fill_mode
            obj.fill = self.settings.color
            obj.fill2 = self.settings.fill2
            obj.gradient_angle = self.settings.gradient_angle
        self.selected_id = obj.id
        self.selectionChanged.emit(obj)
        self.documentChanged.emit()
        self.update()

    def _pick_color(self, doc_pos: QPointF) -> None:
        image = render_to_image(self.document)
        x = int(clamp(doc_pos.x(), 0, self.document.width - 1))
        y = int(clamp(doc_pos.y(), 0, self.document.height - 1))
        color = image.pixelColor(x, y)
        if color.alpha() == 0:
            color = qcolor(self.document.background)
        value = color.name(QColor.NameFormat.HexRgb)
        self.colorPicked.emit(value)
        self.statusMessage.emit(f"Цвет {value.upper()} взят с холста")
        self.settings.tool = "brush"
        self.toolChanged.emit("brush")
        self._update_cursor(self._mouse)

    # ----------------------------------------------------------------- context
    def contextMenuEvent(self, event) -> None:  # noqa: N802
        pos = QPointF(event.pos())
        doc_pos = self.screen_to_doc(pos)
        hit = self.document.hit_test(doc_pos.x(), doc_pos.y(), tolerance=5 / self.zoom)
        if hit is not None and hit.id != self.selected_id:
            self.select(hit.id)
        menu = QMenu(self)
        if self.selected_object() is not None:
            duplicate = menu.addAction(QIcon(make_pixmap("copy", TEXT_MUTED, 16)), "Дублировать")
            duplicate.setShortcut("Ctrl+D")
            duplicate.triggered.connect(self.duplicate_selected)
            front = menu.addAction(QIcon(make_pixmap("front", TEXT_MUTED, 16)), "На передний план")
            front.triggered.connect(self.raise_selected)
            back = menu.addAction(QIcon(make_pixmap("back", TEXT_MUTED, 16)), "На задний план")
            back.triggered.connect(self.lower_selected)
            menu.addSeparator()
            hide = menu.addAction(
                QIcon(
                    make_pixmap(
                        "eye-off" if self.selected_object().visible else "eye", TEXT_MUTED, 16
                    )
                ),
                "Скрыть" if self.selected_object().visible else "Показать",
            )
            hide.triggered.connect(self.toggle_selected_visibility)
            menu.addSeparator()
            delete = menu.addAction(QIcon(make_pixmap("trash", "#FFB4AB", 16)), "Удалить")
            delete.setShortcut("Del")
            delete.triggered.connect(self.delete_selected)
        else:
            action = menu.addAction("Снять выделение")
            action.triggered.connect(self.clear_selection)
        menu.exec(event.globalPos())

    # ----------------------------------------------------------------- keyboard
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = True
            self._update_cursor(self._mouse)
            return
        if key == Qt.Key.Key_Escape:
            if self._polygon_points:
                self._polygon_points.clear()
                self.update()
                return
            if self._drag_mode is not None:
                self._cancel_drag_undo_if_unchanged()
                if self._drag_original is not None:
                    self._apply_copy(self._drag_original)
                self._drag_mode = None
                self._drag_original = None
                self.documentChanged.emit()
                self.update()
                return
            self.clear_selection()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._polygon_points:
            self._finish_polygon()
            return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            return
        if key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
            dx = -step if key == Qt.Key.Key_Left else step if key == Qt.Key.Key_Right else 0
            dy = -step if key == Qt.Key.Key_Up else step if key == Qt.Key.Key_Down else 0
            self.nudge_selected(dx, dy)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = False
            self._update_cursor(self._mouse)
            return
        super().keyReleaseEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._initial_view_done and self.isVisible() and self.width() > 100:
            QTimer.singleShot(0, self.fit_to_view)
        self._position_text_editor()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._initial_view_done:
            QTimer.singleShot(0, self.fit_to_view)

    # ------------------------------------------------------------------ cursor
    def _update_cursor(self, pos: QPointF) -> None:
        tool = self.settings.tool
        if self._panning or tool == "hand" or self._space_down:
            self.setCursor(
                Qt.CursorShape.ClosedHandCursor if self._panning else Qt.CursorShape.OpenHandCursor
            )
            return
        if tool == "select":
            handle = self._handle_at(pos)
            if handle:
                self.setCursor(HANDLE_CURSORS.get(handle, Qt.CursorShape.SizeAllCursor))
                return
            obj = self.selected_object()
            if obj is not None and obj.visible:
                rect = self._selected_screen_rect()
                if rect is not None and rect.adjusted(-4, -4, 4, 4).contains(pos):
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    return
            doc_pos = self.screen_to_doc(pos)
            hit = self.document.hit_test(doc_pos.x(), doc_pos.y(), tolerance=5 / self.zoom)
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if hit is not None else Qt.CursorShape.ArrowCursor
            )
            return
        if tool == "text":
            self.setCursor(Qt.CursorShape.IBeamCursor)
            return
        if tool == "fill":
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            return
        if tool == "picker":
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        if tool in DRAW_TOOLS or tool == "shape":
            if self._page_rect_screen().contains(pos):
                if tool in DRAW_TOOLS:
                    self.setCursor(Qt.CursorShape.BlankCursor)
                else:
                    self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _tool_status(self) -> str:
        if self.settings.tool == "shape":
            return f"Фигура: {SHAPE_KINDS.get(self.settings.shape_kind, '')}"
        return TOOL_HINTS.get(self.settings.tool, "")

    # ------------------------------------------------------------------- images
    def insert_image(self, path: str | Path) -> DrawObject | None:
        image = QImage(str(path))
        if image.isNull():
            self.statusMessage.emit("Не удалось открыть изображение")
            return None
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        encoded = base64.b64encode(bytes(data)).decode("ascii")
        max_w = self.document.width * 0.58
        max_h = self.document.height * 0.58
        scale = min(1.0, max_w / image.width(), max_h / image.height())
        w, h = image.width() * scale, image.height() * scale
        x, y = (self.document.width - w) / 2.0, (self.document.height - h) / 2.0
        obj = DrawObject(
            kind="image",
            x=x,
            y=y,
            w=w,
            h=h,
            image_data=encoded,
            image_format="PNG",
            opacity=1.0,
            name=Path(path).stem,
        )
        self.push_undo()
        self.document.add(obj)
        self.selected_id = obj.id
        self.selectionChanged.emit(obj)
        self.documentChanged.emit()
        self.update()
        return obj

    def insert_image_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Вставить изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)",
        )
        if path:
            self.insert_image(path)

    def paste_image_from_clipboard(self) -> bool:
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            return False
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        encoded = base64.b64encode(bytes(data)).decode("ascii")
        max_w = self.document.width * 0.58
        max_h = self.document.height * 0.58
        scale = min(1.0, max_w / image.width(), max_h / image.height())
        w, h = image.width() * scale, image.height() * scale
        obj = DrawObject(
            kind="image",
            x=(self.document.width - w) / 2,
            y=(self.document.height - h) / 2,
            w=w,
            h=h,
            image_data=encoded,
            name="Вставка",
        )
        self.push_undo()
        self.document.add(obj)
        self.selected_id = obj.id
        self.selectionChanged.emit(obj)
        self.documentChanged.emit()
        self.update()
        return True
