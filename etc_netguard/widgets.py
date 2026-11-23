# -*- coding: utf-8 -*-
"""Reusable pieces: animated switch, nav rail, toasts, cards, wizard artwork."""
from __future__ import annotations

import math

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .theme import ACCENT, ACCENT_2, BORDER, CARD, DANGER, MUTED, TEXT, TEXT_DIM, WARNING




def stop_animation(anim):
    """Stop a QAbstractAnimation that may already have been C++-deleted.

    PyQt wraps animations started with DeleteWhenStopped; keeping the Python
    wrapper around and calling stop() later raises "wrapped C/C++ object has
    been deleted".  That exception inside a Qt slot aborts the process.
    """
    if anim is None:
        return
    try:
        anim.stop()
    except (RuntimeError, TypeError):
        pass

def _mix(c1: str, c2: str, t: float) -> QColor:
    a, b = QColor(c1), QColor(c2)
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )


def label(text: str, obj: str = "", size: int | None = None, color: str | None = None,
          bold: bool = False) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    if size:
        f = lb.font()
        f.setPixelSize(size)
        lb.setFont(f)
    if color:
        lb.setStyleSheet(f"color:{color};")
    if bold:
        f = lb.font()
        f.setWeight(QFont.Bold)
        lb.setFont(f)
    return lb


def hline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet("background: rgba(255,255,255,10); border:none;")
    return line


