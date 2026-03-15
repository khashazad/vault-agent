import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.environ.get("CHANGESET_DB_PATH", ".changesets.db")


# SQLite-backed state tracker for Zotero sync, paper cache, and collection cache.
class ZoteroSyncState:
    # Initialize SQLite connection with WAL mode for Zotero sync state.
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    # Create sync, paper, and collection tables if they don't exist.
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

    # Retrieve the last synced Zotero library version.
    #
    # Returns:
    #     The version number, or None if never synced.
    def get_last_version(self) -> int | None:
        row = self._conn.execute(
            "SELECT last_version FROM zotero_sync_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return row["last_version"]

    # Upsert the Zotero library version and record the current timestamp.
    #
    # Args:
    #     version: Zotero library version number.
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

    # Retrieve the ISO timestamp of the last Zotero sync.
    #
    # Returns:
    #     ISO timestamp string, or None if never synced.
    def get_last_synced(self) -> str | None:
        row = self._conn.execute(
            "SELECT last_synced FROM zotero_sync_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return row["last_synced"]

    # --- Per-paper sync tracking ---

    # Retrieve all paper sync records keyed by paper_key.
    #
    # Returns:
    #     Dict mapping paper_key to sync info (paper_title, last_synced, changeset_id).
    def get_all_paper_syncs(self) -> dict[str, dict]:
        rows = self._conn.execute("SELECT * FROM zotero_paper_sync").fetchall()
        return {
            row["paper_key"]: {
                "paper_title": row["paper_title"],
                "last_synced": row["last_synced"],
                "changeset_id": row["changeset_id"],
            }
            for row in rows
        }

    # Retrieve sync info for a single paper.
    #
    # Args:
    #     paper_key: Zotero paper key.
    #
    # Returns:
    #     Sync info dict, or None if the paper has not been synced.
    def get_paper_sync(self, paper_key: str) -> dict | None:
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

    # Upsert a paper sync record with the current timestamp.
    #
    # Args:
    #     paper_key: Zotero paper key.
    #     paper_title: Title of the paper.
    #     changeset_id: ID of the changeset produced by syncing this paper.
    def set_paper_sync(
        self, paper_key: str, paper_title: str, changeset_id: str
    ) -> None:
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

    # Clear paper sync records that reference a deleted changeset.
    #
    # Args:
    #     changeset_id: The changeset ID being deleted.
    #
    # Returns:
    #     Number of rows cleared.
    def clear_paper_sync_by_changeset(self, changeset_id: str) -> int:
        cursor = self._conn.execute(
            "UPDATE zotero_paper_sync SET last_synced = NULL, changeset_id = NULL WHERE changeset_id = ?",
            (changeset_id,),
        )
        self._conn.commit()
        return cursor.rowcount

    # --- Paper cache (zotero_papers table) ---

    # Bulk upsert paper metadata into the local cache.
    #
    # Args:
    #     papers: List of paper dicts with key, title, authors, doi, etc.
    def upsert_papers(self, papers: list[dict]) -> None:
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

    # Convert a zotero_papers row to a plain dict.
    def _row_to_paper_dict(self, row: sqlite3.Row) -> dict:
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

    # Retrieve all cached papers ordered by year descending, title ascending.
    #
    # Returns:
    #     List of paper dicts.
    def get_all_cached_papers(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM zotero_papers ORDER BY year DESC, title ASC"
        ).fetchall()
        return [self._row_to_paper_dict(row) for row in rows]

    # Retrieve paginated cached papers with optional search and sync status filters.
    #
    # Args:
    #     offset: Number of rows to skip.
    #     limit: Maximum number of rows to return.
    #     search: Optional substring filter on title or authors.
    #     sync_status: Optional filter: "synced" or "unsynced".
    #
    # Returns:
    #     Tuple of (list of paper dicts, total matching count).
    def get_cached_papers_paginated(
        self,
        offset: int = 0,
        limit: int = 25,
        search: str | None = None,
        sync_status: str | None = None,
    ) -> tuple[list[dict], int]:
        conditions: list[str] = []
        params: list = []
        join = ""

        if sync_status in ("synced", "unsynced"):
            join = " LEFT JOIN zotero_paper_sync ps ON p.key = ps.paper_key"
            if sync_status == "synced":
                conditions.append("ps.last_synced IS NOT NULL")
            else:
                conditions.append("ps.last_synced IS NULL AND p.annotation_count > 0")

        if search:
            pattern = f"%{search}%"
            conditions.append("(p.title LIKE ? OR p.authors LIKE ?)")
            params.extend([pattern, pattern])

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        table = "zotero_papers p" if join else "zotero_papers"
        select_cols = "p.*" if join else "*"

        count_row = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM {table}{join}{where}", params
        ).fetchone()
        total = count_row["cnt"]

        rows = self._conn.execute(
            f"SELECT {select_cols} FROM {table}{join}{where} ORDER BY year DESC, title ASC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return [self._row_to_paper_dict(row) for row in rows], total

    # Return the number of cached papers.
    #
    # Returns:
    #     Total count of papers in the cache.
    def get_cached_paper_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM zotero_papers").fetchone()
        return row["cnt"]

    # Retrieve the most recent cached_at timestamp from the paper cache.
    #
    # Returns:
    #     ISO timestamp string, or None if the cache is empty.
    def get_papers_cache_updated_at(self) -> str | None:
        row = self._conn.execute(
            "SELECT MAX(cached_at) as latest FROM zotero_papers"
        ).fetchone()
        return row["latest"] if row and row["latest"] else None

    # Bulk update annotation counts for cached papers.
    #
    # Args:
    #     counts: Dict mapping paper key to annotation count.
    def update_annotation_counts(self, counts: dict[str, int]) -> None:
        self._conn.executemany(
            "UPDATE zotero_papers SET annotation_count = ? WHERE key = ?",
            [(count, key) for key, count in counts.items()],
        )
        self._conn.commit()

    # Remove rows from a table whose key is not in the provided set.
    #
    # Args:
    #     table: SQL table name.
    #     key_column: Column name for the key.
    #     keys: Set of key values to keep.
    #
    # Returns:
    #     Number of rows deleted.
    def _delete_not_in(self, table: str, key_column: str, keys: set[str]) -> int:
        if not keys:
            return 0
        placeholders = ",".join("?" for _ in keys)
        cursor = self._conn.execute(
            f"DELETE FROM {table} WHERE {key_column} NOT IN ({placeholders})",
            list(keys),
        )
        self._conn.commit()
        return cursor.rowcount

    # Remove papers from cache whose keys are not in the provided set.
    #
    # Args:
    #     keys: Set of Zotero paper keys to keep.
    #
    # Returns:
    #     Number of papers deleted.
    def delete_papers_not_in(self, keys: set[str]) -> int:
        return self._delete_not_in("zotero_papers", "key", keys)

    # --- Collection cache (zotero_collections table) ---

    # Bulk upsert collection metadata into the local cache.
    #
    # Args:
    #     collections: List of collection dicts with key, name, parent_collection, etc.
    def upsert_collections(self, collections: list[dict]) -> None:
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

    # Retrieve all cached collections ordered by name ascending.
    #
    # Returns:
    #     List of collection dicts.
    def get_all_cached_collections(self) -> list[dict]:
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

    # Remove collections from cache whose keys are not in the provided set.
    #
    # Args:
    #     keys: Set of Zotero collection keys to keep.
    #
    # Returns:
    #     Number of collections deleted.
    def delete_collections_not_in(self, keys: set[str]) -> int:
        return self._delete_not_in("zotero_collections", "key", keys)
