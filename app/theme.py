"""Material 3 dark palette, bundled font loading and the global stylesheet."""

from __future__ import annotations

import ctypes
import sys

from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QWidget

from .paths import FONTS, ICONS

# Material 3 dark "Plum" scheme
BG = "#0E1014"
SURFACE = "#15181D"
SURFACE_1 = "#1A1E24"
SURFACE_2 = "#20242B"
SURFACE_3 = "#262B33"
SURFACE_4 = "#2C313A"
OUTLINE = "#2D323B"
OUTLINE_STRONG = "#3B414C"
TEXT = "#EAE6F0"
TEXT_MUTED = "#A9A3B4"
TEXT_DIM = "#777280"
PRIMARY = "#D0BCFF"
PRIMARY_HOVER = "#DDD0FF"
ON_PRIMARY = "#2B1B4D"
PRIMARY_CONTAINER = "#493B68"
ON_PRIMARY_CONTAINER = "#EADDFF"
SECONDARY = "#EFB8C8"
TERTIARY = "#A8D7C4"
ERROR = "#FFB4AB"
ERROR_CONTAINER = "#5C2A2D"
SUCCESS = "#A6E3B5"

FONT_ORDER = [
    "Manrope",
    "Inter",
    "Playfair Display",
    "Caveat",
    "Bebas Neue",
    "JetBrains Mono",
    "Pacifico",
]

FONT_FILES = {
    "Manrope": "Manrope.ttf",
    "Inter": "Inter.ttf",
    "Playfair Display": "PlayfairDisplay.ttf",
    "Caveat": "Caveat.ttf",
    "Bebas Neue": "BebasNeue-Regular.ttf",
    "JetBrains Mono": "JetBrainsMono.ttf",
    "Pacifico": "Pacifico-Regular.ttf",
}

_SYSTEM_FALLBACKS = [
    "Segoe UI",
    "Georgia",
    "Arial",
    "Times New Roman",
    "Courier New",
]

_loaded_families: dict[str, str] = {}
_ui_family = "Segoe UI"


def load_fonts() -> dict[str, str]:
    """Register every bundled OFL font and return family -> file path."""
    global _ui_family, _loaded_families
    if _loaded_families:
        return _loaded_families
    loaded: dict[str, str] = {}
    for preferred, filename in FONT_FILES.items():
        path = FONTS / filename
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            continue
        family = families[0]
        loaded[preferred] = family
    _loaded_families = loaded
    _ui_family = loaded.get("Manrope") or loaded.get("Inter") or "Segoe UI"
    return loaded


def ui_font_family() -> str:
    return _ui_family


def free_font_families() -> list[str]:
    """Families exposed to the text tool, bundled first."""
    loaded = load_fonts()
    result: list[str] = []
    for preferred in FONT_ORDER:
        if preferred in loaded:
            result.append(loaded[preferred])
    all_families = set(QFontDatabase.families())
    for family in _SYSTEM_FALLBACKS:
        if family in all_families and family not in result:
            result.append(family)
    return result


def apply_app_theme(app: QApplication) -> None:
    load_fonts()
    app.setStyle("Fusion")
    font = QFont(_ui_family)
    font.setPixelSize(13)
    font.setWeight(QFont.Weight.Medium)
    app.setFont(font)
    app.setStyleSheet(stylesheet())


