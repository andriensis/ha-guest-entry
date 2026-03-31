"""Per-IP and per-username brute-force protection."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ha_client import HaClient

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
LOCKOUTS_FILE = DATA_DIR / "lockouts.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BruteForceProtector:
    def __init__(self, max_attempts: int = 5, lockout_minutes: int = 15) -> None:
        self.max_ip_attempts = max_attempts
        self.lockout_minutes = lockout_minutes
        self.max_user_attempts = 10
        self.user_lockout_hours = 1

        # { ip: {"count": int, "until": datetime | None, "last": datetime} }
        self._ip: dict[str, dict] = {}
        # { username: {"count": int, "suspended": bool, "until": datetime | None} }
        self._users: dict[str, dict] = {}

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not LOCKOUTS_FILE.exists():
            return
        try:
            with LOCKOUTS_FILE.open() as f:
                data = json.load(f)
            for ip, v in data.get("ips", {}).items():
                self._ip[ip] = {
                    "count": v.get("count", 0),
                    "until": datetime.fromisoformat(v["until"]) if v.get("until") else None,
                }
            for username, v in data.get("users", {}).items():
                self._users[username] = {
                    "count": v.get("count", 0),
                    "suspended": v.get("suspended", False),
                    "until": datetime.fromisoformat(v["until"]) if v.get("until") else None,
                }
        except Exception as exc:
            log.warning("Could not load lockouts: %s", exc)

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "ips": {
                ip: {
                    "count": v["count"],
                    "until": v["until"].isoformat() if v["until"] else None,
                }
                for ip, v in self._ip.items()
            },
            "users": {
                u: {
                    "count": v["count"],
                    "suspended": v["suspended"],
                    "until": v["until"].isoformat() if v.get("until") else None,
                }
                for u, v in self._users.items()
            },
        }
        with LOCKOUTS_FILE.open("w") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_ip_locked(self, ip: str) -> tuple[bool, int]:
        """Return (locked, retry_after_seconds)."""
        entry = self._ip.get(ip)
        if not entry:
            return False, 0
        until = entry.get("until")
        if until and _now() < until:
            return True, int((until - _now()).total_seconds())
        # Auto-clear expired lockout
        if until and _now() >= until:
            entry["count"] = 0
            entry["until"] = None
            self._save()
        return False, 0

    def is_user_locked(self, username: str) -> tuple[bool, int]:
        entry = self._users.get(username)
        if not entry:
            return False, 0
        if not entry.get("suspended"):
            return False, 0
        until = entry.get("until")
        if until and _now() < until:
            return True, int((until - _now()).total_seconds())
        # Auto-clear
        entry["suspended"] = False
        entry["count"] = 0
        entry["until"] = None
        self._save()
        return False, 0

    def progressive_delay(self, ip: str) -> float:
        """Return seconds to wait based on failed attempt count for this IP."""
        entry = self._ip.get(ip, {})
        count = entry.get("count", 0)
        if count <= 0:
            return 0.0
        return min(2 ** (count - 1), 16)

    async def record_failure(self, ip: str, username: str, ha_client: "HaClient | None" = None) -> None:
        delay = self.progressive_delay(ip)
        if delay > 0:
            await asyncio.sleep(delay)

        # Per-IP
        ip_entry = self._ip.setdefault(ip, {"count": 0, "until": None})
        ip_entry["count"] += 1
        if ip_entry["count"] >= self.max_ip_attempts and not ip_entry["until"]:
            ip_entry["until"] = _now() + timedelta(minutes=self.lockout_minutes)
            log.warning("IP %s locked out until %s", ip, ip_entry["until"])
            if ha_client:
                await ha_client.notify(
                    f"Guest Dashboard: IP {ip} locked out after {ip_entry['count']} failed attempts."
                )

        # Per-username
        u_entry = self._users.setdefault(username, {"count": 0, "suspended": False, "until": None})
        u_entry["count"] += 1
        if u_entry["count"] >= self.max_user_attempts and not u_entry.get("suspended"):
            u_entry["suspended"] = True
            u_entry["until"] = _now() + timedelta(hours=self.user_lockout_hours)
            log.warning("User %s suspended until %s", username, u_entry["until"])
            if ha_client:
                await ha_client.notify(
                    f"Guest Dashboard: User '{username}' suspended after too many failed logins."
                )

        self._save()

    def record_success(self, ip: str, username: str) -> None:
        """Clear failure counters on successful login."""
        if ip in self._ip:
            self._ip[ip] = {"count": 0, "until": None}
        if username in self._users:
            self._users[username]["count"] = 0
        self._save()
