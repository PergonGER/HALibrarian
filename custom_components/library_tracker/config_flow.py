"""Config flow for HA Library Tracker."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_AUTHOR_CHECK_INTERVAL,
    CONF_GOOGLE_BOOKS_API_KEY,
    CONF_NOTIFY_SERVICE,
    DEFAULT_AUTHOR_CHECK_INTERVAL,
    DOMAIN,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_GOOGLE_BOOKS_API_KEY,
                default=defaults.get(CONF_GOOGLE_BOOKS_API_KEY, ""),
            ): str,
            vol.Optional(
                CONF_NOTIFY_SERVICE,
                default=defaults.get(CONF_NOTIFY_SERVICE, "notify.notify"),
            ): str,
            vol.Optional(
                CONF_AUTHOR_CHECK_INTERVAL,
                default=defaults.get(
                    CONF_AUTHOR_CHECK_INTERVAL, DEFAULT_AUTHOR_CHECK_INTERVAL
                ),
            ): vol.All(int, vol.Range(min=1, max=168)),
        }
    )


class LibraryTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Library Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Handle the initial step.

        The Google Books API key is optional: when omitted, the backend
        (Session 2) falls back to the Open Library API.
        """
        # Only one library per Home Assistant instance.
        self._async_abort_entries_match({})

        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="Library Tracker", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_schema(), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return LibraryTrackerOptionsFlow(config_entry)


class LibraryTrackerOptionsFlow(OptionsFlow):
    """Handle options for HA Library Tracker (edit API key / notify target)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_schema(current)
        )
