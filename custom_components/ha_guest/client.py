"""HTTP client for the Guest Entry app's internal API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .exceptions import GuestEntryAuthError, GuestEntryConnectionError


class GuestEntryClient:
    """Talks to the Guest Entry app via its internal API."""

    def __init__(self, session: aiohttp.ClientSession, addon_url: str, secret: str) -> None:
        self._session = session
        self._base = addon_url.rstrip("/")
        self._secret = secret

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Secret": self._secret}

    async def get_state(self) -> dict[str, Any]:
        """GET /internal/v1/state — returns users list."""
        try:
            async with self._session.get(
                f"{self._base}/internal/v1/state",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 403:
                    raise GuestEntryAuthError("Invalid internal secret")
                resp.raise_for_status()
                return await resp.json()
        except GuestEntryAuthError:
            raise
        except aiohttp.ClientError as exc:
            raise GuestEntryConnectionError(str(exc)) from exc
        except asyncio.TimeoutError as exc:
            raise GuestEntryConnectionError("Request timed out") from exc

    async def set_user_access(self, user_id: str, enabled: bool) -> None:
        """POST /internal/v1/users/{id}/access"""
        try:
            async with self._session.post(
                f"{self._base}/internal/v1/users/{user_id}/access",
                headers=self._headers,
                json={"enabled": enabled},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 403:
                    raise GuestEntryAuthError("Invalid internal secret")
                resp.raise_for_status()
        except GuestEntryAuthError:
            raise
        except aiohttp.ClientError as exc:
            raise GuestEntryConnectionError(str(exc)) from exc
