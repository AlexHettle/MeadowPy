"""Custom accent-color picker dialog.

A premium, fully-custom replacement for QColorDialog designed to match
MeadowPy's dark visual language. Features:
  - Saturation × Value gradient canvas with a vertical hue rainbow strip
  - Hex and R / G / B numeric inputs (all bidirectionally synced)
  - Before / After colour-preview swatch
  - Curated 24-colour preset palette
"""

from typing import Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, QRegularExpression, pyqtSignal
from PyQt6.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath,
    QPen, QBrush, QRegularExpressionValidator,
)
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpinBox, QVBoxLayout,
    QWidget,
)


# ── Curated preset palette (24 colours) ──────────────────────────────
_PRESETS: list[str] = [
    # Warm → cool spectrum
    "#EF4444", "#F97316", "#F59E0B", "#EAB308",
    "#84CC16", "#22C55E", "#14B8A6", "#06B6D4",
    "#3B82F6", "#6366F1", "#8B5CF6", "#EC4899",
    # Deeper / richer shades
    "#DC2626", "#EA580C", "#D97706", "#CA8A04",
    "#16A34A", "#0D9488", "#0284C7", "#2563EB",
    "#4F46E5", "#7C3AED", "#DB2777", "#475569",
]
_PAL_COLS = 12  # columns per palette row


# ══════════════════════════════════════════════════════════════════════
#  Internal widgets
# ══════════════════════════════════════════════════════════════════════

class _SVCanvas(QWidget):
    """Saturation × Value 2-D gradient picker.

    Horizontal axis: saturation  0 → 1  (left  → right)
    Vertical axis:   value       1 → 0  (top   → bottom)
    """

    sv_changed = pyqtSignal(float, float)  # (sat, val)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._hue: float = 0.0
        self._sat: float = 1.0
        self._val: float = 1.0
        self.setMinimumSize(230, 190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ── Public API ─────────────────────────────────────────────────────

    def set_hsv(self, h: float, s: float, v: float) -> None:
        """Push a new HSV state without emitting signals."""
        self._hue, self._sat, self._val = h, s, v
        self.update()

    # ── Painting ───────────────────────────────────────────────────────

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        rect = QRectF(0.0, 0.0, w, h)

        # Rounded clip so the canvas looks polished
        clip = QPainterPath()
        clip.addRoundedRect(rect, 8.0, 8.0)
        p.setClipPath(clip)

        # Layer 1 — saturation axis: white → full-hue colour (left → right)
        hue_col = QColor.fromHsvF(self._hue, 1.0, 1.0)
        sat_grad = QLinearGradient(0.0, 0.0, w, 0.0)
        sat_grad.setColorAt(0.0, QColor(255, 255, 255))
        sat_grad.setColorAt(1.0, hue_col)
        p.fillRect(rect, QBrush(sat_grad))

        # Layer 2 — value axis: transparent → opaque black (top → bottom)
        val_grad = QLinearGradient(0.0, 0.0, 0.0, h)
        val_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        val_grad.setColorAt(1.0, QColor(0, 0, 0, 255))
        p.fillRect(rect, QBrush(val_grad))

        # Cursor — small circle with an anti-aliased double ring for legibility
        cx = self._sat * w
        cy = (1.0 - self._val) * h
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Outer dark shadow ring (contrast on light backgrounds)
        p.setPen(QPen(QColor(0, 0, 0, 110), 1.5))
        p.drawEllipse(QPointF(cx, cy), 7.5, 7.5)
        # Inner white ring
        p.setPen(QPen(QColor(255, 255, 255, 230), 2.0))
        p.drawEllipse(QPointF(cx, cy), 6.0, 6.0)

    # ── Interaction ────────────────────────────────────────────────────

    def _pick(self, x: float, y: float) -> None:
        w, h = float(self.width()), float(self.height())
        self._sat = max(0.0, min(1.0, x / w))
        self._val = max(0.0, min(1.0, 1.0 - y / h))
        self.update()
        self.sv_changed.emit(self._sat, self._val)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._pick(e.position().x(), e.position().y())

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._pick(e.position().x(), e.position().y())


class _HueBar(QWidget):
    """Vertical rainbow strip for hue selection."""

    hue_changed = pyqtSignal(float)  # 0..1

    # Hue rainbow gradient stops
    _STOPS: list[tuple[float, str]] = [
        (0.000, "#FF0000"),
        (0.167, "#FFFF00"),
        (0.333, "#00FF00"),
        (0.500, "#00FFFF"),
        (0.667, "#0000FF"),
        (0.833, "#FF00FF"),
        (1.000, "#FF0000"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._hue: float = 0.0
        self.setFixedWidth(20)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.SizeVerCursor)

    # ── Public API ─────────────────────────────────────────────────────

    def set_hue(self, hue: float) -> None:
        """Push hue without emitting signals."""
        self._hue = hue
        self.update()

    # ── Painting ───────────────────────────────────────────────────────

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())

        # Rounded clip for the gradient strip
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0.0, 0.0, w, h), 5.0, 5.0)
        p.setClipPath(clip)

        grad = QLinearGradient(0.0, 0.0, 0.0, h)
        for pos, hex_col in self._STOPS:
            grad.setColorAt(pos, QColor(hex_col))
        p.fillRect(QRectF(0.0, 0.0, w, h), QBrush(grad))

        # Thumb indicator — centred on current hue position
        ty = self._hue * h
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Shadow stroke
        p.setPen(QPen(QColor(0, 0, 0, 120), 1.0))
        p.drawRoundedRect(QRectF(0.5, ty - 5.0, w - 1.0, 10.0), 3.0, 3.0)
        # White stroke
        p.setPen(QPen(QColor(255, 255, 255, 220), 2.0))
        p.drawRoundedRect(QRectF(1.5, ty - 4.0, w - 3.0, 8.0), 2.5, 2.5)

    # ── Interaction ────────────────────────────────────────────────────

    def _pick(self, y: float) -> None:
        self._hue = max(0.0, min(1.0, y / float(self.height())))
        self.update()
        self.hue_changed.emit(self._hue)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._pick(e.position().y())

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._pick(e.position().y())


