"""Switch entities for Guest Entry: global access + per-user access."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDON_URL, DATA_COORDINATOR, DOMAIN
from .coordinator import GuestEntryCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    coordinator: GuestEntryCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[SwitchEntity] = []

    if coordinator.data:
        for user in coordinator.data.get("users", []):
            entities.append(GuestUserSwitch(coordinator, entry, user))

    async_add_entities(entities)

    # Listen for coordinator updates to add/remove user switches dynamically
    known_user_ids: set[str] = {u["id"] for u in (coordinator.data.get("users", []) if coordinator.data else [])}

    @callback
    def _handle_coordinator_update() -> None:
        nonlocal known_user_ids
        new_users = coordinator.data.get("users", []) if coordinator.data else []
        new_ids = {u["id"] for u in new_users}

        added = new_ids - known_user_ids
        if added:
            new_entities = [
                GuestUserSwitch(coordinator, entry, u)
                for u in new_users
                if u["id"] in added
            ]
            async_add_entities(new_entities)

        known_user_ids = new_ids

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Guest Entry",
        manufacturer="Guest Entry",
        model="Guest Entry App",
        configuration_url=entry.data.get(CONF_ADDON_URL),
    )


class GuestUserSwitch(CoordinatorEntity[GuestEntryCoordinator], SwitchEntity):
    """Controls access for a single guest user."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account"

    def __init__(
        self,
        coordinator: GuestEntryCoordinator,
        entry: ConfigEntry,
        user: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._user_id: str = user["id"]
        self._username: str = user["username"]
        self._attr_unique_id = f"{entry.entry_id}_user_{self._user_id}"
        self._attr_name = user["username"].capitalize()
        self._attr_device_info = _device_info(entry)

    def _current_user(self) -> dict[str, Any] | None:
        if self.coordinator.data is None:
            return None
        return next(
            (u for u in self.coordinator.data.get("users", []) if u["id"] == self._user_id),
            None,
        )

    @property
    def is_on(self) -> bool:
        user = self._current_user()
        return bool(user["enabled"]) if user else False

    @property
    def available(self) -> bool:
        return super().available and self._current_user() is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_user_access(self._user_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_user_access(self._user_id, False)
        await self.coordinator.async_request_refresh()
