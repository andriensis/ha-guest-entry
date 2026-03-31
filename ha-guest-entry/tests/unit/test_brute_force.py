"""Unit tests for brute_force.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.brute_force import BruteForceProtector


@pytest.fixture
def bf(tmp_data) -> BruteForceProtector:
    return BruteForceProtector(max_attempts=3, lockout_minutes=15)


# ------------------------------------------------------------------
# IP lockout
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_lockout_initially(bf):
    locked, _ = bf.is_ip_locked("1.2.3.4")
    assert not locked


@pytest.mark.asyncio
async def test_ip_locked_after_max_attempts(bf):
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        for _ in range(3):
            await bf.record_failure("1.2.3.4", "alice")

    locked, retry_after = bf.is_ip_locked("1.2.3.4")
    assert locked
    assert retry_after > 0


@pytest.mark.asyncio
async def test_different_ips_independent(bf):
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        for _ in range(3):
            await bf.record_failure("1.2.3.4", "alice")

    locked, _ = bf.is_ip_locked("9.9.9.9")
    assert not locked


@pytest.mark.asyncio
async def test_lockout_auto_clears_after_expiry(bf):
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        for _ in range(3):
            await bf.record_failure("1.2.3.4", "alice")

    # Manually expire the lockout
    bf._ip["1.2.3.4"]["until"] = datetime.now(timezone.utc) - timedelta(seconds=1)

    locked, _ = bf.is_ip_locked("1.2.3.4")
    assert not locked


# ------------------------------------------------------------------
# Per-username lockout
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_suspended_after_max_attempts(bf):
    bf.max_user_attempts = 3
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        for _ in range(3):
            await bf.record_failure("1.2.3.4", "alice")

    locked, _ = bf.is_user_locked("alice")
    assert locked


@pytest.mark.asyncio
async def test_user_lockout_auto_clears(bf):
    bf.max_user_attempts = 3
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        for _ in range(3):
            await bf.record_failure("1.2.3.4", "alice")

    bf._users["alice"]["until"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    locked, _ = bf.is_user_locked("alice")
    assert not locked


# ------------------------------------------------------------------
# Progressive delay
# ------------------------------------------------------------------

def test_progressive_delay_zero_initially(bf):
    assert bf.progressive_delay("1.2.3.4") == 0.0


@pytest.mark.asyncio
async def test_progressive_delay_increases(bf):
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        await bf.record_failure("1.2.3.4", "alice")
    assert bf.progressive_delay("1.2.3.4") == 1.0

    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        await bf.record_failure("1.2.3.4", "alice")
    assert bf.progressive_delay("1.2.3.4") == 2.0


def test_progressive_delay_caps_at_16(bf):
    bf._ip["1.2.3.4"] = {"count": 10, "until": None}
    assert bf.progressive_delay("1.2.3.4") == 16.0


# ------------------------------------------------------------------
# Success clears counters
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_success_clears_ip_counter(bf):
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        await bf.record_failure("1.2.3.4", "alice")
        await bf.record_failure("1.2.3.4", "alice")

    bf.record_success("1.2.3.4", "alice")
    assert bf._ip.get("1.2.3.4", {}).get("count", 0) == 0


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lockout_persists_across_instances(tmp_data):
    bf1 = BruteForceProtector(max_attempts=2, lockout_minutes=15)
    with patch("backend.brute_force.asyncio.sleep", new=AsyncMock()):
        await bf1.record_failure("5.5.5.5", "bob")
        await bf1.record_failure("5.5.5.5", "bob")

    bf2 = BruteForceProtector(max_attempts=2, lockout_minutes=15)
    locked, _ = bf2.is_ip_locked("5.5.5.5")
    assert locked
