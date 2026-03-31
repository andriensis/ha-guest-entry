"""DataUpdateCoordinator for the Guest Entry integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import GuestEntryClient
from .const import DOMAIN, SCAN_INTERVAL_SECONDS
from .exceptions import GuestEntryConnectionError

_LOGGER = logging.getLogger(__name__)


class GuestEntryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the Guest Entry app and notifies entities of changes."""

    def __init__(self, hass: HomeAssistant, client: GuestEntryClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch state from the Guest Entry app.

        Returns:
            {
                "global_enabled": bool,
                "users": [{"id": str, "username": str, "enabled": bool}, ...]
            }
        """
        try:
            return await self.client.get_state()
        except GuestEntryConnectionError as exc:
            raise UpdateFailed(f"Cannot reach Guest Entry app: {exc}") from exc
