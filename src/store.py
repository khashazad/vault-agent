import os
import sqlite3

from src.models import Changeset

DEFAULT_DB_PATH = os.environ.get("CHANGESET_DB_PATH", ".changesets.db")


# SQLite-backed persistent store for changesets using WAL journal mode.
class ChangesetStore:
    # Initialize SQLite connection with WAL mode and row factory.
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    # Create changesets table and indexes if they don't exist.
    def _create_table(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS changesets (
                id         TEXT PRIMARY KEY,
                status     TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                data       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_changesets_status
                ON changesets(status);
            CREATE INDEX IF NOT EXISTS idx_changesets_created_at
                ON changesets(created_at);
        """)
        self._conn.commit()

    # Upsert a changeset into the store.
    #
    # Args:
    #     changeset: Changeset to insert or update.
    def set(self, changeset: Changeset) -> None:
        self._conn.execute(
            """
            INSERT INTO changesets (id, status, created_at, data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                data   = excluded.data
            """,
            (
                changeset.id,
                changeset.status,
                changeset.created_at,
                changeset.model_dump_json(),
            ),
        )
        self._conn.commit()

    # Retrieve a changeset by ID.
    #
    # Args:
    #     changeset_id: Unique changeset identifier.
    #
    # Returns:
    #     The matching Changeset, or None if not found.
    def get(self, changeset_id: str) -> Changeset | None:
        row = self._conn.execute(
            "SELECT data FROM changesets WHERE id = ?",
            (changeset_id,),
        ).fetchone()
        if row is None:
            return None
        return Changeset.model_validate_json(row["data"])

    # Retrieve changesets with optional status filter and pagination.
    #
    # Args:
    #     status: Filter by changeset status (None = all).
    #     offset: Number of rows to skip.
    #     limit: Max rows to return.
    #
    # Returns:
    #     Tuple of (matching changesets, total count).
    def get_all_filtered(
        self,
        status: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[Changeset], int]:
        if status:
            count_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM changesets WHERE status = ?",
                (status,),
            ).fetchone()
            rows = self._conn.execute(
                "SELECT data FROM changesets WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        else:
            count_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM changesets"
            ).fetchone()
            rows = self._conn.execute(
                "SELECT data FROM changesets ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        total = count_row["cnt"]
        changesets = [Changeset.model_validate_json(row["data"]) for row in rows]
        return changesets, total

    # Retrieve all changesets ordered by created_at descending.
    #
    # Returns:
    #     List of all changesets, newest first.
    def get_all(self) -> list[Changeset]:
        rows = self._conn.execute(
            "SELECT data FROM changesets ORDER BY created_at DESC"
        ).fetchall()
        return [Changeset.model_validate_json(row["data"]) for row in rows]

    # Delete a changeset by ID.
    #
    # Args:
    #     changeset_id: Unique changeset identifier.
    def delete(self, changeset_id: str) -> None:
        self._conn.execute(
            "DELETE FROM changesets WHERE id = ?",
            (changeset_id,),
        )
        self._conn.commit()

    # Close the SQLite connection.
    def close(self) -> None:
        self._conn.close()


# SQLite-backed store for Anthropic Batch API jobs linked to Zotero papers.
class BatchJobStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    def _create_table(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS zotero_batch_jobs (
                paper_key  TEXT PRIMARY KEY,
                batch_id   TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'pending',
                changeset_id TEXT,
                items_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    # Upsert a batch job record.
    def set(
        self,
        paper_key: str,
        batch_id: str,
        status: str,
        items_json: str,
        created_at: str,
        changeset_id: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO zotero_batch_jobs (paper_key, batch_id, status, items_json, created_at, changeset_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(paper_key) DO UPDATE SET
                batch_id = excluded.batch_id,
                status = excluded.status,
                items_json = excluded.items_json,
                created_at = excluded.created_at,
                changeset_id = excluded.changeset_id
            """,
            (paper_key, batch_id, status, items_json, created_at, changeset_id),
        )
        self._conn.commit()

    # Get a batch job by paper key.
    def get(self, paper_key: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM zotero_batch_jobs WHERE paper_key = ?",
            (paper_key,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    # Update status and optionally changeset_id for a batch job.
    def update_status(
        self, paper_key: str, status: str, changeset_id: str | None = None
    ) -> None:
        if changeset_id:
            self._conn.execute(
                "UPDATE zotero_batch_jobs SET status = ?, changeset_id = ? WHERE paper_key = ?",
                (status, changeset_id, paper_key),
            )
        else:
            self._conn.execute(
                "UPDATE zotero_batch_jobs SET status = ? WHERE paper_key = ?",
                (status, paper_key),
            )
        self._conn.commit()


_changeset_store: ChangesetStore | None = None
_batch_job_store: BatchJobStore | None = None


def get_changeset_store() -> ChangesetStore:
    global _changeset_store
    if _changeset_store is None:
        _changeset_store = ChangesetStore()
    return _changeset_store


def get_batch_job_store() -> BatchJobStore:
    global _batch_job_store
    if _batch_job_store is None:
        _batch_job_store = BatchJobStore()
    return _batch_job_store
