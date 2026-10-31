"""Tests for author releases background check in HA Library Tracker."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound

from custom_components.library_tracker import (
    async_check_author_releases,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.library_tracker.const import (
    CONF_AUTHOR_CHECK_INTERVAL,
    CONF_NOTIFY_SERVICE,
    DOMAIN,
)
from custom_components.library_tracker.db import LibraryTrackerDatabase


@pytest.fixture
def mock_hass() -> HomeAssistant:
    """Fixture providing a mock HomeAssistant instance with database initialized."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.bus = MagicMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        hass.config.path.side_effect = lambda *args: str(Path(tmpdir) / Path(*args)) if args else tmpdir
        db_path = str(Path(tmpdir) / "test.db")
        db = LibraryTrackerDatabase(db_path)
        db.init_db()

        hass.data[DOMAIN] = {"db": db}

        async def async_add_executor_job(target, *args, **kwargs):
            return target(*args, **kwargs)

        hass.async_add_executor_job = AsyncMock(side_effect=async_add_executor_job)
        yield hass


@pytest.mark.asyncio
async def test_author_check_flow(mock_hass: HomeAssistant) -> None:
    """Test full author release check flow:
    - Favorite author with new book triggers notify call and records in DB.
    - Subsequent check does not re-notify.
    - Book already in library is not notified.
    - Non-favorite author is ignored.
    """
    db: LibraryTrackerDatabase = mock_hass.data[DOMAIN]["db"]

    # Add authors
    # Author 1: Favorite
    db.add_book(isbn="9781111111111", title="Existing Book 1", author_name="Brandon Sanderson", status="gelesen")
    # Author 2: Not favorite
    db.add_book(isbn="9782222222222", title="Some Book", author_name="Patrick Rothfuss", status="gelesen")

    authors = db.get_authors()
    sanderson = [a for a in authors if a["name"] == "Brandon Sanderson"][0]
    db.set_author_favorite(sanderson["id"], True)

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.options = {CONF_NOTIFY_SERVICE: "notify.mobile_app_phone"}
    entry.data = {}

    found_books = [
        # Book 1: Already in library (ISBN match)
        {
            "isbn": "9781111111111",
            "title": "Existing Book 1",
            "author": "Brandon Sanderson",
            "published_date": "2010",
        },
        # Book 2: Already in library (Title + Author match, empty ISBN)
        {
            "isbn": "",
            "title": "existing book 1",
            "author": "Brandon Sanderson",
            "published_date": "2010",
        },
        # Book 3: Brand new book
        {
            "isbn": "9783333333333",
            "title": "Wind and Truth",
            "author": "Brandon Sanderson",
            "published_date": "2024-12-06",
        },
    ]

    with patch(
        "custom_components.library_tracker.async_search_books_by_author",
        AsyncMock(return_value=found_books),
    ) as mock_search:
        await async_check_author_releases(mock_hass, entry)

        # Verified search was called for favorite author only
        assert mock_search.call_count == 1
        assert mock_search.call_args[0][2] == "Brandon Sanderson"

        # Notify service was called once for Book 3
        mock_hass.services.async_call.assert_called_once_with(
            "notify",
            "mobile_app_phone",
            {
                "title": "Neues Buch von Brandon Sanderson",
                "message": "Neues Buch von Brandon Sanderson: „Wind and Truth“ (2024-12-06)",
            },
            blocking=True,
        )

        # Verified notification was recorded in DB
        assert db.has_author_notification(sanderson["id"], "Wind and Truth") is True

    # Run check a second time: Should not notify again for "Wind and Truth"
    mock_hass.services.async_call.reset_mock()
    with patch(
        "custom_components.library_tracker.async_search_books_by_author",
        AsyncMock(return_value=found_books),
    ):
        await async_check_author_releases(mock_hass, entry)
        mock_hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_author_check_notify_failure_resilient(mock_hass: HomeAssistant) -> None:
    """Test that a failure in sending notify does not crash and continues for other authors."""
    db: LibraryTrackerDatabase = mock_hass.data[DOMAIN]["db"]

    db.add_book(isbn="111", title="B1", author_name="Author One", status="gelesen")
    db.add_book(isbn="222", title="B2", author_name="Author Two", status="gelesen")

    authors = db.get_authors()
    a1 = [a for a in authors if a["name"] == "Author One"][0]
    a2 = [a for a in authors if a["name"] == "Author Two"][0]
    db.set_author_favorite(a1["id"], True)
    db.set_author_favorite(a2["id"], True)

    entry = MagicMock()
    entry.options = {CONF_NOTIFY_SERVICE: "notify.invalid_service"}
    entry.data = {}

    # Service call raises ServiceNotFound for first call, succeeds for second
    mock_hass.services.async_call.side_effect = [
        ServiceNotFound("notify", "invalid_service"),
        None,
    ]

    async def mock_search(hass, session, author_name, api_key=None):
        if author_name == "Author One":
            return [{"title": "New Book 1", "isbn": "111-new", "published_date": "2024"}]
        return [{"title": "New Book 2", "isbn": "222-new", "published_date": "2024"}]

    with patch(
        "custom_components.library_tracker.async_search_books_by_author",
        side_effect=mock_search,
    ):
        await async_check_author_releases(mock_hass, entry)

        # Both notifications should have been attempted
        assert mock_hass.services.async_call.call_count == 2
        # Both notifications recorded even when service call had error
        assert db.has_author_notification(a1["id"], "New Book 1") is True
        assert db.has_author_notification(a2["id"], "New Book 2") is True


@pytest.mark.asyncio
async def test_periodic_job_setup_and_unload() -> None:
    """Test periodic job scheduling in async_setup_entry and cancellation in async_unload_entry."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.data = {}
    mock_hass.config = MagicMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_hass.config.path.side_effect = lambda *args: str(Path(tmpdir) / Path(*args)) if args else tmpdir

        async def async_add_executor_job(target, *args, **kwargs):
            return target(*args, **kwargs)

        mock_hass.async_add_executor_job = AsyncMock(side_effect=async_add_executor_job)
        mock_hass.http.async_register_static_paths = AsyncMock()

        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {CONF_AUTHOR_CHECK_INTERVAL: 48}
        mock_entry.data = {}
        mock_entry.add_update_listener = MagicMock()

        mock_unsub = MagicMock()

        with (
            patch("custom_components.library_tracker.LibraryTrackerDatabase") as mock_db_cls,
            patch("custom_components.library_tracker.async_track_time_interval", return_value=mock_unsub) as mock_track,
            patch("custom_components.library_tracker.async_register_websocket_commands"),
            patch("custom_components.library_tracker._async_register_panel"),
        ):
            mock_db_cls.return_value.init_db = MagicMock()

            # Setup entry
            assert await async_setup_entry(mock_hass, mock_entry) is True
            mock_track.assert_called_once()
            # Interval timedelta should be 48 hours
            from datetime import timedelta
            assert mock_track.call_args[0][2] == timedelta(hours=48)
            mock_entry.async_on_unload.assert_any_call(mock_unsub)

            # Unload entry
            assert await async_unload_entry(mock_hass, mock_entry) is True
            mock_unsub.assert_called_once()
