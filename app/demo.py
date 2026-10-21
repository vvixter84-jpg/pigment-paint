"""A small demonstration artwork built entirely from editable objects."""

from __future__ import annotations

import math
import random

from .models import Document, DrawObject


def _bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    count: int = 90,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(count + 1):
        t = i / count
        mt = 1.0 - t
        x = (
            mt**3 * p0[0]
            + 3 * mt**2 * t * p1[0]
            + 3 * mt * t**2 * p2[0]
            + t**3 * p3[0]
        )
        y = (
            mt**3 * p0[1]
            + 3 * mt**2 * t * p1[1]
            + 3 * mt * t**2 * p2[1]
            + t**3 * p3[1]
        )
        points.append((x, y))
    return points


def _brush_curve(
    p0,
    p1,
    p2,
    p3,
    *,
    color: str,
    width: float,
    opacity: float = 1.0,
    name: str = "Живописный штрих",
) -> DrawObject:
    points = _bezier(p0, p1, p2, p3, 110)
    widths = [
        width * (0.58 + 0.42 * math.sin(math.pi * i / (len(points) - 1)) ** 0.6)
        for i in range(len(points))
    ]
    obj = DrawObject(
        kind="stroke",
        tool="brush",
        stroke=color,
        stroke_width=width,
        opacity=opacity,
        points=[[x, y] for x, y in points],
        width_profile=widths,
        name=name,
    )
    obj.sanitize()
    return obj


def _spray_cluster(cx: float, cy: float, radius: float, color: str, seed: int = 7) -> DrawObject:
    rng = random.Random(seed)
    dots = []
    for _ in range(330):
        r = radius * math.sqrt(rng.random())
        theta = rng.random() * math.tau
        x = cx + math.cos(theta) * r
        y = cy + math.sin(theta) * r * 0.7
        dot_radius = rng.uniform(0.8, 3.2)
        alpha = rng.uniform(0.08, 0.50)
        dots.append([x, y, dot_radius, alpha])
    obj = DrawObject(
        kind="stroke",
        tool="spray",
        stroke=color,
        stroke_width=40,
        spray_dots=dots,
        points=[[cx - radius, cy - radius], [cx + radius, cy + radius]],
        name="Аэрозоль",
        opacity=0.95,
    )
    obj.sanitize()
    return obj


def _text(
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    family: str,
    size: int,
    color: str,
    bold: bool = False,
    italic: bool = False,
    align: str = "left",
    name: str = "",
    fill_mode: str = "solid",
    fill2: str = "#7D5260",
    angle: float = 0.0,
) -> DrawObject:
    return DrawObject(
        kind="text",
        x=x,
        y=y,
        w=w,
        h=h,
        text=text,
        font_family=family,
        font_size=size,
        bold=bold,
        italic=italic,
        align=align,
        fill=color,
        fill2=fill2,
        fill_mode=fill_mode,
        gradient_angle=angle,
        stroke=color,
        stroke_width=0,
        name=name,
    )


def _circle(
    x: float,
    y: float,
    size: float,
    c1: str,
    c2: str,
    *,
    mode: str = "linear",
    angle: float = 45,
    opacity: float = 1.0,
    name: str = "Круг",
    stroke: str = "#2B1B4D",
    stroke_width: float = 0,
) -> DrawObject:
    return DrawObject(
        kind="ellipse",
        x=x,
        y=y,
        w=size,
        h=size,
        fill=c1,
        fill2=c2,
        fill_mode=mode,
        gradient_angle=angle,
        opacity=opacity,
        stroke=stroke,
        stroke_width=stroke_width,
        name=name,
    )


