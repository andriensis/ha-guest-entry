"""aiohttp application entry point — guest (7979) + admin (7980)."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

import aiohttp
from aiohttp import web

from .admin_api import admin_auth_middleware, register_admin_routes
from .api import auth_middleware, security_headers_middleware, register_routes
from .auth import load_blacklist
from .brute_force import BruteForceProtector
from .config import load_app_config, load_users
from .ha_client import HaClient
from .internal_api import internal_auth_middleware, internal_secret, register_internal_routes
from .ws_proxy import handle_ws

log = logging.getLogger(__name__)

GUEST_PORT = int(os.environ.get("PORT", 7979))
ADMIN_PORT = int(os.environ.get("ADMIN_PORT", 7980))
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


async def _register_discovery(session: aiohttp.ClientSession) -> None:
    """Register with Supervisor so HA auto-discovers the companion integration."""
    if not SUPERVISOR_TOKEN:
        return
    try:
        async with session.post(
            "http://supervisor/discovery",
            json={"service": "ha_guest", "config": {}},
            headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status == 200:
                log.info("Registered Supervisor discovery for ha_guest integration")
            else:
                log.warning("Discovery registration returned %d", resp.status)
    except Exception as exc:
        log.warning("Could not register Supervisor discovery: %s", exc)
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/config"))
STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


def _auto_install_integration() -> None:
    src = Path(__file__).parent.parent / "custom_components"
    if not src.exists():
        return
    dest = CONFIG_DIR / "custom_components"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        if (src / "ha_guest").exists():
            shutil.copytree(src / "ha_guest", dest / "ha_guest", dirs_exist_ok=True)
            log.info("Companion integration installed to %s", dest / "ha_guest")
    except Exception as exc:
        log.warning("Could not auto-install companion integration: %s", exc)


def _get_version() -> str:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with config_path.open() as f:
                return yaml.safe_load(f).get("version", "1.0.0")
        except Exception:
            pass
    return "1.0.0"


def _add_static_routes(app: web.Application, index_file: Path) -> None:
    """Serve an SPA: assets + SPA fallback."""
    async def serve_index(request: web.Request) -> web.Response:
        return web.FileResponse(index_file)

    app.router.add_get("/", serve_index)

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.router.add_static("/assets", assets_dir, follow_symlinks=False)

    for static_file in ("favicon.svg", "manifest.json", "sw.js"):
        if (STATIC_DIR / static_file).exists():
            f = STATIC_DIR / static_file
            app.router.add_get(f"/{static_file}", lambda req, _f=f: web.FileResponse(_f))

    app.router.add_route("GET", "/{path_info:(?!api/|internal/|admin/).*}", serve_index)


def create_guest_app(shared: dict) -> web.Application:
    app = web.Application(middlewares=[internal_auth_middleware, security_headers_middleware, auth_middleware])
    app["version"] = shared["version"]
    app["users"] = shared["users"]
    app["options"] = shared["app_config"]
    app["brute_force"] = shared["brute_force"]
    app["http_session"] = shared["http_session"]
    app["ha_client"] = shared["ha_client"]

    register_internal_routes(app)
    register_routes(app)
    app.router.add_get("/api/v1/ws", handle_ws)

    if STATIC_DIR.exists():
        index = STATIC_DIR / "index.html"
        if index.exists():
            _add_static_routes(app, index)

    return app


def create_admin_app(shared: dict) -> web.Application:
    app = web.Application(middlewares=[admin_auth_middleware])
    app["version"] = shared["version"]
    app["users"] = shared["users"]
    app["app_config"] = shared["app_config"]
    app["http_session"] = shared["http_session"]
    app["ha_client"] = shared["ha_client"]

    register_admin_routes(app)

    if STATIC_DIR.exists():
        admin_index = STATIC_DIR / "admin.html"
        if admin_index.exists():
            _add_static_routes(app, admin_index)

    return app


async def run() -> None:
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # --- Load shared state ---
    app_config = load_app_config()
    try:
        users = load_users()
    except Exception as exc:
        log.warning("Could not load users: %s", exc)
        users = []

    brute_force = BruteForceProtector(
        max_attempts=app_config.get("max_login_attempts", 5),
        lockout_minutes=app_config.get("lockout_duration_minutes", 15),
    )
    load_blacklist()

    http_session = aiohttp.ClientSession()
    ha_client = HaClient(http_session)
    version = _get_version()

    # users list is shared by reference between both apps
    shared = {
        "version": version,
        "users": users,
        "app_config": app_config,
        "brute_force": brute_force,
        "http_session": http_session,
        "ha_client": ha_client,
    }

    internal_secret()
    _auto_install_integration()
    await _register_discovery(http_session)

    guest_app = create_guest_app(shared)
    admin_app = create_admin_app(shared)

    guest_runner = web.AppRunner(guest_app)
    admin_runner = web.AppRunner(admin_app)

    await guest_runner.setup()
    await admin_runner.setup()

    guest_site = web.TCPSite(guest_runner, "0.0.0.0", GUEST_PORT)
    admin_site = web.TCPSite(admin_runner, "0.0.0.0", ADMIN_PORT)

    await guest_site.start()
    await admin_site.start()

    log.info("=" * 60)
    log.info("Guest Entry is running!")
    log.info("")
    log.info("  ADMIN PANEL  : Open the add-on via the HA sidebar or the")
    log.info("                 'Open Web UI' button on the add-on page.")
    log.info("                 Use it to create users and assign entities.")
    log.info("")
    log.info("  GUEST DASHBOARD: http://<your-ha-ip>:%d", GUEST_PORT)
    log.info("                 Share this URL with your guests.")
    log.info("=" * 60)

    try:
        await asyncio.Event().wait()
    finally:
        await http_session.close()
        await guest_runner.cleanup()
        await admin_runner.cleanup()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