class Page(QWidget):
    """A page whose body fades + lifts in whenever it becomes visible."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim: QPropertyAnimation | None = None
        self._fx: QGraphicsOpacityEffect | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.body = QWidget(self)
        self.body.setAttribute(Qt.WA_StyledBackground, False)
        outer.addWidget(self.body)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(30, 22, 30, 22)
        self.body_layout.setSpacing(16)
        # One permanent opacity effect per page.  Old code cleared the effect
        # with setGraphicsEffect(None), which deletes the C++ object while the
        # animation can still reference it -> crash on repeated page switches.
        self._fx = QGraphicsOpacityEffect(self.body)
        self._fx.setOpacity(1.0)
        self._fx.setEnabled(False)
        self.body.setGraphicsEffect(self._fx)
        self._anim = None
        self._move_anim = None

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.animate_in()

    def animate_in(self):
        stop_animation(self._anim)
        stop_animation(self._move_anim)
        self._fx.setEnabled(True)
        self._fx.setOpacity(0.0)
        anim = QPropertyAnimation(self._fx, b"opacity", self)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(
            lambda a=anim: self._fx.setEnabled(False) if self._anim is a else None
        )
        self._anim = anim
        start = self.body.pos()
        move = QPropertyAnimation(self.body, b"pos", self)
        move.setDuration(280)
        move.setStartValue(QPoint(start.x(), start.y() + 12))
        move.setEndValue(start)
        move.setEasingCurve(QEasingCurve.OutCubic)
        self._move_anim = move
        move.start(QPropertyAnimation.DeleteWhenStopped)
        anim.start(QPropertyAnimation.DeleteWhenStopped)


class NavItem(QWidget):
    clicked = pyqtSignal()

    def __init__(self, text: str, icon_name: str, parent=None):
        super().__init__(parent)
        self.text = text
        self.icon_name = icon_name
        self._active = False
        self._hover = 0.0
        self._act = 0.0
        self.setFixedHeight(46)
        self.setMinimumWidth(196)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(180)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)
        self._active_anim = QVariantAnimation(self)
        self._active_anim.setDuration(240)
        self._active_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._active_anim.valueChanged.connect(self._on_act)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def _on_act(self, v):
        self._act = float(v)
        self.update()

    def set_active(self, active: bool):
        if self._active == active:
            return
        self._active = active
        self._active_anim.stop()
        self._active_anim.setStartValue(self._act)
        self._active_anim.setEndValue(1.0 if active else 0.0)
        self._active_anim.start()

    def enterEvent(self, event):  # noqa: N802
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing)
        r = QRectF(2, 3, self.width() - 4, self.height() - 6)

        bg_alpha = int(8 * self._hover) + int(18 * self._act)
        if bg_alpha:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(53, 227, 195, bg_alpha) if self._act > 0 else QColor(255, 255, 255, bg_alpha))
            p.drawRoundedRect(r, 11, 11)
        if self._act > 0.01:
            p.setBrush(QColor(53, 227, 195, 60))
            p.drawRoundedRect(r, 11, 11)
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(QRectF(0, 12, 3, self.height() - 24), 1.5, 1.5)

        color = _mix(MUTED, ACCENT, self._act)
        pm = icons.colored_svg(self.icon_name, color.name(), 20)
        p.drawPixmap(QPoint(17, (self.height() - 20) // 2), pm)
        p.setPen(QColor(235, 246, 243) if self._act > 0.4 else QColor(TEXT_DIM))
        f = QFont()
        f.setPixelSize(14)
        f.setWeight(QFont.DemiBold if self._act > 0.4 else QFont.Normal)
        p.setFont(f)
        p.drawText(QRectF(48, 0, self.width() - 56, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text)
        p.end()


class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, checked: bool = False, accent: str = ACCENT):
        super().__init__(parent)
        self._checked = checked
        self._pos = 1.0 if checked else 0.0
        self._enabled = True
        self.accent = QColor(accent)
        self.setFixedSize(50, 28)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(210)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, v):
        self._pos = float(v)
        self.update()

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True):  # noqa: N802
        if self._checked == checked:
            return
        self._checked = checked
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        if animate:
            self._anim.start()
        else:
            self._pos = 1.0 if checked else 0.0
            self.update()

    def setEnabled(self, enabled: bool):  # noqa: N802
        self._enabled = enabled
        super().setEnabled(enabled)
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self._enabled:
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing)
        r = QRectF(1, 2, self.width() - 2, self.height() - 4)
        off = QColor(38, 51, 64)
        if not self._enabled:
            off = QColor(30, 39, 48)
        track = QColor(
            int(off.red() + (self.accent.red() - off.red()) * self._pos),
            int(off.green() + (self.accent.green() - off.green()) * self._pos),
            int(off.blue() + (self.accent.blue() - off.blue()) * self._pos),
            255,
        )
        p.setPen(QPen(QColor(255, 255, 255, 26 if self._pos < 0.5 else 0), 1))
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        if self._pos > 0.2:
            glow = QColor(self.accent.red(), self.accent.green(), self.accent.blue(), int(38 * self._pos))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), r.height() / 2 + 2, r.height() / 2 + 2)
            p.setBrush(track)
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        knob_d = 22
        x = 3 + self._pos * (self.width() - knob_d - 6)
        kr = QRectF(x, (self.height() - knob_d) / 2, knob_d, knob_d)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(kr.translated(0, 2))
        p.setBrush(QColor(248, 252, 251) if self._enabled else QColor(150, 160, 168))
        p.drawEllipse(kr)
        p.end()


class Toast(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._kind = "ok"
        self._text = ""
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._anim: QPropertyAnimation | None = None
        self._pos_anim: QPropertyAnimation | None = None

    def show_message(self, text: str, kind: str = "ok", msec: int = 3200):
        self._kind = kind
        self._text = text
        self._timer.stop()
        stop_animation(self._anim)
        self.setFixedHeight(48)
        fm = QFontMetrics(self.font())
        self.setFixedWidth(min(max(240, fm.horizontalAdvance(text) + 76), 620))
        self._layout_to_parent(offset=22)
        self.show()
        self.raise_()
        self._fx.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._timer.start(msec)

    def _target_pos(self, offset: int = 0) -> QPoint:
        parent = self.parentWidget()
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 24 + offset
        return QPoint(x, y)

    def _layout_to_parent(self, offset: int = 0):
        self.move(self._target_pos(offset))

    def _fade_out(self):
        stop_animation(self._anim)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setStartValue(self._fx.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start(QPropertyAnimation.DeleteWhenStopped)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.setBrush(QColor(16, 28, 38, 245))
        p.drawRoundedRect(r, 12, 12)
        accent = {"ok": ACCENT, "warn": WARNING, "error": DANGER, "info": ACCENT_2}.get(self._kind, ACCENT)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(accent))
        p.drawRoundedRect(QRectF(0, 14, 3, self.height() - 28), 1.5, 1.5)
        icon = {"ok": "circle-check", "warn": "triangle-alert", "error": "ban", "info": "sparkles"}.get(self._kind, "check")
        if icon == "circle-check" and not (icons.asset_dir() / "icons" / "circle-check.svg").exists():
            icon = "check"
        pm = icons.colored_svg(icon, accent, 20)
        p.drawPixmap(QPoint(16, (self.height() - 20) // 2), pm)
        p.setPen(QColor("#EAF4F2"))
        f = QFont()
        f.setPixelSize(13)
        p.setFont(f)
        p.drawText(QRectF(44, 0, self.width() - 56, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self._text)
        p.end()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._layout_to_parent()


class StatCard(QFrame):
    def __init__(self, caption: str, icon_name: str, accent: str = ACCENT, parent=None):
        super().__init__(parent)
        self.setObjectName("CardSoft")
        self.setFixedHeight(76)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 16, 12)
        lay.setSpacing(12)
        self.badge = QLabel()
        self.badge.setFixedSize(38, 38)
        self.badge.setPixmap(icons.colored_svg(icon_name, accent, 19))
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet(
            f"background: rgba({QColor(accent).red()},{QColor(accent).green()},{QColor(accent).blue()},20);"
            f"border: 1px solid rgba({QColor(accent).red()},{QColor(accent).green()},{QColor(accent).blue()},42);"
            "border-radius: 11px;"
        )
        lay.addWidget(self.badge)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.value = QLabel("0")
        f = self.value.font()
        f.setPixelSize(21)
        f.setWeight(QFont.Bold)
        self.value.setFont(f)
        self.caption = label(caption, "Tiny")
        col.addWidget(self.value)
        col.addWidget(self.caption)
        lay.addLayout(col, 1)

    def set_value(self, value: str):
        self.value.setText(str(value))


class Chip(QWidget):
    closed = pyqtSignal(object)

    def __init__(self, text: str, data=None, parent=None):
        super().__init__(parent)
        self.text = text
        self.data = data
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False
        fm = QFontMetrics(self.font())
        self.setFixedWidth(min(fm.horizontalAdvance(text) + 34, 220))

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.closed.emit(self.data)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(53, 227, 195, 70 if self._hover else 38), 1))
        p.setBrush(QColor(53, 227, 195, 28 if self._hover else 16))
        p.drawRoundedRect(r, 9, 9)
        p.setPen(QColor(ACCENT if self._hover else "#BFEFE6"))
        f = QFont()
        f.setPixelSize(12)
        p.setFont(f)
        p.drawText(r.adjusted(11, 0, -22, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text)
        p.setPen(QPen(QColor(53, 227, 195, 190), 1.6))
        cx, cy = self.width() - 12, self.height() / 2
        p.drawLine(QPointF(cx - 3, cy - 3), QPointF(cx + 3, cy + 3))
        p.drawLine(QPointF(cx + 3, cy - 3), QPointF(cx - 3, cy + 3))
        p.end()


class EmptyState(QWidget):
    def __init__(self, icon_name: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)
        art = QLabel()
        art.setPixmap(icons.colored_svg(icon_name, ACCENT, 46))
        art.setAlignment(Qt.AlignCenter)
        lay.addWidget(art)
        t = label(title, "H3")
        t.setAlignment(Qt.AlignCenter)
        s = label(subtitle, "Muted")
        s.setAlignment(Qt.AlignCenter)
        s.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(s)
        lay.setContentsMargins(20, 24, 20, 28)


class WizardArt(QWidget):
    """Animated, hand-drawn scenes for the seven onboarding steps."""

    def __init__(self, step: int, parent=None):
        super().__init__(parent)
        self.step = step
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(70)
        self.setMinimumSize(330, 360)

    def _tick(self):
        self.phase = (self.phase + 0.045) % 1.0
        self.update()

    def hideEvent(self, event):  # noqa: N802
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):  # noqa: N802
        self.timer.start(55)
        super().showEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        w, h = self.width(), self.height()
        # backdrop
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor("#0C2A2B"))
        grad.setColorAt(0.55, QColor("#0A1B26"))
        grad.setColorAt(1, QColor("#08131B"))
        p.setBrush(grad)
        p.setPen(QPen(QColor(53, 227, 195, 30), 1))
        p.drawRoundedRect(QRectF(0, 0, w, h), 18, 18)

        # moving aurora
        for i, col in enumerate((QColor(53, 227, 195, 42), QColor(78, 155, 255, 34))):
            cx = w * (0.25 + 0.5 * i) + math.sin(self.phase * 2 * math.pi + i) * 28
            cy = h * (0.3 + 0.18 * i) + math.cos(self.phase * 2 * math.pi + i) * 18
            rg = QRadialGradient(QPointF(cx, cy), w * 0.55)
            rg.setColorAt(0, col)
            rg.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
            p.setBrush(rg)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), w * 0.55, w * 0.55)

        # grid dots
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        for x in range(24, w, 32):
            for y in range(24, h, 32):
                p.drawPoint(x, y)

        cx, cy = w / 2, h / 2 - 10
        p.setPen(Qt.NoPen)
        # halo
        glow = QRadialGradient(QPointF(cx, cy), 118)
        glow.setColorAt(0, QColor(53, 227, 195, int(55 + 18 * math.sin(self.phase * 2 * math.pi))))
        glow.setColorAt(1, QColor(53, 227, 195, 0))
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), 125, 125)

        # orbit rings
        p.setPen(QPen(QColor(53, 227, 195, 55), 1))
        p.drawEllipse(QPointF(cx, cy), 92, 92)
        p.setPen(QPen(QColor(78, 155, 255, 40), 1))
        p.drawEllipse(QPointF(cx, cy), 108, 108)
        for i in range(3):
            a = self.phase * 2 * math.pi + i * 2.1
            px = cx + math.cos(a) * 108
            py = cy + math.sin(a) * 108
            p.setBrush(QColor(53, 227, 195, 130))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(px, py), 2.2, 2.2)

        draw = getattr(self, f"_draw_{min(self.step, 7)}", None)
        if draw:
            draw(p, cx, cy, w, h)

        # bottom signature
        p.setPen(QColor(255, 255, 255, 40))
        f = QFont()
        f.setPixelSize(10)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        p.setFont(f)
        p.drawText(QRectF(22, h - 30, w - 44, 20), Qt.AlignLeft | Qt.AlignVCenter, "E T C   N E T G U A R D")
        p.end()

    # --- scenes -----------------------------------------------------------
    @staticmethod
    def _shield(p: QPainter, cx: float, cy: float, s: float, color1="#54F5D9", color2="#3C8DFF"):
        path = QPainterPath()
        path.moveTo(cx, cy - s * 0.52)
        path.lineTo(cx + s * 0.46, cy - s * 0.26)
        path.lineTo(cx + s * 0.39, cy + s * 0.18)
        path.cubicTo(cx + s * 0.28, cy + s * 0.42, cx + s * 0.12, cy + s * 0.49, cx, cy + s * 0.56)
        path.cubicTo(cx - s * 0.12, cy + s * 0.49, cx - s * 0.28, cy + s * 0.42, cx - s * 0.39, cy + s * 0.18)
        path.lineTo(cx - s * 0.46, cy - s * 0.26)
        path.closeSubpath()
        g = QLinearGradient(cx - s, cy - s, cx + s, cy + s)
        g.setColorAt(0, QColor(color1))
        g.setColorAt(1, QColor(color2))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawPath(path)
        return path

    def _draw_1(self, p, cx, cy, w, h):
        self._shield(p, cx, cy - 4, 108)
        p.setPen(QPen(QColor(4, 28, 24, 220), 3))
        p.drawArc(QRectF(cx - 30, cy - 26, 60, 52), 200 * 16, 140 * 16)
        p.setBrush(QColor(4, 28, 24, 220))
        p.drawEllipse(QPointF(cx, cy + 4), 3.2, 3.2)
        p.drawLine(QPointF(cx, cy + 4), QPointF(cx + 18, cy - 13))
        # sparkles
        for i in range(6):
            a = self.phase * 2 * math.pi + i * 1.05
            r = 75 + 14 * math.sin(self.phase * 4 * math.pi + i)
            px, py = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.9
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(180, 255, 238, 110))
            p.drawEllipse(QPointF(px, py), 1.8, 1.8)

    def _draw_2(self, p, cx, cy, w, h):
        self._shield(p, cx - 14, cy, 104)
        # lock
        p.setBrush(QColor(6, 24, 30, 235))
        p.setPen(QPen(QColor(150, 255, 235, 160), 1.4))
        body = QRectF(cx + 28, cy + 4, 46, 38)
        p.drawRoundedRect(body, 8, 8)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(150, 255, 235, 200), 3))
        p.drawArc(QRectF(cx + 38, cy - 16, 26, 30), 0, 180 * 16)
        p.setPen(QPen(QColor(53, 227, 195, 210), 2))
        p.drawLine(QPointF(cx + 51, cy + 18), QPointF(cx + 51, cy + 28))

    def _draw_3(self, p, cx, cy, w, h):
        p.setPen(QPen(QColor(53, 227, 195, 80), 1))
        for r in (36, 62, 88):
            p.drawEllipse(QPointF(cx, cy), r, r)
        p.drawLine(QPointF(cx - 96, cy), QPointF(cx + 96, cy))
        p.drawLine(QPointF(cx, cy - 96), QPointF(cx, cy + 96))
        p.setBrush(QColor(53, 227, 195, 60))
        p.setPen(QPen(QColor(53, 227, 195, 110), 1))
        p.drawEllipse(QPointF(cx, cy), 22, 22)
        p.setBrush(QColor(53, 227, 195, 220))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 4, 4)
        # sweep
        angle = self.phase * 2 * math.pi
        p.setPen(QPen(QColor(53, 227, 195, 90), 2))
        p.drawLine(QPointF(cx, cy), QPointF(cx + math.cos(angle) * 88, cy + math.sin(angle) * 88))
        for i in range(5):
            a = angle - i * 0.12
            p.setPen(QPen(QColor(53, 227, 195, 70 - i * 13), 1.4))
            p.drawLine(QPointF(cx, cy), QPointF(cx + math.cos(a) * 88, cy + math.sin(a) * 88))
        # process dots
        for px, py, ph in ((cx - 56, cy - 30, 0.3), (cx + 62, cy + 26, 0.7), (cx + 30, cy - 64, 0.5), (cx - 34, cy + 60, 0.1)):
            p.setBrush(QColor(78, 155, 255, 180))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(px, py), 3, 3)

    def _draw_4(self, p, cx, cy, w, h):
        rows = 4
        top = cy - 84
        for i in range(rows):
            y = top + i * 44
            rect = QRectF(cx - 92, y, 184, 34)
            p.setPen(QPen(QColor(255, 255, 255, 30), 1))
            p.setBrush(QColor(255, 255, 255, 100 if i == 1 else 45))
            p.setBrush(QColor(10, 24, 32, 220))
            p.drawRoundedRect(rect, 9, 9)
            p.setBrush(QColor(53, 227, 195, 40 + (i == 1) * 30))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(rect.x() + 10, y + 8, 18, 18), 5, 5)
            if i == 1:
                p.setPen(QPen(QColor(53, 227, 195, 240), 2))
                path = QPainterPath()
                path.moveTo(rect.x() + 14, y + 17)
                path.lineTo(rect.x() + 18, y + 21)
                path.lineTo(rect.x() + 25, y + 13)
                p.drawPath(path)
            p.setPen(QColor(220, 240, 238, 150 if i != 1 else 235))
            f = QFont()
            f.setPixelSize(10)
            p.setFont(f)
            p.drawText(QRectF(rect.x() + 40, y, 120, 34), Qt.AlignVCenter, ["chrome.exe", "game.exe", "cloud.exe", "update.exe"][i])
        # cursor
        p.setBrush(QColor(255, 255, 255, 220))
        p.setPen(Qt.NoPen)
        cur = QPointF(cx + 52, top + 44 + 14)
        path = QPainterPath()
        path.moveTo(cur)
        path.lineTo(cur + QPointF(0, 16))
        path.lineTo(cur + QPointF(4, 12))
        path.lineTo(cur + QPointF(9, 12))
        path.closeSubpath()
        p.drawPath(path)

    def _draw_5(self, p, cx, cy, w, h):
        p.setPen(QPen(QColor(255, 255, 255, 35), 1))
        p.setBrush(QColor(8, 22, 28, 210))
        p.drawRoundedRect(QRectF(cx - 104, cy - 58, 208, 132), 18, 18)
        p.setPen(QPen(QColor(53, 227, 195, 120), 2))
        arc = QRectF(cx - 58, cy - 38, 116, 96)
        p.drawArc(arc, 205 * 16, 130 * 16)
        for i in range(11):
            a = math.radians(205 + i * 13)
            inner = QPointF(cx + math.cos(a) * 50, cy + math.sin(a) * 50 + 10)
            outer = QPointF(cx + math.cos(a) * (58 if i % 5 else 62), cy + math.sin(a) * (58 if i % 5 else 62) + 10)
            p.setPen(QPen(QColor(53, 227, 195, 100), 1))
            p.drawLine(inner, outer)
        needle_angle = math.radians(205 + 65 + math.sin(self.phase * 2 * math.pi) * 28)
        p.setPen(QPen(QColor(53, 227, 195, 240), 3))
        p.drawLine(QPointF(cx, cy + 10), QPointF(cx + math.cos(needle_angle) * 44, cy + 10 + math.sin(needle_angle) * 44))
        p.setBrush(QColor(53, 227, 195, 240))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy + 10), 4, 4)
        f = QFont()
        f.setPixelSize(16)
        f.setWeight(QFont.Bold)
        p.setFont(f)
        p.setPen(QColor(225, 255, 250))
        p.drawText(QRectF(cx - 60, cy + 30, 120, 28), Qt.AlignCenter, "120 KB/s")

    def _draw_6(self, p, cx, cy, w, h):
        # globe
        p.setPen(QPen(QColor(78, 155, 255, 170), 1.6))
        p.setBrush(QColor(12, 30, 44, 230))
        p.drawEllipse(QPointF(cx, cy), 66, 66)
        p.setPen(QPen(QColor(53, 227, 195, 80), 1))
        p.drawEllipse(QPointF(cx, cy), 66, 30)
        p.drawEllipse(QPointF(cx, cy), 30, 66)
        p.drawLine(QPointF(cx - 66, cy), QPointF(cx + 66, cy))
        # slash
        p.setPen(QPen(QColor(255, 111, 125, 240), 4))
        p.drawLine(QPointF(cx - 48, cy - 48), QPointF(cx + 48, cy + 48))
        # 404 card
        p.setBrush(QColor(16, 28, 38, 240))
        p.setPen(QPen(QColor(255, 111, 125, 70), 1))
        p.drawRoundedRect(QRectF(cx + 32, cy + 22, 86, 34), 8, 8)
        f = QFont()
        f.setPixelSize(19)
        f.setWeight(QFont.Bold)
        p.setFont(f)
        p.setPen(QColor(255, 150, 160))
        p.drawText(QRectF(cx + 32, cy + 22, 86, 34), Qt.AlignCenter, "404")

    def _draw_7(self, p, cx, cy, w, h):
        p.setBrush(QColor(53, 227, 195, 230))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 46, 46)
        p.setPen(QPen(QColor(4, 34, 27), 5))
        path = QPainterPath()
        path.moveTo(cx - 18, cy + 1)
        path.lineTo(cx - 4, cy + 16)
        path.lineTo(cx + 22, cy - 14)
        p.drawPath(path)
        for i in range(12):
            a = self.phase * 2 * math.pi * 1.2 + i * 0.55
            r = 55 + 18 * math.sin(self.phase * 4 * math.pi + i)
            px, py = cx + math.cos(a) * r, cy + math.sin(a) * r
            col = QColor(53, 227, 195, 140) if i % 2 else QColor(78, 155, 255, 120)
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawEllipse(QPointF(px, py), 2.2, 2.2)


class FlowLayout(QLayout):
    """A small wrapping layout used for the selected-process chips."""

    def __init__(self, parent=None, margin=0, hspacing=8, vspacing=8):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._h = hspacing
        self._v = vspacing
        self._items = []

    def addItem(self, item):  # noqa: N802
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = effective.x(), effective.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h
            if next_x - self._h > effective.right() and line_h > 0:
                x = effective.x()
                y = y + line_h + self._v
                next_x = x + hint.width() + self._h
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()


class ProcessTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["进程", "PID", "状态", "可执行路径"])
        self.setShowGrid(False)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(52)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setSectionResizeMode(0, self.horizontalHeader().Fixed)
        self.horizontalHeader().setSectionResizeMode(1, self.horizontalHeader().Fixed)
        self.horizontalHeader().setSectionResizeMode(2, self.horizontalHeader().Fixed)
        self.horizontalHeader().setSectionResizeMode(3, self.horizontalHeader().Stretch)
        self.setColumnWidth(0, 280)
        self.setColumnWidth(1, 84)
        self.setColumnWidth(2, 112)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setIconSize(QSize(22, 22))
