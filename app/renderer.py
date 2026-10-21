"""QPainter renderer shared by the interactive canvas and image export."""

from __future__ import annotations

import base64
import math
from typing import Iterable

from PyQt6.QtCore import QByteArray, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTextOption,
    QFont,
)
from PyQt6.QtWidgets import QApplication

from .models import Document, DrawObject


def qcolor(value: str, fallback: str = "#000000") -> QColor:
    color = QColor(value)
    if not color.isValid():
        color = QColor(fallback)
    return color


def blend(colors: Iterable[QColor], t: float) -> QColor:
    colors = list(colors)
    if not colors:
        return QColor("#000000")
    if len(colors) == 1:
        return QColor(colors[0])
    t = max(0.0, min(1.0, t))
    scaled = t * (len(colors) - 1)
    index = min(int(scaled), len(colors) - 2)
    local = scaled - index
    a, b = colors[index], colors[index + 1]
    return QColor(
        round(a.red() + (b.red() - a.red()) * local),
        round(a.green() + (b.green() - a.green()) * local),
        round(a.blue() + (b.blue() - a.blue()) * local),
        round(a.alpha() + (b.alpha() - a.alpha()) * local),
    )


def gradient_brush(obj: DrawObject, bounds: tuple[float, float, float, float]) -> QBrush:
    x, y, w, h = bounds
    c1 = qcolor(obj.fill, "#D0BCFF")
    c2 = qcolor(obj.fill2, "#7D5260")
    if obj.fill_mode == "none":
        return QBrush(Qt.BrushStyle.NoBrush)
    if obj.fill_mode == "solid":
        return QBrush(c1)
    if obj.fill_mode == "radial":
        center = QPointF(x + w / 2.0, y + h / 2.0)
        radius = max(w, h) * 0.64
        gradient = QRadialGradient(center, radius, center)
        gradient.setColorAt(0.0, c1)
        gradient.setColorAt(0.55, blend([c1, c2], 0.65))
        gradient.setColorAt(1.0, c2)
        return QBrush(gradient)
    # Linear gradient. 0° is left → right, 90° is top → bottom.
    angle = math.radians(obj.gradient_angle)
    dx, dy = math.cos(angle), math.sin(angle)
    cx, cy = x + w / 2.0, y + h / 2.0
    extent = (abs(w * dx) + abs(h * dy)) / 2.0
    start = QPointF(cx - dx * extent, cy - dy * extent)
    end = QPointF(cx + dx * extent, cy + dy * extent)
    gradient = QLinearGradient(start, end)
    gradient.setColorAt(0.0, c1)
    gradient.setColorAt(1.0, c2)
    return QBrush(gradient)


