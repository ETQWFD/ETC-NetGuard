# -*- coding: utf-8 -*-
"""Password, security settings and blacklist dialogs."""
from __future__ import annotations

import os

from PyQt5.QtCore import QFileInfo, QPropertyAnimation, QPoint, Qt
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import backend, icons
from .dialogs import DialogShell
from .security import is_protected
from .theme import ACCENT, DANGER, MUTED, TEXT, WARNING
from .widgets import ToggleSwitch, label


def _tile(name: str, color: str = ACCENT, size: int = 38) -> QLabel:
    lb = QLabel()
    lb.setFixedSize(size, size)
    lb.setAlignment(Qt.AlignCenter)
    c = QColor(color)
    lb.setStyleSheet(
        f"background: rgba({c.red()},{c.green()},{c.blue()},18);"
        f"border: 1px solid rgba({c.red()},{c.green()},{c.blue()},45);"
        f"border-radius: {size // 2}px;"
    )
    lb.setPixmap(icons.colored_svg(name, color, int(size * 0.48)))
    return lb


def _card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(8)
    return f, lay


class PasswordDialog(DialogShell):
    """Small modal that verifies the local password before a protected action."""

    def __init__(self, parent, state, title="需要密码", desc="请输入关闭密码以继续。"):
        super().__init__(parent, 430, 268)
        self.state = state
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addWidget(label(title, "H2"))
        col.addWidget(label(desc, "Muted"))
        head.addLayout(col, 1)
        self.add_close_button(head)
        self.content.addLayout(head)
        self.content.addSpacing(6)
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)
        self.input.setPlaceholderText("输入密码")
        self.input.setFixedHeight(42)
        self.input.returnPressed.connect(self._submit)
        self.content.addWidget(self.input)
        self.error = label("密码不正确，请重试。", "Danger")
        self.error.hide()
        self.content.addWidget(self.error)
        self.content.addStretch(1)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.setFixedHeight(40)
        cancel.clicked.connect(self.reject)
        ok = QPushButton("确认")
        ok.setObjectName("Primary")
        ok.setFixedHeight(40)
        ok.clicked.connect(self._submit)
        buttons.addWidget(cancel, 1)
        buttons.addWidget(ok, 1)
        self.content.addLayout(buttons)
        self._shake = QPropertyAnimation(self.input, b"pos", self)
        self._shake.setDuration(260)

    def _submit(self):
        if self.state.verify_password(self.input.text()):
            self.accept()
            return
        self.error.show()
        self.input.selectAll()
        self.input.setFocus()
        start = self.input.pos()
        seq = [(start.x() - 6, start.y()), (start.x() + 6, start.y()),
               (start.x() - 4, start.y()), (start.x() + 4, start.y()), (start.x(), start.y())]
        self._shake.stop()
        self._shake.setKeyValues([(0.0, start), (0.15, QPoint(*seq[0])), (0.3, QPoint(*seq[1])),
                                  (0.5, QPoint(*seq[2])), (0.7, QPoint(*seq[3])), (1.0, start)])
        self._shake.start()

    @classmethod
    def ask(cls, parent, state, title="需要密码", desc="请输入密码以继续。") -> bool:
        if not state.password_enabled:
            return True
        dlg = cls(parent, state, title, desc)
        return dlg.exec_() == dlg.Accepted


