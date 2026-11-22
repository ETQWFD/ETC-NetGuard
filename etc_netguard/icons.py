# -*- coding: utf-8 -*-
"""Vector icons, generated avatars and the ETC app mark."""
from __future__ import annotations

import hashlib

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt5.QtSvg import QSvgRenderer

from .theme import ACCENT, ACCENT_2, asset_dir

_svg_cache: dict = {}
_letter_cache: dict = {}
_app_icon: QIcon | None = None


def colored_svg(name: str, color: str, size: int = 18, stroke_scale: float = 1.0) -> QPixmap:
    key = (name, color, size, stroke_scale)
    if key in _svg_cache:
        return _svg_cache[key]
    path = asset_dir() / "icons" / f"{name}.svg"
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    if path.exists():
        p = QPainter(pm)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        QSvgRenderer(str(path)).render(p)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(pm.rect(), QColor(color))
        p.end()
    pm.setDevicePixelRatio(2)
    _svg_cache[key] = pm
    return pm


def svg_icon(name: str, color: str, size: int = 18) -> QIcon:
    return QIcon(colored_svg(name, color, size))


def letter_pixmap(text: str, size: int = 28) -> QPixmap:
    """A soft gradient tile with the first character, used for app/site avatars."""
    seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:6], 16)
    key = (text, size, seed)
    if key in _letter_cache:
        return _letter_cache[key]
    palette = [
        ("#35E3C3", "#1C8FA6"),
        ("#7AA7FF", "#3E5EDB"),
        ("#FFB86B", "#D96C4A"),
        ("#C79BFF", "#6C4BD9"),
        ("#6BE3A3", "#238F68"),
        ("#FF8FA3", "#B84B71"),
        ("#63D8FF", "#2B72C9"),
    ]
    c1, c2 = palette[seed % len(palette)]
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    rect = QRectF(2, 2, size * 2 - 4, size * 2 - 4)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, QColor(c1))
    grad.setColorAt(1, QColor(c2))
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(rect, size * 0.32, size * 0.32)
    p.setPen(QColor(255, 255, 255, 235))
    f = QFont()
    f.setPixelSize(int(size * 1.22))
    f.setWeight(QFont.Bold)
    p.setFont(f)
    ch = (text.strip()[:1] or "?").upper()
    p.drawText(rect, Qt.AlignCenter, ch)
    p.end()
    pm.setDevicePixelRatio(2)
    _letter_cache[key] = pm
    return pm


def app_pixmap(size: int = 256) -> QPixmap:
    # The shipped app.png is the user-selected 404 / no-network mark.
    png = asset_dir() / "app.png"
    if png.exists():
        raw = QPixmap(str(png))
        if not raw.isNull():
            return raw.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    r = QRectF(8, 8, size - 16, size - 16)
    grad = QLinearGradient(r.topLeft(), r.bottomRight())
    grad.setColorAt(0, QColor("#102C2D"))
    grad.setColorAt(0.55, QColor("#0A1B22"))
    grad.setColorAt(1, QColor("#08121A"))
    p.setBrush(grad)
    p.setPen(QPen(QColor(53, 227, 195, 120), size * 0.012))
    p.drawRoundedRect(r, size * 0.2, size * 0.2)

    # inner glow
    rg = QRadialGradient(QPointF(size * 0.28, size * 0.2), size * 0.55)
    rg.setColorAt(0, QColor(53, 227, 195, 55))
    rg.setColorAt(1, QColor(53, 227, 195, 0))
    p.setBrush(rg)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(r.adjusted(1, 1, -1, -1), size * 0.19, size * 0.19)

    # shield
    cx, cy = size / 2, size / 2 - size * 0.02
    w, h = size * 0.42, size * 0.5
    path = QPainterPath()
    path.moveTo(cx, cy - h / 2)
    path.lineTo(cx + w / 2, cy - h * 0.28)
    path.lineTo(cx + w * 0.42, cy + h * 0.2)
    path.cubicTo(cx + w * 0.3, cy + h * 0.43, cx + w * 0.12, cy + h * 0.5, cx, cy + h * 0.56)
    path.cubicTo(cx - w * 0.12, cy + h * 0.5, cx - w * 0.3, cy + h * 0.43, cx - w * 0.42, cy + h * 0.2)
    path.lineTo(cx - w / 2, cy - h * 0.28)
    path.closeSubpath()

    shield_grad = QLinearGradient(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    shield_grad.setColorAt(0, QColor("#54F5D9"))
    shield_grad.setColorAt(1, QColor("#3C8DFF"))
    p.setBrush(shield_grad)
    p.setPen(Qt.NoPen)
    p.drawPath(path)

    # speed arc inside the shield
    p.setPen(QPen(QColor("#062019"), size * 0.02))
    arc_rect = QRectF(cx - w * 0.26, cy - h * 0.14, w * 0.52, h * 0.44)
    p.drawArc(arc_rect, 200 * 16, 140 * 16)
    p.setBrush(QColor("#062019"))
    p.drawEllipse(QPointF(cx, cy + h * 0.08), size * 0.028, size * 0.028)
    p.setPen(QPen(QColor("#062019"), size * 0.018))
    p.drawLine(QPointF(cx, cy + h * 0.08), QPointF(cx + w * 0.15, cy - h * 0.05))
    p.end()
    return pm


def app_icon() -> QIcon:
    global _app_icon
    if _app_icon is None:
        icon = QIcon()
        for s in (16, 24, 32, 48, 64, 128, 256):
            icon.addPixmap(app_pixmap(s))
        _app_icon = icon
    return _app_icon


def ensure_assets() -> None:
    """Generate QSS check marks + app png/ico if missing (also at first run)."""
    d = asset_dir()
    d.mkdir(parents=True, exist_ok=True)
    check = d / "check.png"
    if not check.exists():
        pm = QPixmap(28, 28)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHints(QPainter.Antialiasing)
        pen = QPen(QColor("#04211B"), 5)
        p.setPen(pen)
        path = QPainterPath()
        path.moveTo(6, 15)
        path.lineTo(11.5, 21)
        path.lineTo(23, 8)
        p.drawPath(path)
        p.end()
        pm.save(str(check))
    app_png = d / "app.png"
    if not app_png.exists():
        app_pixmap(256).save(str(app_png))
    ico = d / "app.ico"
    if not ico.exists():
        try:
            from PIL import Image  # type: ignore

            img = Image.open(str(app_png))
            img.save(str(ico), sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        except Exception:
            # Pillow is only needed at build time; the bundled ico already exists in release builds.
            pass
