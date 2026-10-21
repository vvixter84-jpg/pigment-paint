"""Modal Material 3 dialogs for new documents, shortcuts and about."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .icons import logo_pixmap, make_pixmap
from .theme import BG, PRIMARY
from .widgets import ColorControl, ShortcutBadge, separator


class M3Dialog(QDialog):
    """QDialog with an explicitly painted opaque Material surface.

    A top-level QDialog does not always paint its stylesheet background in a
    ``grab()`` or while the window is being composited, so the surface is
    filled here before child widgets are drawn.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(BG))
        painter.end()
        super().paintEvent(event)


def _dialog_header(title: str, subtitle: str, icon: str = "file-plus") -> QWidget:
    wrapper = QWidget()
    row = QHBoxLayout(wrapper)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    badge = QLabel()
    badge.setFixedSize(44, 44)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet("background: #2C2838; border-radius: 14px;")
    badge.setPixmap(make_pixmap(icon, PRIMARY, 23))
    row.addWidget(badge)
    text = QVBoxLayout()
    text.setSpacing(2)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #EAE6F0;")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("Subtle")
    subtitle_label.setWordWrap(True)
    text.addWidget(title_label)
    text.addWidget(subtitle_label)
    row.addLayout(text, 1)
    return wrapper


class NewDocumentDialog(M3Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новый холст")
        self.setModal(True)
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        layout.addWidget(
            _dialog_header("Новый холст", "Задайте размер и фон будущего рисунка.")
        )

        presets = QHBoxLayout()
        presets.setSpacing(6)
        for label, width, height in (
            ("Full HD", 1920, 1080),
            ("Классика", 1600, 1000),
            ("Квадрат", 1080, 1080),
            ("Story", 1080, 1350),
            ("A4", 1240, 1754),
        ):
            button = QPushButton(label)
            button.setObjectName("Ghost")
            button.setToolTip(f"{width} × {height} px")
            button.clicked.connect(
                lambda _=False, w=width, h=height: self._apply_preset(w, h)
            )
            presets.addWidget(button)
        layout.addLayout(presets)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 13, 14, 14)
        card_layout.setSpacing(10)
        size_row = QHBoxLayout()
        size_row.setSpacing(10)
        width_box = QVBoxLayout()
        width_label = QLabel("Ширина, px")
        width_label.setObjectName("FieldLabel")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(64, 12000)
        self.width_spin.setValue(1600)
        self.width_spin.setSingleStep(50)
        width_box.addWidget(width_label)
        width_box.addWidget(self.width_spin)
        height_box = QVBoxLayout()
        height_label = QLabel("Высота, px")
        height_label.setObjectName("FieldLabel")
        self.height_spin = QSpinBox()
        self.height_spin.setRange(64, 12000)
        self.height_spin.setValue(1000)
        self.height_spin.setSingleStep(50)
        height_box.addWidget(height_label)
        height_box.addWidget(self.height_spin)
        size_row.addLayout(width_box, 1)
        size_row.addLayout(height_box, 1)
        card_layout.addLayout(size_row)
        card_layout.addWidget(separator())
        background_label = QLabel("Фон холста")
        background_label.setObjectName("FieldLabel")
        card_layout.addWidget(background_label)
        self.background = ColorControl("#FFFFFF", "Фон холста")
        card_layout.addWidget(self.background)
        hint = QLabel("Совет: тёмный фон отлично подходит для неоновых градиентов.")
        hint.setObjectName("SectionHint")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)
        layout.addWidget(card)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        create = QPushButton("Создать холст")
        create.setObjectName("Primary")
        create.setIcon(QIcon(make_pixmap("arrow-right", "#2B1B4D", 16)))
        create.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        layout.addLayout(buttons)

    def _apply_preset(self, width: int, height: int) -> None:
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)

    def values(self) -> tuple[int, int, str]:
        return self.width_spin.value(), self.height_spin.value(), self.background.color()


