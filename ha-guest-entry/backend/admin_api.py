"""Admin API: /admin/api/* — served on the admin port (7980), ingress only."""

from __future__ import annotations

import logging
import os
import uuid

import bcrypt
from aiohttp import web

from .config import load_app_config, load_users, save_app_config, save_users
from .internal_api import internal_secret

log = logging.getLogger(__name__)

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
SUPPORTED_DOMAINS = {"light", "switch", "cover", "climate", "lock", "alarm_control_panel"}

DOMAIN_ICONS = {
    "light": "💡",
    "switch": "🔌",
    "cover": "🪟",
    "climate": "🌡️",
    "lock": "🔒",
    "alarm_control_panel": "🚨",
}


@web.middleware
async def admin_auth_middleware(request: web.Request, handler):
    """Admin port (7980) is only reachable via HA ingress (not in ports: mapping),
    so HA's own session auth is the security boundary. No additional check needed."""
    return await handler(request)


async def handle_admin_status(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "version": request.app["version"]})


async def handle_get_config(request: web.Request) -> web.Response:
    return web.json_response(request.app["app_config"])


async def handle_put_config(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    cfg = request.app["app_config"]
    for key in ("instance_name", "session_duration_hours", "max_login_attempts", "lockout_duration_minutes"):
        if key in body:
            cfg[key] = body[key]
    save_app_config(cfg)
    request.app["app_config"] = cfg
    # Propagate to guest app
    await _notify_guest(request, "/internal/v1/webhook/config-changed")
    return web.json_response({"ok": True})


async def handle_get_users(request: web.Request) -> web.Response:
    users = request.app["users"]
    return web.json_response({
        "users": [_user_public(u) for u in users]
    })


async def handle_create_user(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    username = (body.get("username") or "").strip().lower()
    password = body.get("password") or ""
    if not username or not password:
        raise web.HTTPBadRequest(reason="username and password required")

    users: list[dict] = request.app["users"]
    if any(u["username"].lower() == username for u in users):
        raise web.HTTPConflict(reason="Username already exists")

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    new_user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "password_hash": password_hash,
        "display_name": (body.get("display_name") or "").strip() or username,
        "enabled": bool(body.get("enabled", True)),
        "allowed_entities": _parse_entities(body.get("allowed_entities") or []),
    }
    users.append(new_user)
    save_users(users)
    await _notify_guest(request, "/internal/v1/webhook/users-changed")
    return web.json_response(_user_public(new_user), status=201)


async def handle_update_user(request: web.Request) -> web.Response:
    user_id = request.match_info["user_id"]
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    users: list[dict] = request.app["users"]
    user = next((u for u in users if u["id"] == user_id), None)
    if user is None:
        raise web.HTTPNotFound(reason="User not found")

    if "display_name" in body:
        user["display_name"] = (body["display_name"] or "").strip() or user["username"]
    if "enabled" in body:
        user["enabled"] = bool(body["enabled"])
    if "password" in body and body["password"]:
        user["password_hash"] = bcrypt.hashpw(body["password"].encode(), bcrypt.gensalt(rounds=12)).decode()
    if "allowed_entities" in body:
        if not isinstance(body["allowed_entities"], list):
            raise web.HTTPBadRequest(reason="allowed_entities must be a list")
        user["allowed_entities"] = _parse_entities(body["allowed_entities"])

    save_users(users)
    await _notify_guest(request, "/internal/v1/webhook/users-changed")
    return web.json_response(_user_public(user))


async def handle_delete_user(request: web.Request) -> web.Response:
    user_id = request.match_info["user_id"]
    users: list[dict] = request.app["users"]
    idx = next((i for i, u in enumerate(users) if u["id"] == user_id), None)
    if idx is None:
        raise web.HTTPNotFound(reason="User not found")
    users.pop(idx)
    save_users(users)
    await _notify_guest(request, "/internal/v1/webhook/users-changed")
    return web.json_response({"ok": True})


async def handle_get_entities(request: web.Request) -> web.Response:
    ha_client = request.app["ha_client"]
    try:
        all_states = await ha_client.get_states()
    except Exception as exc:
        raise web.HTTPBadGateway(reason=f"Could not fetch HA entities: {exc}")

    entities = []
    for s in all_states:
        domain = s["entity_id"].split(".")[0]
        if domain not in SUPPORTED_DOMAINS:
            continue
        entities.append({
            "entity_id": s["entity_id"],
            "name": s.get("attributes", {}).get("friendly_name", s["entity_id"]),
            "domain": domain,
            "state": s["state"],
        })

    entities.sort(key=lambda e: (e["domain"], e["name"].lower()))
    return web.json_response({"entities": entities})




async def _notify_guest(request: web.Request, path: str, method: str = "POST", json: dict | None = None) -> None:
    """Fire-and-forget call to the guest app's internal API."""
    session = request.app["http_session"]
    secret = internal_secret()
    try:
        async with session.request(
            method,
            f"http://localhost:7979{path}",
            headers={"X-Internal-Secret": secret},
            json=json or {},
        ) as resp:
            if resp.status not in (200, 204):
                log.warning("Guest app webhook %s returned %d", path, resp.status)
    except Exception as exc:
        log.warning("Could not notify guest app (%s): %s", path, exc)


def _parse_entities(raw: list) -> list[dict]:
    """Accept either plain entity_id strings or {entity_id, label} dicts."""
    result = []
    for e in raw:
        if isinstance(e, str):
            result.append({"entity_id": e, "label": None})
        elif isinstance(e, dict) and isinstance(e.get("entity_id"), str):
            result.append({"entity_id": e["entity_id"], "label": e.get("label") or None})
    return result


def _user_public(u: dict) -> dict:
    return {
        "id": u["id"],
        "username": u["username"],
        "display_name": u.get("display_name") or u["username"],
        "enabled": u.get("enabled", True),
        "allowed_entities": [
            {"entity_id": e["entity_id"], "label": e.get("label") or None}
            for e in u.get("allowed_entities", [])
        ],
    }


def register_admin_routes(app: web.Application) -> None:
    app.router.add_get("/admin/api/status", handle_admin_status)
    app.router.add_get("/admin/api/config", handle_get_config)
    app.router.add_put("/admin/api/config", handle_put_config)
    app.router.add_get("/admin/api/users", handle_get_users)
    app.router.add_post("/admin/api/users", handle_create_user)
    app.router.add_put("/admin/api/users/{user_id}", handle_update_user)
    app.router.add_delete("/admin/api/users/{user_id}", handle_delete_user)
    app.router.add_get("/admin/api/entities", handle_get_entities)
