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

from datetime import datetime, timedelta

from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .api import async_search_books_by_author
from .const import (
    CONF_AUTHOR_CHECK_INTERVAL,
    CONF_GOOGLE_BOOKS_API_KEY,
    CONF_NOTIFY_SERVICE,
    COVERS_DIR_NAME,
    COVERS_URL_BASE,
    DB_FILENAME,
    DEFAULT_AUTHOR_CHECK_INTERVAL,
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

    # Ensure covers directory exists and register static path
    covers_dir = Path(hass.config.path(COVERS_DIR_NAME))
    await hass.async_add_executor_job(lambda: covers_dir.mkdir(parents=True, exist_ok=True))
    if not domain_data.get("covers_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    COVERS_URL_BASE,
                    str(covers_dir),
                    cache_headers=False,
                )
            ]
        )
        domain_data["covers_registered"] = True

    # Register periodic author releases check
    raw_interval = None
    if isinstance(entry.options, dict):
        raw_interval = entry.options.get(CONF_AUTHOR_CHECK_INTERVAL)
    if raw_interval is None and isinstance(entry.data, dict):
        raw_interval = entry.data.get(CONF_AUTHOR_CHECK_INTERVAL)

    try:
        interval_hours = int(raw_interval) if raw_interval is not None else DEFAULT_AUTHOR_CHECK_INTERVAL
    except (TypeError, ValueError):
        interval_hours = DEFAULT_AUTHOR_CHECK_INTERVAL

    async def _scheduled_author_check(now: datetime | None = None) -> None:
        await async_check_author_releases(hass, entry)

    unsub_check = async_track_time_interval(
        hass, _scheduled_author_check, timedelta(hours=interval_hours)
    )
    entry.async_on_unload(unsub_check)

    domain_data[entry.entry_id] = {
        "entry": entry,
        "unsub_author_check": unsub_check,
    }

    # Register WebSocket commands
    async_register_websocket_commands(hass)

    # Register sidebar panel
    await _async_register_panel(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    entry_data = domain_data.pop(entry.entry_id, None)
    if entry_data and "unsub_author_check" in entry_data:
        entry_data["unsub_author_check"]()

    # Only clean up panel and database reference once no config entries are left.
    remaining_entries = [
        k
        for k in domain_data.keys()
        if k not in ("db", "panel_registered", "ws_commands_registered", "covers_registered")
    ]
    if not remaining_entries:
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
        domain_data.pop("db", None)
        domain_data.pop("panel_registered", None)

    return True


async def async_check_author_releases(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Check for new books by favorite authors and send notifications."""
    domain_data = hass.data.get(DOMAIN, {})
    db: LibraryTrackerDatabase | None = domain_data.get("db")
    if db is None:
        _LOGGER.warning("Database not available for author releases check")
        return

    favorite_authors = await hass.async_add_executor_job(db.get_favorite_authors)
    if not favorite_authors:
        _LOGGER.debug("No favorite authors found to check for new releases")
        return

    notify_service = entry.options.get(
        CONF_NOTIFY_SERVICE,
        entry.data.get(CONF_NOTIFY_SERVICE, "notify.notify"),
    )
    api_key = entry.options.get(
        CONF_GOOGLE_BOOKS_API_KEY,
        entry.data.get(CONF_GOOGLE_BOOKS_API_KEY, ""),
    ) or None

    session = async_get_clientsession(hass)

    for author_info in favorite_authors:
        author_id = author_info["id"]
        author_name = author_info["name"]

        try:
            found_books = await async_search_books_by_author(
                hass, session, author_name, api_key
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to search books for author %s", author_name)
            continue

        for book in found_books:
            title = book.get("title", "").strip()
            isbn = book.get("isbn", "").strip()
            if not title:
                continue

            # 1. Dedup against existing books in library
            # Find duplicate using the existing find_duplicate_books method
            is_in_library = await hass.async_add_executor_job(
                lambda b_isbn=isbn, b_title=title, b_author=author_name: bool(
                    db.find_duplicate_books(b_isbn, b_title, b_author)
                )
            )
            if is_in_library:
                continue

            # 2. Check if user was already notified
            already_notified = await hass.async_add_executor_job(
                db.has_author_notification, author_id, title
            )
            if already_notified:
                continue

            # 3. Send notification
            published_date = book.get("published_date", "")
            date_info = f" ({published_date})" if published_date else ""
            msg = f"Neues Buch von {author_name}: „{title}“{date_info}"
            alert_title = f"Neues Buch von {author_name}"

            if "." in notify_service:
                domain, service = notify_service.split(".", 1)
            else:
                domain, service = "notify", notify_service

            try:
                await hass.services.async_call(
                    domain,
                    service,
                    {"title": alert_title, "message": msg},
                    blocking=True,
                )
            except ServiceNotFound:
                _LOGGER.error("Configured notify service '%s' not found", notify_service)
            except HomeAssistantError as err:
                _LOGGER.error("Error calling notify service '%s': %s", notify_service, err)
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Unexpected error notifying for new book '%s' by '%s'",
                    title,
                    author_name,
                )

            # Record notification in DB so we don't alert again
            try:
                await hass.async_add_executor_job(
                    db.record_author_notification, author_id, title, isbn or None
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Failed to record author release notification in database for '%s'",
                    title,
                )


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
