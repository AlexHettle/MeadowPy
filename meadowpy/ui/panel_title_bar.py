"""Shared setup for custom dock panel title bars."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy


PANEL_TITLE_BAR_HEIGHT = 36
PANEL_TITLE_CONTENT_HEIGHT = 24
PANEL_TITLE_CONTROL_SIZE = 24
PANEL_TITLE_ICON_BUTTON_SIZE = 22
PANEL_TITLE_ICON_SIZE = 16
PANEL_TITLE_LEFT_MARGIN = 10
PANEL_TITLE_RIGHT_MARGIN = 6
PANEL_TITLE_VERTICAL_MARGIN = 6


def configure_panel_title_bar(
    title_bar,
    layout,
    *,
    right_margin=PANEL_TITLE_RIGHT_MARGIN,
    spacing=6,
) -> None:
    """Apply the common dock title-bar sizing and vertical centering."""
    title_bar.setFixedHeight(PANEL_TITLE_BAR_HEIGHT)
    title_bar.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    layout.setContentsMargins(
        PANEL_TITLE_LEFT_MARGIN,
        PANEL_TITLE_VERTICAL_MARGIN,
        right_margin,
        PANEL_TITLE_VERTICAL_MARGIN,
    )
    layout.setSpacing(spacing)
    layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)


def configure_panel_title_label(label) -> None:
    """Keep title text baselines consistent with icon/button title bars."""
    label.setFixedHeight(PANEL_TITLE_CONTENT_HEIGHT)
    label.setAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    label.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed,
    )
