# -*- coding: utf-8 -*-
"""Frameless shell, navigation, tray behaviour and async rule orchestration."""
from __future__ import annotations

import math

from PyQt5.QtCore import (
    QEasingCurve,
    QEvent,
    QUrl,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizeGrip,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import backend, icons, theme, native
from .dialogs import AboutAuthorDialog, ConfirmDialog
from .onboarding import OnboardingOverlay
from .pages import HomePage, LimitPage, SettingsPage, SitesPage
from .security import GuardWorker
from .security_dialogs import PasswordDialog, SettingsDialog
from .state import AppState
from .theme import ACCENT, ACCENT_2, DANGER, MUTED, TEXT, TEXT_DIM, WARNING
from .widgets import NavItem, Toast, label


class Worker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            r = self.fn(*self.args, **self.kwargs)
            self.result.emit(r)
        except Exception as e:
            self.error.emit(str(e))


class Shell(QWidget):
    """Rounded, animated background with two slow aurora glows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.radius = 24
        self.phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(90)

    def _tick(self):
        self.phase = (self.phase + 0.006) % 1.0
        if self.isVisible():
            self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)
        p.setClipPath(path)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(theme.SHELL_TOP))
        g.setColorAt(1, QColor(theme.SHELL_BOTTOM))
        p.fillPath(path, g)

        # aurora
        for i, col in enumerate((QColor(53, 227, 195, 26), QColor(78, 155, 255, 26))):
            cx = self.width() * (0.2 if i == 0 else 0.82) + math.sin((self.phase + i * 0.4) * 2 * math.pi) * 40
            cy = self.height() * (0.05 if i == 0 else 0.9) + math.cos((self.phase + i * 0.4) * 2 * math.pi) * 26
            rg = QRadialGradient(QPointF(cx, cy), self.width() * 0.55)
            rg.setColorAt(0, col)
            rg.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
            p.setPen(Qt.NoPen)
            p.setBrush(rg)
            p.drawEllipse(QPointF(cx, cy), self.width() * 0.55, self.width() * 0.55)

        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, self.radius, self.radius)
        p.end()


class TitleBar(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self.win = window
        self.setFixedHeight(54)
        self._drag_pos: QPoint | None = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 9, 12, 8)
        lay.setSpacing(8)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setObjectName("Ghost")
        self.settings_btn.setFixedHeight(32)
        self.settings_btn.setIcon(icons.svg_icon("settings", MUTED, 15))
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(window.open_settings)
        lay.addWidget(self.settings_btn)

        self.about_btn = QPushButton("关于作者")
        self.about_btn.setObjectName("Ghost")
        self.about_btn.setFixedHeight(32)
        self.about_btn.setIcon(icons.svg_icon("user-round", MUTED, 15))
        self.about_btn.setCursor(Qt.PointingHandCursor)
        self.about_btn.clicked.connect(window.show_about)
        lay.addWidget(self.about_btn)
        crumb = label("网络控制台", "Tiny")
        crumb.setStyleSheet(f"color:{MUTED}; letter-spacing:1px; padding-left:6px;")
        lay.addWidget(crumb)
        lay.addStretch(1)

        self.status_chip = QLabel("待配置")
        self.status_chip.setObjectName("Pill")
        self.status_chip.setFixedHeight(26)
        lay.addWidget(self.status_chip, 0, Qt.AlignVCenter)

        self.min_btn = self._ctrl("minus", "WinBtn")
        self.min_btn.clicked.connect(window.showMinimized)
        lay.addWidget(self.min_btn)
        self.max_btn = self._ctrl("square", "WinBtn")
        self.max_btn.clicked.connect(window.toggle_max)
        lay.addWidget(self.max_btn)
        self.close_btn = self._ctrl("x", "WinClose")
        self.close_btn.clicked.connect(window.request_close)
        lay.addWidget(self.close_btn)

    def _ctrl(self, icon: str, obj: str) -> QPushButton:
        b = QPushButton()
        b.setObjectName(obj)
        b.setFixedSize(34, 30)
        b.setIcon(icons.svg_icon(icon, TEXT_DIM, 14))
        b.setCursor(Qt.PointingHandCursor)
        return b

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.win.isMaximized() is False:
            self._drag_pos = event.globalPos() - self.win.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            if self.win.isMaximized():
                return
            self.win.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.win.toggle_max()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(255, 255, 255, 2))
        p.setPen(QPen(QColor(255, 255, 255, 10), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.state = AppState()
        self._quitting = False
        self._action_busy = False
        self._workers: set[Worker] = set()
        self._scan_worker: Worker | None = None
        self._tray_hint_shown = False
        self._maximized = False
        self._sites_busy = False
        self._close_prompt_open = False
        self._native_ok = False

        self.setWindowTitle("ETC NetGuard")
        self.setWindowIcon(icons.app_icon())
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(1080, 680)
        self.resize(1260, 820)

        self.setStyleSheet(theme.qss() + theme.SHELL_QSS)

        self.root = QWidget(self)
        self.root_layout = QVBoxLayout(self.root)
        self.root_layout.setContentsMargins(18, 18, 18, 18)
        self.setCentralWidget(self.root)

        self.shell = Shell(self.root)
        self.root_layout.addWidget(self.shell)
        self.shadow = QGraphicsDropShadowEffect(self.shell)
        self.shadow.setBlurRadius(44)
        self.shadow.setOffset(0, 10)
        self.shadow.setColor(QColor(0, 0, 0, 175))
        self.shell.setGraphicsEffect(self.shadow)

        shell_lay = QVBoxLayout(self.shell)
        shell_lay.setContentsMargins(0, 0, 0, 0)
        shell_lay.setSpacing(0)
        self.titlebar = TitleBar(self)
        shell_lay.addWidget(self.titlebar)
        self.body = QWidget(self.shell)
        shell_lay.addWidget(self.body, 1)

        body_lay = QHBoxLayout(self.body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(228)
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(15, 16, 15, 14)
        side_lay.setSpacing(6)
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(42))
        logo.setFixedSize(42, 42)
        logo_row.addWidget(logo)
        lcol = QVBoxLayout()
        lcol.setSpacing(0)
        n = QLabel("ETC NetGuard")
        f = QFont()
        f.setPixelSize(16)
        f.setWeight(QFont.Bold)
        n.setFont(f)
        lcol.addWidget(n)
        sub = label("NETWORK CONTROL", "Tiny")
        sub.setStyleSheet(f"color:{MUTED}; letter-spacing:1.6px; font-size:9px;")
        lcol.addWidget(sub)
        logo_row.addLayout(lcol, 1)
        side_lay.addLayout(logo_row)
        side_lay.addSpacing(16)

        self.nav_items = []
        for text, icon, idx in (("首页 · 进程", "house", 0), ("限速 · 断网", "gauge", 1),
                                ("网站禁用", "globe", 2), ("设置", "settings", 3)):
            item = NavItem(text, icon)
            item.clicked.connect(lambda i=idx: self.goto(i))
            side_lay.addWidget(item)
            self.nav_items.append(item)
        self.nav_items[0].set_active(True)
        side_lay.addStretch(1)

        admin_card = QFrame()
        admin_card.setObjectName("AdminCard")
        ac = QHBoxLayout(admin_card)
        ac.setContentsMargins(11, 9, 11, 9)
        ac.setSpacing(9)
        ai = QLabel()
        ai.setFixedSize(30, 30)
        ai.setPixmap(icons.colored_svg("shield-check", ACCENT, 17))
        ai.setAlignment(Qt.AlignCenter)
        ac.addWidget(ai)
        acol = QVBoxLayout()
        acol.setSpacing(1)
        self.admin_title = label("管理员模式", "H3")
        self.admin_title.setStyleSheet("font-size:12px;")
        self.admin_sub = label("正在检查权限…", "Tiny")
        acol.addWidget(self.admin_title)
        acol.addWidget(self.admin_sub)
        ac.addLayout(acol, 1)
        side_lay.addWidget(admin_card)
        side_lay.addSpacing(8)
        by = QHBoxLayout()
        by.addWidget(label("by etc", "Tiny"))
        by.addStretch(1)
        gh_btn = QPushButton()
        gh_btn.setObjectName("Link")
        gh_btn.setFixedSize(24, 20)
        gh_btn.setIcon(icons.svg_icon("github", MUTED, 14))
        gh_btn.setToolTip("打开 GitHub 开源仓库")
        gh_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(backend.REPO_URL)))
        by.addWidget(gh_btn)
        side_lay.addLayout(by)

        body_lay.addWidget(self.sidebar)
        self.content = QStackedWidget()
        self.content.setObjectName("ContentArea")
        body_lay.addWidget(self.content, 1)

        self.home = HomePage(self)
        self.limit = LimitPage(self)
        self.sites = SitesPage(self)
        self.settings = SettingsPage(self)
        for page in (self.home, self.limit, self.sites, self.settings):
            self.content.addWidget(page)

        self.toast = Toast(self)

        self.onboarding = OnboardingOverlay(self.body)
        self.onboarding.finished.connect(self._onboarding_finished)
        self.onboarding.hide()

        self.grip = QSizeGrip(self.shell)
        self.grip.setFixedSize(18, 18)
        self.grip.setStyleSheet("background: transparent;")

        self._setup_tray()

        self.guard = GuardWorker(self)
        self.guard.blocked.connect(self._guard_blocked)
        self.guard.failed.connect(self._guard_failed)
        self.guard.update_rules(self.state.block_cmd, self.state.block_taskmgr,
                               self.state.block_browsers, self.state.blacklist)
        self.guard.start()

        self._close_poll = QTimer(self)
        self._close_poll.setInterval(220)
        self._close_poll.timeout.connect(self._poll_native_close)
        QTimer.singleShot(120, self._install_native_guard)

        self.scan_timer = QTimer(self)
        self.scan_timer.setInterval(self.state.refresh_sec * 1000)
        self.scan_timer.timeout.connect(self.refresh_processes)
        self.scan_timer.start()

        QTimer.singleShot(80, self._center_on_screen)
        QTimer.singleShot(160, self._startup)

    # ------------------------------------------------------------------
    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        w = min(self.width(), geo.width() - 30)
        h = min(self.height(), geo.height() - 50)
        self.resize(w, h)
        self.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)

    def _setup_tray(self):
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(icons.app_icon(), self)
        menu = QMenu()
        show = QAction("显示控制台", self)
        show.triggered.connect(self._show_from_tray)
        menu.addAction(show)
        menu.addSeparator()
        quit_action = QAction("退出 ETC NetGuard", self)
        quit_action.triggered.connect(self.request_quit)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.setToolTip("ETC NetGuard · 网络控制台")
        tray.activated.connect(lambda reason: self._show_from_tray() if reason == QSystemTrayIcon.Trigger else None)
        tray.show()
        self.tray = tray

    def _show_from_tray(self):
        if self.state.password_enabled and not PasswordDialog.ask(
                self, self.state, "打开主窗口", "从托盘打开控制台需要关闭密码。"):
            return
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.refresh_processes()

    def _startup(self):
        self.refresh_processes()
        self._update_status()
        self.settings.refresh_view()
        native.NATIVE.set_close_guard(self.state.password_enabled)
        if backend.IS_WINDOWS and not backend.is_admin() and not backend.PREVIEW:
            self.toast.show_message("未获得管理员权限，限速 / 断网 / hosts 规则将无法生效。请右键以管理员身份运行。", "warn", 5200)
        if self.state.sites_enabled and self.state.sites:
            self._restore_sites()
        if not self.state.onboarding_done:
            QTimer.singleShot(380, lambda: self.onboarding.open_at(0))

    def _restore_sites(self):
        def done(res):
            ok, msg = res
            if not ok:
                self.state.sites_enabled = False
                self.state.save()
                self.toast.show_message(f"网站拦截未能恢复：{msg}", "error", 4500)
                self.sync_ui()
        self._run(backend.apply_sites, self.state.sites, True, on_done=done, passive=True)

    # ------------------------------------------------------------------
    def goto(self, index: int):
        index = max(0, min(self.content.count() - 1, index))
        if index == 3 and self.state.password_enabled and not self.content.currentIndex() == 3:
            if not PasswordDialog.ask(self, self.state, "打开设置页", "查看设置与维护需要关闭密码。"):
                return
        if self.content.currentIndex() == index and self.content.currentWidget().isVisible():
            self._refresh_page(index)
            return
        old = self.content.currentWidget()
        if old is not None and old.isVisible():
            pix = old.grab()
            overlay = QLabel(self.content)
            overlay.setPixmap(pix)
            overlay.setGeometry(old.geometry())
            overlay.show()
            overlay.raise_()
            eff = QGraphicsOpacityEffect(overlay)
            overlay.setGraphicsEffect(eff)
            eff.setOpacity(1.0)
            anim = QPropertyAnimation(eff, b"opacity", overlay)
            anim.setDuration(220)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(overlay.deleteLater)
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            self._page_overlay_anim = anim
        self.content.setCurrentIndex(index)
        for i, item in enumerate(self.nav_items):
            item.set_active(i == index)
        self._refresh_page(index)

    def _refresh_page(self, index: int):
        if index == 0:
            self.home.refresh_view()
        elif index == 1:
            self.limit.refresh_view()
        elif index == 2:
            self.sites.refresh_view()
        else:
            self.settings.refresh_view()

    def go_home(self):
        self.goto(0)

    def go_limit(self):
        if not self.state.selected_items():
            self.toast.show_message("请先在首页勾选需要限速的进程", "warn")
            return
        self.goto(1)

    # ------------------------------------------------------------------
    def refresh_processes(self, force: bool = False):
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
        if self.isHidden() and not force:
            return
        w = Worker(backend.list_processes)
        w.result.connect(self._on_scanned)
        w.error.connect(lambda msg: self.toast.show_message(f"扫描进程失败：{msg}", "error") if force else None)
        w.finished.connect(lambda: self._cleanup_worker(w))
        self._workers.add(w)
        self._scan_worker = w
        w.start()

    def _on_scanned(self, rows):
        if not isinstance(rows, list):
            return
        self.state.set_processes(rows)
        self.home.set_processes(rows)
        self.home.update_stats()
        if self.content.currentIndex() == 1:
            self.limit.refresh_view()

    def _cleanup_worker(self, w: Worker):
        self._workers.discard(w)
        if self._scan_worker is w:
            self._scan_worker = None
        w.deleteLater()

    def _run(self, fn, *args, on_done, passive: bool = False, busy_message: str = ""):
        if self._action_busy and not passive:
            self.toast.show_message("上一条规则还在执行，请稍候再试。", "info")
            return
        if not passive:
            self._action_busy = True
        if busy_message:
            self.toast.show_message(busy_message, "info", 1800)
        w = Worker(fn, *args)
        w.result.connect(lambda res: self._after_action(w, res, on_done, passive))
        w.error.connect(lambda msg: self._after_error(w, msg, on_done, passive))
        w.finished.connect(lambda: self._cleanup_worker(w))
        self._workers.add(w)
        w.start()

    def _after_action(self, w, res, on_done, passive):
        if not passive:
            self._action_busy = False
        try:
            on_done(res)
        except Exception:
            pass

    def _after_error(self, w, msg, on_done, passive):
        if not passive:
            self._action_busy = False
        self.toast.show_message(f"操作失败：{msg}", "error", 4200)
        try:
            on_done((False, msg))
        except Exception:
            pass

    # -- actions -------------------------------------------------------
    def apply_limit(self, items: list[dict], bps: int):
        if not items:
            self.toast.show_message("请先在首页勾选进程", "warn")
            return
        paths = [x["path"] for x in items]

        def work():
            backend.remove_blocks(paths)
            return backend.apply_limits(items, bps)

        def done(res):
            ok, msg = res if isinstance(res, tuple) else (False, str(res))
            if ok:
                self.state.remove_block_rules(paths)
                self.state.set_limit_rules(items, bps)
                self.sync_ui()
                self.toast.show_message(f"已限制 {len(items)} 个进程 · {backend.format_rate(bps)}", "ok")
            else:
                self.toast.show_message(f"限速失败：{msg}", "error", 4600)
                self.limit.refresh_view()

        self._run(work, on_done=done)

    def remove_limit(self, items: list[dict]):
        if not self._require_pw("关闭限速", "关闭限速开关需要关闭密码。"):
            self.limit.refresh_view()
            return
        paths = [x["path"] for x in items]

        def done(res):
            ok, msg = res if isinstance(res, tuple) else (False, str(res))
            if ok:
                self.state.remove_limit_rules(paths)
                self.sync_ui()
                self.toast.show_message("已解除所选进程的限速", "ok")
            else:
                self.toast.show_message(f"解除失败：{msg}", "error")
                self.limit.refresh_view()

        self._run(backend.remove_limits, paths, on_done=done)

    def apply_block(self, items: list[dict]):
        if not items:
            self.toast.show_message("请先在首页勾选进程", "warn")
            return
        paths = [x["path"] for x in items]

        def work():
            backend.remove_limits(paths)
            return backend.apply_blocks(items, True)

        def done(res):
            ok, msg = res if isinstance(res, tuple) else (False, str(res))
            if ok:
                self.state.remove_limit_rules(paths)
                self.state.set_block_rules(items)
                self.sync_ui()
                self.toast.show_message(f"已切断 {len(items)} 个进程的网络", "ok")
            else:
                self.toast.show_message(f"断网失败：{msg}", "error", 4600)
                self.limit.refresh_view()
                self.home.refresh_view()

        self._run(work, on_done=done)

    def remove_block(self, items: list[dict]):
        if not self._require_pw("关闭断网", "关闭断网开关需要关闭密码。"):
            self.limit.refresh_view()
            return
        paths = [x["path"] for x in items]

        def done(res):
            ok, msg = res if isinstance(res, tuple) else (False, str(res))
            if ok:
                self.state.remove_block_rules(paths)
                self.sync_ui()
                self.toast.show_message("已恢复所选进程的网络", "ok")
            else:
                self.toast.show_message(f"恢复失败：{msg}", "error")
                self.limit.refresh_view()

        self._run(backend.remove_blocks, paths, on_done=done)

    def block_selected(self):
        self.apply_block(self.state.selected_items())

    def clear_rules_selected(self):
        items = self.state.selected_items()
        if not items:
            self.toast.show_message("请先勾选进程", "warn")
            return
        if not self._require_pw("解除限制", "解除所选进程的限速或断网需要关闭密码。"):
            return
        paths = [x["path"] for x in items]

        def work():
            backend.remove_limits(paths)
            backend.remove_blocks(paths)
            return True, "OK"

        def done(res):
            ok, msg = res if isinstance(res, tuple) else (True, "")
            if ok:
                self.state.remove_limit_rules(paths)
                self.state.remove_block_rules(paths)
                self.sync_ui()
                self.toast.show_message(f"已解除 {len(items)} 个进程的全部限制", "ok")
            else:
                self.toast.show_message(f"解除失败：{msg}", "error")

        self._run(work, on_done=done)

    def remove_rule(self, kind: str, path: str):
        if not self._require_pw("移除规则", "移除一条已生效的规则需要关闭密码。"):
            return
        def work():
            if kind == "limit":
                return backend.remove_limits([path])
            return backend.remove_blocks([path])

        def done(res):
            ok, msg = res if isinstance(res, tuple) else (True, "")
            if ok:
                if kind == "limit":
                    self.state.remove_limit_rules([path])
                else:
                    self.state.remove_block_rules([path])
                self.sync_ui()
                self.toast.show_message("已移除该规则", "ok")
            else:
                self.toast.show_message(f"移除失败：{msg}", "error")

        self._run(work, on_done=done)

    def clear_all_rules(self):
        if not self._require_pw("清除全部规则", "清除限速、断网和网站拦截需要关闭密码。"):
            return
        if not (self.state.limits or self.state.blocks or self.state.sites_enabled):
            self.toast.show_message("当前没有需要清除的规则", "info")
            return
        dlg = ConfirmDialog("清除全部规则？", "将移除所有限速、断网与网站拦截规则，并停止本地 404 服务。此操作不会删除你的网站列表。",
                            "全部清除", True, self)
        if dlg.exec_() != dlg.Accepted:
            return

        def done(res):
            self.state.limits.clear()
            self.state.blocks.clear()
            self.state.sites_enabled = False
            self.state.save()
            self.sync_ui()
            self.toast.show_message("全部规则已清除，网络已恢复", "ok")

        self._run(backend.clear_all_rules, on_done=done)

    def set_sites_enabled(self, checked: bool):
        if self._action_busy:
            self.sites.refresh_view()
            self.toast.show_message("上一条规则还在执行，请稍候再试。", "info")
            return
        if self._sites_busy:
            self.sites.refresh_view()
            self.toast.show_message("正在应用网站规则，请稍候", "info")
            return
        if checked and not self.state.sites:
            self.sites.refresh_view()
            self.toast.show_message("请先添加至少一个网站", "warn")
            return
        if not checked and not self._require_pw("关闭网站拦截", "关闭网站拦截需要关闭密码。"):
            self.sites.refresh_view()
            return
        self._sites_busy = True

        def done(res):
            self._sites_busy = False
            ok, msg = res if isinstance(res, tuple) else (False, str(res))
            if ok:
                self.state.sites_enabled = checked
                self.state.save()
                self.sync_ui()
                self.toast.show_message("网站拦截已启用 · 命中返回 404" if checked else "网站拦截已关闭", "ok")
            else:
                self.toast.show_message(f"网站拦截设置失败：{msg}", "error", 4800)
                self.sites.refresh_view()

        self._run(backend.apply_sites, self.state.sites, checked, on_done=done, busy_message="正在更新网站规则…")

    def add_site(self, domain: str, name: str):
        if not self.state.add_site(domain, name):
            self.toast.show_message("这个网站已经在列表里了", "warn")
            return
        if self.state.sites_enabled:
            def done(res):
                ok, msg = res if isinstance(res, tuple) else (False, str(res))
                if not ok:
                    self.state.sites_enabled = False
                    self.state.save()
                    self.toast.show_message(f"网站规则生效失败：{msg}", "error", 4600)
                else:
                    self.toast.show_message(f"已添加 {domain} · 访问返回 404", "ok")
                self.sync_ui()

            self._run(backend.apply_sites, self.state.sites, True, on_done=done, busy_message="正在写入新的网站规则…")
        else:
            self.sync_ui()
            self.toast.show_message(f"已保存 {domain}，启用总开关后生效", "ok")

    def remove_site(self, domain: str):
        if not self._require_pw("删除网站规则", "删除网站拦截规则需要关闭密码。"):
            return
        self.state.remove_site(domain)
        if self.state.sites_enabled:
            def done(res):
                ok, msg = res if isinstance(res, tuple) else (False, str(res))
                if not ok:
                    self.state.sites_enabled = False
                    self.state.save()
                    self.toast.show_message(f"更新网站规则失败：{msg}", "error")
                else:
                    self.toast.show_message("网站规则已删除", "ok")
                self.sync_ui()

            self._run(backend.apply_sites, self.state.sites, True, on_done=done, busy_message="正在更新网站规则…")
        else:
            self.sync_ui()
            self.toast.show_message("网站规则已删除", "ok")

    # ------------------------------------------------------------------
    def on_selection_changed(self):
        self.home.update_stats()
        if self.content.currentIndex() == 1:
            self.limit.refresh_view()
        self._update_status()

    def sync_ui(self):
        self.home.refresh_view()
        self.limit.refresh_view()
        self.sites.refresh_view()
        self.settings.refresh_view()
        self._update_status()

    def _update_status(self):
        n = (len(self.state.limits) + len(self.state.blocks)
             + (len(self.state.sites) if self.state.sites_enabled else 0)
             + self.state.restriction_count() + len(self.state.blacklist))
        if n:
            self.titlebar.status_chip.setText(f"防护中 · {n} 项生效")
            self.titlebar.status_chip.setStyleSheet(
                "background: rgba(53,227,195,20); color:#35E3C3; border:1px solid rgba(53,227,195,50);"
                "border-radius:8px; padding:3px 9px; font-size:11px; font-weight:600;"
            )
        else:
            self.titlebar.status_chip.setText("待配置")
            self.titlebar.status_chip.setStyleSheet(
                "background: rgba(255,255,255,8); color:#7F93A8; border:1px solid rgba(255,255,255,16);"
                "border-radius:8px; padding:3px 9px; font-size:11px;"
            )
        admin = backend.is_admin()
        self.admin_title.setText("管理员模式" if admin else "权限受限")
        self.admin_sub.setText("已获得系统权限" if admin else "请以管理员身份运行")
        self.admin_sub.setStyleSheet(f"color:{ACCENT if admin else DANGER}; font-size:10px;")
        if self.tray:
            self.tray.setToolTip(f"ETC NetGuard · {'防护中' if n else '待配置'} · {n} 项生效")

    # ------------------------------------------------------------------
    def _require_pw(self, title: str, desc: str) -> bool:
        if not self.state.password_enabled:
            return True
        return PasswordDialog.ask(self, self.state, title, desc)

    def open_settings(self):
        if self.state.password_enabled and not PasswordDialog.ask(
                self, self.state, "打开安全设置", "修改密码、限制与黑名单需要关闭密码。"):
            return
        dlg = SettingsDialog(self)
        dlg.exec_()
        self.apply_security()
        self.sync_ui()

    def apply_security(self):
        native.NATIVE.set_close_guard(self.state.password_enabled)
        self.sync_guard()
        self.settings.refresh_view()
        self._update_status()

    def sync_guard(self):
        if hasattr(self, "guard"):
            self.guard.update_rules(self.state.block_cmd, self.state.block_taskmgr,
                                    self.state.block_browsers, self.state.blacklist)

    def _guard_blocked(self, name: str, reason: str):
        self.toast.show_message(f"已阻止 {name} · {reason}", "warn", 3000)

    def _guard_failed(self, name: str, msg: str):
        self.toast.show_message(f"{name}：{msg}", "error", 3600)

    def _install_native_guard(self):
        try:
            hwnd = int(self.winId())
        except Exception:
            return
        self._native_ok = native.NATIVE.install_close_guard(hwnd)
        native.NATIVE.set_close_guard(self.state.password_enabled)
        if self._native_ok:
            self._close_poll.start()

    def _poll_native_close(self):
        if native.NATIVE.take_close_request():
            self.request_close()

    def request_close(self):
        # Without a password the window closes directly. With a password the
        # native WM_CLOSE guard (etc_guard.dll) lands here and the window is
        # held until the password is verified; then it hides to the tray.
        if not self.state.password_enabled:
            self.quit_app()
            return
        if self._close_prompt_open:
            return
        self._close_prompt_open = True
        try:
            ok = PasswordDialog.ask(
                self, self.state, "关闭主窗口",
                "关闭主窗口需要关闭密码；验证后会隐藏到托盘，退出请使用托盘菜单。",
            )
        finally:
            self._close_prompt_open = False
        if ok:
            self._hide_to_tray()

    def _hide_to_tray(self):
        self.hide()
        if self.tray:
            self.tray.showMessage(
                "ETC NetGuard",
                "已隐藏到托盘。右键托盘图标可显示控制台或退出，退出需要关闭密码。",
                QSystemTrayIcon.Information,
                3200,
            )

    def request_quit(self):
        if self.state.password_enabled and not PasswordDialog.ask(
                self, self.state, "退出软件", "退出托盘中的 ETC NetGuard 需要关闭密码。"):
            return
        native.NATIVE.set_close_guard(False)
        self.quit_app()

    # ------------------------------------------------------------------
    def show_about(self):
        dlg = AboutAuthorDialog(self)
        dlg.exec_()

    def replay_onboarding(self):
        self.onboarding.open_at(0)

    def _onboarding_finished(self):
        if not self.state.onboarding_done:
            self.state.finish_onboarding()
            self.toast.show_message("引导完成，开始使用吧", "ok")
        else:
            self.toast.show_message("随时可以在设置页重新观看引导", "info")
        self._update_status()

    # ------------------------------------------------------------------
    def toggle_max(self):
        if self.isMaximized():
            self.showNormal()
            self._maximized = False
        else:
            self.showMaximized()
            self._maximized = True
        self._apply_max_style()

    def _apply_max_style(self):
        maximized = self.isMaximized()
        self.root_layout.setContentsMargins(0, 0, 0, 0) if maximized else self.root_layout.setContentsMargins(18, 18, 18, 18)
        self.shell.radius = 0 if maximized else 24
        self.shadow.setEnabled(not maximized)
        self.shell.update()

    def changeEvent(self, event):  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self._apply_max_style()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "onboarding"):
            self.onboarding.setGeometry(self.body.rect())
        if hasattr(self, "grip"):
            self.grip.move(self.shell.width() - 22, self.shell.height() - 22)
        if hasattr(self, "toast"):
            self.toast._layout_to_parent()
        self._center_on_screen_card()

    def _center_on_screen_card(self):
        if hasattr(self, "onboarding") and self.onboarding.isVisible():
            self.onboarding._center()

    def quit_app(self):
        self._quitting = True
        native.NATIVE.set_close_guard(False)
        if hasattr(self, "guard"):
            self.guard.stop()
        backend.BLOCK_SERVER.stop()
        if self.tray:
            self.tray.hide()
        for w in list(self._workers):
            try:
                w.wait(2500)
            except Exception:
                pass
        QApplication.quit()

    def closeEvent(self, event):  # noqa: N802
        if self._quitting:
            backend.BLOCK_SERVER.stop()
            event.accept()
            return
        if self.state.password_enabled:
            event.ignore()
            QTimer.singleShot(0, self.request_close)
            return
        self._quitting = True
        native.NATIVE.set_close_guard(False)
        if hasattr(self, "guard"):
            self.guard.stop()
        backend.BLOCK_SERVER.stop()
        event.accept()
        QApplication.quit()