def smooth_path(points: list[tuple[float, float]]) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(points[0][0], points[0][1])
    if len(points) == 1:
        return path
    if len(points) == 2:
        path.lineTo(points[1][0], points[1][1])
        return path
    for i in range(1, len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        midx, midy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        path.quadTo(x0, y0, midx, midy)
    path.lineTo(points[-1][0], points[-1][1])
    return path


def _variable_width_path(obj: DrawObject) -> QPainterPath:
    """Build a filled ribbon around the stroke centerline.

    Two round caps and polygon strips between sampled points approximate a
    pressure-sensitive brush without requiring QPainter's fixed-width QPen.
    """
    points = [(p[0], p[1]) for p in obj.points]
    if not points:
        return QPainterPath()
    base = max(1.0, float(obj.stroke_width))
    widths: list[float] = []
    for i in range(len(points)):
        if i < len(obj.width_profile):
            widths.append(max(0.4, float(obj.width_profile[i])))
        else:
            widths.append(base)
    path = QPainterPath()
    if len(points) == 1:
        r = widths[0] / 2.0
        path.addEllipse(QPointF(points[0][0], points[0][1]), r, r)
        return path

    for i, (x, y) in enumerate(points):
        r = widths[i] / 2.0
        path.addEllipse(QPointF(x, y), r, r)

    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length < 0.001:
            continue
        nx, ny = -dy / length, dx / length
        r0, r1 = widths[i] / 2.0, widths[i + 1] / 2.0
        path.moveTo(x0 + nx * r0, y0 + ny * r0)
        path.lineTo(x1 + nx * r1, y1 + ny * r1)
        path.lineTo(x1 - nx * r1, y1 - ny * r1)
        path.lineTo(x0 - nx * r0, y0 - ny * r0)
        path.closeSubpath()
    return path


def _paint_stroke(painter: QPainter, obj: DrawObject, background: str) -> None:
    if not obj.points:
        return
    tool = obj.tool or "brush"
    color = qcolor(obj.stroke if tool == "eraser" else obj.stroke, "#000000")
    if tool == "eraser":
        color = qcolor(background, "#FFFFFF")

    if tool == "spray":
        brush = QBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(brush)
        for dot in obj.spray_dots:
            if len(dot) < 4:
                continue
            x, y, radius, alpha = dot
            c = QColor(color)
            c.setAlpha(int(max(0.0, min(1.0, alpha)) * 255))
            painter.setBrush(QBrush(c))
            painter.drawEllipse(QPointF(x, y), radius, radius)
        return

    if tool == "pencil":
        if len(obj.points) == 1:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(
                QPointF(obj.points[0][0], obj.points[0][1]),
                max(0.6, obj.stroke_width / 2.0),
                max(0.6, obj.stroke_width / 2.0),
            )
            return
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(color, max(0.6, obj.stroke_width))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(smooth_path([(p[0], p[1]) for p in obj.points]))
        # A second, offset pass gives the pencil a subtle graphite texture.
        texture = QColor(color)
        texture.setAlpha(int(texture.alpha() * 0.20))
        pen2 = QPen(texture, max(0.5, obj.stroke_width * 0.55))
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen2)
        offset = max(0.6, obj.stroke_width * 0.20)
        painter.drawPath(
            smooth_path([(p[0] + offset, p[1] + offset) for p in obj.points])
        )
        return

    path = _variable_width_path(obj)
    painter.setPen(Qt.PenStyle.NoPen)
    c = QColor(color)
    if tool == "brush":
        c.setAlpha(int(c.alpha() * 0.90))
    painter.setBrush(QBrush(c))
    painter.drawPath(path)


def _shape_path(obj: DrawObject) -> QPainterPath:
    path = QPainterPath()
    x, y, w, h = obj.bounds()
    if obj.kind == "rect":
        path.addRect(QRectF(x, y, w, h))
    elif obj.kind == "rounded_rect":
        radius = min(obj.corner_radius, w / 2.0, h / 2.0)
        path.addRoundedRect(QRectF(x, y, w, h), radius, radius)
    elif obj.kind == "ellipse":
        path.addEllipse(QRectF(x, y, w, h))
    elif obj.kind in {"polygon", "star"}:
        pts = obj.shape_polygon()
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for px, py in pts[1:]:
                path.lineTo(px, py)
            path.closeSubpath()
    elif obj.kind == "line":
        if len(obj.points) >= 2:
            path.moveTo(obj.points[0][0], obj.points[0][1])
            path.lineTo(obj.points[1][0], obj.points[1][1])
    return path


def paint_text(painter: QPainter, obj: DrawObject) -> None:
    x, y, w, h = obj.bounds()
    font = QFont(obj.font_family)
    font.setPixelSize(max(6, int(obj.font_size)))
    font.setBold(obj.bold)
    font.setItalic(obj.italic)
    font.setUnderline(obj.underline)
    painter.setFont(font)
    brush = gradient_brush(obj, (x, y, w, max(h, obj.font_size * 1.4)))
    if obj.fill_mode == "none":
        brush = QBrush(qcolor(obj.stroke))
    painter.setPen(QPen(brush, 1))
    option = QTextOption()
    alignment = {
        "left": Qt.AlignmentFlag.AlignLeft,
        "center": Qt.AlignmentFlag.AlignHCenter,
        "right": Qt.AlignmentFlag.AlignRight,
    }.get(obj.align, Qt.AlignmentFlag.AlignLeft)
    option.setAlignment(alignment | Qt.AlignmentFlag.AlignTop)
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    painter.drawText(QRectF(x, y, max(1.0, w), max(1.0, h)), obj.text, option)


