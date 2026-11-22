# -*- coding: utf-8 -*-
"""ETC NetGuard - visual language: deep space dark, mint accent, quiet motion."""
from __future__ import annotations

import os
from pathlib import Path

BG = "#070C11"
SHELL_TOP = "#0B141C"
SHELL_BOTTOM = "#070D13"
SIDEBAR = "#091119"
CARD = "#0F1A24"
CARD_SOFT = "#0C1620"
CARD_HOVER = "#14212D"
BORDER = "rgba(255, 255, 255, 17)"
BORDER_SOFT = "rgba(255, 255, 255, 9)"
TEXT = "#EAF2F8"
TEXT_DIM = "#A9BCCC"
MUTED = "#7F93A8"
MUTED_DIM = "#5C7186"
ACCENT = "#35E3C3"
ACCENT_2 = "#4E9BFF"
ACCENT_DARK = "#17BFA2"
DANGER = "#FF6F7D"
WARNING = "#FFC46B"
OK = "#5BE3A6"

FONT_STACK = '"Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif'


def asset_dir() -> Path:
    """Works both from source and from a PyInstaller one-file bundle."""
    import sys
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "assets"
        if p.exists():
            return p
    return Path(__file__).resolve().parent.parent / "assets"


def qss() -> str:
    check = (asset_dir() / "check.png").as_posix()
    return f"""
* {{
    font-family: {FONT_STACK};
    outline: none;
}}
QWidget {{
    color: {TEXT};
    font-size: 13px;
}}
QToolTip {{
    background: #14212C;
    color: {TEXT};
    border: 1px solid rgba(53, 227, 195, 70);
    border-radius: 8px;
    padding: 6px 9px;
}}
QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#CardSoft {{
    background: {CARD_SOFT};
    border: 1px solid {BORDER_SOFT};
    border-radius: 14px;
}}
QFrame#DialogPanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #12202B, stop:1 #0C151D);
    border: 1px solid rgba(255, 255, 255, 26);
    border-radius: 18px;
}}
QFrame#Plain {{
    background: transparent;
    border: none;
}}
QLabel {{
    background: transparent;
    color: {TEXT};
}}
QLabel#PageTitle {{
    font-size: 27px;
    font-weight: 700;
    letter-spacing: 0.2px;
}}
QLabel#PageSub {{
    color: {MUTED};
    font-size: 13px;
}}
QLabel#H2 {{
    font-size: 17px;
    font-weight: 600;
}}
QLabel#H3 {{
    font-size: 14px;
    font-weight: 600;
}}
QLabel#Muted {{
    color: {MUTED};
}}
QLabel#Tiny {{
    color: {MUTED_DIM};
    font-size: 11px;
}}
QLabel#Accent {{
    color: {ACCENT};
    font-weight: 600;
}}
QLabel#Danger {{
    color: {DANGER};
}}
QLabel#Pill {{
    background: rgba(53, 227, 195, 22);
    color: {ACCENT};
    border: 1px solid rgba(53, 227, 195, 55);
    border-radius: 9px;
    padding: 3px 9px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton {{
    font-size: 13px;
}}
QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #45F0D0, stop:1 #22C7AE);
    color: #03201A;
    font-weight: 700;
    border: none;
    border-radius: 11px;
    padding: 10px 18px;
}}
QPushButton#Primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5BFFDF, stop:1 #2FD5BA);
}}
QPushButton#Primary:pressed {{
    background: #1FB89D;
}}
QPushButton#Primary:disabled {{
    background: rgba(53, 227, 195, 40);
    color: rgba(234, 242, 248, 90);
}}
QPushButton#Ghost {{
    background: rgba(255, 255, 255, 9);
    color: {TEXT};
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 11px;
    padding: 9px 16px;
}}
QPushButton#Ghost:hover {{
    background: rgba(255, 255, 255, 16);
    border-color: rgba(255, 255, 255, 32);
}}
QPushButton#Ghost:pressed {{
    background: rgba(255, 255, 255, 7);
}}
QPushButton#DangerGhost {{
    background: rgba(255, 111, 125, 14);
    color: #FF9AA5;
    border: 1px solid rgba(255, 111, 125, 55);
    border-radius: 11px;
    padding: 9px 16px;
}}
QPushButton#DangerGhost:hover {{
    background: rgba(255, 111, 125, 24);
    border-color: rgba(255, 111, 125, 100);
}}
QPushButton#DangerPrimary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FF8B96, stop:1 #F0526A);
    color: #28060B;
    font-weight: 700;
    border: none;
    border-radius: 11px;
    padding: 10px 18px;
}}
QPushButton#DangerPrimary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFA2AC, stop:1 #FF657C);
}}
QPushButton#DangerPrimary:pressed {{
    background: #DE4258;
}}
QPushButton#DangerPrimary:disabled {{
    background: rgba(255, 111, 125, 40);
    color: rgba(234, 242, 248, 90);
}}
QPushButton#Chip {{
    background: rgba(255, 255, 255, 8);
    color: {TEXT_DIM};
    border: 1px solid rgba(255, 255, 255, 15);
    border-radius: 9px;
    padding: 7px 13px;
}}
QPushButton#Chip:hover {{
    border-color: rgba(53, 227, 195, 80);
    color: {TEXT};
}}
QPushButton#Chip:checked {{
    background: rgba(53, 227, 195, 22);
    color: {ACCENT};
    border: 1px solid rgba(53, 227, 195, 95);
}}
QPushButton#Icon {{
    background: rgba(255, 255, 255, 8);
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 10px;
    padding: 7px;
}}
QPushButton#Icon:hover {{
    background: rgba(255, 255, 255, 16);
    border-color: rgba(53, 227, 195, 70);
}}
QPushButton#Link {{
    background: transparent;
    border: none;
    color: {MUTED};
    padding: 4px 2px;
    text-align: left;
}}
QPushButton#Link:hover {{
    color: {ACCENT};
}}
QLineEdit {{
    background: #0A141C;
    color: {TEXT};
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 10px;
    padding: 9px 13px;
    selection-background-color: {ACCENT};
    selection-color: #042019;
}}
QLineEdit:hover {{
    border-color: rgba(255, 255, 255, 30);
}}
QLineEdit:focus {{
    border-color: rgba(53, 227, 195, 120);
    background: #0B1720;
}}
QLineEdit::placeholder {{
    color: {MUTED_DIM};
}}
QSpinBox {{
    background: #0A141C;
    color: {TEXT};
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 10px;
    padding: 8px 10px;
}}
QSpinBox:focus {{
    border-color: rgba(53, 227, 195, 110);
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 18px;
    background: rgba(255, 255, 255, 6);
    border: none;
}}
QTableWidget {{
    background: transparent;
    border: none;
    gridline-color: transparent;
    selection-background-color: transparent;
    selection-color: {TEXT};
    alternate-background-color: transparent;
}}
QTableWidget::item {{
    border-bottom: 1px solid rgba(255, 255, 255, 8);
    padding: 0px 6px;
    color: {TEXT};
}}
QTableWidget::item:hover {{
    background: rgba(255, 255, 255, 7);
}}
QTableWidget::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid rgba(255, 255, 255, 55);
    background: transparent;
}}
QTableWidget::indicator:hover {{
    border-color: {ACCENT};
    background: rgba(53, 227, 195, 18);
}}
QTableWidget::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    image: url("{check}");
}}
QHeaderView::section {{
    background: transparent;
    color: {MUTED_DIM};
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 12);
    padding: 9px 6px 9px 8px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
}}
QTableCornerButton::section {{
    background: transparent;
    border: none;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 3px 1px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 26);
    border-radius: 4px;
    min-height: 36px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(53, 227, 195, 80);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    height: 0px;
    background: transparent;
}}
QMenu {{
    background: #101B25;
    color: {TEXT};
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 16px;
    border-radius: 7px;
}}
QMenu::item:selected {{
    background: rgba(53, 227, 195, 24);
    color: {ACCENT};
}}
QDialog {{
    background: transparent;
}}
"""


def window_icon_path() -> str:
    return str(asset_dir() / "app.ico")


SHELL_QSS = f"""
QFrame#Sidebar {{
    background: rgba(255, 255, 255, 4);
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 10);
}}
QWidget#ContentArea {{
    background: transparent;
}}
QPushButton#WinBtn {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0px;
}}
QPushButton#WinBtn:hover {{
    background: rgba(255, 255, 255, 15);
}}
QPushButton#WinClose {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0px;
}}
QPushButton#WinClose:hover {{
    background: #D94850;
}}
QFrame#AdminCard {{
    background: rgba(53, 227, 195, 10);
    border: 1px solid rgba(53, 227, 195, 26);
    border-radius: 12px;
}}
QSizeGrip {{
    background: transparent;
    width: 18px;
    height: 18px;
}}
"""
