# -*- coding: utf-8 -*-
"""Single source of truth for selections, rules and persisted choices."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

from . import backend


class AppState:
    def __init__(self):
        self.config = backend.load_config()
        self.processes: list[dict] = []
        self.selected: set[str] = set()
        self.selected_meta: dict[str, dict] = {}
        self.known: dict[str, dict] = {}
        self.last_scan = 0.0

        self.limits: dict[str, dict] = {}
        for r in self.config.get("limits", []):
            if r.get("path"):
                self.limits[backend.norm_path(r["path"])] = {
                    "path": r["path"], "name": r.get("name") or "unknown",
                    "rate_bps": int(r.get("rate_bps") or 0),
                }
        self.blocks: dict[str, dict] = {}
        for r in self.config.get("blocks", []):
            if r.get("path"):
                self.blocks[backend.norm_path(r["path"])] = {
                    "path": r["path"], "name": r.get("name") or "unknown",
                }
        self.sites: list[dict] = [
            {"domain": s.get("domain", ""), "name": s.get("name", "")}
            for s in self.config.get("sites", []) if s.get("domain")
        ]
        self.sites_enabled = bool(self.config.get("sites_enabled"))
        self.onboarding_done = bool(self.config.get("onboarding_done"))
        self.refresh_sec = max(2, int(self.config.get("refresh_sec") or 3))
        self.password_enabled = bool(self.config.get("password_enabled"))
        self.password_salt = str(self.config.get("password_salt") or "")
        self.password_hash = str(self.config.get("password_hash") or "")
        self.password_iterations = max(50000, int(self.config.get("password_iterations") or 200000))
        self.block_cmd = bool(self.config.get("block_cmd"))
        self.block_taskmgr = bool(self.config.get("block_taskmgr"))
        self.block_browsers = bool(self.config.get("block_browsers"))
        self.blacklist: list[dict] = [
            {"path": r.get("path", ""), "name": r.get("name") or "unknown"}
            for r in self.config.get("blacklist", []) if r.get("path")
        ]

    # -- persistence ------------------------------------------------------
    def save(self):
        self.config["limits"] = list(self.limits.values())
        self.config["blocks"] = list(self.blocks.values())
        self.config["sites"] = self.sites
        self.config["sites_enabled"] = self.sites_enabled
        self.config["onboarding_done"] = self.onboarding_done
        self.config["password_enabled"] = self.password_enabled
        self.config["password_salt"] = self.password_salt
        self.config["password_hash"] = self.password_hash
        self.config["password_iterations"] = self.password_iterations
        self.config["block_cmd"] = self.block_cmd
        self.config["block_taskmgr"] = self.block_taskmgr
        self.config["block_browsers"] = self.block_browsers
        self.config["blacklist"] = self.blacklist
        backend.save_config(self.config)

    # -- processes --------------------------------------------------------
    def set_processes(self, rows: list[dict]):
        self.processes = rows
        self.last_scan = time.time()
        for r in rows:
            key = backend.norm_path(r.get("path", "")) or f"pid:{r['pid']}"
            self.known[key] = {"path": r.get("path", ""), "name": r.get("name", "unknown")}
        # drop selections whose process closed but keep executable path
        for key in list(self.selected):
            if key not in self.known and key.startswith("pid:"):
                self.selected.discard(key)
                self.selected_meta.pop(key, None)

    def process_key(self, row: dict) -> str:
        return backend.norm_path(row.get("path", "")) or f"pid:{row['pid']}"

    def is_selectable(self, row: dict) -> bool:
        return bool(row.get("path")) and row.get("path", "").lower().endswith((".exe", ".com", ".bat", ".cmd", ".msi"))

    def toggle(self, row: dict, checked: bool):
        key = self.process_key(row)
        if checked:
            if not self.is_selectable(row):
                return
            self.selected.add(key)
            self.selected_meta[key] = {"path": row.get("path", ""), "name": row.get("name", "unknown")}
        else:
            self.selected.discard(key)
            self.selected_meta.pop(key, None)

    def set_selected(self, keys: set[str], checked: bool):
        if checked:
            for key in keys:
                row = self.known.get(key, {})
                if row.get("path") and row.get("path", "").lower().endswith((".exe", ".com", ".bat", ".cmd", ".msi")):
                    self.selected.add(key)
                    self.selected_meta[key] = {"path": row["path"], "name": row.get("name", "unknown")}
            return
        for key in keys:
            self.selected.discard(key)
            self.selected_meta.pop(key, None)

    def clear_selection(self):
        self.selected.clear()
        self.selected_meta.clear()

    def selected_items(self) -> list[dict]:
        items = []
        for key in self.selected:
            meta = self.selected_meta.get(key) or self.known.get(key)
            if meta and meta.get("path"):
                items.append({"path": meta["path"], "name": meta.get("name") or "unknown", "key": key})
        return items

    def selected_names(self) -> list[str]:
        return [x["name"] for x in self.selected_items()]

    def selected_count(self) -> int:
        return len(self.selected_items())

    # -- rules ------------------------------------------------------------
    def limit_for(self, path: str) -> dict | None:
        return self.limits.get(backend.norm_path(path))

    def block_for(self, path: str) -> dict | None:
        return self.blocks.get(backend.norm_path(path))

    def set_limit_rules(self, items: list[dict], bps: int):
        for it in items:
            key = backend.norm_path(it["path"])
            self.limits[key] = {"path": it["path"], "name": it.get("name", "unknown"), "rate_bps": bps}
        self.save()

    def remove_limit_rules(self, paths: list[str] | None = None):
        if paths is None:
            self.limits.clear()
        else:
            for p in paths:
                self.limits.pop(backend.norm_path(p), None)
        self.save()

    def set_block_rules(self, items: list[dict]):
        for it in items:
            key = backend.norm_path(it["path"])
            self.blocks[key] = {"path": it["path"], "name": it.get("name", "unknown")}
        self.save()

    def remove_block_rules(self, paths: list[str] | None = None):
        if paths is None:
            self.blocks.clear()
        else:
            for p in paths:
                self.blocks.pop(backend.norm_path(p), None)
        self.save()

    def all_rule_rows(self) -> list[dict]:
        rows = []
        for key, r in self.limits.items():
            rows.append({"key": key, "kind": "limit", "path": r["path"], "name": r["name"],
                         "detail": backend.format_rate(r["rate_bps"]), "rate_bps": r["rate_bps"]})
        for key, r in self.blocks.items():
            rows.append({"key": key, "kind": "block", "path": r["path"], "name": r["name"], "detail": "完全阻断"})
        rows.sort(key=lambda x: (x["kind"], x["name"].lower()))
        return rows

    # -- password / restrictions -----------------------------------------
    def set_password(self, password: str):
        salt = os.urandom(16)
        iterations = 200000
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        self.password_salt = salt.hex()
        self.password_hash = digest.hex()
        self.password_iterations = iterations
        self.password_enabled = True
        self.save()

    def clear_password(self):
        self.password_enabled = False
        self.password_salt = ""
        self.password_hash = ""
        self.save()

    def verify_password(self, password: str) -> bool:
        if not self.password_enabled or not self.password_salt or not self.password_hash:
            return True
        try:
            salt = bytes.fromhex(self.password_salt)
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.password_iterations)
            return hmac.compare_digest(digest.hex(), self.password_hash)
        except Exception:
            return False

    def set_restriction(self, key: str, enabled: bool):
        if key not in ("block_cmd", "block_taskmgr", "block_browsers"):
            return
        setattr(self, key, bool(enabled))
        self.save()

    def add_blacklist(self, path: str, name: str) -> bool:
        key = backend.norm_path(path)
        if not key or any(backend.norm_path(x["path"]) == key for x in self.blacklist):
            return False
        self.blacklist.append({"path": path, "name": name or os.path.basename(path) or "unknown"})
        self.save()
        return True

    def remove_blacklist(self, path: str):
        key = backend.norm_path(path)
        self.blacklist = [x for x in self.blacklist if backend.norm_path(x["path"]) != key]
        self.save()

    def restriction_count(self) -> int:
        return sum(bool(getattr(self, k)) for k in ("block_cmd", "block_taskmgr", "block_browsers"))

    # -- sites ------------------------------------------------------------
    def add_site(self, domain: str, name: str) -> bool:
        domain = backend.normalize_domain(domain)
        if not domain:
            return False
        if any(domain in backend.domain_variants(s["domain"]) for s in self.sites):
            return False
        self.sites.append({"domain": domain, "name": name.strip() or domain})
        self.save()
        return True

    def remove_site(self, domain: str):
        self.sites = [s for s in self.sites if s["domain"] != domain]
        self.save()

    def finish_onboarding(self):
        self.onboarding_done = True
        self.save()

    def reset_onboarding(self):
        self.onboarding_done = False
        self.save()
