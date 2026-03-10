import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.environ.get("CHANGESET_DB_PATH", ".changesets.db")


class ZoteroSyncState:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    def _create_table(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS zotero_sync_state (
                id           INTEGER PRIMARY KEY CHECK (id = 1),
                last_version INTEGER NOT NULL DEFAULT 0,
                last_synced  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS zotero_paper_sync (
                paper_key    TEXT PRIMARY KEY,
                paper_title  TEXT NOT NULL DEFAULT '',
                last_synced  TEXT,
                changeset_id TEXT
            );
            CREATE TABLE IF NOT EXISTS zotero_papers (
                key               TEXT PRIMARY KEY,
                title             TEXT NOT NULL DEFAULT '',
                authors           TEXT NOT NULL DEFAULT '[]',
                doi               TEXT NOT NULL DEFAULT '',
                abstract          TEXT NOT NULL DEFAULT '',
                publication_title TEXT NOT NULL DEFAULT '',
                year              TEXT NOT NULL DEFAULT '',
                item_type         TEXT NOT NULL DEFAULT '',
                url               TEXT NOT NULL DEFAULT '',
                cached_at         TEXT NOT NULL,
                annotation_count  INTEGER
            );
            CREATE TABLE IF NOT EXISTS zotero_collections (
                key               TEXT PRIMARY KEY,
                name              TEXT NOT NULL DEFAULT '',
                parent_collection TEXT,
                num_items         INTEGER NOT NULL DEFAULT 0,
                num_collections   INTEGER NOT NULL DEFAULT 0,
                cached_at         TEXT NOT NULL
            );
        """)
        # Migration: add annotation_count column to existing tables
        try:
            self._conn.execute(
                "ALTER TABLE zotero_papers ADD COLUMN annotation_count INTEGER"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    def get_last_version(self) -> int | None:
        row = self._conn.execute(
            "SELECT last_version FROM zotero_sync_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return row["last_version"]

    def set_last_version(self, version: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO zotero_sync_state (id, last_version, last_synced)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_version = excluded.last_version,
                last_synced  = excluded.last_synced
            """,
            (version, now),
        )
        self._conn.commit()

    def get_last_synced(self) -> str | None:
        row = self._conn.execute(
            "SELECT last_synced FROM zotero_sync_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return row["last_synced"]

    # --- Per-paper sync tracking ---

    def get_all_paper_syncs(self) -> dict[str, dict]:
        """Return all paper sync records keyed by paper_key."""
        rows = self._conn.execute("SELECT * FROM zotero_paper_sync").fetchall()
        return {
            row["paper_key"]: {
                "paper_title": row["paper_title"],
                "last_synced": row["last_synced"],
                "changeset_id": row["changeset_id"],
            }
            for row in rows
        }

    def get_paper_sync(self, paper_key: str) -> dict | None:
        """Return sync info for a single paper, or None."""
        row = self._conn.execute(
            "SELECT * FROM zotero_paper_sync WHERE paper_key = ?", (paper_key,)
        ).fetchone()
        if row is None:
            return None
        return {
            "paper_title": row["paper_title"],
            "last_synced": row["last_synced"],
            "changeset_id": row["changeset_id"],
        }

    def set_paper_sync(
        self, paper_key: str, paper_title: str, changeset_id: str
    ) -> None:
        """Upsert paper sync record with current timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO zotero_paper_sync (paper_key, paper_title, last_synced, changeset_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(paper_key) DO UPDATE SET
                paper_title  = excluded.paper_title,
                last_synced  = excluded.last_synced,
                changeset_id = excluded.changeset_id
            """,
            (paper_key, paper_title, now, changeset_id),
        )
        self._conn.commit()

    # --- Paper cache (zotero_papers table) ---

    def upsert_papers(self, papers: list[dict]) -> None:
        """Bulk upsert paper metadata into the cache."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.executemany(
            """
            INSERT INTO zotero_papers (key, title, authors, doi, abstract, publication_title, year, item_type, url, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                title             = excluded.title,
                authors           = excluded.authors,
                doi               = excluded.doi,
                abstract          = excluded.abstract,
                publication_title = excluded.publication_title,
                year              = excluded.year,
                item_type         = excluded.item_type,
                url               = excluded.url,
                cached_at         = excluded.cached_at
            """,
            [
                (
                    p["key"],
                    p.get("title", ""),
                    json.dumps(p.get("authors", [])),
                    p.get("doi", ""),
                    p.get("abstract", ""),
                    p.get("publication_title", ""),
                    p.get("year", ""),
                    p.get("item_type", ""),
                    p.get("url", ""),
                    now,
                )
                for p in papers
            ],
        )
        self._conn.commit()

    def _row_to_paper_dict(self, row: sqlite3.Row) -> dict:
        """Convert a zotero_papers row to a dict."""
        return {
            "key": row["key"],
            "title": row["title"],
            "authors": json.loads(row["authors"]),
            "doi": row["doi"],
            "abstract": row["abstract"],
            "publication_title": row["publication_title"],
            "year": row["year"],
            "item_type": row["item_type"],
            "url": row["url"],
            "cached_at": row["cached_at"],
            "annotation_count": row["annotation_count"],
        }

    def get_all_cached_papers(self) -> list[dict]:
        """Return all cached papers ordered by year DESC, title ASC."""
        rows = self._conn.execute(
            "SELECT * FROM zotero_papers ORDER BY year DESC, title ASC"
        ).fetchall()
        return [self._row_to_paper_dict(row) for row in rows]

    def get_cached_papers_paginated(
        self,
        offset: int = 0,
        limit: int = 25,
        search: str | None = None,
    ) -> tuple[list[dict], int]:
        """Return paginated cached papers with optional search filter."""
        where = ""
        params: list = []
        if search:
            where = "WHERE title LIKE ? OR authors LIKE ?"
            pattern = f"%{search}%"
            params = [pattern, pattern]

        count_row = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM zotero_papers {where}", params
        ).fetchone()
        total = count_row["cnt"]

        rows = self._conn.execute(
            f"SELECT * FROM zotero_papers {where} ORDER BY year DESC, title ASC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return [self._row_to_paper_dict(row) for row in rows], total

    def get_cached_paper_count(self) -> int:
        """Return the number of cached papers."""
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM zotero_papers").fetchone()
        return row["cnt"]

    def get_papers_cache_updated_at(self) -> str | None:
        """Return the most recent cached_at timestamp, or None if cache is empty."""
        row = self._conn.execute(
            "SELECT MAX(cached_at) as latest FROM zotero_papers"
        ).fetchone()
        return row["latest"] if row and row["latest"] else None

    def update_annotation_counts(self, counts: dict[str, int]) -> None:
        """Bulk update annotation counts for cached papers."""
        self._conn.executemany(
            "UPDATE zotero_papers SET annotation_count = ? WHERE key = ?",
            [(count, key) for key, count in counts.items()],
        )
        self._conn.commit()

    def delete_papers_not_in(self, keys: set[str]) -> int:
        """Remove papers from cache that are no longer in Zotero. Returns count deleted."""
        if not keys:
            return 0
        placeholders = ",".join("?" for _ in keys)
        cursor = self._conn.execute(
            f"DELETE FROM zotero_papers WHERE key NOT IN ({placeholders})",
            list(keys),
        )
        self._conn.commit()
        return cursor.rowcount

    # --- Collection cache (zotero_collections table) ---

    def upsert_collections(self, collections: list[dict]) -> None:
        """Bulk upsert collection metadata into the cache."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.executemany(
            """
            INSERT INTO zotero_collections (key, name, parent_collection, num_items, num_collections, cached_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                name              = excluded.name,
                parent_collection = excluded.parent_collection,
                num_items         = excluded.num_items,
                num_collections   = excluded.num_collections,
                cached_at         = excluded.cached_at
            """,
            [
                (
                    c["key"],
                    c.get("name", ""),
                    c.get("parent_collection"),
                    c.get("num_items", 0),
                    c.get("num_collections", 0),
                    now,
                )
                for c in collections
            ],
        )
        self._conn.commit()

    def get_all_cached_collections(self) -> list[dict]:
        """Return all cached collections ordered by name ASC."""
        rows = self._conn.execute(
            "SELECT * FROM zotero_collections ORDER BY name ASC"
        ).fetchall()
        return [
            {
                "key": row["key"],
                "name": row["name"],
                "parent_collection": row["parent_collection"],
                "num_items": row["num_items"],
                "num_collections": row["num_collections"],
            }
            for row in rows
        ]

    def delete_collections_not_in(self, keys: set[str]) -> int:
        """Remove collections from cache that are no longer in Zotero. Returns count deleted."""
        if not keys:
            return 0
        placeholders = ",".join("?" for _ in keys)
        cursor = self._conn.execute(
            f"DELETE FROM zotero_collections WHERE key NOT IN ({placeholders})",
            list(keys),
        )
        self._conn.commit()
        return cursor.rowcount
