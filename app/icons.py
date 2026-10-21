"""Hand-built Lucide-style icon set and the Pigment logo.

Icons are rendered from inline SVG so every control stays crisp at any DPI and
can be recoloured for Material 3 button states.
"""

from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer

ICON_BODIES: dict[str, str] = {
    "cursor": '<path d="M4.04 4.69a.5.5 0 0 1 .65-.65l16 6.5a.5.5 0 0 1-.06.95l-6.12 1.58a2 2 0 0 0-1.44 1.43l-1.58 6.13a.5.5 0 0 1-.95.06z"/>',
    "hand": '<path d="M18 11V6a2 2 0 0 0-2-2 2 2 0 0 0-2 2"/><path d="M14 10V4a2 2 0 0 0-2-2 2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2 2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>',
    "pencil": '<path d="M21.17 6.81a1 1 0 0 0-3.99-3.99L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35a.5.5 0 0 0 .62.63l4.35-1.32a2 2 0 0 0 .83-.5z"/><path d="m15 5 4 4"/>',
    "brush": '<path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08"/><path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.1 2.49 2.02 4 2.02 2.2 0 4-1.8 4-4.04a3.01 3.01 0 0 0-3-3.02z"/>',
    "pen": '<path d="M15.71 21.29a1 1 0 0 1-1.42 0l-1.58-1.58a1 1 0 0 1 0-1.42l5.58-5.58a1 1 0 0 1 1.42 0l1.58 1.58a1 1 0 0 1 0 1.42z"/><path d="m18 13-1.38-6.87a1 1 0 0 0-.75-.78L3.24 2.03a1 1 0 0 0-1.21 1.2l4.12 12.65a1 1 0 0 0 .78.75L13 18"/><path d="m2.3 2.3 7.29 7.29"/><circle cx="11" cy="11" r="2"/>',
    "spray": '<rect x="8" y="9" width="7" height="12" rx="2"/><path d="M15 13h2a2 2 0 0 0 2-2V7h-4v4"/><path d="M15 6V5a2 2 0 0 0-2-2h-3"/><path d="M19 3h.01M22 3h.01M19 6h.01M22 6h.01M22 9h.01"/>',
    "eraser": '<path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 9 9"/>',
    "fill": '<path d="m19 11-8-8-8.6 8.6a2 2 0 0 0 0 2.8l5.2 5.2c.8.8 2 .8 2.8 0z"/><path d="m5 2 5 5"/><path d="M2 13h15"/><path d="M22 20a2 2 0 1 1-4 0c0-1.6 1.7-2.4 2-4 .3 1.6 2 2.4 2 4z"/>',
    "eyedropper": '<path d="m2 22 1-1h3l9-9"/><path d="M3 21v-3l9-9"/><path d="m15 6 3.4-3.4a2.1 2.1 0 1 1 3 3L18 9l.4.4a2.1 2.1 0 1 1-3 3l-3.8-3.8a2.1 2.1 0 1 1 3-3z"/>',
    "text": '<path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/>',
    "shapes": '<path d="M8.3 10a.7.7 0 0 1-.63-1.08L11.4 3a.7.7 0 0 1 1.2-.04l3.7 5.94A.7.7 0 0 1 15.73 10z"/><rect x="3" y="14" width="7" height="7" rx="1"/><circle cx="17.5" cy="17.5" r="3.5"/>',
    "line": '<path d="M5 19 19 5"/><circle cx="5" cy="19" r="1.5"/><circle cx="19" cy="5" r="1.5"/>',
    "square": '<rect x="3" y="3" width="18" height="18" rx="1.5"/>',
    "rounded-square": '<rect x="3" y="3" width="18" height="18" rx="5"/>',
    "circle": '<circle cx="12" cy="12" r="9"/>',
    "star": '<path d="m12 2.7 2.86 5.8 6.4.93-4.63 4.51 1.1 6.37L12 17.3l-5.73 3.01 1.1-6.37L2.74 9.43l6.4-.93z"/>',
    "polygon": '<path d="M12 2.8 21 9.4l-3.44 10.6H6.44L3 9.4z"/><circle cx="12" cy="2.8" r="1.2"/><circle cx="21" cy="9.4" r="1.2"/><circle cx="17.56" cy="20" r="1.2"/><circle cx="6.44" cy="20" r="1.2"/><circle cx="3" cy="9.4" r="1.2"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5V19"/>',
    "redo": '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5A5.5 5.5 0 0 0 4 14.5V19"/>',
    "file-plus": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M12 18v-6"/><path d="M9 15h6"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "folder-open": '<path d="m6 14 1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    "save": '<path d="M15.2 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8.8z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15-4.35-4.35a2 2 0 0 0-2.83 0L4 21"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6M14 11v6"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2"/>',
    "front": '<rect x="8" y="8" width="9" height="9" rx="2"/><path d="M4 11V6a2 2 0 0 1 2-2h5"/><path d="M20 13v5a2 2 0 0 1-2 2h-5"/>',
    "back": '<rect x="7" y="7" width="9" height="9" rx="2"/><path d="M4 13v5a2 2 0 0 0 2 2h5"/><path d="M20 11V6a2 2 0 0 0-2-2h-5"/>',
    "arrow-up": '<path d="m18 15-6-6-6 6"/>',
    "arrow-down": '<path d="m6 9 6 6 6-6"/>',
    "arrow-left": '<path d="m15 18-6-6 6-6"/>',
    "arrow-right": '<path d="m9 18 6-6-6-6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "fit": '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    "more": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    "keyboard": '<rect x="2" y="4" width="20" height="16" rx="3"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M8 16h8"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
    "palette": '<circle cx="13.5" cy="6.5" r=".6"/><circle cx="17.5" cy="10.5" r=".6"/><circle cx="8.5" cy="7.5" r=".6"/><circle cx="6.5" cy="12.5" r=".6"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.69 0-.44-.18-.84-.44-1.13-.29-.29-.44-.65-.44-1.12a1.64 1.64 0 0 1 1.67-1.67h2c3.05 0 5.56-2.5 5.56-5.55C22 6.01 17.46 2 12 2z"/>',
    "gradient": '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M3 14h18M3 9h18"/><path d="M17 7 10 17" opacity=".55"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M10.7 5.1A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-2.2 3.2"/><path d="M6.6 6.6A17.4 17.4 0 0 0 2 12s3.5 7 10 7a10.6 10.6 0 0 0 5.4-1.5"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="m2 2 20 20"/>',
    "swap": '<path d="M7 4 3 8l4 4"/><path d="M3 8h13a4 4 0 0 1 0 8h-2"/><path d="m17 20 4-4-4-4"/><path d="M21 16H8"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "sparkles": '<path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/><path d="m19 15 .7 2.1 2.1.7-2.1.7L19 21l-.7-2.1-2.1-.7 2.1-.7z"/><path d="m5 14 .6 1.8 1.8.6-1.8.6L5 19l-.6-1.8-1.8-.6 1.8-.6z"/>',
    "layers": '<path d="m12 2 9 5-9 5-9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/><path d="M1 14h6M9 8h6M17 16h6"/>',
    "rotate": '<path d="M21 12a9 9 0 1 1-3.2-6.9"/><path d="M21 3v6h-6"/>',
}

