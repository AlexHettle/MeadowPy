"""Shared item delegates used by MeadowPy panels."""

from PyQt6.QtWidgets import QStyle, QStyledItemDelegate


class NoFocusDelegate(QStyledItemDelegate):
    """Suppresses the dotted focus rectangle on item views."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus
