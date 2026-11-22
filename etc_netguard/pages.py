# -*- coding: utf-8 -*-
"""Main pages: processes, bandwidth & block, blocked sites, settings."""
from __future__ import annotations

from PyQt5.QtCore import QFileInfo, QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QButtonGroup,
    QFileIconProvider,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import backend, icons
from .dialogs import AddSiteDialog, ConfirmDialog
from .theme import (
    ACCENT,
    ACCENT_2,
    BORDER,
    CARD_SOFT,
    DANGER,
    MUTED,
    MUTED_DIM,
    TEXT,
    TEXT_DIM,
    WARNING,
)
from .widgets import (
    Chip,
    EmptyState,
    Page,
    ProcessTable,
    StatCard,
    ToggleSwitch,
    hline,
    label,
)


def card_frame() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(12)
    return f, lay


def icon_tile(name: str, color: str = ACCENT, size: int = 42) -> QLabel:
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


def tiny_dot(color: str = ACCENT) -> QLabel:
    d = QLabel()
    d.setFixedSize(8, 8)
    d.setStyleSheet(f"background:{color}; border-radius:4px;")
    return d


class HomePage(Page):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.state = main.state
        self._rows: list[dict] = []
        self._signature = None
        self._rebuilding = False
        self._icon_cache: dict[str, QIcon] = {}
        self._icons = QFileIconProvider()
        self._build()
        self.update_stats()

    # ------------------------------------------------------------------
    def _build(self):
        head = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_col.addWidget(label("进程管理", "PageTitle"))
        title_col.addWidget(label("扫描系统中正在运行的程序，勾选后即可限速或断开网络。", "PageSub"))
        head.addLayout(title_col, 1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索进程 / PID / 路径")
        self.search.setFixedSize(272, 40)
        self.search.setClearButtonEnabled(True)
        act = QAction(icons.svg_icon("search", MUTED, 16), "", self.search)
        self.search.addAction(act, QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._on_search)
        head.addWidget(self.search, 0, Qt.AlignVCenter)

        refresh = QPushButton()
        refresh.setObjectName("Icon")
        refresh.setFixedSize(40, 40)
        refresh.setIcon(icons.svg_icon("refresh-cw", MUTED, 18))
        refresh.setToolTip("立即重新扫描")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.clicked.connect(lambda: self.main.refresh_processes(force=True))
        head.addWidget(refresh, 0, Qt.AlignVCenter)
        self.body_layout.addLayout(head)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.stat_total = StatCard("运行中的进程", "monitor", ACCENT_2)
        self.stat_selected = StatCard("已选择", "check", ACCENT)
        self.stat_limit = StatCard("限速中", "gauge", "#FFC46B")
        self.stat_block = StatCard("已断网", "wifi-off", DANGER)
        for c in (self.stat_total, self.stat_selected, self.stat_limit, self.stat_block):
            stats.addWidget(c, 1)
        self.body_layout.addLayout(stats)

        card, lay = card_frame()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        top = QHBoxLayout()
        top.setContentsMargins(20, 16, 18, 10)
        top.setSpacing(10)
        top.addWidget(label("进程列表", "H2"))
        self.count_chip = QLabel("共 0 个进程")
        self.count_chip.setObjectName("Pill")
        top.addWidget(self.count_chip)
        top.addStretch(1)
        auto = QHBoxLayout()
        auto.setSpacing(6)
        auto.addWidget(tiny_dot(ACCENT))
        auto.addWidget(label(f"自动刷新 · 每 {self.state.refresh_sec} 秒", "Tiny"))
        top.addLayout(auto)
        self.select_all_btn = QPushButton("全选当前结果")
        self.select_all_btn.setObjectName("Link")
        self.select_all_btn.setCursor(Qt.PointingHandCursor)
        self.select_all_btn.clicked.connect(self._toggle_select_all)
        top.addWidget(self.select_all_btn)
        lay.addLayout(top)

        self.table = ProcessTable()
        self.table.itemChanged.connect(self._on_item_changed)
        self.empty_search = EmptyState("search", "没有匹配的进程", "换个关键词，或清空搜索框再试。")
        self.empty_none = EmptyState("monitor", "没有检测到进程", "点击右上角刷新按钮重新扫描系统进程。")
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty_search)
        self.stack.addWidget(self.empty_none)
        lay.addWidget(self.stack, 1)

        lay.addWidget(hline())
        foot = QHBoxLayout()
        foot.setContentsMargins(20, 10, 18, 12)
        foot.setSpacing(10)
        self.sel_label = label("已选择 0 个进程", "Muted")
        foot.addWidget(self.sel_label)
        clear = QPushButton("清空选择")
        clear.setObjectName("Link")
        clear.setCursor(Qt.PointingHandCursor)
        clear.clicked.connect(self._clear_selection)
        foot.addWidget(clear)
        foot.addStretch(1)
        self.clear_rules_btn = QPushButton("解除限制")
        self.clear_rules_btn.setObjectName("Ghost")
        self.clear_rules_btn.setFixedHeight(38)
        self.clear_rules_btn.clicked.connect(self.main.clear_rules_selected)
        foot.addWidget(self.clear_rules_btn)
        self.block_btn = QPushButton("禁止联网")
        self.block_btn.setObjectName("DangerGhost")
        self.block_btn.setFixedHeight(38)
        self.block_btn.setIcon(icons.svg_icon("wifi-off", "#FF9AA5", 16))
        self.block_btn.clicked.connect(self.main.block_selected)
        foot.addWidget(self.block_btn)
        self.limit_btn = QPushButton("限制网速")
        self.limit_btn.setObjectName("Primary")
        self.limit_btn.setFixedHeight(38)
        self.limit_btn.setIcon(icons.svg_icon("gauge", "#04211B", 16))
        self.limit_btn.clicked.connect(self.main.go_limit)
        foot.addWidget(self.limit_btn)
        lay.addLayout(foot)
        self.body_layout.addWidget(card, 1)
        self.table.setMouseTracking(True)

    # ------------------------------------------------------------------
    def icon_for(self, row: dict) -> QIcon:
        path = row.get("path", "")
        name = row.get("name", "app.exe")
        if path and not backend.PREVIEW:
            key = path.lower()
            if key in self._icon_cache:
                return self._icon_cache[key]
            try:
                ic = self._icons.icon(QFileInfo(path))
            except Exception:
                ic = QIcon()
            if not ic.isNull():
                if len(self._icon_cache) < 800:
                    self._icon_cache[key] = ic
                return ic
        return QIcon(icons.letter_pixmap(name, 26))

    def key_for(self, row: dict) -> str:
        return self.state.process_key(row)

    def _status_text(self, row: dict) -> tuple[str, str]:
        lim = self.state.limit_for(row.get("path", ""))
        blk = self.state.block_for(row.get("path", ""))
        if blk:
            return "已断网", DANGER
        if lim:
            return "限速 " + backend.format_rate(lim["rate_bps"]), "#FFC46B"
        return "正常", MUTED

    def set_processes(self, rows: list[dict]):
        self._rows = rows
        sig = tuple((r["pid"], r.get("path", ""), r.get("name", "")) for r in rows)
        if sig == self._signature:
            self._refresh_status_cells()
            self.update_stats()
            return
        self._signature = sig
        scroll = self.table.verticalScrollBar().value()
        self._rebuilding = True
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            key = self.key_for(row)

            name_item = QTableWidgetItem(row.get("name") or "unknown")
            name_item.setIcon(self.icon_for(row))
            name_item.setData(Qt.UserRole, key)
            name_item.setToolTip(row.get("path") or "无法读取路径的系统进程")
            if self.state.is_selectable(row):
                name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                name_item.setCheckState(Qt.Checked if key in self.state.selected else Qt.Unchecked)
            else:
                name_item.setFlags(Qt.ItemIsEnabled)
                name_item.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, name_item)

            pid_item = QTableWidgetItem(str(row["pid"]))
            pids = row.get("pids") or [row.get("pid")]
            if len(pids) > 1:
                pid_item.setToolTip(f"{len(pids)} 个实例 · PID " + "、".join(str(x) for x in pids))
            pid_item.setForeground(QBrush(QColor(MUTED)))
            pid_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.table.setItem(i, 1, pid_item)

            st_item = QTableWidgetItem("")
            txt, color = self._status_text(row)
            st_item.setText(txt)
            st_item.setForeground(QBrush(QColor(color)))
            f = st_item.font()
            f.setWeight(QFont.DemiBold if txt != "正常" else QFont.Normal)
            st_item.setFont(f)
            st_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.table.setItem(i, 2, st_item)

            path_item = QTableWidgetItem(row.get("path") or "系统保护进程")
            path_item.setForeground(QBrush(QColor(MUTED_DIM)))
            path_item.setToolTip(row.get("path") or "")
            path_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.table.setItem(i, 3, path_item)
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        self._rebuilding = False
        self._apply_filter()
        self.table.verticalScrollBar().setValue(scroll)
        self.update_stats()

    def _refresh_status_cells(self):
        for i, row in enumerate(self._rows):
            txt, color = self._status_text(row)
            item = self.table.item(i, 2)
            if item:
                item.setText(txt)
                item.setForeground(QBrush(QColor(color)))
                f = item.font()
                f.setWeight(QFont.DemiBold if txt != "正常" else QFont.Normal)
                item.setFont(f)

    # ------------------------------------------------------------------
    def _on_item_changed(self, item):
        if self._rebuilding or item.column() != 0:
            return
        row = item.row()
        if row < 0 or row >= len(self._rows):
            return
        data = self._rows[row]
        checked = item.checkState() == Qt.Checked
        if checked and not self.state.is_selectable(data):
            self._rebuilding = True
            item.setCheckState(Qt.Unchecked)
            self._rebuilding = False
            self.main.toast("系统保护进程没有可访问的可执行路径，无法应用规则。", "warn")
            return
        self.state.toggle(data, checked)
        self.update_stats()
        self.main.on_selection_changed()

    def _clear_selection(self):
        self.state.clear_selection()
        self._sync_checks()
        self.update_stats()
        self.main.on_selection_changed()

    def _sync_checks(self):
        self._rebuilding = True
        self.table.blockSignals(True)
        for i, row in enumerate(self._rows):
            item = self.table.item(i, 0)
            if not item or not (item.flags() & Qt.ItemIsUserCheckable):
                continue
            item.setCheckState(Qt.Checked if self.key_for(row) in self.state.selected else Qt.Unchecked)
        self.table.blockSignals(False)
        self._rebuilding = False

    def _visible_rows(self) -> list[dict]:
        q = self.search.text().strip().lower()
        out = []
        for r in self._rows:
            hay = f"{r.get('name','')} {r.get('pid','')} {r.get('path','')}".lower()
            if not q or q in hay:
                out.append(r)
        return out

    def _toggle_select_all(self):
        vis = self._visible_rows()
        keys = {self.key_for(r) for r in vis if self.state.is_selectable(r)}
        all_on = bool(keys) and all(k in self.state.selected for k in keys)
        self.state.set_selected(keys, not all_on)
        self._sync_checks()
        self.update_stats()
        self.main.on_selection_changed()

    def _apply_filter(self):
        q = self.search.text().strip().lower()
        visible = 0
        for i, r in enumerate(self._rows):
            hay = f"{r.get('name','')} {r.get('pid','')} {r.get('path','')}".lower()
            show = (not q) or q in hay
            self.table.setRowHidden(i, not show)
            if show:
                visible += 1
        if not self._rows:
            self.stack.setCurrentWidget(self.empty_none)
        elif visible == 0:
            self.stack.setCurrentWidget(self.empty_search)
        else:
            self.stack.setCurrentWidget(self.table)
        self.count_chip.setText(f"共 {len(self._rows)} 个进程" if not q else f"{visible} / {len(self._rows)} 个进程")

    def _on_search(self, _):
        self._apply_filter()

    def update_stats(self):
        n = len(self._rows)
        sel = self.state.selected_count()
        self.stat_total.set_value(str(n))
        self.stat_selected.set_value(str(sel))
        self.stat_limit.set_value(str(len(self.state.limits)))
        self.stat_block.set_value(str(len(self.state.blocks)))
        self.sel_label.setText(f"已选择 {sel} 个进程")
        enabled = sel > 0
        for b in (self.limit_btn, self.block_btn, self.clear_rules_btn):
            b.setEnabled(enabled)

    def refresh_view(self):
        self._sync_checks()
        self._refresh_status_cells()
        self.update_stats()


class LimitPage(Page):
    PRESETS = [("20 KB/s", 20), ("50 KB/s", 50), ("100 KB/s", 100), ("300 KB/s", 300),
               ("500 KB/s", 500), ("1 MB/s", 1024), ("2 MB/s", 2048), ("5 MB/s", 5120)]

    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.state = main.state
        self.rate_bps = 102400
        self._build()
        self.refresh_view()

    def _build(self):
        head = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_col.addWidget(label("限速与断网", "PageTitle"))
        title_col.addWidget(label("按你勾选的程序，限制它的网络速度，或完全切断它的网络。", "PageSub"))
        head.addLayout(title_col, 1)
        self.scope_pill = QLabel("未选择进程")
        self.scope_pill.setObjectName("Pill")
        head.addWidget(self.scope_pill, 0, Qt.AlignVCenter)
        self.body_layout.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollArea>QWidget>QWidget{background:transparent;}")
        self.inner = QWidget()
        self.inner_lay = QVBoxLayout(self.inner)
        self.inner_lay.setContentsMargins(0, 0, 4, 2)
        self.inner_lay.setSpacing(10)
        self.scroll.setWidget(self.inner)
        self.body_layout.addWidget(self.scroll, 1)
        lay = self.inner_lay

        # selected scope
        scope_card, scope_lay = card_frame()
        scope_lay.setContentsMargins(16, 8, 16, 8)
        scope_lay.setSpacing(4)
        row = QHBoxLayout()
        row.addWidget(label("作用范围", "H3"))
        self.scope_count = label("0 个进程", "Tiny")
        row.addWidget(self.scope_count)
        row.addStretch(1)
        go = QPushButton("去首页选择")
        go.setObjectName("Link")
        go.setCursor(Qt.PointingHandCursor)
        go.clicked.connect(self.main.go_home)
        row.addWidget(go)
        scope_lay.addLayout(row)
        self.chip_scroll = QScrollArea()
        self.chip_scroll.setFixedHeight(26)
        self.chip_scroll.setWidgetResizable(True)
        self.chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chip_scroll.setStyleSheet("background: transparent; border: none;")
        self.chip_host = QWidget()
        self.chip_lay = QHBoxLayout(self.chip_host)
        self.chip_lay.setContentsMargins(0, 0, 0, 0)
        self.chip_lay.setSpacing(8)
        self.chip_lay.addStretch(1)
        self.chip_scroll.setWidget(self.chip_host)
        scope_lay.addWidget(self.chip_scroll)
        scope_card.setFixedHeight(68)
        lay.addWidget(scope_card)

        mid = QHBoxLayout()
        mid.setSpacing(12)

        # rate card
        rate_card, rate_lay = card_frame()
        rate_lay.setContentsMargins(15, 13, 15, 13)
        rate_lay.setSpacing(6)
        rhead = QHBoxLayout()
        rhead.setSpacing(12)
        rhead.addWidget(icon_tile("gauge", ACCENT, 36))
        rcol = QVBoxLayout()
        rcol.setSpacing(2)
        rcol.addWidget(label("限制网速", "H2"))
        rcol.addWidget(label("对所选程序的出站流量限速", "Muted"))
        rhead.addLayout(rcol, 1)
        self.rate_switch = ToggleSwitch()
        self.rate_switch.toggled.connect(self._on_rate_switch)
        rhead.addWidget(self.rate_switch, 0, Qt.AlignVCenter)
        rate_lay.addLayout(rhead)
        rate_lay.addSpacing(2)
        rate_lay.addWidget(label("限速档位", "Tiny"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.preset_group = QButtonGroup(self)
        self.preset_group.setExclusive(False)
        self.preset_buttons = []
        for i, (text, kb) in enumerate(self.PRESETS):
            b = QPushButton(text)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setFixedHeight(30)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=kb: self._select_preset(v))
            grid.addWidget(b, i // 4, i % 4)
            self.preset_group.addButton(b)
            self.preset_buttons.append((b, kb))
        rate_lay.addLayout(grid)
        custom = QHBoxLayout()
        custom.setSpacing(8)
        custom.addWidget(label("自定义", "Tiny"))
        self.spin = QSpinBox()
        self.spin.setRange(1, 1024 * 1024)
        self.spin.setValue(100)
        self.spin.setSuffix(" KB/s")
        self.spin.setFixedHeight(30)
        self.spin.setFixedWidth(128)
        self.spin.valueChanged.connect(self._on_custom)
        custom.addWidget(self.spin)
        custom.addStretch(1)
        rate_lay.addLayout(custom)
        rate_lay.addStretch(1)
        self.rate_apply = QPushButton("应用到所选进程")
        self.rate_apply.setObjectName("Primary")
        self.rate_apply.setFixedHeight(38)
        self.rate_apply.setIcon(icons.svg_icon("gauge", "#04211B", 17))
        self.rate_apply.clicked.connect(self._apply_rate)
        rate_lay.addWidget(self.rate_apply)
        rate_lay.addWidget(label("策略 QoS · 关闭开关即解除 · 重启后规则仍保留", "Tiny"))
        rate_card.setFixedHeight(300)

        # block card
        block_card, block_lay = card_frame()
        block_lay.setContentsMargins(15, 13, 15, 13)
        block_lay.setSpacing(6)
        bhead = QHBoxLayout()
        bhead.setSpacing(12)
        bhead.addWidget(icon_tile("shield-check", DANGER, 36))
        bcol = QVBoxLayout()
        bcol.setSpacing(2)
        bcol.addWidget(label("完全断网", "H2"))
        bcol.addWidget(label("阻断该程序的入站与出站连接", "Muted"))
        bhead.addLayout(bcol, 1)
        self.block_switch = ToggleSwitch(accent=DANGER)
        self.block_switch.toggled.connect(self._on_block_switch)
        bhead.addWidget(self.block_switch, 0, Qt.AlignVCenter)
        block_lay.addLayout(bhead)
        block_lay.addSpacing(8)
        box = QFrame()
        box.setObjectName("CardSoft")
        box.setMinimumHeight(72)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(14, 12, 14, 12)
        bl.setSpacing(6)
        bl.addWidget(label("双向阻断", "H3"))
        bl.addWidget(label("Windows 防火墙规则会同时拦截下载与上传，\n程序将完全无法连接网络。", "Muted"))
        block_lay.addWidget(box)
        block_lay.addStretch(1)
        self.block_apply = QPushButton("立即阻断所选进程")
        self.block_apply.setObjectName("DangerPrimary")
        self.block_apply.setFixedHeight(38)
        self.block_apply.setIcon(icons.svg_icon("wifi-off", "#28060B", 17))
        self.block_apply.clicked.connect(self._apply_block)
        block_lay.addWidget(self.block_apply)
        block_lay.addWidget(label("立即生效 · 关闭开关即恢复联网", "Tiny"))
        block_card.setFixedHeight(300)

        mid.addWidget(rate_card, 3)
        mid.addWidget(block_card, 2)
        lay.addLayout(mid)

        # active rules
        rules_card, rules_lay = card_frame()
        rules_lay.setContentsMargins(18, 10, 18, 8)
        top = QHBoxLayout()
        top.addWidget(label("生效中的规则", "H2"))
        self.rules_count = QLabel("0 条")
        self.rules_count.setObjectName("Pill")
        top.addWidget(self.rules_count)
        top.addStretch(1)
        self.clear_all_btn = QPushButton("全部解除")
        self.clear_all_btn.setObjectName("Link")
        self.clear_all_btn.setCursor(Qt.PointingHandCursor)
        self.clear_all_btn.clicked.connect(self._confirm_clear_all)
        top.addWidget(self.clear_all_btn)
        rules_lay.addLayout(top)
        self.rules_scroll = QScrollArea()
        self.rules_scroll.setWidgetResizable(True)
        self.rules_scroll.setStyleSheet("background: transparent; border:none;")
        self.rules_host = QWidget()
        self.rules_list = QVBoxLayout(self.rules_host)
        self.rules_list.setContentsMargins(0, 0, 0, 0)
        self.rules_list.setSpacing(6)
        self.rules_list.addStretch(1)
        self.rules_scroll.setWidget(self.rules_host)
        rules_lay.addWidget(self.rules_scroll, 1)
        self.empty_rules = label("还没有任何规则。选中进程后，打开上方的开关即可生效。", "Muted")
        self.empty_rules.setAlignment(Qt.AlignCenter)
        rules_lay.addWidget(self.empty_rules)
        rules_card.setMinimumHeight(190)
        lay.addWidget(rules_card, 1)

    # -- chips ---------------------------------------------------------
    def _rebuild_chips(self):
        while self.chip_lay.count():
            item = self.chip_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        items = self.state.selected_items()
        if not items:
            hint = label("尚未选择进程 —— 去首页勾选要限速的程序", "Muted")
            self.chip_lay.addWidget(hint)
        else:
            for it in items[:24]:
                ch = Chip(it["name"], data=it["path"])
                ch.closed.connect(self._remove_from_selection)
                self.chip_lay.addWidget(ch)
            if len(items) > 24:
                self.chip_lay.addWidget(label(f"+{len(items) - 24}", "Tiny"))
        self.chip_lay.addStretch(1)
        self.scope_count.setText(f"{len(items)} 个进程")
        self.scope_pill.setText(f"作用于 {len(items)} 个进程" if items else "未选择进程")

    def _remove_from_selection(self, path: str):
        key = backend.norm_path(path)
        self.state.selected.discard(key)
        self.state.selected_meta.pop(key, None)
        self.main.on_selection_changed()

    # -- rate ----------------------------------------------------------
    def _select_preset(self, kb: int):
        self.spin.blockSignals(True)
        self.spin.setValue(kb)
        self.spin.blockSignals(False)
        for b, v in self.preset_buttons:
            b.setChecked(v == kb)
        self.rate_bps = kb * 1024

    def _on_custom(self, value: int):
        for b, _ in self.preset_buttons:
            b.setChecked(False)
        self.rate_bps = max(1, value) * 1024

    def _sync_presets(self):
        match = None
        for b, kb in self.preset_buttons:
            if self.rate_bps == kb * 1024:
                match = b
            b.setChecked(self.rate_bps == kb * 1024)
        if match is None and self.spin.value() != int(self.rate_bps / 1024):
            self.spin.blockSignals(True)
            self.spin.setValue(max(1, int(self.rate_bps / 1024)))
            self.spin.blockSignals(False)

    def _apply_rate(self):
        items = self.state.selected_items()
        if not items:
            self.main.toast("请先在首页勾选需要限速的进程", "warn")
            return
        self.main.apply_limit(items, self.rate_bps)

    def _on_rate_switch(self, checked: bool):
        items = self.state.selected_items()
        if not items:
            self.rate_switch.setChecked(False)
            self.main.toast("请先在首页勾选需要限速的进程", "warn")
            return
        if checked:
            self.main.apply_limit(items, self.rate_bps)
        else:
            self.main.remove_limit(items)

    # -- block ---------------------------------------------------------
    def _apply_block(self):
        items = self.state.selected_items()
        if not items:
            self.main.toast("请先在首页勾选需要断网的进程", "warn")
            return
        self.main.apply_block(items)

    def _on_block_switch(self, checked: bool):
        items = self.state.selected_items()
        if not items:
            self.block_switch.setChecked(False)
            self.main.toast("请先在首页勾选需要断网的进程", "warn")
            return
        if checked:
            self.main.apply_block(items)
        else:
            self.main.remove_block(items)

    # -- active rules --------------------------------------------------
    def _confirm_clear_all(self):
        if not self.state.limits and not self.state.blocks:
            self.main.toast("当前没有生效中的规则", "info")
            return
        dlg = ConfirmDialog("解除全部规则？", "将移除所有限速与断网规则，并由系统恢复网络。", "全部解除", True, self.main)
        if dlg.exec_() == dlg.Accepted:
            self.main.clear_all_rules()

    def _rebuild_rules(self):
        while self.rules_list.count():
            item = self.rules_list.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        rows = self.state.all_rule_rows()
        self.rules_count.setText(f"{len(rows)} 条")
        self.empty_rules.setVisible(not rows)
        self.rules_scroll.setVisible(bool(rows))
        for r in rows:
            row = QFrame()
            row.setObjectName("CardSoft")
            row.setFixedHeight(44)
            lay = QHBoxLayout(row)
            lay.setContentsMargins(10, 5, 8, 5)
            lay.setSpacing(8)
            ic = QLabel()
            ic.setFixedSize(26, 26)
            ic.setPixmap(icons.letter_pixmap(r["name"], 20))
            ic.setAlignment(Qt.AlignCenter)
            lay.addWidget(ic)
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(label(r["name"], "H3"))
            p = label(r["path"], "Tiny")
            p.setMaximumWidth(460)
            f = p.font()
            f.setPixelSize(10)
            p.setFont(f)
            col.addWidget(p)
            lay.addLayout(col, 1)
            badge = QLabel(("限速 " + r["detail"]) if r["kind"] == "limit" else "已断网")
            badge.setStyleSheet(
                "background: rgba(255,196,107,20); color:#FFC46B; border:1px solid rgba(255,196,107,50);"
                "border-radius:7px; padding:2px 8px; font-size:10px; font-weight:600;"
                if r["kind"] == "limit" else
                "background: rgba(255,111,125,18); color:#FF9AA5; border:1px solid rgba(255,111,125,50);"
                "border-radius:7px; padding:2px 8px; font-size:10px; font-weight:600;"
            )
            lay.addWidget(badge)
            rm = QPushButton()
            rm.setObjectName("Icon")
            rm.setFixedSize(26, 26)
            rm.setIcon(icons.svg_icon("x", MUTED, 14))
            rm.setCursor(Qt.PointingHandCursor)
            rm.setToolTip("移除这条规则")
            rm.clicked.connect(lambda _=False, kind=r["kind"], path=r["path"]: self.main.remove_rule(kind, path))
            lay.addWidget(rm)
            self.rules_list.addWidget(row)
        self.rules_list.addStretch(1)

    def refresh_view(self):
        self._rebuild_chips()
        items = self.state.selected_items()
        any_limit = bool(items) and all(self.state.limit_for(x["path"]) for x in items)
        any_block = bool(items) and all(self.state.block_for(x["path"]) for x in items)
        self.rate_switch.setChecked(any_limit, animate=False)
        self.block_switch.setChecked(any_block, animate=False)
        self._rebuild_rules()
        self._sync_presets()
        has = bool(items)
        self.rate_apply.setEnabled(has)
        self.block_apply.setEnabled(has)


class SitesPage(Page):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.state = main.state
        self._build()
        self.refresh_view()

    def _build(self):
        head = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_col.addWidget(label("网站禁用", "PageTitle"))
        title_col.addWidget(label("添加网址后，访问它就会命中本机 404 拦截页。", "PageSub"))
        head.addLayout(title_col, 1)
        add = QPushButton("添加网站")
        add.setObjectName("Primary")
        add.setFixedHeight(40)
        add.setIcon(icons.svg_icon("plus", "#04211B", 16))
        add.clicked.connect(self._add_site)
        head.addWidget(add, 0, Qt.AlignVCenter)
        self.body_layout.addLayout(head)

        master, mlay = card_frame()
        mlay.setContentsMargins(20, 16, 20, 16)
        row = QHBoxLayout()
        row.setSpacing(14)
        self.master_icon = icon_tile("globe", ACCENT_2)
        row.addWidget(self.master_icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("网站访问拦截", "H2"))
        self.master_sub = label("尚未启用", "Muted")
        col.addWidget(self.master_sub)
        row.addLayout(col, 1)
        self.status_dot = tiny_dot(ACCENT)
        row.addWidget(self.status_dot)
        self.status_label = label("服务未启动", "Tiny")
        row.addWidget(self.status_label)
        self.master_switch = ToggleSwitch()
        self.master_switch.toggled.connect(self._on_master)
        row.addWidget(self.master_switch)
        mlay.addLayout(row)
        self.body_layout.addWidget(master)

        note = QFrame()
        note.setObjectName("CardSoft")
        nl = QHBoxLayout(note)
        nl.setContentsMargins(14, 10, 14, 10)
        nl.setSpacing(10)
        ni = QLabel()
        ni.setPixmap(icons.colored_svg("shield-check", ACCENT, 16))
        nl.addWidget(ni)
        text = label("HTTP 访问会返回自绘的 404 拦截页；HTTPS 站点会被直接阻断。应用关闭后拦截规则仍然保留。", "Tiny")
        text.setWordWrap(True)
        nl.addWidget(text, 1)
        self.body_layout.addWidget(note)

        list_card, llist = card_frame()
        llist.setContentsMargins(20, 16, 20, 12)
        top = QHBoxLayout()
        top.addWidget(label("被禁用的网站", "H2"))
        self.site_count = QLabel("0 个")
        self.site_count.setObjectName("Pill")
        top.addWidget(self.site_count)
        top.addStretch(1)
        top.addWidget(label("命中即返回 404", "Tiny"))
        llist.addLayout(top)
        self.site_scroll = QScrollArea()
        self.site_scroll.setWidgetResizable(True)
        self.site_scroll.setStyleSheet("background: transparent; border:none;")
        self.host = QWidget()
        self.site_list = QVBoxLayout(self.host)
        self.site_list.setContentsMargins(0, 0, 0, 0)
        self.site_list.setSpacing(8)
        self.site_list.addStretch(1)
        self.site_scroll.setWidget(self.host)
        llist.addWidget(self.site_scroll, 1)
        self.empty = EmptyState("globe", "还没有被禁用的网站", "点击右上角「添加网站」，输入网址后保存。")
        llist.addWidget(self.empty, 1)
        self.body_layout.addWidget(list_card, 1)

    def _add_site(self):
        dlg = AddSiteDialog(self.main)
        if dlg.exec_() == dlg.Accepted:
            domain, name = dlg.data()
            self.main.add_site(domain, name)

    def _on_master(self, checked: bool):
        self.main.set_sites_enabled(checked)

    def _remove(self, domain: str):
        self.main.remove_site(domain)

    def refresh_view(self):
        self.master_switch.setChecked(self.state.sites_enabled, animate=False)
        n = len(self.state.sites)
        self.site_count.setText(f"{n} 个")
        active = self.state.sites_enabled and n > 0
        self.master_sub.setText(f"已启用 · {n} 个网站返回 404" if active else ("已关闭 · 规则暂不生效" if n else "尚未添加网站"))
        self.status_dot.setStyleSheet(f"background:{ACCENT if active else MUTED}; border-radius:4px;")
        self.status_label.setText("拦截服务运行中 · 127.0.0.1:80" if active else "服务未启动")
        self.status_label.setStyleSheet(f"color:{ACCENT if active else MUTED}; font-size:11px;")

        while self.site_list.count():
            item = self.site_list.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.empty.setVisible(n == 0)
        self.site_scroll.setVisible(n > 0)
        for s in self.state.sites:
            self.site_list.addWidget(self._site_row(s))
        self.site_list.addStretch(1)

    def _site_row(self, s: dict) -> QFrame:
        row = QFrame()
        row.setObjectName("CardSoft")
        row.setFixedHeight(64)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 9, 10, 9)
        lay.setSpacing(12)
        av = QLabel()
        av.setPixmap(icons.letter_pixmap(s.get("name") or s["domain"], 30))
        av.setFixedSize(40, 40)
        av.setAlignment(Qt.AlignCenter)
        lay.addWidget(av)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(s.get("name") or s["domain"], "H3"))
        dom = label(s["domain"], "Tiny")
        dom.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        col.addWidget(dom)
        lay.addLayout(col, 1)
        badge = QLabel("404")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(52, 26)
        badge.setStyleSheet(
            "background: rgba(255,111,125,16); color:#FF9AA5; border:1px solid rgba(255,111,125,45);"
            "border-radius:7px; font-size:11px; font-weight:700; letter-spacing:1px;"
        )
        lay.addWidget(badge)
        rm = QPushButton()
        rm.setObjectName("Icon")
        rm.setFixedSize(32, 32)
        rm.setIcon(icons.svg_icon("trash-2", MUTED, 15))
        rm.setToolTip("删除这条网站规则")
        rm.setCursor(Qt.PointingHandCursor)
        rm.clicked.connect(lambda _=False, d=s["domain"]: self._remove(d))
        lay.addWidget(rm)
        return row


