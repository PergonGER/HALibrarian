"""Tests for metadata API in HA Library Tracker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.library_tracker.api import (
    async_find_cover_url,
    async_lookup_isbn,
    async_search_books_by_text,
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
                        "seriesInfo": {
                            "volumeSeries": [
                                {
                                    "seriesId": "series_c_prog",
                                    "orderNumber": "1"
                                }
                            ]
                        }
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
    assert result["series_id"] == "series_c_prog"
    assert result["series_order"] == 1
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
async def test_async_lookup_isbn_google_isbn_mismatch_falls_back() -> None:
    """Google's isbn: search is a text search, not an exact lookup - it can
    return a completely unrelated book for an ISBN it doesn't have well
    indexed. If the returned item's own ISBN contradicts the one we
    queried, that match must be discarded (falling back to Open Library)
    instead of silently handing back the wrong book's metadata.
    """
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
                        "title": "Gefühlte Dreißig - Ein Hoffnungsbote",
                        "authors": ["Bernd Gieseking"],
                        "industryIdentifiers": [
                            {
                                "type": "ISBN_13",
                                "identifier": "9783596703616",
                            }
                        ],
                    }
                }
            ],
        }
    )
    mock_google_cm = AsyncMock()
    mock_google_cm.__aenter__.return_value = mock_google_resp

    mock_ol_resp = AsyncMock()
    mock_ol_resp.status = 200
    mock_ol_resp.json = AsyncMock(
        return_value={
            "ISBN:9783596703678": {
                "title": "Correct Book From Open Library",
                "authors": [{"name": "Correct Author"}],
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
        result = await async_lookup_isbn(mock_hass, "9783596703678")

    assert result is not None
    assert result["title"] == "Correct Book From Open Library"
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


@pytest.mark.asyncio
async def test_async_find_cover_url_google_success() -> None:
    """Test finding cover via Google Books API."""
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
                        "imageLinks": {
                            "thumbnail": "http://books.google.com/books/cover.jpg"
                        },
                    }
                }
            ],
        }
    )
    cm = AsyncMock()
    cm.__aenter__.return_value = mock_google_resp
    mock_session.get.return_value = cm

    with patch(
        "custom_components.library_tracker.api.async_get_clientsession",
        return_value=mock_session,
    ):
        cover = await async_find_cover_url(mock_hass, "9780132350884")

    assert cover == "https://books.google.com/books/cover.jpg"


@pytest.mark.asyncio
async def test_async_find_cover_url_accepts_isbn_mismatch() -> None:
    """A cover-only lookup must accept a Google Books hit even if the
    item's own ISBN doesn't match the one we queried - unlike
    async_lookup_isbn(), where the same mismatch is rejected to avoid
    substituting a wrong book's title/author. Books still missing a cover
    are disproportionately ones whose stored ISBN didn't cleanly match
    Google's index in the first place, so a strict match here would keep
    rejecting most of them again.
    """
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
                        "title": "Das Profil",
                        "authors": ["Hubertus Borck"],
                        "imageLinks": {
                            "thumbnail": "http://books.google.com/cover.jpg"
                        },
                        "industryIdentifiers": [
                            {"type": "ISBN_13", "identifier": "9789999999999"}
                        ],
                    }
                }
            ],
        }
    )
    cm = AsyncMock()
    cm.__aenter__.return_value = mock_google_resp
    mock_session.get.return_value = cm

    with patch(
        "custom_components.library_tracker.api.async_get_clientsession",
        return_value=mock_session,
    ):
        cover = await async_find_cover_url(mock_hass, "9781234567897")

    assert cover == "https://books.google.com/cover.jpg"


@pytest.mark.asyncio
async def test_async_find_cover_url_open_library_and_direct_fallback() -> None:
    """Test finding cover falling back to Open Library API and then direct endpoint."""
    mock_hass = MagicMock()

    # 1. Test Open Library API fallback
    mock_session1 = MagicMock()
    google_empty = AsyncMock()
    google_empty.status = 200
    google_empty.json = AsyncMock(return_value={"totalItems": 0})
    google_cm = AsyncMock()
    google_cm.__aenter__.return_value = google_empty

    ol_resp = AsyncMock()
    ol_resp.status = 200
    ol_resp.json = AsyncMock(
        return_value={
            "ISBN:9780132350884": {
                "title": "Clean Code",
                "cover": {"large": "https://covers.openlibrary.org/b/id/123-L.jpg"},
            }
        }
    )
    ol_cm = AsyncMock()
    ol_cm.__aenter__.return_value = ol_resp
    mock_session1.get.side_effect = [google_cm, ol_cm]

    with patch(
        "custom_components.library_tracker.api.async_get_clientsession",
        return_value=mock_session1,
    ):
        cover = await async_find_cover_url(mock_hass, "9780132350884")
    assert cover == "https://covers.openlibrary.org/b/id/123-L.jpg"

    # 2. Test direct HEAD endpoint fallback
    mock_session2 = MagicMock()
    ol_empty = AsyncMock()
    ol_empty.status = 200
    ol_empty.json = AsyncMock(return_value={})
    ol_empty_cm = AsyncMock()
    ol_empty_cm.__aenter__.return_value = ol_empty
    mock_session2.get.side_effect = [google_cm, ol_empty_cm]

    head_resp = AsyncMock()
    head_resp.status = 200
    head_cm = AsyncMock()
    head_cm.__aenter__.return_value = head_resp
    mock_session2.head.return_value = head_cm

    with patch(
        "custom_components.library_tracker.api.async_get_clientsession",
        return_value=mock_session2,
    ):
        cover_direct = await async_find_cover_url(mock_hass, "9780132350884")
    assert (
        cover_direct
        == "https://covers.openlibrary.org/b/isbn/9780132350884-L.jpg?default=false"
    )
    # aiohttp's .head() defaults to NOT following redirects (unlike
    # .get()) - must be passed explicitly, otherwise a real cover behind
    # Open Library's routine 302 redirect gets misread as absent.
    assert mock_session2.head.call_args.kwargs.get("allow_redirects") is True

    # 3. Test direct HEAD endpoint returning 404 (None returned)
    mock_session3 = MagicMock()
    mock_session3.get.side_effect = [google_cm, ol_empty_cm]
    head_404 = AsyncMock()
    head_404.status = 404
    head_404_cm = AsyncMock()
    head_404_cm.__aenter__.return_value = head_404
    mock_session3.head.return_value = head_404_cm

    with patch(
        "custom_components.library_tracker.api.async_get_clientsession",
        return_value=mock_session3,
    ):
        cover_none = await async_find_cover_url(mock_hass, "9780132350884")
    assert cover_none is None


@pytest.mark.asyncio
async def test_async_find_cover_url_invalid_isbn() -> None:
    """Test async_find_cover_url with invalid or empty ISBN."""
    mock_hass = MagicMock()
    res = await async_find_cover_url(mock_hass, "  -  ")
    assert res is None


@pytest.mark.asyncio
async def test_async_search_books_by_text_success() -> None:
    """Test free text search with Google Books API returning results."""
    mock_session = MagicMock()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "totalItems": 2,
            "items": [
                {
                    "volumeInfo": {
                        "title": "Der Schwarm",
                        "authors": ["Frank Schätzing"],
                        "publishedDate": "2004",
                        "imageLinks": {
                            "thumbnail": "http://books.google.com/schwarm.jpg"
                        },
                        "industryIdentifiers": [
                            {"type": "ISBN_10", "identifier": "3462033743"},
                            {"type": "ISBN_13", "identifier": "9783462033748"},
                        ],
                    }
                },
                {
                    "volumeInfo": {
                        "title": "Limit",
                        "authors": ["Frank Schätzing"],
                        "publishedDate": "2009",
                    }
                },
            ],
        }
    )

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.get.return_value = cm

    results = await async_search_books_by_text(
        mock_session, "Frank Schätzing", api_key="key123"
    )

    assert len(results) == 2
    assert results[0]["title"] == "Der Schwarm"
    assert results[0]["author"] == "Frank Schätzing"
    assert results[0]["isbn"] == "9783462033748"
    assert results[0]["cover_url"] == "https://books.google.com/schwarm.jpg"

    assert results[1]["title"] == "Limit"
    assert results[1]["author"] == "Frank Schätzing"
    assert results[1]["isbn"] == ""


@pytest.mark.asyncio
async def test_async_search_books_by_text_empty_query() -> None:
    """Test searching with an empty query."""
    mock_session = MagicMock()
    results = await async_search_books_by_text(mock_session, "   ")
    assert results == []
    mock_session.get.assert_not_called()


@pytest.mark.asyncio
async def test_async_search_books_by_text_no_results() -> None:
    """Test search returning no items."""
    mock_session = MagicMock()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"totalItems": 0})

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.get.return_value = cm

    results = await async_search_books_by_text(mock_session, "Unknown Query")
    assert results == []


@pytest.mark.asyncio
async def test_async_ai_lookup_series_success() -> None:
    """Test successful AI series lookup."""
    mock_hass = MagicMock()
    fake_ai_data = {
        "is_series": True,
        "series_name": "Harry Potter",
        "books": [
            {"title": "Harry Potter und der Stein der Weisen", "order": 1},
            {"title": "Harry Potter und die Kammer des Schreckens", "order": 2},
        ],
    }
    # async_generate_data() returns a GenDataTaskResult dataclass with the
    # structured payload in .data, not a plain dict - mock that shape so
    # this test actually exercises the real return-value handling.
    fake_result = MagicMock()
    fake_result.data = fake_ai_data

    mock_ai_task = MagicMock()
    mock_ai_task.async_generate_data = AsyncMock(return_value=fake_result)

    with patch.dict("sys.modules", {"homeassistant.components.ai_task": mock_ai_task}):
        from custom_components.library_tracker.api import async_ai_lookup_series

        res = await async_ai_lookup_series(
            mock_hass, "Harry Potter und der Stein der Weisen", "J.K. Rowling"
        )
        assert res["is_series"] is True
        assert res["series_name"] == "Harry Potter"
        assert len(res["books"]) == 2


@pytest.mark.asyncio
async def test_async_ai_lookup_series_error() -> None:
    """Test AI series lookup when ai_task fails."""
    mock_hass = MagicMock()

    mock_ai_task = MagicMock()
    mock_ai_task.async_generate_data = AsyncMock(
        side_effect=Exception("Provider unavailable")
    )

    with patch.dict("sys.modules", {"homeassistant.components.ai_task": mock_ai_task}):
        from custom_components.library_tracker.api import async_ai_lookup_series

        with pytest.raises(RuntimeError) as exc_info:
            await async_ai_lookup_series(mock_hass, "Some Title", "Some Author")
        assert "KI-Serien-Suche fehlgeschlagen" in str(exc_info.value)