class PasswordSetupDialog(DialogShell):
    def __init__(self, parent, state, start_enabled: bool = True):
        super().__init__(parent, 520, 452)
        self.state = state
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addWidget(label("关闭密码", "H2"))
        col.addWidget(label("密码只以 PBKDF2 散列保存在本机，不上传。", "Muted"))
        head.addLayout(col, 1)
        self.add_close_button(head)
        self.content.addLayout(head)

        row = QFrame()
        row.setObjectName("CardSoft")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 10, 14, 10)
        rc = QVBoxLayout()
        rc.setSpacing(1)
        rc.addWidget(label("关闭软件时需要密码", "H3"))
        rc.addWidget(label("退出托盘、重新打开主窗口、移出黑名单都会校验。", "Tiny"))
        rl.addLayout(rc, 1)
        self.toggle = ToggleSwitch(checked=state.password_enabled or start_enabled)
        self.toggle.toggled.connect(self._sync_fields)
        rl.addWidget(self.toggle, 0, Qt.AlignVCenter)
        self.content.addWidget(row)

        self.current_label = label("当前密码", "Tiny")
        self.current = QLineEdit()
        self.current.setEchoMode(QLineEdit.Password)
        self.current.setPlaceholderText("修改或关闭密码前需要验证")
        self.current.setFixedHeight(38)
        self.content.addWidget(self.current_label)
        self.content.addWidget(self.current)

        self.new_label = label("新密码", "Tiny")
        self.new = QLineEdit()
        self.new.setEchoMode(QLineEdit.Password)
        self.new.setPlaceholderText("至少 4 位，建议 6 位以上")
        self.new.setFixedHeight(38)
        self.content.addWidget(self.new_label)
        self.content.addWidget(self.new)

        self.confirm_label = label("确认新密码", "Tiny")
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        self.confirm.setPlaceholderText("再输入一次")
        self.confirm.setFixedHeight(38)
        self.confirm.returnPressed.connect(self._save)
        self.content.addWidget(self.confirm_label)
        self.content.addWidget(self.confirm)

        self.error = label("", "Danger")
        self.error.setWordWrap(True)
        self.error.hide()
        self.content.addWidget(self.error)
        self.content.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.setFixedHeight(40)
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setObjectName("Primary")
        save.setFixedHeight(40)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel, 1)
        buttons.addWidget(save, 1)
        self.content.addLayout(buttons)
        self._sync_fields()

    def _sync_fields(self, *_):
        enabled = self.toggle.isChecked()
        existing = self.state.password_enabled
        self.current_label.setVisible(existing)
        self.current.setVisible(existing)
        self.new_label.setVisible(enabled)
        self.new.setVisible(enabled)
        self.confirm_label.setVisible(enabled)
        self.confirm.setVisible(enabled)
        if not enabled:
            self.error.hide()

    def _save(self):
        self.error.hide()
        enabled = self.toggle.isChecked()
        if self.state.password_enabled:
            if not self.state.verify_password(self.current.text()):
                return self._fail("当前密码不正确。")
        if not enabled:
            self.state.clear_password()
            self.accept()
            return
        new = self.new.text()
        if not new:
            if self.state.password_enabled:
                self.accept()
                return
            return self._fail("请设置一个密码。")
        if len(new) < 4:
            return self._fail("密码至少需要 4 位。")
        if len(new) > 64:
            return self._fail("密码最长 64 位。")
        if new != self.confirm.text():
            return self._fail("两次输入的密码不一致。")
        self.state.set_password(new)
        self.accept()

    def _fail(self, text: str):
        self.error.setText(text)
        self.error.show()
        return None


