"""Lightweight mock Home Assistant REST + WebSocket server for tests and local dev."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiohttp import WSMsgType, web

log = logging.getLogger(__name__)

# Default entity states used by tests
DEFAULT_STATES: list[dict[str, Any]] = [
    {
        "entity_id": "light.living_room",
        "state": "on",
        "attributes": {
            "friendly_name": "Living Room Light",
            "brightness": 200,
            "color_temp_kelvin": 4000,
            "supported_color_modes": ["color_temp"],
            "color_mode": "color_temp",
        },
        "last_changed": "2026-03-29T10:00:00+00:00",
    },
    {
        "entity_id": "switch.tv",
        "state": "off",
        "attributes": {"friendly_name": "TV"},
        "last_changed": "2026-03-29T09:00:00+00:00",
    },
    {
        "entity_id": "cover.garage_door",
        "state": "closed",
        "attributes": {"friendly_name": "Garage Door", "current_position": 0},
        "last_changed": "2026-03-29T08:00:00+00:00",
    },
    {
        "entity_id": "climate.living_room",
        "state": "heat",
        "attributes": {
            "friendly_name": "Living Room AC",
            "hvac_mode": "heat",
            "hvac_modes": ["off", "heat", "cool", "auto"],
            "temperature": 21.5,
            "current_temperature": 19.0,
            "min_temp": 16,
            "max_temp": 30,
            "target_temp_step": 0.5,
        },
        "last_changed": "2026-03-29T08:00:00+00:00",
    },
    {
        "entity_id": "lock.front_door",
        "state": "locked",
        "attributes": {"friendly_name": "Front Door"},
        "last_changed": "2026-03-29T07:00:00+00:00",
    },
    {
        "entity_id": "light.bedroom",
        "state": "off",
        "attributes": {"friendly_name": "Bedroom Light", "brightness": 0},
        "last_changed": "2026-03-29T07:00:00+00:00",
    },
    {
        "entity_id": "switch.fan",
        "state": "on",
        "attributes": {"friendly_name": "Fan"},
        "last_changed": "2026-03-29T06:00:00+00:00",
    },
]


class MockHaServer:
    """Embeddable mock HA server. Call .start() / .stop()."""

    def __init__(self, port: int = 8099) -> None:
        self.port = port
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._states: dict[str, dict] = {s["entity_id"]: s for s in DEFAULT_STATES}
        self._service_calls: list[dict] = []
        self._ws_clients: list[web.WebSocketResponse] = []
        self._ws_msg_id = 1
        self._setup_routes()

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://localhost:{self.port}/websocket"

    @property
    def service_calls(self) -> list[dict]:
        return list(self._service_calls)

    def set_state(self, entity_id: str, state: str, attributes: dict | None = None) -> None:
        if entity_id in self._states:
            self._states[entity_id]["state"] = state
            if attributes:
                self._states[entity_id]["attributes"].update(attributes)
        else:
            self._states[entity_id] = {
                "entity_id": entity_id,
                "state": state,
                "attributes": attributes or {},
                "last_changed": "2026-03-29T10:00:00+00:00",
            }

    def clear_service_calls(self) -> None:
        self._service_calls.clear()

    async def push_state_changed(self, entity_id: str, new_state: str) -> None:
        """Push a state_changed event to all connected WS clients."""
        if entity_id in self._states:
            self._states[entity_id]["state"] = new_state

        event_msg = {
            "id": self._ws_msg_id,
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {
                    "entity_id": entity_id,
                    "new_state": self._states.get(entity_id, {
                        "entity_id": entity_id,
                        "state": new_state,
                        "attributes": {},
                        "last_changed": "2026-03-29T10:05:00+00:00",
                    }),
                },
            },
        }
        self._ws_msg_id += 1
        for ws in list(self._ws_clients):
            if not ws.closed:
                await ws.send_json(event_msg)

    def _setup_routes(self) -> None:
        self._app.router.add_get("/api/states", self._handle_get_states)
        self._app.router.add_get("/api/states/{entity_id}", self._handle_get_state)
        self._app.router.add_post("/api/services/{domain}/{service}", self._handle_service)
        self._app.router.add_post("/api/services/persistent_notification/create", self._handle_notify)
        self._app.router.add_get("/websocket", self._handle_websocket)

    async def _handle_get_states(self, request: web.Request) -> web.Response:
        return web.json_response(list(self._states.values()))

    async def _handle_get_state(self, request: web.Request) -> web.Response:
        entity_id = request.match_info["entity_id"]
        if entity_id not in self._states:
            raise web.HTTPNotFound()
        return web.json_response(self._states[entity_id])

    async def _handle_service(self, request: web.Request) -> web.Response:
        domain = request.match_info["domain"]
        service = request.match_info["service"]
        try:
            body = await request.json()
        except Exception:
            body = {}
        self._service_calls.append({"domain": domain, "service": service, "data": body})
        log.debug("Service call: %s.%s %s", domain, service, body)
        # Update state optimistically
        entity_id = body.get("entity_id")
        if entity_id and entity_id in self._states:
            if service == "turn_on":
                self._states[entity_id]["state"] = "on"
            elif service == "turn_off":
                self._states[entity_id]["state"] = "off"
            elif service == "toggle":
                current = self._states[entity_id]["state"]
                self._states[entity_id]["state"] = "off" if current == "on" else "on"
        return web.json_response([])

    async def _handle_notify(self, request: web.Request) -> web.Response:
        return web.json_response([])

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.append(ws)

        # Send auth_required
        await ws.send_json({"type": "auth_required", "ha_version": "2024.1.0"})

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")
                    msg_id = data.get("id")

                    if msg_type == "auth":
                        await ws.send_json({"type": "auth_ok", "ha_version": "2024.1.0"})
                    elif msg_type == "subscribe_events":
                        await ws.send_json({
                            "id": msg_id,
                            "type": "result",
                            "success": True,
                            "result": None,
                        })
                elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                    break
        finally:
            self._ws_clients.remove(ws)

        return ws

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "localhost", self.port)
        await site.start()
        log.info("Mock HA server started on %s", self.base_url)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            log.info("Mock HA server stopped")


# ---------------------------------------------------------------------------
# Standalone entrypoint for local dev
# ---------------------------------------------------------------------------

async def _run_standalone() -> None:
    import signal

    server = MockHaServer(port=8099)
    await server.start()
    print(f"Mock HA server running at {server.base_url}")
    print(f"WebSocket: {server.ws_url}")
    print("Ctrl+C to stop")

    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGINT, stop.set_result, None)
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)
    await stop
    await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_standalone())
