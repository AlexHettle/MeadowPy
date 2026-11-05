import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor, QPainter, QPalette, QPixmap, QTextDocument
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem, QTreeWidget, QTreeWidgetItem

from meadowpy.ui import symbol_outline


@pytest.mark.parametrize("kind", ["class", "function", "method"])
@pytest.mark.parametrize("selected", [False, True])
def test_symbol_delegate_uses_selection_text_color(qapp, monkeypatch, kind, selected):
    documents = []

    class CapturedDocument(QTextDocument):
        def __init__(self):
            super().__init__()
            documents.append(self)

    monkeypatch.setattr(symbol_outline, "QTextDocument", CapturedDocument)
    tree = QTreeWidget()
    tree.setColumnCount(1)
    item = QTreeWidgetItem(tree, ["sample"])
    item.setData(0, symbol_outline._KIND_ROLE, kind)
    item.setData(0, symbol_outline._NAME_ROLE, "sample")
    delegate = symbol_outline._SymbolItemDelegate(tree)
    delegate.set_accent_color("#246824")
    option = QStyleOptionViewItem()
    option.widget = tree
    option.rect = QRect(0, 0, 200, 30)
    option.state = QStyle.StateFlag.State_Enabled
    if selected:
        option.state |= QStyle.StateFlag.State_Selected
    option.palette.setColor(QPalette.ColorRole.Text, QColor("#123456"))
    option.palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#fedcba"))
    # Normal text would disappear against this selected-row background.
    option.palette.setColor(QPalette.ColorRole.Highlight, QColor("#123456"))
    pixmap = QPixmap(200, 30)
    pixmap.fill(QColor("white"))
    painter = QPainter(pixmap)
    try:
        delegate.paint(painter, option, tree.indexFromItem(item))
    finally:
        painter.end()
        tree.deleteLater()

    assert len(documents) == 1
    document = documents[0]
    expected = "#fedcba" if selected else "#123456"
    name_cursor = document.find("sample")
    assert not name_cursor.isNull()
    assert name_cursor.charFormat().foreground().color().name() == expected
    glyph = delegate._CLASS_GLYPH if kind == "class" else delegate._FUNC_GLYPH
    glyph_cursor = document.find(glyph)
    assert not glyph_cursor.isNull()
    glyph_color = "#246824" if kind == "class" else expected
    assert glyph_cursor.charFormat().foreground().color().name() == glyph_color
