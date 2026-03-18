import os
import sqlite3

from src.models import Changeset, MigrationJob, MigrationNote, TaxonomyProposal

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
        where = "WHERE status = ?" if status else ""
        params = (status,) if status else ()

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


# SQLite-backed store for vault migration jobs, notes, and taxonomies.
class MigrationStore:
    # Initialize SQLite connection with WAL mode and row factory.
    #
    # Args:
    #     db_path: Path to the SQLite database file.
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
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


_changeset_store: ChangesetStore | None = None
_batch_job_store: BatchJobStore | None = None
_migration_store: MigrationStore | None = None


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


# Return the global MigrationStore singleton, creating it on first call.
#
# Returns:
#     Shared MigrationStore instance.
def get_migration_store() -> MigrationStore:
    global _migration_store
    if _migration_store is None:
        _migration_store = MigrationStore()
    return _migration_store
