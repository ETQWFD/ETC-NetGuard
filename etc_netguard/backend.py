# -*- coding: utf-8 -*-
"""ETC NetGuard - Windows network control core.

Real enforcement paths
----------------------
* Per-process bandwidth cap : Policy-based QoS (`New-NetQosPolicy` + ThrottleRateActionBitsPerSecond)
* Per-process full block    : Windows Firewall outbound + inbound program rules
* Website 404 interception  : hosts file -> 127.0.0.1 + local HTTP server returning HTTP 404
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = "ETC NetGuard"
APP_VERSION = "1.2.1"
AUTHOR = "etc"
REPO_URL = "https://github.com/ETQWFD/ETC-NetGuard"

IS_WINDOWS = sys.platform == "win32"
PREVIEW = os.environ.get("ETC_PREVIEW") == "1"

MARK_START = "# >>> ETC NetGuard blocked sites >>>"
MARK_END = "# <<< ETC NetGuard blocked sites <<<"
QOS_PREFIX = "ETCNetGuard_QoS_"
FW_PREFIX = "ETCNetGuard_Block_"


# ---------------------------------------------------------------------------
# paths / config
# ---------------------------------------------------------------------------
def data_dir() -> Path:
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    p = Path(base) / "ETCNetGuard"
    p.mkdir(parents=True, exist_ok=True)
    return p


CONFIG_PATH = data_dir() / "config.json"

DEFAULT_CONFIG = {
    "onboarding_done": False,
    "limits": [],          # [{path,name,rate_bps}]
    "blocks": [],          # [{path,name}]
    "sites": [],           # [{domain,name}]
    "sites_enabled": False,
    "refresh_sec": 3,
    "theme": "dark",
    "password_enabled": False,
    "password_salt": "",
    "password_hash": "",
    "password_iterations": 200000,
    "block_cmd": False,
    "block_taskmgr": False,
    "block_browsers": False,
    "blacklist": [],
}


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        if CONFIG_PATH.exists():
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k in cfg:
                    if k in raw:
                        cfg[k] = raw[k]
    except Exception:
        pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_PATH)
    except Exception:
        pass


def norm_path(path: str) -> str:
    # Normalise regardless of host OS so tests and Windows builds agree.
    return (path or "").strip().replace("/", "\\").lower()


def rule_hash(path: str) -> str:
    return hashlib.md5(norm_path(path).encode("utf-8")).hexdigest()[:10]


def qos_name(path: str) -> str:
    return QOS_PREFIX + rule_hash(path)


def fw_name(path: str) -> str:
    return FW_PREFIX + rule_hash(path)


def format_rate(bps: int) -> str:
    if bps >= 1024 * 1024:
        return f"{bps / (1024 * 1024):g} MB/s"
    return f"{max(1, int(bps / 1024))} KB/s"


# ---------------------------------------------------------------------------
# privilege / powershell
# ---------------------------------------------------------------------------
def is_admin() -> bool:
    if PREVIEW:
        return True
    if not IS_WINDOWS:
        try:
            return os.geteuid() == 0
        except Exception:
            return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate() -> tuple[bool, str]:
    if PREVIEW or not IS_WINDOWS:
        return False, "当前为预览环境"
    try:
        exe = sys.executable
        params = "" if getattr(sys, "frozen", False) else f'"{Path(sys.argv[0]).resolve()}"'
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        return (rc > 32, "" if rc > 32 else f"提权失败（{rc}）")
    except Exception as e:
        return False, str(e)


def _powershell() -> str:
    p = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if p.exists():
        return str(p)
    return shutil.which("powershell.exe") or "powershell.exe"


def run_ps(script: str, timeout: int = 90) -> tuple[bool, str]:
    """Run an elevated PowerShell script and return (ok, stdout-or-error)."""
    if not IS_WINDOWS or PREVIEW:
        time.sleep(0.05)
        return True, "OK"
    script = ("$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
              "$ProgressPreference='SilentlyContinue'\n" + script)
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    creation = 0x08000000 if IS_WINDOWS else 0
    try:
        proc = subprocess.run(
            [_powershell(), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-EncodedCommand", enc],
            capture_output=True, text=True, timeout=timeout, creationflags=creation,
        )
    except Exception as e:
        return False, f"命令执行失败：{e}"
    out = (proc.stdout or "").replace("\ufeff", "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        msg = err or out
        # keep the most human-readable line
        lines = [x.strip() for x in msg.splitlines() if x.strip()]
        return False, (lines[-1] if lines else f"PowerShell 返回 {proc.returncode}")[:300]
    # PowerShell 5 sometimes writes non-terminating errors to stderr with rc=0
    if err and ("Exception" in err or "错误" in err) and not out:
        return False, err.splitlines()[-1][:300]
    return True, out


def ps_quote(s: str) -> str:
    return "'" + (s or "").replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# process enumeration
# ---------------------------------------------------------------------------
class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _win_processes() -> list[dict]:
    from ctypes import wintypes
    psapi = ctypes.WinDLL("psapi")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                    wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    psapi.EnumProcesses.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    psapi.EnumProcesses.restype = wintypes.BOOL
    pids = (wintypes.DWORD * 4096)()
    needed = wintypes.DWORD()
    if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(needed)):
        return []
    count = needed.value // ctypes.sizeof(wintypes.DWORD)
    if needed.value >= ctypes.sizeof(pids):
        bigger_count = max(8192, int(needed.value / ctypes.sizeof(wintypes.DWORD) * 1.25))
        pids = (wintypes.DWORD * bigger_count)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(needed)):
            return []
        count = min(bigger_count, needed.value // ctypes.sizeof(wintypes.DWORD))

    rows: list[dict] = []
    PROCESS_QUERY_LIMITED = 0x1000
    for i in range(count):
        pid = int(pids[i])
        if pid in (0,):
            continue
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not h:
            if pid == 4:
                rows.append({"pid": pid, "name": "System", "path": "", "mem": 0.0})
            continue
        try:
            buf = ctypes.create_unicode_buffer(4096)
            size = wintypes.DWORD(4096)
            ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            path = buf.value if ok else ""
            name = os.path.basename(path) if path else ""
            mem = 0.0
            mc = _PROCESS_MEMORY_COUNTERS()
            mc.cb = ctypes.sizeof(mc)
            if psapi.GetProcessMemoryInfo(h, ctypes.byref(mc), mc.cb):
                mem = round(mc.WorkingSetSize / (1024 * 1024), 1)
            if not name:
                continue
            rows.append({"pid": pid, "name": name, "path": path, "mem": mem})
        except Exception:
            continue
        finally:
            kernel32.CloseHandle(h)
    return rows


def _group_processes(rows: list[dict]) -> list[dict]:
    """One row per executable: multi-instance apps are merged, not duplicated."""
    grouped: dict[str, dict] = {}
    for row in rows:
        path = (row.get("path") or "").strip()
        key = norm_path(path) if path else f"pid:{row.get('pid')}:{row.get('name')}"
        cur = grouped.get(key)
        if cur is None:
            cur = dict(row)
            cur["pids"] = [int(row.get("pid") or 0)]
            cur["instances"] = 1
            grouped[key] = cur
        else:
            cur["pids"].append(int(row.get("pid") or 0))
            cur["instances"] = int(cur.get("instances", 1)) + 1
            cur["mem"] = round(float(cur.get("mem") or 0) + float(row.get("mem") or 0), 1)
            if path and not cur.get("path"):
                cur["path"] = path
                cur["name"] = row.get("name") or cur.get("name")
    out = []
    for row in grouped.values():
        pids = sorted(p for p in row.get("pids", []) if p)
        row["pid"] = pids[0] if pids else int(row.get("pid") or 0)
        row["pids"] = pids
        out.append(row)
    return sorted(out, key=lambda r: (str(r.get("name", "")).lower(), int(r.get("pid") or 0)))


PREVIEW_PROCESSES = [
    ("chrome.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe", 412.5),
    ("WeChat.exe", r"C:\Program Files\Tencent\WeChat\WeChat.exe", 286.4),
    ("QQ.exe", r"C:\Program Files\Tencent\QQNT\QQ.exe", 198.2),
    ("Steam.exe", r"C:\Program Files (x86)\Steam\steam.exe", 154.7),
    ("Douyin.exe", r"C:\Users\etc\AppData\Local\Douyin\Douyin.exe", 342.1),
    ("CloudMusic.exe", r"C:\Program Files\Netease\CloudMusic\cloudmusic.exe", 121.8),
    ("Code.exe", r"C:\Users\etc\AppData\Local\Programs\Microsoft VS Code\Code.exe", 508.3),
    ("Docker Desktop.exe", r"C:\Program Files\Docker\Docker\Docker Desktop.exe", 621.9),
    ("Telegram.exe", r"C:\Users\etc\AppData\Roaming\Telegram Desktop\Telegram.exe", 96.5),
    ("msedge.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", 377.2),
    ("explorer.exe", r"C:\Windows\explorer.exe", 84.6),
    ("spotify.exe", r"C:\Users\etc\AppData\Roaming\Spotify\Spotify.exe", 233.4),
    ("Bilibili.exe", r"C:\Program Files\Bilibili\Bilibili.exe", 175.9),
    ("Thunder.exe", r"C:\Program Files (x86)\Thunder Network\Thunder\Thunder.exe", 267.0),
    ("OneDrive.exe", r"C:\Users\etc\AppData\Local\Microsoft\OneDrive\OneDrive.exe", 148.3),
    ("Photoshop.exe", r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe", 912.7),
]


def list_processes() -> list[dict]:
    if PREVIEW:
        base = int(time.time()) % 7
        rows = []
        for i, (name, path, mem) in enumerate(PREVIEW_PROCESSES):
            rows.append({"pid": 1200 + i * 73 + base, "name": name, "path": path,
                         "mem": round(mem + (base % 5) * 1.7, 1)})
        return _group_processes(rows)
    if IS_WINDOWS:
        return _group_processes(_win_processes())
    # Linux/macOS fallback for development previews
    rows = []
    proc = Path("/proc")
    if proc.exists():
        for d in proc.iterdir():
            if not d.name.isdigit():
                continue
            try:
                comm = (d / "comm").read_text(errors="ignore").strip()
                exe = os.readlink(d / "exe") if (d / "exe").exists() else ""
                mem = 0.0
                statm = (d / "statm").read_text().split()
                if len(statm) > 1:
                    mem = round(int(statm[1]) * 4096 / (1024 * 1024), 1)
                if comm:
                    rows.append({"pid": int(d.name), "name": os.path.basename(exe) or comm,
                                 "path": exe, "mem": mem})
            except Exception:
                continue
    return sorted(rows, key=lambda r: (r["name"].lower(), r["pid"]))


# ---------------------------------------------------------------------------
# QoS limits
# ---------------------------------------------------------------------------
def apply_limits(items: list[dict], bps: int) -> tuple[bool, str]:
    """items: [{path,name}] - create/replace one QoS policy per executable."""
    if not IS_WINDOWS:
        return False, "Linux 版暂不支持按进程 QoS 限速；请使用 Windows 版"
    items = [x for x in items if x.get("path")]
    if not items:
        return False, "请先在首页勾选需要限速的进程"
    if IS_WINDOWS and not is_admin() and not PREVIEW:
        return False, "需要管理员权限才能应用限速规则"
    entries = []
    seen = set()
    for it in items:
        path = it["path"]
        key = norm_path(path)
        if key in seen:
            continue
        seen.add(key)
        # UI stores bytes/second (KB/s); Windows QoS expects bits/second.
        entries.append(f"@{{n={ps_quote(qos_name(path))}; p={ps_quote(path)}; b=[UInt64]{int(bps) * 8}}}")
    sep = ",\n  "
    script = (
        "$ErrorActionPreference='Stop'\n"
        f"$items = @(\n  {sep.join(entries)}\n)\n"
        "foreach ($i in $items) {\n"
        "  $old = Get-NetQosPolicy -Name $i.n -ErrorAction SilentlyContinue\n"
        "  if ($old) { Remove-NetQosPolicy -Name $i.n -Confirm:$false -ErrorAction SilentlyContinue | Out-Null }\n"
        "  New-NetQosPolicy -Name $i.n -AppPathNameMatchCondition $i.p "
        "-ThrottleRateActionBitsPerSecond $i.b -NetworkProfile All | Out-Null\n"
        "}\n"
        "Write-Output 'OK'\n"
    )
    return run_ps(script)


def remove_limits(paths: list[str] | None = None) -> tuple[bool, str]:
    if not IS_WINDOWS:
        return True, "Linux 版无需清理限速规则"
    if paths:
        names = [qos_name(p) for p in paths if p]
        if not names:
            return True, "OK"
        arr = ", ".join(ps_quote(n) for n in names)
        script = (
            "$ErrorActionPreference='Continue'\n"
            f"@({arr}) | ForEach-Object {{ Remove-NetQosPolicy -Name $_ -Confirm:$false -ErrorAction SilentlyContinue | Out-Null }}\n"
            "Write-Output 'OK'\n"
        )
    else:
        script = (
            "$ErrorActionPreference='Continue'\n"
            "Get-NetQosPolicy -ErrorAction SilentlyContinue | "
            f"Where-Object {{ $_.Name -like '{QOS_PREFIX}*' }} | "
            "ForEach-Object { Remove-NetQosPolicy -Name $_.Name -Confirm:$false -ErrorAction SilentlyContinue | Out-Null }\n"
            "Write-Output 'OK'\n"
        )
    return run_ps(script)


# ---------------------------------------------------------------------------
# Firewall full block
# ---------------------------------------------------------------------------
def apply_blocks(items: list[dict], enabled: bool = True) -> tuple[bool, str]:
    if not IS_WINDOWS:
        return False, "Linux 版暂不支持按进程防火墙断网；请使用 Windows 版"
    items = [x for x in items if x.get("path")]
    if not items:
        return False, "请先在首页勾选需要断网的进程"
    if IS_WINDOWS and not is_admin() and not PREVIEW:
        return False, "需要管理员权限才能阻断进程联网"
    if not enabled:
        return remove_blocks([x["path"] for x in items])
    entries = []
    seen = set()
    for it in items:
        key = norm_path(it["path"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(f"@{{n={ps_quote(fw_name(it['path']))}; p={ps_quote(it['path'])}}}")
    sep = ",\n  "
    script = (
        "$ErrorActionPreference='Stop'\n"
        f"$items = @(\n  {sep.join(entries)}\n)\n"
        "foreach ($i in $items) {\n"
        "  Get-NetFirewallRule -DisplayName $i.n -ErrorAction SilentlyContinue | Remove-NetFirewallRule -Confirm:$false\n"
        "  New-NetFirewallRule -DisplayName $i.n -Direction Outbound -Program $i.p -Action Block "
        "-Profile Any -Enabled True | Out-Null\n"
        "  New-NetFirewallRule -DisplayName ($i.n + '_IN') -Direction Inbound -Program $i.p -Action Block "
        "-Profile Any -Enabled True | Out-Null\n"
        "}\n"
        "Write-Output 'OK'\n"
    )
    return run_ps(script)


def remove_blocks(paths: list[str] | None = None) -> tuple[bool, str]:
    if not IS_WINDOWS:
        return True, "Linux 版无需清理断网规则"
    if paths:
        names = []
        for p in paths:
            n = fw_name(p)
            names.extend([n, n + "_IN"])
        if not names:
            return True, "OK"
        arr = ", ".join(ps_quote(n) for n in names)
        script = (
            "$ErrorActionPreference='Continue'\n"
            f"@({arr}) | ForEach-Object {{ Get-NetFirewallRule -DisplayName $_ -ErrorAction SilentlyContinue | Remove-NetFirewallRule -Confirm:$false }}\n"
            "Write-Output 'OK'\n"
        )
    else:
        script = (
            "$ErrorActionPreference='Continue'\n"
            "Get-NetFirewallRule -ErrorAction SilentlyContinue | "
            f"Where-Object {{ $_.DisplayName -like '{FW_PREFIX}*' }} | "
            "Remove-NetFirewallRule -Confirm:$false\n"
            "Write-Output 'OK'\n"
        )
    return run_ps(script)


# ---------------------------------------------------------------------------
# hosts + local 404 server
# ---------------------------------------------------------------------------
def hosts_path() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def normalize_domain(text: str) -> str:
    text = (text or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/")[0].split("?")[0].split("#")[0]
    text = text.split("@")[-1]
    text = text.split(":")[0]
    text = text.strip(".")
    if text.startswith("*."):
        text = text[2:]
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+", text):
        return ""
    return text


def domain_variants(domain: str) -> list[str]:
    """Block the apex plus the hosts people actually type on phones."""
    d = normalize_domain(domain)
    if not d:
        return []
    apex = d
    for prefix in ("www.", "m.", "mobile."):
        if d.startswith(prefix) and "." in d[len(prefix):]:
            apex = d[len(prefix):]
            break
    # hosts has no wildcard syntax.  Cover the subdomain names browsers and
    # mobile apps actually use, so typing only "example.com" blocks the site
    # and its common front doors (www / m / mobile / cdn / api / ...).
    prefixes = (
        "www", "m", "mobile", "wap", "web", "api", "cdn", "static",
        "img", "images", "video", "music", "live", "h5", "app",
        "download", "passport", "login", "pay", "service",
    )
    out = [d, apex]
    out += [p + "." + apex for p in prefixes]
    return list(dict.fromkeys(out))


# Backwards-compatible internal alias
_domain_variants = domain_variants


def _strip_block(text: str) -> str:
    pattern = re.compile(rf"\n?{re.escape(MARK_START)}.*?{re.escape(MARK_END)}\n?", re.S)
    return pattern.sub("\n", text).strip() + "\n"


def write_hosts(sites: list[dict], enabled: bool, redirect_ip: str = "127.0.0.1") -> tuple[bool, str]:
    if PREVIEW:
        return True, "OK"
    hp = hosts_path()
    try:
        raw = hp.read_text(encoding="utf-8", errors="ignore") if hp.exists() else ""
        backup = data_dir() / "hosts.backup"
        if hp.exists() and not backup.exists():
            try:
                shutil.copy2(hp, backup)
            except Exception:
                pass
        clean = _strip_block(raw)
        if enabled and sites:
            domains = []
            for s in sites:
                d = normalize_domain(s.get("domain", ""))
                if d:
                    for v in _domain_variants(d):
                        if v not in domains:
                            domains.append(v)
            block = [MARK_START, "# Managed by ETC NetGuard. Do not edit this section.",
                     "# Any listed domain resolves to the local 404 interception page."]
            v4 = redirect_ip if redirect_ip else "127.0.0.1"
            v6 = "::1"
            # IPv4 + IPv6: Windows prefers AAAA first on many networks, so a
            # hosts file with only 127.0.0.1 can be bypassed over IPv6.
            block += [f"{v4} {d}" for d in domains]
            block += [f"{v6} {d}" for d in domains]
            block.append(MARK_END)
            clean = clean.rstrip() + "\n\n" + "\n".join(block) + "\n"
        hp.parent.mkdir(parents=True, exist_ok=True)
        with open(str(hp), "w", encoding="utf-8", newline="\r\n") as f:
            f.write(clean)
        # Read-back verification catches antivirus/EDR silently reverting hosts.
        if enabled and sites:
            written = hp.read_text(encoding="utf-8", errors="ignore")
            if MARK_START not in written or not any(d in written for d in domains):
                return False, "hosts 写入后校验失败，可能被安全软件拦截"
        _flush_dns()
        return True, "OK"
    except PermissionError:
        return False, "写入 hosts 需要管理员权限"
    except Exception as e:
        return False, f"写入 hosts 失败：{e}"


def _flush_dns():
    if PREVIEW:
        return
    if not IS_WINDOWS:
        for cmd in (["resolvectl", "flush-caches"], ["systemd-resolve", "--flush-caches"]):
            try:
                subprocess.run(cmd, capture_output=True, timeout=10)
            except Exception:
                pass
        return
    try:
        ctypes.windll.dnsapi.DnsFlushResolverCache()
    except Exception:
        pass
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=20,
                       creationflags=0x08000000)
    except Exception:
        pass
    try:
        subprocess.run(["ipconfig", "/registerdns"], capture_output=True, timeout=25,
                       creationflags=0x08000000)
    except Exception:
        pass


BLOCK_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>404 · 已被 ETC NetGuard 拦截</title>
<style>
  :root{{color-scheme:dark}}
  *{{box-sizing:border-box}}
  body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
        background:radial-gradient(1200px 700px at 18% 0%,#0d2b2c 0%,#081219 45%,#05090d 100%);
        color:#eaf2f8;font-family:"Microsoft YaHei UI","Microsoft YaHei",system-ui,-apple-system,"Segoe UI",sans-serif;
        overflow:hidden}}
  body:before,body:after{{content:"";position:fixed;border-radius:50%;filter:blur(70px);opacity:.5;pointer-events:none}}
  body:before{{width:420px;height:420px;background:#1e8f83;left:-120px;top:-140px}}
  body:after{{width:380px;height:380px;background:#2456a8;right:-100px;bottom:-150px}}
  .card{{position:relative;width:min(620px,92vw);padding:54px 54px 42px;border-radius:24px;
         background:linear-gradient(145deg,rgba(19,33,43,.94),rgba(10,18,25,.96));
         border:1px solid rgba(255,255,255,.09);box-shadow:0 30px 90px rgba(0,0,0,.55);z-index:2}}
  .brand{{display:flex;align-items:center;gap:10px;font-size:11px;letter-spacing:.32em;color:#5f7a8b;text-transform:uppercase}}
  .mark{{width:30px;height:30px;border-radius:9px;background:linear-gradient(140deg,#4df3d5,#3c8dff);
          display:flex;align-items:center;justify-content:center;color:#041a16;font-weight:800;font-size:14px;letter-spacing:0}}
  .code{{font-size:104px;font-weight:800;line-height:1;letter-spacing:-.04em;margin:34px 0 18px;
         background:linear-gradient(120deg,#5bffe0,#4e9bff);-webkit-background-clip:text;background-clip:text;color:transparent}}
  h1{{font-size:22px;margin:0 0 12px;font-weight:650}}
  p{{margin:0;color:#93a9ba;font-size:14px;line-height:1.85}}
  .site{{display:inline-block;margin:22px 0 6px;padding:8px 14px;border-radius:10px;
         background:rgba(255,111,125,.08);border:1px solid rgba(255,111,125,.22);color:#ff9aa5;font-size:13px}}
  .bar{{height:1px;background:linear-gradient(90deg,rgba(53,227,195,.45),rgba(255,255,255,.04));margin:34px 0 18px}}
  .foot{{display:flex;justify-content:space-between;color:#5f7487;font-size:12px}}
  .dot{{display:inline-block;width:6px;height:6px;border-radius:50%;background:#35e3c3;margin-right:7px;vertical-align:1px}}
  @media(max-width:560px){{.card{{padding:34px 26px 28px}}.code{{font-size:76px}}}}
</style>
</head>
<body>
  <main class="card">
    <div class="brand"><span class="mark">E</span>ETC NETGUARD · WEBSITE BLOCK</div>
    <div class="code">404</div>
    <h1>这个网站已被禁止访问</h1>
    <p>请求的站点命中 ETC NetGuard 的本地拦截规则，连接被重定向到本机，<br>并返回标准 HTTP 404。它没有加载任何真实内容。</p>
    <div class="site">{host}</div>
    <div class="bar"></div>
    <div class="foot"><span><i class="dot"></i>拦截服务运行中 · 127.0.0.1</span><span>by etc · v{version}</span></div>
  </main>
</body>
</html>"""


