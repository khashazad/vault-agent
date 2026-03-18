import pytest

from src.db import ChangesetStore, BatchJobStore
import src.db as db_module


@pytest.fixture
def memory_changeset_store():
    """In-memory ChangesetStore for test isolation."""
    s = ChangesetStore(db_path=":memory:")
    # Inject into the module so get_changeset_store() returns it
    old = db_module._changeset_store
    db_module._changeset_store = s
    yield s
    db_module._changeset_store = old
    s.close()


@pytest.fixture
def memory_batch_job_store():
    """In-memory BatchJobStore for test isolation."""
    s = BatchJobStore(db_path=":memory:")
    old = db_module._batch_job_store
    db_module._batch_job_store = s
    yield s
    db_module._batch_job_store = old
    if hasattr(s, "close"):
        s.close()
