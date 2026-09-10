"""Tests for database manager in HA Library Tracker."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sqlite3

import pytest

from custom_components.library_tracker.db import LibraryTrackerDatabase


@pytest.fixture
def db() -> LibraryTrackerDatabase:
    """Fixture for an initialized temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_library.db")
        database = LibraryTrackerDatabase(db_path)
        database.init_db()
        yield database


def test_init_db(db: LibraryTrackerDatabase) -> None:
    """Test table creation in database."""
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    assert "Authors" in tables
    assert "Books" in tables
    assert "Releases" in tables


def test_add_and_get_book(db: LibraryTrackerDatabase) -> None:
    """Test adding a book and retrieving it."""
    book = db.add_book(
        isbn="9780131103627",
        title="The C Programming Language",
        author_name="Brian W. Kernighan",
        status="gelesen",
        published_date="1988",
        cover_url="https://example.com/cover.jpg",
        rating=5,
        series_id="series_123",
        series_order=1,
    )

    assert book["id"] is not None
    assert book["isbn"] == "9780131103627"
    assert book["title"] == "The C Programming Language"
    assert book["author"] == "Brian W. Kernighan"
    assert book["status"] == "gelesen"
    assert book["rating"] == 5
    assert book["series_id"] == "series_123"
    assert book["series_order"] == 1

    books = db.get_books()
    assert len(books) == 1
    assert books[0]["id"] == book["id"]
    assert books[0]["series_id"] == "series_123"

    single = db.get_book(book["id"])
    assert single is not None
    assert single["title"] == "The C Programming Language"
    assert single["series_id"] == "series_123"


def test_get_books_by_series(db: LibraryTrackerDatabase) -> None:
    """Test retrieving books belonging to a series."""
    book1 = db.add_book(
        isbn="111",
        title="Series Vol 2",
        author_name="Author A",
        status="gelesen",
        series_id="series_abc",
        series_order=2,
    )
    book2 = db.add_book(
        isbn="222",
        title="Series Vol 1",
        author_name="Author A",
        status="gelesen",
        series_id="series_abc",
        series_order=1,
    )
    book3 = db.add_book(
        isbn="333",
        title="Series Vol Extra",
        author_name="Author A",
        status="ungelesen",
        series_id="series_abc",
        series_order=None,
    )
    db.add_book(
        isbn="444",
        title="Other Book",
        author_name="Author B",
        status="gelesen",
        series_id="series_xyz",
        series_order=1,
    )

    series_books = db.get_books_by_series("series_abc")
    assert len(series_books) == 3
    # Order should be Vol 1 (order 1), Vol 2 (order 2), Vol Extra (order None)
    assert series_books[0]["id"] == book2["id"]
    assert series_books[1]["id"] == book1["id"]
    assert series_books[2]["id"] == book3["id"]

    # Exclude book 2 (Vol 1)
    filtered_series = db.get_books_by_series("series_abc", exclude_book_id=book2["id"])
    assert len(filtered_series) == 2
    assert [b["id"] for b in filtered_series] == [book1["id"], book3["id"]]


def test_get_books_status_filter(db: LibraryTrackerDatabase) -> None:
    """Test filtering books by status."""
    db.add_book(
        isbn="111", title="Book One", author_name="Author A", status="gelesen"
    )
    db.add_book(
        isbn="222", title="Book Two", author_name="Author B", status="ungelesen"
    )
    db.add_book(
        isbn="333", title="Book Three", author_name="Author A", status="wunschliste"
    )

    gelesen = db.get_books(status="gelesen")
    assert len(gelesen) == 1
    assert gelesen[0]["title"] == "Book One"

    ungelesen = db.get_books(status="ungelesen")
    assert len(ungelesen) == 1
    assert ungelesen[0]["title"] == "Book Two"

    wunschliste = db.get_books(status="wunschliste")
    assert len(wunschliste) == 1
    assert wunschliste[0]["title"] == "Book Three"


def test_update_book(db: LibraryTrackerDatabase) -> None:
    """Test updating book details."""
    book = db.add_book(
        isbn="111", title="Original Title", author_name="Author A", status="ungelesen"
    )

    updated = db.update_book(
        book_id=book["id"],
        status="gelesen",
        rating=4,
        title="New Title",
        author_name="Author B",
    )

    assert updated is not None
    assert updated["status"] == "gelesen"
    assert updated["rating"] == 4
    assert updated["title"] == "New Title"
    assert updated["author"] == "Author B"

    # Test clearing rating
    cleared = db.update_book(book_id=book["id"], clear_rating=True)
    assert cleared is not None
    assert cleared["rating"] is None


def test_delete_book(db: LibraryTrackerDatabase) -> None:
    """Test deleting a book."""
    book = db.add_book(
        isbn="111", title="To Delete", author_name="Author A", status="ungelesen"
    )

    assert db.delete_book(book["id"]) is True
    assert db.get_book(book["id"]) is None
    assert db.delete_book(book["id"]) is False


def test_authors_and_favorite(db: LibraryTrackerDatabase) -> None:
    """Test listing authors and setting favorite status."""
    db.add_book(
        isbn="111", title="Book 1", author_name="Author Alpha", status="gelesen"
    )
    db.add_book(
        isbn="222", title="Book 2", author_name="Author Beta", status="ungelesen"
    )

    authors = db.get_authors()
    assert len(authors) == 2
    assert authors[0]["name"] == "Author Alpha"
    assert authors[0]["is_favorite"] is False
    assert authors[0]["rating"] is None

    alpha_id = authors[0]["id"]
    updated_author = db.set_author_favorite(alpha_id, True)
    assert updated_author is not None
    assert updated_author["is_favorite"] is True
    assert updated_author["rating"] is None

    authors_after = db.get_authors()
    assert [a for a in authors_after if a["id"] == alpha_id][0]["is_favorite"] is True


def test_author_rating(db: LibraryTrackerDatabase) -> None:
    """Test setting and clearing author ratings."""
    db.add_book(
        isbn="111", title="Book 1", author_name="Author Alpha", status="gelesen"
    )
    authors = db.get_authors()
    alpha_id = authors[0]["id"]
    assert authors[0]["rating"] is None

    # Set rating
    updated = db.set_author_rating(alpha_id, 5)
    assert updated is not None
    assert updated["rating"] == 5

    authors_after = db.get_authors()
    assert authors_after[0]["rating"] == 5

    # Clear rating
    cleared = db.set_author_rating(alpha_id, None)
    assert cleared is not None
    assert cleared["rating"] is None

    # Non-existent author
    assert db.set_author_rating(999, 4) is None

    # Invalid ratings
    with pytest.raises(ValueError):
        db.set_author_rating(alpha_id, 0)

    with pytest.raises(ValueError):
        db.set_author_rating(alpha_id, 6)


def test_migration_existing_authors_table() -> None:
    """Test migration against an existing Authors table without rating column."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "old_library.db")

        # Simulate existing database with old schema (without rating column)
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE Authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_favorite INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute(
            "INSERT INTO Authors (name, is_favorite) VALUES ('Old Author', 1);"
        )
        conn.commit()
        conn.close()

        # Run init_db migration
        database = LibraryTrackerDatabase(db_path)
        database.init_db()

        # Verify old author data is preserved and rating column exists
        authors = database.get_authors()
        assert len(authors) == 1
        assert authors[0]["name"] == "Old Author"
        assert authors[0]["is_favorite"] is True
        assert authors[0]["rating"] is None

        # Verify idempotency by calling init_db again
        database.init_db()
        authors_again = database.get_authors()
        assert len(authors_again) == 1
