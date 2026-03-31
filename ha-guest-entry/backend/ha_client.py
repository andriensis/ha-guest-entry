"""Home Assistant REST + WebSocket client."""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

log = logging.getLogger(__name__)

HA_BASE_URL = os.environ.get("HA_BASE_URL", "http://supervisor/core/api")
HA_WS_URL = os.environ.get("HA_WS_URL", "ws://supervisor/core/websocket")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


class HaClientError(Exception):
    pass


class HaClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._base_url = HA_BASE_URL.rstrip("/")
        self._ws_url = HA_WS_URL
        self._token = SUPERVISOR_TOKEN

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # REST
    # ------------------------------------------------------------------

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        url = f"{self._base_url}/states/{entity_id}"
        async with self._session.get(url, headers=self._headers) as resp:
            if resp.status == 404:
                raise HaClientError(f"Entity not found: {entity_id}")
            resp.raise_for_status()
            return await resp.json()

    async def get_states(self) -> list[dict[str, Any]]:
        url = f"{self._base_url}/states"
        async with self._session.get(url, headers=self._headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def call_service(self, domain: str, service: str, data: dict | None = None) -> list:
        url = f"{self._base_url}/services/{domain}/{service}"
        async with self._session.post(url, headers=self._headers, json=data or {}) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def notify(self, message: str, title: str = "Guest Dashboard") -> None:
        try:
            await self.call_service(
                "persistent_notification",
                "create",
                {"message": message, "title": title},
            )
        except Exception as exc:
            log.warning("Failed to send HA notification: %s", exc)

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------

    async def ws_connect(self) -> aiohttp.ClientWebSocketResponse:
        ws = await self._session.ws_connect(self._ws_url)
        # Auth handshake
        auth_required = await ws.receive_json()
        assert auth_required.get("type") == "auth_required"
        await ws.send_json({"type": "auth", "access_token": self._token})
        auth_ok = await ws.receive_json()
        if auth_ok.get("type") != "auth_ok":
            await ws.close()
            raise HaClientError("WebSocket authentication failed")
        return ws