def image_for_object(obj: DrawObject) -> QImage | None:
    if not obj.image_data:
        return None
    try:
        raw = base64.b64decode(obj.image_data.encode("ascii"))
        image = QImage()
        if not image.loadFromData(QByteArray(raw)):
            return None
        return image
    except Exception:
        return None


def paint_object(
    painter: QPainter,
    obj: DrawObject,
    background: str = "#FFFFFF",
) -> None:
    if not obj.visible:
        return
    painter.save()
    painter.setOpacity(max(0.0, min(1.0, obj.opacity)))
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        if obj.kind == "stroke":
            _paint_stroke(painter, obj, background)
        elif obj.kind == "text":
            paint_text(painter, obj)
        elif obj.kind == "image":
            image = image_for_object(obj)
            if image is not None:
                x, y, w, h = obj.bounds()
                painter.drawImage(QRectF(x, y, w, h), image)
        else:
            path = _shape_path(obj)
            if path.isEmpty():
                return
            if obj.kind != "line" and obj.fill_mode != "none":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(gradient_brush(obj, obj.bounds()))
                painter.drawPath(path)
            if obj.stroke_width > 0:
                pen = QPen(qcolor(obj.stroke, "#000000"), max(0.5, obj.stroke_width))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
    finally:
        painter.restore()


def render_document(
    painter: QPainter,
    document: Document,
    *,
    draw_background: bool = True,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    if draw_background:
        painter.fillRect(
            QRectF(0, 0, document.width, document.height),
            qcolor(document.background, "#FFFFFF"),
        )
    for obj in document.objects:
        paint_object(painter, obj, document.background)
    painter.restore()


def render_to_image(document: Document, scale: float = 1.0) -> QImage:
    width = max(1, int(round(document.width * scale)))
    height = max(1, int(round(document.height * scale)))
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(qcolor(document.background, "#FFFFFF"))
    painter = QPainter(image)
    painter.scale(scale, scale)
    render_document(painter, document, draw_background=False)
    painter.end()
    return image


def checkerboard_pixmap(size: int = 16, c1: str = "#202329", c2: str = "#262A31") -> QPixmap:
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(qcolor(c1))
    painter = QPainter(pixmap)
    painter.fillRect(0, 0, size, size, qcolor(c2))
    painter.fillRect(size, size, size, size, qcolor(c2))
    painter.end()
    return pixmap


def gradient_preview(
    width: int,
    height: int,
    c1: str,
    c2: str,
    angle: float = 0.0,
    mode: str = "linear",
) -> QPixmap:
    ratio = QApplication.primaryScreen().devicePixelRatio() if QApplication.instance() else 1.0
    pixmap = QPixmap(int(width * ratio), int(height * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = QRectF(0, 0, width, height)
    path = QPainterPath()
    path.addRoundedRect(rect, 9, 9)
    if mode == "radial":
        grad = QRadialGradient(rect.center(), max(width, height) * 0.65)
    elif mode == "solid":
        painter.fillPath(path, qcolor(c1))
        painter.end()
        return pixmap
    else:
        rad = math.radians(angle)
        dx, dy = math.cos(rad), math.sin(rad)
        extent = (abs(width * dx) + abs(height * dy)) / 2.0
        c = rect.center()
        grad = QLinearGradient(
            QPointF(c.x() - dx * extent, c.y() - dy * extent),
            QPointF(c.x() + dx * extent, c.y() + dy * extent),
        )
    grad.setColorAt(0.0, qcolor(c1))
    grad.setColorAt(1.0, qcolor(c2))
    painter.fillPath(path, QBrush(grad))
    painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
    painter.drawPath(path)
    painter.end()
    return pixmap
