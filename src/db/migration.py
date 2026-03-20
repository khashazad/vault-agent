import os
import sqlite3

from src.models import MigrationJob, MigrationNote, TaxonomyProposal


# SQLite-backed store for vault migration jobs, notes, and taxonomies.
class MigrationStore:
    # Initialize SQLite connection with WAL mode and row factory.
    #
    # Args:
    #     db_path: Path to the SQLite database file.
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.environ.get("DB_PATH", ".vault-agent.db")
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    # Create migration_jobs, migration_notes, and taxonomy tables if they don't exist.
    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS migration_jobs (
                id         TEXT PRIMARY KEY,
                status     TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                data       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_migration_jobs_status
                ON migration_jobs(status);

            CREATE TABLE IF NOT EXISTS migration_notes (
                id         TEXT PRIMARY KEY,
                job_id     TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'pending',
                data       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_migration_notes_job_id
                ON migration_notes(job_id);
            CREATE INDEX IF NOT EXISTS idx_migration_notes_status
                ON migration_notes(status);

            CREATE TABLE IF NOT EXISTS taxonomy (
                id         TEXT PRIMARY KEY,
                status     TEXT NOT NULL DEFAULT 'imported',
                created_at TEXT NOT NULL,
                data       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_taxonomy_status
                ON taxonomy(status);
        """)
        self._conn.commit()

    # --- Jobs ---

    # Upsert a migration job into the store.
    #
    # Args:
    #     job: MigrationJob to insert or update.
    def set_job(self, job: MigrationJob) -> None:
        self._conn.execute(
            """
            INSERT INTO migration_jobs (id, status, created_at, data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                data   = excluded.data
            """,
            (job.id, job.status, job.created_at, job.model_dump_json()),
        )
        self._conn.commit()

    # Retrieve a migration job by ID.
    #
    # Args:
    #     job_id: Unique job identifier.
    #
    # Returns:
    #     The matching MigrationJob, or None if not found.
    def get_job(self, job_id: str) -> MigrationJob | None:
        row = self._conn.execute(
            "SELECT data FROM migration_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        return MigrationJob.model_validate_json(row["data"])

    # Update the status field of a migration job.
    #
    # Args:
    #     job_id: Unique job identifier.
    #     status: New status string.
    def update_job_status(self, job_id: str, status: str) -> None:
        job = self.get_job(job_id)
        if job:
            job.status = status  # type: ignore[assignment]
            self.set_job(job)

    # Increment the processed_notes counter for a migration job.
    #
    # Args:
    #     job_id: Unique job identifier.
    def increment_processed(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job:
            job.processed_notes += 1
            self.set_job(job)

    # List migration jobs ordered by creation time (newest first).
    #
    # Args:
    #     status: Optional status filter.
    #     limit: Max rows to return.
    #
    # Returns:
    #     List of matching MigrationJob objects.
    def list_jobs(
        self, status: str | None = None, limit: int = 10
    ) -> list[MigrationJob]:
        where = ""
        params: list = []
        if status:
            where = "WHERE status = ?"
            params.append(status)
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT data FROM migration_jobs {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [MigrationJob.model_validate_json(r["data"]) for r in rows]

    # Reset notes stuck in 'processing' back to 'pending' for a given job.
    #
    # Args:
    #     job_id: Parent job identifier.
    #
    # Returns:
    #     Number of notes reset.
    def reset_stuck_notes(self, job_id: str) -> int:
        notes, _ = self.get_notes_by_job(job_id, status="processing", limit=10000)
        for note in notes:
            note.status = "pending"
            note.error = None
            self.set_note(job_id, note)
        return len(notes)

    # --- Notes ---

    # Upsert a migration note into the store.
    #
    # Args:
    #     job_id: Parent job identifier.
    #     note: MigrationNote to insert or update.
    def set_note(self, job_id: str, note: MigrationNote) -> None:
        self._conn.execute(
            """
            INSERT INTO migration_notes (id, job_id, status, data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                data   = excluded.data
            """,
            (note.id, job_id, note.status, note.model_dump_json()),
        )
        self._conn.commit()

    # Retrieve a migration note by ID.
    #
    # Args:
    #     note_id: Unique note identifier.
    #
    # Returns:
    #     The matching MigrationNote, or None if not found.
    def get_note(self, note_id: str) -> MigrationNote | None:
        row = self._conn.execute(
            "SELECT data FROM migration_notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            return None
        return MigrationNote.model_validate_json(row["data"])

    # Retrieve migration notes for a job with optional status filter and pagination.
    #
    # Args:
    #     job_id: Parent job identifier.
    #     status: Filter by note status (None = all).
    #     offset: Number of rows to skip.
    #     limit: Max rows to return.
    #
    # Returns:
    #     Tuple of (matching notes, total count).
    def get_notes_by_job(
        self,
        job_id: str,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[MigrationNote], int]:
        where = "WHERE job_id = ?"
        params: list = [job_id]
        if status:
            where += " AND status = ?"
            params.append(status)

        total = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM migration_notes {where}", params
        ).fetchone()["cnt"]
        rows = self._conn.execute(
            f"SELECT data FROM migration_notes {where} ORDER BY rowid LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [MigrationNote.model_validate_json(r["data"]) for r in rows], total

    # Update a migration note (delegates to set_note).
    #
    # Args:
    #     job_id: Parent job identifier.
    #     note: MigrationNote with updated fields.
    def update_note(self, job_id: str, note: MigrationNote) -> None:
        self.set_note(job_id, note)

    # --- Taxonomy ---

    # Upsert a taxonomy proposal into the store.
    #
    # Args:
    #     taxonomy: TaxonomyProposal to insert or update.
    def set_taxonomy(self, taxonomy: TaxonomyProposal) -> None:
        self._conn.execute(
            """
            INSERT INTO taxonomy (id, status, created_at, data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                data   = excluded.data
            """,
            (
                taxonomy.id,
                taxonomy.status,
                taxonomy.created_at,
                taxonomy.model_dump_json(),
            ),
        )
        self._conn.commit()

    # Retrieve a taxonomy proposal by ID.
    #
    # Args:
    #     taxonomy_id: Unique taxonomy identifier.
    #
    # Returns:
    #     The matching TaxonomyProposal, or None if not found.
    def get_taxonomy(self, taxonomy_id: str) -> TaxonomyProposal | None:
        row = self._conn.execute(
            "SELECT data FROM taxonomy WHERE id = ?", (taxonomy_id,)
        ).fetchone()
        if row is None:
            return None
        return TaxonomyProposal.model_validate_json(row["data"])

    # Retrieve the most recently created active taxonomy.
    #
    # Returns:
    #     The active TaxonomyProposal, or None if no active taxonomy exists.
    def get_active_taxonomy(self) -> TaxonomyProposal | None:
        row = self._conn.execute(
            "SELECT data FROM taxonomy WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return TaxonomyProposal.model_validate_json(row["data"])

    # Set all active taxonomies to 'curated' status.
    def deactivate_all_taxonomies(self) -> None:
        self._conn.execute(
            "UPDATE taxonomy SET status = 'curated' WHERE status = 'active'"
        )
        self._conn.commit()

    # Close the SQLite connection.
    def close(self) -> None:
        self._conn.close()
