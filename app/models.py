"""Document model for Pigment Paint.

The model is deliberately Qt-free so it can be serialized, tested and reused
without a running QApplication.  Every visual element is a vector object, which
is what makes shapes and text editable after they have been committed.
"""

from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field, fields
from typing import Any, Iterable


FORMAT_NAME = "pigment-document"
FORMAT_VERSION = 1


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def point_distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(bx - ax, by - ay)


def distance_to_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return point_distance(px, py, ax, ay)
    t = clamp(((px - ax) * dx + (py - ay) * dy) / length_sq, 0.0, 1.0)
    return point_distance(px, py, ax + t * dx, ay + t * dy)


def distance_to_polyline(px: float, py: float, points: Iterable[tuple[float, float]]) -> float:
    pts = list(points)
    if not pts:
        return float("inf")
    if len(pts) == 1:
        return point_distance(px, py, pts[0][0], pts[0][1])
    return min(
        distance_to_segment(px, py, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        for i in range(len(pts) - 1)
    )


def point_in_polygon(px: float, py: float, points: list[tuple[float, float]]) -> bool:
    """Ray casting test. Points on the boundary count as inside."""
    if len(points) < 3:
        return False
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if distance_to_segment(px, py, xi, yi, xj, yj) <= 0.8:
            return True
        if (yi > py) != (yj > py):
            x_intersect = (xj - xi) * (py - yi) / ((yj - yi) or 1e-12) + xi
            if px < x_intersect:
                inside = not inside
        j = i
    return inside


def polygon_from_bounds(
    x: float, y: float, w: float, h: float, count: int = 5, inner_ratio: float = 0.45
) -> list[tuple[float, float]]:
    """Return an absolute-coordinate star polygon."""
    count = max(3, int(count))
    inner_ratio = clamp(float(inner_ratio), 0.12, 0.95)
    cx, cy = x + w / 2.0, y + h / 2.0
    rx, ry = abs(w) / 2.0, abs(h) / 2.0
    result: list[tuple[float, float]] = []
    for i in range(count * 2):
        angle = -math.pi / 2.0 + i * math.pi / count
        radius = 1.0 if i % 2 == 0 else inner_ratio
        result.append((cx + math.cos(angle) * rx * radius, cy + math.sin(angle) * ry * radius))
    return result


KIND_LABELS = {
    "stroke": "Штрих",
    "line": "Линия",
    "rect": "Прямоугольник",
    "rounded_rect": "Скруглённый прямоугольник",
    "ellipse": "Эллипс",
    "polygon": "Многоугольник",
    "star": "Звезда",
    "text": "Текст",
    "image": "Изображение",
}

TOOL_LABELS = {
    "pencil": "Карандаш",
    "brush": "Кисть",
    "pen": "Перо",
    "spray": "Баллончик",
    "eraser": "Ластик",
}

TOOL_ICONS = {
    "pencil": "pencil",
    "brush": "brush",
    "pen": "pen",
    "spray": "spray",
    "eraser": "eraser",
}

KIND_ICONS = {
    "stroke": "brush",
    "line": "line",
    "rect": "square",
    "rounded_rect": "rounded-square",
    "ellipse": "circle",
    "polygon": "polygon",
    "star": "star",
    "text": "text",
    "image": "image",
}


def object_icon(obj: "DrawObject") -> str:
    if obj.kind == "stroke":
        return TOOL_ICONS.get(obj.tool, "brush")
    return KIND_ICONS.get(obj.kind, "shapes")


def object_label(obj: "DrawObject") -> str:
    if obj.kind == "stroke":
        return TOOL_LABELS.get(obj.tool, "Штрих")
    return KIND_LABELS.get(obj.kind, "Объект")


@dataclass
class DrawObject:
    """A single editable vector object on the artboard.

    Coordinates are stored in artboard pixels.  Point-based objects keep their
    absolute points; resizing maps those points from the old bounding box to the
    new one, so freehand strokes remain fully editable.
    """

    id: str = field(default_factory=new_id)
    kind: str = "rect"
    name: str = ""
    visible: bool = True
    opacity: float = 1.0
    x: float = 0.0
    y: float = 0.0
    w: float = 160.0
    h: float = 120.0
    points: list[list[float]] = field(default_factory=list)
    tool: str = ""
    stroke: str = "#000000"
    stroke_width: float = 2.0
    fill_mode: str = "solid"  # solid | linear | radial | none
    fill: str = "#D0BCFF"
    fill2: str = "#8574C9"
    gradient_angle: float = 45.0
    corner_radius: float = 28.0
    star_points: int = 5
    star_inner: float = 0.45
    text: str = ""
    font_family: str = "Manrope"
    font_size: int = 54
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: str = "left"  # left | center | right
    spray_dots: list[list[float]] = field(default_factory=list)
    width_profile: list[float] = field(default_factory=list)
    image_data: str = ""
    image_format: str = "PNG"

    # ------------------------------------------------------------------ basics
    @property
    def is_point_based(self) -> bool:
        return self.kind in {"stroke", "line", "polygon"}

    @property
    def label(self) -> str:
        if self.name.strip():
            return self.name.strip()
        if self.kind == "text" and self.text.strip():
            first = self.text.strip().splitlines()[0]
            return first[:26] + ("…" if len(first) > 26 else "")
        return object_label(self)

    def copy(self) -> "DrawObject":
        result = copy.deepcopy(self)
        result.id = new_id()
        result.name = (self.name + " копия").strip() if self.name else ""
        return result

    def as_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DrawObject":
        valid = {f.name for f in fields(cls)}
        clean = {key: value for key, value in data.items() if key in valid}
        obj = cls(**clean)
        if not obj.id:
            obj.id = new_id()
        if obj.kind not in KIND_LABELS:
            obj.kind = "rect"
        if obj.fill_mode not in {"solid", "linear", "radial", "none"}:
            obj.fill_mode = "solid"
        if obj.align not in {"left", "center", "right"}:
            obj.align = "left"
        obj.opacity = clamp(float(obj.opacity), 0.0, 1.0)
        obj.stroke_width = max(0.0, float(obj.stroke_width))
        obj.points = [[float(p[0]), float(p[1])] for p in obj.points if len(p) >= 2]
        obj.spray_dots = [
            [float(p[0]), float(p[1]), float(p[2]), float(p[3])]
            for p in obj.spray_dots
            if len(p) >= 4
        ]
        obj.width_profile = [float(v) for v in obj.width_profile]
        return obj

    # ---------------------------------------------------------------- geometry
    def bounds(self) -> tuple[float, float, float, float]:
        if self.is_point_based and self.points:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            x, y = min(xs), min(ys)
            return x, y, max(1.0, max(xs) - x), max(1.0, max(ys) - y)
        return self.x, self.y, max(1.0, self.w), max(1.0, self.h)

    def recalc_bounds(self) -> None:
        if self.is_point_based and self.points:
            self.x, self.y, self.w, self.h = self.bounds()

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy
        if self.points:
            for point in self.points:
                point[0] += dx
                point[1] += dy
        if self.spray_dots:
            for dot in self.spray_dots:
                dot[0] += dx
                dot[1] += dy

    def scale_to(
        self,
        new_x: float,
        new_y: float,
        new_w: float,
        new_h: float,
        old_bounds: tuple[float, float, float, float] | None = None,
    ) -> None:
        new_w = max(1.0, new_w)
        new_h = max(1.0, new_h)
        if self.is_point_based and self.points:
            ox, oy, ow, oh = old_bounds or self.bounds()
            sx = new_w / max(1e-6, ow)
            sy = new_h / max(1e-6, oh)
            for point in self.points:
                point[0] = new_x + (point[0] - ox) * sx
                point[1] = new_y + (point[1] - oy) * sy
            if self.spray_dots:
                for dot in self.spray_dots:
                    dot[0] = new_x + (dot[0] - ox) * sx
                    dot[1] = new_y + (dot[1] - oy) * sy
                    dot[2] *= (sx + sy) / 2.0
            self.x, self.y, self.w, self.h = new_x, new_y, new_w, new_h
            return
        if self.kind == "text":
            # Text reflows inside its new box instead of being stretched.
            self.x, self.y = new_x, new_y
            self.w, self.h = new_w, new_h
            return
        self.x, self.y, self.w, self.h = new_x, new_y, new_w, new_h

    def shape_polygon(self) -> list[tuple[float, float]]:
        if self.kind == "star":
            return polygon_from_bounds(self.x, self.y, self.w, self.h, self.star_points, self.star_inner)
        if self.kind == "polygon":
            return [(p[0], p[1]) for p in self.points]
        return []

    # ---------------------------------------------------------------- hit test
    def hit_test(self, px: float, py: float, tolerance: float = 5.0) -> bool:
        if not self.visible:
            return False
        x, y, w, h = self.bounds()
        in_box = x - tolerance <= px <= x + w + tolerance and y - tolerance <= py <= y + h + tolerance
        if not in_box:
            return False

        if self.kind == "line" and len(self.points) >= 2:
            threshold = max(self.stroke_width / 2.0, 2.0) + tolerance
            return (
                distance_to_segment(
                    px,
                    py,
                    self.points[0][0],
                    self.points[0][1],
                    self.points[1][0],
                    self.points[1][1],
                )
                <= threshold
            )
        if self.kind == "stroke":
            if self.tool == "spray":
                # A spray cloud is forgiving: any point inside its box selects it.
                return in_box
            threshold = max(self.stroke_width / 2.0, 2.0) + tolerance
            return distance_to_polyline(px, py, [(p[0], p[1]) for p in self.points]) <= threshold
        if self.kind == "ellipse":
            cx, cy = x + w / 2.0, y + h / 2.0
            rx, ry = max(1.0, w / 2.0), max(1.0, h / 2.0)
            return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1.0
        if self.kind in {"polygon", "star"}:
            pts = self.shape_polygon()
            if point_in_polygon(px, py, pts):
                return True
            threshold = max(self.stroke_width / 2.0, 2.0) + tolerance
            closed = pts + [pts[0]] if pts else pts
            return distance_to_polyline(px, py, closed) <= threshold
        return True

    # --------------------------------------------------------------- validation
    def sanitize(self) -> None:
        self.w = max(1.0, abs(float(self.w)))
        self.h = max(1.0, abs(float(self.h)))
        self.opacity = clamp(float(self.opacity), 0.05, 1.0)
        self.stroke_width = clamp(float(self.stroke_width), 0.0, 160.0)
        self.font_size = int(clamp(float(self.font_size), 6, 420))
        self.star_points = int(clamp(float(self.star_points), 3, 16))
        self.star_inner = clamp(float(self.star_inner), 0.12, 0.95)
        self.corner_radius = clamp(float(self.corner_radius), 0.0, max(self.w, self.h))
        self.gradient_angle = float(self.gradient_angle) % 360.0
        self.recalc_bounds()


@dataclass
class Document:
    width: int = 1600
    height: int = 1000
    background: str = "#FFFFFF"
    name: str = "Без названия"
    objects: list[DrawObject] = field(default_factory=list)
    format: str = FORMAT_NAME
    version: int = FORMAT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "width": self.width,
            "height": self.height,
            "background": self.background,
            "name": self.name,
            "objects": [obj.as_dict() for obj in self.objects],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        if not isinstance(data, dict):
            raise ValueError("Корень файла должен быть JSON-объектом.")
        if data.get("format") not in (None, FORMAT_NAME):
            raise ValueError("Этот файл создан другой программой.")
        width = int(clamp(float(data.get("width", 1600)), 64, 12000))
        height = int(clamp(float(data.get("height", 1000)), 64, 12000))
        objects: list[DrawObject] = []
        seen: set[str] = set()
        for raw in data.get("objects", []):
            if not isinstance(raw, dict):
                continue
            obj = DrawObject.from_dict(raw)
            if obj.id in seen:
                obj.id = new_id()
            seen.add(obj.id)
            obj.sanitize()
            objects.append(obj)
        return cls(
            width=width,
            height=height,
            background=str(data.get("background", "#FFFFFF")),
            name=str(data.get("name", "Без названия")),
            objects=objects,
            format=FORMAT_NAME,
            version=FORMAT_VERSION,
        )

    def to_json(self) -> str:
        import json

        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "Document":
        import json

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Некорректный JSON: {exc.msg}") from exc
        return cls.from_dict(data)

    def clone(self) -> "Document":
        return Document.from_dict(self.as_dict())

    def object_by_id(self, object_id: str | None) -> DrawObject | None:
        if object_id is None:
            return None
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        return None

    def index_of(self, object_id: str | None) -> int:
        if object_id is None:
            return -1
        for i, obj in enumerate(self.objects):
            if obj.id == object_id:
                return i
        return -1

    def hit_test(self, px: float, py: float, tolerance: float = 5.0) -> DrawObject | None:
        for obj in reversed(self.objects):
            if obj.hit_test(px, py, tolerance):
                return obj
        return None

    def add(self, obj: DrawObject) -> DrawObject:
        obj.sanitize()
        self.objects.append(obj)
        return obj

    def remove(self, object_id: str) -> DrawObject | None:
        index = self.index_of(object_id)
        if index < 0:
            return None
        return self.objects.pop(index)

    def duplicate(self, object_id: str) -> DrawObject | None:
        index = self.index_of(object_id)
        if index < 0:
            return None
        obj = self.objects[index].copy()
        obj.move(24, 24)
        self.objects.insert(index + 1, obj)
        return obj

    def reorder(self, object_id: str, direction: int) -> bool:
        index = self.index_of(object_id)
        target = index + direction
        if index < 0 or target < 0 or target >= len(self.objects):
            return False
        self.objects[index], self.objects[target] = self.objects[target], self.objects[index]
        return True

    def raise_to_top(self, object_id: str) -> bool:
        index = self.index_of(object_id)
        if index < 0 or index == len(self.objects) - 1:
            return False
        self.objects.append(self.objects.pop(index))
        return True

    def send_to_back(self, object_id: str) -> bool:
        index = self.index_of(object_id)
        if index <= 0:
            return False
        self.objects.insert(0, self.objects.pop(index))
        return True


@dataclass
class ToolSettings:
    """Live settings for newly created objects."""

    tool: str = "brush"
    color: str = "#D0BCFF"
    secondary: str = "#EFB8C8"
    size: int = 16
    opacity: float = 100.0
    fill_mode: str = "solid"
    fill2: str = "#7D5260"
    gradient_angle: float = 45.0
    stroke_width: float = 3.0
    shape_kind: str = "rect"
    font_family: str = "Manrope"
    font_size: int = 64
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: str = "left"
    corner_radius: float = 28.0
    star_points: int = 5
    star_inner: float = 0.45
    show_grid: bool = False
