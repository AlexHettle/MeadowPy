"""Toolbar construction."""

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
)
from PyQt6.QtWidgets import QToolBar, QToolButton, QWidget

from meadowpy.core.shortcuts import get_default_shortcut, get_shortcut
from meadowpy.resources.resource_loader import (
    load_themed_icon,
    theme_is_dark,
    theme_is_high_contrast,
)


class RunFileButton(QToolButton):
    """Fixed-size toolbar run button that elides long target names."""

    _WIDTH = 190
    _HEIGHT = 32
    _LABEL_PIXEL_SIZE = 13
    _HORIZONTAL_PAD = 12
    _RIGHT_PAD = 8
    _ICON_SIZE = 12
    _ICON_GAP = 8
    _CONTENT_X_OFFSET = -2
    _ICON_Y_OFFSET = 1

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.setObjectName("runButton")
        self.setDefaultAction(action)
        self.setFixedSize(self._WIDTH, self._HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._label_font = self.font()
        self._apply_label_font()
        self._target_name = "File"
        self._accent = QColor("#2F7A44")
        action.changed.connect(self._sync_from_action)
        self._sync_from_action()

    def _apply_label_font(self) -> None:
        self._label_font = self.font()
        self._label_font.setPixelSize(self._LABEL_PIXEL_SIZE)
        self._label_font.setBold(True)

    def set_target_name(self, name: str | None) -> None:
        self._target_name = (name or "File").strip() or "File"
        self._sync_text()
        self.update()

    def set_accent_color(self, hex_color: str) -> None:
        color = QColor(hex_color)
        if color.isValid():
            self._accent = color
            self.update()

    def displayed_text(self) -> str:
        return self._elide_text(self._full_label(), self._available_text_width())

    def event(self, event) -> bool:
        result = super().event(event)
        if event.type() in {
            QEvent.Type.StyleChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.FontChange,
        }:
            self._apply_label_font()
            self.update()
        return result

    def _sync_from_action(self) -> None:
        action = self.defaultAction()
        if action is None:
            return
        self.setEnabled(action.isEnabled())
        self.setToolTip(action.toolTip())
        self._sync_text()
        self.update()

    def _sync_text(self) -> None:
        label = self._full_label()
        self.setText(label)
        self.setAccessibleName(label)

    def _verb(self) -> str:
        action = self.defaultAction()
        tooltip = action.toolTip() if action is not None else ""
        if tooltip.startswith("Continue"):
            return "Continue"
        return "Run"

    def _full_label(self) -> str:
        verb = self._verb()
        if verb == "Continue":
            return verb
        return f"{verb} {self._target_name}"

    def _available_text_width(self) -> int:
        return (
            self.width()
            - (self._HORIZONTAL_PAD * 2)
            - self._ICON_SIZE
            - self._ICON_GAP
        )

    def _elide_text(self, text: str, max_width: int) -> str:
        metrics = QFontMetrics(self._label_font)
        if metrics.horizontalAdvance(text) <= max_width:
            return text

        ellipsis = "..."
        if max_width <= metrics.horizontalAdvance(ellipsis):
            return ellipsis

        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            candidate = f"{text[:mid].rstrip()}{ellipsis}"
            if metrics.horizontalAdvance(candidate) <= max_width:
                low = mid
            else:
                high = mid - 1
        return f"{text[:low].rstrip()}{ellipsis}" if low else ellipsis

    def _foreground_for(self, background: QColor) -> QColor:
        brightness = (
            background.red() * 0.299
            + background.green() * 0.587
            + background.blue() * 0.114
        )
        return QColor("#000000") if brightness > 180 else QColor("#FFFFFF")

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._label_font)

        bg = QColor(self._accent)
        if not self.isEnabled():
            bg = QColor("#555555")
            fg = QColor("#888888")
        elif self.isDown():
            bg = bg.darker(125)
            fg = self._foreground_for(bg)
        elif self.underMouse():
            bg = bg.darker(112)
            fg = self._foreground_for(bg)
        else:
            fg = self._foreground_for(bg)

        rect = self.rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 6, 6)

        center_y = self.rect().center().y()
        label = self.displayed_text()
        label_width = QFontMetrics(self._label_font).horizontalAdvance(label)
        content_width = self._ICON_SIZE + self._ICON_GAP + label_width
        icon_left = int((self.width() - content_width) / 2) + self._CONTENT_X_OFFSET
        icon_half = self._ICON_SIZE // 2
        icon_top = center_y - icon_half + self._ICON_Y_OFFSET
        icon_bottom = center_y + icon_half + self._ICON_Y_OFFSET
        icon_center_y = center_y + self._ICON_Y_OFFSET
        icon_tip = icon_left + self._ICON_SIZE
        triangle = QPainterPath()
        triangle.moveTo(icon_left + 2.2, icon_top + 1.0)
        triangle.cubicTo(
            icon_left + 0.8,
            icon_top + 0.1,
            icon_left,
            icon_top + 1.1,
            icon_left,
            icon_top + 2.8,
        )
        triangle.lineTo(icon_left, icon_bottom - 2.8)
        triangle.cubicTo(
            icon_left,
            icon_bottom - 1.1,
            icon_left + 0.8,
            icon_bottom - 0.1,
            icon_left + 2.2,
            icon_bottom - 1.0,
        )
        triangle.lineTo(icon_tip - 3.0, icon_center_y + 1.8)
        triangle.cubicTo(
            icon_tip - 0.5,
            icon_center_y + 0.6,
            icon_tip - 0.5,
            icon_center_y - 0.6,
            icon_tip - 3.0,
            icon_center_y - 1.8,
        )
        triangle.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fg)
        painter.drawPath(triangle)

        text_left = icon_left + self._ICON_SIZE + self._ICON_GAP
        text_rect = self.rect().adjusted(text_left, 0, -self._RIGHT_PAD, 0)
        painter.setPen(fg)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )
        painter.end()


