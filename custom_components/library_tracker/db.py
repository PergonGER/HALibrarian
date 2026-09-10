"""Database manager for HA Library Tracker using SQLite."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

_LOGGER = logging.getLogger(__name__)


class LibraryTrackerDatabase:
    """Class to manage SQLite database operations for Library Tracker."""

    def __init__(self, db_path: str) -> None:
        """Initialize database manager with SQLite file path."""
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Create database tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS Authors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    is_favorite INTEGER NOT NULL DEFAULT 0,
                    rating INTEGER
                );
                """
            )

            # Migration: Ensure rating column exists on Authors table
            cursor.execute("PRAGMA table_info(Authors);")
            columns = {row["name"] for row in cursor.fetchall()}
            if "rating" not in columns:
                cursor.execute("ALTER TABLE Authors ADD COLUMN rating INTEGER;")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS Books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isbn TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author_id INTEGER NOT NULL,
                    published_date TEXT,
                    cover_url TEXT,
                    status TEXT NOT NULL,
                    rating INTEGER,
                    series_id TEXT,
                    series_order INTEGER,
                    FOREIGN KEY (author_id) REFERENCES Authors(id) ON DELETE CASCADE
                );
                """
            )

            # Migration: Ensure series_id and series_order columns exist on Books table
            cursor.execute("PRAGMA table_info(Books);")
            books_columns = {row["name"] for row in cursor.fetchall()}
            if "series_id" not in books_columns:
                cursor.execute("ALTER TABLE Books ADD COLUMN series_id TEXT;")
            if "series_order" not in books_columns:
                cursor.execute("ALTER TABLE Books ADD COLUMN series_order INTEGER;")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS Releases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    release_date TEXT,
                    notified_bool INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (author_id) REFERENCES Authors(id) ON DELETE CASCADE
                );
                """
            )

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_books_status ON Books(status);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_books_author ON Books(author_id);"
            )
            conn.commit()

    def _get_or_create_author(self, conn: sqlite3.Connection, name: str) -> int:
        """Get existing author id or create a new author."""
        clean_name = name.strip()
        cursor = conn.cursor()

        # INSERT OR IGNORE + re-SELECT instead of SELECT-then-INSERT: two
        # executor-thread calls racing to create the same new author would
        # otherwise both pass the initial SELECT before either INSERTs,
        # and the second INSERT would fail on the UNIQUE constraint.
        cursor.execute(
            "INSERT OR IGNORE INTO Authors (name, is_favorite) VALUES (?, 0)",
            (clean_name,),
        )
        cursor.execute("SELECT id FROM Authors WHERE name = ?", (clean_name,))
        row = cursor.fetchone()
        return int(row["id"])

    def get_books(self, status: str | None = None) -> list[dict[str, Any]]:
        """Retrieve all books, optionally filtered by status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    b.id,
                    b.isbn,
                    b.title,
                    b.author_id,
                    a.name AS author,
                    b.published_date,
                    b.cover_url,
                    b.status,
                    b.rating,
                    b.series_id,
                    b.series_order
                FROM Books b
                JOIN Authors a ON b.author_id = a.id
            """
            params: list[Any] = []
            if status:
                query += " WHERE b.status = ?"
                params.append(status)

            query += " ORDER BY b.id DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_book(self, book_id: int) -> dict[str, Any] | None:
        """Retrieve a single book by id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    b.id,
                    b.isbn,
                    b.title,
                    b.author_id,
                    a.name AS author,
                    b.published_date,
                    b.cover_url,
                    b.status,
                    b.rating,
                    b.series_id,
                    b.series_order
                FROM Books b
                JOIN Authors a ON b.author_id = a.id
                WHERE b.id = ?
                """,
                (book_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_book(
        self,
        isbn: str,
        title: str,
        author_name: str,
        status: str,
        published_date: str | None = None,
        cover_url: str | None = None,
        rating: int | None = None,
        series_id: str | None = None,
        series_order: int | None = None,
    ) -> dict[str, Any]:
        """Add a new book to the database."""
        with self._get_connection() as conn:
            author_id = self._get_or_create_author(conn, author_name)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO Books (isbn, title, author_id, published_date, cover_url, status, rating, series_id, series_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    isbn,
                    title,
                    author_id,
                    published_date,
                    cover_url,
                    status,
                    rating,
                    series_id,
                    series_order,
                ),
            )
            book_id = cursor.lastrowid
            conn.commit()

        # Retrieve inserted book
        book = self.get_book(book_id)
        if book is None:
            raise RuntimeError("Failed to retrieve newly added book.")
        return book

    def update_book(
        self,
        book_id: int,
        status: str | None = None,
        rating: int | None = None,
        title: str | None = None,
        author_name: str | None = None,
        published_date: str | None = None,
        cover_url: str | None = None,
        clear_rating: bool = False,
    ) -> dict[str, Any] | None:
        """Update fields of an existing book."""
        existing = self.get_book(book_id)
        if existing is None:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates: list[str] = []
            params: list[Any] = []

            if title is not None:
                updates.append("title = ?")
                params.append(title)

            if author_name is not None:
                author_id = self._get_or_create_author(conn, author_name)
                updates.append("author_id = ?")
                params.append(author_id)

            if published_date is not None:
                updates.append("published_date = ?")
                params.append(published_date)

            if cover_url is not None:
                updates.append("cover_url = ?")
                params.append(cover_url)

            if status is not None:
                updates.append("status = ?")
                params.append(status)

            if clear_rating:
                updates.append("rating = NULL")
            elif rating is not None:
                updates.append("rating = ?")
                params.append(rating)

            if updates:
                query = f"UPDATE Books SET {', '.join(updates)} WHERE id = ?"
                params.append(book_id)
                cursor.execute(query, params)
                conn.commit()

        return self.get_book(book_id)

    def get_books_by_series(
        self, series_id: str, exclude_book_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve all books in the library with the given series_id.

        Ordered by series_order (NULLs last), then by id ASC.
        Optionally excludes a specific book_id.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    b.id,
                    b.isbn,
                    b.title,
                    b.author_id,
                    a.name AS author,
                    b.published_date,
                    b.cover_url,
                    b.status,
                    b.rating,
                    b.series_id,
                    b.series_order
                FROM Books b
                JOIN Authors a ON b.author_id = a.id
                WHERE b.series_id = ?
            """
            params: list[Any] = [series_id]

            if exclude_book_id is not None:
                query += " AND b.id != ?"
                params.append(exclude_book_id)

            query += " ORDER BY CASE WHEN b.series_order IS NULL THEN 1 ELSE 0 END, b.series_order ASC, b.id ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_book(self, book_id: int) -> bool:
        """Delete a book by id. Returns True if deleted, False if not found."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Books WHERE id = ?", (book_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_authors(self) -> list[dict[str, Any]]:
        """Retrieve all authors with at least one book, plus favorites.

        Authors with zero books are hidden (they're just clutter, usually
        left over from a deleted book) unless marked as favorite - a
        favorited author with no current books is a deliberate "track
        their future releases" entry (see Session 4 author-tracking) and
        must stay visible.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    a.id,
                    a.name,
                    a.is_favorite,
                    a.rating
                FROM Authors a
                WHERE a.is_favorite = 1
                   OR EXISTS (SELECT 1 FROM Books b WHERE b.author_id = a.id)
                ORDER BY a.name ASC
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "is_favorite": bool(row["is_favorite"]),
                    "rating": row["rating"],
                }
                for row in rows
            ]

    def set_author_favorite(
        self, author_id: int, is_favorite: bool
    ) -> dict[str, Any] | None:
        """Set or unset author favorite status."""
        fav_val = 1 if is_favorite else 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Authors SET is_favorite = ? WHERE id = ?", (fav_val, author_id)
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            cursor.execute(
                "SELECT id, name, is_favorite, rating FROM Authors WHERE id = ?", (author_id,)
            )
            row = cursor.fetchone()
            return (
                {
                    "id": row["id"],
                    "name": row["name"],
                    "is_favorite": bool(row["is_favorite"]),
                    "rating": row["rating"],
                }
                if row
                else None
            )

    def set_author_rating(
        self, author_id: int, rating: int | None
    ) -> dict[str, Any] | None:
        """Set or clear author rating (1-5 or None)."""
        if rating is not None and (not isinstance(rating, int) or not (1 <= rating <= 5)):
            raise ValueError("Rating must be between 1 and 5, or None.")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Authors SET rating = ? WHERE id = ?", (rating, author_id)
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            cursor.execute(
                "SELECT id, name, is_favorite, rating FROM Authors WHERE id = ?", (author_id,)
            )
            row = cursor.fetchone()
            return (
                {
                    "id": row["id"],
                    "name": row["name"],
                    "is_favorite": bool(row["is_favorite"]),
                    "rating": row["rating"],
                }
                if row
                else None
            )