class SettingsPage(Page):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.state = main.state
        self._build()

    def _build(self):
        head = QVBoxLayout()
        head.setSpacing(4)
        head.addWidget(label("设置与维护", "PageTitle"))
        head.addWidget(label("检查权限、修复规则，或重新观看引导。", "PageSub"))
        self.body_layout.addLayout(head)

        top = QHBoxLayout()
        top.setSpacing(14)
        status, sl = card_frame()
        sl.setContentsMargins(20, 18, 20, 18)
        sl.addWidget(label("运行状态", "H2"))
        self.admin_row = self._info_row("shield-check", "管理员权限", "检查中…")
        sl.addLayout(self.admin_row[0])
        self.version_row = self._info_row("sparkles", "版本", f"v{backend.APP_VERSION} · 桌面版")
        sl.addLayout(self.version_row[0])
        self.server_row = self._info_row("globe", "404 拦截服务", "未启动")
        sl.addLayout(self.server_row[0])
        sl.addStretch(1)
        data_btn = QPushButton("打开数据目录")
        data_btn.setObjectName("Ghost")
        data_btn.setFixedHeight(38)
        data_btn.setIcon(icons.svg_icon("folder-open", MUTED, 15))
        data_btn.clicked.connect(backend.open_data_dir)
        sl.addWidget(data_btn)

        about, al = card_frame()
        al.setContentsMargins(20, 18, 20, 18)
        al.addWidget(label("关于作者", "H2"))
        ar = QHBoxLayout()
        ar.setSpacing(12)
        av = QLabel()
        av.setPixmap(icons.app_pixmap(58))
        av.setFixedSize(58, 58)
        ar.addWidget(av)
        ac = QVBoxLayout()
        ac.setSpacing(2)
        ac.addWidget(label("etc", "H3"))
        ac.addWidget(label("ETC NetGuard 的作者 · 独立开发者", "Muted"))
        ar.addLayout(ac, 1)
        al.addLayout(ar)
        al.addWidget(label("开源、无广告、无账号。所有规则都只在本机执行。", "Tiny"))
        gh = QPushButton("查看开源仓库")
        gh.setObjectName("Ghost")
        gh.setFixedHeight(38)
        gh.setIcon(icons.svg_icon("github", TEXT, 16))
        gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(backend.REPO_URL)))
        al.addWidget(gh)
        top.addWidget(status, 3)
        top.addWidget(about, 2)
        self.body_layout.addLayout(top)

        maint, ml = card_frame()
        ml.setContentsMargins(20, 18, 20, 18)
        ml.addWidget(label("维护", "H2"))
        ml.addWidget(label("清除规则会立刻移除 QoS 限速、防火墙断网与 hosts 拦截，并停止本地 404 服务。", "Muted"))
        self.security_info = label("", "Tiny")
        ml.addWidget(self.security_info)
        row = QHBoxLayout()
        row.setSpacing(10)
        security = QPushButton("安全设置")
        security.setObjectName("Ghost")
        security.setFixedHeight(40)
        security.setIcon(icons.svg_icon("shield-check", MUTED, 16))
        security.clicked.connect(self.main.open_settings)
        row.addWidget(security)
        replay = QPushButton("重新观看新手引导")
        replay.setObjectName("Ghost")
        replay.setFixedHeight(40)
        replay.setIcon(icons.svg_icon("rotate-ccw", MUTED, 16))
        replay.clicked.connect(self.main.replay_onboarding)
        row.addWidget(replay)
        clear = QPushButton("清除全部规则")
        clear.setObjectName("DangerGhost")
        clear.setFixedHeight(40)
        clear.setIcon(icons.svg_icon("trash-2", "#FF9AA5", 16))
        clear.clicked.connect(self.main.clear_all_rules)
        row.addWidget(clear)
        row.addStretch(1)
        ml.addLayout(row)
        ml.addStretch(1)
        self.body_layout.addWidget(maint, 1)

        foot = QHBoxLayout()
        foot.addWidget(label("ETC NetGuard · by etc · 2026", "Tiny"))
        foot.addStretch(1)
        foot.addWidget(label("本地运行 · 不上传任何数据", "Tiny"))
        self.body_layout.addLayout(foot)

    def _info_row(self, icon_name: str, key: str, value: str):
        row = QHBoxLayout()
        row.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icons.colored_svg(icon_name, MUTED, 16))
        row.addWidget(ic)
        row.addWidget(label(key, "Muted"))
        row.addStretch(1)
        val = label(value, "H3")
        val.setStyleSheet(f"color:{TEXT}; font-size:13px;")
        row.addWidget(val)
        return row, val

    def refresh_view(self):
        admin = backend.is_admin()
        self.admin_row[1].setText("已授权" if admin else "受限")
        self.admin_row[1].setStyleSheet(f"color:{ACCENT if admin else DANGER}; font-size:13px; font-weight:600;")
        self.server_row[1].setText("运行中 · 127.0.0.1:80" if (self.state.sites_enabled and self.state.sites) else "未启动")
        n = self.state.restriction_count()
        bits = []
        bits.append("关闭密码已启用" if self.state.password_enabled else "关闭密码未设置")
        bits.append(f"{n} 项限制")
        bits.append(f"黑名单 {len(self.state.blacklist)} 个")
        self.security_info.setText(" · ".join(bits))
        self.server_row[1].setStyleSheet(f"color:{ACCENT if (self.state.sites_enabled and self.state.sites) else MUTED}; font-size:13px;")
