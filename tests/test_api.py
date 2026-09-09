"""Tests for metadata API in HA Library Tracker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.library_tracker.api import (
    async_lookup_isbn,
    clean_isbn,
)


def test_clean_isbn() -> None:
    """Test ISBN cleaning helper."""
    assert clean_isbn("978-0-13-110362-7") == "9780131103627"
    assert clean_isbn(" 978 0 13 110362 7 ") == "9780131103627"
    assert clean_isbn("0-306-40615-2") == "0306406152"
    assert clean_isbn("123456789X") == "123456789X"


@pytest.mark.asyncio
async def test_async_lookup_isbn_google_success() -> None:
    """Test successful lookup via Google Books API."""
    mock_hass = MagicMock()
    mock_session = MagicMock()

    mock_google_resp = AsyncMock()
    mock_google_resp.status = 200
    mock_google_resp.json = AsyncMock(
        return_value={
            "totalItems": 1,
            "items": [
                {
                    "volumeInfo": {
                        "title": "Clean Code",
                        "authors": ["Robert C. Martin"],
                        "publishedDate": "2008-08-01",
                        "imageLinks": {
                            "thumbnail": "http://books.google.com/books/cover.jpg"
                        },
                    }
                }
            ],
        }
    )

    # Make session.get return an async context manager yielding mock_google_resp
    cm = AsyncMock()
    cm.__aenter__.return_value = mock_google_resp
    mock_session.get.return_value = cm

    with patch(
        "custom_components.library_tracker.api.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await async_lookup_isbn(
            mock_hass, "978-0132350884", google_api_key="test_key"
        )

    assert result is not None
    assert result["title"] == "Clean Code"
    assert result["author"] == "Robert C. Martin"
    assert result["published_date"] == "2008-08-01"
    assert result["cover_url"] == "https://books.google.com/books/cover.jpg"
    assert result["source"] == "google_books"


@pytest.mark.asyncio
async def test_async_lookup_isbn_fallback_to_open_library() -> None:
    """Test fallback to Open Library when Google Books returns no items."""
    mock_hass = MagicMock()
    mock_session = MagicMock()

    mock_google_resp = AsyncMock()
    mock_google_resp.status = 200
    mock_google_resp.json = AsyncMock(return_value={"totalItems": 0})

    mock_google_cm = AsyncMock()
    mock_google_cm.__aenter__.return_value = mock_google_resp

    mock_ol_resp = AsyncMock()
    mock_ol_resp.status = 200
    mock_ol_resp.json = AsyncMock(
        return_value={
            "ISBN:9780132350884": {
                "title": "Clean Code OpenLibrary",
                "authors": [{"name": "Robert C. Martin"}],
                "publish_date": "2008",
                "cover": {"large": "https://covers.openlibrary.org/b/id/123-L.jpg"},
            }
        }
    )

    mock_ol_cm = AsyncMock()
    mock_ol_cm.__aenter__.return_value = mock_ol_resp

    mock_session.get.side_effect = [mock_google_cm, mock_ol_cm]

    with patch(
        "custom_components.library_tracker.api.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await async_lookup_isbn(mock_hass, "9780132350884")

    assert result is not None
    assert result["title"] == "Clean Code OpenLibrary"
    assert result["author"] == "Robert C. Martin"
    assert result["source"] == "open_library"


@pytest.mark.asyncio
async def test_async_lookup_isbn_not_found() -> None:
    """Test lookup when neither API finds the book."""
    mock_hass = MagicMock()
    mock_session = MagicMock()

    mock_google_resp = AsyncMock()
    mock_google_resp.status = 200
    mock_google_resp.json = AsyncMock(return_value={"totalItems": 0})
    mock_google_cm = AsyncMock()
    mock_google_cm.__aenter__.return_value = mock_google_resp

    mock_ol_resp = AsyncMock()
    mock_ol_resp.status = 200
    mock_ol_resp.json = AsyncMock(return_value={})
    mock_ol_cm = AsyncMock()
    mock_ol_cm.__aenter__.return_value = mock_ol_resp

    mock_session.get.side_effect = [mock_google_cm, mock_ol_cm]

    with patch(
        "custom_components.library_tracker.api.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await async_lookup_isbn(mock_hass, "0000000000000")

    assert result is None
