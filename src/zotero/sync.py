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
                cached_at         TEXT NOT NULL
            );
        """)

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

    def get_all_cached_papers(self) -> list[dict]:
        """Return all cached papers ordered by year DESC, title ASC."""
        rows = self._conn.execute(
            "SELECT * FROM zotero_papers ORDER BY year DESC, title ASC"
        ).fetchall()
        return [
            {
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
            }
            for row in rows
        ]

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
