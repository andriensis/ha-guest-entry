"""Load options, hash passwords, persist users.json."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import bcrypt

log = logging.getLogger(__name__)

OPTIONS_FILE = Path(os.environ.get("OPTIONS_FILE", "/data/options.json"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
USERS_FILE = DATA_DIR / "users.json"


class ConfigError(Exception):
    pass


def _hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=12)).decode()


def _is_bcrypt(value: str) -> bool:
    return value.startswith("$2b$") or value.startswith("$2a$")


def load_options() -> dict[str, Any]:
    if not OPTIONS_FILE.exists():
        raise ConfigError(f"Options file not found: {OPTIONS_FILE}")
    with OPTIONS_FILE.open() as f:
        return json.load(f)


def _load_existing_users() -> dict[str, dict]:
    """Return existing users keyed by username, preserving hashed passwords."""
    if not USERS_FILE.exists():
        return {}
    with USERS_FILE.open() as f:
        data = json.load(f)
    return {u["username"]: u for u in data.get("users", [])}


def sync_users(options: dict[str, Any]) -> list[dict]:
    """Diff options users against users.json, hash new passwords, return merged list."""
    existing = _load_existing_users()
    merged: list[dict] = []

    for raw in options.get("users", []):
        username = raw["username"]
        password_field = raw["password"]

        if _is_bcrypt(password_field):
            # Already hashed (shouldn't happen in options, but be safe)
            password_hash = password_field
        elif username in existing and _is_bcrypt(existing[username]["password_hash"]):
            # Same plaintext placeholder — HA Supervisor replaces plaintext with a masked
            # token on re-save; if it matches the stored hash, keep the existing hash.
            # If the plaintext actually changed, re-hash.
            stored_hash = existing[username]["password_hash"].encode()
            if bcrypt.checkpw(password_field.encode(), stored_hash):
                password_hash = existing[username]["password_hash"]
            else:
                log.info("Password changed for user %s, re-hashing", username)
                password_hash = _hash_password(password_field)
        else:
            log.info("Hashing password for new user %s", username)
            password_hash = _hash_password(password_field)

        user_id = existing[username]["id"] if username in existing else str(uuid.uuid4())

        # allowed_entities from Supervisor schema is a list of entity_id strings
        raw_entities = raw.get("allowed_entities") or []
        allowed_entities = [
            {"entity_id": e, "label": None} for e in raw_entities if isinstance(e, str)
        ]

        merged.append(
            {
                "id": user_id,
                "username": username,
                "password_hash": password_hash,
                "display_name": raw.get("display_name") or username,
                "enabled": raw.get("enabled", True),
                "allowed_entities": allowed_entities,
            }
        )

    return merged


def save_users(users: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with USERS_FILE.open("w") as f:
        json.dump({"users": users}, f, indent=2)


def load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []
    with USERS_FILE.open() as f:
        return json.load(f).get("users", [])


def get_addon_version() -> str:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        import yaml  # type: ignore[import]
        with config_path.open() as f:
            cfg = yaml.safe_load(f)
        return cfg.get("version", "1.0.0")
    return "1.0.0"


APP_CONFIG_FILE = DATA_DIR / "app_config.json"

DEFAULT_APP_CONFIG = {
    "instance_name": "Home",
    "session_duration_hours": 24,
    "max_login_attempts": 5,
    "lockout_duration_minutes": 15,
}


def load_app_config() -> dict:
    """Load app config from app_config.json; migrate from options.json on first run."""
    if APP_CONFIG_FILE.exists():
        with APP_CONFIG_FILE.open() as f:
            stored = json.load(f)
        return {**DEFAULT_APP_CONFIG, **stored}
    # Migration: read from options.json if it exists
    if OPTIONS_FILE.exists():
        try:
            with OPTIONS_FILE.open() as f:
                opts = json.load(f)
            cfg = {k: opts[k] for k in DEFAULT_APP_CONFIG if k in opts}
            merged = {**DEFAULT_APP_CONFIG, **cfg}
            save_app_config(merged)
            return merged
        except Exception:
            pass
    save_app_config(DEFAULT_APP_CONFIG)
    return dict(DEFAULT_APP_CONFIG)


def save_app_config(config: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with APP_CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)
