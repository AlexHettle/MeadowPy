"""Icon loading helpers for MeadowPy resources."""

from pathlib import Path

from meadowpy.resources.resource_paths import DEFAULT_RESOURCES_DIR, get_icon_path

# Hardcoded fills inside the colorful SVG icons (run, debug, restart, stop, ...).
# High contrast mode collapses semantic color onto pure white.
_HC_ICON_COLOR_MAP: dict[str, str] = {
    "#4CAF50": "#FFFFFF",
    "#FF9800": "#FFFFFF",
    "#E65100": "#FFFFFF",
    "#F57C00": "#FFFFFF",
    "#E51400": "#FFFFFF",
    "#A30000": "#FFFFFF",
}


def load_themed_icon(
    name: str,
    theme_name: str = "",
    resources_dir: Path | str = DEFAULT_RESOURCES_DIR,
):
    """Return a QIcon for *name*, color-mapped if the current theme requires it."""
    from PyQt6.QtGui import QIcon

    path = get_icon_path(name, resources_dir)
    if not path:
        return QIcon()

    if theme_name != "default_high_contrast" or not path.endswith(".svg"):
        return QIcon(path)

    try:
        from PyQt6.QtCore import QByteArray, QSize, Qt
        from PyQt6.QtGui import QPainter, QPixmap
        from PyQt6.QtSvg import QSvgRenderer

        svg_text = Path(path).read_text(encoding="utf-8")
        for old, new in _HC_ICON_COLOR_MAP.items():
            svg_text = svg_text.replace(old, new)
            svg_text = svg_text.replace(old.lower(), new)
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))

        size = 48
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return QIcon(path)


def load_tinted_icon(
    name: str,
    color: str,
    size: int = 16,
    resources_dir: Path | str = DEFAULT_RESOURCES_DIR,
):
    """Render a ``{{COLOR}}``-templated SVG into a QIcon at the given color."""
    from PyQt6.QtCore import QByteArray, QSize, Qt
    from PyQt6.QtGui import QIcon, QPainter, QPixmap
    from PyQt6.QtSvg import QSvgRenderer

    svg_path = Path(resources_dir) / "icons" / f"{name}.svg"
    if not svg_path.exists():
        return QIcon()

    svg_data = svg_path.read_text(encoding="utf-8").replace("{{COLOR}}", color)
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))

    render_size = size * 2
    pixmap = QPixmap(QSize(render_size, render_size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2.0)

    icon = QIcon()
    for mode in (
        QIcon.Mode.Normal,
        QIcon.Mode.Active,
        QIcon.Mode.Selected,
        QIcon.Mode.Disabled,
    ):
        for state in (QIcon.State.On, QIcon.State.Off):
            icon.addPixmap(pixmap, mode, state)
    return icon
