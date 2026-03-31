"""Integration tests: entity endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_entities_returns_allowed_only(app_client, alice_token):
    resp = await app_client.get(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 200
    data = await resp.json()
    entity_ids = [e["entity_id"] for e in data["entities"]]
    assert "light.living_room" in entity_ids
    assert "switch.tv" in entity_ids
    # Bedroom belongs to Bob, not Alice
    assert "light.bedroom" not in entity_ids


@pytest.mark.asyncio
async def test_get_entities_no_auth(app_client):
    resp = await app_client.get("/api/v1/entities")
    assert resp.status == 401


@pytest.mark.asyncio
async def test_get_single_entity_allowed(app_client, alice_token):
    resp = await app_client.get(
        "/api/v1/entities/light.living_room",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["entity_id"] == "light.living_room"
    assert "state" in data
    assert "domain" in data


@pytest.mark.asyncio
async def test_get_single_entity_forbidden(app_client, alice_token):
    # light.bedroom is Bob's, not Alice's
    resp = await app_client.get(
        "/api/v1/entities/light.bedroom",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 403


@pytest.mark.asyncio
async def test_entity_action_allowed(app_client, alice_token, mock_ha):
    mock_ha.clear_service_calls()
    resp = await app_client.post(
        "/api/v1/entities/light.living_room/action",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"action": "turn_off"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True
    # Verify service call reached mock HA
    calls = mock_ha.service_calls
    assert any(c["service"] == "turn_off" for c in calls)


@pytest.mark.asyncio
async def test_entity_action_forbidden(app_client, alice_token):
    resp = await app_client.post(
        "/api/v1/entities/light.bedroom/action",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"action": "turn_on"},
    )
    assert resp.status == 403


@pytest.mark.asyncio
async def test_entity_action_invalid_for_domain(app_client, alice_token):
    resp = await app_client.post(
        "/api/v1/entities/switch.tv/action",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"action": "open_cover"},  # cover action on switch domain
    )
    assert resp.status == 422


@pytest.mark.asyncio
async def test_entity_label_in_response(app_client, alice_token):
    resp = await app_client.get(
        "/api/v1/entities/light.living_room",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    data = await resp.json()
    assert data["label"] == "Living Room"
