"""AI-powered series lookup using Home Assistant AI Task platform."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

# Voluptuous schema for structured AI response
AI_SERIES_STRUCTURE = vol.Schema(
    {
        vol.Required("is_series"): bool,
        vol.Optional("series_name"): vol.Any(str, None),
        vol.Optional("books"): [
            vol.Schema(
                {
                    vol.Required("title"): str,
                    vol.Optional("order"): vol.Any(int, vol.Coerce(int), None),
                }
            )
        ],
    }
)


async def async_ai_series_lookup(
    hass: HomeAssistant, title: str, author: str
) -> dict[str, Any] | None:
    """Query Home Assistant AI Task platform to identify book series and volumes.

    Returns a dict with is_series, series_name, and books if successful, or None
    if ai_task is unavailable, no provider entity is configured, or lookup fails.
    """
    try:
        from homeassistant.components import ai_task  # type: ignore[attr-defined]
    except (ImportError, AttributeError):
        _LOGGER.warning("ai_task component is not available in Home Assistant")
        return None

    instructions = (
        f"Identifiziere die Buchreihe für das folgende Buch: Titel: '{title}', Autor: '{author}'. "
        f"Nenne den genauen Namen der Buchreihe (series_name) und alle bekannten Bände (Titel und deren Reihenfolge/Order in der Serie, falls bekannt). "
        f"Falls es sich um keine Buchreihe handelt oder Unsicherheit besteht, setze 'is_series' explizit auf false und rate nicht."
    )

    try:
        response = await ai_task.async_generate_data(
            hass,
            task_name="library_tracker_series_lookup",
            instructions=instructions,
            structure=AI_SERIES_STRUCTURE,
        )
        if not isinstance(response, dict):
            _LOGGER.warning("AI task returned non-dict response for '%s'", title)
            return None

        books_data = []
        raw_books = response.get("books") or []
        if isinstance(raw_books, list):
            for item in raw_books:
                if isinstance(item, dict) and "title" in item:
                    books_data.append(
                        {
                            "title": str(item["title"]).strip(),
                            "order": int(item["order"]) if item.get("order") is not None else None,
                        }
                    )

        return {
            "is_series": bool(response.get("is_series", False)),
            "series_name": str(response["series_name"]).strip()
            if response.get("series_name")
            else None,
            "books": books_data,
        }

    except HomeAssistantError as err:
        _LOGGER.warning(
            "Home Assistant AI task error during series lookup for '%s': %s",
            title,
            err,
        )
        return None
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error during AI series lookup for '%s': %s", title, err
        )
        return None
