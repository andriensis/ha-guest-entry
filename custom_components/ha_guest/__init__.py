"""The Guest Entry integration."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import GuestEntryClient
from .const import CONF_ADDON_URL, CONF_INTERNAL_SECRET, DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from .coordinator import GuestEntryCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Guest Entry from a config entry."""
    session = async_get_clientsession(hass)
    client = GuestEntryClient(
        session=session,
        addon_url=entry.data[CONF_ADDON_URL],
        secret=entry.data[CONF_INTERNAL_SECRET],
    )

    coordinator = GuestEntryCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_CLIENT: client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