def stylesheet() -> str:
    icons = ICONS.as_posix()
    ui = _ui_family or "Segoe UI"
    return f"""
* {{
    font-family: "{ui}";
    font-size: 13px;
    color: {TEXT};
    selection-background-color: {PRIMARY_CONTAINER};
    selection-color: {TEXT};
}}
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget {{
    background: transparent;
}}
QLabel {{
    background: transparent;
}}
QFrame#AppBar {{
    background: {SURFACE};
    border-bottom: 1px solid {OUTLINE};
}}
QFrame#ToolRail {{
    background: {SURFACE};
    border-right: 1px solid {OUTLINE};
}}
QFrame#Inspector {{
    background: {SURFACE};
    border-left: 1px solid {OUTLINE};
}}
QFrame#StatusBar {{
    background: {SURFACE};
    border-top: 1px solid {OUTLINE};
}}
QFrame#Card {{
    background: {SURFACE_1};
    border: 1px solid {OUTLINE};
    border-radius: 18px;
}}
QFrame#InsetCard {{
    background: {SURFACE_2};
    border: 1px solid {OUTLINE};
    border-radius: 12px;
}}
QFrame#Divider {{
    background: {OUTLINE};
    max-height: 1px;
    border: none;
}}
QFrame#VDivider {{
    background: {OUTLINE};
    max-width: 1px;
    border: none;
}}
QFrame#RailSeparator {{
    background: {OUTLINE};
    max-height: 1px;
    margin: 6px 14px;
}}
QFrame#ZoomChip {{
    background: {SURFACE_1};
    border: 1px solid {OUTLINE};
    border-radius: 16px;
}}
QFrame#SwatchRow {{
    background: transparent;
}}
QLabel#AppName {{
    font-size: 17px;
    font-weight: 800;
}}
QLabel#AppSub {{
    color: {TEXT_DIM};
    font-size: 10px;
    font-weight: 700;
}}
QLabel#DocName {{
    font-size: 13px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#DocHint, QLabel#Subtle {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}
QLabel#SectionTitle {{
    font-size: 12px;
    font-weight: 800;
    color: {TEXT};
}}
QLabel#SectionHint {{
    color: {TEXT_DIM};
    font-size: 10px;
}}
QLabel#FieldLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#ValueLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
}}
QLabel#Badge {{
    background: {SURFACE_3};
    border: 1px solid {OUTLINE};
    border-radius: 9px;
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
}}
QLabel#PrimaryBadge {{
    background: {PRIMARY_CONTAINER};
    border-radius: 9px;
    color: {ON_PRIMARY_CONTAINER};
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
}}
QLabel#StatusText {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}
QLabel#StatusDim {{
    color: {TEXT_DIM};
    font-size: 10px;
}}
QLabel#InspectorTitle {{
    font-size: 16px;
    font-weight: 800;
}}
QLabel#EmptyHint {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
QLabel#FontPreview {{
    color: {TEXT};
    font-size: 14px;
}}

QPushButton {{
    background: {SURFACE_2};
    border: 1px solid {OUTLINE};
    border-radius: 12px;
    padding: 8px 14px;
    font-weight: 650;
    min-height: 20px;
}}
QPushButton:hover {{
    background: {SURFACE_3};
    border-color: {OUTLINE_STRONG};
}}
QPushButton:pressed {{
    background: {SURFACE_4};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background: {SURFACE_1};
}}
QPushButton#Primary {{
    background: {PRIMARY};
    color: {ON_PRIMARY};
    border: none;
    padding: 9px 18px;
    font-weight: 800;
}}
QPushButton#Primary:hover {{
    background: {PRIMARY_HOVER};
}}
QPushButton#Primary:pressed {{
    background: #BFA8F5;
}}
QPushButton#Tonal {{
    background: {PRIMARY_CONTAINER};
    color: {ON_PRIMARY_CONTAINER};
    border: 1px solid #5B4A7E;
}}
QPushButton#Tonal:hover {{
    background: #57457A;
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {OUTLINE_STRONG};
    color: {TEXT_MUTED};
}}
QPushButton#Ghost:hover {{
    background: {SURFACE_2};
    color: {TEXT};
}}
QPushButton#Danger {{
    background: {ERROR_CONTAINER};
    color: {ERROR};
    border: 1px solid #763B40;
}}
QPushButton#Danger:hover {{
    background: #6B3337;
}}
QPushButton#Link {{
    background: transparent;
    border: none;
    color: {PRIMARY};
    padding: 4px;
    font-weight: 700;
}}
QPushButton#Link:hover {{
    color: {PRIMARY_HOVER};
}}

QToolButton {{
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 6px;
}}
QToolButton:hover {{
    background: {SURFACE_3};
}}
QToolButton:pressed {{
    background: {SURFACE_4};
}}
QToolButton:disabled {{
    background: transparent;
}}
QToolButton#ToolButton {{
    border-radius: 16px;
    min-width: 46px;
    max-width: 46px;
    min-height: 46px;
    max-height: 46px;
    padding: 0;
}}
QToolButton#ToolButton:hover {{
    background: {SURFACE_3};
}}
QToolButton#ToolButton:checked {{
    background: {PRIMARY_CONTAINER};
    border: 1px solid #6B58A0;
}}
QToolButton#BarButton {{
    border-radius: 11px;
    min-width: 34px;
    min-height: 34px;
    padding: 5px;
}}
QToolButton#BarButton:hover {{
    background: {SURFACE_3};
}}
QToolButton#MiniButton {{
    border-radius: 13px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
}}
QToolButton#MiniButton:hover {{
    background: {SURFACE_3};
}}
QToolButton#TabButton {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 8px 4px 11px 4px;
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 700;
}}
QToolButton#TabButton:hover {{
    color: {TEXT};
    background: transparent;
}}
QToolButton#TabButton:checked {{
    color: {ON_PRIMARY_CONTAINER};
    border-bottom: 2px solid {PRIMARY};
}}
QToolButton#SegmentButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 6px 10px;
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
}}
QToolButton#SegmentButton:hover {{
    background: {SURFACE_3};
    color: {TEXT};
}}
QToolButton#SegmentButton:checked {{
    background: {PRIMARY};
    color: {ON_PRIMARY};
    border-color: {PRIMARY};
}}
QToolButton#ShapeChoice {{
    border-radius: 13px;
    min-width: 44px;
    max-width: 44px;
    min-height: 40px;
    max-height: 40px;
    padding: 0;
}}
QToolButton#ShapeChoice:checked {{
    background: {PRIMARY_CONTAINER};
    border: 1px solid #6B58A0;
}}
QToolButton#Swatch {{
    border-radius: 15px;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    padding: 0;
    border: 2px solid transparent;
}}
QToolButton#Swatch:hover {{
    border-color: {TEXT_MUTED};
}}
QToolButton#Swatch:checked {{
    border-color: {PRIMARY};
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background: {SURFACE_2};
    border: 1px solid {OUTLINE};
    border-radius: 10px;
    padding: 7px 9px;
    color: {TEXT};
    min-height: 20px;
    selection-background-color: {PRIMARY_CONTAINER};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QTextEdit:hover {{
    border-color: {OUTLINE_STRONG};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid #8F7BC2;
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    color: {TEXT_DIM};
    background: {SURFACE_1};
}}
QSpinBox, QDoubleSpinBox {{
    padding-right: 20px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border: none;
    background: transparent;
    margin-top: 3px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border: none;
    background: transparent;
    margin-bottom: 3px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({icons}/chevron-up.svg);
    width: 9px;
    height: 9px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({icons}/chevron-down.svg);
    width: 9px;
    height: 9px;
}}
QComboBox {{
    padding-right: 26px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: url({icons}/chevron-down.svg);
    width: 11px;
    height: 11px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {OUTLINE_STRONG};
    border-radius: 10px;
    padding: 5px;
    outline: 0;
    selection-background-color: {PRIMARY_CONTAINER};
    selection-color: {ON_PRIMARY_CONTAINER};
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 8px;
    border-radius: 6px;
    min-height: 22px;
}}
QTextEdit, QPlainTextEdit {{
    padding: 8px;
}}

QSlider {{
    min-height: 22px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {SURFACE_4};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {PRIMARY};
    border-radius: 2px;
}}
QSlider::add-page:horizontal {{
    background: {SURFACE_4};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #F7F2FF;
    border: 2px solid {PRIMARY};
    width: 12px;
    height: 12px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: #FFFFFF;
    border-color: {PRIMARY_HOVER};
}}
QSlider::sub-page:horizontal:disabled {{
    background: {TEXT_DIM};
}}
QSlider::handle:horizontal:disabled {{
    border-color: {TEXT_DIM};
    background: {SURFACE_3};
}}

QCheckBox {{
    spacing: 8px;
    color: {TEXT_MUTED};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid {OUTLINE_STRONG};
    background: {SURFACE_2};
}}
QCheckBox::indicator:hover {{
    border-color: {TEXT_MUTED};
}}
QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
    image: url({icons}/check.svg);
}}
QRadioButton {{
    spacing: 8px;
    color: {TEXT};
}}
QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 9px;
    border: 1px solid {OUTLINE_STRONG};
    background: {SURFACE_2};
}}
QRadioButton::indicator:checked {{
    background: {PRIMARY};
    border: 4px solid {PRIMARY_CONTAINER};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE_4};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: #444A56;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 9px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {SURFACE_4};
    border-radius: 4px;
    min-width: 32px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
    width: 0;
}}

QListWidget {{
    background: transparent;
    border: none;
    outline: 0;
    padding: 2px;
}}
QListWidget::item {{
    background: transparent;
    border-radius: 10px;
    padding: 7px 8px;
    margin: 2px 0;
    color: {TEXT_MUTED};
}}
QListWidget::item:hover {{
    background: {SURFACE_2};
    color: {TEXT};
}}
QListWidget::item:selected {{
    background: {PRIMARY_CONTAINER};
    color: {ON_PRIMARY_CONTAINER};
}}

QMenu {{
    background: {SURFACE_2};
    border: 1px solid {OUTLINE_STRONG};
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 28px 8px 12px;
    border-radius: 8px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background: {PRIMARY_CONTAINER};
    color: {ON_PRIMARY_CONTAINER};
}}
QMenu::item:disabled {{
    color: {TEXT_DIM};
}}
QMenu::separator {{
    height: 1px;
    background: {OUTLINE};
    margin: 6px 8px;
}}
QMenu::icon {{
    padding-left: 8px;
}}

QToolTip {{
    background: #2B3038;
    color: {TEXT};
    border: 1px solid {OUTLINE_STRONG};
    border-radius: 8px;
    padding: 6px 9px;
    font-size: 11px;
}}

QMessageBox {{
    background: {SURFACE};
}}
QMessageBox QLabel {{
    color: {TEXT};
    min-width: 320px;
}}
QStatusBar {{
    background: {SURFACE};
}}
QSizeGrip {{
    background: transparent;
}}
QSplitter::handle {{
    background: {OUTLINE};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
"""


def set_dark_titlebar(widget: QWidget) -> None:
    """Ask DWM for a dark native title bar on Windows 10/11."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):
            if dwm.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            ) == 0:
                break
        # Windows 11 caption / border / text colours (COLORREF is 0x00BBGGRR).
        caption = ctypes.c_int(0x001D1815)
        text = ctypes.c_int(0x00F0E6EA)
        border = ctypes.c_int(0x003B302D)
        for attribute, value in ((35, caption), (36, text), (34, border)):
            try:
                dwm.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
                )
            except Exception:
                pass
    except Exception:
        # Dark title bar is cosmetic; the app still runs on systems without DWM.
        pass


def color(value: str, alpha: int | None = None) -> QColor:
    result = QColor(value)
    if alpha is not None:
        result.setAlpha(alpha)
    return result
