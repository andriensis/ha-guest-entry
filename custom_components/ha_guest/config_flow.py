"""Config flow for Guest Entry integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # HA < 2024.4
    from typing import Any as ConfigFlowResult  # type: ignore[assignment]

try:
    from homeassistant.components.hassio import HassioServiceInfo
except ImportError:
    HassioServiceInfo = None  # type: ignore[assignment,misc]


from .client import GuestEntryClient
from .const import (
    CONF_ADDON_URL,
    CONF_INTERNAL_SECRET,
    DATA_CLIENT,
    DEFAULT_ADDON_URL,
    DOMAIN,
    SECRET_FILE_PATH,
)
from .exceptions import GuestEntryAuthError, GuestEntryConnectionError

_LOGGER = logging.getLogger(__name__)

_DONE_KEY = "__done__"


def _read_secret_from_file() -> str | None:
    try:
        return Path(SECRET_FILE_PATH).read_text().strip()
    except OSError:
        return None


class GuestEntryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow."""

    VERSION = 1

    async def async_step_hassio(
        self, discovery_info: Any
    ) -> ConfigFlowResult:
        """Auto-configure when the add-on registers with Supervisor discovery."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        secret = _read_secret_from_file()
        if not secret:
            # Secret file not ready yet — fall back to manual setup
            return await self.async_step_user()

        session = async_get_clientsession(self.hass)
        client = GuestEntryClient(session=session, addon_url=DEFAULT_ADDON_URL, secret=secret)
        try:
            await client.get_state()
        except Exception:
            _LOGGER.warning("Auto-discovery: could not connect to Guest Entry add-on")
            return await self.async_step_user()

        return self.async_create_entry(
            title="Guest Entry",
            data={CONF_ADDON_URL: DEFAULT_ADDON_URL, CONF_INTERNAL_SECRET: secret},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        auto_secret = _read_secret_from_file()

        if user_input is not None:
            addon_url = user_input[CONF_ADDON_URL].rstrip("/")
            secret = user_input[CONF_INTERNAL_SECRET].strip()

            session = async_get_clientsession(self.hass)
            client = GuestEntryClient(session=session, addon_url=addon_url, secret=secret)

            try:
                await client.get_state()
            except GuestEntryAuthError:
                errors[CONF_INTERNAL_SECRET] = "invalid_auth"
            except GuestEntryConnectionError:
                errors[CONF_ADDON_URL] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error connecting to Guest Entry app")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Guest Entry",
                    data={
                        CONF_ADDON_URL: addon_url,
                        CONF_INTERNAL_SECRET: secret,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ADDON_URL, default=DEFAULT_ADDON_URL): str,
                vol.Required(
                    CONF_INTERNAL_SECRET,
                    default=auto_secret or vol.UNDEFINED,
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"secret_file": SECRET_FILE_PATH},
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return GuestEntryOptionsFlow(config_entry)


class GuestEntryOptionsFlow(OptionsFlow):
    """Options flow — users and entity assignments are managed in the admin panel."""

    def __init__(self, config_entry) -> None:
        pass

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
