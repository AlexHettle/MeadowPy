"""Keyboard shortcut editor dialog."""

from __future__ import annotations

import re

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QKeyEvent, QPainter, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from meadowpy.core.shortcuts import (
    SHORTCUT_OVERRIDES_KEY,
    ShortcutDefinition,
    all_shortcuts,
    find_shortcut_conflict,
    get_shortcut,
    normalize_shortcut,
    reset_all_shortcuts,
    reset_shortcut,
    set_shortcut,
    shortcut_count,
    shortcut_from_key_event,
    shortcut_is_default,
)


class _MemorySettings:
    """Small settings stand-in used by isolated dialog tests."""

    def __init__(self):
        self._values = {SHORTCUT_OVERRIDES_KEY: {}}

    def get(self, key: str, default=None):
        return self._values.get(key, default)

    def set(self, key: str, value) -> None:
        self._values[key] = value

    def save(self) -> None:
        pass


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _stylesheet_color(selector: str, property_name: str) -> QColor | None:
    app = QApplication.instance()
    stylesheet = app.styleSheet() if app is not None else ""
    if not stylesheet:
        return None
    block = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\}}", stylesheet, re.S)
    if block is None:
        return None
    value = re.search(
        rf"\b{re.escape(property_name)}\s*:\s*(#[0-9A-Fa-f]{{6}})",
        block.group("body"),
    )
    return QColor(value.group(1)) if value is not None else None


