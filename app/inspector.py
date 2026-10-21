"""Right-hand Material 3 inspector: tool options, object properties, layers."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .canvas import Canvas
from .icons import make_icon, make_pixmap
from .models import (
    DrawObject,
    KIND_LABELS,
    TOOL_LABELS,
    object_icon,
    object_label,
)
from .theme import (
    PRIMARY,
    TEXT_MUTED,
    free_font_families,
)
from .widgets import (
    ColorControl,
    FontCombo,
    GradientPreview,
    LabeledSlider,
    SegmentedControl,
    SwatchRow,
    icon_button,
    separator,
)


def _card() -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(13, 12, 13, 13)
    layout.setSpacing(10)
    return card, layout


def _title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionHint")
    label.setWordWrap(True)
    return label


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(int(value))
    spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
    return spin


def _tool_header(icon: str, title: str, subtitle: str) -> QFrame:
    card, layout = _card()
    row = QHBoxLayout()
    row.setSpacing(12)
    badge = QLabel()
    badge.setFixedSize(44, 44)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet("background: #2C2838; border-radius: 14px;")
    badge.setPixmap(make_pixmap(icon, PRIMARY, 23))
    row.addWidget(badge)
    text = QVBoxLayout()
    text.setSpacing(1)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 15px; font-weight: 800; color: #EAE6F0;")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("SectionHint")
    subtitle_label.setWordWrap(True)
    text.addWidget(title_label)
    text.addWidget(subtitle_label)
    row.addLayout(text, 1)
    layout.addLayout(row)
    return card


class Inspector(QFrame):
    colorsChanged = pyqtSignal(str, str)
    settingsChanged = pyqtSignal()
    statusMessage = pyqtSignal(str)

    def __init__(self, canvas: Canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setObjectName("Inspector")
        self.setFixedWidth(328)
        self._syncing_list = False
        self._syncing_geometry = False
        self._last_object_signature: tuple | None = None
        self._object_geometry_spins: dict[str, QSpinBox] = {}
        self._tool_color_control: ColorControl | None = None
        self._tool_size_slider: LabeledSlider | None = None
        self._text_debounce = QTimer(self)
        self._text_debounce.setSingleShot(True)
        self._text_debounce.setInterval(420)
        self._text_debounce.timeout.connect(self._apply_text_field)
        self._pending_text: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 0, 0)
        title = QLabel("Инспектор")
        title.setObjectName("InspectorTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.badge = QLabel("M3")
        self.badge.setObjectName("PrimaryBadge")
        header.addWidget(self.badge)
        root.addLayout(header)

        tabs = QHBoxLayout()
        tabs.setSpacing(14)
        self.properties_tab = QToolButton()
        self.properties_tab.setObjectName("TabButton")
        self.properties_tab.setText("Свойства")
        self.properties_tab.setCheckable(True)
        self.properties_tab.setChecked(True)
        self.properties_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.objects_tab = QToolButton()
        self.objects_tab.setObjectName("TabButton")
        self.objects_tab.setText("Объекты")
        self.objects_tab.setCheckable(True)
        self.objects_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        tabs.addWidget(self.properties_tab)
        tabs.addWidget(self.objects_tab)
        tabs.addStretch(1)
        root.addLayout(tabs)
        root.addWidget(separator())

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.props_scroll = QScrollArea()
        self.props_scroll.setWidgetResizable(True)
        self.props_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack.addWidget(self.props_scroll)

        self.objects_page = QWidget()
        objects_layout = QVBoxLayout(self.objects_page)
        objects_layout.setContentsMargins(0, 4, 0, 0)
        objects_layout.setSpacing(10)
        objects_header = QHBoxLayout()
        self.objects_count = QLabel("0 объектов")
        self.objects_count.setObjectName("Subtle")
        objects_header.addWidget(self.objects_count)
        objects_header.addStretch(1)
        self.visibility_button = icon_button("eye", "Показать / скрыть", size=17)
        self.visibility_button.clicked.connect(self.canvas.toggle_selected_visibility)
        self.duplicate_button = icon_button("copy", "Дублировать  Ctrl+D", size=17)
        self.duplicate_button.clicked.connect(self.canvas.duplicate_selected)
        self.delete_button = icon_button("trash", "Удалить  Del", size=17)
        self.delete_button.clicked.connect(self.canvas.delete_selected)
        objects_header.addWidget(self.visibility_button)
        objects_header.addWidget(self.duplicate_button)
        objects_header.addWidget(self.delete_button)
        objects_layout.addLayout(objects_header)
        objects_layout.addWidget(
            _hint("Верх списка — ближе к зрителю. Выберите объект, чтобы изменить его.")
        )
        self.object_list = QListWidget()
        self.object_list.setIconSize(QSize(18, 18))
        self.object_list.setSpacing(1)
        self.object_list.currentItemChanged.connect(self._object_item_selected)
        objects_layout.addWidget(self.object_list, 1)
        self.empty_objects = QLabel("На холсте пока нет объектов.\nНачните с кисти или фигуры.")
        self.empty_objects.setObjectName("EmptyHint")
        self.empty_objects.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_objects.setWordWrap(True)
        self.empty_objects.setMinimumHeight(96)
        objects_layout.addWidget(self.empty_objects)
        order_row = QHBoxLayout()
        order_row.setSpacing(8)
        up = QPushButton("Выше")
        up.setIcon(make_icon("arrow-up", TEXT_MUTED))
        up.clicked.connect(lambda: self.canvas.reorder_selected_step(1))
        down = QPushButton("Ниже")
        down.setIcon(make_icon("arrow-down", TEXT_MUTED))
        down.clicked.connect(lambda: self.canvas.reorder_selected_step(-1))
        order_row.addWidget(up)
        order_row.addWidget(down)
        objects_layout.addLayout(order_row)
        self.stack.addWidget(self.objects_page)

        self.properties_tab.clicked.connect(lambda: self._show_tab(0))
        self.objects_tab.clicked.connect(lambda: self._show_tab(1))
        self.refresh()

    # ------------------------------------------------------------------- tabs
    def _show_tab(self, index: int) -> None:
        self.properties_tab.setChecked(index == 0)
        self.objects_tab.setChecked(index == 1)
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.refresh_objects()

    def show_objects(self) -> None:
        self._show_tab(1)

    # ----------------------------------------------------------------- refresh
    def refresh(self) -> None:
        obj = self.canvas.selected_object()
        if obj is not None:
            self._build_object_properties(obj)
        else:
            self._build_tool_properties()
        self.refresh_objects()
        self._update_object_actions()

    def refresh_geometry(self) -> None:
        obj = self.canvas.selected_object()
        if obj is None:
            return
        x, y, w, h = obj.bounds()
        values = {"x": x, "y": y, "w": w, "h": h}
        self._syncing_geometry = True
        for key, spin in self._object_geometry_spins.items():
            spin.blockSignals(True)
            spin.setValue(int(round(values[key])))
            spin.blockSignals(False)
        self._syncing_geometry = False

    def invalidate(self) -> None:
        """Force a rebuild of the layers list and property inspector."""
        self._last_object_signature = None
        self.refresh()

    def refresh_objects(self) -> None:
        objects = self.canvas.document.objects
        signature = tuple(
            (obj.id, obj.label, obj.visible, object_icon(obj)) for obj in reversed(objects)
        )
        if signature != self._last_object_signature:
            self._last_object_signature = signature
            self._syncing_list = True
            self.object_list.clear()
            for obj in reversed(objects):
                item = QListWidgetItem(
                    QIcon(make_pixmap(object_icon(obj), TEXT_MUTED, 17)),
                    obj.label + ("  ·  скрыт" if not obj.visible else ""),
                )
                item.setData(Qt.ItemDataRole.UserRole, obj.id)
                item.setToolTip(
                    f"{object_label(obj)} · {round(obj.w)} × {round(obj.h)} px"
                )
                self.object_list.addItem(item)
            self._syncing_list = False
        self._syncing_list = True
        selected_id = self.canvas.selected_id
        row = -1
        for index in range(self.object_list.count()):
            item = self.object_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == selected_id:
                row = index
                break
        self.object_list.setCurrentRow(row)
        self._syncing_list = False
        count = len(objects)
        self.objects_count.setText(f"{count} объект" if count == 1 else f"{count} объектов")
        self.objects_tab.setText(f"Объекты" + (f"  {count}" if count else ""))
        self.empty_objects.setVisible(count == 0)
        self.object_list.setVisible(count > 0)
        self._update_object_actions()

    def _update_object_actions(self) -> None:
        obj = self.canvas.selected_object()
        enabled = obj is not None
        self.visibility_button.setEnabled(enabled)
        self.duplicate_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        if obj is not None:
            self.visibility_button.setIcon(
                make_icon("eye-off" if obj.visible else "eye", TEXT_MUTED, PRIMARY)
            )

    def _object_item_selected(self, current: QListWidgetItem | None, previous=None) -> None:
        if self._syncing_list or current is None:
            return
        object_id = current.data(Qt.ItemDataRole.UserRole)
        if object_id and object_id != self.canvas.selected_id:
            self.canvas.select(object_id)

    # ------------------------------------------------------------------ helpers
    def _new_props_content(self) -> tuple[QWidget, QVBoxLayout]:
        content = QWidget()
        content.setObjectName("PropsContent")
        content.setMinimumWidth(0)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(1, 4, 4, 10)
        layout.setSpacing(13)
        return content, layout

    def _show_props_content(self, content: QWidget) -> None:
        # A QScrollArea does not relayout a replacement widget that is already
        # visible unless its size hint is resolved before installation.
        content.adjustSize()
        self.props_scroll.setWidget(content)
        content.show()
        content.layout().activate()

    def _set_primary(self, value: str) -> None:
        self.canvas.settings.color = value
        if self._tool_color_control is not None:
            self._tool_color_control.set_color(value)
        self.canvas.update()
        self.colorsChanged.emit(self.canvas.settings.color, self.canvas.settings.secondary)
        self.settingsChanged.emit()

    def _set_secondary(self, value: str) -> None:
        self.canvas.settings.secondary = value
        self.colorsChanged.emit(self.canvas.settings.color, self.canvas.settings.secondary)
        self.settingsChanged.emit()

    def _set_fill_settings(self, values: dict) -> None:
        for key, value in values.items():
            setattr(self.canvas.settings, key, value)
        self.canvas.update()
        self.settingsChanged.emit()

    def _apply_text_field(self) -> None:
        if self._pending_text is None:
            return
        obj = self.canvas.selected_object()
        if obj is None or obj.kind != "text":
            return
        if obj.text != self._pending_text:
            self.canvas.update_selected(text=self._pending_text)
        self._pending_text = None

    # --------------------------------------------------------------- object UI
    def _build_object_properties(self, obj: DrawObject) -> None:
        self._tool_color_control = None
        self._tool_size_slider = None
        content, layout = self._new_props_content()

        header, header_layout = _card()
        row = QHBoxLayout()
        row.setSpacing(11)
        badge = QLabel()
        badge.setFixedSize(42, 42)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("background: #2C2838; border-radius: 13px;")
        badge.setPixmap(make_pixmap(object_icon(obj), PRIMARY, 22))
        row.addWidget(badge)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        name = QLabel(obj.label)
        name.setStyleSheet("font-size: 14px; font-weight: 800; color: #EAE6F0;")
        name.setWordWrap(True)
        name.setMinimumWidth(0)
        type_label = QLabel(KIND_LABELS.get(obj.kind, "Объект"))
        type_label.setObjectName("SectionHint")
        titles.addWidget(name)
        titles.addWidget(type_label)
        row.addLayout(titles, 1)
        eye = icon_button("eye-off" if obj.visible else "eye", "Показать / скрыть", size=17)
        eye.clicked.connect(self._toggle_visibility_and_refresh)
        row.addWidget(eye)
        header_layout.addLayout(row)
        layout.addWidget(header)

        layout.addWidget(self._geometry_card(obj))
        if obj.kind in {"rect", "rounded_rect", "ellipse", "star", "polygon"}:
            layout.addWidget(self._shape_style_card(obj))
        elif obj.kind == "line":
            layout.addWidget(self._line_style_card(obj))
        elif obj.kind == "stroke":
            layout.addWidget(self._stroke_style_card(obj))
        elif obj.kind == "text":
            layout.addWidget(self._text_style_card(obj))
        elif obj.kind == "image":
            layout.addWidget(self._image_card(obj))
        layout.addWidget(self._opacity_card(obj))
        layout.addWidget(self._order_card())
        layout.addStretch(1)
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._show_props_content(content)
        self._update_object_actions()

    def _toggle_visibility_and_refresh(self) -> None:
        obj = self.canvas.selected_object()
        if obj is None:
            return
        self.canvas.update_selected(visible=not obj.visible)
        self.refresh()

    def _geometry_card(self, obj: DrawObject) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Геометрия"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        x, y, w, h = obj.bounds()
        definitions = [
            ("x", "X", int(round(x)), -50000, 50000),
            ("y", "Y", int(round(y)), -50000, 50000),
            ("w", "Ш", int(round(w)), 1, 50000),
            ("h", "В", int(round(h)), 1, 50000),
        ]
        self._object_geometry_spins = {}
        for index, (key, label, value, minimum, maximum) in enumerate(definitions):
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(6)
            caption = _field_label(label)
            caption.setFixedWidth(14)
            spin = _spin(minimum, maximum, value)
            spin.setMinimumWidth(70)
            spin.valueChanged.connect(self._geometry_spin_changed)
            cell_layout.addWidget(caption)
            cell_layout.addWidget(spin, 1)
            self._object_geometry_spins[key] = spin
            grid.addWidget(cell, index // 2, index % 2)
        layout.addLayout(grid)
        if obj.kind in {"stroke", "line", "polygon"}:
            note = _hint("Размер меняет геометрию объекта; толщина линии сохраняется.")
            layout.addWidget(note)
        return card

    def _geometry_spin_changed(self) -> None:
        if self._syncing_geometry:
            return
        spins = self._object_geometry_spins
        if not spins:
            return
        self.canvas.set_selected_bounds(
            x=spins["x"].value(),
            y=spins["y"].value(),
            w=spins["w"].value(),
            h=spins["h"].value(),
        )

    def _fill_controls(
        self,
        mode: str,
        c1: str,
        c2: str,
        angle: float,
        on_change: Callable[[str, str], None],
    ) -> tuple[QWidget, dict[str, QWidget]]:
        """Build a reusable fill editor and return show/hide targets."""
        wrapper = QWidget()
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_label = _field_label("Тип")
        mode_label.setFixedWidth(50)
        combo = QComboBox()
        combo.setMinimumWidth(0)
        combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        combo.setMinimumContentsLength(9)
        for label, value in (
            ("Сплошной цвет", "solid"),
            ("Линейный градиент", "linear"),
            ("Радиальный градиент", "radial"),
            ("Без заливки", "none"),
        ):
            combo.addItem(label, value)
        index = combo.findData(mode)
        combo.setCurrentIndex(max(0, index))
        combo.currentIndexChanged.connect(
            lambda _index: on_change("mode", str(combo.currentData()))
        )
        mode_row.addWidget(mode_label)
        mode_row.addWidget(combo, 1)
        outer.addLayout(mode_row)

        preview = GradientPreview()
        preview.set_values(c1, c2, angle, mode if mode in {"linear", "radial"} else "solid")
        outer.addWidget(preview)

        solid_control = ColorControl(c1)
        solid_control.colorChanged.connect(lambda value: on_change("fill", value))
        outer.addWidget(solid_control)

        gradient_stops = QWidget()
        stops_layout = QVBoxLayout(gradient_stops)
        stops_layout.setContentsMargins(0, 0, 0, 0)
        stops_layout.setSpacing(7)
        first = ColorControl(c1)
        second = ColorControl(c2)
        first.colorChanged.connect(lambda value: on_change("fill", value))
        second.colorChanged.connect(lambda value: on_change("fill2", value))
        stops_layout.addWidget(first)
        stops_layout.addWidget(second)
        outer.addWidget(gradient_stops)

        angle_slider = LabeledSlider("Угол градиента", 0, 359, int(angle), "°")
        angle_slider.valueChanged.connect(lambda value: on_change("angle", str(value)))
        outer.addWidget(angle_slider)

        def update_visibility(current_mode: str) -> None:
            solid_control.setVisible(current_mode == "solid")
            gradient_stops.setVisible(current_mode in {"linear", "radial"})
            angle_slider.setVisible(current_mode == "linear")
            preview.setVisible(current_mode != "none")
            text = {
                "solid": "Один цвет заливки.",
                "linear": "Два цвета с настраиваемым углом.",
                "radial": "Плавный переход от центра к краям.",
                "none": "Только контур без заливки.",
            }.get(current_mode, "")
            mode_hint.setText(text)

        def update_preview() -> None:
            preview.set_values(
                first.color(),
                second.color(),
                angle_slider.value(),
                str(combo.currentData()) if combo.currentData() in {"linear", "radial"} else "solid",
            )

        first.colorChanged.connect(lambda _v: update_preview())
        second.colorChanged.connect(lambda _v: update_preview())
        angle_slider.valueChanged.connect(lambda _v: update_preview())
        combo.currentIndexChanged.connect(
            lambda _i: (
                update_visibility(str(combo.currentData())),
                update_preview(),
            )
        )
        mode_hint = _hint("")
        outer.addWidget(mode_hint)
        update_visibility(mode)
        return wrapper, {
            "mode": combo,
            "preview": preview,
            "solid": solid_control,
            "gradient": gradient_stops,
            "angle": angle_slider,
            "hint": mode_hint,
            "update": update_visibility,  # type: ignore[dict-item]
        }

    def _shape_style_card(self, obj: DrawObject) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Заливка"))
        container, controls = self._fill_controls(
            obj.fill_mode,
            obj.fill,
            obj.fill2,
            obj.gradient_angle,
            self._shape_fill_changed,
        )
        layout.addWidget(container)

        if obj.kind == "rounded_rect":
            radius = LabeledSlider("Радиус углов", 0, 240, int(obj.corner_radius), " px")
            radius.valueChanged.connect(lambda value: self.canvas.update_selected(corner_radius=float(value)))
            layout.addWidget(radius)
        if obj.kind == "star":
            points = LabeledSlider("Лучей", 3, 16, obj.star_points, "")
            points.valueChanged.connect(lambda value: self.canvas.update_selected(star_points=value))
            layout.addWidget(points)
            inner = LabeledSlider("Глубина лучей", 15, 90, int(obj.star_inner * 100), "%")
            inner.valueChanged.connect(lambda value: self.canvas.update_selected(star_inner=value / 100.0))
            layout.addWidget(inner)

        layout.addWidget(separator())
        layout.addWidget(_title("Обводка"))
        stroke = ColorControl(obj.stroke, "Цвет обводки")
        stroke.colorChanged.connect(lambda value: self.canvas.update_selected(stroke=value))
        layout.addWidget(stroke)
        width = LabeledSlider("Толщина", 0, 80, int(obj.stroke_width), " px")
        width.valueChanged.connect(lambda value: self.canvas.update_selected(stroke_width=float(value)))
        layout.addWidget(width)
        return card

    def _line_style_card(self, obj: DrawObject) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Линия"))
        color = ColorControl(obj.stroke, "Цвет линии")
        color.colorChanged.connect(lambda value: self.canvas.update_selected(stroke=value))
        layout.addWidget(color)
        width = LabeledSlider("Толщина", 1, 80, int(obj.stroke_width), " px")
        width.valueChanged.connect(lambda value: self.canvas.update_selected(stroke_width=float(value)))
        layout.addWidget(width)
        return card

    def _stroke_style_card(self, obj: DrawObject) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Штрих"))
        layout.addWidget(_hint(f"Инструмент: {TOOL_LABELS.get(obj.tool, 'Кисть')}"))
        color = ColorControl(obj.stroke, "Цвет штриха")
        color.colorChanged.connect(lambda value: self.canvas.update_selected(stroke=value))
        layout.addWidget(color)
        width = LabeledSlider("Толщина", 1, 180, int(obj.stroke_width), " px")
        width.valueChanged.connect(lambda value: self.canvas.update_selected(stroke_width=float(value)))
        layout.addWidget(width)
        return card

    def _text_style_card(self, obj: DrawObject) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Текст"))
        editor = QTextEdit()
        editor.setPlainText(obj.text)
        editor.setMinimumHeight(82)
        editor.setMaximumHeight(112)
        editor.setPlaceholderText("Введите текст…")
        editor.textChanged.connect(lambda: self._queue_text(editor.toPlainText()))

        hint = _hint("Двойной клик по тексту на холсте открывает редактор на месте.")
        layout.addWidget(editor)
        layout.addWidget(hint)

        font_row = QHBoxLayout()
        font_row.setSpacing(7)
        self._font_combo = FontCombo(free_font_families(), obj.font_family)
        self._font_combo.currentTextChanged.connect(
            lambda value: self.canvas.update_selected(font_family=value)
        )
        font_row.addWidget(self._font_combo, 1)
        layout.addLayout(font_row)

        size_row = QHBoxLayout()
        size_row.setSpacing(7)
        size_label = _field_label("Размер")
        size = _spin(6, 420, obj.font_size)
        size.setFixedWidth(74)
        size.valueChanged.connect(lambda value: self.canvas.update_selected(font_size=value))
        style_bold = QToolButton()
        style_bold.setObjectName("SegmentButton")
        style_bold.setText("B")
        style_bold.setCheckable(True)
        style_bold.setChecked(obj.bold)
        style_bold.setToolTip("Жирный")
        style_bold.setStyleSheet("font-weight: 900;")
        style_italic = QToolButton()
        style_italic.setObjectName("SegmentButton")
        style_italic.setText("I")
        style_italic.setCheckable(True)
        style_italic.setChecked(obj.italic)
        style_italic.setToolTip("Курсив")
        style_italic.setStyleSheet("font-style: italic; font-family: Georgia;")
        style_underline = QToolButton()
        style_underline.setObjectName("SegmentButton")
        style_underline.setText("U")
        style_underline.setCheckable(True)
        style_underline.setChecked(obj.underline)
        style_underline.setToolTip("Подчёркнутый")
        style_underline.setStyleSheet("text-decoration: underline;")
        style_bold.toggled.connect(lambda value: self.canvas.update_selected(bold=value))
        style_italic.toggled.connect(lambda value: self.canvas.update_selected(italic=value))
        style_underline.toggled.connect(lambda value: self.canvas.update_selected(underline=value))
        size_row.addWidget(size_label)
        size_row.addWidget(size)
        size_row.addStretch(1)
        size_row.addWidget(style_bold)
        size_row.addWidget(style_italic)
        size_row.addWidget(style_underline)
        layout.addLayout(size_row)

        align = SegmentedControl(
            [("left", "Слева"), ("center", "Центр"), ("right", "Справа")],
            obj.align,
        )
        align.valueChanged.connect(lambda value: self.canvas.update_selected(align=value))
        layout.addWidget(align)

        layout.addWidget(separator())
        layout.addWidget(_title("Цвет текста"))
        fill_mode = QComboBox()
        fill_mode.setMinimumWidth(0)
        fill_mode.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        fill_mode.setMinimumContentsLength(9)
        for label, value in (("Сплошной", "solid"), ("Линейный градиент", "linear"), ("Радиальный градиент", "radial")):
            fill_mode.addItem(label, value)
        index = fill_mode.findData(obj.fill_mode if obj.fill_mode != "none" else "solid")
        fill_mode.setCurrentIndex(max(0, index))
        fill_mode.currentIndexChanged.connect(
            lambda _i: self._text_fill_mode_changed(str(fill_mode.currentData()))
        )
        layout.addWidget(fill_mode)
        color = ColorControl(obj.fill, "Цвет текста")
        color.colorChanged.connect(lambda value: self.canvas.update_selected(fill=value))
        layout.addWidget(color)
        if obj.fill_mode in {"linear", "radial"}:
            color2 = ColorControl(obj.fill2, "Второй цвет")
            color2.colorChanged.connect(lambda value: self.canvas.update_selected(fill2=value))
            layout.addWidget(color2)

        preview = QLabel("Pigment")
        preview.setMinimumHeight(46)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_font = QFont(obj.font_family)
        preview_font.setPixelSize(min(28, obj.font_size))
        preview_font.setBold(obj.bold)
        preview_font.setItalic(obj.italic)
        preview_font.setUnderline(obj.underline)
        preview.setFont(preview_font)
        preview.setStyleSheet(
            "background: #20242B; border: 1px solid #2D323B; border-radius: 11px; color: #EAE6F0; padding: 6px;"
        )
        layout.addWidget(preview)
        return card

    def _queue_text(self, text: str) -> None:
        self._pending_text = text
        self._text_debounce.start()

    def _text_fill_mode_changed(self, value: str) -> None:
        self.canvas.update_selected(fill_mode=value)
        scroll = self.props_scroll.verticalScrollBar().value()
        self.refresh()
        QTimer.singleShot(0, lambda: self.props_scroll.verticalScrollBar().setValue(scroll))

    def _image_card(self, obj: DrawObject) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Изображение"))
        layout.addWidget(_hint("Растровое изображение. Пропорции можно менять в разделе «Геометрия»."))
        fit = QPushButton("Вписать в холст")
        fit.clicked.connect(self._fit_image_to_canvas)
        layout.addWidget(fit)
        return card

    def _fit_image_to_canvas(self) -> None:
        obj = self.canvas.selected_object()
        if obj is None or obj.kind != "image":
            return
        image_w = max(1.0, obj.w)
        image_h = max(1.0, obj.h)
        scale = min(
            (self.canvas.document.width * 0.72) / image_w,
            (self.canvas.document.height * 0.72) / image_h,
        )
        new_w, new_h = image_w * scale, image_h * scale
        self.canvas.set_selected_bounds(
            x=(self.canvas.document.width - new_w) / 2,
            y=(self.canvas.document.height - new_h) / 2,
            w=new_w,
            h=new_h,
        )

    def _opacity_card(self, obj: DrawObject) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Прозрачность"))
        slider = LabeledSlider("Непрозрачность", 5, 100, int(obj.opacity * 100), "%")
        slider.valueChanged.connect(
            lambda value: self.canvas.update_selected(opacity=value / 100.0)
        )
        layout.addWidget(slider)
        visible = QCheckBox("Объект виден")
        visible.setChecked(obj.visible)
        visible.toggled.connect(lambda value: self.canvas.update_selected(visible=value))
        layout.addWidget(visible)
        return card

    def _order_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Порядок"))
        row = QHBoxLayout()
        row.setSpacing(7)
        front = QPushButton("Вперёд")
        front.setIcon(make_icon("front", TEXT_MUTED))
        front.clicked.connect(self.canvas.raise_selected)
        back = QPushButton("Назад")
        back.setIcon(make_icon("back", TEXT_MUTED))
        back.clicked.connect(self.canvas.lower_selected)
        row.addWidget(front)
        row.addWidget(back)
        layout.addLayout(row)
        actions = QHBoxLayout()
        actions.setSpacing(7)
        duplicate = QPushButton("Дублировать")
        duplicate.setIcon(make_icon("copy", TEXT_MUTED))
        duplicate.clicked.connect(self.canvas.duplicate_selected)
        delete = QPushButton("Удалить")
        delete.setObjectName("Danger")
        delete.setIcon(make_icon("trash", "#FFB4AB"))
        delete.clicked.connect(self.canvas.delete_selected)
        actions.addWidget(duplicate)
        actions.addWidget(delete)
        layout.addLayout(actions)
        return card

    def _shape_fill_changed(self, key: str, value: str) -> None:
        if key == "mode":
            self.canvas.update_selected(fill_mode=value)
        elif key == "fill":
            self.canvas.update_selected(fill=value)
        elif key == "fill2":
            self.canvas.update_selected(fill2=value)
        elif key == "angle":
            self.canvas.update_selected(gradient_angle=float(value))

    # ------------------------------------------------------------------ tool UI
    def _build_tool_properties(self) -> None:
        self._tool_color_control = None
        self._tool_size_slider = None
        content, layout = self._new_props_content()
        tool = self.canvas.settings.tool
        titles = {
            "select": ("cursor", "Выделение", "Выберите объект на холсте, чтобы редактировать его форму, цвет и текст."),
            "hand": ("hand", "Рука", "Перетаскивайте холст. Средняя кнопка мыши и пробел работают так же."),
            "fill": ("fill", "Заливка", "Палитра заливает фигуру под курсором, а пустой холст — выбранным цветом."),
            "picker": ("eyedropper", "Пипетка", "Возьмите любой цвет прямо с холста. После выбора включится кисть."),
        }
        if tool in titles:
            icon, title, subtitle = titles[tool]
            layout.addWidget(_tool_header(icon, title, subtitle))
        elif tool == "shape":
            layout.addWidget(_tool_header("shapes", "Фигуры", "Выберите форму и настройте заливку и обводку. Shift — ровные пропорции."))
        elif tool == "text":
            layout.addWidget(_tool_header("text", "Текст", "Кликните на холсте, введите текст и нажмите Ctrl+Enter."))
        else:
            label = TOOL_LABELS.get(tool, "Кисть")
            hints = {
                "pencil": "Тонкая графитовая линия с лёгкой текстурой.",
                "brush": "Мягкая кисть с нажимом: медленнее — плотнее.",
                "pen": "Каллиграфическое перо с тонкими быстрыми линиями.",
                "spray": "Аэрозольные точки с естественным разбросом.",
                "eraser": "Стирает до цвета фона холста.",
            }
            layout.addWidget(_tool_header({"pencil": "pencil", "brush": "brush", "pen": "pen", "spray": "spray", "eraser": "eraser"}.get(tool, "brush"), label, hints.get(tool, "")))

        if tool == "select":
            layout.addWidget(self._canvas_info_card())
        elif tool == "shape":
            layout.addWidget(self._shape_tool_card())
            layout.addWidget(self._shape_fill_tool_card())
        elif tool == "text":
            layout.addWidget(self._text_tool_card())
        elif tool in {"hand", "fill", "picker"}:
            if tool == "fill":
                layout.addWidget(self._quick_palette_card())
            layout.addWidget(self._canvas_info_card())
        else:
            layout.addWidget(self._brush_tool_card())
            layout.addWidget(self._quick_palette_card())

        if tool in {"pencil", "brush", "pen", "spray", "eraser", "text", "shape"}:
            layout.addWidget(self._canvas_info_card())
        layout.addStretch(1)
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._show_props_content(content)

    def _brush_tool_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Параметры"))
        self._tool_color_control = ColorControl(self.canvas.settings.color, "Цвет")
        self._tool_color_control.colorChanged.connect(self._set_primary)
        layout.addWidget(self._tool_color_control)
        size = LabeledSlider("Размер", 1, 180, self.canvas.settings.size, " px")
        size.valueChanged.connect(self._tool_size_changed)
        self._tool_size_slider = size
        layout.addWidget(size)
        opacity = LabeledSlider("Непрозрачность", 5, 100, int(self.canvas.settings.opacity), "%")
        opacity.valueChanged.connect(self._tool_opacity_changed)
        layout.addWidget(opacity)
        hint = _hint("Совет: у кисти и пера толщина зависит от скорости движения.")
        layout.addWidget(hint)
        return card

    def _tool_size_changed(self, value: int) -> None:
        self.canvas.settings.size = value
        self.canvas.update()
        self.settingsChanged.emit()

    def _tool_opacity_changed(self, value: int) -> None:
        self.canvas.settings.opacity = float(value)
        self.canvas.update()
        self.settingsChanged.emit()

    def _shape_tool_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Форма"))
        grid = QGridLayout()
        grid.setSpacing(5)
        shapes = [
            ("line", "line", "Линия"),
            ("rect", "square", "Прямоугольник"),
            ("rounded_rect", "rounded-square", "Скруглённый"),
            ("ellipse", "circle", "Эллипс"),
            ("star", "star", "Звезда"),
            ("polygon", "polygon", "Многоугольник"),
        ]
        from PyQt6.QtWidgets import QButtonGroup

        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, (kind, icon, title) in enumerate(shapes):
            button = QToolButton()
            button.setObjectName("ShapeChoice")
            button.setCheckable(True)
            button.setIcon(make_icon(icon, TEXT_MUTED, PRIMARY))
            button.setIconSize(QSize(21, 21))
            button.setToolTip(title)
            button.setChecked(self.canvas.settings.shape_kind == kind)
            button.clicked.connect(lambda _=False, k=kind: self._choose_shape(k))
            group.addButton(button)
            grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(grid)
        return card

    def _choose_shape(self, kind: str) -> None:
        self.canvas.set_shape_kind(kind)
        self.refresh()

    def _shape_fill_tool_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Заливка и обводка"))
        container, controls = self._fill_controls(
            self.canvas.settings.fill_mode,
            self.canvas.settings.color,
            self.canvas.settings.fill2,
            self.canvas.settings.gradient_angle,
            self._tool_fill_changed,
        )
        layout.addWidget(container)
        layout.addWidget(separator())
        stroke = ColorControl(self.canvas.settings.secondary, "Обводка")
        stroke.colorChanged.connect(self._set_secondary)
        layout.addWidget(stroke)
        width = LabeledSlider(
            "Толщина обводки", 0, 80, int(self.canvas.settings.stroke_width), " px"
        )
        width.valueChanged.connect(self._tool_stroke_width_changed)
        layout.addWidget(width)
        kind = self.canvas.settings.shape_kind
        if kind == "rounded_rect":
            radius = LabeledSlider("Радиус углов", 0, 240, int(self.canvas.settings.corner_radius), " px")
            radius.valueChanged.connect(self._tool_corner_radius_changed)
            layout.addWidget(radius)
        if kind == "star":
            points = LabeledSlider("Лучей", 3, 16, self.canvas.settings.star_points, "")
            points.valueChanged.connect(self._tool_star_points_changed)
            layout.addWidget(points)
            inner = LabeledSlider("Глубина лучей", 15, 90, int(self.canvas.settings.star_inner * 100), "%")
            inner.valueChanged.connect(self._tool_star_inner_changed)
            layout.addWidget(inner)
        return card

    def _tool_fill_changed(self, key: str, value: str) -> None:
        if key == "mode":
            self.canvas.settings.fill_mode = value
        elif key == "fill":
            self.canvas.settings.color = value
            self.colorsChanged.emit(self.canvas.settings.color, self.canvas.settings.secondary)
        elif key == "fill2":
            self.canvas.settings.fill2 = value
        elif key == "angle":
            self.canvas.settings.gradient_angle = float(value)
        self.canvas.update()
        self.settingsChanged.emit()

    def _tool_stroke_width_changed(self, value: int) -> None:
        self.canvas.settings.stroke_width = float(value)
        self.canvas.update()
        self.settingsChanged.emit()

    def _tool_corner_radius_changed(self, value: int) -> None:
        self.canvas.settings.corner_radius = float(value)
        self.settingsChanged.emit()

    def _tool_star_points_changed(self, value: int) -> None:
        self.canvas.settings.star_points = value
        self.settingsChanged.emit()

    def _tool_star_inner_changed(self, value: int) -> None:
        self.canvas.settings.star_inner = value / 100.0
        self.settingsChanged.emit()

    def _text_tool_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Шрифт"))
        font_combo = FontCombo(free_font_families(), self.canvas.settings.font_family)
        font_combo.currentTextChanged.connect(self._font_family_changed)
        layout.addWidget(font_combo)
        row = QHBoxLayout()
        row.setSpacing(7)
        row.addWidget(_field_label("Размер"))
        size = _spin(6, 420, self.canvas.settings.font_size)
        size.setFixedWidth(78)
        size.valueChanged.connect(self._font_size_changed)
        row.addWidget(size)
        row.addStretch(1)
        for text, attr, tooltip, style in (
            ("B", "bold", "Жирный", "font-weight: 900;"),
            ("I", "italic", "Курсив", "font-style: italic; font-family: Georgia;"),
            ("U", "underline", "Подчёркнутый", "text-decoration: underline;"),
        ):
            button = QToolButton()
            button.setObjectName("SegmentButton")
            button.setText(text)
            button.setCheckable(True)
            button.setChecked(getattr(self.canvas.settings, attr))
            button.setStyleSheet(style)
            button.setToolTip(tooltip)
            button.toggled.connect(
                lambda value, a=attr: self._font_style_changed(a, value)
            )
            row.addWidget(button)
        layout.addLayout(row)
        align = SegmentedControl(
            [("left", "Слева"), ("center", "Центр"), ("right", "Справа")],
            self.canvas.settings.align,
        )
        align.valueChanged.connect(self._text_align_changed)
        layout.addWidget(align)
        layout.addWidget(separator())
        layout.addWidget(_title("Цвет"))
        color = ColorControl(self.canvas.settings.color, "Цвет текста")
        color.colorChanged.connect(self._set_primary)
        layout.addWidget(color)
        preview = QLabel("Pigment")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_font = QFont(self.canvas.settings.font_family)
        preview_font.setPixelSize(min(30, self.canvas.settings.font_size))
        preview_font.setBold(self.canvas.settings.bold)
        preview_font.setItalic(self.canvas.settings.italic)
        preview.setFont(preview_font)
        preview.setStyleSheet(
            "background: #20242B; border: 1px solid #2D323B; border-radius: 11px; color: #EAE6F0; padding: 8px;"
        )
        layout.addWidget(preview)
        layout.addWidget(_hint("Все семь встроенных шрифтов распространяются по лицензии SIL OFL."))
        return card

    def _font_family_changed(self, family: str) -> None:
        self.canvas.settings.font_family = family
        self.settingsChanged.emit()

    def _font_size_changed(self, value: int) -> None:
        self.canvas.settings.font_size = value
        self.settingsChanged.emit()

    def _font_style_changed(self, attr: str, value: bool) -> None:
        setattr(self.canvas.settings, attr, value)
        self.settingsChanged.emit()

    def _text_align_changed(self, value: str) -> None:
        self.canvas.settings.align = value
        self.settingsChanged.emit()

    def _quick_palette_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Палитра"))
        swatches = SwatchRow(5)
        swatches.colorSelected.connect(self._set_primary)
        layout.addWidget(swatches)
        return card

    def _canvas_info_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_title("Холст"))
        size = QLabel(
            f"{self.canvas.document.width} × {self.canvas.document.height} px · "
            f"{len(self.canvas.document.objects)} объектов"
        )
        size.setObjectName("Subtle")
        layout.addWidget(size)
        background = ColorControl(self.canvas.document.background, "Фон холста")
        background.colorChanged.connect(self.canvas.set_document_background)
        layout.addWidget(background)
        grid = QCheckBox("Показывать сетку")
        grid.setChecked(self.canvas.settings.show_grid)
        grid.toggled.connect(self._toggle_grid)
        layout.addWidget(grid)
        return card

    def _toggle_grid(self, value: bool) -> None:
        self.canvas.settings.show_grid = value
        self.canvas.update()
        self.settingsChanged.emit()
