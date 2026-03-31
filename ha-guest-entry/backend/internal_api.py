"""Internal API: /internal/v1/* — called only by the companion integration."""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from aiohttp import web

from .config import load_users, save_users

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/config"))
SECRET_FILE = DATA_DIR / "internal_secret.txt"
SECRET_CONFIG_PATH = CONFIG_DIR / ".ha_guest_entry_secret"


def _load_or_create_secret() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    secret = secrets.token_hex(32)
    SECRET_FILE.write_text(secret)
    log.info("Generated internal secret: %s (copy to companion integration config)", secret)
    # Also write to /config so the companion integration can read it automatically
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SECRET_CONFIG_PATH.write_text(secret)
    except Exception as exc:
        log.warning("Could not write secret to config dir: %s", exc)
    return secret


_INTERNAL_SECRET: str | None = None


def internal_secret() -> str:
    global _INTERNAL_SECRET
    if _INTERNAL_SECRET is None:
        _INTERNAL_SECRET = _load_or_create_secret()
    return _INTERNAL_SECRET


@web.middleware
async def internal_auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/internal/"):
        return await handler(request)
    provided = request.headers.get("X-Internal-Secret", "")
    if not secrets.compare_digest(provided, internal_secret()):
        raise web.HTTPForbidden(reason="Invalid internal secret")
    return await handler(request)


async def handle_get_state(request: web.Request) -> web.Response:
    app = request.app
    users: list[dict] = app["users"]
    return web.json_response({
        "users": [
            {
                "id": u["id"],
                "username": u["username"],
                "display_name": u.get("display_name") or u["username"],
                "enabled": u.get("enabled", True),
                "entity_ids": [e["entity_id"] for e in u.get("allowed_entities", [])],
            }
            for u in users
        ],
    })


async def handle_set_user_access(request: web.Request) -> web.Response:
    app = request.app
    user_id = request.match_info["user_id"]

    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    enabled = bool(body.get("enabled", True))
    users: list[dict] = app["users"]
    user = next((u for u in users if u["id"] == user_id), None)
    if user is None:
        raise web.HTTPNotFound(reason="User not found")

    user["enabled"] = enabled
    save_users(users)
    log.info("User %s enabled=%s via internal API", user["username"], enabled)

    # When disabling a user, any outstanding JWT they hold is already blocked
    # by the enabled check in auth_middleware (reads live shared state).
    # No explicit blacklisting needed — the shared users list is updated in-place.

    return web.json_response({"ok": True})


async def handle_users_changed(request: web.Request) -> web.Response:
    """Reload users from disk — mutate in place so both apps see the update."""
    app = request.app
    new_users = load_users()
    current: list = app["users"]
    current.clear()
    current.extend(new_users)
    log.info("Users reloaded via webhook: %d users", len(current))
    return web.json_response({"ok": True, "user_count": len(current)})


async def handle_config_changed(request: web.Request) -> web.Response:
    """Reload app config from disk."""
    from .config import load_app_config
    app = request.app
    new_cfg = load_app_config()
    app["options"].update(new_cfg)
    # Update brute force protector limits
    bf = app["brute_force"]
    bf.max_ip_attempts = new_cfg.get("max_login_attempts", 5)
    bf.lockout_minutes = new_cfg.get("lockout_duration_minutes", 15)
    log.info("App config reloaded via webhook")
    return web.json_response({"ok": True})


def register_internal_routes(app: web.Application) -> None:
    app.router.add_get("/internal/v1/state", handle_get_state)
    app.router.add_post("/internal/v1/users/{user_id}/access", handle_set_user_access)
    app.router.add_post("/internal/v1/webhook/users-changed", handle_users_changed)
    app.router.add_post("/internal/v1/webhook/config-changed", handle_config_changed)