class _ShortcutBadgeRow(QWidget):
    """Reusable row of key badges for one shortcut string."""

    _HEIGHT = 24
    _MIN_KEY_WIDTH = 22
    _HORIZONTAL_PADDING = 18
    _SPACING = 8

    def __init__(self, shortcut: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("shortcutBadgeRow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        font = QFont("Consolas")
        font.setPointSize(9)
        self.setFont(font)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._keys: list[str] = []
        self.set_shortcut(shortcut)

    def set_shortcut(self, shortcut: str) -> None:
        self._keys = [key.strip() for key in shortcut.split("+") if key.strip()]
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._content_width(), self._HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setFont(self.font())

        if not self._keys:
            painter.setPen(self._empty_color())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No shortcut")
            return

        fill, text = self._badge_colors()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)

        x = 0
        for key in self._keys:
            width = self._key_width(key)
            rect = QRectF(x, 0, width, self._HEIGHT)
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(text)
            painter.drawText(
                rect.toRect(),
                Qt.AlignmentFlag.AlignCenter,
                key,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            x += width + self._SPACING

    def _content_width(self) -> int:
        if not self._keys:
            return QFontMetrics(self.font()).horizontalAdvance("No shortcut")
        return (
            sum(self._key_width(key) for key in self._keys)
            + self._SPACING * (len(self._keys) - 1)
        )

    def _key_width(self, key: str) -> int:
        metrics = QFontMetrics(self.font())
        return max(
            self._MIN_KEY_WIDTH,
            metrics.horizontalAdvance(key) + self._HORIZONTAL_PADDING,
        )

    def _badge_colors(self) -> tuple[QColor, QColor]:
        fill = _stylesheet_color("#shortcutKeyBadge", "background")
        text = _stylesheet_color("#shortcutKeyBadge", "color")
        if fill is not None and text is not None:
            return fill, text
        is_dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        return (
            QColor("#3C3C3C" if is_dark else "#F0F0F0"),
            QColor("#DDDDDD" if is_dark else "#333333"),
        )

    def _empty_color(self) -> QColor:
        color = _stylesheet_color("#shortcutEmptyBadge", "color")
        if color is not None:
            return color
        is_dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        return QColor("#888888" if is_dark else "#777777")


class _ShortcutRow(QFrame):
    """Selectable action row in the shortcut list."""

    selected = pyqtSignal(str)

    def __init__(self, definition: ShortcutDefinition, shortcut: str, parent=None):
        super().__init__(parent)
        self.definition = definition
        self.setObjectName("shortcutRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._shortcut_text = ""
        self._action_text = definition.name.lower()
        self._category_text = definition.category.lower()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(8)

        self._action_label = QLabel(definition.name)
        self._action_label.setObjectName("shortcutActionLabel")
        self._action_label.setWordWrap(True)
        self._action_label.setMinimumWidth(0)
        self._action_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self._action_label, 1)

        self._badges = _ShortcutBadgeRow()
        layout.addWidget(
            self._badges,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.refresh(shortcut)

    def refresh(self, shortcut: str) -> None:
        self._shortcut_text = normalize_shortcut(shortcut).lower()
        self._badges.set_shortcut(normalize_shortcut(shortcut))

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        _refresh_style(self)

    def matches_filter(self, text: str) -> bool:
        return (
            text in self._action_text
            or text in self._shortcut_text
            or text in self._category_text
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.definition.id)
            event.accept()
            return
        super().mousePressEvent(event)


class _ShortcutListSection(QFrame):
    """A category section in the left shortcut list."""

    def __init__(
        self,
        category: str,
        rows: list[_ShortcutRow],
        parent=None,
    ):
        super().__init__(parent)
        self.category = category
        self._rows = rows
        self._category_lower = category.lower()
        self.setObjectName("shortcutListSection")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QLabel(category.upper())
        header.setObjectName("shortcutCardHeader")
        header_font = QFont()
        header_font.setPointSize(10)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        for row in rows:
            layout.addWidget(row)

    def apply_filter(self, text: str) -> bool:
        if not text:
            for row in self._rows:
                row.setVisible(True)
            return True

        if text in self._category_lower:
            for row in self._rows:
                row.setVisible(True)
            return True

        any_visible = False
        for row in self._rows:
            visible = row.matches_filter(text)
            row.setVisible(visible)
            any_visible = any_visible or visible
        return any_visible


class _ShortcutCaptureDialog(QDialog):
    """Modal key capture dialog."""

    def __init__(
        self,
        definition: ShortcutDefinition,
        current_shortcut: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Change Shortcut")
        self.setObjectName("ShortcutCaptureDialog")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._shortcut = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel(f"Press keys for {definition.name}")
        title.setObjectName("shortcutTitle")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel("Press the key combination you want to use.")
        subtitle.setObjectName("shortcutSubtitle")
        layout.addWidget(subtitle)

        capture = QFrame()
        capture.setObjectName("shortcutCaptureBox")
        capture_layout = QVBoxLayout(capture)
        capture_layout.setContentsMargins(16, 16, 16, 16)
        capture_layout.setSpacing(8)

        waiting = QLabel("Waiting for keys...")
        waiting.setObjectName("shortcutCaptureText")
        waiting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capture_layout.addWidget(waiting)

        current = QLabel(f"Current: {current_shortcut or 'No shortcut'}")
        current.setObjectName("shortcutSubtitle")
        current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capture_layout.addWidget(current)
        layout.addWidget(capture)

        buttons = QHBoxLayout()
        clear = QPushButton("Clear shortcut")
        clear.setObjectName("shortcutResetBtn")
        clear.clicked.connect(self._clear_and_accept)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("shortcutCloseBtn")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(clear)
        buttons.addStretch()
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def shortcut(self) -> str:
        return self._shortcut

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        shortcut = shortcut_from_key_event(event)
        if shortcut:
            self._shortcut = shortcut
            self.accept()
            return
        super().keyPressEvent(event)

    def _clear_and_accept(self) -> None:
        self._shortcut = ""
        self.accept()


class _ShortcutConflictDialog(QDialog):
    """Conflict resolver shown when a shortcut is already assigned."""

    def __init__(
        self,
        shortcut: str,
        target: ShortcutDefinition,
        conflict: ShortcutDefinition,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Shortcut Taken")
        self.setObjectName("ShortcutConflictDialog")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._choice = "cancel"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("These keys are taken")
        title.setObjectName("shortcutTitle")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        summary = QLabel(
            f"{shortcut} is already used by {conflict.name}. "
            "What would you like to do?"
        )
        summary.setObjectName("shortcutSubtitle")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        use_btn = QPushButton(f"Use it for {target.name}")
        use_btn.setObjectName("shortcutConflictPrimary")
        use_btn.setMinimumHeight(48)
        use_btn.setToolTip(f"{conflict.name} will be left without a shortcut")
        use_btn.clicked.connect(self._choose_use)
        layout.addWidget(use_btn)

        pick_btn = QPushButton("Pick different keys")
        pick_btn.setObjectName("shortcutConflictSecondary")
        pick_btn.setMinimumHeight(48)
        pick_btn.setToolTip("Go back and try another combo")
        pick_btn.clicked.connect(self._choose_pick)
        layout.addWidget(pick_btn)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("shortcutLinkBtn")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(cancel)
        row.addStretch()
        layout.addLayout(row)

    def choice(self) -> str:
        return self._choice

    def _choose_use(self) -> None:
        self._choice = "use"
        self.accept()

    def _choose_pick(self) -> None:
        self._choice = "pick"
        self.accept()


class _ResetAllShortcutsDialog(QDialog):
    """Confirmation dialog for resetting all shortcuts."""

    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reset Shortcuts")
        self.setObjectName("ShortcutResetAllDialog")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("Reset all shortcuts?")
        title.setObjectName("shortcutTitle")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        message = QLabel(
            f"This puts all {count} shortcuts back to their original keys. "
            "Any custom shortcuts you set will be removed. You can't undo this."
        )
        message.setObjectName("shortcutSubtitle")
        message.setWordWrap(True)
        layout.addWidget(message)

        buttons = QHBoxLayout()
        buttons.addStretch()
        keep = QPushButton("Keep my shortcuts")
        keep.setObjectName("shortcutCloseBtn")
        keep.clicked.connect(self.reject)
        reset = QPushButton("Reset all")
        reset.setObjectName("shortcutDangerBtn")
        reset.clicked.connect(self.accept)
        buttons.addWidget(keep)
        buttons.addWidget(reset)
        layout.addLayout(buttons)


class ShortcutReferenceDialog(QDialog):
    """Searchable shortcut editor."""

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self._settings = (
            settings
            or getattr(parent, "_settings", None)
            or _MemorySettings()
        )
        self.setWindowTitle("Keyboard Shortcuts")
        self.setObjectName("ShortcutReferenceDialog")
        self.setMinimumSize(760, 500)
        self.resize(960, 620)
        self._cards: list[_ShortcutListSection] = []
        self._rows_by_id: dict[str, _ShortcutRow] = {}
        self._selected_id = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        sidebar = QFrame()
        sidebar.setObjectName("shortcutSidebar")
        sidebar.setMinimumWidth(300)
        sidebar.setMaximumWidth(380)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 18, 12, 12)
        sidebar_layout.setSpacing(12)

        self._search = QLineEdit()
        self._search.setObjectName("shortcutSearch")
        self._search.setPlaceholderText("Search shortcuts...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_filter)
        sidebar_layout.addWidget(self._search)

        scroll = QScrollArea()
        scroll.setObjectName("shortcutScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setObjectName("shortcutContainer")
        self._card_layout = QVBoxLayout(container)
        self._card_layout.setContentsMargins(0, 0, 4, 0)
        self._card_layout.setSpacing(8)
        self._build_shortcut_list()
        self._card_layout.addStretch()
        scroll.setWidget(container)
        sidebar_layout.addWidget(scroll, 1)

        body.addWidget(sidebar)

        detail = QFrame()
        detail.setObjectName("shortcutDetailPane")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(30, 28, 26, 24)
        detail_layout.setSpacing(12)

        self._detail_category = QLabel("")
        self._detail_category.setObjectName("shortcutDetailCategory")
        detail_layout.addWidget(self._detail_category)

        self._detail_title = QLabel("")
        self._detail_title.setObjectName("shortcutTitle")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self._detail_title.setFont(title_font)
        detail_layout.addWidget(self._detail_title)

        self._detail_description = QLabel("")
        self._detail_description.setObjectName("shortcutSubtitle")
        self._detail_description.setWordWrap(True)
        detail_layout.addWidget(self._detail_description)

        shortcut_label = QLabel("SHORTCUT")
        shortcut_label.setObjectName("shortcutDetailCategory")
        detail_layout.addWidget(shortcut_label)

        shortcut_row = QHBoxLayout()
        shortcut_row.setSpacing(12)
        self._detail_shortcut_box = QFrame()
        self._detail_shortcut_box.setObjectName("shortcutCurrentBox")
        box_layout = QHBoxLayout(self._detail_shortcut_box)
        box_layout.setContentsMargins(14, 10, 14, 10)
        self._detail_badges = _ShortcutBadgeRow()
        box_layout.addWidget(self._detail_badges)
        shortcut_row.addWidget(self._detail_shortcut_box, 0)

        self._change_btn = QPushButton("Change")
        self._change_btn.setObjectName("shortcutChangeBtn")
        self._change_btn.setMinimumHeight(38)
        self._change_btn.clicked.connect(self._on_change_clicked)
        shortcut_row.addWidget(self._change_btn, 0)
        shortcut_row.addStretch()
        detail_layout.addLayout(shortcut_row)

        self._detail_hint = QLabel(
            "Click Change, then press the keys you want. "
            "We'll warn you if they're already taken."
        )
        self._detail_hint.setObjectName("shortcutSubtitle")
        self._detail_hint.setWordWrap(True)
        detail_layout.addWidget(self._detail_hint)

        detail_layout.addStretch()

        separator = QFrame()
        separator.setObjectName("shortcutCardSep")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        detail_layout.addWidget(separator)

        status_row = QHBoxLayout()
        self._default_note = QLabel("")
        self._default_note.setObjectName("shortcutSubtitle")
        status_row.addWidget(self._default_note, 1)
        self._reset_btn = QPushButton("Reset to default")
        self._reset_btn.setObjectName("shortcutResetBtn")
        self._reset_btn.clicked.connect(self._on_reset_current)
        status_row.addWidget(self._reset_btn)
        detail_layout.addLayout(status_row)

        body.addWidget(detail, 1)

        self._no_results = QLabel("No matching shortcuts found.")
        self._no_results.setObjectName("shortcutNoResults")
        self._no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_results.setVisible(False)
        root.addWidget(self._no_results)

        footer = QFrame()
        footer.setObjectName("shortcutFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 14)
        footer_layout.setSpacing(12)

        reset_all = QPushButton("Reset all to defaults")
        reset_all.setObjectName("shortcutLinkBtn")
        reset_all.clicked.connect(self._on_reset_all)
        footer_layout.addWidget(reset_all)
        footer_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("shortcutCloseBtn")
        close_btn.setMinimumHeight(34)
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.close)
        footer_layout.addWidget(close_btn)
        root.addWidget(footer)

        if self._rows_by_id:
            self._select_shortcut(next(iter(self._rows_by_id)))

    def _build_shortcut_list(self) -> None:
        sections: dict[str, list[_ShortcutRow]] = {}
        order: list[str] = []
        for definition, shortcut in all_shortcuts(self._settings):
            if definition.category not in sections:
                sections[definition.category] = []
                order.append(definition.category)
            row = _ShortcutRow(definition, shortcut)
            row.selected.connect(self._select_shortcut)
            sections[definition.category].append(row)
            self._rows_by_id[definition.id] = row

        for category in order:
            section = _ShortcutListSection(category, sections[category])
            self._cards.append(section)
            self._card_layout.addWidget(section)

    def _on_filter(self, text: str) -> None:
        query = text.strip().lower()
        any_visible = False
        first_visible_id = ""
        selected_visible = False
        for section in self._cards:
            visible = section.apply_filter(query)
            section.setVisible(visible)
            any_visible = any_visible or visible
            if visible and not first_visible_id:
                for row in section._rows:
                    if row.isVisible():
                        first_visible_id = row.definition.id
                        break
            if visible and self._selected_id:
                selected_visible = selected_visible or any(
                    row.definition.id == self._selected_id and not row.isHidden()
                    for row in section._rows
                )
        self._no_results.setVisible(not any_visible)
        if first_visible_id and not selected_visible:
            self._select_shortcut(first_visible_id)

    def _select_shortcut(self, shortcut_id: str) -> None:
        if shortcut_id not in self._rows_by_id:
            return
        for row_id, row in self._rows_by_id.items():
            row.set_selected(row_id == shortcut_id)
        self._selected_id = shortcut_id
        self._refresh_detail()

    def _refresh_all(self) -> None:
        for definition, shortcut in all_shortcuts(self._settings):
            row = self._rows_by_id.get(definition.id)
            if row is not None:
                row.refresh(shortcut)
        self._refresh_detail()
        self._on_filter(self._search.text())

    def _refresh_detail(self) -> None:
        row = self._rows_by_id.get(self._selected_id)
        if row is None:
            return
        definition = row.definition
        shortcut = get_shortcut(self._settings, definition.id)
        self._detail_category.setText(definition.category.upper())
        self._detail_title.setText(definition.name)
        self._detail_description.setText(definition.description)
        self._detail_badges.set_shortcut(shortcut)
        self._default_note.setText(
            "This is the default shortcut."
            if shortcut_is_default(self._settings, definition.id)
            else "This shortcut has been customized."
        )
        self._reset_btn.setEnabled(
            not shortcut_is_default(self._settings, definition.id)
        )

    def _on_change_clicked(self) -> None:
        row = self._rows_by_id.get(self._selected_id)
        if row is None:
            return
        definition = row.definition
        while True:
            capture = _ShortcutCaptureDialog(
                definition,
                get_shortcut(self._settings, definition.id),
                self,
            )
            if capture.exec() != QDialog.DialogCode.Accepted:
                return

            shortcut = capture.shortcut()
            if not shortcut:
                set_shortcut(self._settings, definition.id, "")
                self._save_settings()
                self._refresh_all()
                return

            conflict = find_shortcut_conflict(
                self._settings,
                definition.id,
                shortcut,
            )
            if conflict is None:
                set_shortcut(self._settings, definition.id, shortcut)
                self._save_settings()
                self._refresh_all()
                return

            conflict_dialog = _ShortcutConflictDialog(
                shortcut,
                definition,
                conflict,
                self,
            )
            if conflict_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            if conflict_dialog.choice() == "pick":
                continue
            if conflict_dialog.choice() == "use":
                set_shortcut(self._settings, conflict.id, "")
                set_shortcut(self._settings, definition.id, shortcut)
                self._save_settings()
                self._refresh_all()
                return

    def _on_reset_current(self) -> None:
        if not self._selected_id:
            return
        reset_shortcut(self._settings, self._selected_id)
        self._save_settings()
        self._refresh_all()

    def _on_reset_all(self) -> None:
        dialog = _ResetAllShortcutsDialog(shortcut_count(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        reset_all_shortcuts(self._settings)
        self._save_settings()
        self._refresh_all()

    def _save_settings(self) -> None:
        save = getattr(self._settings, "save", None)
        if callable(save):
            save()