class CompactRunControlButton(QToolButton):
    """Compact text+symbol toolbar button with deterministic label painting."""

    _HEIGHT = RunFileButton._HEIGHT
    _ICON_SIZE = 12
    _ICON_GAP = 7
    _HORIZONTAL_PAD = 8
    _WIDTH_SLACK = 4
    _STOP_COLOR = QColor("#E51400")
    _DEBUG_COLOR = QColor("#FF9800")

    def __init__(self, action, label: str, symbol: str, width: int, parent=None):
        super().__init__(parent)
        self.setDefaultAction(action)
        self._base_width = width
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(self._ICON_SIZE, self._ICON_SIZE))
        self.setAutoRaise(False)
        self._label = label
        self._symbol = symbol
        self._is_dark = True
        self._is_high_contrast = False
        self._label_font = self.font()
        self._apply_label_font()
        self._refresh_fixed_size()
        action.changed.connect(self._sync_from_action)
        self._sync_from_action()

    def _apply_label_font(self) -> None:
        self._label_font = self.font()
        self._label_font.setPixelSize(RunFileButton._LABEL_PIXEL_SIZE)
        self._label_font.setBold(True)

    def apply_theme(self, theme_name: str, custom_base: str = "dark") -> None:
        self._is_high_contrast = theme_is_high_contrast(theme_name)
        self._is_dark = theme_is_dark(theme_name, custom_base)
        self.update()

    def displayed_text(self) -> str:
        metrics = QFontMetrics(self._label_font)
        if metrics.horizontalAdvance(self._label) <= self._available_text_width():
            return self._label
        return metrics.elidedText(
            self._label,
            Qt.TextElideMode.ElideRight,
            self._available_text_width(),
        )

    def event(self, event) -> bool:
        result = super().event(event)
        if event.type() in {
            QEvent.Type.StyleChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.FontChange,
        }:
            self._apply_label_font()
            self._refresh_fixed_size()
            self.update()
        return result

    def _content_width(self) -> int:
        return (
            QFontMetrics(self._label_font).horizontalAdvance(self._label)
            + (self._HORIZONTAL_PAD * 2)
            + self._ICON_SIZE
            + self._ICON_GAP
            + self._WIDTH_SLACK
        )

    def _refresh_fixed_size(self) -> None:
        self.setFixedSize(max(self._base_width, self._content_width()), self._HEIGHT)

    def _available_text_width(self) -> int:
        return (
            self.width()
            - (self._HORIZONTAL_PAD * 2)
            - self._ICON_SIZE
            - self._ICON_GAP
        )

    def _sync_from_action(self) -> None:
        action = self.defaultAction()
        if action is None:
            return
        self.setText(self._label)
        self.setAccessibleName(self._label)
        self.setToolTip(action.toolTip())
        self.setEnabled(action.isEnabled())
        self.update()

    def _colors(self) -> tuple[QColor, QColor, QColor | None]:
        if self._is_high_contrast:
            fg = QColor("#FFFFFF") if self.isEnabled() else QColor("#7F7F7F")
            border = (
                QColor("#FFFFFF")
                if self.isEnabled()
                and (self.underMouse() or self.isDown() or self.hasFocus())
                else None
            )
            return QColor("#000000"), fg, border

        if self._is_dark:
            bg = QColor("#4A4E52")
            hover_bg = QColor("#565B60")
            press_bg = QColor("#3F4347")
            disabled_bg = QColor("#3A3D40")
            disabled_fg = QColor("#B8BEC4")
            border_hover = QColor("#6A7076")
        else:
            bg = QColor("#5C636A")
            hover_bg = QColor("#687079")
            press_bg = QColor("#4E555C")
            disabled_bg = QColor("#E2E6EA")
            disabled_fg = QColor("#495057")
            border_hover = QColor("#7A838C")

        if not self.isEnabled():
            return disabled_bg, disabled_fg, None
        if self.isDown():
            return press_bg, QColor("#FFFFFF"), border_hover
        if self.underMouse():
            return hover_bg, QColor("#FFFFFF"), border_hover
        return bg, QColor("#FFFFFF"), None

    def symbol_color(self) -> QColor:
        """Return the semantic glyph color for the current theme/state."""
        if self._is_high_contrast:
            return QColor("#FFFFFF") if self.isEnabled() else QColor("#7F7F7F")
        if self._symbol == "debug":
            return QColor(self._DEBUG_COLOR)
        return QColor(self._STOP_COLOR)

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._label_font)

        bg, fg, border = self._colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(bg)
        if border is None:
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setPen(border)
        painter.drawRoundedRect(rect, 5, 5)

        label = self.displayed_text()
        label_width = QFontMetrics(self._label_font).horizontalAdvance(label)
        content_width = self._ICON_SIZE + self._ICON_GAP + label_width
        content_left = int((self.width() - content_width) / 2)
        center_y = self.rect().center().y()
        icon_top = center_y - (self._ICON_SIZE / 2) + 0.5
        icon_rect = QRectF(
            content_left,
            icon_top,
            self._ICON_SIZE,
            self._ICON_SIZE,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.symbol_color())
        if self._symbol == "debug":
            self._paint_debug_diamond(painter, icon_rect)
        else:
            painter.drawRoundedRect(icon_rect.adjusted(1, 1, -1, -1), 2, 2)

        text_rect = QRectF(
            content_left + self._ICON_SIZE + self._ICON_GAP,
            0,
            label_width,
            self.height(),
        )
        painter.setPen(fg)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )
        painter.end()

    def _paint_debug_diamond(self, painter: QPainter, rect: QRectF) -> None:
        cx = rect.center().x()
        cy = rect.center().y()
        half = rect.width() / 2
        diamond = QPainterPath()
        diamond.moveTo(cx, cy - half)
        diamond.lineTo(cx + half, cy)
        diamond.lineTo(cx, cy + half)
        diamond.lineTo(cx - half, cy)
        diamond.closeSubpath()
        painter.drawPath(diamond)


