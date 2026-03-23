import os
import sqlite3

from src.models import Changeset


# SQLite-backed persistent store for changesets using WAL journal mode.
class ChangesetStore:
    # Initialize SQLite connection with WAL mode and row factory.
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.environ.get("DB_PATH", ".vault-agent.db")
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
        self._maybe_add_source_type_column()

    # Add source_type column to existing tables and backfill from JSON data.
    def _maybe_add_source_type_column(self) -> None:
        cols = [
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(changesets)").fetchall()
        ]
        if "source_type" not in cols:
            self._conn.execute(
                "ALTER TABLE changesets ADD COLUMN source_type TEXT NOT NULL DEFAULT 'web'"
            )
            self._conn.execute(
                "UPDATE changesets SET source_type = json_extract(data, '$.source_type') "
                "WHERE json_extract(data, '$.source_type') IS NOT NULL"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_changesets_source_type ON changesets(source_type)"
            )
            self._conn.commit()

    # Upsert a changeset into the store.
    #
    # Args:
    #     changeset: Changeset to insert or update.
    def set(self, changeset: Changeset) -> None:
        self._conn.execute(
            """
            INSERT INTO changesets (id, status, created_at, data, source_type)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                data   = excluded.data,
                source_type = excluded.source_type
            """,
            (
                changeset.id,
                changeset.status,
                changeset.created_at,
                changeset.model_dump_json(),
                changeset.source_type,
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

    # Retrieve changesets with optional status/source_type filter and pagination.
    #
    # Args:
    #     status: Filter by changeset status (None = all).
    #     offset: Number of rows to skip.
    #     limit: Max rows to return.
    #     source_type: Filter by source type (None = all).
    #
    # Returns:
    #     Tuple of (matching changesets, total count).
    def get_all_filtered(
        self,
        status: str | None = None,
        offset: int = 0,
        limit: int = 25,
        source_type: str | None = None,
    ) -> tuple[list[Changeset], int]:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        total = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM changesets {where}", params
        ).fetchone()["cnt"]
        rows = self._conn.execute(
            f"SELECT data FROM changesets {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [Changeset.model_validate_json(r["data"]) for r in rows], total

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
