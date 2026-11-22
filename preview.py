# -*- coding: utf-8 -*-
"""Render every screen offscreen for design review and README screenshots."""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREVIEW = ROOT / "preview"
CFG = PREVIEW / "config"
shutil.rmtree(CFG, ignore_errors=True)
os.environ["XDG_CONFIG_HOME"] = str(CFG)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["ETC_PREVIEW"] = "1"
sys.path.insert(0, str(ROOT))

from etc_netguard import backend, icons  # noqa: E402

paths = {x[0]: x[1] for x in backend.PREVIEW_PROCESSES}
cfg_data = {
    "onboarding_done": True,
    "limits": [
        {"path": paths["chrome.exe"], "name": "chrome.exe", "rate_bps": 102400},
        {"path": paths["Code.exe"], "name": "Code.exe", "rate_bps": 524288},
    ],
    "blocks": [
        {"path": paths["Thunder.exe"], "name": "Thunder.exe"},
    ],
    "sites": [
        {"domain": "douyin.com", "name": "抖音网页版"},
        {"domain": "bilibili.com", "name": "哔哩哔哩"},
        {"domain": "example.com", "name": "示例站点"},
    ],
    "sites_enabled": True,
}
backend.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
backend.CONFIG_PATH.write_text(json.dumps(cfg_data, ensure_ascii=False, indent=2), encoding="utf-8")

from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
icons.ensure_assets()

from etc_netguard.main_window import MainWindow  # noqa: E402

w = MainWindow()
w.resize(1260, 820)
w.show()
QTest.qWait(700)
w.setMinimumSize(1260, 820)
w.resize(1260, 820)
QTest.qWait(350)

# pick two limited processes so the limit page switch is genuinely "on"
for row in w.state.processes:
    if row["name"] in ("chrome.exe", "Code.exe"):
        w.state.toggle(row, True)
w.on_selection_changed()
w.home.set_processes(w.state.processes)
QTest.qWait(300)

shots = PREVIEW / "shots"
shots.mkdir(parents=True, exist_ok=True)


def snap(name: str, widget=None):
    QTest.qWait(450)
    target = widget or w
    target.grab().save(str(shots / name))
    print("saved", name)


for idx, name in ((0, "01-home.png"), (1, "02-limit.png"), (2, "03-sites.png"), (3, "04-settings.png")):
    w.goto(idx)
    snap(name)

# onboarding first step
w.goto(0)
w.onboarding.setGeometry(w.body.rect())
w.onboarding.setGeometry(w.body.rect())
w.onboarding.open_at(0)
QTest.qWait(250)
print("onboarding", w.onboarding.geometry().getRect(), w.onboarding.card.geometry().getRect())
snap("05-onboarding-1.png")

# onboarding bandwidth step
w.onboarding._set_step(4, animate=False)
snap("06-onboarding-5.png")
w.onboarding.hide()

# about author dialog
from etc_netguard.dialogs import AboutAuthorDialog, AddSiteDialog  # noqa: E402

dlg = AboutAuthorDialog(w)
dlg.show()
snap("07-about-author.png", dlg)
dlg.close()

dlg = AddSiteDialog(w)
dlg.show()
dlg.url.setText("https://www.example.com/watch")
dlg.name.setText("示例视频站")
snap("08-add-site.png", dlg)
dlg.close()

# security center + password screens
from etc_netguard.security_dialogs import PasswordDialog, PasswordSetupDialog, SettingsDialog  # noqa: E402

w.state.set_password("etc1234")
w.state.set_restriction("block_cmd", True)
w.state.set_restriction("block_browsers", True)
for n in ("chrome.exe", "Thunder.exe", "Telegram.exe"):
    w.state.add_blacklist(paths[n], n)
dlg = SettingsDialog(w)
dlg.show()
QTest.qWait(500)
dlg.grab().save(str(shots / "09-security-settings.png"))
print("saved 09-security-settings.png", dlg.width(), dlg.height())
dlg.scroll.verticalScrollBar().setValue(dlg.scroll.verticalScrollBar().maximum())
QTest.qWait(250)
dlg.grab().save(str(shots / "10-security-blacklist.png"))
print("saved 10-security-blacklist.png")
dlg.close()

pd = PasswordDialog(w, w.state, "关闭软件", "退出 ETC NetGuard 需要关闭密码。")
pd.show()
QTest.qWait(300)
pd.grab().save(str(shots / "11-password-prompt.png"))
print("saved 11-password-prompt.png")
pd.close()

ps = PasswordSetupDialog(w, w.state, start_enabled=True)
ps.show()
QTest.qWait(300)
ps.grab().save(str(shots / "12-password-setup.png"))
print("saved 12-password-setup.png")
ps.close()

w.quit_app()
print("done")
