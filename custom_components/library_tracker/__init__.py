"""The HA Library Tracker integration.

Session 2 scope: Backend logic, SQLite database & WebSocket API.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import (
    DB_FILENAME,
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL_BASE,
)
from .db import LibraryTrackerDatabase
from .websocket_api import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []

PANEL_DIR = Path(__file__).parent / "panel"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Library Tracker from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    # Initialize SQLite database if not present
    if "db" not in domain_data:
        db_path = hass.config.path(DB_FILENAME)
        db = LibraryTrackerDatabase(db_path)
        await hass.async_add_executor_job(db.init_db)
        domain_data["db"] = db

    domain_data[entry.entry_id] = {"entry": entry}

    # Register WebSocket commands
    async_register_websocket_commands(hass)

    # Register sidebar panel
    await _async_register_panel(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)

    # Only clean up panel and database reference once no config entries are left.
    remaining_entries = [
        k for k in domain_data.keys() if k not in ("db", "panel_registered", "ws_commands_registered")
    ]
    if not remaining_entries:
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
        domain_data.pop("db", None)
        domain_data.pop("panel_registered", None)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Serve the static frontend and register the sidebar panel.

    Uses panel_custom with embed_iframe=False to render as a direct ES module
    custom web component, avoiding iframe permission blocks (e.g. camera on iOS/Safari)
    and avoiding the need for manual Long-Lived Access Tokens.
    """
    if hass.data[DOMAIN].get("panel_registered"):
        return

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                STATIC_URL_BASE,
                str(PANEL_DIR),
                cache_headers=False,
            )
        ]
    )

    # Cache-busting: append the integration version as a query string, so a
    # new release forces browsers/WebViews to fetch a fresh copy of the
    # panel module (and, via import.meta.url in the module itself, of
    # style.css/html5-qrcode.min.js too) instead of serving a stale cached
    # one that happens to have the same URL. cache_headers=False alone
    # doesn't help here - it only affects HTTP caching, not aggressive
    # module caches some WebViews keep across app restarts (root cause of
    # several "same URL, old behavior" bugs seen during development).
    try:
        integration = await async_get_integration(hass, DOMAIN)
        cache_bust = f"?v={integration.version}"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Could not determine integration version for cache-busting")
        cache_bust = ""

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name="library-tracker-panel",
        module_url=f"{STATIC_URL_BASE}/library-tracker-panel.js{cache_bust}",
        embed_iframe=False,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
    )

    hass.data[DOMAIN]["panel_registered"] = True
