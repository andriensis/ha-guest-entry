"""Unit tests for config.py: options loading, password hashing."""

from __future__ import annotations

import json

import bcrypt
import pytest

from backend.config import load_options, load_state, save_state, save_users, sync_users


def _write_options(path, users):
    opts = {
        "instance_name": "Test",
        "session_duration_hours": 1,
        "max_login_attempts": 5,
        "lockout_duration_minutes": 15,
        "users": users,
    }
    (path / "options.json").write_text(json.dumps(opts))
    return opts


def test_load_options(tmp_data):
    _write_options(tmp_data, [])
    opts = load_options()
    assert opts["instance_name"] == "Test"


def test_load_options_missing(tmp_data):
    from backend.config import ConfigError
    with pytest.raises(ConfigError):
        load_options()


def test_sync_users_hashes_passwords(tmp_data):
    opts = _write_options(tmp_data, [
        {
            "username": "alice",
            "password": "hunter2",
            "display_name": "Alice",
            "enabled": True,
            "allowed_entities": [],
        }
    ])
    users = sync_users(opts)
    assert len(users) == 1
    alice = users[0]
    assert alice["username"] == "alice"
    assert alice["password_hash"].startswith("$2b$")
    assert bcrypt.checkpw(b"hunter2", alice["password_hash"].encode())


def test_sync_users_preserves_existing_hash(tmp_data):
    import bcrypt as _bcrypt
    existing_hash = _bcrypt.hashpw(b"mypassword", _bcrypt.gensalt(rounds=4)).decode()
    users_data = {
        "users": [{
            "id": "uuid-123",
            "username": "bob",
            "password_hash": existing_hash,
            "display_name": "Bob",
            "enabled": True,
            "allowed_entities": [],
        }]
    }
    (tmp_data / "users.json").write_text(json.dumps(users_data))

    # Options has the same plaintext (HA Supervisor behavior)
    opts = _write_options(tmp_data, [
        {
            "username": "bob",
            "password": "mypassword",
            "enabled": True,
            "allowed_entities": [],
        }
    ])
    users = sync_users(opts)
    # Hash should be unchanged (matched checkpw)
    assert users[0]["password_hash"] == existing_hash
    assert users[0]["id"] == "uuid-123"


def test_sync_users_assigns_uuid(tmp_data):
    opts = _write_options(tmp_data, [
        {"username": "carol", "password": "pass", "enabled": True, "allowed_entities": []}
    ])
    users = sync_users(opts)
    assert len(users[0]["id"]) == 36  # UUID4 format


def test_save_and_reload_state(tmp_data):
    state = {"guest_access_enabled": False}
    save_state(state)
    loaded = load_state()
    assert loaded["guest_access_enabled"] is False


def test_load_state_default_when_missing(tmp_data):
    state = load_state()
    assert state["guest_access_enabled"] is True
