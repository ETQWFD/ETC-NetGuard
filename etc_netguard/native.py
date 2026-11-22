# -*- coding: utf-8 -*-
"""Optional Windows native helper (etc_guard.dll)."""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from .theme import asset_dir


class NativeGuard:
    def __init__(self):
        self.lib = None
        self.error = ""
        if sys.platform != "win32":
            self.error = "非 Windows 环境"
            return
        path = asset_dir() / "native" / "etc_guard.dll"
        if not path.exists():
            self.error = "未找到 native/etc_guard.dll"
            return
        try:
            lib = ctypes.WinDLL(str(path))
            lib.ng_install_close_guard.argtypes = [ctypes.c_void_p]
            lib.ng_install_close_guard.restype = ctypes.c_int
            lib.ng_set_close_guard.argtypes = [ctypes.c_int]
            lib.ng_set_close_guard.restype = None
            lib.ng_take_close_request.restype = ctypes.c_int
            lib.ng_terminate_process.argtypes = [ctypes.c_ulong]
            lib.ng_terminate_process.restype = ctypes.c_int
            lib.ng_single_instance.argtypes = [ctypes.c_wchar_p]
            lib.ng_single_instance.restype = ctypes.c_int
            self.lib = lib
        except Exception as exc:
            self.error = str(exc)

    @property
    def available(self) -> bool:
        return self.lib is not None

    def install_close_guard(self, hwnd: int) -> bool:
        if not self.lib:
            return False
        try:
            return bool(self.lib.ng_install_close_guard(ctypes.c_void_p(hwnd)))
        except Exception:
            return False

    def set_close_guard(self, enabled: bool) -> None:
        if self.lib:
            try:
                self.lib.ng_set_close_guard(1 if enabled else 0)
            except Exception:
                pass

    def take_close_request(self) -> bool:
        if not self.lib:
            return False
        try:
            return bool(self.lib.ng_take_close_request())
        except Exception:
            return False

    def terminate_process(self, pid: int) -> bool:
        if not self.lib:
            return False
        try:
            return bool(self.lib.ng_terminate_process(int(pid)))
        except Exception:
            return False

    def single_instance(self, name: str) -> bool:
        if not self.lib:
            return True
        try:
            return bool(self.lib.ng_single_instance(name))
        except Exception:
            return True


NATIVE = NativeGuard()
