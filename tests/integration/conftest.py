import pytest

from src.store import ChangesetStore, BatchJobStore
import src.store as store_module


@pytest.fixture
def memory_changeset_store():
    """In-memory ChangesetStore for test isolation."""
    s = ChangesetStore(db_path=":memory:")
    # Inject into the module so get_changeset_store() returns it
    old = store_module._changeset_store
    store_module._changeset_store = s
    yield s
    store_module._changeset_store = old
    s.close()


@pytest.fixture
def memory_batch_job_store():
    """In-memory BatchJobStore for test isolation."""
    s = BatchJobStore(db_path=":memory:")
    old = store_module._batch_job_store
    store_module._batch_job_store = s
    yield s
    store_module._batch_job_store = old
    if hasattr(s, "close"):
        s.close()
