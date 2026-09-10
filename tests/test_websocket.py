"""Tests for WebSocket API in HA Library Tracker."""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.library_tracker.const import DOMAIN
from custom_components.library_tracker.db import LibraryTrackerDatabase
from custom_components.library_tracker.websocket_api import (
    async_register_websocket_commands,
    ws_authors_list,
    ws_authors_set_favorite,
    ws_authors_set_rating,
    ws_books_add,
    ws_books_ai_series_lookup,
    ws_books_delete,
    ws_books_list,
    ws_books_update,
    ws_lookup_isbn,
)


@pytest.fixture
def mock_hass() -> Generator[HomeAssistant, None, None]:
    """Fixture for mock HomeAssistant object with database initialized."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        db = LibraryTrackerDatabase(db_path)
        db.init_db()

        hass.data[DOMAIN] = {"db": db}

        async def async_add_executor_job(target, *args, **kwargs):
            return target(*args, **kwargs)

        hass.async_add_executor_job = AsyncMock(side_effect=async_add_executor_job)
        hass.config_entries.async_entries.return_value = []
        yield hass


def test_async_register_websocket_commands(mock_hass: HomeAssistant) -> None:
    """Test registration of custom WebSocket commands."""
    with patch(
        "homeassistant.components.websocket_api.async_register_command"
    ) as mock_register:
        async_register_websocket_commands(mock_hass)
        assert mock_register.call_count == 11
        assert mock_hass.data[DOMAIN]["ws_commands_registered"] is True

        # Second call should be a no-op
        mock_register.reset_mock()
        async_register_websocket_commands(mock_hass)
        mock_register.assert_not_called()


@pytest.mark.asyncio
async def test_ws_books_add_and_list(mock_hass: HomeAssistant) -> None:
    """Test adding a book and listing books via WebSocket handlers."""
    conn = MagicMock()

    # Add book
    add_msg = {
        "id": 1,
        "type": "library_tracker/books/add",
        "isbn": "9780131103627",
        "title": "The C Programming Language",
        "author": "Kernighan & Ritchie",
        "status": "gelesen",
        "rating": 5,
    }
    await inspect.unwrap(ws_books_add)(mock_hass, conn, add_msg)
    conn.send_result.assert_called_once()
    result_book = conn.send_result.call_args[0][1]
    assert result_book["title"] == "The C Programming Language"
    assert result_book["rating"] == 5

    # List books
    conn.reset_mock()
    list_msg = {"id": 2, "type": "library_tracker/books/list", "status": "gelesen"}
    await inspect.unwrap(ws_books_list)(mock_hass, conn, list_msg)
    conn.send_result.assert_called_once()
    books = conn.send_result.call_args[0][1]
    assert len(books) == 1
    assert books[0]["isbn"] == "9780131103627"


@pytest.mark.asyncio
async def test_ws_books_update_and_delete(mock_hass: HomeAssistant) -> None:
    """Test updating and deleting a book via WebSocket handlers."""
    conn = MagicMock()

    # First add a book
    add_msg = {
        "id": 1,
        "type": "library_tracker/books/add",
        "isbn": "12345",
        "title": "Initial Title",
        "author": "Initial Author",
        "status": "ungelesen",
    }
    await inspect.unwrap(ws_books_add)(mock_hass, conn, add_msg)
    book_id = conn.send_result.call_args[0][1]["id"]

    # Update book
    conn.reset_mock()
    update_msg = {
        "id": 2,
        "type": "library_tracker/books/update",
        "book_id": book_id,
        "status": "gelesen",
        "rating": 4,
    }
    await inspect.unwrap(ws_books_update)(mock_hass, conn, update_msg)
    conn.send_result.assert_called_once()
    updated = conn.send_result.call_args[0][1]
    assert updated["status"] == "gelesen"
    assert updated["rating"] == 4

    # Delete book
    conn.reset_mock()
    delete_msg = {
        "id": 3,
        "type": "library_tracker/books/delete",
        "book_id": book_id,
    }
    await inspect.unwrap(ws_books_delete)(mock_hass, conn, delete_msg)
    conn.send_result.assert_called_once()
    assert conn.send_result.call_args[0][1] == {"success": True, "id": book_id}


@pytest.mark.asyncio
async def test_ws_authors_list_and_favorite(mock_hass: HomeAssistant) -> None:
    """Test listing authors and toggling favorite status via WebSocket handlers."""
    conn = MagicMock()

    # Add book to auto-create author
    await inspect.unwrap(ws_books_add)(
        mock_hass,
        conn,
        {
            "id": 1,
            "type": "library_tracker/books/add",
            "isbn": "111",
            "title": "Book 1",
            "author": "Famous Author",
            "status": "gelesen",
        },
    )

    # List authors
    conn.reset_mock()
    await inspect.unwrap(ws_authors_list)(
        mock_hass, conn, {"id": 2, "type": "library_tracker/authors/list"}
    )
    conn.send_result.assert_called_once()
    authors = conn.send_result.call_args[0][1]
    assert len(authors) == 1
    author_id = authors[0]["id"]
    assert authors[0]["is_favorite"] is False

    # Set favorite
    conn.reset_mock()
    await inspect.unwrap(ws_authors_set_favorite)(
        mock_hass,
        conn,
        {
            "id": 3,
            "type": "library_tracker/authors/set_favorite",
            "author_id": author_id,
            "is_favorite": True,
        },
    )
    conn.send_result.assert_called_once()
    updated_author = conn.send_result.call_args[0][1]
    assert updated_author["is_favorite"] is True


@pytest.mark.asyncio
async def test_ws_authors_set_rating(mock_hass: HomeAssistant) -> None:
    """Test setting author rating via WebSocket handler."""
    conn = MagicMock()

    # Add book to auto-create author
    await inspect.unwrap(ws_books_add)(
        mock_hass,
        conn,
        {
            "id": 1,
            "type": "library_tracker/books/add",
            "isbn": "111",
            "title": "Book 1",
            "author": "Famous Author",
            "status": "gelesen",
        },
    )

    # Get author id
    conn.reset_mock()
    await inspect.unwrap(ws_authors_list)(
        mock_hass, conn, {"id": 2, "type": "library_tracker/authors/list"}
    )
    authors = conn.send_result.call_args[0][1]
    author_id = authors[0]["id"]

    # Set rating to 4
    conn.reset_mock()
    await inspect.unwrap(ws_authors_set_rating)(
        mock_hass,
        conn,
        {
            "id": 3,
            "type": "library_tracker/authors/set_rating",
            "author_id": author_id,
            "rating": 4,
        },
    )
    conn.send_result.assert_called_once()
    updated_author = conn.send_result.call_args[0][1]
    assert updated_author["rating"] == 4

    # Clear rating
    conn.reset_mock()
    await inspect.unwrap(ws_authors_set_rating)(
        mock_hass,
        conn,
        {
            "id": 4,
            "type": "library_tracker/authors/set_rating",
            "author_id": author_id,
            "rating": None,
        },
    )
    conn.send_result.assert_called_once()
    updated_author = conn.send_result.call_args[0][1]
    assert updated_author["rating"] is None

    # Error case: unknown author_id
    conn.reset_mock()
    await inspect.unwrap(ws_authors_set_rating)(
        mock_hass,
        conn,
        {
            "id": 5,
            "type": "library_tracker/authors/set_rating",
            "author_id": 999,
            "rating": 3,
        },
    )
    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_found"

    # Error case: missing author_id
    conn.reset_mock()
    await inspect.unwrap(ws_authors_set_rating)(
        mock_hass,
        conn,
        {
            "id": 6,
            "type": "library_tracker/authors/set_rating",
            "rating": 3,
        },
    )
    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "invalid_format"


@pytest.mark.asyncio
async def test_ws_books_list_by_series(mock_hass: HomeAssistant) -> None:
    """Test listing books by series via WebSocket handler."""
    conn = MagicMock()

    # Add 2 books in same series
    await inspect.unwrap(ws_books_add)(
        mock_hass,
        conn,
        {
            "id": 1,
            "type": "library_tracker/books/add",
            "isbn": "111",
            "title": "Series Vol 1",
            "author": "Author A",
            "status": "gelesen",
            "series_id": "series_test",
            "series_order": 1,
        },
    )
    b1_id = conn.send_result.call_args[0][1]["id"]

    await inspect.unwrap(ws_books_add)(
        mock_hass,
        conn,
        {
            "id": 2,
            "type": "library_tracker/books/add",
            "isbn": "222",
            "title": "Series Vol 2",
            "author": "Author A",
            "status": "ungelesen",
            "series_id": "series_test",
            "series_order": 2,
        },
    )
    b2_id = conn.send_result.call_args[0][1]["id"]

    # List all in series
    conn.reset_mock()
    from custom_components.library_tracker.websocket_api import ws_books_list_by_series

    await inspect.unwrap(ws_books_list_by_series)(
        mock_hass,
        conn,
        {
            "id": 3,
            "type": "library_tracker/books/list_by_series",
            "series_id": "series_test",
        },
    )
    conn.send_result.assert_called_once()
    series_books = conn.send_result.call_args[0][1]
    assert len(series_books) == 2
    assert series_books[0]["id"] == b1_id
    assert series_books[1]["id"] == b2_id

    # List with exclude_book_id
    conn.reset_mock()
    await inspect.unwrap(ws_books_list_by_series)(
        mock_hass,
        conn,
        {
            "id": 4,
            "type": "library_tracker/books/list_by_series",
            "series_id": "series_test",
            "exclude_book_id": b1_id,
        },
    )
    conn.send_result.assert_called_once()
    series_books_filtered = conn.send_result.call_args[0][1]
    assert len(series_books_filtered) == 1
    assert series_books_filtered[0]["id"] == b2_id


@pytest.mark.asyncio
async def test_ws_books_ai_series_lookup(mock_hass: HomeAssistant) -> None:
    """Test AI series lookup WebSocket handler."""
    conn = MagicMock()

    # First add a book
    add_msg = {
        "id": 1,
        "type": "library_tracker/books/add",
        "isbn": "9780345339706",
        "title": "Der Herr der Ringe - Die Gefährten",
        "author": "J.R.R. Tolkien",
        "status": "gelesen",
    }
    await inspect.unwrap(ws_books_add)(mock_hass, conn, add_msg)
    book_id = conn.send_result.call_args[0][1]["id"]

    # Call AI series lookup successfully
    conn.reset_mock()
    fake_result = {
        "is_series": True,
        "series_name": "Der Herr der Ringe",
        "books": [{"title": "Die Gefährten", "order": 1}],
    }
    with patch(
        "custom_components.library_tracker.websocket_api.async_ai_series_lookup",
        return_value=fake_result,
    ):
        await inspect.unwrap(ws_books_ai_series_lookup)(
            mock_hass,
            conn,
            {
                "id": 2,
                "type": "library_tracker/books/ai_series_lookup",
                "book_id": book_id,
            },
        )

    conn.send_result.assert_called_once_with(2, fake_result)

    # Call with non-existent book_id
    conn.reset_mock()
    await inspect.unwrap(ws_books_ai_series_lookup)(
        mock_hass,
        conn,
        {
            "id": 3,
            "type": "library_tracker/books/ai_series_lookup",
            "book_id": 9999,
        },
    )
    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_found"

    # Call when AI service is unavailable (returns None)
    conn.reset_mock()
    with patch(
        "custom_components.library_tracker.websocket_api.async_ai_series_lookup",
        return_value=None,
    ):
        await inspect.unwrap(ws_books_ai_series_lookup)(
            mock_hass,
            conn,
            {
                "id": 4,
                "type": "library_tracker/books/ai_series_lookup",
                "book_id": book_id,
            },
        )

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "ai_task_not_available"


@pytest.mark.asyncio
async def test_ws_lookup_isbn(mock_hass: HomeAssistant) -> None:
    """Test lookup_isbn WebSocket handler."""
    conn = MagicMock()

    fake_metadata = {
        "isbn": "9780131103627",
        "title": "The C Programming Language",
        "author": "Brian W. Kernighan",
        "published_date": "1988",
        "cover_url": "https://example.com/cover.jpg",
        "source": "google_books",
    }

    with patch(
        "custom_components.library_tracker.websocket_api.async_lookup_isbn",
        return_value=fake_metadata,
    ):
        await inspect.unwrap(ws_lookup_isbn)(
            mock_hass,
            conn,
            {"id": 1, "type": "library_tracker/lookup_isbn", "isbn": "9780131103627"},
        )

    conn.send_result.assert_called_once_with(1, fake_metadata)

    # Test lookup_isbn when not found
    conn.reset_mock()
    with patch(
        "custom_components.library_tracker.websocket_api.async_lookup_isbn",
        return_value=None,
    ):
        await inspect.unwrap(ws_lookup_isbn)(
            mock_hass,
            conn,
            {"id": 2, "type": "library_tracker/lookup_isbn", "isbn": "0000000000"},
        )

    conn.send_error.assert_called_once()
