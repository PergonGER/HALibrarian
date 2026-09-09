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
    )

    assert book["id"] is not None
    assert book["isbn"] == "9780131103627"
    assert book["title"] == "The C Programming Language"
    assert book["author"] == "Brian W. Kernighan"
    assert book["status"] == "gelesen"
    assert book["rating"] == 5

    books = db.get_books()
    assert len(books) == 1
    assert books[0]["id"] == book["id"]

    single = db.get_book(book["id"])
    assert single is not None
    assert single["title"] == "The C Programming Language"


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

    alpha_id = authors[0]["id"]
    updated_author = db.set_author_favorite(alpha_id, True)
    assert updated_author is not None
    assert updated_author["is_favorite"] is True

    authors_after = db.get_authors()
    assert [a for a in authors_after if a["id"] == alpha_id][0]["is_favorite"] is True
