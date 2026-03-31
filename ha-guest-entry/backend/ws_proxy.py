"""WebSocket proxy: subscribes to HA, filters events to per-user allowed entities."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiohttp import WSMsgType, web

from .auth import AuthError, verify_token
from .ha_client import HaClient, HaClientError

log = logging.getLogger(__name__)

_MSG_ID = 0


def _next_id() -> int:
    global _MSG_ID
    _MSG_ID += 1
    return _MSG_ID


async def handle_ws(request: web.Request) -> web.WebSocketResponse:
    app = request.app
    users: list[dict] = app["users"]
    ha_client: HaClient = app["ha_client"]

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    # -- Auth: header (server-to-server) or first message (browser WebSocket) --
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        # Browsers cannot set custom WS headers — read token from first message
        try:
            first = await asyncio.wait_for(ws.receive(), timeout=10)
            if first.type == WSMsgType.TEXT:
                data = json.loads(first.data)
                if data.get("type") == "auth":
                    token = data.get("token")
        except (asyncio.TimeoutError, Exception):
            pass

    if not token:
        await ws.send_json({"type": "error", "message": "Authentication required"})
        await ws.close()
        return ws

    try:
        payload = verify_token(token)
    except AuthError as exc:
        await ws.send_json({"type": "error", "message": str(exc)})
        await ws.close()
        return ws

    user = next((u for u in users if u["id"] == payload["sub"]), None)
    if user is None or not user.get("enabled", True):
        await ws.send_json({"type": "access_revoked", "reason": "user_disabled"})
        await ws.close()
        return ws

    allowed_ids = {e["entity_id"] for e in user.get("allowed_entities", [])}
    log.debug("WS connected: user=%s entities=%s", user["username"], allowed_ids)

    # Connect to HA WebSocket
    try:
        ha_ws = await ha_client.ws_connect()
    except HaClientError as exc:
        await ws.send_json({"type": "error", "message": f"HA connection failed: {exc}"})
        await ws.close()
        return ws

    # Subscribe to state_changed events
    msg_id = _next_id()
    await ha_ws.send_json({
        "id": msg_id,
        "type": "subscribe_events",
        "event_type": "state_changed",
    })

    async def _forward_ha_events() -> None:
        async for msg in ha_ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    continue

                if data.get("type") != "event":
                    continue

                event_data = data.get("event", {}).get("data", {})
                entity_id = event_data.get("entity_id", "")
                if entity_id not in allowed_ids:
                    continue

                new_state = event_data.get("new_state") or {}
                await ws.send_json({
                    "type": "state_changed",
                    "entity_id": entity_id,
                    "state": new_state.get("state"),
                    "attributes": new_state.get("attributes", {}),
                    "changed_at": new_state.get("last_changed"),
                })
            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break

    async def _handle_client_messages() -> None:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    continue
                if data.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break

    # Check for revoked access while connected
    async def _watch_access() -> None:
        while not ws.closed:
            await asyncio.sleep(10)
            current_users: list[dict] = app["users"]
            current_user = next((u for u in current_users if u["id"] == user["id"]), None)
            if current_user is None or not current_user.get("enabled", True):
                await ws.send_json({"type": "access_revoked", "reason": "user_disabled"})
                await ws.close()
                return

    tasks = [
        asyncio.ensure_future(_forward_ha_events()),
        asyncio.ensure_future(_handle_client_messages()),
        asyncio.ensure_future(_watch_access()),
    ]

    try:
        await asyncio.gather(*tasks)
    except Exception as exc:
        log.debug("WS session ended: %s", exc)
    finally:
        for t in tasks:
            t.cancel()
        if not ha_ws.closed:
            await ha_ws.close()

    return ws
