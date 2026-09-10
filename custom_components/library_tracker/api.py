"""Metadata API module for looking up book information by ISBN."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote

import voluptuous as vol
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


def clean_isbn(isbn: str) -> str:
    """Normalize ISBN string by stripping hyphens, spaces, and formatting as upper case."""
    return re.sub(r"[^\dX]", "", isbn.upper())


async def async_lookup_isbn(
    hass: HomeAssistant, isbn: str, google_api_key: str | None = None
) -> dict[str, Any] | None:
    """Look up book metadata by ISBN using Google Books with fallback to Open Library.

    Returns a dict with metadata if found, or None if not found/error.
    """
    normalized_isbn = clean_isbn(isbn)
    if not normalized_isbn:
        _LOGGER.warning("Invalid or empty ISBN provided: %s", isbn)
        return None

    session = async_get_clientsession(hass)

    # 1. Try Google Books API
    google_result = await _async_query_google_books(
        session, normalized_isbn, google_api_key
    )
    if google_result is not None:
        return google_result

    _LOGGER.info(
        "Google Books returned no match or failed for ISBN %s. Falling back to Open Library.",
        normalized_isbn,
    )

    # 2. Fallback to Open Library API
    open_library_result = await _async_query_open_library(session, normalized_isbn)
    if open_library_result is not None:
        return open_library_result

    _LOGGER.warning("No metadata found for ISBN %s on any provider", normalized_isbn)
    return None


def _parse_google_book_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single volume item from Google Books API response."""
    if not isinstance(item, dict):
        return None

    volume_info = item.get("volumeInfo")
    if not isinstance(volume_info, dict):
        return None

    title = str(volume_info.get("title", "")).strip()
    if not title:
        return None

    authors_list = volume_info.get("authors")
    if isinstance(authors_list, list) and authors_list:
        author = ", ".join(str(a) for a in authors_list if a)
    else:
        author = "Unbekannter Autor"

    published_date = str(volume_info.get("publishedDate", ""))

    image_links = volume_info.get("imageLinks")
    cover_url = ""
    if isinstance(image_links, dict):
        raw_cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        if raw_cover and isinstance(raw_cover, str):
            cover_url = raw_cover
            if cover_url.startswith("http://"):
                cover_url = "https://" + cover_url[7:]

    isbn = ""
    industry_identifiers = volume_info.get("industryIdentifiers")
    if isinstance(industry_identifiers, list):
        isbn_13 = ""
        isbn_10 = ""
        other_isbn = ""
        for ident in industry_identifiers:
            if isinstance(ident, dict):
                ident_type = str(ident.get("type", ""))
                val = clean_isbn(str(ident.get("identifier", "")))
                if ident_type == "ISBN_13":
                    isbn_13 = val
                elif ident_type == "ISBN_10":
                    isbn_10 = val
                elif "ISBN" in ident_type:
                    other_isbn = val
        isbn = isbn_13 or isbn_10 or other_isbn

    series_id: str | None = None
    series_order: int | None = None
    series_info = volume_info.get("seriesInfo")
    if isinstance(series_info, dict):
        volume_series = series_info.get("volumeSeries")
        if isinstance(volume_series, list) and volume_series:
            first_series = volume_series[0]
            if isinstance(first_series, dict):
                s_id = first_series.get("seriesId")
                if s_id and isinstance(s_id, str):
                    series_id = s_id
                raw_order = first_series.get("orderNumber")
                if raw_order is not None:
                    try:
                        series_order = int(raw_order)
                    except (ValueError, TypeError):
                        series_order = None

    return {
        "isbn": isbn,
        "title": title,
        "author": author,
        "published_date": published_date,
        "cover_url": cover_url,
        "series_id": series_id,
        "series_order": series_order,
        "source": "google_books",
    }


