import os
import sqlite3


# SQLite-backed store for Anthropic Batch API jobs linked to Zotero papers.
class BatchJobStore:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.environ.get("DB_PATH", ".vault-agent.db")
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
        self._conn.execute(
            "UPDATE zotero_batch_jobs SET status = ?, changeset_id = ? WHERE paper_key = ?",
            (status, changeset_id, paper_key),
        )
        self._conn.commit()
