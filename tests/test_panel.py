"""Tests for custom panel registration in HA Library Tracker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.library_tracker import _async_register_panel, async_unload_entry
from custom_components.library_tracker.const import (
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL_BASE,
)


@pytest.mark.asyncio
async def test_async_register_panel() -> None:
    """Test panel_custom.async_register_panel is called with correct parameters."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.data = {DOMAIN: {}}
    mock_hass.http.async_register_static_paths = AsyncMock()

    with patch(
        "homeassistant.components.panel_custom.async_register_panel",
        new_callable=AsyncMock,
    ) as mock_register_panel:
        await _async_register_panel(mock_hass)

        assert mock_hass.data[DOMAIN]["panel_registered"] is True
        mock_hass.http.async_register_static_paths.assert_called_once()

        mock_register_panel.assert_called_once_with(
            mock_hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name="library-tracker-panel",
            module_url=f"{STATIC_URL_BASE}/library-tracker-panel.js",
            embed_iframe=False,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            require_admin=False,
        )

        # Calling a second time should be a no-op
        mock_register_panel.reset_mock()
        await _async_register_panel(mock_hass)
        mock_register_panel.assert_not_called()


@pytest.mark.asyncio
async def test_async_unload_entry_removes_panel() -> None:
    """Test unloading entry removes panel when no remaining entries."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.data = {
        DOMAIN: {
            "entry_1": {},
            "panel_registered": True,
            "db": MagicMock(),
        }
    }

    mock_entry = MagicMock()
    mock_entry.entry_id = "entry_1"

    with patch("homeassistant.components.frontend.async_remove_panel") as mock_remove:
        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is True
        mock_remove.assert_called_once_with(mock_hass, PANEL_URL_PATH)
        assert "panel_registered" not in mock_hass.data[DOMAIN]