SHORTCUT_GROUPS = [
    (
        "Файл",
        [
            ("Ctrl+N", "Новый холст"),
            ("Ctrl+O", "Открыть проект"),
            ("Ctrl+S", "Сохранить"),
            ("Ctrl+Shift+S", "Сохранить как"),
            ("Ctrl+E", "Экспорт PNG / JPEG"),
            ("Ctrl+Shift+V", "Вставить изображение"),
        ],
    ),
    (
        "Редактирование",
        [
            ("Ctrl+Z", "Отменить"),
            ("Ctrl+Shift+Z / Ctrl+Y", "Повторить"),
            ("Ctrl+D", "Дублировать объект"),
            ("Del", "Удалить объект"),
            ("Стрелки", "Сдвинуть на 1 px"),
            ("Shift + стрелки", "Сдвинуть на 10 px"),
            ("Esc", "Снять выделение / отмена"),
        ],
    ),
    (
        "Инструменты",
        [
            ("V", "Выделение"),
            ("H", "Рука"),
            ("P", "Карандаш"),
            ("B", "Кисть"),
            ("N", "Перо"),
            ("A", "Баллончик"),
            ("E", "Ластик"),
            ("G", "Заливка"),
            ("I", "Пипетка"),
            ("T", "Текст"),
            ("R", "Фигуры"),
        ],
    ),
    (
        "Вид и холст",
        [
            ("Space + перетаскивание", "Перемещение холста"),
            ("Средняя кнопка", "Перемещение холста"),
            ("Ctrl + колесо", "Масштаб"),
            ("Ctrl+0", "Вписать холст"),
            ("Ctrl+1", "Масштаб 100%"),
            ("Ctrl++ / Ctrl+−", "Приблизить / отдалить"),
            ("Shift при рисовании", "Ровные пропорции / угол 45°"),
            ("Alt при рисовании", "Фигура из центра"),
            ("F1", "Эта справка"),
        ],
    ),
]


class ShortcutsDialog(M3Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Горячие клавиши")
        self.setModal(True)
        self.resize(590, 680)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(13)
        root.addWidget(
            _dialog_header(
                "Горячие клавиши",
                "Всё, что ускоряет работу с Pigment.",
                "keyboard",
            )
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 6, 0)
        content_layout.setSpacing(11)
        for group_title, items in SHORTCUT_GROUPS:
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(13, 12, 13, 13)
            card_layout.setSpacing(8)
            title = QLabel(group_title)
            title.setObjectName("SectionTitle")
            card_layout.addWidget(title)
            for shortcut, description in items:
                row = QHBoxLayout()
                row.setSpacing(12)
                badge = ShortcutBadge(shortcut)
                badge.setMinimumWidth(154)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                text = QLabel(description)
                text.setStyleSheet("color: #C9C4D2;")
                row.addWidget(badge)
                row.addWidget(text, 1)
                card_layout.addLayout(row)
            content_layout.addWidget(card)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        close = QPushButton("Понятно")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)


class AboutDialog(M3Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе Pigment")
        self.setModal(True)
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(13)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(76))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        name = QLabel("Pigment")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("font-size: 28px; font-weight: 800; color: #EAE6F0;")
        layout.addWidget(name)
        tagline = QLabel("Paint-студия с редактируемыми фигурами и Material 3")
        tagline.setObjectName("Subtle")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 15)
        card_layout.setSpacing(8)
        about = QLabel(
            "Векторные фигуры, живые штрихи, градиенты и текст остаются "
            "редактируемыми после создания. Проект написан на Python 3 и PyQt6, "
            "интерфейс следует принципам Material 3."
        )
        about.setWordWrap(True)
        about.setStyleSheet("color: #D7D2E0;")
        card_layout.addWidget(about)
        fonts = QLabel(
            "Шрифты Manrope, Inter, Playfair Display, Caveat, Bebas Neue, "
            "JetBrains Mono и Pacifico входят в комплект под лицензией SIL Open Font License."
        )
        fonts.setWordWrap(True)
        fonts.setObjectName("Subtle")
        card_layout.addWidget(fonts)
        version = QLabel("Pigment 1.0 · Python 3.12 · PyQt6 6.7")
        version.setObjectName("SectionHint")
        card_layout.addWidget(version)
        layout.addWidget(card)
        close = QPushButton("Закрыть")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