class _BlockHandler(BaseHTTPRequestHandler):
    server_version = "ETCNetGuard/1.0"
    protocol_version = "HTTP/1.1"

    def _send(self, with_body: bool = True):
        host = self.headers.get("Host", "unknown")
        host = host.split(":")[0][:80]
        body = BLOCK_PAGE.format(host=host, version=APP_VERSION).encode("utf-8")
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex")
        self.end_headers()
        if with_body:
            try:
                self.wfile.write(body)
            except Exception:
                pass

    def do_GET(self):  # noqa: N802
        self._send(True)

    def do_HEAD(self):  # noqa: N802
        self._send(False)

    def do_POST(self):  # noqa: N802
        self._send(True)

    def log_message(self, fmt, *args):
        pass


class BlockServer:
    def __init__(self):
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port = 80

    @property
    def running(self) -> bool:
        return self.httpd is not None

    def start(self) -> tuple[bool, str]:
        if self.httpd:
            return True, "OK"
        if PREVIEW:
            self.httpd = object()  # type: ignore
            return True, "OK"
        try:
            server = ThreadingHTTPServer(("127.0.0.1", self.port), _BlockHandler)
            server.daemon_threads = True
        except OSError as e:
            if getattr(e, "winerror", None) == 10048 or e.errno in (98, 48):
                return False, f"端口 {self.port} 已被占用，无法启动 404 拦截页"
            return False, f"无法启动本地拦截服务：{e}"
        except Exception as e:
            return False, f"无法启动本地拦截服务：{e}"
        self.httpd = server
        self.thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
        self.thread.start()
        return True, "OK"

    def stop(self):
        httpd = self.httpd
        self.httpd = None
        self.thread = None
        if httpd is not None and hasattr(httpd, "shutdown"):
            try:
                httpd.shutdown()
            except Exception:
                pass
            try:
                httpd.server_close()
            except Exception:
                pass


