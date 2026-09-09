"""WebSocket API for HA Library Tracker."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .api import async_lookup_isbn
from .const import CONF_GOOGLE_BOOKS_API_KEY, DOMAIN
from .db import LibraryTrackerDatabase

_LOGGER = logging.getLogger(__name__)


def _get_db(hass: HomeAssistant) -> LibraryTrackerDatabase:
    """Get database instance from hass.data."""
    if DOMAIN not in hass.data or "db" not in hass.data[DOMAIN]:
        raise RuntimeError("Library Tracker database is not initialized.")
    return hass.data[DOMAIN]["db"]  # type: ignore[no-any-return]


def _get_google_api_key(hass: HomeAssistant) -> str | None:
    """Extract Google Books API key from config entries if available."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return None
    entry = entries[0]
    key = entry.options.get(CONF_GOOGLE_BOOKS_API_KEY) or entry.data.get(
        CONF_GOOGLE_BOOKS_API_KEY
    )
    return str(key) if key else None


@websocket_api.websocket_command(
    {
        vol.Required("type"): "library_tracker/books/list",
        vol.Optional("status"): vol.In(["gelesen", "ungelesen", "wunschliste"]),
    }
)
@websocket_api.async_response
async def ws_books_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List all books, optionally filtered by status."""
    try:
        db = _get_db(hass)
        status = msg.get("status")
        books = await hass.async_add_executor_job(db.get_books, status)
        connection.send_result(msg["id"], books)
    except Exception as err:
        _LOGGER.error("Error in library_tracker/books/list: %s", err)
        connection.send_error(msg["id"], "db_error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "library_tracker/books/add",
        vol.Required("isbn"): vol.All(cv.string, vol.Strip),
        vol.Required("title"): vol.All(cv.string, vol.Strip),
        vol.Required("author"): vol.All(cv.string, vol.Strip),
        vol.Optional("published_date", default=""): cv.string,
        vol.Optional("cover_url", default=""): cv.string,
        vol.Required("status"): vol.In(["gelesen", "ungelesen", "wunschliste"]),
        vol.Optional("rating"): vol.Maybe(
            vol.All(vol.Coerce(int), vol.Range(min=1, max=5))
        ),
    }
)
@websocket_api.async_response
async def ws_books_add(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a new book."""
    try:
        db = _get_db(hass)
        book = await hass.async_add_executor_job(
            db.add_book,
            msg["isbn"],
            msg["title"],
            msg["author"],
            msg["status"],
            msg.get("published_date"),
            msg.get("cover_url"),
            msg.get("rating"),
        )
        connection.send_result(msg["id"], book)
    except Exception as err:
        _LOGGER.error("Error in library_tracker/books/add: %s", err)
        connection.send_error(msg["id"], "db_error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "library_tracker/books/update",
        vol.Optional("book_id"): vol.Coerce(int),
        vol.Optional("id"): vol.Coerce(int),
        vol.Optional("status"): vol.In(["gelesen", "ungelesen", "wunschliste"]),
        vol.Optional("rating"): vol.Maybe(
            vol.All(vol.Coerce(int), vol.Range(min=1, max=5))
        ),
        vol.Optional("title"): vol.All(cv.string, vol.Strip),
        vol.Optional("author"): vol.All(cv.string, vol.Strip),
        vol.Optional("published_date"): cv.string,
        vol.Optional("cover_url"): cv.string,
    }
)
@websocket_api.async_response
async def ws_books_update(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update an existing book."""
    try:
        db = _get_db(hass)
        book_id = msg.get("book_id") or msg.get("id")
        if book_id is None:
            connection.send_error(
                msg["id"], "invalid_format", "book_id or id is required"
            )
            return

        clear_rating = "rating" in msg and msg["rating"] is None
        rating = msg.get("rating") if not clear_rating else None

        updated = await hass.async_add_executor_job(
            db.update_book,
            book_id,
            msg.get("status"),
            rating,
            msg.get("title"),
            msg.get("author"),
            msg.get("published_date"),
            msg.get("cover_url"),
            clear_rating,
        )
        if updated is None:
            connection.send_error(
                msg["id"], "not_found", f"Book with id {book_id} not found"
            )
            return

        connection.send_result(msg["id"], updated)
    except Exception as err:
        _LOGGER.error("Error in library_tracker/books/update: %s", err)
        connection.send_error(msg["id"], "db_error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "library_tracker/books/delete",
        vol.Optional("book_id"): vol.Coerce(int),
        vol.Optional("id"): vol.Coerce(int),
    }
)
@websocket_api.async_response
async def ws_books_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a book by id."""
    try:
        db = _get_db(hass)
        book_id = msg.get("book_id") or msg.get("id")
        if book_id is None:
            connection.send_error(
                msg["id"], "invalid_format", "book_id or id is required"
            )
            return

        deleted = await hass.async_add_executor_job(db.delete_book, book_id)
        if not deleted:
            connection.send_error(
                msg["id"], "not_found", f"Book with id {book_id} not found"
            )
            return

        connection.send_result(msg["id"], {"success": True, "id": book_id})
    except Exception as err:
        _LOGGER.error("Error in library_tracker/books/delete: %s", err)
        connection.send_error(msg["id"], "db_error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "library_tracker/authors/list",
    }
)
@websocket_api.async_response
async def ws_authors_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List all authors."""
    try:
        db = _get_db(hass)
        authors = await hass.async_add_executor_job(db.get_authors)
        connection.send_result(msg["id"], authors)
    except Exception as err:
        _LOGGER.error("Error in library_tracker/authors/list: %s", err)
        connection.send_error(msg["id"], "db_error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "library_tracker/authors/set_favorite",
        vol.Optional("author_id"): vol.Coerce(int),
        vol.Optional("id"): vol.Coerce(int),
        vol.Required("is_favorite"): cv.boolean,
    }
)
@websocket_api.async_response
async def ws_authors_set_favorite(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Set favorite status of an author."""
    try:
        db = _get_db(hass)
        author_id = msg.get("author_id") or msg.get("id")
        if author_id is None:
            connection.send_error(
                msg["id"], "invalid_format", "author_id or id is required"
            )
            return

        updated = await hass.async_add_executor_job(
            db.set_author_favorite, author_id, msg["is_favorite"]
        )
        if updated is None:
            connection.send_error(
                msg["id"], "not_found", f"Author with id {author_id} not found"
            )
            return

        connection.send_result(msg["id"], updated)
    except Exception as err:
        _LOGGER.error("Error in library_tracker/authors/set_favorite: %s", err)
        connection.send_error(msg["id"], "db_error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "library_tracker/lookup_isbn",
        vol.Required("isbn"): vol.All(cv.string, vol.Strip),
    }
)
@websocket_api.async_response
async def ws_lookup_isbn(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Look up book metadata by ISBN."""
    try:
        api_key = _get_google_api_key(hass)
        metadata = await async_lookup_isbn(hass, msg["isbn"], google_api_key=api_key)
        if metadata is None:
            connection.send_error(
                msg["id"], "not_found", f"No metadata found for ISBN: {msg['isbn']}"
            )
            return

        connection.send_result(msg["id"], metadata)
    except Exception as err:
        _LOGGER.error("Error in library_tracker/lookup_isbn: %s", err)
        connection.send_error(msg["id"], "api_error", str(err))


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register custom WebSocket commands for Library Tracker."""
    if hass.data.get(DOMAIN, {}).get("ws_commands_registered"):
        return

    websocket_api.async_register_command(hass, ws_books_list)
    websocket_api.async_register_command(hass, ws_books_add)
    websocket_api.async_register_command(hass, ws_books_update)
    websocket_api.async_register_command(hass, ws_books_delete)
    websocket_api.async_register_command(hass, ws_authors_list)
    websocket_api.async_register_command(hass, ws_authors_set_favorite)
    websocket_api.async_register_command(hass, ws_lookup_isbn)

    hass.data.setdefault(DOMAIN, {})["ws_commands_registered"] = True