def build_demo_document() -> Document:
    doc = Document(
        width=1600,
        height=1000,
        background="#F7F3ED",
        name="Демо — Pigment",
    )

    # Soft gradient poster card.
    doc.add(
        DrawObject(
            kind="rounded_rect",
            x=58,
            y=58,
            w=1484,
            h=884,
            corner_radius=54,
            fill_mode="linear",
            fill="#EADDFF",
            fill2="#FFE0EA",
            gradient_angle=32,
            stroke_width=0,
            name="Градиентная подложка",
        )
    )
    doc.add(
        _circle(
            1015,
            104,
            438,
            "#A8D7C4",
            "#8FB9F2",
            mode="radial",
            opacity=0.96,
            name="Мятный круг",
        )
    )
    doc.add(
        DrawObject(
            kind="star",
            x=945,
            y=338,
            w=476,
            h=476,
            star_points=5,
            star_inner=0.43,
            fill_mode="linear",
            fill="#FFF3B0",
            fill2="#EFB8C8",
            gradient_angle=125,
            stroke="#2B1B4D",
            stroke_width=7,
            name="Градиентная звезда",
        )
    )
    doc.add(
        DrawObject(
            kind="polygon",
            points=[
                [840, 745],
                [1010, 865],
                [1185, 700],
                [1300, 860],
                [1010, 910],
            ],
            fill_mode="linear",
            fill="#A8C7FA",
            fill2="#D0BCFF",
            gradient_angle=15,
            stroke="#2B1B4D",
            stroke_width=5,
            opacity=0.88,
            name="Пятиугольник",
        )
    )

    # Typography.
    doc.add(
        _text(
            "PIGMENT",
            122,
            126,
            880,
            246,
            family="Bebas Neue",
            size=214,
            color="#2B1B4D",
            name="Заголовок PIGMENT",
        )
    )
    doc.add(
        _text(
            "PAINT  ·  SHAPES  ·  TYPE",
            132,
            374,
            720,
            48,
            family="JetBrains Mono",
            size=27,
            bold=True,
            color="#6B4A84",
            name="Подзаголовок",
        )
    )
    doc.add(
        _text(
            "рисуй свободно",
            150,
            760,
            530,
            100,
            family="Caveat",
            size=82,
            color="#A34D6D",
            name="Рукописная подпись",
        )
    )

    # White information card.
    doc.add(
        DrawObject(
            kind="rounded_rect",
            x=128,
            y=492,
            w=620,
            h=218,
            corner_radius=36,
            fill_mode="solid",
            fill="#FFFDF9",
            stroke="#FFFFFF",
            stroke_width=2,
            opacity=0.94,
            name="Карточка",
        )
    )
    doc.add(
        _text(
            "Идеи начинаются\nс одного штриха.",
            178,
            548,
            520,
            126,
            family="Manrope",
            size=48,
            bold=True,
            color="#31213F",
            name="Текст на карточке",
        )
    )

    # Painterly strokes and texture.
    doc.add(
        _brush_curve(
            (132, 706),
            (465, 608),
            (760, 860),
            (1260, 690),
            color="#7B5AC7",
            width=36,
            opacity=0.82,
            name="Лиловый мазок",
        )
    )
    doc.add(
        _brush_curve(
            (166, 728),
            (550, 690),
            (935, 874),
            (1370, 748),
            color="#E98BA8",
            width=13,
            opacity=0.92,
            name="Розовый акцент",
        )
    )
    doc.add(
        _brush_curve(
            (1085, 196),
            (1210, 80),
            (1380, 280),
            (1320, 418),
            color="#FFFFFF",
            width=22,
            opacity=0.52,
            name="Белый блик",
        )
    )
    doc.add(_spray_cluster(1340, 845, 132, "#2B1B4D", seed=12))

    # Small palette dots.
    palette = [
        ("#D0BCFF", 640, 838),
        ("#EFB8C8", 704, 838),
        ("#A8D7C4", 768, 838),
        ("#FFD8A8", 832, 838),
        ("#8FB9F2", 896, 838),
    ]
    for color, x, y in palette:
        doc.add(
            _circle(
                x,
                y,
                46,
                color,
                color,
                mode="solid",
                stroke="#2B1B4D",
                stroke_width=2,
                name="Палитра",
            )
        )

    # A pencil line and a calligraphic signature accent.
    pencil_points = _bezier((1150, 610), (1230, 510), (1390, 690), (1300, 850), 55)
    pencil = DrawObject(
        kind="stroke",
        tool="pencil",
        stroke="#2B1B4D",
        stroke_width=3.2,
        points=[[x, y] for x, y in pencil_points],
        name="Карандашная линия",
    )
    pencil.sanitize()
    doc.add(pencil)
    pen_points = _bezier((1318, 640), (1392, 572), (1470, 720), (1276, 748), 60)
    pen = DrawObject(
        kind="stroke",
        tool="pen",
        stroke="#2B1B4D",
        stroke_width=7.0,
        points=[[x, y] for x, y in pen_points],
        width_profile=[
            7.0 * (0.18 + 0.82 * math.sin(math.pi * i / 59) ** 0.7) for i in range(60)
        ],
        name="Перо",
    )
    pen.sanitize()
    doc.add(pen)

    return doc