class ToolBarBuilder:
    """Builds the main toolbar with icon buttons."""

    _COMPACT_CONTROL_HEIGHT = CompactRunControlButton._HEIGHT
    _COMPACT_CONTROL_ICON_SIZE = CompactRunControlButton._ICON_SIZE
    _STOP_CONTROL_WIDTH = 82
    _DEBUG_CONTROL_WIDTH = 94

    def __init__(self, main_window):
        self._window = main_window
        self._tooltip_actions = []
        self._compact_controls = []

    def build(self) -> QToolBar:
        """Build and return the main toolbar."""
        toolbar = QToolBar("Main Toolbar", self._window)
        toolbar.setObjectName("MainToolBar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        self._add(
            toolbar,
            "new",
            "Create a new blank file",
            self._window.action_new_file,
            "file.new",
        )
        self._add(
            toolbar,
            "open_file",
            "Open an existing file",
            self._window.action_open_file,
            "file.open",
        )
        self._add(
            toolbar,
            "save",
            "Save the current file",
            self._window.action_save,
            "file.save",
        )
        toolbar.addSeparator()
        self._add(
            toolbar,
            "undo",
            "Undo last change",
            lambda: self._editor_call("undo"),
            "edit.undo",
        )
        self._add(
            toolbar,
            "redo",
            "Redo undone change",
            lambda: self._editor_call("redo"),
            "edit.redo",
        )
        toolbar.addSeparator()
        self._add(
            toolbar,
            "find",
            "Find text in the current file",
            self._window.action_toggle_find,
            "edit.find",
        )
        toolbar.addSeparator()

        # Run/Stop/Debug use shared QActions from main_window so enable/disable
        # stays in sync across menu and toolbar.
        run_left_margin = QWidget(toolbar)
        run_left_margin.setFixedWidth(4)
        toolbar.addWidget(run_left_margin)
        run_btn = RunFileButton(self._window._run_action, toolbar)
        toolbar.addWidget(run_btn)
        self._stop_btn = self._add_compact_control(
            toolbar,
            self._window._stop_action,
            object_name="stopButton",
            label="Stop",
            symbol="stop",
            width=self._STOP_CONTROL_WIDTH,
        )
        self._debug_btn = self._add_compact_control(
            toolbar,
            self._window._debug_action,
            object_name="debugButton",
            label="Debug",
            symbol="debug",
            width=self._DEBUG_CONTROL_WIDTH,
        )

        # Debug step actions — hidden until a debug session starts
        toolbar.addSeparator()
        self._debug_separator = toolbar.actions()[-1]  # the separator we just added
        self._debug_separator.setVisible(False)

        self._window._step_over_action = toolbar.addAction(
            self._icon("step_over"), "Step Over"
        )
        self._track_tooltip(
            self._window._step_over_action,
            "Step Over",
            "debug.step_over",
        )
        self._window._step_over_action.setVisible(False)

        self._window._step_into_action = toolbar.addAction(
            self._icon("step_into"), "Step Into"
        )
        self._track_tooltip(
            self._window._step_into_action,
            "Step Into",
            "debug.step_into",
        )
        self._window._step_into_action.setVisible(False)

        self._window._step_out_action = toolbar.addAction(
            self._icon("step_out"), "Step Out"
        )
        self._track_tooltip(
            self._window._step_out_action,
            "Step Out",
            "debug.step_out",
        )
        self._window._step_out_action.setVisible(False)

        # Remember the run button so its fill can be re-tinted when the user
        # switches to a custom theme with a different accent colour.
        self._run_btn = run_btn
        self.update_run_file_label(self._window._tab_manager.current_editor())

        self._window._debug_separator = self._debug_separator
        self._window.addToolBar(toolbar)
        return toolbar

    def update_accent_color(self, hex_color: str) -> None:
        """Refresh the Run button fill color (called on theme change)."""
        if getattr(self, "_run_btn", None):
            self._run_btn.set_accent_color(hex_color)
        self._apply_compact_control_theme()

    def update_run_file_label(self, editor=None) -> None:
        """Update the fixed Run button label from the active editor."""
        run_btn = getattr(self, "_run_btn", None)
        if run_btn is None:
            return
        display_name = getattr(editor, "display_name", None)
        run_btn.set_target_name(display_name or "File")

    def update_shortcut_tooltips(self) -> None:
        """Refresh toolbar tooltip text after shortcut customization."""
        for action, text, shortcut_id in self._tooltip_actions:
            self._apply_tooltip(action, text, shortcut_id)

    def _add(
        self,
        toolbar: QToolBar,
        icon_name: str,
        tooltip: str,
        callback,
        shortcut_id: str | None = None,
    ) -> None:
        action = toolbar.addAction(self._icon(icon_name), tooltip, callback)
        if shortcut_id is None:
            action.setToolTip(tooltip)
        else:
            self._track_tooltip(action, tooltip, shortcut_id)

    def _add_compact_control(
        self,
        toolbar: QToolBar,
        action,
        *,
        object_name: str,
        label: str,
        symbol: str,
        width: int,
    ) -> CompactRunControlButton:
        button = CompactRunControlButton(action, label, symbol, width, toolbar)
        button.setObjectName(object_name)
        button.setProperty("compactRunControl", True)
        toolbar.addWidget(button)
        self._compact_controls.append(button)
        self._apply_compact_control_theme()
        return button

    def _apply_compact_control_theme(self) -> None:
        theme_name = self._window._settings.get("editor.theme") or ""
        custom_base = self._window._settings.get("editor.custom_theme.base") or "dark"
        for button in self._compact_controls:
            button.apply_theme(theme_name, custom_base)

    def _track_tooltip(self, action, text: str, shortcut_id: str) -> None:
        self._tooltip_actions.append((action, text, shortcut_id))
        self._apply_tooltip(action, text, shortcut_id)

    def _apply_tooltip(self, action, text: str, shortcut_id: str) -> None:
        shortcut = self._active_shortcut(shortcut_id)
        action.setToolTip(f"{text} ({shortcut})" if shortcut else text)

    def _active_shortcut(self, shortcut_id: str) -> str:
        settings = getattr(self._window, "_settings", None)
        if settings is not None:
            return get_shortcut(settings, shortcut_id)
        return get_default_shortcut(shortcut_id)

    def _icon(self, name: str) -> QIcon:
        # Route through the themed loader so colorful SVGs (run/debug/stop/
        # restart) get rewritten to the HC accent when High Contrast is on.
        theme_name = self._window._settings.get("editor.theme") or ""
        return load_themed_icon(name, theme_name)

    def _editor_call(self, method: str) -> None:
        editor = self._window._tab_manager.current_editor()
        if editor and hasattr(editor, method):
            getattr(editor, method)()
