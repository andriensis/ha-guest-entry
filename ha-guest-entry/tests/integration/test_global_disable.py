"""Integration tests: global guest access disable."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_discover_shows_disabled(app_client):
    # Disable global access via internal API
    from backend.internal_api import internal_secret
    secret = internal_secret()

    await app_client.post(
        "/internal/v1/access",
        json={"enabled": False},
        headers={"X-Internal-Secret": secret},
    )

    resp = await app_client.get("/api/v1/discover")
    data = await resp.json()
    assert data["guest_access_enabled"] is False

    # Re-enable for other tests
    await app_client.post(
        "/internal/v1/access",
        json={"enabled": True},
        headers={"X-Internal-Secret": secret},
    )


@pytest.mark.asyncio
async def test_login_returns_503_when_disabled(app_client):
    from backend.internal_api import internal_secret
    secret = internal_secret()

    await app_client.post(
        "/internal/v1/access",
        json={"enabled": False},
        headers={"X-Internal-Secret": secret},
    )

    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    assert resp.status == 503

    # Re-enable
    await app_client.post(
        "/internal/v1/access",
        json={"enabled": True},
        headers={"X-Internal-Secret": secret},
    )
