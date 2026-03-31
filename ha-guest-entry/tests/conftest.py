"""Shared pytest fixtures."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator

# ---------------------------------------------------------------------------
# Set env vars BEFORE importing backend modules — module-level constants like
# DATA_DIR are evaluated at import time, so they must see the right values.
# ---------------------------------------------------------------------------
_TEST_TMPDIR = tempfile.mkdtemp(prefix="ha_guest_test_")
os.environ.setdefault("DATA_DIR", _TEST_TMPDIR)
os.environ.setdefault("CONFIG_DIR", _TEST_TMPDIR + "/config")
os.environ.setdefault("OPTIONS_FILE", _TEST_TMPDIR + "/options.json")
os.environ.setdefault("HA_BASE_URL", "http://localhost:8099/api")
os.environ.setdefault("HA_WS_URL", "ws://localhost:8099/websocket")
os.environ.setdefault("SUPERVISOR_TOKEN", "test-token")
os.environ.setdefault("PORT", "7979")

import pytest
import pytest_asyncio

from tests.mock_ha import MockHaServer
from aiohttp.test_utils import TestClient, TestServer
from backend.main import create_app


@pytest_asyncio.fixture(scope="session")
async def mock_ha() -> AsyncGenerator[MockHaServer, None]:
    server = MockHaServer(port=8099)
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
def tmp_data(tmp_path):
    """Return a fresh temp data dir and update env vars for this test."""
    os.environ["DATA_DIR"] = str(tmp_path)
    os.environ["OPTIONS_FILE"] = str(tmp_path / "options.json")
    return tmp_path


@pytest.fixture
def alice_user():
    return {
        "username": "alice",
        "password": "password123",
        "display_name": "Alice",
        "enabled": True,
        "allowed_entities": [
            {"entity_id": "light.living_room", "label": "Living Room"},
            {"entity_id": "switch.tv", "label": None},
        ],
    }


@pytest.fixture
def bob_user():
    return {
        "username": "bob",
        "password": "bobsecret",
        "display_name": "Bob",
        "enabled": True,
        "allowed_entities": [
            {"entity_id": "light.bedroom", "label": "Bedroom"},
        ],
    }


@pytest.fixture
def options_with_users(tmp_data, alice_user, bob_user):
    opts = {
        "instance_name": "Test Home",
        "session_duration_hours": 1,
        "max_login_attempts": 5,
        "lockout_duration_minutes": 1,
        "users": [alice_user, bob_user],
    }
    (tmp_data / "options.json").write_text(json.dumps(opts))
    return opts


# ---------------------------------------------------------------------------
# App fixture (integration tests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def app_client(mock_ha, options_with_users, tmp_data) -> AsyncGenerator[TestClient, None]:
    """Full aiohttp test client wired to mock HA."""
    # Reload modules so their module-level constants pick up the per-test DATA_DIR
    import importlib
    import backend.config as cfg_mod
    import backend.auth as auth_mod
    import backend.ha_client as ha_mod
    import backend.brute_force as bf_mod
    import backend.internal_api as int_mod

    for mod in (cfg_mod, auth_mod, ha_mod, bf_mod, int_mod):
        importlib.reload(mod)

    app = create_app()
    client = TestClient(TestServer(app))
    await client.start_server()
    yield client
    await client.close()


@pytest_asyncio.fixture
async def alice_token(app_client) -> str:
    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    data = await resp.json()
    return data["token"]


@pytest_asyncio.fixture
async def bob_token(app_client) -> str:
    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "bobsecret"},
    )
    data = await resp.json()
    return data["token"]
