"""Guest-facing REST API endpoints: /api/v1/*"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from aiohttp import web

from .auth import AuthError, blacklist_jti, issue_token, verify_password, verify_token
from .brute_force import BruteForceProtector

log = logging.getLogger(__name__)

# Per-domain allowed actions
DOMAIN_ACTIONS: dict[str, set[str]] = {
    "light": {"turn_on", "turn_off", "toggle"},
    "switch": {"turn_on", "turn_off", "toggle"},
    "cover": {"open_cover", "close_cover", "stop_cover"},
    "climate": {"set_hvac_mode", "set_temperature"},
    "lock": {"lock", "unlock", "open"},
    "alarm_control_panel": {"alarm_disarm", "alarm_arm_home", "alarm_arm_away", "alarm_arm_night"},
}

# Normalised supported_features per domain (what the frontend should show)
DOMAIN_FEATURES: dict[str, list[str]] = {
    "light": ["brightness", "color_temp"],
    "switch": [],
    "cover": ["position"],
    "climate": ["hvac_mode", "temperature"],
    "lock": [],
    "alarm_control_panel": ["code_required"],
}


def _client_ip(request: web.Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote or "unknown"


def _filter_attributes(domain: str, attributes: dict) -> dict:
    """Return only the attributes relevant to the domain."""
    keep: dict = {}
    if domain == "light":
        for key in ("brightness", "color_temp_kelvin", "color_temp", "min_mireds", "max_mireds",
                    "min_color_temp_kelvin", "max_color_temp_kelvin", "supported_color_modes",
                    "color_mode"):
            if key in attributes:
                keep[key] = attributes[key]
        keep["supported_features"] = DOMAIN_FEATURES["light"]
    elif domain == "cover":
        for key in ("current_position", "current_tilt_position"):
            if key in attributes:
                keep[key] = attributes[key]
        keep["supported_features"] = DOMAIN_FEATURES["cover"]
    elif domain == "climate":
        for key in ("hvac_mode", "hvac_modes", "temperature", "current_temperature",
                    "target_temp_step", "min_temp", "max_temp"):
            if key in attributes:
                keep[key] = attributes[key]
        keep["supported_features"] = DOMAIN_FEATURES["climate"]
    elif domain == "alarm_control_panel":
        for key in ("code_format", "changed_by", "supported_features"):
            if key in attributes:
                keep[key] = attributes[key]
        # Expose whether a code is required for arming/disarming
        code_format = attributes.get("code_format")
        keep["code_required"] = bool(code_format)
        keep["code_format"] = code_format  # "number" | "text" | None
        keep["supported_features"] = DOMAIN_FEATURES["alarm_control_panel"]
    else:
        keep["supported_features"] = DOMAIN_FEATURES.get(domain, [])
    return keep


def _entity_response(ha_state: dict, allowed_entity: dict) -> dict:
    domain = ha_state["entity_id"].split(".")[0]
    return {
        "entity_id": ha_state["entity_id"],
        "name": ha_state.get("attributes", {}).get("friendly_name", ha_state["entity_id"]),
        "label": allowed_entity.get("label"),
        "domain": domain,
        "state": ha_state["state"],
        "attributes": _filter_attributes(domain, ha_state.get("attributes", {})),
        "last_changed": ha_state.get("last_changed"),
    }


# ---------------------------------------------------------------------------
# Middleware: security headers + CORS
# ---------------------------------------------------------------------------

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' ws: wss:; "
        "img-src 'self' data:; "
        "frame-ancestors 'none';"
    ),
}


@web.middleware
async def security_headers_middleware(request: web.Request, handler):
    # Block cross-origin API requests (CORS pre-flight and requests with Origin header)
    origin = request.headers.get("Origin")
    if origin and request.path.startswith("/api/"):
        host = request.headers.get("Host", "")
        # Respect X-Forwarded-Proto set by reverse proxies (Cloudflare, Nginx, etc.)
        scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        expected = f"{scheme}://{host}"
        if origin != expected:
            raise web.HTTPForbidden(reason="Cross-origin requests not allowed")

    response = await handler(request)
    for key, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


# ---------------------------------------------------------------------------
# Middleware: auth
# ---------------------------------------------------------------------------

@web.middleware
async def auth_middleware(request: web.Request, handler):
    # Only enforce auth on /api/v1/* routes (not static files, not internal API)
    if not request.path.startswith("/api/"):
        return await handler(request)
    public = {"/api/v1/health", "/api/v1/discover", "/api/v1/auth/login", "/api/v1/openapi.json", "/api/v1/ws"}
    if request.path in public:
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(reason="Missing Bearer token")

    token = auth_header[7:]
    try:
        payload = verify_token(token)
    except AuthError as exc:
        raise web.HTTPUnauthorized(reason=str(exc))

    # Attach user to request
    app = request.app
    users: list[dict] = app["users"]
    user = next((u for u in users if u["id"] == payload["sub"]), None)
    if user is None:
        raise web.HTTPUnauthorized(reason="User not found")
    if not user.get("enabled", True):
        raise web.HTTPForbidden(reason="User account disabled")

    request["user"] = user
    request["token_payload"] = payload
    return await handler(request)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "version": request.app["version"]})


async def handle_discover(request: web.Request) -> web.Response:
    app = request.app
    options = app["options"]
    return web.json_response({
        "server": "ha-guest-entry",
        "version": app["version"],
        "instance_name": options.get("instance_name", "My Home"),
        "capabilities": ["lights", "switches", "covers", "climate", "locks", "alarm_control_panel"],
        "auth_required": True,
    })


async def handle_login(request: web.Request) -> web.Response:
    app = request.app
    options = app["options"]
    brute: BruteForceProtector = app["brute_force"]
    ha_client = app["ha_client"]
    ip = _client_ip(request)

    # IP lockout check
    locked, retry_after = brute.is_ip_locked(ip)
    if locked:
        return web.json_response(
            {"error": "Too many attempts", "retry_after": retry_after}, status=423
        )

    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    username = body.get("username", "").strip().lower()
    password = body.get("password", "")

    if not username or not password:
        raise web.HTTPBadRequest(reason="username and password required")

    users: list[dict] = app["users"]
    user = next((u for u in users if u["username"].lower() == username), None)

    # Username lockout
    if user:
        user_locked, retry_after = brute.is_user_locked(username)
        if user_locked:
            return web.json_response(
                {"error": "Account suspended", "retry_after": retry_after}, status=423
            )

    # Validate credentials
    if user is None or not verify_password(password, user["password_hash"]):
        await brute.record_failure(ip, username, ha_client)
        raise web.HTTPUnauthorized(reason="Invalid credentials")

    if not user.get("enabled", True):
        return web.json_response({"error": "Account disabled"}, status=403)

    brute.record_success(ip, username)
    duration = options.get("session_duration_hours", 24)
    token, expires_at = issue_token(user, duration)

    return web.json_response({
        "token": token,
        "expires_at": expires_at.isoformat(),
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name", user["username"]),
        },
    })


async def handle_refresh(request: web.Request) -> web.Response:
    app = request.app
    options = app["options"]
    user = request["user"]
    old_payload = request["token_payload"]

    blacklist_jti(old_payload["jti"])
    duration = options.get("session_duration_hours", 24)
    token, expires_at = issue_token(user, duration)

    return web.json_response({
        "token": token,
        "expires_at": expires_at.isoformat(),
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name", user["username"]),
        },
    })


async def handle_logout(request: web.Request) -> web.Response:
    payload = request["token_payload"]
    blacklist_jti(payload["jti"])
    return web.json_response({"ok": True})


async def handle_entities(request: web.Request) -> web.Response:
    user = request["user"]
    ha_client = request.app["ha_client"]
    allowed = user.get("allowed_entities", [])

    entities = []
    for entry in allowed:
        entity_id = entry["entity_id"]
        try:
            ha_state = await ha_client.get_state(entity_id)
            entities.append(_entity_response(ha_state, entry))
        except Exception as exc:
            log.warning("Could not fetch state for %s: %s", entity_id, exc)
            # Include with unknown state rather than failing the whole request
            domain = entity_id.split(".")[0]
            entities.append({
                "entity_id": entity_id,
                "name": entity_id,
                "label": entry.get("label"),
                "domain": domain,
                "state": "unavailable",
                "attributes": {"supported_features": DOMAIN_FEATURES.get(domain, [])},
                "last_changed": None,
            })

    return web.json_response({"entities": entities})


async def handle_entity(request: web.Request) -> web.Response:
    user = request["user"]
    ha_client = request.app["ha_client"]
    entity_id = request.match_info["entity_id"]

    allowed = user.get("allowed_entities", [])
    allowed_entry = next((e for e in allowed if e["entity_id"] == entity_id), None)
    if allowed_entry is None:
        raise web.HTTPForbidden(reason="Entity not in your allow list")

    try:
        ha_state = await ha_client.get_state(entity_id)
    except Exception as exc:
        raise web.HTTPBadGateway(reason=str(exc))

    return web.json_response(_entity_response(ha_state, allowed_entry))


async def handle_entity_action(request: web.Request) -> web.Response:
    user = request["user"]
    ha_client = request.app["ha_client"]
    entity_id = request.match_info["entity_id"]

    allowed = user.get("allowed_entities", [])
    if not any(e["entity_id"] == entity_id for e in allowed):
        raise web.HTTPForbidden(reason="Entity not in your allow list")

    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    action = body.get("action", "")
    params = body.get("params", {})
    domain = entity_id.split(".")[0]

    allowed_actions = DOMAIN_ACTIONS.get(domain, set())
    if action not in allowed_actions:
        return web.json_response(
            {"error": f"Action '{action}' not allowed for domain '{domain}'",
             "allowed": list(allowed_actions)},
            status=422,
        )

    service_data = {"entity_id": entity_id, **params}
    try:
        await ha_client.call_service(domain, action, service_data)
    except Exception as exc:
        raise web.HTTPBadGateway(reason=str(exc))

    # Fetch updated state
    try:
        ha_state = await ha_client.get_state(entity_id)
        new_state = ha_state["state"]
    except Exception:
        new_state = "unknown"

    return web.json_response({"ok": True, "state": new_state})


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/v1/health", handle_health)
    app.router.add_get("/api/v1/discover", handle_discover)
    app.router.add_post("/api/v1/auth/login", handle_login)
    app.router.add_post("/api/v1/auth/refresh", handle_refresh)
    app.router.add_post("/api/v1/auth/logout", handle_logout)
    app.router.add_get("/api/v1/entities", handle_entities)
    app.router.add_get("/api/v1/entities/{entity_id}", handle_entity)
    app.router.add_post("/api/v1/entities/{entity_id}/action", handle_entity_action)
