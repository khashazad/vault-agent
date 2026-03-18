from src.db.changesets import ChangesetStore
from src.db.batch_jobs import BatchJobStore
from src.db.migration import MigrationStore

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


def get_migration_store() -> MigrationStore:
    global _migration_store
    if _migration_store is None:
        _migration_store = MigrationStore()
    return _migration_store


__all__ = [
    "ChangesetStore",
    "BatchJobStore",
    "MigrationStore",
    "get_changeset_store",
    "get_batch_job_store",
    "get_migration_store",
]
