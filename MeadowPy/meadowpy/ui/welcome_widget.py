"""Welcome screen shown when MeadowPy launches with no files open."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from meadowpy.ui.welcome_hero import _WelcomeHeroWidget
from meadowpy.ui.welcome_templates import TEMPLATES


class WelcomeWidget(QWidget):
    """Welcome screen displayed as a tab when no files are open.

    Signals
    -------
    action_new_file()
        User clicked the New File button.
    action_open_file()
        User clicked the Open File button.
    action_open_folder()
        User clicked the Open Folder button.
    template_selected(str, str)
        User clicked a template.  Arguments: (tab_name, code).
    """

    action_new_file = pyqtSignal()
    action_open_file = pyqtSignal()
    action_open_folder = pyqtSignal()
    template_selected = pyqtSignal(str, str)   # (tab_name, code)

    def __init__(
        self,
        theme_name: str = "default_light",
        custom_base: str = "dark",
        custom_accent: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("WelcomeWidget")
        self._setup_ui()
        self.apply_theme(theme_name, custom_base, custom_accent)

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scroll area so the welcome page can be viewed even when the
        # window is shorter than the content (e.g. with tabs open).
        scroll = QScrollArea()
        scroll.setObjectName("welcomeScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Let the theme background (light or dark) show through instead of
        # the scroll area's default opaque viewport colour.
        scroll.setStyleSheet(
            "QScrollArea#welcomeScrollArea, "
            "QScrollArea#welcomeScrollArea > QWidget > QWidget "
            "{ background: transparent; }"
        )
        outer.addWidget(scroll)

        scroll_content = QWidget()
        scroll_content.setObjectName("welcomeScrollContent")
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        scroll.setWidget(scroll_content)
        scroll_outer = QVBoxLayout(scroll_content)
        scroll_outer.setContentsMargins(0, 0, 0, 0)

        # Scrollable center column
        center = QWidget()
        center.setObjectName("welcomeCenter")
        # Allow dock panels to narrow the editor without forcing the hidden
        # horizontal scrollbar to clip the welcome content.
        center.setMinimumWidth(0)
        center.setMaximumWidth(720)
        center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        # ── Title area ────────────────────────────────────────────
        self._hero_widget = _WelcomeHeroWidget(self)
        layout.addWidget(self._hero_widget)

        layout.addSpacing(24)

        # ── Quick actions row ─────────────────────────────────────
        actions_label = QLabel("Get Started")
        actions_label.setObjectName("welcomeSectionLabel")
        section_font = QFont()
        section_font.setPointSize(12)
        section_font.setBold(True)
        actions_label.setFont(section_font)
        actions_label.setWordWrap(True)
        actions_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(actions_label)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        new_btn = self._make_action_btn("New File", "Create a blank Python file")
        new_btn.clicked.connect(self.action_new_file.emit)
        actions_row.addWidget(new_btn)

        open_btn = self._make_action_btn("Open File", "Open an existing file")
        open_btn.clicked.connect(self.action_open_file.emit)
        actions_row.addWidget(open_btn)

        folder_btn = self._make_action_btn("Open Folder", "Open a project folder")
        folder_btn.clicked.connect(self.action_open_folder.emit)
        actions_row.addWidget(folder_btn)

        layout.addLayout(actions_row)

        layout.addSpacing(24)

        # ── Templates grid ────────────────────────────────────────
        templates_label = QLabel("Quick-Start Templates")
        templates_label.setObjectName("welcomeSectionLabel")
        templates_label.setFont(section_font)
        templates_label.setWordWrap(True)
        templates_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(templates_label)

        # Build the grid as stacked HBox rows inside a VBox.
        # We use setSpacing(0) plus explicit addSpacing(...) between rows
        # so the gap is a hard guarantee — previous spacing values were
        # being visually collapsed somewhere in the layout tree.
        grid_wrap = QVBoxLayout()
        grid_wrap.setSpacing(0)
        grid_wrap.setContentsMargins(0, 0, 0, 0)

        COLS = 3
        H_GAP = 14   # horizontal gap between cards in a row
        V_GAP = 22   # vertical gap between rows — tuned so it visually
        # matches the horizontal gap (Qt's addSpacing is exact pixels;
        # HBox setSpacing renders slightly larger due to card borders/radius)
        current_row = None
        for idx, tmpl in enumerate(TEMPLATES):
            if idx % COLS == 0:
                if idx != 0:
                    grid_wrap.addSpacing(V_GAP)
                current_row = QHBoxLayout()
                current_row.setSpacing(H_GAP)
                grid_wrap.addLayout(current_row)
            current_row.addWidget(self._make_template_card(tmpl), 1)

        # If the last row is short, pad with invisible placeholders so
        # remaining cards keep their 1/3 width (don't stretch to fill).
        remainder = len(TEMPLATES) % COLS
        if remainder and current_row is not None:
            for _ in range(COLS - remainder):
                spacer = QWidget()
                spacer.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
                )
                current_row.addWidget(spacer, 1)

        layout.addLayout(grid_wrap)

        layout.addStretch(1)

        # Center the column horizontally inside the scroll area
        scroll_outer.addStretch(1)
        h_box = QHBoxLayout()
        # Give the center column all available width until it reaches its
        # 720-pixel cap.  Zero-stretch side spacers then share any remainder,
        # keeping the full-width column centered without collapsing it.
        h_box.addStretch()
        h_box.addWidget(center, 1)
        h_box.addStretch()
        scroll_outer.addLayout(h_box)
        scroll_outer.addStretch(1)

    def apply_theme(
        self,
        theme_name: str,
        custom_base: str = "dark",
        custom_accent: str | None = None,
    ) -> None:
        """Refresh the welcome hero styling for the current theme."""
        self._hero_widget.apply_theme(theme_name, custom_base, custom_accent)

    # ── Widget builders ───────────────────────────────────────────

    def _make_action_btn(self, text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("welcomeActionBtn")
        btn.setToolTip(tooltip)
        btn.setMinimumHeight(40)
        # Let the three-button row contract with narrow editor viewports;
        # the labels still have enough room at the supported window minimum.
        btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _make_template_card(self, tmpl: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("welcomeTemplateCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        # Lock the card to a uniform size so every row looks identical,
        # regardless of whether the description wraps to 1 or 2 lines.
        card.setFixedHeight(110)
        # The three-column grid must be able to contract with its container.
        # Its labels already wrap and ignore their intrinsic width hints.
        card.setMinimumWidth(0)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        header = QLabel(f"{tmpl['icon']}  {tmpl['name']}")
        header.setObjectName("welcomeCardTitle")
        header_font = QFont()
        header_font.setPointSize(11)
        header_font.setBold(True)
        header.setFont(header_font)
        # Allow the title to wrap and ignore its own size hint so one long
        # name (e.g. "Temperature Converter") doesn't force its column wider
        # than the others.
        header.setWordWrap(True)
        header.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        card_layout.addWidget(header)

        desc = QLabel(tmpl["desc"])
        desc.setObjectName("welcomeCardDesc")
        desc.setWordWrap(True)
        # Same trick as the title — don't let description minWidth push
        # the column wider than the stretch allocation.
        desc.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc.setFont(desc_font)
        card_layout.addWidget(desc)

        card_layout.addStretch()

        # Make the whole card clickable without treating context or
        # middle-click gestures as requests to open the template.
        card.mousePressEvent = (
            lambda event, template=tmpl: self._on_template_card_pressed(
                event, template
            )
        )
        return card

    def _on_template_card_pressed(self, event, tmpl: dict) -> None:
        """Open a template only for the standard left-button gesture."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_template_clicked(tmpl)

    def _on_template_clicked(self, tmpl: dict) -> None:
        self.template_selected.emit(tmpl["name"], tmpl["code"])