async def async_search_books_by_text(
    session: Any, query: str, api_key: str | None = None
) -> list[dict[str, Any]]:
    """Search Google Books by free text query.

    Returns a list of dicts with book metadata (up to 10 results),
    or an empty list if no items found or on network/timeout error.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    url = f"https://www.googleapis.com/books/v1/volumes?q={quote(clean_query)}&maxResults=10"
    if api_key:
        url += f"&key={api_key}"

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with session.get(url) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "Google Books API returned status %s for query %s",
                        response.status,
                        clean_query,
                    )
                    return []
                data = await response.json()

        total_items = data.get("totalItems", 0)
        items = data.get("items", [])
        if total_items == 0 or not items or not isinstance(items, list):
            return []

        results: list[dict[str, Any]] = []
        for item in items:
            parsed = _parse_google_book_item(item)
            if parsed:
                results.append(parsed)

        return results

    except (ClientError, asyncio.TimeoutError) as err:
        _LOGGER.debug("Error querying Google Books API for query %s: %s", clean_query, err)
        return []
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error parsing Google Books response for query %s", clean_query)
        return []


async def _async_query_google_books(
    session: Any, isbn: str, api_key: str | None
) -> dict[str, Any] | None:
    """Query Google Books API for metadata."""
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    if api_key:
        url += f"&key={api_key}"

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with session.get(url) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "Google Books API returned status %s for ISBN %s",
                        response.status,
                        isbn,
                    )
                    return None
                data = await response.json()

        total_items = data.get("totalItems", 0)
        items = data.get("items", [])
        if total_items == 0 or not items or not isinstance(items, list):
            return None

        parsed = _parse_google_book_item(items[0])
        if parsed is None:
            return None

        if not parsed["isbn"]:
            parsed["isbn"] = isbn

        return parsed

    except (ClientError, asyncio.TimeoutError) as err:
        # Expected failure mode (network/timeout) - fall back to the next
        # provider without alarming the user.
        _LOGGER.debug("Error querying Google Books API for ISBN %s: %s", isbn, err)
        return None
    except Exception:  # noqa: BLE001 - see comment below
        # Anything else (e.g. an unexpected response shape breaking the
        # parsing above) is a bug, not an expected "ISBN not found" case.
        # Still fall back to Open Library, but log loudly so it doesn't
        # get silently mistaken for a normal "no match".
        _LOGGER.exception("Unexpected error parsing Google Books response for ISBN %s", isbn)
        return None


async def _async_query_open_library(session: Any, isbn: str) -> dict[str, Any] | None:
    """Query Open Library API for metadata."""
    bib_key = f"ISBN:{isbn}"
    url = f"https://openlibrary.org/api/books?bibkeys={bib_key}&format=json&jscmd=data"

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with session.get(url) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "Open Library API returned status %s for ISBN %s",
                        response.status,
                        isbn,
                    )
                    return None
                data = await response.json()

        book_data = data.get(bib_key)
        if not book_data:
            return None

        title = book_data.get("title", "").strip()
        if not title:
            return None

        authors_raw = book_data.get("authors", [])
        authors_list = [
            a.get("name") for a in authors_raw if isinstance(a, dict) and a.get("name")
        ]
        author = ", ".join(authors_list) if authors_list else "Unbekannter Autor"

        published_date = book_data.get("publish_date", "")

        covers = book_data.get("cover", {})
        cover_url = (
            covers.get("large")
            or covers.get("medium")
            or covers.get("small")
        )
        if cover_url and cover_url.startswith("http://"):
            cover_url = "https://" + cover_url[7:]

        return {
            "isbn": isbn,
            "title": title,
            "author": author,
            "published_date": published_date,
            "cover_url": cover_url or "",
            "source": "open_library",
        }

    except (ClientError, asyncio.TimeoutError) as err:
        # Expected failure mode (network/timeout) - no more providers to
        # fall back to, so lookup_isbn simply reports "not found".
        _LOGGER.debug("Error querying Open Library API for ISBN %s: %s", isbn, err)
        return None
    except Exception:  # noqa: BLE001 - see comment below
        # Anything else (e.g. an unexpected response shape breaking the
        # parsing above) is a bug, not an expected "ISBN not found" case.
        # Log loudly so it doesn't get silently mistaken for a normal
        # "no match" - this is our last fallback, so nothing downstream
        # will catch it either.
        _LOGGER.exception("Unexpected error parsing Open Library response for ISBN %s", isbn)
        return None


async def async_ai_lookup_series(
    hass: HomeAssistant, title: str, author: str
) -> dict[str, Any]:
    """Look up book series information using Home Assistant's AI Task platform."""
    try:
        from homeassistant.components import ai_task
    except ImportError as err:
        _LOGGER.warning(
            "AI Task component (homeassistant.components.ai_task) is not available: %s",
            err,
        )
        raise RuntimeError(
            "AI Task platform is not available in this Home Assistant environment."
        ) from err

    instructions = (
        f"Identifiziere die Buchreihe für das Buch '{title}' von '{author}'. "
        "Nenne alle bekannten Bände dieser Reihe mit Titel und Reihenfolge (1, 2, 3...). "
        "Falls das Buch zu keiner Buchreihe gehört oder du unsicher bist, setze is_series auf false."
    )

    schema = vol.Schema(
        {
            vol.Required("is_series"): bool,
            vol.Optional("series_name"): vol.Any(str, None),
            vol.Optional("books", default=[]): [
                vol.Schema(
                    {
                        vol.Required("title"): str,
                        vol.Optional("order"): vol.Any(int, None),
                    }
                )
            ],
        }
    )

    try:
        result = await ai_task.async_generate_data(
            hass,
            task_name="library_tracker_series_lookup",
            instructions=instructions,
            structure=schema,
        )
        if isinstance(result, dict):
            return result
        return {"is_series": False, "series_name": None, "books": []}
    except Exception as err:
        _LOGGER.warning(
            "Error generating AI series data for '%s' by '%s': %s",
            title,
            author,
            err,
        )
        raise RuntimeError(f"KI-Serien-Suche fehlgeschlagen: {err}") from err
