"""Metadata API module for looking up book information by ISBN."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

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
        if total_items == 0 or not items:
            return None

        volume_info = items[0].get("volumeInfo", {})
        title = volume_info.get("title", "").strip()
        if not title:
            return None

        authors_list = volume_info.get("authors", [])
        author = ", ".join(authors_list) if authors_list else "Unbekannter Autor"

        published_date = volume_info.get("publishedDate", "")

        image_links = volume_info.get("imageLinks", {})
        cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        if cover_url and cover_url.startswith("http://"):
            cover_url = "https://" + cover_url[7:]

        return {
            "isbn": isbn,
            "title": title,
            "author": author,
            "published_date": published_date,
            "cover_url": cover_url or "",
            "source": "google_books",
        }

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
