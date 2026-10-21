"""Small Material 3 building blocks used throughout the interface."""

from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QColorDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .icons import make_icon, make_pixmap
from .renderer import gradient_preview
from .theme import OUTLINE_STRONG


def icon_button(
    icon_name: str,
    tooltip: str,
    *,
    size: int = 20,
    object_name: str = "BarButton",
    checkable: bool = False,
    icon_color: str = "#D7D2E0",
    active_color: str = "#EADDFF",
) -> QToolButton:
    button = QToolButton()
    button.setObjectName(object_name)
    button.setIcon(make_icon(icon_name, icon_color, active_color))
    button.setIconSize(QSize(size, size))
    button.setToolTip(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setCheckable(checkable)
    button.setAutoRaise(True)
    return button


def icon_label(name: str, color: str = "#A9A3B4", size: int = 16) -> QLabel:
    label = QLabel()
    label.setPixmap(make_pixmap(name, color, size))
    label.setFixedSize(size, size)
    return label


def separator(vertical: bool = False) -> QFrame:
    frame = QFrame()
    frame.setObjectName("VDivider" if vertical else "Divider")
    if vertical:
        frame.setFixedWidth(1)
        frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    else:
        frame.setFixedHeight(1)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return frame


def muted_label(text: str = "", object_name: str = "Subtle") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    return label


def section_title(text: str, hint: str | None = None) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)
    title = QLabel(text)
    title.setObjectName("SectionTitle")
    layout.addWidget(title)
    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("SectionHint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
    return wrapper


def _preview_checker(size: int = 10) -> QPixmap:
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(QColor("#D8D5DD"))
    painter = QPainter(pixmap)
    painter.fillRect(0, 0, size, size, QColor("#BEBAC7"))
    painter.fillRect(size, size, size, size, QColor("#BEBAC7"))
    painter.end()
    return pixmap


class SwatchButton(QAbstractButton):
    """Round color swatch used for presets and the current colors."""

    def __init__(self, color: str = "#D0BCFF", size: int = 30, parent=None):
        super().__init__(parent)
        self._color = color
        self._diameter = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(False)
        self._checker = _preview_checker()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def color(self) -> str:
        return self._color

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.8, 0.8, self.width() - 1.6, self.height() - 1.6)
        path = QPainterPath()
        path.addRoundedRect(rect, self.width() * 0.34, self.width() * 0.34)
        painter.setClipPath(path)
        painter.fillRect(rect, QBrush(self._checker))
        painter.fillRect(rect, QColor(self._color))
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#FFFFFF33"), 1))
        painter.drawPath(path)
        if self.isChecked():
            painter.setPen(QPen(QColor("#D0BCFF"), 2))
            painter.drawPath(path)
        painter.end()


