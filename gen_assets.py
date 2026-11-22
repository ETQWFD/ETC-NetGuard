# -*- coding: utf-8 -*-
"""Generate app icon + QSS check mark for the build."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication

from etc_netguard import icons

app = QApplication(sys.argv)
icons.ensure_assets()
print("assets ready:", icons.asset_dir())
for name in ("app.png", "app.ico", "check.png"):
    p = icons.asset_dir() / name
    print(name, p.exists(), p.stat().st_size if p.exists() else 0)
