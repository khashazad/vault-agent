from tests.factories import make_changeset


class TestChangesetStore:
    def test_set_and_get(self, memory_changeset_store):
        cs = make_changeset()
        memory_changeset_store.set(cs)
        retrieved = memory_changeset_store.get(cs.id)
        assert retrieved is not None
        assert retrieved.id == cs.id
        assert retrieved.status == "pending"

    def test_get_nonexistent(self, memory_changeset_store):
        assert memory_changeset_store.get("nonexistent") is None

    def test_get_all(self, memory_changeset_store):
        cs1 = make_changeset()
        cs2 = make_changeset()
        memory_changeset_store.set(cs1)
        memory_changeset_store.set(cs2)
        all_cs = memory_changeset_store.get_all()
        assert len(all_cs) == 2

    def test_upsert_updates_status(self, memory_changeset_store):
        cs = make_changeset()
        memory_changeset_store.set(cs)
        cs.status = "applied"
        memory_changeset_store.set(cs)
        retrieved = memory_changeset_store.get(cs.id)
        assert retrieved.status == "applied"

    def test_delete(self, memory_changeset_store):
        cs = make_changeset()
        memory_changeset_store.set(cs)
        memory_changeset_store.delete(cs.id)
        assert memory_changeset_store.get(cs.id) is None


class TestBatchJobStore:
    def test_set_and_get(self, memory_batch_job_store):
        memory_batch_job_store.set(
            paper_key="KEY1",
            batch_id="batch_123",
            status="pending",
            items_json="[]",
            created_at="2024-01-01T00:00:00Z",
        )
        job = memory_batch_job_store.get("KEY1")
        assert job is not None
        assert job["batch_id"] == "batch_123"
        assert job["status"] == "pending"

    def test_get_nonexistent(self, memory_batch_job_store):
        assert memory_batch_job_store.get("NOPE") is None

    def test_update_status(self, memory_batch_job_store):
        memory_batch_job_store.set(
            paper_key="KEY2",
            batch_id="batch_456",
            status="pending",
            items_json="[]",
            created_at="2024-01-01T00:00:00Z",
        )
        memory_batch_job_store.update_status("KEY2", "completed", "cs-id-123")
        job = memory_batch_job_store.get("KEY2")
        assert job["status"] == "completed"
        assert job["changeset_id"] == "cs-id-123"
