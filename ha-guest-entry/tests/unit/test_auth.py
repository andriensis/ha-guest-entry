"""Unit tests for auth.py: bcrypt, JWT, blacklist."""

from __future__ import annotations

import time

import pytest

from backend.auth import (
    AuthError,
    TokenBlacklistedError,
    blacklist_jti,
    is_blacklisted,
    issue_token,
    load_blacklist,
    verify_password,
    verify_token,
)


@pytest.fixture(autouse=True)
def reset_blacklist(tmp_data):
    load_blacklist()


def _make_user(uid="user-1", username="alice"):
    return {"id": uid, "username": username}


# ------------------------------------------------------------------
# Password
# ------------------------------------------------------------------

def test_verify_password_correct():
    import bcrypt
    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt(rounds=4)).decode()
    assert verify_password("secret", hashed) is True


def test_verify_password_wrong():
    import bcrypt
    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt(rounds=4)).decode()
    assert verify_password("wrong", hashed) is False


def test_verify_password_bad_hash():
    assert verify_password("anything", "not-a-valid-hash") is False


# ------------------------------------------------------------------
# JWT issue + verify
# ------------------------------------------------------------------

def test_issue_and_verify_token():
    user = _make_user()
    token, expires_at = issue_token(user, duration_hours=1)
    assert isinstance(token, str)
    payload = verify_token(token)
    assert payload["sub"] == user["id"]
    assert payload["username"] == user["username"]
    assert "jti" in payload


def test_verify_expired_token():
    user = _make_user()
    token, _ = issue_token(user, duration_hours=0)  # 0h = already expired
    with pytest.raises(AuthError, match="expired"):
        verify_token(token)


def test_verify_invalid_token():
    with pytest.raises(AuthError):
        verify_token("not.a.valid.jwt")


# ------------------------------------------------------------------
# Blacklist
# ------------------------------------------------------------------

def test_blacklist_jti(tmp_data):
    user = _make_user()
    token, _ = issue_token(user, duration_hours=1)
    payload = verify_token(token)
    jti = payload["jti"]

    assert not is_blacklisted(jti)
    blacklist_jti(jti)
    assert is_blacklisted(jti)


def test_blacklisted_token_raises(tmp_data):
    user = _make_user()
    token, _ = issue_token(user, duration_hours=1)
    payload = verify_token(token)
    blacklist_jti(payload["jti"])

    with pytest.raises(TokenBlacklistedError):
        verify_token(token)


def test_blacklist_persists(tmp_data):
    user = _make_user()
    token, _ = issue_token(user, duration_hours=1)
    payload = verify_token(token)
    blacklist_jti(payload["jti"])

    # Reload blacklist from disk
    load_blacklist()
    assert is_blacklisted(payload["jti"])
