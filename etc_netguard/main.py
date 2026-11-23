# -*- coding: utf-8 -*-
"""Application entry point for ETC NetGuard."""
from __future__ import annotations

import ctypes
import faulthandler
import os
import sys
import time
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMessageBox

from . import backend, icons


_LOG_STREAM = None


def _install_logging():
    """Write Python/native crashes to a local log so failures are diagnosable."""
    global _LOG_STREAM
    try:
        log_path = backend.data_dir() / "error.log"
        _LOG_STREAM = open(str(log_path), "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_LOG_STREAM, all_threads=True)
        def hook(t, v, tb):
            try:
                _LOG_STREAM.write("\n[%s] unhandled exception\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
                traceback.print_exception(t, v, tb, file=_LOG_STREAM)
                _LOG_STREAM.flush()
            except Exception:
                pass
            sys.__excepthook__(t, v, tb)
        sys.excepthook = hook
    except Exception:
        pass


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
    _install_logging()
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

    try:
        window = MainWindow()
        window.show()
    except Exception:
        try:
            log = backend.data_dir() / "error.log"
            with open(str(log), "a", encoding="utf-8") as f:
                f.write("\n[%s] startup failed\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
                traceback.print_exc(file=f)
        except Exception:
            log = ""
        QMessageBox.critical(None, "ETC NetGuard 启动失败",
                             "程序启动时发生错误。\n请把日志发给作者：\n%s" % log)
        return 1
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
