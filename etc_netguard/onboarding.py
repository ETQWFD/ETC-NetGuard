# -*- coding: utf-8 -*-
"""Seven-step first-run guide, drawn in the same dark-mint language."""
from __future__ import annotations

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PyQt5.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .theme import ACCENT, ACCENT_2, MUTED, TEXT, TEXT_DIM
from .widgets import WizardArt, label


STEPS = [
    {
        "kicker": "WELCOME · 01",
        "title": "把网速的遥控器\n交到你手里",
        "desc": "ETC NetGuard 按「程序」管理网络：给某个程序限速、让它彻底断网，\n或者让指定网站直接返回 404。所有规则都在本机真实生效。",
        "bullets": ["按进程限速，不影响其他程序", "一键双向断网，立即生效", "网站拦截，访问即返回 404"],
    },
    {
        "kicker": "PERMISSION · 02",
        "title": "先给工具\n一把管理员钥匙",
        "desc": "限速需要写入 Windows 策略 QoS，断网需要创建防火墙规则，\n网站拦截需要修改 hosts —— 这三件事都需要管理员权限。",
        "bullets": ["启动时会自动请求管理员权限", "可在左上角设置关闭密码与黑名单", "不会收集、上传任何本机数据"],
    },
    {
        "kicker": "PROCESSES · 03",
        "title": "第一步\n在首页找到进程",
        "desc": "首页会自动扫描系统中正在运行的所有程序，并显示真实的应用图标。\n列表每隔几秒自动刷新，你勾选过的程序不会因为刷新而丢失。",
        "bullets": ["实时扫描，自动刷新", "显示图标、PID、路径与状态", "支持搜索与全选当前结果"],
    },
    {
        "kicker": "SELECT · 04",
        "title": "第二步\n勾选要管理的程序",
        "desc": "在进程列表左侧勾选一个或多个程序。勾选就是「选中目标」，\n它们会一直保留，直到你主动取消。",
        "bullets": ["多选：浏览器、游戏、下载器都可以", "勾选状态在自动刷新后保持", "随时一键清空所有选择"],
    },
    {
        "kicker": "BANDWIDTH · 05",
        "title": "第三步\n打开限速开关",
        "desc": "进入「限速」页，选择 20KB/s 到 5MB/s 的预设，或输入自定义速度，\n打开开关后，所选程序的出站流量会被真实限制在这个速度。",
        "bullets": ["策略 QoS 限速，重启后依旧保留", "关闭开关即立刻解除所选程序", "可在「生效中的规则」逐条移除"],
    },
    {
        "kicker": "BLOCK · 06",
        "title": "第四步\n断网，或者让网站 404",
        "desc": "「完全断网」用防火墙双向阻断所选程序的入站与出站连接。\n「网站禁用」添加网址后，访问会命中本机 404 拦截页。",
        "bullets": ["断网是双向的，不是只挡下载", "网站支持添加、删除与总开关", "HTTP 返回 404，HTTPS 直接阻断"],
    },
    {
        "kicker": "READY · 07",
        "title": "准备好了\n现在开始使用",
        "desc": "点击「开始使用」进入控制台。之后随时可以在左上角「设置」中\n调整密码、应用限制与黑名单。",
        "bullets": ["规则实时生效，状态一眼可见", "最小化后驻留托盘，后台守护继续运行", "任何问题都可在设置中一键复原"],
    },
]


class StepDots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.count = len(STEPS)
        self.current = 0
        self.setFixedHeight(6)

    def set_current(self, i: int):
        self.current = i
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing)
        gap = 6
        total_w = self.width() - gap * (self.count - 1)
        seg = total_w / self.count
        for i in range(self.count):
            x = i * (seg + gap)
            r = QRectF(x, 0, seg, 4)
            if i < self.current:
                p.setBrush(QColor(53, 227, 195, 90))
            elif i == self.current:
                p.setBrush(QColor(ACCENT))
            else:
                p.setBrush(QColor(255, 255, 255, 24))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 2, 2)
        p.end()


