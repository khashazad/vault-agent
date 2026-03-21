from src.db.changesets import ChangesetStore
from src.db.batch_jobs import BatchJobStore
from src.db.migration import MigrationStore
from src.db.settings import SettingsStore

_changeset_store: ChangesetStore | None = None
_batch_job_store: BatchJobStore | None = None
_migration_store: MigrationStore | None = None
_settings_store: SettingsStore | None = None


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


def get_settings_store() -> SettingsStore:
    global _settings_store
    if _settings_store is None:
        _settings_store = SettingsStore()
    return _settings_store


__all__ = [
    "ChangesetStore",
    "BatchJobStore",
    "MigrationStore",
    "SettingsStore",
    "get_changeset_store",
    "get_batch_job_store",
    "get_migration_store",
    "get_settings_store",
]