class SwatchRow(QWidget):
    colorSelected = pyqtSignal(str)

    PRESETS = [
        "#EAE6F0",
        "#D0BCFF",
        "#EFB8C8",
        "#A8D7C4",
        "#FFD8A8",
        "#FFB4AB",
        "#A8C7FA",
        "#C9B458",
        "#5E5A66",
        "#24252B",
    ]

    def __init__(self, columns: int = 5, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        row: QHBoxLayout | None = None
        for i, value in enumerate(self.PRESETS):
            if i % columns == 0:
                row = QHBoxLayout()
                row.setSpacing(7)
                layout.addLayout(row)
            button = SwatchButton(value, 27)
            button.setToolTip(value.upper())
            button.clicked.connect(lambda _=False, c=value: self.colorSelected.emit(c))
            assert row is not None
            row.addWidget(button)
        if row is not None and row.count() < columns:
            row.addStretch(1)
        layout.addStretch(1)


class ColorControl(QWidget):
    colorChanged = pyqtSignal(str)

    def __init__(self, value: str = "#D0BCFF", label: str = "Цвет", parent=None):
        super().__init__(parent)
        self._value = value
        self._label_text = label
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.swatch = SwatchButton(value, 34)
        self.swatch.setToolTip("Открыть палитру")
        self.swatch.clicked.connect(self._open_dialog)
        layout.addWidget(self.swatch)
        self.hex_edit = QLineEdit(value.upper())
        self.hex_edit.setMaxLength(9)
        self.hex_edit.setToolTip("HEX-код цвета")
        self.hex_edit.editingFinished.connect(self._hex_committed)
        self.hex_edit.setMinimumWidth(84)
        layout.addWidget(self.hex_edit, 1)
        self._update_hex_style()

    def color(self) -> str:
        return self._value

    def set_color(self, value: str) -> None:
        color = QColor(value)
        if not color.isValid():
            return
        self._value = value
        self.swatch.set_color(value)
        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(value.upper())
        self.hex_edit.blockSignals(False)
        self._update_hex_style()

    def _update_hex_style(self) -> None:
        self.hex_edit.setStyleSheet(
            "QLineEdit { color: #EAE6F0; background: #20242B; "
            "border: 1px solid #2D323B; border-radius: 10px; padding: 7px 9px; "
            "font-family: 'JetBrains Mono'; font-size: 12px; font-weight: 600; }"
            "QLineEdit:focus { border-color: #8F7BC2; }"
        )

    def _open_dialog(self) -> None:
        initial = QColor(self._value)
        selected = QColorDialog.getColor(
            initial,
            self,
            self._label_text,
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not selected.isValid():
            return
        value = (
            selected.name(QColor.NameFormat.HexArgb)
            if selected.alpha() < 255
            else selected.name(QColor.NameFormat.HexRgb)
        )
        self.set_color(value)
        self.colorChanged.emit(value)

    def _hex_committed(self) -> None:
        raw = self.hex_edit.text().strip()
        if not raw.startswith("#"):
            raw = "#" + raw
        if QColor(raw).isValid() and raw.upper() != self._value.upper():
            self.set_color(raw.upper())
            self.colorChanged.emit(self._value)
        else:
            self.set_color(self._value)


class GradientPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(54)
        self._c1 = "#D0BCFF"
        self._c2 = "#7D5260"
        self._angle = 45.0
        self._mode = "linear"
        self._pixmap: QPixmap | None = None

    def set_values(self, c1: str, c2: str, angle: float, mode: str = "linear") -> None:
        self._c1, self._c2, self._angle, self._mode = c1, c2, angle, mode
        self._pixmap = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._pixmap is None:
            self._pixmap = gradient_preview(
                max(1, self.width()), 54, self._c1, self._c2, self._angle, self._mode
            )
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._pixmap = None
        super().resizeEvent(event)


class SegmentedControl(QWidget):
    valueChanged = pyqtSignal(str)

    def __init__(
        self,
        options: Iterable[tuple[str, str]],
        value: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._buttons: dict[str, QToolButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        for option_value, label in options:
            button = QToolButton()
            button.setObjectName("SegmentButton")
            button.setText(label)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _checked=False, v=option_value: self._select(v, emit=True)
            )
            layout.addWidget(button, 1)
            self._buttons[option_value] = button
        if value in self._buttons:
            self._buttons[value].setChecked(True)
        elif self._buttons:
            next(iter(self._buttons.values())).setChecked(True)

    def value(self) -> str:
        for value, button in self._buttons.items():
            if button.isChecked():
                return value
        return ""

    def set_value(self, value: str, emit: bool = False) -> None:
        self._select(value, emit=emit)

    def _select(self, value: str, emit: bool = False) -> None:
        if value not in self._buttons:
            return
        for key, button in self._buttons.items():
            button.setChecked(key == value)
        if emit:
            self.valueChanged.emit(value)


class LabeledSlider(QWidget):
    valueChanged = pyqtSignal(int)
    interactionStarted = pyqtSignal()
    interactionFinished = pyqtSignal()

    def __init__(
        self,
        label: str,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._suffix = suffix
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        self.value_label = QLabel(f"{value}{suffix}")
        self.value_label.setObjectName("ValueLabel")
        header.addWidget(self.label)
        header.addStretch(1)
        header.addWidget(self.value_label)
        layout.addLayout(header)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.valueChanged.connect(self._on_value)
        self.slider.sliderPressed.connect(self._pressed)
        self.slider.sliderReleased.connect(self._released)
        layout.addWidget(self.slider)
        self._was_pressed = False

    def set_value(self, value: int, emit: bool = False) -> None:
        blocked = self.slider.blockSignals(True)
        self.slider.setValue(int(value))
        self.slider.blockSignals(blocked)
        self.value_label.setText(f"{int(value)}{self._suffix}")
        if emit:
            self.valueChanged.emit(int(value))

    def value(self) -> int:
        return self.slider.value()

    def _on_value(self, value: int) -> None:
        self.value_label.setText(f"{value}{self._suffix}")
        self.valueChanged.emit(value)

    def _pressed(self) -> None:
        self._was_pressed = True
        if hasattr(self, "interactionStarted"):
            self.interactionStarted()  # type: ignore[attr-defined]

    def _released(self) -> None:
        if hasattr(self, "interactionFinished"):
            self.interactionFinished()  # type: ignore[attr-defined]


class FontCombo(QComboBox):
    def __init__(self, families: list[str], current: str = "Manrope", parent=None):
        super().__init__(parent)
        self._families = families
        for family in families:
            self.addItem(family)
            index = self.count() - 1
            font = QFont(family)
            font.setPixelSize(13)
            self.setItemData(index, font, Qt.ItemDataRole.FontRole)
            self.setItemData(index, family, Qt.ItemDataRole.UserRole)
            free = family in {
                "Manrope",
                "Inter",
                "Playfair Display",
                "Caveat",
                "Bebas Neue",
                "JetBrains Mono",
                "Pacifico",
            }
            self.setItemData(
                index,
                f"{family} — бесплатный шрифт" if free else family,
                Qt.ItemDataRole.ToolTipRole,
            )
        if current:
            index = self.findText(current)
            if index >= 0:
                self.setCurrentIndex(index)
        self.setMinimumWidth(150)


class ColorPair(QWidget):
    """Paint-style overlapping primary/secondary colour circles."""

    primaryClicked = pyqtSignal()
    secondaryClicked = pyqtSignal()

    def __init__(self, primary: str = "#D0BCFF", secondary: str = "#EFB8C8", parent=None):
        super().__init__(parent)
        self._primary = primary
        self._secondary = secondary
        self.setFixedSize(70, 58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Основной и дополнительный цвет")

    def set_colors(self, primary: str, secondary: str) -> None:
        self._primary = primary
        self._secondary = secondary
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Secondary sits behind and to the lower-right, like classic Paint.
        sec_center = QPointF(44, 34)
        painter.setPen(QPen(QColor("#0E1014"), 2))
        painter.setBrush(QColor(self._secondary))
        painter.drawEllipse(sec_center, 15, 15)
        painter.setPen(QPen(QColor(OUTLINE_STRONG), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(sec_center, 15, 15)

        pri_center = QPointF(26, 24)
        painter.setPen(QPen(QColor("#0E1014"), 3))
        painter.setBrush(QColor(self._primary))
        painter.drawEllipse(pri_center, 17, 17)
        painter.setPen(QPen(QColor("#FFFFFF66"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(pri_center, 17, 17)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if (pos - QPointF(26, 24)).manhattanLength() <= 24:
            self.primaryClicked.emit()
        else:
            self.secondaryClicked.emit()


class Toast(QFrame):
    """Small transient confirmation pill at the bottom of the window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InsetCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 16, 8)
        layout.setSpacing(9)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(make_pixmap("check", "#A6E3B5", 16))
        self.text_label = QLabel()
        self.text_label.setStyleSheet("font-size: 12px; font-weight: 650;")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._animation = QPropertyAnimation(self._effect, b"opacity", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text: str, kind: str = "success") -> None:
        self.text_label.setText(text)
        color = "#A6E3B5" if kind == "success" else "#FFB4AB" if kind == "error" else "#D0BCFF"
        icon = "check" if kind == "success" else "info"
        self.icon_label.setPixmap(make_pixmap(icon, color, 16))
        self.adjustSize()
        self._position()
        self.show()
        self.raise_()
        self._animation.stop()
        self._animation.setStartValue(self._effect.opacity())
        self._animation.setEndValue(1.0)
        self._animation.start()
        self._timer.start(2600)

    def _fade_out(self) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._effect.opacity())
        self._animation.setEndValue(0.0)
        self._animation.finished.connect(self._hide_once)
        self._animation.start()

    def _hide_once(self) -> None:
        try:
            self._animation.finished.disconnect(self._hide_once)
        except TypeError:
            pass
        if self._effect.opacity() < 0.05:
            self.hide()

    def _position(self) -> None:
        if self.parentWidget() is None:
            return
        parent = self.parentWidget()
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 48
        self.move(max(12, x), max(12, y))


class ShortcutBadge(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("Badge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class FontPreviewLabel(QLabel):
    def __init__(self, text: str, family: str, size: int = 18, parent=None):
        super().__init__(text, parent)
        font = QFont(family)
        font.setPixelSize(size)
        self.setFont(font)
        self.setObjectName("FontPreview")
        self.setMinimumHeight(32)