class OnboardCard(QWidget):
    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor("#0E1C26"))
        g.setColorAt(0.6, QColor("#0B151D"))
        g.setColorAt(1, QColor("#081119"))
        p.setBrush(g)
        p.setPen(QPen(QColor(255, 255, 255, 24), 1))
        p.drawRoundedRect(r, 22, 22)
        rg = QRadialGradient(r.width() * 0.18, 0, r.width() * 0.55)
        rg.setColorAt(0, QColor(53, 227, 195, 32))
        rg.setColorAt(1, QColor(53, 227, 195, 0))
        p.setBrush(rg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 22, 22)
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        for x in range(36, int(r.width()), 34):
            for y in range(30, int(r.height()), 34):
                p.drawPoint(x, y)
        p.end()


class OnboardingOverlay(QWidget):
    finished = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.step = 0
        self._busy = False
        self._closing = False
        self.card = OnboardCard(self)
        self.card.setFixedSize(980, 560)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(38, 26, 38, 26)
        lay.setSpacing(14)

        # header
        head = QHBoxLayout()
        head.setSpacing(10)
        mark = QLabel()
        mark.setFixedSize(32, 32)
        mark.setPixmap(icons.app_pixmap(32))
        head.addWidget(mark)
        brand = QVBoxLayout()
        brand.setSpacing(1)
        b1 = label("ETC NETGUARD", "H3")
        b1.setStyleSheet("letter-spacing:2px;")
        brand.addWidget(b1)
        brand.addWidget(label("首次使用引导", "Tiny"))
        head.addLayout(brand)
        head.addStretch(1)
        self.step_label = label("第 1 步 / 共 7 步", "Muted")
        head.addWidget(self.step_label)
        skip = QPushButton("跳过引导")
        skip.setObjectName("Link")
        skip.setCursor(Qt.PointingHandCursor)
        skip.clicked.connect(self.finish)
        head.addWidget(skip)
        lay.addLayout(head)

        # stage
        self.stage = QWidget()
        stage_lay = QHBoxLayout(self.stage)
        stage_lay.setContentsMargins(0, 4, 0, 0)
        stage_lay.setSpacing(34)
        self.art = WizardArt(1)
        self.art.setFixedSize(360, 360)
        stage_lay.addWidget(self.art)
        right = QVBoxLayout()
        right.setSpacing(12)
        right.setContentsMargins(0, 18, 0, 0)
        self.kicker = label("WELCOME · 01", "Tiny")
        self.kicker.setStyleSheet(f"color:{ACCENT}; letter-spacing:2px;")
        right.addWidget(self.kicker)
        self.title = QLabel("")
        f = QFont()
        f.setPixelSize(31)
        f.setWeight(QFont.Bold)
        self.title.setFont(f)
        self.title.setStyleSheet("line-height:130%;")
        self.title.setWordWrap(True)
        right.addWidget(self.title)
        right.addSpacing(4)
        self.desc = label("", "Muted")
        self.desc.setWordWrap(True)
        self.desc.setStyleSheet("line-height:170%;")
        right.addWidget(self.desc)
        right.addSpacing(8)
        self.bullets = []
        for i in range(3):
            row = QHBoxLayout()
            row.setSpacing(10)
            ic = QLabel()
            ic.setFixedSize(18, 18)
            ic.setPixmap(icons.colored_svg("check", ACCENT, 16))
            txt = label("", "", 13, TEXT_DIM)
            txt.setWordWrap(True)
            row.addWidget(ic, 0, Qt.AlignTop)
            row.addWidget(txt, 1)
            right.addLayout(row)
            self.bullets.append(txt)
        right.addStretch(1)
        stage_lay.addLayout(right, 1)
        self.stage_fx = QGraphicsOpacityEffect(self.stage)
        self.stage_fx.setOpacity(1)
        lay.addWidget(self.stage, 1)

        # footer
        self.dots = StepDots()
        lay.addWidget(self.dots)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.back = QPushButton("上一步")
        self.back.setObjectName("Ghost")
        self.back.setFixedHeight(44)
        self.back.setMinimumWidth(112)
        self.back.clicked.connect(lambda: self._move(-1))
        btns.addWidget(self.back)
        btns.addStretch(1)
        self.next = QPushButton("下一步")
        self.next.setObjectName("Primary")
        self.next.setFixedHeight(44)
        self.next.setMinimumWidth(150)
        self.next.setIcon(icons.svg_icon("arrow-right", "#04211B", 16))
        self.next.setLayoutDirection(Qt.RightToLeft)
        self.next.clicked.connect(lambda: self._move(1))
        btns.addWidget(self.next)
        lay.addLayout(btns)

        self._set_step(0, animate=False)
        self._card_anim: QPropertyAnimation | None = None

    def _sync_geometry(self):
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def _center(self):
        self._sync_geometry()
        w = self.width() or (self.parentWidget().width() if self.parentWidget() else 1200)
        h = self.height() or (self.parentWidget().height() if self.parentWidget() else 760)
        self.card.move(max(16, (w - self.card.width()) // 2), max(14, (h - self.card.height()) // 2))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._center()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(4, 8, 12, 232))
        p.end()

    def open_at(self, step: int = 0):
        self._closing = False
        self._set_step(step, animate=False)
        self.show()
        self.raise_()
        effect = QGraphicsOpacityEffect(self.card)
        self.card.setGraphicsEffect(effect)
        effect.setOpacity(0)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(260)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._card_fade = anim
        self._center()
        target = self.card.pos()
        move = QPropertyAnimation(self.card, b"pos", self)
        move.setDuration(320)
        move.setStartValue(QPoint(target.x(), target.y() + 22))
        move.setEndValue(target)
        move.setEasingCurve(QEasingCurve.OutCubic)
        move.start(QPropertyAnimation.DeleteWhenStopped)
        self._card_anim = move
        QTimer.singleShot(360, lambda: self.card.setGraphicsEffect(None))

    def _set_step(self, i: int, animate: bool = True):
        i = max(0, min(len(STEPS) - 1, i))
        data = STEPS[i]
        self.step = i
        self.step_label.setText(f"第 {i + 1} 步 / 共 7 步")
        self.kicker.setText(data["kicker"])
        self.title.setText(data["title"])
        self.desc.setText(data["desc"])
        for j, b in enumerate(self.bullets):
            b.setText(data["bullets"][j] if j < len(data["bullets"]) else "")
        self.art.step = i + 1
        self.art.update()
        self.dots.set_current(i)
        self.back.setEnabled(i > 0)
        self.next.setText("开始使用" if i == len(STEPS) - 1 else "下一步")
        self.next.setIcon(icons.svg_icon("check" if i == len(STEPS) - 1 else "arrow-right", "#04211B", 16))

    def _move(self, delta: int):
        if self._busy:
            return
        target = self.step + delta
        if target >= len(STEPS):
            self.finish()
            return
        if target < 0:
            return
        self._busy = True
        self.stage.setGraphicsEffect(self.stage_fx)
        self.stage_fx.setOpacity(1)
        out = QPropertyAnimation(self.stage_fx, b"opacity", self)
        out.setDuration(120)
        out.setStartValue(1.0)
        out.setEndValue(0.0)
        out.finished.connect(lambda: self._after_fade(target))
        out.start(QPropertyAnimation.DeleteWhenStopped)
        self._out = out

    def _after_fade(self, target: int):
        self._set_step(target)
        in_anim = QPropertyAnimation(self.stage_fx, b"opacity", self)
        in_anim.setDuration(210)
        in_anim.setStartValue(0.0)
        in_anim.setEndValue(1.0)
        in_anim.setEasingCurve(QEasingCurve.OutCubic)
        in_anim.finished.connect(self._end_stage_fade)
        in_anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._in = in_anim

    def _end_stage_fade(self):
        self._busy = False
        self.stage.setGraphicsEffect(None)

    def finish(self):
        if self._closing:
            return
        self._closing = True
        effect = QGraphicsOpacityEffect(self.card)
        self.card.setGraphicsEffect(effect)
        effect.setOpacity(1.0)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(200)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self._done)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._finish_anim = anim

    def _done(self):
        self.hide()
        self.finished.emit()