class SettingsDialog(DialogShell):
    """Popup security center opened from the top-left settings button."""

    def __init__(self, main):
        parent_h = main.height() if main is not None else 820
        panel_h = max(600, min(660, int(parent_h) - 120))
        super().__init__(main, 790, panel_h)
        self.main = main
        self.state = main.state
        self._icons = QFileIconProvider()
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addWidget(label("安全设置", "PageTitle"))
        col.addWidget(label("密码保护 · 应用限制 · 程序黑名单。所有设置只保存在本机。", "Muted"))
        head.addLayout(col, 1)
        self.add_close_button(head)
        self.content.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollArea>QWidget>QWidget{background:transparent;}")
        host = QWidget()
        host_lay = QVBoxLayout(host)
        host_lay.setContentsMargins(0, 0, 4, 0)
        host_lay.setSpacing(10)
        scroll.setWidget(host)
        self.content.addWidget(scroll, 1)
        self.scroll = scroll

        # password card
        pc, pl = _card()
        prow = QHBoxLayout()
        prow.setSpacing(12)
        prow.addWidget(_tile("shield-check", ACCENT, 38))
        pcol = QVBoxLayout()
        pcol.setSpacing(2)
        pcol.addWidget(label("关闭密码", "H2"))
        self.pw_desc = label("", "Tiny")
        pcol.addWidget(self.pw_desc)
        prow.addLayout(pcol, 1)
        self.pw_btn = QPushButton("")
        self.pw_btn.setObjectName("Primary")
        self.pw_btn.setFixedHeight(36)
        self.pw_btn.clicked.connect(self._edit_password)
        prow.addWidget(self.pw_btn, 0, Qt.AlignVCenter)
        pl.addLayout(prow)
        host_lay.addWidget(pc)

        # restrictions
        rc, rl = _card()
        rhead = QHBoxLayout()
        rhead.addWidget(_tile("ban", WARNING, 38))
        rcol = QVBoxLayout()
        rcol.setSpacing(2)
        rcol.addWidget(label("应用限制", "H2"))
        rcol.addWidget(label("开启后由后台守护每 1.5 秒检查并结束对应程序。", "Tiny"))
        rhead.addLayout(rcol, 1)
        rl.addLayout(rhead)
        self.toggles = {}
        for key, title, desc in (
            ("block_cmd", "禁止命令提示符与 PowerShell", "阻止 cmd、PowerShell、Windows Terminal 启动。"),
            ("block_taskmgr", "禁止任务管理器", "阻止 Taskmgr.exe 运行。"),
            ("block_browsers", "禁止浏览器", "阻止 Chrome、Edge、Firefox 及常见国产浏览器。"),
        ):
            rl.addWidget(self._toggle_row(key, title, desc))
        host_lay.addWidget(rc)

        # blacklist
        bc, bl = _card()
        bhead = QHBoxLayout()
        bcol = QVBoxLayout()
        bcol.setSpacing(2)
        brow = QHBoxLayout()
        brow.setSpacing(8)
        brow.addWidget(label("程序黑名单", "H2"))
        self.bl_count = QLabel("0 个")
        self.bl_count.setObjectName("Pill")
        brow.addWidget(self.bl_count)
        brow.addStretch(1)
        bcol.addLayout(brow)
        bcol.addWidget(label("被加入的程序一启动就会被结束；移除需要密码。", "Tiny"))
        bhead.addLayout(bcol, 1)
        add_btn = QPushButton("添加程序")
        add_btn.setObjectName("Ghost")
        add_btn.setFixedHeight(34)
        add_btn.setIcon(icons.svg_icon("plus", TEXT, 14))
        add_btn.clicked.connect(self._add_blacklist)
        bhead.addWidget(add_btn, 0, Qt.AlignVCenter)
        bl.addLayout(bhead)
        self.bl_scroll = QScrollArea()
        self.bl_scroll.setWidgetResizable(True)
        self.bl_scroll.setFixedHeight(140)
        self.bl_scroll.setFrameShape(QFrame.NoFrame)
        self.bl_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollArea>QWidget>QWidget{background:transparent;}")
        self.bl_host = QWidget()
        self.bl_list = QVBoxLayout(self.bl_host)
        self.bl_list.setContentsMargins(0, 0, 0, 0)
        self.bl_list.setSpacing(6)
        self.bl_scroll.setWidget(self.bl_host)
        bl.addWidget(self.bl_scroll)
        host_lay.addWidget(bc)

        note = QFrame()
        note.setObjectName("CardSoft")
        nl = QHBoxLayout(note)
        nl.setContentsMargins(12, 9, 12, 9)
        ni = QLabel()
        ni.setFixedSize(18, 18)
        ni.setPixmap(icons.colored_svg("triangle-alert", WARNING, 16))
        nl.addWidget(ni, 0, Qt.AlignTop)
        nt = label("安全边界：本工具不会修改安全模式、Ctrl+Alt+Delete、登录策略或系统内核；"
                   "这些抗恢复手段可能把电脑永久锁死，因此不提供。请保留密码并牢记卸载方式。", "Tiny")
        nt.setWordWrap(True)
        nl.addWidget(nt, 1)
        host_lay.addWidget(note)
        host_lay.addStretch(1)

        foot = QHBoxLayout()
        foot.addWidget(label("ETC NetGuard · by etc", "Tiny"))
        foot.addStretch(1)
        done = QPushButton("完成")
        done.setObjectName("Primary")
        done.setFixedHeight(38)
        done.setMinimumWidth(108)
        done.clicked.connect(self.accept)
        foot.addWidget(done)
        self.content.addLayout(foot)

        self._refresh()

    def _toggle_row(self, key: str, title: str, desc: str) -> QFrame:
        row = QFrame()
        row.setObjectName("CardSoft")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 9, 12, 9)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(title, "H3"))
        d = label(desc, "Tiny")
        d.setWordWrap(True)
        col.addWidget(d)
        lay.addLayout(col, 1)
        sw = ToggleSwitch(checked=bool(getattr(self.state, key)))
        sw.toggled.connect(lambda checked, k=key: self._set_restriction(k, checked))
        lay.addWidget(sw, 0, Qt.AlignVCenter)
        self.toggles[key] = sw
        return row

    def _set_restriction(self, key: str, checked: bool):
        self.state.set_restriction(key, checked)
        self.main.sync_guard()
        self.main._update_status()

    def _refresh(self):
        if self.state.password_enabled:
            self.pw_desc.setText("已启用 · 退出、打开托盘窗口与移除黑名单均需验证")
            self.pw_btn.setText("修改密码")
        else:
            self.pw_desc.setText("未启用 · 点击右侧设置一个关闭密码")
            self.pw_btn.setText("设置密码")
        self.bl_count.setText(f"{len(self.state.blacklist)} 个")
        self._rebuild_blacklist()

    def _edit_password(self):
        dlg = PasswordSetupDialog(self, self.state, start_enabled=True)
        if dlg.exec_() == dlg.Accepted:
            self.main.apply_security()
            self._refresh()

    def _clear_blacklist_rows(self):
        while self.bl_list.count():
            item = self.bl_list.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _rebuild_blacklist(self):
        self._clear_blacklist_rows()
        if not self.state.blacklist:
            empty = label("还没有黑名单程序。点击右上角「添加程序」选择 .exe。", "Muted")
            empty.setAlignment(Qt.AlignCenter)
            empty.setMinimumHeight(120)
            self.bl_list.addWidget(empty)
            return
        for item in self.state.blacklist:
            row = QFrame()
            row.setObjectName("CardSoft")
            row.setFixedHeight(48)
            row.setContextMenuPolicy(Qt.CustomContextMenu)
            row.customContextMenuRequested.connect(
                lambda pos, p=item["path"], n=item["name"], r=row: self._row_menu(p, n, r, pos)
            )
            lay = QHBoxLayout(row)
            lay.setContentsMargins(8, 5, 8, 5)
            lay.setSpacing(8)
            ic = QLabel()
            ic.setFixedSize(28, 28)
            ic.setPixmap(self._icon_for(item["path"], item["name"]))
            ic.setAlignment(Qt.AlignCenter)
            lay.addWidget(ic)
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(item["name"], "H3"))
            pth = label(item["path"], "Tiny")
            pth.setMaximumWidth(520)
            col.addWidget(pth)
            lay.addLayout(col, 1)
            rm = QPushButton()
            rm.setObjectName("Icon")
            rm.setFixedSize(28, 28)
            rm.setIcon(icons.svg_icon("trash-2", MUTED, 14))
            rm.setToolTip("移出黑名单（需要密码）")
            rm.clicked.connect(lambda _=False, p=item["path"]: self._remove_blacklist(p))
            lay.addWidget(rm)
            self.bl_list.addWidget(row)
        self.bl_list.addStretch(1)

    def _icon_for(self, path: str, name: str) -> QPixmap:
        if path and not backend.PREVIEW:
            ic = self._icons.icon(QFileInfo(path))
            if not ic.isNull():
                return ic.pixmap(28, 28)
        return icons.letter_pixmap(name, 22)

    def _add_blacklist(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择要禁止运行的程序", "", "程序 (*.exe)")
        if not path:
            return
        name = os.path.basename(path)
        if is_protected(name, path):
            self.main.toast.show_message("系统关键进程不能加入黑名单。", "error")
            return
        if not self.state.add_blacklist(path, name):
            self.main.toast.show_message("这个程序已经在黑名单里了。", "info")
            return
        self.main.sync_guard()
        self._refresh()
        self.main.toast.show_message(f"已加入黑名单：{name}", "ok")

    def _remove_blacklist(self, path: str):
        name = os.path.basename(path)
        if self.state.password_enabled and not PasswordDialog.ask(
                self, self.state, "移出黑名单", f"移出 {name} 需要关闭密码。"):
            return
        self.state.remove_blacklist(path)
        self.main.sync_guard()
        self._refresh()
        self.main.toast.show_message(f"已移出黑名单：{name}", "ok")

    def _row_menu(self, path: str, name: str, row: QWidget, pos):
        menu = QMenu(self)
        act = menu.addAction("移出黑名单")
        act.triggered.connect(lambda: self._remove_blacklist(path))
        menu.exec_(row.mapToGlobal(pos))
