"""Integration tests: brute-force lockout."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_ip_locked_after_max_attempts(app_client):
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        for _ in range(5):
            await app_client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "wrong"},
                headers={"X-Forwarded-For": "10.0.0.1"},
            )

    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "wrong"},
        headers={"X-Forwarded-For": "10.0.0.1"},
    )
    assert resp.status == 423
    data = await resp.json()
    assert "retry_after" in data


@pytest.mark.asyncio
async def test_different_ips_independent(app_client):
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        for _ in range(5):
            await app_client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "wrong"},
                headers={"X-Forwarded-For": "10.0.0.2"},
            )

    # Different IP should not be locked
    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "password123"},
        headers={"X-Forwarded-For": "10.0.0.99"},
    )
    assert resp.status == 200
