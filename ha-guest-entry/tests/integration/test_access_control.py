"""Integration tests: user isolation — user A cannot see user B's entities."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_alice_cannot_see_bobs_entity(app_client, alice_token):
    resp = await app_client.get(
        "/api/v1/entities/light.bedroom",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 403


@pytest.mark.asyncio
async def test_bob_cannot_see_alices_entity(app_client, bob_token):
    resp = await app_client.get(
        "/api/v1/entities/light.living_room",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert resp.status == 403


@pytest.mark.asyncio
async def test_alice_entity_list_excludes_bobs_entities(app_client, alice_token):
    resp = await app_client.get(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status == 200
    data = await resp.json()
    ids = [e["entity_id"] for e in data["entities"]]
    assert "light.bedroom" not in ids  # Bob's


@pytest.mark.asyncio
async def test_bob_entity_list_excludes_alices_entities(app_client, bob_token):
    resp = await app_client.get(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert resp.status == 200
    data = await resp.json()
    ids = [e["entity_id"] for e in data["entities"]]
    assert "light.living_room" not in ids
    assert "switch.tv" not in ids


@pytest.mark.asyncio
async def test_alice_cannot_act_on_bobs_entity(app_client, alice_token):
    resp = await app_client.post(
        "/api/v1/entities/light.bedroom/action",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"action": "turn_on"},
    )
    assert resp.status == 403


@pytest.mark.asyncio
async def test_bob_cannot_act_on_alices_entity(app_client, bob_token):
    resp = await app_client.post(
        "/api/v1/entities/switch.tv/action",
        headers={"Authorization": f"Bearer {bob_token}"},
        json={"action": "turn_on"},
    )
    assert resp.status == 403
