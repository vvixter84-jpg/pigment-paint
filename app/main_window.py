"""Pigment Paint main window and application-level workflows."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QKeySequence,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .canvas import Canvas, SHAPE_KINDS
from .dialogs import AboutDialog, NewDocumentDialog, ShortcutsDialog
from .demo import build_demo_document
from .icons import app_icon, logo_pixmap, make_icon, make_pixmap
from .inspector import Inspector
from .models import Document, TOOL_LABELS, ToolSettings
from .renderer import render_to_image
from .theme import (
    ON_PRIMARY,
    PRIMARY,
    TEXT_MUTED,
    set_dark_titlebar,
)
from .widgets import ColorPair, Toast, icon_button, separator

PROJECT_FILTER = "Pigment (*.pigment);;JSON (*.json);;Все файлы (*.*)"
IMAGE_FILTER = "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)"

TOOL_SHORTCUTS = {
    "V": "select",
    "H": "hand",
    "P": "pencil",
    "B": "brush",
    "N": "pen",
    "A": "spray",
    "E": "eraser",
    "G": "fill",
    "I": "picker",
    "T": "text",
    "R": "shape",
}

SHAPE_ICONS = {
    "line": "line",
    "rect": "square",
    "rounded_rect": "rounded-square",
    "ellipse": "circle",
    "star": "star",
    "polygon": "polygon",
}

TOOL_ICONS = {
    "select": "cursor",
    "hand": "hand",
    "pencil": "pencil",
    "brush": "brush",
    "pen": "pen",
    "spray": "spray",
    "eraser": "eraser",
    "fill": "fill",
    "picker": "eyedropper",
    "text": "text",
    "shape": "shapes",
}

TOOL_DESCRIPTIONS = {
    "select": "Выделение и редактирование",
    "hand": "Перемещение холста",
    "pencil": "Карандаш",
    "brush": "Кисть",
    "pen": "Перо",
    "spray": "Баллончик",
    "eraser": "Ластик",
    "fill": "Заливка",
    "picker": "Пипетка",
    "text": "Текст",
    "shape": "Фигуры",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pigment — Paint Studio")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1180, 760)
        self.setAcceptDrops(True)

        self.settings = ToolSettings()
        self.document = Document(
            width=1600,
            height=1000,
            background="#FFFFFF",
            name="Без названия",
        )
        self.current_path: Path | None = None
        self.dirty = False
        self._loading = False
        self._focus_typing = False
        self._tool_shortcuts: list[QShortcut] = []

        self._build_actions()
        self._build_interface()
        self._connect_signals()
        self._setup_shortcuts()
        self._apply_initial_document()
        self._update_history_buttons()
        self._sync_tool_buttons()
        self._update_status()
        self._update_title()
        self._size_window()
        self.toast = Toast(self)
        QTimer.singleShot(0, self._finish_startup)

    # ------------------------------------------------------------------- setup
    def _build_actions(self) -> None:
        self.new_action = self._action("Новый холст", "Ctrl+N", "file-plus", self.new_document)
        self.open_action = self._action("Открыть проект…", "Ctrl+O", "folder-open", self.open_project)
        self.save_action = self._action("Сохранить", "Ctrl+S", "save", self.save_project)
        self.save_as_action = self._action(
            "Сохранить как…", "Ctrl+Shift+S", "save", self.save_project_as
        )
        self.export_action = self._action(
            "Экспорт PNG / JPEG…", "Ctrl+E", "download", self.export_image
        )
        self.insert_image_action = self._action(
            "Вставить изображение из файла…", None, "image", self.insert_image_file
        )
        self.paste_image_action = self._action(
            "Вставить изображение из буфера", "Ctrl+Shift+V", "image", self.paste_image
        )
        self.undo_action = self._action("Отменить", "Ctrl+Z", "undo", self.undo)
        self.redo_action = self._action(
            "Повторить", ["Ctrl+Shift+Z", "Ctrl+Y"], "redo", self.redo
        )
        self.duplicate_action = self._action(
            "Дублировать объект", "Ctrl+D", "copy", self.duplicate_selected
        )
        self.delete_action = self._action("Удалить объект", "Del", "trash", self.delete_selected)
        self.fit_action = self._action("Вписать холст", "Ctrl+0", "fit", self.fit_canvas)
        self.actual_action = self._action("Масштаб 100%", "Ctrl+1", None, self.actual_size)
        self.zoom_in_action = self._action("Приблизить", "Ctrl+=", "plus", self.zoom_in)
        self.zoom_out_action = self._action("Отдалить", "Ctrl+-", "minus", self.zoom_out)
        self.shortcuts_action = self._action(
            "Горячие клавиши", "F1", "keyboard", self.show_shortcuts
        )
        self.about_action = self._action("О программе", None, "info", self.show_about)
        self.demo_action = self._action("Открыть демо-работу", None, "sparkles", self.load_demo)
        self.grid_action = self._action("Показывать сетку", None, "grid", self.toggle_grid)
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(self.settings.show_grid)

    def _action(self, text: str, shortcut, icon: str | None, handler) -> QAction:
        action = QAction(text, self)
        if shortcut:
            if isinstance(shortcut, (list, tuple)):
                action.setShortcuts([QKeySequence(value) for value in shortcut])
            else:
                action.setShortcut(QKeySequence(shortcut))
        if icon:
            action.setIcon(make_icon(icon, TEXT_MUTED, PRIMARY))
        action.triggered.connect(handler)
        self.addAction(action)
        return action

    def _build_interface(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_app_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_tool_rail())

        self.canvas = Canvas(self.document, self.settings)
        body.addWidget(self.canvas, 1)

        self.inspector = Inspector(self.canvas)
        body.addWidget(self.inspector)
        root.addLayout(body, 1)
        root.addWidget(self._build_status_bar())
        self.setCentralWidget(central)

    def _build_app_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("AppBar")
        bar.setFixedHeight(66)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 9, 14, 9)
        layout.setSpacing(11)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(40))
        logo.setFixedSize(40, 40)
        layout.addWidget(logo)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(0)
        title = QLabel("Pigment")
        title.setObjectName("AppName")
        subtitle = QLabel("PAINT STUDIO")
        subtitle.setObjectName("AppSub")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        layout.addLayout(title_wrap)
        layout.addWidget(separator(vertical=True))

        doc_wrap = QVBoxLayout()
        doc_wrap.setSpacing(0)
        self.doc_name_label = QLabel("Без названия")
        self.doc_name_label.setObjectName("DocName")
        self.doc_name_label.setMaximumWidth(170)
        self.doc_hint_label = QLabel("Новый документ")
        self.doc_hint_label.setObjectName("DocHint")
        doc_wrap.addWidget(self.doc_name_label)
        doc_wrap.addWidget(self.doc_hint_label)
        layout.addLayout(doc_wrap)
        layout.addSpacing(4)

        self.new_button = self._top_text_button("Новый", "file-plus", self.new_document, "Ctrl+N")
        self.open_button = self._top_text_button("Открыть", "folder-open", self.open_project, "Ctrl+O")
        self.save_button = self._top_text_button("Сохранить", "save", self.save_project, "Ctrl+S")
        layout.addWidget(self.new_button)
        layout.addWidget(self.open_button)
        layout.addWidget(self.save_button)
        layout.addStretch(1)

        self.undo_button = icon_button("undo", "Отменить  Ctrl+Z", size=19)
        self.redo_button = icon_button("redo", "Повторить  Ctrl+Shift+Z", size=19)
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        layout.addWidget(self.undo_button)
        layout.addWidget(self.redo_button)

        zoom_chip = QFrame()
        zoom_chip.setObjectName("ZoomChip")
        zoom_layout = QHBoxLayout(zoom_chip)
        zoom_layout.setContentsMargins(3, 3, 3, 3)
        zoom_layout.setSpacing(1)
        minus = icon_button("minus", "Отдалить  Ctrl+−", size=14, object_name="MiniButton")
        minus.clicked.connect(self.zoom_out)
        plus = icon_button("plus", "Приблизить  Ctrl++", size=14, object_name="MiniButton")
        plus.clicked.connect(self.zoom_in)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(44)
        self.zoom_label.setObjectName("StatusText")
        fit_button = icon_button("fit", "Вписать холст  Ctrl+0", size=14, object_name="MiniButton")
        fit_button.clicked.connect(self.fit_canvas)
        zoom_layout.addWidget(minus)
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(plus)
        zoom_layout.addWidget(fit_button)
        layout.addWidget(zoom_chip)

        self.export_button = QPushButton("Экспорт")
        self.export_button.setObjectName("Primary")
        self.export_button.setIcon(QIcon(make_pixmap("download", ON_PRIMARY, 16)))
        self.export_button.setIconSize(QSize(16, 16))
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.clicked.connect(self.export_image)
        self.export_button.setToolTip("Экспорт PNG / JPEG  Ctrl+E")
        layout.addWidget(self.export_button)

        more = icon_button("more", "Ещё", size=19)
        more.clicked.connect(self._show_more_menu)
        layout.addWidget(more)
        return bar

    def _top_text_button(self, text: str, icon: str, handler, shortcut: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("Ghost")
        button.setIcon(make_icon(icon, TEXT_MUTED, PRIMARY))
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(f"{text}  {shortcut}")
        button.clicked.connect(handler)
        button.setFixedHeight(34)
        return button

    def _build_tool_rail(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("ToolRail")
        rail.setFixedWidth(100)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons: dict[str, QToolButton] = {}
        groups = [
            [("select", "V"), ("hand", "H")],
            [("pencil", "P"), ("brush", "B"), ("pen", "N"), ("spray", "A"), ("eraser", "E")],
            [("fill", "G"), ("picker", "I"), ("text", "T")],
            [("shape", "R")],
        ]
        for group_index, entries in enumerate(groups):
            for tool, key in entries:
                button = QToolButton()
                button.setObjectName("ToolButton")
                button.setCheckable(True)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                icon_name = TOOL_ICONS[tool]
                if tool == "shape":
                    icon_name = SHAPE_ICONS.get(self.settings.shape_kind, "shapes")
                button.setIcon(make_icon(icon_name, TEXT_MUTED, PRIMARY))
                button.setIconSize(QSize(22, 22))
                button.setToolTip(
                    f"{TOOL_DESCRIPTIONS[tool]}  {key}"
                    + (
                        "  ·  нажмите ещё раз, чтобы сменить форму"
                        if tool == "shape"
                        else ""
                    )
                )
                if tool == "shape":
                    button.clicked.connect(self._shape_button_clicked)
                else:
                    button.clicked.connect(lambda _=False, t=tool: self._select_tool(t))
                self.tool_group.addButton(button)
                self.tool_buttons[tool] = button
                layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
            if group_index < len(groups) - 1:
                line = QFrame()
                line.setObjectName("RailSeparator")
                line.setFixedHeight(1)
                layout.addWidget(line)
        layout.addStretch(1)

        help_button = icon_button("keyboard", "Горячие клавиши  F1", size=18)
        help_button.clicked.connect(self.show_shortcuts)
        layout.addWidget(help_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.color_pair = ColorPair(self.settings.color, self.settings.secondary)
        self.color_pair.primaryClicked.connect(lambda: self.pick_color(False))
        self.color_pair.secondaryClicked.connect(lambda: self.pick_color(True))
        layout.addWidget(self.color_pair, 0, Qt.AlignmentFlag.AlignHCenter)
        color_hint = QLabel("ЦВЕТ")
        color_hint.setObjectName("SectionHint")
        color_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(color_hint)
        return rail

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)
        self.status_icon = QLabel()
        self.status_icon.setPixmap(make_pixmap("brush", PRIMARY, 14))
        layout.addWidget(self.status_icon)
        self.status_tool = QLabel("Кисть")
        self.status_tool.setObjectName("StatusText")
        layout.addWidget(self.status_tool)
        layout.addWidget(separator(vertical=True))
        self.status_hint = QLabel("Медленнее — плотнее. Ctrl+колесо — масштаб.")
        self.status_hint.setObjectName("StatusDim")
        layout.addWidget(self.status_hint)
        layout.addStretch(1)
        self.coord_label = QLabel("x —   y —")
        self.coord_label.setObjectName("StatusDim")
        layout.addWidget(self.coord_label)
        layout.addWidget(separator(vertical=True))
        self.doc_size_label = QLabel("1600 × 1000 px")
        self.doc_size_label.setObjectName("StatusDim")
        layout.addWidget(self.doc_size_label)
        layout.addWidget(separator(vertical=True))
        self.object_count_label = QLabel("0 объектов")
        self.object_count_label.setObjectName("StatusDim")
        layout.addWidget(self.object_count_label)
        layout.addWidget(separator(vertical=True))
        self.status_zoom = QLabel("100%")
        self.status_zoom.setObjectName("StatusText")
        layout.addWidget(self.status_zoom)
        return bar

    def _connect_signals(self) -> None:
        self.canvas.documentChanged.connect(self._on_document_changed)
        self.canvas.selectionChanged.connect(self._on_selection_changed)
        self.canvas.geometryChanged.connect(self._on_geometry_changed)
        self.canvas.historyChanged.connect(self._update_history_buttons)
        self.canvas.zoomChanged.connect(self._on_zoom_changed)
        self.canvas.cursorMoved.connect(self._on_cursor_moved)
        self.canvas.colorPicked.connect(self._on_color_picked)
        self.canvas.toolChanged.connect(self._on_tool_changed)
        self.canvas.statusMessage.connect(self._on_canvas_status)
        self.inspector.colorsChanged.connect(self._on_colors_changed)
        self.inspector.settingsChanged.connect(self._on_settings_changed)

    def _setup_shortcuts(self) -> None:
        for key, tool in TOOL_SHORTCUTS.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(lambda t=tool: self._select_tool(t))
            self._tool_shortcuts.append(shortcut)
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    def _apply_initial_document(self) -> None:
        self.canvas.set_document(self.document, fit=True)
        self.inspector.refresh()
        self.doc_size_label.setText(f"{self.document.width} × {self.document.height} px")

    def _finish_startup(self) -> None:
        set_dark_titlebar(self)
        self.canvas.fit_to_view()
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)
        self.toast = getattr(self, "toast", Toast(self))
        self._update_status()

    def _size_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1440, 900)
            return
        available = screen.availableGeometry()
        width = min(1480, max(1180, available.width() - 80))
        height = min(930, max(760, available.height() - 80))
        self.resize(width, height)
        self.move(
            available.x() + (available.width() - width) // 2,
            available.y() + (available.height() - height) // 2,
        )

    # ------------------------------------------------------------------ actions
    def _select_tool(self, tool: str) -> None:
        self.canvas.set_tool(tool)
        self.canvas.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _shape_button_clicked(self) -> None:
        if self.canvas.settings.tool == "shape":
            self._show_shape_menu()
        else:
            self.canvas.set_tool("shape")
            self.canvas.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _show_shape_menu(self) -> None:
        menu = QMenu(self)
        for kind, label in SHAPE_KINDS.items():
            action = menu.addAction(make_icon(SHAPE_ICONS[kind], TEXT_MUTED, PRIMARY), label)
            action.setCheckable(True)
            action.setChecked(self.settings.shape_kind == kind)
            action.triggered.connect(lambda _=False, k=kind: self._choose_shape(k))
        button = self.tool_buttons.get("shape")
        if button is not None:
            menu.exec(button.mapToGlobal(QPoint(button.width() + 8, 0)))
        else:
            menu.exec(self.mapToGlobal(self.rect().center()))

    def _choose_shape(self, kind: str) -> None:
        self.canvas.set_shape_kind(kind)
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)
        self._sync_shape_icon()

    def _show_more_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction(self.demo_action)
        menu.addAction(self.insert_image_action)
        menu.addAction(self.paste_image_action)
        copy_action = menu.addAction(
            make_icon("copy", TEXT_MUTED, PRIMARY), "Копировать PNG в буфер"
        )
        copy_action.triggered.connect(self.copy_png)
        menu.addAction(self.grid_action)
        menu.addSeparator()
        menu.addAction(self.shortcuts_action)
        menu.addAction(self.about_action)
        button = self.sender()
        if isinstance(button, QToolButton):
            menu.exec(button.mapToGlobal(QPoint(-180, button.height() + 6)))
        else:
            menu.exec(self.mapToGlobal(self.rect().center()))

    def pick_color(self, secondary: bool = False) -> None:
        initial = QColor(self.settings.secondary if secondary else self.settings.color)
        selected = QColorDialog.getColor(
            initial,
            self,
            "Дополнительный цвет" if secondary else "Основной цвет",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not selected.isValid():
            return
        value = (
            selected.name(QColor.NameFormat.HexArgb)
            if selected.alpha() < 255
            else selected.name(QColor.NameFormat.HexRgb)
        )
        if secondary:
            self.settings.secondary = value
        else:
            self.settings.color = value
        self._on_colors_changed(self.settings.color, self.settings.secondary)
        if self.canvas.selected_object() is None:
            self.inspector.refresh()
        self.canvas.update()

    def undo(self) -> None:
        if self._focus_typing:
            return
        self.canvas.finish_text_edit()
        self.canvas.undo()
        self.inspector.refresh()

    def redo(self) -> None:
        if self._focus_typing:
            return
        self.canvas.finish_text_edit()
        self.canvas.redo()
        self.inspector.refresh()

    def duplicate_selected(self) -> None:
        if self._focus_typing:
            return
        self.canvas.duplicate_selected()

    def delete_selected(self) -> None:
        if self._focus_typing:
            return
        self.canvas.delete_selected()

    def fit_canvas(self) -> None:
        self.canvas.fit_to_view()

    def actual_size(self) -> None:
        self.canvas.actual_size()

    def zoom_in(self) -> None:
        self.canvas.zoom_in()

    def zoom_out(self) -> None:
        self.canvas.zoom_out()

    def toggle_grid(self, checked: bool) -> None:
        self.settings.show_grid = checked
        self.canvas.update()
        if self.canvas.selected_object() is None:
            self.inspector.refresh()

    # ------------------------------------------------------------------ signals
    def _on_document_changed(self) -> None:
        if not self._loading:
            self._set_dirty(True)
        self.inspector.refresh_objects()
        self._update_status()

    def _on_selection_changed(self, obj) -> None:
        self.inspector.refresh()
        self._update_history_buttons()
        self._update_status()

    def _on_geometry_changed(self) -> None:
        self.inspector.refresh_geometry()

    def _on_zoom_changed(self, zoom: float) -> None:
        text = f"{round(zoom * 100)}%"
        self.zoom_label.setText(text)
        self.status_zoom.setText(text)

    def _on_cursor_moved(self, x: float, y: float) -> None:
        self.coord_label.setText(f"x {round(x)}   y {round(y)}")

    def _on_color_picked(self, value: str) -> None:
        self.settings.color = value
        self.color_pair.set_colors(self.settings.color, self.settings.secondary)
        self.inspector.refresh()
        self.toast.show_message(f"Цвет {value.upper()} выбран", "info")

    def _on_tool_changed(self, tool: str) -> None:
        self._sync_tool_buttons()
        self._update_status()
        self.inspector.refresh()

    def _on_colors_changed(self, primary: str, secondary: str) -> None:
        self.color_pair.set_colors(primary, secondary)
        self._update_status()

    def _on_settings_changed(self) -> None:
        self._sync_shape_icon()
        self._update_status()

    def _on_canvas_status(self, message: str) -> None:
        self.status_hint.setText(message)
        if message and ("Не удалось" in message or "ошибка" in message.lower()):
            self.toast.show_message(message, "error")

    def _sync_tool_buttons(self) -> None:
        tool = self.settings.tool
        for name, button in self.tool_buttons.items():
            button.blockSignals(True)
            button.setChecked(name == tool)
            button.blockSignals(False)
        self._sync_shape_icon()

    def _sync_shape_icon(self) -> None:
        button = self.tool_buttons.get("shape")
        if button is not None:
            button.setIcon(
                make_icon(SHAPE_ICONS.get(self.settings.shape_kind, "shapes"), TEXT_MUTED, PRIMARY)
            )

    def _update_history_buttons(self, can_undo: bool | None = None, can_redo: bool | None = None) -> None:
        if can_undo is None:
            can_undo = self.canvas.can_undo()
        if can_redo is None:
            can_redo = self.canvas.can_redo()
        enabled_undo = bool(can_undo) and not self._focus_typing
        enabled_redo = bool(can_redo) and not self._focus_typing
        self.undo_button.setEnabled(enabled_undo)
        self.redo_button.setEnabled(enabled_redo)
        self.undo_action.setEnabled(enabled_undo)
        self.redo_action.setEnabled(enabled_redo)
        self.duplicate_action.setEnabled(not self._focus_typing)
        self.delete_action.setEnabled(not self._focus_typing)

    def _on_focus_changed(self, old, new) -> None:
        typing = isinstance(
            new,
            (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox),
        )
        self._focus_typing = typing
        for shortcut in self._tool_shortcuts:
            shortcut.setEnabled(not typing)
        self.paste_image_action.setEnabled(not typing)
        self._update_history_buttons()

    # ------------------------------------------------------------------- status
    def _update_status(self) -> None:
        tool = self.settings.tool
        icon = TOOL_ICONS.get(tool, "brush")
        self.status_icon.setPixmap(make_pixmap(icon, PRIMARY, 14))
        if tool == "shape":
            tool_label = f"Фигура · {SHAPE_KINDS.get(self.settings.shape_kind, '')}"
            hint = "Shift — ровные пропорции, Alt — из центра."
        elif tool in {"pencil", "brush", "pen", "spray", "eraser"}:
            tool_label = f"{TOOL_LABELS.get(tool, 'Кисть')} · {self.settings.size} px"
            hint = {
                "pencil": "Тонкая графитовая линия.",
                "brush": "Медленнее — плотнее. Ctrl+колесо — масштаб.",
                "pen": "Скорость движения меняет толщину.",
                "spray": "Точки распределяются с естественным разбросом.",
                "eraser": "Стирает до цвета фона холста.",
            }.get(tool, "")
        else:
            tool_label = TOOL_DESCRIPTIONS.get(tool, "")
            hint = {
                "select": "Тяните объект, чтобы переместить. Двойной клик по тексту — редактирование.",
                "hand": "Перетаскивайте холст или удерживайте пробел.",
                "fill": "Клик по фигуре заливает её выбранным цветом.",
                "picker": "Клик по холсту берёт цвет.",
                "text": "Клик по холсту добавляет текст.",
            }.get(tool, "")
        self.status_tool.setText(tool_label)
        self.status_hint.setText(hint)
        self.doc_size_label.setText(f"{self.document.width} × {self.document.height} px")
        count = len(self.document.objects)
        self.object_count_label.setText(
            f"{count} объект" if count == 1 else f"{count} объектов"
        )
        self.status_zoom.setText(f"{round(self.canvas.zoom * 100)}%")
        self._update_title()

    def _update_title(self) -> None:
        name = self.document.name or "Без названия"
        if len(name) > 24:
            display = name[:21] + "…"
        else:
            display = name
        self.doc_name_label.setText(display)
        if self.dirty:
            self.doc_hint_label.setText("Не сохранено · •")
            self.doc_hint_label.setStyleSheet("color: #EFB8C8;")
        elif self.current_path is not None:
            self.doc_hint_label.setText("Сохранено")
            self.doc_hint_label.setStyleSheet("")
        elif name not in {"Без названия", ""}:
            self.doc_hint_label.setText("Без файла")
            self.doc_hint_label.setStyleSheet("")
        else:
            self.doc_hint_label.setText("Новый документ")
            self.doc_hint_label.setStyleSheet("")
        mark = " •" if self.dirty else ""
        self.setWindowTitle(f"Pigment — {name}{mark}")

    def _set_dirty(self, dirty: bool) -> None:
        if self.dirty == dirty:
            return
        self.dirty = dirty
        self._update_title()

    # ---------------------------------------------------------------- documents
    def _confirm_unsaved(self) -> bool:
        if not self.dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Несохранённые изменения")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("Сохранить изменения в проекте?")
        box.setInformativeText(
            "Если не сохранить, изменения рисунка будут потеряны."
        )
        save = box.addButton("Сохранить", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Не сохранять", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return self.save_project()
        if clicked is discard:
            return True
        if clicked is cancel:
            return False
        return False

    def new_document(self) -> None:
        if not self._confirm_unsaved():
            return
        dialog = NewDocumentDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        width, height, background = dialog.values()
        self._load_new_document(Document(width, height, background, "Без названия"))
        self.toast.show_message(f"Новый холст {width} × {height} px")

    def _load_new_document(self, document: Document) -> None:
        self._loading = True
        self.document = document
        self.canvas.set_document(document, fit=True)
        self.current_path = None
        self.dirty = False
        self.inspector.invalidate()
        self._sync_tool_buttons()
        self._update_history_buttons()
        self._update_status()
        self._update_title()
        self._loading = False
        QTimer.singleShot(0, self.canvas.fit_to_view)

    def open_project(self) -> None:
        if not self._confirm_unsaved():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", PROJECT_FILTER)
        if path:
            self._open_path(Path(path))

    def _open_path(self, path: Path) -> None:
        try:
            raw = path.read_text(encoding="utf-8")
            document = Document.from_json(raw)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Не удалось открыть проект",
                f"Файл повреждён или имеет неверный формат.\n\n{exc}",
            )
            return
        document.name = path.stem
        self._loading = True
        self.document = document
        self.canvas.set_document(document, fit=True)
        self.current_path = path
        self.dirty = False
        self.inspector.invalidate()
        self._sync_tool_buttons()
        self._update_history_buttons()
        self._update_status()
        self._update_title()
        self._loading = False
        QTimer.singleShot(0, self.canvas.fit_to_view)
        self.toast.show_message(f"Открыт проект «{path.name}»")

    def save_project(self) -> bool:
        self.canvas.finish_text_edit()
        if self.current_path is None:
            return self.save_project_as()
        return self._write_project(self.current_path)

    def save_project_as(self) -> bool:
        self.canvas.finish_text_edit()
        default = str(
            self.current_path
            if self.current_path is not None
            else Path.cwd() / f"{self._safe_name()}.pigment"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", default, PROJECT_FILTER
        )
        if not path:
            return False
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".pigment")
        return self._write_project(target)

    def _write_project(self, path: Path) -> bool:
        try:
            self.document.name = path.stem
            path.write_text(self.document.to_json(), encoding="utf-8")
        except OSError as exc:
            self.toast.show_message(f"Ошибка сохранения: {exc}", "error")
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))
            return False
        self.current_path = path
        self._loading = True
        self.dirty = False
        self._loading = False
        self._update_title()
        self.toast.show_message(f"Сохранено · {path.name}")
        return True

    def export_image(self) -> None:
        self.canvas.finish_text_edit()
        default = str(Path.cwd() / f"{self._safe_name()}.png")
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Экспорт изображения",
            default,
            "PNG (*.png);;JPEG (*.jpg *.jpeg)",
        )
        if not path:
            return
        target = Path(path)
        suffix = target.suffix.lower()
        if not suffix:
            suffix = ".jpg" if "JPEG" in selected_filter else ".png"
            target = target.with_suffix(suffix)
        fmt = "JPEG" if suffix in {".jpg", ".jpeg"} else "PNG"
        image = render_to_image(self.document, 1.0)
        if not image.save(str(target), fmt, 95 if fmt == "JPEG" else -1):
            self.toast.show_message("Не удалось сохранить изображение", "error")
            return
        self.toast.show_message(f"Экспорт готов · {target.name}")

    def copy_png(self) -> None:
        image = render_to_image(self.document, 1.0)
        QApplication.clipboard().setImage(image)
        self.toast.show_message("PNG скопирован в буфер обмена")

    def insert_image_file(self) -> None:
        self.canvas.finish_text_edit()
        self.canvas.insert_image_dialog()

    def paste_image(self) -> None:
        self.canvas.finish_text_edit()
        if not self.canvas.paste_image_from_clipboard():
            self.toast.show_message("В буфере обмена нет изображения", "error")

    def load_demo(self) -> None:
        if not self._confirm_unsaved():
            return
        demo = build_demo_document()
        self._load_new_document(demo)
        self.toast.show_message("Демо-работа открыта")

    def show_shortcuts(self) -> None:
        ShortcutsDialog(self).exec()

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def _safe_name(self) -> str:
        name = self.document.name.strip() or "pigment"
        for char in '<>:"/\\|?*':
            name = name.replace(char, "_")
        return name

    # --------------------------------------------------------------- UI events
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast._position()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.canvas.finish_text_edit()
        if self._confirm_unsaved():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------ drop
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(self._supported_drop(url.toLocalFile()) for url in urls):
                event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        for url in urls:
            path = Path(url.toLocalFile())
            if not self._supported_drop(str(path)):
                continue
            if path.suffix.lower() in {".pigment", ".json"}:
                if self._confirm_unsaved():
                    self._open_path(path)
            else:
                self.canvas.insert_image(path)
                self.toast.show_message(f"Изображение «{path.name}» добавлено")
            event.acceptProposedAction()
            return

    @staticmethod
    def _supported_drop(path: str) -> bool:
        suffix = Path(path).suffix.lower()
        return suffix in {".pigment", ".json", ".png", ".jpg", ".jpeg", ".webp", ".bmp"}


# Backwards-friendly alias used by scripts.
PaintWindow = MainWindow