# ══════════════════════════════════════════════════════════════════════
#  Public dialog
# ══════════════════════════════════════════════════════════════════════

class AccentColorPickerDialog(QDialog):
    """Premium accent-colour picker that replaces the stock QColorDialog."""

    def __init__(
        self,
        initial_hex: str = "#3B82F6",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pick accent color")
        self.setModal(True)
        self.setMinimumWidth(510)

        # Canonical HSV state (floats 0..1)
        self._h: float = 0.0
        self._s: float = 1.0
        self._v: float = 1.0
        self._initial_hex = initial_hex

        self._build_ui()
        self._apply_stylesheet()
        self._push_color(QColor(initial_hex), init=True)

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(18)

        # ╔══ Picker row ════════════════════════════════════════════════╗
        picker_row = QHBoxLayout()
        picker_row.setSpacing(10)

        self._canvas = _SVCanvas()
        self._huebar = _HueBar()
        self._canvas.sv_changed.connect(self._on_sv_changed)
        self._huebar.hue_changed.connect(self._on_hue_changed)
        picker_row.addWidget(self._canvas, 1)
        picker_row.addWidget(self._huebar)
        picker_row.addSpacing(10)

        # ── Right-hand info column ──────────────────────────────────────
        info = QVBoxLayout()
        info.setSpacing(14)

        # Before / After preview swatch (split rectangle)
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(0)
        self._sw_old = QLabel()
        self._sw_old.setFixedSize(56, 42)
        self._sw_old.setToolTip("Before")
        self._sw_new = QLabel()
        self._sw_new.setFixedSize(56, 42)
        self._sw_new.setToolTip("After")
        swatch_row.addWidget(self._sw_old)
        swatch_row.addWidget(self._sw_new)
        swatch_row.addStretch()
        info.addLayout(swatch_row)

        # Hex field
        hex_row = QHBoxLayout()
        hex_row.setSpacing(5)
        hash_lbl = QLabel("#")
        hash_lbl.setObjectName("colorHash")
        self._hex_edit = QLineEdit()
        self._hex_edit.setMaxLength(6)
        self._hex_edit.setFixedWidth(82)
        self._hex_edit.setPlaceholderText("RRGGBB")
        self._hex_edit.setValidator(
            QRegularExpressionValidator(
                QRegularExpression("[0-9A-Fa-f]{0,6}"), self
            )
        )
        self._hex_edit.textEdited.connect(self._on_hex_edited)
        hex_row.addWidget(hash_lbl)
        hex_row.addWidget(self._hex_edit)
        hex_row.addStretch()
        info.addLayout(hex_row)

        # R / G / B channel spinboxes
        rgb_row = QHBoxLayout()
        rgb_row.setSpacing(8)
        r_col, self._spin_r = self._make_channel("R")
        g_col, self._spin_g = self._make_channel("G")
        b_col, self._spin_b = self._make_channel("B")
        for col in (r_col, g_col, b_col):
            rgb_row.addLayout(col)
        rgb_row.addStretch()
        self._spin_r.valueChanged.connect(self._on_rgb_changed)
        self._spin_g.valueChanged.connect(self._on_rgb_changed)
        self._spin_b.valueChanged.connect(self._on_rgb_changed)
        info.addLayout(rgb_row)
        info.addStretch()

        picker_row.addLayout(info)
        root.addLayout(picker_row)

        # ╔══ Separator ═════════════════════════════════════════════════╗
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("colorSep")
        root.addWidget(sep)

        # ╔══ Palette ═══════════════════════════════════════════════════╗
        pal_hdr = QLabel("PALETTE")
        pal_hdr.setObjectName("palHdr")
        root.addWidget(pal_hdr)

        grid = QGridLayout()
        grid.setSpacing(6)
        for i, hx in enumerate(_PRESETS):
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(hx)
            btn.setStyleSheet(
                f"QPushButton{{"
                f"background:{hx};"
                f"border:1px solid rgba(255,255,255,.08);"
                f"border-radius:6px;}}"
                f"QPushButton:hover{{"
                f"border:2px solid rgba(255,255,255,.55);}}"
                f"QPushButton:pressed{{"
                f"border:2px solid rgba(255,255,255,.85);}}"
            )
            btn.clicked.connect(lambda _, c=hx: self._push_color(QColor(c)))
            grid.addWidget(btn, i // _PAL_COLS, i % _PAL_COLS)
        root.addLayout(grid)

        # ╔══ Dialog buttons ════════════════════════════════════════════╗
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("colorCancel")
        cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton("Select")
        self._ok_btn.setObjectName("colorOk")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(6)
        btn_row.addWidget(self._ok_btn)
        root.addLayout(btn_row)

    @staticmethod
    def _make_channel(label: str) -> tuple[QVBoxLayout, QSpinBox]:
        col: QVBoxLayout = QVBoxLayout()
        col.setSpacing(3)
        lbl = QLabel(label)
        lbl.setObjectName("rgbLbl")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin = QSpinBox()
        spin.setRange(0, 255)
        spin.setFixedWidth(54)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        col.addWidget(lbl)
        col.addWidget(spin)
        return col, spin

    # ── Stylesheet ─────────────────────────────────────────────────────

    def _apply_stylesheet(self) -> None:
        # Derive hover / pressed shades from the current accent colour
        accent = QColor(self._initial_hex)
        h, s, v, _ = accent.getHsvF()
        hover  = QColor.fromHsvF(h, s, min(1.0, v + 0.10))
        pressed = QColor.fromHsvF(h, max(0.0, s - 0.05), max(0.0, v - 0.10))
        hover_hex   = "#{:02X}{:02X}{:02X}".format(hover.red(),   hover.green(),   hover.blue())
        pressed_hex = "#{:02X}{:02X}{:02X}".format(pressed.red(), pressed.green(), pressed.blue())

        self.setStyleSheet(f"""
            QDialog {{
                background-color: #1C1C1C;
            }}

            QLabel {{
                color: #C0C0C0;
                font-size: 12px;
                background: transparent;
            }}

            QLabel#colorHash {{
                color: #4A4A4A;
                font-size: 15px;
                font-family: "Consolas", "Courier New", monospace;
            }}

            QLabel#palHdr {{
                color: #484848;
                font-size: 10px;
                letter-spacing: 1.5px;
            }}

            QLabel#rgbLbl {{
                color: #585858;
                font-size: 10px;
                font-weight: 600;
            }}

            QFrame#colorSep {{
                color: #2A2A2A;
                margin: 0px 0px;
            }}

            QLineEdit {{
                background-color: #242424;
                color: #E0E0E0;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 13px;
                font-family: "Consolas", "Courier New", monospace;
                selection-background-color: {self._initial_hex};
            }}
            QLineEdit:focus {{
                border-color: {self._initial_hex};
                background-color: #272727;
            }}

            QSpinBox {{
                background-color: #242424;
                color: #E0E0E0;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 5px 6px;
                font-size: 12px;
                font-family: "Consolas", "Courier New", monospace;
            }}
            QSpinBox:focus {{
                border-color: {self._initial_hex};
                background-color: #272727;
            }}

            QPushButton#colorCancel {{
                background-color: #2A2A2A;
                color: #999999;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 80px;
            }}
            QPushButton#colorCancel:hover {{
                background-color: #323232;
                color: #BBBBBB;
                border-color: #444444;
            }}
            QPushButton#colorCancel:pressed {{
                background-color: #222222;
            }}

            QPushButton#colorOk {{
                background-color: {self._initial_hex};
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 600;
                min-width: 80px;
            }}
            QPushButton#colorOk:hover {{
                background-color: {hover_hex};
            }}
            QPushButton#colorOk:pressed {{
                background-color: {pressed_hex};
            }}
        """)

    # ── Colour synchronisation ─────────────────────────────────────────

    def _push_color(self, color: QColor, *, init: bool = False) -> None:
        """Synchronise every widget to *color* without feedback loops."""
        h, s, v, _ = color.getHsvF()
        # getHsvF() returns h=-1 for achromatic colours; preserve current hue
        if h < 0.0:
            h = self._h
        self._h, self._s, self._v = h, s, v

        # Push to picker widgets (no signals emitted by set_* methods)
        self._canvas.set_hsv(h, s, v)
        self._huebar.set_hue(h)

        # Block text/spin signals to prevent re-entry
        for w in (self._hex_edit, self._spin_r, self._spin_g, self._spin_b):
            w.blockSignals(True)
        self._hex_edit.setText(
            "{:02X}{:02X}{:02X}".format(color.red(), color.green(), color.blue())
        )
        self._spin_r.setValue(color.red())
        self._spin_g.setValue(color.green())
        self._spin_b.setValue(color.blue())
        for w in (self._hex_edit, self._spin_r, self._spin_g, self._spin_b):
            w.blockSignals(False)

        # Update the "after" swatch; update the "before" swatch only on init
        name = color.name().upper()
        self._sw_new.setStyleSheet(
            f"QLabel{{background:{name};"
            f"border:1px solid #353535;"
            f"border-left:none;"
            f"border-radius:0px 7px 7px 0px;}}"
        )
        if init:
            self._sw_old.setStyleSheet(
                f"QLabel{{background:{name};"
                f"border:1px solid #353535;"
                f"border-radius:7px 0px 0px 7px;}}"
            )

    # ── Signal handlers ────────────────────────────────────────────────

    def _on_hue_changed(self, hue: float) -> None:
        self._push_color(QColor.fromHsvF(hue, self._s, self._v))

    def _on_sv_changed(self, sat: float, val: float) -> None:
        self._push_color(QColor.fromHsvF(self._h, sat, val))

    def _on_hex_edited(self, text: str) -> None:
        if len(text) == 6:
            c = QColor(f"#{text}")
            if c.isValid():
                self._push_color(c)

    def _on_rgb_changed(self) -> None:
        self._push_color(
            QColor(self._spin_r.value(), self._spin_g.value(), self._spin_b.value())
        )

    # ── Result ─────────────────────────────────────────────────────────

    def selected_hex(self) -> str:
        """Return the chosen colour as ``#RRGGBB``."""
        c = QColor.fromHsvF(self._h, self._s, self._v)
        return "#{:02X}{:02X}{:02X}".format(c.red(), c.green(), c.blue())
