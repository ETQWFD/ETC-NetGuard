# -*- coding: utf-8 -*-
"""Frameless, animated dialogs: about-author, add-site, confirm."""
from __future__ import annotations

from PyQt5.QtCore import QPoint, QPropertyAnimation, QRect, QRectF, Qt, QUrl
from PyQt5.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
)
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import backend, icons
from .theme import ACCENT, ACCENT_2, MUTED, TEXT
from .widgets import label


class DialogShell(QDialog):
    def __init__(self, parent=None, width=460, height=440):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedSize(width + 44, height + 44)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 22, 22, 22)
        self.panel = QFrame(self)
        self.panel.setObjectName("DialogPanel")
        self.panel.setFixedSize(width, height)
        outer.addWidget(self.panel)
        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(46)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 190))
        self.panel.setGraphicsEffect(shadow)
        self.content = QVBoxLayout(self.panel)
        self.content.setContentsMargins(28, 22, 28, 24)
        self.content.setSpacing(12)
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)

    def showEvent(self, event):  # noqa: N802
        parent = self.parentWidget()
        if parent:
            center = parent.mapToGlobal(parent.rect().center())
            self.move(center - QPoint(self.width() // 2, self.height() // 2 + 10))
        else:
            self.move(QPoint(240, 140))
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start(QPropertyAnimation.DeleteWhenStopped)
        super().showEvent(event)

    def add_close_button(self, row: QHBoxLayout):
        btn = QPushButton()
        btn.setObjectName("Icon")
        btn.setFixedSize(34, 34)
        btn.setIcon(icons.svg_icon("x", MUTED, 16))
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.reject)
        row.addWidget(btn)
        return btn


class AvatarCircle(QWidget):
    def __init__(self, text: str = "etc", size: int = 88, parent=None):
        super().__init__(parent)
        self.text = text
        self.setFixedSize(size, size)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        r = QRectF(3, 3, self.width() - 6, self.height() - 6)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor("#58F6DB"))
        g.setColorAt(1, QColor("#3E7BFF"))
        p.setPen(QPen(QColor(255, 255, 255, 35), 1))
        p.setBrush(g)
        p.drawEllipse(r)
        p.setPen(QPen(QColor(5, 32, 27, 220), 2))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(r.x() + 18, r.y() + 15, r.width() - 36, r.height() - 32), 200 * 16, 140 * 16)
        p.setBrush(QColor(5, 32, 27, 220))
        p.setPen(Qt.NoPen)
        p.drawEllipse(r.center() + QPoint(0, 8), 2.6, 2.6)
        p.drawLine(r.center() + QPoint(0, 8), r.center() + QPoint(12, -5))
        p.setPen(QColor("#04211B"))
        f = QFont()
        f.setPixelSize(17)
        f.setWeight(QFont.Black)
        p.setFont(f)
        p.drawText(QRectF(0, self.height() - 30, self.width(), 22), Qt.AlignCenter, "ETC NETGUARD")
        p.end()


class AboutAuthorDialog(DialogShell):
    def __init__(self, parent=None):
        super().__init__(parent, 470, 506)
        head = QHBoxLayout()
        head.addStretch(1)
        self.add_close_button(head)
        self.content.addLayout(head)

        top = QVBoxLayout()
        top.setSpacing(10)
        top.setAlignment(Qt.AlignHCenter)
        av = QLabel()
        av.setPixmap(icons.app_pixmap(92))
        av.setFixedSize(92, 92)
        top.addWidget(av, 0, Qt.AlignHCenter)
        name = label("etc", "PageTitle")
        name.setAlignment(Qt.AlignCenter)
        top.addWidget(name)
        role = label("ETC NetGuard 作者 · 独立开发者 · 家长控制工具", "Muted")
        role.setAlignment(Qt.AlignCenter)
        top.addWidget(role)
        self.content.addLayout(top)

        quote = label(
            "把网络、应用与网站管理做成一个可控的工具：\n"
            "按进程限速、彻底断网、网站 404，以及密码守护。\n"
            "规则透明、可撤销、可卸载，不碰系统抗恢复机制。",
            "Muted",
        )
        quote.setAlignment(Qt.AlignCenter)
        quote.setWordWrap(True)
        quote.setStyleSheet("line-height:160%;")
        self.content.addWidget(quote)

        gh = QPushButton("   在 GitHub 查看开源仓库")
        gh.setObjectName("Ghost")
        gh.setCursor(Qt.PointingHandCursor)
        gh.setFixedHeight(48)
        gh.setIcon(icons.svg_icon("github", TEXT, 19))
        gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(backend.REPO_URL)))
        self.content.addWidget(gh)

        url = label(backend.REPO_URL.replace("https://", ""), "Tiny")
        url.setAlignment(Qt.AlignCenter)
        self.content.addWidget(url)

        tip = label("开源仓库内含完整源码、构建脚本与说明，欢迎 Star。", "Tiny")
        tip.setAlignment(Qt.AlignCenter)
        tip.setWordWrap(True)
        self.content.addWidget(tip)
        self.content.addStretch(1)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(255,255,255,10);")
        self.content.addWidget(line)
        foot = QHBoxLayout()
        foot.addWidget(label(f"v{backend.APP_VERSION} · 桌面版", "Tiny"))
        foot.addStretch(1)
        foot.addWidget(label("by etc · 2026", "Tiny"))
        self.content.addLayout(foot)


