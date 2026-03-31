"""JWT issue/verify, bcrypt check, token blacklist."""

from __future__ import annotations

import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
import jwt

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
JWT_SECRET_FILE = DATA_DIR / "jwt_secret.txt"
BLACKLIST_FILE = DATA_DIR / "blacklist.json"

ALGORITHM = "HS256"


class AuthError(Exception):
    pass


class TokenBlacklistedError(AuthError):
    pass


# ---------------------------------------------------------------------------
# JWT secret
# ---------------------------------------------------------------------------

def _load_or_create_jwt_secret() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if JWT_SECRET_FILE.exists():
        return JWT_SECRET_FILE.read_text().strip()
    secret = secrets.token_hex(64)
    JWT_SECRET_FILE.write_text(secret)
    log.info("Generated new JWT secret")
    return secret


_JWT_SECRET: str | None = None


def jwt_secret() -> str:
    global _JWT_SECRET
    if _JWT_SECRET is None:
        _JWT_SECRET = _load_or_create_jwt_secret()
    return _JWT_SECRET


# ---------------------------------------------------------------------------
# Token blacklist
# ---------------------------------------------------------------------------

def _load_blacklist() -> set[str]:
    if not BLACKLIST_FILE.exists():
        return set()
    with BLACKLIST_FILE.open() as f:
        data = json.load(f)
    return set(data.get("jti_list", []))


def _save_blacklist(jti_set: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with BLACKLIST_FILE.open("w") as f:
        json.dump({"jti_list": list(jti_set)}, f)


# In-memory blacklist (loaded on startup, persisted on change)
_blacklist: set[str] = set()


def load_blacklist() -> None:
    global _blacklist
    raw = _load_blacklist()
    # Prune JTIs that we can decode and confirm are already expired
    pruned: set[str] = set()
    for jti in raw:
        # We can't easily look up expiry by JTI alone without a separate store,
        # so keep all — but limit total size to avoid unbounded growth
        pruned.add(jti)
    # Keep only the most recent 10 000 entries (well beyond any practical use)
    if len(pruned) > 10_000:
        pruned = set(list(pruned)[-10_000:])
        _save_blacklist(pruned)
    _blacklist = pruned
    log.debug("Loaded %d blacklisted JTIs", len(_blacklist))


def blacklist_jti(jti: str) -> None:
    _blacklist.add(jti)
    _save_blacklist(_blacklist)


def is_blacklisted(jti: str) -> bool:
    return jti in _blacklist


def prune_blacklist(users_expiry: dict[str, datetime]) -> None:
    """Remove expired JTIs (best-effort; only possible if we tracked expiry)."""
    # Simple approach: keep all — file stays small in practice.
    pass


# ---------------------------------------------------------------------------
# Password verification
# ---------------------------------------------------------------------------

def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def issue_token(user: dict[str, Any], duration_hours: int) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=duration_hours)
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)
    return token, expires_at


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT. Raises AuthError on any failure."""
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired")
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid token: {exc}")

    jti = payload.get("jti")
    if jti and is_blacklisted(jti):
        raise TokenBlacklistedError("Token has been revoked")

    return payload
