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


changeset_store = ChangesetStore()