class AddSiteDialog(DialogShell):
    def __init__(self, parent=None):
        super().__init__(parent, 480, 408)
        head = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title_col.addWidget(label("添加禁用网站", "H2"))
        title_col.addWidget(label("直接输入域名即可，不用写 http://；会自动覆盖常用子域名。", "Muted"))
        head.addLayout(title_col, 1)
        self.add_close_button(head)
        self.content.addLayout(head)

        self.content.addSpacing(6)
        self.content.addWidget(label("网站地址", "H3"))
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://example.com  或  example.com")
        self.url.setFixedHeight(42)
        self.url.textChanged.connect(self._preview)
        self.content.addWidget(self.url)
        self.preview = label("将同时拦截主域名及其 www / m / mobile 等子域", "Tiny")
        self.preview.setWordWrap(True)
        self.content.addWidget(self.preview)

        self.content.addSpacing(6)
        self.content.addWidget(label("显示名称", "H3"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("随便起个名字，例如：某视频网站（可留空）")
        self.name.setFixedHeight(42)
        self.content.addWidget(self.name)

        self.error = label("", "Danger")
        self.error.setWordWrap(True)
        self.error.hide()
        self.content.addWidget(self.error)

        self.content.addStretch(1)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.setFixedHeight(42)
        cancel.clicked.connect(self.reject)
        ok = QPushButton("添加并保存")
        ok.setObjectName("Primary")
        ok.setFixedHeight(42)
        ok.clicked.connect(self._accept)
        btns.addWidget(cancel, 1)
        btns.addWidget(ok, 1)
        self.content.addLayout(btns)
        self.url.returnPressed.connect(self._accept)
        self.name.returnPressed.connect(self._accept)
        self._preview("")

    def _preview(self, text: str):
        d = backend.normalize_domain(text)
        if not d:
            self.preview.setText("输入完整网址，例如 www.example.com/page")
            self.preview.setStyleSheet(f"color:{MUTED};")
        else:
            variants = backend.domain_variants(d)
            head = "  ·  ".join(variants[:4])
            self.preview.setText(f"将拦截 {len(variants)} 个地址：{head} 等")
            self.preview.setStyleSheet(f"color:{ACCENT};")

    def _accept(self):
        d = backend.normalize_domain(self.url.text())
        if not d:
            self.error.setText("请输入有效的网站地址，例如 example.com")
            self.error.show()
            return
        self.error.hide()
        self.accept()

    def data(self) -> tuple[str, str]:
        return backend.normalize_domain(self.url.text()), self.name.text().strip()


class ConfirmDialog(DialogShell):
    def __init__(self, title: str, message: str, confirm_text: str = "确认", danger: bool = True,
                 parent=None):
        super().__init__(parent, 440, 292)
        self.content.addWidget(label(title, "H2"))
        msg = label(message, "Muted")
        msg.setWordWrap(True)
        self.content.addWidget(msg)
        self.content.addStretch(1)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.setFixedHeight(42)
        cancel.clicked.connect(self.reject)
        ok = QPushButton(confirm_text)
        ok.setObjectName("DangerPrimary" if danger else "Primary")
        ok.setFixedHeight(42)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel, 1)
        btns.addWidget(ok, 1)
        self.content.addLayout(btns)
