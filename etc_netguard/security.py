# -*- coding: utf-8 -*-
"""Parental-control guard: password gating, timer-driven app restrictions."""
from __future__ import annotations

import os
import time

from PyQt5.QtCore import QThread, pyqtSignal

from . import backend
from .native import NATIVE

# Never terminate these even if a user tries to add them to the blacklist.
PROTECTED_NAMES = {
    "system", "system idle process", "registry", "memory compression",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe", "spoolsv.exe",
    "explorer.exe", "etc-netguard.exe", "python.exe", "pythonw.exe",
    "conhost.exe", "sihost.exe", "taskhostw.exe", "runtimebroker.exe",
}

CMD_NAMES = {"cmd.exe", "powershell.exe", "pwsh.exe", "powershell_ise.exe",
             "wt.exe", "windowsterminal.exe"}
TASKMGR_NAMES = {"taskmgr.exe"}
BROWSER_NAMES = {
    "chrome.exe", "msedge.exe", "firefox.exe", "iexplore.exe",
    "opera.exe", "brave.exe", "vivaldi.exe", "360chrome.exe", "360se.exe",
    "qqbrowser.exe", "sogouexplorer.exe", "maxthon.exe", "ucbrowser.exe",
    "theworld.exe", "liebao.exe",
}

PROTECTED_PATHS = {r"c:\windows\explorer.exe"}


def is_protected(name: str, path: str = "") -> bool:
    n = (name or "").lower()
    if n in PROTECTED_NAMES:
        return True
    p = (path or "").lower().replace("/", "\\")
    if p in PROTECTED_PATHS:
        return True
    return False


def _terminate_fallback(pid: int) -> bool:
    if pid in (0, 4) or pid == os.getpid():
        return False
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        h = kernel32.OpenProcess(0x0001, False, int(pid))
        if not h:
            return False
        ok = bool(kernel32.TerminateProcess(h, 1))
        kernel32.CloseHandle(h)
        return ok
    except Exception:
        return False


class GuardWorker(QThread):
    """Checks running apps every 1.5 s and stops the ones the parent blocked."""

    blocked = pyqtSignal(str, str)      # app name, reason
    failed = pyqtSignal(str, str)       # app name, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._block_cmd = False
        self._block_taskmgr = False
        self._block_browsers = False
        self._blacklist: set[str] = set()
        self._last_notice: dict[str, float] = {}
        self._stop = False

    def update_rules(self, block_cmd: bool, block_taskmgr: bool, block_browsers: bool, blacklist: list[dict]):
        self._block_cmd = bool(block_cmd)
        self._block_taskmgr = bool(block_taskmgr)
        self._block_browsers = bool(block_browsers)
        self._blacklist = {backend.norm_path(x.get("path", "")) for x in blacklist if x.get("path")}

    @property
    def active(self) -> bool:
        return bool(self._block_cmd or self._block_taskmgr or self._block_browsers or self._blacklist)

    def _reason(self, row: dict) -> str:
        name = (row.get("name") or "").lower()
        path = row.get("path") or ""
        if self._block_cmd and name in CMD_NAMES:
            return "命令提示符 / PowerShell 已禁用"
        if self._block_taskmgr and name in TASKMGR_NAMES:
            return "任务管理器已禁用"
        if self._block_browsers and name in BROWSER_NAMES:
            return "浏览器已禁用"
        if path and backend.norm_path(path) in self._blacklist:
            return "黑名单程序已阻止"
        return ""

    def _notify_ok(self, name: str) -> bool:
        now = time.time()
        if now - self._last_notice.get(name, 0) < 8:
            return False
        self._last_notice[name] = now
        return True

    def run(self):
        while not self._stop and not self.isInterruptionRequested():
            if not self.active or not backend.IS_WINDOWS or backend.PREVIEW:
                self.msleep(1400)
                continue
            try:
                rows = backend.list_processes()
            except Exception:
                rows = []
            own = os.getpid()
            for row in rows:
                reason = self._reason(row)
                if not reason:
                    continue
                name = row.get("name") or "unknown"
                if is_protected(name, row.get("path") or ""):
                    continue
                pids = row.get("pids") or [row.get("pid")]
                killed = False
                for pid in pids:
                    if not pid or int(pid) == own:
                        continue
                    if NATIVE.terminate_process(int(pid)) or _terminate_fallback(int(pid)):
                        killed = True
                if killed and self._notify_ok(name):
                    self.blocked.emit(name, reason)
                elif not killed and self._notify_ok(name):
                    self.failed.emit(name, "权限不足，无法结束该进程")
            self.msleep(1500)

    def stop(self):
        self._stop = True
        self.requestInterruption()
        self.wait(2500)
        if self.isRunning():
            try:
                self.terminate()
                self.wait(1200)
            except Exception:
                pass
