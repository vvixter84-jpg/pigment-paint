
from app.demo import build_demo_document
from app.models import (
    Document,
    DrawObject,
    point_in_polygon,
    polygon_from_bounds,
)


def test_document_roundtrip_preserves_objects_and_styles():
    document = Document(width=1200, height=800, background="#F7F3ED", name="Roundtrip")
    star = DrawObject(
        kind="star",
        x=100,
        y=80,
        w=300,
        h=260,
        fill_mode="linear",
        fill="#FFD8A8",
        fill2="#EFB8C8",
        gradient_angle=72,
        stroke="#2B1B4D",
        stroke_width=6,
        star_points=7,
        star_inner=0.5,
        name="Семилучевая",
    )
    text = DrawObject(
        kind="text",
        x=20,
        y=30,
        w=500,
        h=100,
        text="Привет, Pigment!",
        font_family="Caveat",
        font_size=64,
        bold=True,
        fill="#2B1B4D",
        name="Текст",
    )
    stroke = DrawObject(
        kind="stroke",
        tool="brush",
        points=[[10, 10], [40, 30], [70, 25]],
        width_profile=[12, 10, 8],
        stroke="#7B5AC7",
        stroke_width=12,
    )
    document.objects.extend([star, text, stroke])
    restored = Document.from_json(document.to_json())
    assert restored.width == 1200
    assert restored.height == 800
    assert restored.background == "#F7F3ED"
    assert len(restored.objects) == 3
    assert restored.objects[0].fill_mode == "linear"
    assert restored.objects[0].star_points == 7
    assert restored.objects[1].font_family == "Caveat"
    assert restored.objects[1].text == "Привет, Pigment!"
    assert len(restored.objects[2].points) == 3
    assert restored.objects[2].width_profile == [12, 10, 8]
    assert restored.objects[0].id == star.id


def test_move_and_scale_point_based_object():
    obj = DrawObject(
        kind="polygon",
        points=[[10, 10], [110, 10], [60, 60]],
        fill="#fff",
    )
    obj.sanitize()
    assert obj.bounds() == (10, 10, 100, 50)
    obj.move(15, -5)
    assert obj.bounds() == (25, 5, 100, 50)
    obj.scale_to(0, 0, 200, 100)
    assert obj.bounds() == (0, 0, 200, 100)
    assert obj.points[0] == [0.0, 0.0]
    assert obj.points[1] == [200.0, 0.0]
    assert obj.points[2] == [100.0, 100.0]


def test_hit_testing_shapes_and_lines():
    ellipse = DrawObject(kind="ellipse", x=100, y=100, w=200, h=100, fill="#fff")
    assert ellipse.hit_test(200, 150)
    assert not ellipse.hit_test(100, 100)
    line = DrawObject(kind="line", points=[[0, 0], [300, 300]], stroke_width=4)
    line.sanitize()
    assert line.hit_test(150, 151, tolerance=4)
    assert not line.hit_test(150, 200, tolerance=4)
    star = DrawObject(kind="star", x=0, y=0, w=200, h=200, star_points=5, fill="#fff")
    assert star.hit_test(100, 100)
    assert not star.hit_test(0, 200)


def test_star_and_polygon_geometry():
    points = polygon_from_bounds(0, 0, 200, 100, count=5, inner_ratio=0.45)
    assert len(points) == 10
    assert point_in_polygon(100, 50, points)
    assert not point_in_polygon(-20, 50, points)
    assert 190 < max(x for x, _ in points) <= 200


def test_document_reordering_and_duplication():
    document = Document()
    first = DrawObject(name="first")
    second = DrawObject(name="second")
    document.add(first)
    document.add(second)
    assert document.raise_to_top(first.id)
    assert document.objects[-1].id == first.id
    assert document.send_to_back(first.id)
    assert document.objects[0].id == first.id
    copied = document.duplicate(first.id)
    assert copied is not None
    assert copied.id != first.id
    assert len(document.objects) == 3


def test_demo_document_contains_all_editable_types():
    document = build_demo_document()
    kinds = {obj.kind for obj in document.objects}
    tools = {obj.tool for obj in document.objects if obj.kind == "stroke"}
    assert document.width == 1600
    assert document.height == 1000
    assert "rounded_rect" in kinds
    assert "ellipse" in kinds
    assert "star" in kinds
    assert "polygon" in kinds
    assert "text" in kinds
    assert "brush" in tools
    assert "spray" in tools
    assert len(document.objects) >= 15
