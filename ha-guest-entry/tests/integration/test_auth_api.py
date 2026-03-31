"""Integration tests: auth endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_success(app_client):
    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "token" in data
    assert data["user"]["username"] == "alice"
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_login_wrong_password(app_client):
    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "wrongpassword"},
    )
    assert resp.status == 401


@pytest.mark.asyncio
async def test_login_unknown_user(app_client):
    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "pass"},
    )
    assert resp.status == 401


@pytest.mark.asyncio
async def test_login_missing_fields(app_client):
    resp = await app_client.post("/api/v1/auth/login", json={"username": "alice"})
    assert resp.status == 400


@pytest.mark.asyncio
async def test_refresh_token(app_client, alice_token):
    resp = await app_client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "token" in data
    new_token = data["token"]
    assert new_token != alice_token


@pytest.mark.asyncio
async def test_old_token_blacklisted_after_refresh(app_client, alice_token):
    resp = await app_client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 200

    # Old token should now be blacklisted
    resp2 = await app_client.get(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp2.status == 401


@pytest.mark.asyncio
async def test_logout(app_client, alice_token):
    resp = await app_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_token_unusable_after_logout(app_client, alice_token):
    await app_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    resp = await app_client.get(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 401


@pytest.mark.asyncio
async def test_health(app_client):
    resp = await app_client.get("/api/v1/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_discover(app_client):
    resp = await app_client.get("/api/v1/discover")
    assert resp.status == 200
    data = await resp.json()
    assert data["server"] == "ha-guest-entry"
    assert "guest_access_enabled" in data
