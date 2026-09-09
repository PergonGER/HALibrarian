"""The HA Library Tracker integration.

Session 1 scope: scaffolding + registration of the custom sidebar panel.
The panel currently loads a static placeholder frontend; the WebSocket
backend, database and API integrations are added in later sessions.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL_BASE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []

PANEL_DIR = Path(__file__).parent / "panel"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Library Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"entry": entry}

    await _async_register_panel(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)

    # Only remove the panel once no config entries are left.
    if not hass.data[DOMAIN]:
        frontend = hass.components.frontend
        frontend.async_remove_panel(PANEL_URL_PATH)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Serve the static frontend and register the sidebar panel.

    Uses a plain iframe panel loading a static HTML/JS/CSS bundle, so no
    frontend build toolchain is required. Re-registering an already
    registered static path / panel is a no-op guarded via hass.data.
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

    frontend = hass.components.frontend
    frontend.async_register_built_in_panel(
        "iframe",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL_PATH,
        config={"url": f"{STATIC_URL_BASE}/index.html"},
        require_admin=False,
    )

    hass.data[DOMAIN]["panel_registered"] = True
