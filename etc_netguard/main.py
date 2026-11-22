# -*- coding: utf-8 -*-
"""Application entry point for ETC NetGuard."""
from __future__ import annotations

import ctypes
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

from . import backend, icons


def _windows_bootstrap():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("etc.netguard.desktop.1")
    except Exception:
        pass


def main():
    _windows_bootstrap()
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("ETC NetGuard")
    app.setApplicationDisplayName("ETC NetGuard")
    app.setOrganizationName("etc")
    app.setQuitOnLastWindowClosed(False)

    font = QFont()
    try:
        font.setFamilies(["Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC"])
    except Exception:
        font.setFamily("Microsoft YaHei UI")
    font.setPixelSize(13)
    app.setFont(font)

    icons.ensure_assets()

    from .main_window import MainWindow

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