BLOCK_SERVER = BlockServer()


def apply_sites(sites: list[dict], enabled: bool) -> tuple[bool, str]:
    """Start/stop the 404 server and rewrite the hosts block atomically."""
    if PREVIEW:
        return True, "OK"
    server_ok = True
    server_msg = "OK"
    if enabled and sites:
        server_ok, server_msg = BLOCK_SERVER.start()
    # Even when port 80 is taken, the hosts block must still be written.  In
    # that case point blocked hosts at 0.0.0.0 so they fail closed instead of
    # being served by whatever happens to own port 80.
    redirect_ip = "127.0.0.1" if server_ok else "0.0.0.0"
    ok, msg = write_hosts(sites, enabled, redirect_ip)
    if not ok:
        if enabled and sites:
            BLOCK_SERVER.stop()
        return False, msg
    if not enabled or not sites:
        BLOCK_SERVER.stop()
        return True, "OK"
    if not server_ok:
        return True, f"域名已被阻断，但 404 页面服务未启动（{server_msg}）。"
    return True, "OK"


def test_local_404() -> tuple[bool, str]:
    if PREVIEW:
        return False, "预览环境不启动真实端口"
    if not BLOCK_SERVER.running:
        return False, "404 拦截服务未启动"
    try:
        s = socket.create_connection(("127.0.0.1", 80), timeout=2)
        s.sendall(b"GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n")
        data = s.recv(200).decode("utf-8", "ignore")
        s.close()
        return ("404" in data.splitlines()[0], data.splitlines()[0] if data else "无响应")
    except Exception as e:
        return False, str(e)


def clear_all_rules() -> list[str]:
    msgs = []
    ok, msg = remove_limits(None)
    msgs.append("限速规则已清除" if ok else f"限速清除失败：{msg}")
    ok, msg = remove_blocks(None)
    msgs.append("断网规则已清除" if ok else f"断网清除失败：{msg}")
    ok, msg = write_hosts([], False, "127.0.0.1")
    BLOCK_SERVER.stop()
    msgs.append("网站拦截已关闭" if ok else f"hosts 恢复失败：{msg}")
    return msgs


def clear_all() -> list[str]:
    return clear_all_rules()


def open_data_dir():
    if IS_WINDOWS:
        try:
            os.startfile(str(data_dir()))  # type: ignore[attr-defined]
        except Exception:
            pass
    else:
        subprocess.Popen(["xdg-open", str(data_dir())])