# Some icons read better as filled shapes (e.g. star).
FILLED = {"star"}


@lru_cache(maxsize=512)
def _render_svg(svg: str, size: int, dpr: int = 2) -> QPixmap:
    pixmap = QPixmap(size * dpr, size * dpr)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(svg.encode("utf-8"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def svg_string(name: str, color: str, stroke_width: float = 1.9) -> str:
    body = ICON_BODIES.get(name, ICON_BODIES["info"])
    fill = color if name in FILLED else "none"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" '
        f'fill="{fill}" stroke="{color}" stroke-width="{stroke_width}" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )


def make_icon(
    name: str,
    color: str = "#D7D2E0",
    active: str = "#EADDFF",
    disabled: str = "#615E68",
    size: int = 24,
) -> QIcon:
    icon = QIcon()
    icon.addPixmap(_render_svg(svg_string(name, color), size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_render_svg(svg_string(name, active), size), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(_render_svg(svg_string(name, active), size), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(_render_svg(svg_string(name, active), size), QIcon.Mode.Active, QIcon.State.On)
    icon.addPixmap(
        _render_svg(svg_string(name, disabled), size), QIcon.Mode.Disabled, QIcon.State.Off
    )
    return icon


def make_pixmap(name: str, color: str = "#D7D2E0", size: int = 24) -> QPixmap:
    return _render_svg(svg_string(name, color), size)


def color_icon(color: str, size: int = 18, ring: str = "#FFFFFF55") -> QIcon:
    dpr = 2
    pixmap = QPixmap(size * dpr, size * dpr)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(ring), 1))
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), size * 0.32, size * 0.32)
    painter.end()
    return QIcon(pixmap)


def logo_pixmap(size: int = 40) -> QPixmap:
    dpr = 2
    pixmap = QPixmap(size * dpr, size * dpr)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = QRectF(0.8, 0.8, size - 1.6, size - 1.6)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#D0BCFF"))
    gradient.setColorAt(0.55, QColor("#B8A1F2"))
    gradient.setColorAt(1.0, QColor("#EFB8C8"))
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.29, size * 0.29)
    painter.fillPath(path, gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(45, 27, 78, 235))
    painter.drawEllipse(QPointF(size * 0.68, size * 0.34), size * 0.075, size * 0.075)
    stroke = QPainterPath()
    stroke.moveTo(size * 0.22, size * 0.68)
    stroke.cubicTo(
        size * 0.38,
        size * 0.38,
        size * 0.57,
        size * 0.82,
        size * 0.79,
        size * 0.52,
    )
    pen = QPen(QColor(45, 27, 78), max(2.0, size * 0.085))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawPath(stroke)
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(size))
    return icon
